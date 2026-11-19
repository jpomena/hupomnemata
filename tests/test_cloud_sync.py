"""Unit tests for CloudSyncService (Google Drive appDataFolder sync, snapshots, and conflict resolution)."""

import gzip
import json
import shutil
import sqlite3
from unittest.mock import MagicMock

import pytest

from src.services.cloud_sync_service import (
    MANIFEST_FILE_NAME,
    SNAPSHOT_FILE_NAME,
    CloudSyncService,
    SyncStatus,
)


@pytest.fixture
def sync_service(tmp_path, clean_db):
    """Instantiate a CloudSyncService configured in a temporary sandbox directory."""
    base_dir = tmp_path / "app"
    base_dir.mkdir(parents=True, exist_ok=True)
    config_dir = base_dir / "configs"
    config_dir.mkdir(parents=True, exist_ok=True)

    db_file = base_dir / "test_hupomnemata.db"
    # Create valid SQLite DB by vacuuming the isolated in-memory database.
    with clean_db.connect() as conn:
        conn.exec_driver_sql(f'VACUUM INTO "{db_file.as_posix()}"')

    service = CloudSyncService(base_dir=base_dir, config_dir=config_dir, db_path=db_file)
    return service


def test_get_device_id_persists(sync_service):
    """Device ID should be created once and remain deterministic across calls."""
    dev_id1 = sync_service.get_device_id()
    assert dev_id1 is not None and len(dev_id1) == 36

    dev_id2 = sync_service.get_device_id()
    assert dev_id1 == dev_id2


def test_is_authenticated_false_when_no_token(sync_service):
    """Should return False if token.json is absent."""
    assert sync_service.is_authenticated() is False


def test_logout_clears_token_file(sync_service):
    """Logout should remove token.json from disk."""
    sync_service.token_path.write_text('{"token": "dummy"}', encoding="utf-8")
    assert sync_service.token_path.exists() is True

    result = sync_service.logout()
    assert result is True
    assert sync_service.token_path.exists() is False


def test_create_local_snapshot_and_sha256(sync_service):
    """Atomic VACUUM INTO + Gzip snapshot should produce a valid compressed archive."""
    gz_path, sha_hash = sync_service.create_local_snapshot()

    assert gz_path.exists()
    assert gz_path.name == SNAPSHOT_FILE_NAME
    assert len(sha_hash) == 64

    # Verify that uncompressed file is a valid SQLite database header
    with gzip.open(gz_path, "rb") as f:
        header = f.read(16)
        assert header.startswith(b"SQLite format 3")


def test_create_conflict_backup(sync_service):
    """Safety fork should duplicate current database with dated timestamp."""
    backup_path = sync_service.create_conflict_backup()

    assert backup_path.exists()
    assert "hupomnemata_conflict_" in backup_path.name
    assert backup_path.stat().st_size == sync_service.db_path.stat().st_size


def test_sync_unauthenticated(sync_service):
    """Calling sync without credentials should abort with UNAUTHENTICATED status."""
    res = sync_service.sync()
    assert res.status == SyncStatus.UNAUTHENTICATED


def test_sync_initial_push_mocked(sync_service):
    """When remote appDataFolder has no files, sync should perform initial upload."""
    mock_drive = MagicMock()
    # No files on remote
    mock_drive.files().list().execute.return_value = {"files": []}
    mock_drive.files().create().execute.return_value = {"id": "remote_file_123"}
    sync_service._drive_service = mock_drive
    sync_service.is_authenticated = MagicMock(return_value=True)

    result = sync_service.sync(sync_pdfs=False)

    assert result.status == SyncStatus.SUCCESS
    assert "pushed" in result.message.lower()
    assert (sync_service.sync_dir / MANIFEST_FILE_NAME).exists()
    assert (sync_service.sync_dir / "last_synced_hash.txt").exists()


def test_sync_no_changes_mocked(sync_service):
    """When local hash equals remote manifest hash, status should be NO_CHANGES."""
    # Create local snapshot to get real hash
    _, local_sha = sync_service.create_local_snapshot()
    manifest = sync_service.build_manifest(local_sha)

    mock_drive = MagicMock()
    mock_drive.files().list().execute.side_effect = [
        {"files": [{"id": "meta_1", "name": MANIFEST_FILE_NAME}]},
        {"files": [{"id": "snap_1", "name": SNAPSHOT_FILE_NAME}]},
    ]

    def mock_download(file_id, dest_path):
        dest_path.write_text(json.dumps(manifest), encoding="utf-8")
        return dest_path

    sync_service._download_appdata_file = mock_download
    sync_service._drive_service = mock_drive
    sync_service.is_authenticated = MagicMock(return_value=True)

    result = sync_service.sync(sync_pdfs=False)

    assert result.status == SyncStatus.NO_CHANGES
    assert "already synchronized" in result.message.lower()


def test_sync_conflict_creates_safety_fork(sync_service):
    """When remote has changes from another device and local has divergent changes, trigger safety fork."""
    _, local_sha = sync_service.create_local_snapshot()
    # Record old sync hash to simulate that local was modified since then
    sync_service._set_last_synced_sha256("old_local_hash_before_edits")

    remote_manifest = {
        "manifest_version": "1.0",
        "schema_version": "8793c7031ee3",
        "device_id": "other-device-uuid-9999",
        "timestamp_utc": "2026-11-16T12:00:00Z",
        "db_sha256": "different_remote_sha256_hash",
    }

    mock_drive = MagicMock()
    mock_drive.files().list().execute.side_effect = [
        {"files": [{"id": "meta_1", "name": MANIFEST_FILE_NAME}]},
        {"files": [{"id": "snap_1", "name": SNAPSHOT_FILE_NAME}]},
    ]

    def mock_download(file_id, dest_path):
        dest_path.write_text(json.dumps(remote_manifest), encoding="utf-8")
        return dest_path

    sync_service._download_appdata_file = mock_download
    sync_service._drive_service = mock_drive
    sync_service.is_authenticated = MagicMock(return_value=True)

    result = sync_service.sync(sync_pdfs=False)

    assert result.status == SyncStatus.CONFLICT
    assert result.conflict_backup_path is not None
    assert "hupomnemata_conflict_" in result.conflict_backup_path


def test_sync_pull_remote_changes(sync_service, tmp_path, clean_db):
    """When remote is ahead and local has no divergent edits, download and restore."""
    _, local_sha = sync_service.create_local_snapshot()
    sync_service._set_last_synced_sha256(local_sha)

    # Create dummy remote snapshot
    dummy_remote_db = tmp_path / "remote.db"
    with clean_db.connect() as conn:
        conn.exec_driver_sql(f'VACUUM INTO "{dummy_remote_db.as_posix()}"')

    with sqlite3.connect(dummy_remote_db) as s_conn:
        s_conn.execute("CREATE TABLE remote_update_test (id INTEGER PRIMARY KEY)")
        s_conn.commit()

    remote_gz = tmp_path / "remote_snapshot.db.gz"
    with open(dummy_remote_db, "rb") as f_in, open(remote_gz, "wb") as raw_out:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw_out, mtime=0.0) as f_out:
            shutil.copyfileobj(f_in, f_out)
    remote_sha = sync_service.compute_sha256(remote_gz)

    remote_manifest = {
        "manifest_version": "1.0",
        "schema_version": sync_service.get_current_schema_version(),
        "device_id": "laptop-b-uuid",
        "timestamp_utc": "2026-11-16T12:00:00Z",
        "db_sha256": remote_sha,
    }

    mock_drive = MagicMock()
    mock_drive.files().list().execute.side_effect = [
        {"files": [{"id": "meta_1", "name": MANIFEST_FILE_NAME}]},
        {"files": [{"id": "snap_1", "name": SNAPSHOT_FILE_NAME}]},
    ]

    def mock_download(file_id, dest_path):
        if "remote_manifest" in dest_path.name:
            dest_path.write_text(json.dumps(remote_manifest), encoding="utf-8")
        else:
            shutil.copy2(remote_gz, dest_path)
        return dest_path

    sync_service._download_appdata_file = mock_download
    sync_service._drive_service = mock_drive
    sync_service.is_authenticated = MagicMock(return_value=True)

    result = sync_service.sync(sync_pdfs=False)

    assert result.status == SyncStatus.SUCCESS
    assert "updated from google drive" in result.message.lower()
    assert sync_service._get_last_synced_sha256() == remote_sha

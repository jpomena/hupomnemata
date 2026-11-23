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


def test_loopback_oauth_survives_empty_preconnect(monkeypatch):
    """LibreWolf abre uma conexão vazia antes do GET real; o fluxo deve continuar."""
    import socket
    import threading
    import time
    import urllib.request
    from urllib.parse import urlparse

    from src.services import cloud_sync_service as module

    class FakeFlow:
        redirect_uri = None
        credentials = object()

        def authorization_url(self, **kwargs):
            self.auth_kwargs = kwargs
            return "https://accounts.example/auth", "state"

        def fetch_token(self, authorization_response):
            self.callback = authorization_response

    flow = FakeFlow()

    def fake_open(url, new=1, autoraise=True):
        port = urlparse(flow.redirect_uri).port

        def hit():
            with socket.create_connection(("127.0.0.1", port)):
                pass
            time.sleep(0.05)
            urllib.request.urlopen(
                flow.redirect_uri + "?code=abc&state=state", timeout=2
            ).read()

        threading.Thread(target=hit, daemon=True).start()
        return True

    monkeypatch.setattr(module.webbrowser, "open", fake_open)
    callback = module._run_loopback_oauth(flow, timeout_seconds=5)
    assert callback.endswith("/?code=abc&state=state")
    assert flow.auth_kwargs["access_type"] == "offline"
    assert flow.auth_kwargs["prompt"] == "consent"


def test_authenticate_uses_tolerant_loopback(sync_service, tmp_path, monkeypatch):
    """authenticate deve usar o servidor tolerante e trocar o código pelo token."""
    creds_file = tmp_path / "credentials.json"
    creds_file.write_text('{"installed": {}}', encoding="utf-8")
    captured = {}

    class FakeFlow:
        credentials = object()

        def fetch_token(self, authorization_response):
            captured["response"] = authorization_response

    def fake_loopback(flow, timeout_seconds):
        captured["timeout"] = timeout_seconds
        return "http://127.0.0.1:1234/?code=abc&state=state"

    monkeypatch.setattr(
        "src.services.cloud_sync_service.InstalledAppFlow.from_client_secrets_file",
        lambda *args, **kwargs: FakeFlow(),
    )
    monkeypatch.setattr(
        "src.services.cloud_sync_service._run_loopback_oauth", fake_loopback
    )
    monkeypatch.setattr(
        sync_service, "_save_credentials", lambda creds: captured.setdefault("saved", True)
    )

    assert sync_service.authenticate(client_secrets_path=creds_file) is True
    assert captured["timeout"] == 600
    assert captured["response"].startswith("https://127.0.0.1:1234/")
    assert captured.get("saved") is True


def test_first_sync_empty_local_pulls_remote(sync_service, monkeypatch, tmp_path):
    """Primeira sincronização com banco local vazio deve baixar a nuvem."""
    monkeypatch.setattr(sync_service, "is_authenticated", lambda: True)
    monkeypatch.setattr(
        sync_service,
        "create_local_snapshot",
        lambda: (tmp_path / "local.db.gz", "localhash"),
    )
    monkeypatch.setattr(sync_service, "_get_last_synced_sha256", lambda: None)
    monkeypatch.setattr(sync_service, "_local_has_data", lambda: False)
    monkeypatch.setattr(
        sync_service, "_find_appdata_file", lambda name: {"id": f"id-{name}"}
    )

    remote_manifest = {"db_sha256": "remotehash", "device_id": "outra-estacao"}

    def fake_download(file_id, dest):
        if "manifest" in file_id:
            dest.write_text(json.dumps(remote_manifest), encoding="utf-8")
        else:
            dest.write_bytes(b"snapshot")
        return dest

    monkeypatch.setattr(sync_service, "_download_appdata_file", fake_download)
    monkeypatch.setattr(sync_service, "compute_sha256", lambda path: "remotehash")
    restored = {}
    monkeypatch.setattr(
        sync_service,
        "restore_from_snapshot",
        lambda path: restored.setdefault("path", path),
    )
    uploads = []
    monkeypatch.setattr(
        sync_service,
        "_upload_appdata_file",
        lambda *args, **kwargs: uploads.append(args),
    )
    monkeypatch.setattr(sync_service, "_set_last_synced_sha256", lambda value: None)

    result = sync_service.sync()
    assert result.status == SyncStatus.SUCCESS
    assert "updated from Google Drive" in result.message
    assert restored.get("path") is not None
    assert uploads == []


def test_first_sync_with_local_data_requires_explicit_choice(
    sync_service, monkeypatch, tmp_path
):
    """Primeira sincronização com dados locais não pode sobrescrever a nuvem."""
    monkeypatch.setattr(sync_service, "is_authenticated", lambda: True)
    monkeypatch.setattr(
        sync_service,
        "create_local_snapshot",
        lambda: (tmp_path / "local.db.gz", "localhash"),
    )
    monkeypatch.setattr(sync_service, "_get_last_synced_sha256", lambda: None)
    monkeypatch.setattr(sync_service, "_local_has_data", lambda: True)
    monkeypatch.setattr(
        sync_service, "_find_appdata_file", lambda name: {"id": f"id-{name}"}
    )

    def fake_download(file_id, dest):
        dest.write_text(
            json.dumps({"db_sha256": "remotehash", "device_id": "outra-estacao"}),
            encoding="utf-8",
        )
        return dest

    monkeypatch.setattr(sync_service, "_download_appdata_file", fake_download)
    backup = tmp_path / "conflict.db"
    monkeypatch.setattr(sync_service, "create_conflict_backup", lambda: backup)
    uploads = []
    monkeypatch.setattr(
        sync_service,
        "_upload_appdata_file",
        lambda *args, **kwargs: uploads.append(args),
    )

    result = sync_service.sync()
    assert result.status == SyncStatus.CONFLICT
    assert result.conflict_backup_path == str(backup)
    assert uploads == []


def test_partial_remote_never_overwrites_empty_local(sync_service, monkeypatch, tmp_path):
    """Nuvem com manifesto mas sem snapshot não pode ser sobrescrita por engano."""
    monkeypatch.setattr(sync_service, "is_authenticated", lambda: True)
    monkeypatch.setattr(
        sync_service,
        "create_local_snapshot",
        lambda: (tmp_path / "local.db.gz", "localhash"),
    )
    monkeypatch.setattr(sync_service, "_local_has_data", lambda: False)

    def fake_find(name):
        if name == MANIFEST_FILE_NAME:
            return {"id": "manifest_id"}
        return None

    monkeypatch.setattr(sync_service, "_find_appdata_file", fake_find)
    uploads = []
    monkeypatch.setattr(
        sync_service,
        "_upload_appdata_file",
        lambda *args, **kwargs: uploads.append(args),
    )

    result = sync_service.sync()
    assert result.status == SyncStatus.ERROR
    assert "incompleta" in result.message
    assert uploads == []


def test_force_pull_refuses_empty_remote_when_local_has_data(
    sync_service, monkeypatch, tmp_path
):
    """'Manter Nuvem' não pode apagar a base local se a nuvem estiver vazia."""
    monkeypatch.setattr(sync_service, "is_authenticated", lambda: True)
    monkeypatch.setattr(
        sync_service,
        "create_local_snapshot",
        lambda: (tmp_path / "local.db.gz", "localhash"),
    )
    monkeypatch.setattr(sync_service, "_get_last_synced_sha256", lambda: None)
    monkeypatch.setattr(sync_service, "_local_has_data", lambda: True)
    monkeypatch.setattr(sync_service, "_snapshot_has_data", lambda path: False)
    monkeypatch.setattr(
        sync_service, "_find_appdata_file", lambda name: {"id": f"id-{name}"}
    )

    def fake_download(file_id, dest):
        if "manifest" in file_id:
            dest.write_text(
                json.dumps({"db_sha256": "remotehash", "device_id": "outra"}),
                encoding="utf-8",
            )
        else:
            dest.write_bytes(b"snapshot")
        return dest

    monkeypatch.setattr(sync_service, "_download_appdata_file", fake_download)
    monkeypatch.setattr(sync_service, "compute_sha256", lambda path: "remotehash")
    restored = []
    monkeypatch.setattr(
        sync_service,
        "restore_from_snapshot",
        lambda path: restored.append(path),
    )

    result = sync_service.sync(force_pull=True)
    assert result.status == SyncStatus.ERROR
    assert "nuvem está vazia" in result.message
    assert restored == []


def test_delete_remote_database_removes_manifest_snapshot_and_markers(
    sync_service, monkeypatch
):
    """Apagar o banco remoto remove manifesto, snapshot e marcadores locais."""
    drive = MagicMock()
    sync_service.get_drive_service = MagicMock(return_value=drive)
    monkeypatch.setattr(
        sync_service,
        "_find_appdata_file",
        lambda name: {"id": f"id-{name}"},
    )

    for name in (
        "last_synced_hash.txt",
        "remote_manifest.json",
        SNAPSHOT_FILE_NAME,
        "downloaded_snapshot.db.gz",
    ):
        (sync_service.sync_dir / name).write_bytes(b"x")

    deleted = sync_service.delete_remote_database()

    assert set(deleted) == {MANIFEST_FILE_NAME, SNAPSHOT_FILE_NAME}
    assert drive.files.return_value.delete.call_count == 2
    assert not (sync_service.sync_dir / "last_synced_hash.txt").exists()
    assert not (sync_service.sync_dir / "remote_manifest.json").exists()
    assert not (sync_service.sync_dir / SNAPSHOT_FILE_NAME).exists()
    assert not (sync_service.sync_dir / "downloaded_snapshot.db.gz").exists()

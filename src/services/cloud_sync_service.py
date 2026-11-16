"""Cloud synchronization service utilizing user personal Google Drive (appDataFolder).

Zero infrastructure cost architecture leveraging OAuth2 Desktop Client credentials,
atomic SQLite VACUUM snapshots, Alembic schema versioning, and Safety Fork conflict resolution.
"""

import gzip
import hashlib
import json
import shutil
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import Resource, build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from sqlalchemy import text

from src.configs.settings import CONFIG_DIR
from src.db.db import DATABASE_PATH, apply_migrations, engine
from src.services.pdf_service import DEFAULT_PDF_STORAGE_DIR
from src.utils.error_log import log_exception

if getattr(sys, "frozen", False):
    _BASE_DIR = Path(sys.executable).parent
else:
    _BASE_DIR = Path(__file__).resolve().parents[2]

SCOPES = ["https://www.googleapis.com/auth/drive.appdata"]
SNAPSHOT_FILE_NAME = "snapshot.db.gz"
MANIFEST_FILE_NAME = "sync_manifest.json"


class SyncStatus(str, Enum):
    """Synchronization outcome status codes."""

    SUCCESS = "success"
    NO_CHANGES = "no_changes"
    CONFLICT = "conflict"
    UNAUTHENTICATED = "unauthenticated"
    ERROR = "error"


@dataclass
class SyncResult:
    """Represents the canonical outcome of a synchronization operation."""

    status: SyncStatus
    message: str
    timestamp_utc: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    conflict_backup_path: str | None = None
    uploaded_pdfs: int = 0
    downloaded_pdfs: int = 0
    details: dict[str, Any] = field(default_factory=dict)


class CloudSyncService:
    """Orchestrates secure, atomic cloud synchronization with Google Drive."""

    def __init__(
        self,
        base_dir: Path | None = None,
        config_dir: Path | None = None,
        db_path: Path | None = None,
    ) -> None:
        self.base_dir = Path(base_dir or _BASE_DIR)
        self.config_dir = Path(config_dir or CONFIG_DIR)
        self.db_path = Path(db_path or DATABASE_PATH)
        self.sync_dir = self.base_dir / "data" / "sync"
        self.sync_dir.mkdir(parents=True, exist_ok=True)
        self.pdf_storage_dir = Path(DEFAULT_PDF_STORAGE_DIR)

        self.token_path = self.config_dir / "token.json"
        self.bundled_credentials_path = self.config_dir / "credentials.json"
        self.user_credentials_path = self.config_dir / "credentials_user.json"

        self._drive_service: Resource | None = None

    def get_device_id(self) -> str:
        """Retrieve persistent device identifier or generate one if absent."""
        device_file = self.sync_dir / "device_id.txt"
        if device_file.exists():
            content = device_file.read_text(encoding="utf-8").strip()
            if content:
                return content

        new_id = str(uuid.uuid4())
        device_file.write_text(new_id, encoding="utf-8")
        return new_id

    def is_authenticated(self) -> bool:
        """Check whether valid Google Drive credentials exist."""
        if not self.token_path.exists():
            return False

        try:
            creds = Credentials.from_authorized_user_file(
                str(self.token_path), SCOPES
            )
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                self.token_path.write_text(creds.to_json(), encoding="utf-8")
            return bool(creds and creds.valid)
        except Exception as error:
            log_exception("Failed checking Google Drive credentials", error)
            return False

    def authenticate(self, client_secrets_path: Path | None = None) -> bool:
        """Run interactive local server OAuth2 authentication flow."""
        creds_file = (
            client_secrets_path
            or (self.user_credentials_path if self.user_credentials_path.exists() else None)
            or self.bundled_credentials_path
        )

        if not creds_file or not creds_file.exists():
            raise FileNotFoundError(
                f"Google Drive client credentials file not found at: {creds_file}"
            )

        try:
            flow = InstalledAppFlow.from_client_secrets_file(str(creds_file), SCOPES)
            creds = flow.run_local_server(port=0)
            self.token_path.write_text(creds.to_json(), encoding="utf-8")
            self._drive_service = None
            return True
        except Exception as error:
            log_exception("Failed during Google OAuth2 authentication flow", error)
            raise

    def logout(self) -> bool:
        """Purge saved authentication tokens."""
        self._drive_service = None
        if self.token_path.exists():
            self.token_path.unlink()
            return True
        return False

    def get_drive_service(self) -> Resource:
        """Initialize or return cached Google Drive v3 API resource."""
        if self._drive_service is not None:
            return self._drive_service

        if not self.token_path.exists():
            raise RuntimeError("Cannot build Drive service: Unauthenticated.")

        creds = Credentials.from_authorized_user_file(
            str(self.token_path), SCOPES
        )
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            self.token_path.write_text(creds.to_json(), encoding="utf-8")

        self._drive_service = build("drive", "v3", credentials=creds)
        return self._drive_service

    @staticmethod
    def compute_sha256(file_path: Path) -> str:
        """Calculate cryptographic SHA-256 hash of a file."""
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    def create_local_snapshot(self) -> tuple[Path, str]:
        """Generate an atomic, cold SQLite snapshot via VACUUM INTO and gzip compress it."""
        temp_db_path = self.sync_dir / "temp_vacuum.db"
        if temp_db_path.exists():
            temp_db_path.unlink()

        try:
            with engine.connect() as conn:
                conn.exec_driver_sql(f'VACUUM INTO "{temp_db_path.as_posix()}"')

            gz_path = self.sync_dir / SNAPSHOT_FILE_NAME
            with open(temp_db_path, "rb") as src_file, open(gz_path, "wb") as raw_out:
                with gzip.GzipFile(filename="", mode="wb", fileobj=raw_out, mtime=0.0) as gz_file:
                    shutil.copyfileobj(src_file, gz_file)

            sha256_hash = self.compute_sha256(gz_path)
            return gz_path, sha256_hash
        finally:
            if temp_db_path.exists():
                temp_db_path.unlink()

    def restore_from_snapshot(self, gz_path: Path) -> None:
        """Decompress a remote snapshot and atomically replace local database."""
        temp_restored = self.sync_dir / "temp_restored.db"
        if temp_restored.exists():
            temp_restored.unlink()

        with gzip.open(gz_path, "rb") as gz_file, open(temp_restored, "wb") as dst_file:
            shutil.copyfileobj(gz_file, dst_file)

        # Dispose active connection pool before atomic file replacement
        engine.dispose()
        shutil.copy2(temp_restored, self.db_path)
        temp_restored.unlink()

        # Execute Alembic migrations to ensure schema parity if remote was newer
        apply_migrations()

    def create_conflict_backup(self) -> Path:
        """Create dated safety fork of the current local database."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.base_dir / "data" / f"hupomnemata_conflict_{timestamp}.db"
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self.db_path, backup_path)
        return backup_path

    def get_current_schema_version(self) -> str:
        """Query the active Alembic revision from database."""
        try:
            with engine.connect() as conn:
                result = conn.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar()
                return str(result or "unknown")
        except Exception:
            return "unknown"

    def build_manifest(self, db_sha256: str) -> dict[str, Any]:
        """Construct canonical sync manifest."""
        return {
            "manifest_version": "1.0",
            "schema_version": self.get_current_schema_version(),
            "device_id": self.get_device_id(),
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "db_sha256": db_sha256,
        }

    def _find_appdata_file(self, filename: str) -> dict[str, Any] | None:
        """Find a file inside Google Drive appDataFolder by name."""
        service = self.get_drive_service()
        response = service.files().list(
            spaces="appDataFolder",
            q=f"name = '{filename}' and trashed = false",
            fields="files(id, name, modifiedTime, size)",
            pageSize=1,
        ).execute()
        files = response.get("files", [])
        return files[0] if files else None

    def _upload_appdata_file(
        self,
        local_path: Path,
        remote_name: str,
        mime_type: str = "application/octet-stream",
    ) -> str:
        """Upload or update a file in the appDataFolder."""
        service = self.get_drive_service()
        existing = self._find_appdata_file(remote_name)
        media = MediaFileUpload(str(local_path), mimetype=mime_type, resumable=True)

        if existing:
            updated = service.files().update(
                fileId=existing["id"],
                media_body=media,
                fields="id",
            ).execute()
            return str(updated["id"])

        created = service.files().create(
            body={"name": remote_name, "parents": ["appDataFolder"]},
            media_body=media,
            fields="id",
        ).execute()
        return str(created["id"])

    def _download_appdata_file(self, file_id: str, dest_path: Path) -> Path:
        """Download file content from Google Drive."""
        service = self.get_drive_service()
        request = service.files().get_media(fileId=file_id)
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        with open(dest_path, "wb") as f:
            downloader = MediaIoBaseDownload(f, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()

        return dest_path

    def _get_last_synced_sha256(self) -> str | None:
        """Retrieve the SHA-256 hash recorded during the last successful sync."""
        marker = self.sync_dir / "last_synced_hash.txt"
        if marker.exists():
            return marker.read_text(encoding="utf-8").strip()
        return None

    def _set_last_synced_sha256(self, sha256_hash: str) -> None:
        """Save the SHA-256 hash of the most recent sync."""
        marker = self.sync_dir / "last_synced_hash.txt"
        marker.write_text(sha256_hash, encoding="utf-8")

    def sync(
        self,
        sync_pdfs: bool = False,
        force_push: bool = False,
        force_pull: bool = False,
    ) -> SyncResult:
        """Execute full two-tier cloud synchronization.

        1. Tier 1: Core Database Snapshot & Manifest with Safety Fork on divergence.
        2. Tier 2: Differential PDF synchronization based on SHA-256 deduplication.
        """
        if not self.is_authenticated():
            return SyncResult(
                status=SyncStatus.UNAUTHENTICATED,
                message="Google Drive is not authenticated.",
            )

        try:
            local_gz, local_sha256 = self.create_local_snapshot()
            remote_manifest_meta = self._find_appdata_file(MANIFEST_FILE_NAME)
            remote_snapshot_meta = self._find_appdata_file(SNAPSHOT_FILE_NAME)

            # Scenario A: Initial cloud upload (remote is blank or force push requested)
            if not remote_manifest_meta or not remote_snapshot_meta or force_push:
                manifest = self.build_manifest(local_sha256)
                manifest_path = self.sync_dir / MANIFEST_FILE_NAME
                manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

                self._upload_appdata_file(local_gz, SNAPSHOT_FILE_NAME)
                self._upload_appdata_file(manifest_path, MANIFEST_FILE_NAME, "application/json")
                self._set_last_synced_sha256(local_sha256)

                uploaded_pdfs = 0
                if sync_pdfs:
                    uploaded_pdfs, _ = self.sync_pdf_storage()

                return SyncResult(
                    status=SyncStatus.SUCCESS,
                    message="Initial database state successfully pushed to Google Drive.",
                    uploaded_pdfs=uploaded_pdfs,
                )

            # Download and analyze remote manifest
            remote_manifest_path = self.sync_dir / "remote_manifest.json"
            self._download_appdata_file(remote_manifest_meta["id"], remote_manifest_path)
            remote_manifest = json.loads(remote_manifest_path.read_text(encoding="utf-8"))
            remote_sha256 = remote_manifest.get("db_sha256", "")
            remote_device = remote_manifest.get("device_id", "")
            local_device = self.get_device_id()
            last_synced_sha256 = self._get_last_synced_sha256()

            # Scenario B: Hashes are identical
            if local_sha256 == remote_sha256 and not force_pull:
                uploaded_pdfs, downloaded_pdfs = (0, 0)
                if sync_pdfs:
                    uploaded_pdfs, downloaded_pdfs = self.sync_pdf_storage()

                return SyncResult(
                    status=SyncStatus.NO_CHANGES,
                    message="Database is already synchronized with Google Drive.",
                    uploaded_pdfs=uploaded_pdfs,
                    downloaded_pdfs=downloaded_pdfs,
                )

            # Scenario C: Conflict / Divergence Detection
            # Remote differs from local, originated from a different machine, and local changed since last sync
            is_divergent = (
                remote_device != local_device
                and last_synced_sha256 is not None
                and local_sha256 != last_synced_sha256
                and not force_pull
            )

            if is_divergent:
                conflict_backup = self.create_conflict_backup()
                return SyncResult(
                    status=SyncStatus.CONFLICT,
                    message="Conflict detected: cloud version has changes from another device.",
                    conflict_backup_path=str(conflict_backup),
                    details={"remote_manifest": remote_manifest, "local_sha256": local_sha256},
                )

            # Scenario D: Pull remote changes (remote is ahead, or force pull requested)
            if force_pull or (last_synced_sha256 == local_sha256 and local_sha256 != remote_sha256):
                downloaded_gz = self.sync_dir / "downloaded_snapshot.db.gz"
                self._download_appdata_file(remote_snapshot_meta["id"], downloaded_gz)
                downloaded_sha = self.compute_sha256(downloaded_gz)

                if downloaded_sha != remote_sha256:
                    raise ValueError("Remote snapshot checksum verification failed.")

                self.restore_from_snapshot(downloaded_gz)
                self._set_last_synced_sha256(remote_sha256)

                uploaded_pdfs, downloaded_pdfs = (0, 0)
                if sync_pdfs:
                    uploaded_pdfs, downloaded_pdfs = self.sync_pdf_storage()

                return SyncResult(
                    status=SyncStatus.SUCCESS,
                    message="Database successfully updated from Google Drive.",
                    uploaded_pdfs=uploaded_pdfs,
                    downloaded_pdfs=downloaded_pdfs,
                )

            # Scenario E: Push local changes (local modified, same device or fast-forward)
            manifest = self.build_manifest(local_sha256)
            manifest_path = self.sync_dir / MANIFEST_FILE_NAME
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

            self._upload_appdata_file(local_gz, SNAPSHOT_FILE_NAME)
            self._upload_appdata_file(manifest_path, MANIFEST_FILE_NAME, "application/json")
            self._set_last_synced_sha256(local_sha256)

            uploaded_pdfs, downloaded_pdfs = (0, 0)
            if sync_pdfs:
                uploaded_pdfs, downloaded_pdfs = self.sync_pdf_storage()

            return SyncResult(
                status=SyncStatus.SUCCESS,
                message="Local changes successfully uploaded to Google Drive.",
                uploaded_pdfs=uploaded_pdfs,
                downloaded_pdfs=downloaded_pdfs,
            )

        except Exception as error:
            log_exception("Unhandled error during cloud sync", error)
            return SyncResult(
                status=SyncStatus.ERROR,
                message=f"Cloud synchronization failed: {error}",
            )

    def sync_pdf_storage(self) -> tuple[int, int]:
        """Perform differential two-way synchronization of PDF documents."""
        service = self.get_drive_service()
        uploaded_count = 0
        downloaded_count = 0

        # Query all PDF documents stored in appDataFolder
        response = service.files().list(
            spaces="appDataFolder",
            q="name contains 'pdf_' and trashed = false",
            fields="files(id, name, size)",
            pageSize=1000,
        ).execute()

        remote_pdfs = {f["name"]: f["id"] for f in response.get("files", [])}
        local_pdfs = {}

        if self.pdf_storage_dir.exists():
            for pdf_file in self.pdf_storage_dir.glob("*.pdf"):
                local_pdfs[f"pdf_{pdf_file.name}"] = pdf_file

        # Upload local PDFs missing on cloud
        for remote_name, local_path in local_pdfs.items():
            if remote_name not in remote_pdfs:
                self._upload_appdata_file(local_path, remote_name, "application/pdf")
                uploaded_count += 1

        # Download remote PDFs missing locally
        for remote_name, file_id in remote_pdfs.items():
            if remote_name not in local_pdfs:
                clean_name = remote_name.removeprefix("pdf_")
                dest = self.pdf_storage_dir / clean_name
                self._download_appdata_file(file_id, dest)
                downloaded_count += 1

        return uploaded_count, downloaded_count

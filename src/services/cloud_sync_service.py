"""Cloud synchronization service utilizing user personal Google Drive (appDataFolder).

Zero infrastructure cost architecture leveraging OAuth2 Desktop Client credentials,
atomic SQLite VACUUM snapshots, Alembic schema versioning, and Safety Fork conflict resolution.
"""

import gzip
import hashlib
import json
import logging
import os
import shutil
from contextlib import contextmanager
import sqlite3
import sys
import threading
import time
import uuid
import webbrowser
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow, WSGITimeoutError
from googleapiclient.discovery import Resource, build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

from src.configs.paths import resolve_data_dir, resolve_pdf_storage_dir
from src.configs.settings import CONFIG_DIR
from src.db.db import DATABASE_PATH, apply_migrations
from src.services.secret_store import FileBackend, SecretStore
from src.utils.error_log import log_exception

if getattr(sys, "frozen", False):
    _BASE_DIR = Path(sys.executable).parent
else:
    _BASE_DIR = Path(__file__).resolve().parents[2]

SCOPES = ["https://www.googleapis.com/auth/drive.appdata"]
SNAPSHOT_FILE_NAME = "snapshot.db.gz"
MANIFEST_FILE_NAME = "sync_manifest.json"
TOKEN_SECRET_NAME = "google_drive_token"

logger = logging.getLogger("hupomnemata.cloud_sync")

OAUTH_TIMEOUT_SECONDS = 600
OAUTH_SUCCESS_BODY = (
    '<!doctype html><html lang="pt-BR"><meta charset="utf-8">'
    '<title>Hupomnêmata</title><body style="font-family:sans-serif;padding:2rem">'
    '<h1>Autenticação concluída</h1>'
    '<p>Você já pode fechar esta janela e voltar ao Hupomnêmata.</p>'
    '</body></html>'
).encode('utf-8')


class _OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Aceita conexões especulativas e só encerra no callback real."""

    server: '_OAuthCallbackServer'

    def do_GET(self) -> None:
        query = parse_qs(urlparse(self.path).query)
        if 'code' in query or 'error' in query:
            self.server.callback_path = self.path
            body = OAUTH_SUCCESS_BODY
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        body = b'Not found'
        self.send_response(404)
        self.send_header('Content-Type', 'text/plain; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        logger.debug('OAuth callback: ' + format, *args)


class _OAuthCallbackServer(ThreadingHTTPServer):
    """Servidor loopback concorrente: preconnects vazios não matam o fluxo."""

    daemon_threads = True
    allow_reuse_address = False
    callback_path: str | None = None


def _run_loopback_oauth(
    flow: InstalledAppFlow,
    timeout_seconds: int = OAUTH_TIMEOUT_SECONDS,
) -> str:
    """Executa o consentimento e devolve a URL de callback válida.

    O LibreWolf abre uma conexão TCP especulativa vazia antes do GET real.
    Um servidor de requisição única (como ``run_local_server``) consome essa
    conexão e encerra; aqui o servidor é concorrente e ignora conexões sem
    ``code``/``error`` até o callback verdadeiro ou o timeout.
    """
    server = _OAuthCallbackServer(('127.0.0.1', 0), _OAuthCallbackHandler)
    server.timeout = 0.5
    try:
        flow.redirect_uri = f'http://127.0.0.1:{server.server_port}/'
        auth_url, _ = flow.authorization_url(
            access_type='offline',
            prompt='consent',
        )
        logger.info('Abrindo o navegador para o consentimento Google.')
        webbrowser.open(auth_url, new=1, autoraise=True)

        deadline = time.monotonic() + timeout_seconds
        while server.callback_path is None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise WSGITimeoutError(
                    'Timed out waiting for response from authorization server'
                )
            server.timeout = min(0.5, remaining)
            server.handle_request()

        callback = f'http://127.0.0.1:{server.server_port}{server.callback_path}'
        if 'error=' in callback:
            raise RuntimeError(
                'A autorização foi recusada no navegador. Tente novamente.'
            )
        return callback
    finally:
        server.server_close()


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
    direction: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


class CloudSyncService:
    """Orchestrates secure, atomic cloud synchronization with Google Drive."""

    def __init__(
        self,
        base_dir: Path | None = None,
        config_dir: Path | None = None,
        db_path: Path | None = None,
        secret_store: SecretStore | None = None,
    ) -> None:
        self._explicit_base_dir = base_dir is not None
        self.base_dir = (
            Path(base_dir) if base_dir is not None else resolve_data_dir()
        )
        self.config_dir = Path(config_dir or CONFIG_DIR)
        self.db_path = Path(db_path or DATABASE_PATH)
        self.sync_dir = (
            self.base_dir / "data" / "sync"
            if base_dir is not None
            else resolve_data_dir() / "sync"
        )
        self.sync_dir.mkdir(parents=True, exist_ok=True)
        self.pdf_storage_dir = resolve_pdf_storage_dir()

        self.token_path = self.config_dir / "token.json"
        self.bundled_credentials_path = self.config_dir / "credentials.json"
        self.user_credentials_path = self.config_dir / "credentials_user.json"

        if secret_store is not None:
            self.secret_store = secret_store
        elif config_dir is not None and self.config_dir != CONFIG_DIR:
            # Instância isolada (testes): cofre de arquivo, sem tocar no SO.
            fallback = self.config_dir / "secrets.json"
            self.secret_store = SecretStore(
                fallback_path=fallback,
                backend=FileBackend(fallback),
            )
        else:
            self.secret_store = SecretStore()

        self._drive_service: Resource | None = None
        self._sync_lock = threading.Lock()

    # ── credenciais OAuth ─────────────────────────────────────

    def _load_credentials(self) -> Credentials | None:
        """Lê o token do cofre; migra ``token.json`` legado e o remove."""
        raw = self.secret_store.get_secret(TOKEN_SECRET_NAME)
        if not raw and self.token_path.exists():
            try:
                raw = self.token_path.read_text(encoding='utf-8')
                if raw.strip():
                    self.secret_store.set_secret(TOKEN_SECRET_NAME, raw)
                    self.token_path.unlink()
                    logger.info(
                        'Token OAuth legado migrado para o cofre do sistema.'
                    )
            except OSError:
                raw = None
        if not raw:
            return None
        try:
            info = json.loads(raw)
            return Credentials.from_authorized_user_info(info, SCOPES)
        except (ValueError, TypeError):
            return None

    def _save_credentials(self, creds: Credentials) -> None:
        self.secret_store.set_secret(TOKEN_SECRET_NAME, creds.to_json())
        try:
            self.token_path.unlink(missing_ok=True)
        except OSError as error:
            logger.warning(
                'Não foi possível remover o token legado %s: %s',
                self.token_path,
                error,
            )

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
        creds = self._load_credentials()
        if creds is None:
            return False

        try:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                self._save_credentials(creds)
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
            callback = _run_loopback_oauth(flow, timeout_seconds=OAUTH_TIMEOUT_SECONDS)
            flow.fetch_token(
                authorization_response=callback.replace('http://', 'https://', 1)
            )
            self._save_credentials(flow.credentials)
            self._drive_service = None
            return True
        except WSGITimeoutError as error:
            log_exception("Google OAuth2 authentication timed out", error)
            raise RuntimeError(
                "A autenticação com o Google expirou. Feche a aba antiga do "
                "navegador e tente novamente; conclua o consentimento em até "
                "10 minutos."
            ) from error
        except Exception as error:
            log_exception("Failed during Google OAuth2 authentication flow", error)
            raise

    def logout(self) -> bool:
        """Purge saved authentication tokens (keyring and legacy file)."""
        self._drive_service = None
        removed = self.secret_store.delete_secret(TOKEN_SECRET_NAME)
        legacy_existed = self.token_path.exists()
        if legacy_existed:
            self.token_path.unlink(missing_ok=True)
        return removed or legacy_existed

    def get_drive_service(self) -> Resource:
        """Initialize or return cached Google Drive v3 API resource."""
        if self._drive_service is not None:
            return self._drive_service

        creds = self._load_credentials()
        if creds is None:
            raise RuntimeError("Cannot build Drive service: Unauthenticated.")

        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            self._save_credentials(creds)

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
            connection = sqlite3.connect(str(self.db_path))
            try:
                connection.execute('VACUUM INTO ?', (str(temp_db_path),))
                connection.commit()
            finally:
                connection.close()

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

        # Preflight: só promove um snapshot estruturalmente íntegro.
        check = sqlite3.connect(str(temp_restored))
        try:
            integrity = check.execute('PRAGMA integrity_check').fetchone()
            if not integrity or str(integrity[0]).lower() != 'ok':
                raise RuntimeError(
                    'Snapshot remoto corrompido: integrity_check falhou.'
                )
        finally:
            check.close()

        # Preserva o estado atual antes de substituir (rollback primário).
        self.create_conflict_backup()

        # Dispose do pool e remoção dos sidecars WAL antes da troca atômica.
        from src.db import db as db_module
        db_module.engine.dispose()
        for suffix in ('-wal', '-shm'):
            sidecar = Path(str(self.db_path) + suffix)
            if sidecar.exists():
                sidecar.unlink()
        os.replace(temp_restored, self.db_path)

        # Execute Alembic migrations to ensure schema parity if remote was newer
        apply_migrations()

    def create_conflict_backup(self) -> Path:
        """Create dated safety fork of the current local database (WAL-safe)."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_root = (
            self.base_dir / "data"
            if self._explicit_base_dir
            else self.base_dir
        )
        backup_path = backup_root / f"hupomnemata_conflict_{timestamp}.db"
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        source = sqlite3.connect(str(self.db_path))
        destination = sqlite3.connect(str(backup_path))
        try:
            with destination:
                source.backup(destination)
        finally:
            destination.close()
            source.close()
        return backup_path

    def get_current_schema_version(self) -> str:
        """Query the active Alembic revision from the local database."""
        try:
            connection = sqlite3.connect(str(self.db_path))
            try:
                result = connection.execute(
                    "SELECT version_num FROM alembic_version"
                ).fetchone()
            finally:
                connection.close()
            return str(result[0]) if result else "unknown"
        except Exception as error:
            log_exception("CloudSyncService.get_current_schema_version", error)
            return "unknown"

    def build_manifest(self, db_sha256: str) -> dict[str, Any]:
        """Construct canonical sync manifest."""
        return {
            "manifest_version": "1.1",
            "schema_version": self.get_current_schema_version(),
            "device_id": self.get_device_id(),
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "db_sha256": db_sha256,
            "counts": self._database_counts(self.db_path),
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

    @staticmethod
    def _database_counts(path: Path) -> dict[str, int]:
        """Conta registros do usuário em um banco (tolerante a esquema legado)."""
        counts: dict[str, int] = {}
        if not path.exists():
            return counts
        try:
            connection = sqlite3.connect(str(path))
            try:
                for key, table in (
                    ('resources', 'bibliographic_resources'),
                    ('fragments', 'fragments'),
                    ('compilations', 'compilations'),
                ):
                    try:
                        row = connection.execute(
                            f'SELECT COUNT(*) FROM {table}'
                        ).fetchone()
                        counts[key] = int(row[0]) if row else 0
                    except sqlite3.Error:
                        counts[key] = 0
            finally:
                connection.close()
        except sqlite3.Error as error:
            log_exception('CloudSyncService._database_counts', error)
        return counts

    def _local_has_data(self) -> bool:
        """Indica se o banco local já contém registros do usuário."""
        return any(self._database_counts(self.db_path).values())

    def _snapshot_has_data(self, gz_path: Path) -> bool:
        """Inspeciona o snapshot comprimido antes de promover qualquer troca."""
        temp = self.sync_dir / 'temp_inspect.db'
        if temp.exists():
            temp.unlink()
        try:
            with gzip.open(gz_path, 'rb') as source, open(temp, 'wb') as target:
                shutil.copyfileobj(source, target)
            return any(self._database_counts(temp).values())
        finally:
            if temp.exists():
                temp.unlink()

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

    @contextmanager
    def sync_exclusive(self):
        """Reserva a sincronização para uma operação destrutiva exclusiva."""
        with self._sync_lock:
            yield

    def sync(
        self,
        sync_pdfs: bool = False,
        force_push: bool = False,
        force_pull: bool = False,
    ) -> SyncResult:
        """Serializa sincronizações manuais, automáticas e de encerramento."""
        with self._sync_lock:
            return self._sync_unlocked(
                sync_pdfs=sync_pdfs,
                force_push=force_push,
                force_pull=force_pull,
            )

    def _sync_unlocked(
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

            remote_is_blank = not remote_manifest_meta and not remote_snapshot_meta

            # Scenario A: nuvem virgem ou push explicitamente solicitado
            if force_push or remote_is_blank:
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
                    direction="push",
                )

            # Nuvem parcial (só manifesto ou só snapshot): não sobrescrever
            # silenciosamente e não tentar baixar um arquivo inexistente.
            if not remote_manifest_meta or not remote_snapshot_meta:
                if force_pull:
                    return SyncResult(
                        status=SyncStatus.ERROR,
                        message=(
                            "A nuvem está incompleta (manifesto ou snapshot "
                            "ausente); não é possível baixar. Nada foi alterado."
                        ),
                    )
                if self._local_has_data():
                    conflict_backup = self.create_conflict_backup()
                    return SyncResult(
                        status=SyncStatus.CONFLICT,
                        message=(
                            "A nuvem está incompleta (manifesto ou snapshot "
                            "ausente). Escolha explicitamente qual cópia deve "
                            "prevalecer."
                        ),
                        conflict_backup_path=str(conflict_backup),
                        direction="conflict",
                    )
                return SyncResult(
                    status=SyncStatus.ERROR,
                    message=(
                        "A nuvem está incompleta (manifesto ou snapshot "
                        "ausente). Nada foi sobrescrito; verifique o Google Drive."
                    ),
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
                    direction="none",
                )

            # Primeira sincronização desta instalação com nuvem já povoada:
            # nunca sobrescrever o remoto em silêncio. Banco local vazio puxa
            # a nuvem; banco local com dados exige decisão explícita.
            if last_synced_sha256 is None and not force_push and not force_pull:
                if not self._local_has_data():
                    force_pull = True
                else:
                    conflict_backup = self.create_conflict_backup()
                    return SyncResult(
                        status=SyncStatus.CONFLICT,
                        message=(
                            "Primeira sincronização: existem dados locais e "
                            "uma cópia remota. Escolha explicitamente qual "
                            "cópia deve prevalecer."
                        ),
                        conflict_backup_path=str(conflict_backup),
                        direction="conflict",
                        details={
                            "remote_manifest": remote_manifest,
                            "local_sha256": local_sha256,
                        },
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
                    direction="conflict",
                    details={"remote_manifest": remote_manifest, "local_sha256": local_sha256},
                )

            # Scenario D: Pull remote changes (remote is ahead, or force pull requested)
            if force_pull or (last_synced_sha256 == local_sha256 and local_sha256 != remote_sha256):
                downloaded_gz = self.sync_dir / "downloaded_snapshot.db.gz"
                self._download_appdata_file(remote_snapshot_meta["id"], downloaded_gz)
                downloaded_sha = self.compute_sha256(downloaded_gz)

                if downloaded_sha != remote_sha256:
                    raise ValueError("Remote snapshot checksum verification failed.")

                # Pull explicitamente solicitado, mas a nuvem está vazia:
                # substituir apagaria toda a base local sem possibilidade de
                # recuperação. O usuário deve usar "Manter Local" para enviar.
                if (
                    force_pull
                    and self._local_has_data()
                    and not self._snapshot_has_data(downloaded_gz)
                ):
                    return SyncResult(
                        status=SyncStatus.ERROR,
                        message=(
                            "A nuvem está vazia (0 obras). A substituição foi "
                            "bloqueada para proteger os dados locais. Use "
                            "'Manter Local' para enviar esta base à nuvem."
                        ),
                    )

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
                    direction="pull",
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
                direction="push",
            )

        except Exception as error:
            log_exception("Unhandled error during cloud sync", error)
            return SyncResult(
                status=SyncStatus.ERROR,
                message=f"Cloud synchronization failed: {error}",
            )

    def delete_remote_database(self) -> list[str]:
        """Apaga manifesto e snapshot do banco no appDataFolder do Drive.

        Não remove PDFs nem outros arquivos do usuário. Deve ser chamado sob
        ``sync_exclusive()`` para não competir com uma sincronização em curso.
        """
        service = self.get_drive_service()
        deleted: list[str] = []
        for name in (MANIFEST_FILE_NAME, SNAPSHOT_FILE_NAME):
            meta = self._find_appdata_file(name)
            if not meta:
                continue
            service.files().delete(fileId=meta["id"]).execute()
            deleted.append(name)
            logger.info('Arquivo de banco removido da nuvem: %s', name)

        for name in (
            'last_synced_hash.txt',
            'remote_manifest.json',
            SNAPSHOT_FILE_NAME,
            'downloaded_snapshot.db.gz',
            'temp_restored.db',
        ):
            path = self.sync_dir / name
            if path.exists():
                path.unlink()
        return deleted

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

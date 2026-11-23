"""Manutenção destrutiva dos bancos locais do Hupomnêmata."""

import logging
from pathlib import Path

from src.configs.paths import resolve_data_dir
from src.utils.error_log import log_exception

logger = logging.getLogger('hupomnemata.maintenance')

_DATABASE_PATTERNS = (
    'hupomnemata.db',
    'hupomnemata.db-wal',
    'hupomnemata.db-shm',
    'hupomnemata_conflict_*.db',
    '*.db.bak',
)
_SYNC_PATTERNS = (
    'snapshot.db.gz',
    'downloaded_snapshot.db.gz',
    'remote_manifest.json',
    'last_synced_hash.txt',
    'temp_*.db',
)


def local_database_files(data_dir: Path | None = None) -> list[Path]:
    """Lista banco ativo, backups e snapshots locais de sincronização."""
    directory = Path(data_dir or resolve_data_dir())
    files: list[Path] = []
    for pattern in _DATABASE_PATTERNS:
        files.extend(sorted(directory.glob(pattern)))
    backups = directory / 'backups'
    if backups.exists():
        files.extend(sorted(backups.glob('*.db')))
    sync_dir = directory / 'sync'
    if sync_dir.exists():
        for pattern in _SYNC_PATTERNS:
            files.extend(sorted(sync_dir.glob(pattern)))
    return [path for path in files if path.is_file()]


def delete_local_databases(
    data_dir: Path | None = None,
    dispose_engine: bool | None = None,
) -> list[Path]:
    """Apaga os bancos locais e devolve os arquivos removidos.

    O banco ativo é fechado via ``engine.dispose()`` antes da remoção. A
    recriação do esquema limpo fica a cargo do chamador (``init_db``).
    """
    if dispose_engine is None:
        dispose_engine = data_dir is None
    if dispose_engine:
        from src.db import db as db_module

        db_module.engine.dispose()

    removed: list[Path] = []
    for path in local_database_files(data_dir):
        try:
            path.unlink()
            removed.append(path)
        except OSError as error:
            log_exception(f'Falha ao apagar banco {path}', error)
            raise
    logger.info('Bancos locais apagados: %s', len(removed))
    return removed

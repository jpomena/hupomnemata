"""Resolução canônica dos diretórios de dados do usuário.

Regra de ouro: **dado do usuário nunca mora dentro do código**. O banco, os
backups e o estado de sincronização passam a viver no diretório padrão de
dados do sistema operacional, com migração única e não destrutiva do banco
legado (``src/db/hupomnemata.db``), que permanece preservado como backup.

Ordem de precedência:

1. ``HUPOMNEMATA_DATA_DIR`` — sobrescreve tudo (diagnóstico e testes).
2. Windows: ``%LOCALAPPDATA%\\Hupomnemata`` (fallback ``%APPDATA%``).
3. macOS: ``~/Library/Application Support/Hupomnemata``.
4. Linux/Unix: ``$XDG_DATA_HOME/hupomnemata`` ou ``~/.local/share/hupomnemata``.

``sys.frozen`` **não** altera o destino do dado; serve apenas para localizar
candidatos legados ao lado do executável.
"""

from __future__ import annotations

import os
import platform
import shutil
import sqlite3
import sys
from pathlib import Path

APP_DIR_NAME = 'Hupomnemata'
DATA_DIR_ENV = 'HUPOMNEMATA_DATA_DIR'
PROJECT_ROOT = Path(__file__).resolve().parents[2]
LEGACY_CONFIG_DIR = PROJECT_ROOT / 'src' / 'configs'


def resolve_data_dir(
    env: dict[str, str] | None = None,
    system: str | None = None,
    home: Path | None = None,
) -> Path:
    """Resolve o diretório gravável de dados do usuário."""
    env = env if env is not None else os.environ
    override = env.get(DATA_DIR_ENV)
    if override:
        return Path(override).expanduser()

    system = system or platform.system()
    home = Path(home or Path.home())

    if system == 'Windows':
        base = env.get('LOCALAPPDATA') or env.get('APPDATA')
        if base:
            return Path(base) / APP_DIR_NAME
        return home / 'AppData' / 'Local' / APP_DIR_NAME

    if system == 'Darwin':
        return home / 'Library' / 'Application Support' / APP_DIR_NAME

    xdg = env.get('XDG_DATA_HOME')
    if xdg:
        return Path(xdg).expanduser() / 'hupomnemata'
    return home / '.local' / 'share' / 'hupomnemata'


def resolve_database_path(env: dict[str, str] | None = None) -> Path:
    env = env if env is not None else os.environ
    explicit = env.get('HUPOMNEMATA_DATABASE_PATH')
    if explicit:
        return Path(explicit).expanduser()
    return resolve_data_dir(env) / 'hupomnemata.db'


def resolve_backups_dir(env: dict[str, str] | None = None) -> Path:
    return resolve_data_dir(env) / 'backups'


def resolve_sync_dir(env: dict[str, str] | None = None) -> Path:
    return resolve_data_dir(env) / 'sync'


def resolve_preferences_path(env: dict[str, str] | None = None) -> Path:
    """Preferências de aparência (tema, escala) no diretório do usuário."""
    return resolve_data_dir(env) / 'user_preferences.json'


def resolve_pdf_storage_dir(env: dict[str, str] | None = None) -> Path:
    """Repositório gerenciado de PDFs, sempre gravável e fora do código."""
    return resolve_data_dir(env) / 'pdfs'


def resolve_secrets_path(env: dict[str, str] | None = None) -> Path:
    """Fallback local do cofre, quando o keyring do SO não está disponível."""
    return resolve_data_dir(env) / 'secrets.json'


def legacy_database_candidates() -> list[Path]:
    """Candidatos de banco legado, na ordem em que devem ser adotados."""
    candidates = [PROJECT_ROOT / 'src' / 'db' / 'hupomnemata.db']
    if getattr(sys, 'frozen', False):
        executable_dir = Path(sys.executable).resolve().parent
        candidates.insert(0, executable_dir / 'hupomnemata.db')
    return candidates


def _vacuum_into(source: Path, target: Path) -> None:
    """Copia um banco SQLite de forma consistente via ``VACUUM INTO``."""
    connection = sqlite3.connect(str(source))
    try:
        connection.execute('VACUUM INTO ?', (str(target),))
        connection.commit()
    finally:
        connection.close()


def migrate_legacy_database(
    target: Path | None = None,
    candidates: list[Path] | None = None,
) -> dict[str, str | bool]:
    """Adota o primeiro banco legado existente, sem sobrescrever o destino.

    O arquivo legado **nunca** é apagado: serve de backup até validação do
    usuário. A operação é idempotente: se o destino já existe, nada acontece.
    """
    target = Path(target or resolve_database_path())
    if target.exists():
        return {
            'migrated': False,
            'target': str(target),
            'reason': 'destino já existe',
        }

    for candidate in (candidates or legacy_database_candidates()):
        if not candidate.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            _vacuum_into(candidate, target)
        except sqlite3.Error:
            # Última linha de defesa: cópia bruta (legado presumidamente
            # quiescente, pois ainda não houve conexão da aplicação nova).
            target.write_bytes(candidate.read_bytes())
        return {
            'migrated': True,
            'source': str(candidate),
            'target': str(target),
        }

    return {'migrated': False, 'target': str(target), 'reason': 'sem legado'}


def _adopt_legacy_file(source: Path, target: Path) -> str | None:
    """Copia um arquivo legado para o destino, sem sobrescrever existente."""
    if target.exists() or not source.exists() or not source.is_file():
        return None
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return str(target)


def ensure_user_environment(
    data_dir: Path | None = None,
    legacy_config_dir: Path | None = None,
    database_target: Path | None = None,
) -> dict[str, object]:
    """Prepara o diretório de dados e adota artefatos legados.

    Idempotente e não destrutivo: bancos, preferências e cofre de fallback são
    copiados apenas quando o destino ainda não existe; os originais permanecem
    no lugar como backup.
    """
    resolved_dir = Path(data_dir) if data_dir is not None else resolve_data_dir()
    resolved_dir.mkdir(parents=True, exist_ok=True)
    (resolved_dir / 'backups').mkdir(parents=True, exist_ok=True)
    (resolved_dir / 'pdfs').mkdir(parents=True, exist_ok=True)

    legacy_dir = (
        Path(legacy_config_dir)
        if legacy_config_dir is not None
        else LEGACY_CONFIG_DIR
    )
    adopted_files = [
        adopted
        for adopted in (
            _adopt_legacy_file(
                legacy_dir / 'user_preferences.json',
                resolved_dir / 'user_preferences.json',
            ),
            _adopt_legacy_file(
                legacy_dir / 'secrets.json',
                resolved_dir / 'secrets.json',
            ),
        )
        if adopted
    ]

    database_target = (
        database_target
        if database_target is not None
        else (resolved_dir / 'hupomnemata.db' if data_dir is not None else None)
    )
    database = migrate_legacy_database(database_target)
    database['adopted_files'] = adopted_files
    return database

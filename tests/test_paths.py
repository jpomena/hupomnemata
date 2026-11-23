"""Resolução do diretório de dados e adoção do banco legado."""

import sqlite3
from pathlib import Path

from src.configs.paths import (
    DATA_DIR_ENV,
    ensure_user_environment,
    migrate_legacy_database,
    resolve_data_dir,
    resolve_database_path,
    resolve_pdf_storage_dir,
    resolve_preferences_path,
    resolve_secrets_path,
)


def test_env_override_has_priority(tmp_path):
    env = {DATA_DIR_ENV: str(tmp_path / 'custom')}
    assert resolve_data_dir(env=env, system='Windows') == tmp_path / 'custom'
    assert resolve_database_path(env=env) == tmp_path / 'custom' / 'hupomnemata.db'


def test_windows_uses_local_appdata(tmp_path):
    env = {'LOCALAPPDATA': str(tmp_path / 'Local')}
    resolved = resolve_data_dir(env=env, system='Windows', home=tmp_path)
    assert resolved == tmp_path / 'Local' / 'Hupomnemata'


def test_windows_falls_back_to_appdata_and_home(tmp_path):
    env = {'APPDATA': str(tmp_path / 'Roaming')}
    assert resolve_data_dir(
        env=env, system='Windows', home=tmp_path
    ) == tmp_path / 'Roaming' / 'Hupomnemata'

    assert resolve_data_dir(
        env={}, system='Windows', home=tmp_path
    ) == tmp_path / 'AppData' / 'Local' / 'Hupomnemata'


def test_linux_honors_xdg_then_home(tmp_path):
    env = {'XDG_DATA_HOME': str(tmp_path / 'xdg')}
    assert resolve_data_dir(
        env=env, system='Linux', home=tmp_path
    ) == tmp_path / 'xdg' / 'hupomnemata'

    assert resolve_data_dir(
        env={}, system='Linux', home=tmp_path
    ) == tmp_path / '.local' / 'share' / 'hupomnemata'


def test_macos_uses_application_support(tmp_path):
    assert resolve_data_dir(
        env={}, system='Darwin', home=tmp_path
    ) == tmp_path / 'Library' / 'Application Support' / 'Hupomnemata'


def _create_legacy_database(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path))
    try:
        connection.execute('CREATE TABLE legacy (id INTEGER PRIMARY KEY, tag TEXT)')
        connection.execute("INSERT INTO legacy (tag) VALUES ('preservado')")
        connection.execute(
            'CREATE TABLE alembic_version '
            '(version_num VARCHAR(32) NOT NULL PRIMARY KEY)'
        )
        connection.execute(
            "INSERT INTO alembic_version (version_num) "
            "VALUES ('8793c7031ee3')"
        )
        connection.commit()
    finally:
        connection.close()


def test_pre_alembic_database_is_not_adopted(tmp_path):
    """Banco anterior ao Alembic não deve ser importado automaticamente."""
    legacy = tmp_path / 'old' / 'hupomnemata.db'
    target = tmp_path / 'novo' / 'hupomnemata.db'
    legacy.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(legacy))
    try:
        connection.execute(
            'CREATE TABLE legacy (id INTEGER PRIMARY KEY, tag TEXT)'
        )
        connection.execute("INSERT INTO legacy (tag) VALUES ('antigo')")
        connection.commit()
    finally:
        connection.close()

    result = migrate_legacy_database(target, candidates=[legacy])

    assert result['migrated'] is False
    assert 'Alembic' in str(result['reason'])
    assert not target.exists()
    assert legacy.exists()


def test_legacy_database_is_adopted_once_and_preserved(tmp_path):
    legacy = tmp_path / 'old' / 'hupomnemata.db'
    target = tmp_path / 'novo' / 'hupomnemata.db'
    _create_legacy_database(legacy)

    first = migrate_legacy_database(target, candidates=[legacy])
    assert first['migrated'] is True
    assert legacy.exists(), 'o banco legado nunca deve ser apagado'

    connection = sqlite3.connect(str(target))
    try:
        row = connection.execute('SELECT tag FROM legacy').fetchone()
    finally:
        connection.close()
    assert row == ('preservado',)

    second = migrate_legacy_database(target, candidates=[legacy])
    assert second['migrated'] is False


def test_existing_target_is_never_overwritten(tmp_path):
    legacy = tmp_path / 'old.db'
    target = tmp_path / 'novo.db'
    _create_legacy_database(legacy)

    _create_legacy_database(target)
    connection = sqlite3.connect(str(target))
    try:
        connection.execute("INSERT INTO legacy (tag) VALUES ('atual')")
        connection.commit()
    finally:
        connection.close()

    result = migrate_legacy_database(target, candidates=[legacy])
    assert result['migrated'] is False

    connection = sqlite3.connect(str(target))
    try:
        tags = {row[0] for row in connection.execute('SELECT tag FROM legacy')}
    finally:
        connection.close()
    assert 'atual' in tags


def test_paths_support_spaces_and_unicode(tmp_path):
    directory = tmp_path / 'gab. carrijo' / 'Área de Dados'
    env = {DATA_DIR_ENV: str(directory)}
    assert resolve_database_path(env=env).parent == directory


def test_artifacts_resolve_under_data_dir(tmp_path):
    directory = tmp_path / 'dados'
    env = {DATA_DIR_ENV: str(directory)}
    assert resolve_preferences_path(env) == directory / 'user_preferences.json'
    assert resolve_secrets_path(env) == directory / 'secrets.json'
    assert resolve_pdf_storage_dir(env) == directory / 'pdfs'


def test_environment_adopts_legacy_preferences_once(tmp_path):
    legacy = tmp_path / 'legacy_config'
    legacy.mkdir()
    (legacy / 'user_preferences.json').write_text(
        '{"theme_mode": "dark"}', encoding='utf-8'
    )
    (legacy / 'secrets.json').write_text(
        '{"gemini_api_key": "chave"}', encoding='utf-8'
    )

    data = tmp_path / 'dados'
    data.mkdir()
    # Destino de banco já existente evita adotar o banco real do projeto.
    sqlite3.connect(str(data / 'hupomnemata.db')).close()

    result = ensure_user_environment(
        data_dir=data,
        legacy_config_dir=legacy,
        database_target=data / 'hupomnemata.db',
    )

    assert (data / 'user_preferences.json').read_text(encoding='utf-8')
    assert (data / 'secrets.json').read_text(encoding='utf-8')
    assert len(result['adopted_files']) == 2
    # Originais preservados.
    assert (legacy / 'user_preferences.json').exists()
    assert (legacy / 'secrets.json').exists()

    # Segunda execução não sobrescreve o destino.
    (data / 'user_preferences.json').write_text('novo', encoding='utf-8')
    ensure_user_environment(
        data_dir=data,
        legacy_config_dir=legacy,
        database_target=data / 'hupomnemata.db',
    )
    assert (data / 'user_preferences.json').read_text(encoding='utf-8') == 'novo'

"""`init_db` e rotinas legadas devem operar apenas na engine recebida."""

import pytest
from sqlalchemy import inspect
from sqlalchemy.pool import StaticPool

from src.db import db as db_module
from src.db.db import (
    _ensure_compilation_fragment_columns,
    _ensure_compilation_outline_columns,
    _ensure_legacy_columns,
    _migrate_periodical_parent_links,
    _rename_legacy_citations_table,
    _split_resources_with_multiple_work_types,
    init_db,
)
from src.db.sqlite_runtime import create_sqlite_engine


def _memory_engine():
    return create_sqlite_engine(
        'sqlite://',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )


def test_init_db_initializes_only_target_engine(monkeypatch):
    global_engine = _memory_engine()
    target_engine = _memory_engine()
    monkeypatch.setattr(db_module, 'engine', global_engine)
    monkeypatch.setattr(db_module, '_initialized_engine', None)

    try:
        init_db(target_engine)
        target_tables = set(inspect(target_engine).get_table_names())
        global_tables = set(inspect(global_engine).get_table_names())

        assert 'bibliographic_resources' in target_tables
        assert 'fragments' in target_tables
        assert global_tables == set()
    finally:
        target_engine.dispose()
        global_engine.dispose()


@pytest.mark.parametrize(
    'helper',
    [
        _rename_legacy_citations_table,
        _ensure_legacy_columns,
        _ensure_compilation_fragment_columns,
        _ensure_compilation_outline_columns,
        _split_resources_with_multiple_work_types,
        _migrate_periodical_parent_links,
    ],
)
def test_legacy_helpers_never_touch_global_engine(helper, monkeypatch):
    global_engine = _memory_engine()
    target_engine = _memory_engine()
    db_module.Base.metadata.create_all(bind=target_engine)
    monkeypatch.setattr(db_module, 'engine', global_engine)
    monkeypatch.setattr(db_module, '_initialized_engine', None)

    try:
        helper(target_engine)
        assert set(inspect(global_engine).get_table_names()) == set()
    finally:
        target_engine.dispose()
        global_engine.dispose()


def test_init_db_is_idempotent_on_same_engine():
    engine = _memory_engine()
    try:
        init_db(engine)
        init_db(engine)
        assert 'bibliographic_resources' in inspect(engine).get_table_names()
    finally:
        engine.dispose()

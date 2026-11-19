"""Regressão do runtime SQLite: PRAGMAs, integridade e reparo de órfãos."""

import sqlite3
from datetime import datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import StaticPool

from src.db import db as db_module
from src.db.integrity import ensure_referential_integrity
from src.db.sqlite_runtime import BUSY_TIMEOUT_MS, create_sqlite_engine
from src.domains import BibliographicResource, EditorialMonograph


def _pragmas(engine):
    with engine.connect() as connection:
        return {
            'foreign_keys': connection.exec_driver_sql(
                'PRAGMA foreign_keys'
            ).scalar(),
            'busy_timeout': connection.exec_driver_sql(
                'PRAGMA busy_timeout'
            ).scalar(),
            'journal_mode': connection.exec_driver_sql(
                'PRAGMA journal_mode'
            ).scalar(),
            'synchronous': connection.exec_driver_sql(
                'PRAGMA synchronous'
            ).scalar(),
        }


def test_file_engine_pragmas_are_canonical(tmp_path):
    engine = create_sqlite_engine(tmp_path / 'runtime.db')
    try:
        pragmas = _pragmas(engine)
        assert pragmas['foreign_keys'] == 1
        assert pragmas['busy_timeout'] == BUSY_TIMEOUT_MS
        assert str(pragmas['journal_mode']).lower() == 'wal'
        # synchronous=NORMAL é representado por 1 no SQLite.
        assert pragmas['synchronous'] == 1
    finally:
        engine.dispose()


def test_memory_engine_keeps_foreign_keys_without_wal():
    engine = create_sqlite_engine(
        'sqlite://',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    try:
        pragmas = _pragmas(engine)
        assert pragmas['foreign_keys'] == 1
        assert str(pragmas['journal_mode']).lower() == 'memory'
    finally:
        engine.dispose()


def test_foreign_key_rejects_orphan_fragment(clean_db):
    with clean_db.begin() as connection:
        with pytest.raises(IntegrityError):
            connection.exec_driver_sql(
                'INSERT INTO fragments '
                '(excerpt, fragment_type, bib_res_id, created_at) '
                "VALUES ('órfão', 'quote', 999999, ?)",
                (datetime.now().isoformat(sep=' '),),
            )


def test_raw_delete_cascades_at_database_level(clean_db):
    with db_module.SessionLocal() as session:
        resource = BibliographicResource(
            editorial_monograph=EditorialMonograph(title='Cascata')
        )
        session.add(resource)
        session.commit()
        resource_id = resource.id

    with clean_db.begin() as connection:
        connection.exec_driver_sql(
            'INSERT INTO fragments '
            '(excerpt, fragment_type, bib_res_id, created_at) '
            "VALUES ('excerto', 'quote', ?, ?)",
            (resource_id, datetime.now().isoformat(sep=' ')),
        )
        connection.exec_driver_sql(
            'DELETE FROM bibliographic_resources WHERE id = ?',
            (resource_id,),
        )

    with clean_db.connect() as connection:
        remaining = connection.exec_driver_sql(
            'SELECT COUNT(*) FROM fragments WHERE bib_res_id = ?',
            (resource_id,),
        ).scalar()
    assert remaining == 0


def test_integrity_repair_quarantines_and_removes_orphans(tmp_path):
    database = tmp_path / 'legacy.db'
    engine = create_sqlite_engine(database)
    db_module.Base.metadata.create_all(bind=engine)
    engine.dispose()

    # Simula banco legado: órfão inserido com FK desligada.
    raw = sqlite3.connect(str(database))
    try:
        raw.execute('PRAGMA foreign_keys=OFF')
        raw.execute(
            'INSERT INTO fragments '
            '(excerpt, fragment_type, bib_res_id, created_at) '
            "VALUES ('legado', 'quote', 424242, ?)",
            (datetime.now().isoformat(sep=' '),),
        )
        raw.commit()
    finally:
        raw.close()

    engine = create_sqlite_engine(database)
    try:
        summary = ensure_referential_integrity(engine, tmp_path / 'backups')

        assert summary['violations'] == 1
        assert summary['repaired'].get('deleted') == 1
        assert summary['backup']
        assert summary['quarantine']
        assert (tmp_path / 'backups').exists()

        quarantine = list((tmp_path / 'backups').glob('fk_quarantine_*.jsonl'))
        assert quarantine and quarantine[0].read_text(encoding='utf-8')

        with engine.connect() as connection:
            remaining = connection.exec_driver_sql(
                'SELECT COUNT(*) FROM fragments'
            ).scalar()
        assert remaining == 0
    finally:
        engine.dispose()

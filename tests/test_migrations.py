"""Paridade entre o esquema criado pelo Alembic e o metadata do ORM."""

from pathlib import Path

from sqlalchemy import inspect
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from src.db import db as db_module
from src.db.db import (
    LEGACY_BASELINE_REVISION,
    apply_migrations,
    init_db,
    schema_differences,
)
from src.db.sqlite_runtime import create_sqlite_engine
from src.domains import BibliographicResource, EditorialMonograph


def _memory_engine():
    return create_sqlite_engine(
        'sqlite://',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )


def test_upgrade_head_matches_orm_metadata():
    engine = _memory_engine()
    try:
        apply_migrations(engine)
        differences = schema_differences(engine)
        assert differences == []
    finally:
        engine.dispose()


def test_upgrade_head_creates_every_orm_table():
    engine = _memory_engine()
    try:
        apply_migrations(engine)
        materialized = set(inspect(engine).get_table_names()) - {'alembic_version'}
        expected = set(db_module.Base.metadata.tables)
        assert materialized == expected
    finally:
        engine.dispose()


def test_apply_migrations_is_idempotent():
    engine = _memory_engine()
    try:
        apply_migrations(engine)
        apply_migrations(engine)
    finally:
        engine.dispose()


def test_init_db_on_fresh_database_uses_alembic_only():
    engine = _memory_engine()
    try:
        init_db(engine)
        assert 'bibliographic_resources' in inspect(engine).get_table_names()
        assert schema_differences(engine) == []
    finally:
        engine.dispose()


def test_legacy_unversioned_database_is_adopted_without_data_loss(tmp_path: Path):
    database = tmp_path / 'legacy.db'
    engine = create_sqlite_engine(database)
    try:
        db_module.Base.metadata.create_all(bind=engine)
        # Insere dados usando a engine isolada.
        with Session(engine) as session:
            session.add(
                BibliographicResource(
                    editorial_monograph=EditorialMonograph(title='Obra legada')
                )
            )
            session.commit()

        # Remove o marcador do Alembic e recria a coluna obsoleta, simulando
        # o esquema anterior à consolidação.
        with engine.begin() as conn:
            conn.exec_driver_sql('DROP TABLE IF EXISTS alembic_version')
            conn.exec_driver_sql(
                'ALTER TABLE statutes ADD COLUMN publication_date DATE'
            )

        init_db(engine)

        assert 'alembic_version' in inspect(engine).get_table_names()
        with engine.connect() as conn:
            revision = conn.exec_driver_sql(
                'SELECT version_num FROM alembic_version'
            ).scalar()
        assert revision and revision != LEGACY_BASELINE_REVISION

        columns = {
            column['name']
            for column in inspect(engine).get_columns('statutes')
        }
        assert 'publication_date' not in columns

        with Session(engine) as session:
            titles = [
                resource.specific_work.title
                for resource in session.query(BibliographicResource).all()
            ]
        assert titles == ['Obra legada']
    finally:
        engine.dispose()


def test_legacy_citations_are_renamed_before_stamp(tmp_path: Path):
    database = tmp_path / 'legacy_citations.db'
    engine = create_sqlite_engine(database)
    try:
        db_module.Base.metadata.create_all(bind=engine)
        with engine.begin() as conn:
            conn.exec_driver_sql('DROP TABLE fragments')
            conn.exec_driver_sql('DROP TABLE IF EXISTS alembic_version')
            conn.exec_driver_sql(
                """
                CREATE TABLE citations (
                    id INTEGER PRIMARY KEY,
                    excerpt TEXT NOT NULL,
                    bib_res_id INTEGER NOT NULL,
                    start_page INTEGER,
                    end_page INTEGER
                )
                """
            )
            conn.exec_driver_sql(
                "INSERT INTO citations (id, excerpt, bib_res_id, start_page, "
                "end_page) VALUES (7, 'Trecho', 1, 10, 12)"
            )

        init_db(engine)

        with engine.connect() as conn:
            row = conn.exec_driver_sql(
                'SELECT fragment_type, location_type, location_value, '
                'created_at FROM fragments WHERE id = 7'
            ).fetchone()
        assert row is not None
        assert row[0] == 'quote'
        assert row[1] == 'Página'
        assert row[2] == '10-12'
        assert row[3] is not None
    finally:
        engine.dispose()

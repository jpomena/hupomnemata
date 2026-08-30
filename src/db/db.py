from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_PATH = Path(__file__).resolve().parents[0] / 'hupomnemata.db'
DATABASE_URL = f'sqlite:///{DATABASE_PATH.as_posix()}'

engine = create_engine(DATABASE_URL)


class Base(DeclarativeBase):
    pass


def _import_domain_models() -> None:
    import src.domains  # noqa: F401


def _cleanup_duplicate_specific_works() -> None:
    """Remove registros antigos de obras específicas duplicadas por recurso."""
    tables = [
        'editorial_monographs',
        'academic_monographs',
        'correspondence_monographs',
        'periodical_collections',
        'journal_articles',
        'newspaper_articles',
        'monographic_proceedings',
        'periodical_proceedings',
        'patents',
        'statutes',
        'caselaws',
        'audiovisual_documents',
        'audio_documents',
        'visual_documents',
        'three_dimensional_documents',
        'cartographic_documents',
        'musical_scores',
    ]
    with engine.begin() as conn:
        for table_name in tables:
            try:
                rows = conn.execute(
                    text(
                        f"""
                        SELECT id, bib_res_id
                        FROM {table_name}
                        WHERE id NOT IN (
                            SELECT MAX(id)
                            FROM {table_name}
                            GROUP BY bib_res_id
                        )
                        """
                    )
                ).fetchall()
                for row_id, _ in rows:
                    conn.execute(
                        text(f"DELETE FROM {table_name} WHERE id = :row_id"),
                        {'row_id': row_id},
                    )
            except Exception:
                continue


def _ensure_legacy_columns() -> None:
    """Adiciona colunas faltantes em bancos já existentes."""
    _import_domain_models()
    with engine.begin() as conn:
        table_columns = {
            row[0]: {column[1] for column in conn.execute(
                text(f'PRAGMA table_info("{row[0]}")')
            ).fetchall()}
            for row in conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            ).fetchall()
        }
        if 'statutes' in table_columns and 'publication_date' not in table_columns['statutes']:  # noqa: E501
            conn.execute(
                text('ALTER TABLE statutes ADD COLUMN publication_date DATE')
            )


def init_db():
    _import_domain_models()
    Base.metadata.create_all(bind=engine)
    _ensure_legacy_columns()
    _cleanup_duplicate_specific_works()


class _SessionLocal(sessionmaker):
    def __call__(self, **local_kw):
        _import_domain_models()
        init_db()
        return super().__call__(**local_kw)


SessionLocal = _SessionLocal(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

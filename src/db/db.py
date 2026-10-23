from pathlib import Path

from sqlalchemy import create_engine, or_, select, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from src.utils.error_log import log_exception

DATABASE_PATH = Path(__file__).resolve().parents[0] / 'hupomnemata.db'
DATABASE_URL = f'sqlite:///{DATABASE_PATH.as_posix()}'

engine = create_engine(DATABASE_URL)


class Base(DeclarativeBase):
    pass


def _import_domain_models() -> None:
    import src.domains  # noqa: F401


def _rename_legacy_citations_table() -> None:
    """Move the original citations table to the fragments table name."""
    with engine.begin() as conn:
        tables = {
            row[0]
            for row in conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            )
        }
        if 'citations' in tables and 'fragments' not in tables:
            conn.execute(text('ALTER TABLE citations RENAME TO fragments'))


def _cleanup_duplicate_specific_works() -> None:
    """Remove registros antigos de obras específicas duplicadas por recurso."""
    tables = [
        'editorial_monographs',
        'academic_monographs',
        'correspondence_monographs',
        'periodical_collections',
        'magazines',
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
            except Exception as error:
                log_exception(
                    f"Falha ao limpar duplicatas da tabela {table_name}",
                    error,
                )
                continue


def _split_resources_with_multiple_work_types() -> None:
    """Move works of conflicting types to separate bibliographic resources."""
    work_tables = (
        'editorial_monographs',
        'academic_monographs',
        'correspondence_monographs',
        'periodical_collections',
        'magazines',
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
        'miscellaneous_digital_documents',
    )
    partial_work_tables = {
        'editorial_monographs',
        'academic_monographs',
        'correspondence_monographs',
        'periodical_collections',
        'journal_articles',
        'newspaper_articles',
        'monographic_proceedings',
        'periodical_proceedings',
        'audio_documents',
        'musical_scores',
    }
    parent_child_tables = {
        table: {table}
        for table in partial_work_tables
        if table != 'periodical_collections'
    }
    parent_child_tables['magazines'] = {
        'journal_articles',
        'periodical_collections',
    }

    try:
        with engine.begin() as conn:
            available_tables = {
                row[0]
                for row in conn.execute(text(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ))
            }
            resource_work_tables = [
                table for table in work_tables
                if table in available_tables
            ]
            work_by_resource: dict[int, list[tuple[str, int]]] = {}
            for table in resource_work_tables:
                rows = conn.execute(text(
                    f'SELECT id, bib_res_id FROM "{table}" '
                    'ORDER BY id'
                )).fetchall()
                for row_id, resource_id in rows:
                    work_by_resource.setdefault(resource_id, []).append(
                        (table, row_id)
                    )

            for resource_id, works in work_by_resource.items():
                if len(works) < 2:
                    continue

                for table, row_id in works[1:]:
                    new_resource_id = conn.execute(text(
                        'INSERT INTO bibliographic_resources DEFAULT VALUES'
                    )).lastrowid
                    if new_resource_id is None:
                        raise RuntimeError(
                            'Não foi possível separar obras específicas '
                            f'associadas ao recurso {resource_id}.'
                        )

                    conn.execute(
                        text(
                            f'UPDATE "{table}" SET bib_res_id = :new_id '
                            'WHERE id = :work_id'
                        ),
                        {'new_id': new_resource_id, 'work_id': row_id},
                    )

                    for child_table in parent_child_tables.get(table, set()):
                        if child_table in available_tables:
                            conn.execute(
                                text(
                                    f'UPDATE "{child_table}" '
                                    'SET parent_bibliographic_resource_id '
                                    '= :new_id '
                                    'WHERE parent_bibliographic_resource_id '
                                    '= :old_id'
                                ),
                                {
                                    'new_id': new_resource_id,
                                    'old_id': resource_id,
                                },
                            )
    except Exception as error:
        log_exception(
            'Falha ao separar recursos bibliográficos com obras '
            'específicas conflitantes',
            error,
        )
        raise


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
        for table in Base.metadata.tables.values():
            columns = table_columns.get(table.name, set())
            if (
                {'title', 'bib_res_id'} <= columns
                and 'preserve_title_spelling' not in columns
            ):
                conn.execute(text(
                    f'ALTER TABLE "{table.name}" ADD COLUMN '
                    'preserve_title_spelling BOOLEAN NOT NULL DEFAULT 0'
                ))
                columns.add('preserve_title_spelling')
        if 'fragments' in table_columns:
            fragment_columns = table_columns['fragments']
            fragment_migrations = {
                'fragment_type': (
                    "VARCHAR(20) NOT NULL DEFAULT 'quote'"
                ),
                'location_type': 'VARCHAR(30)',
                'location_value': 'VARCHAR(100)',
                'created_at': 'DATETIME',
                'updated_at': 'DATETIME',
            }
            for column_name, column_type in fragment_migrations.items():
                if column_name not in fragment_columns:
                    conn.execute(text(
                        'ALTER TABLE fragments ADD COLUMN '
                        f'{column_name} {column_type}'
                    ))
                    fragment_columns.add(column_name)
            conn.execute(text(
                'UPDATE fragments SET created_at = CURRENT_TIMESTAMP '
                'WHERE created_at IS NULL'
            ))
            if {'start_page', 'end_page'} <= fragment_columns:
                conn.execute(text(
                    """
                    UPDATE fragments
                    SET location_type = 'Página',
                        location_value = CASE
                            WHEN start_page IS NOT NULL
                                AND end_page IS NOT NULL
                                THEN CAST(start_page AS TEXT) || '-' ||
                                     CAST(end_page AS TEXT)
                            WHEN start_page IS NOT NULL
                                THEN CAST(start_page AS TEXT)
                            ELSE CAST(end_page AS TEXT)
                        END
                    WHERE location_type IS NULL
                      AND (start_page IS NOT NULL OR end_page IS NOT NULL)
                    """
                ))
        if 'statutes' in table_columns and 'publication_date' not in table_columns['statutes']:  # noqa: E501
            conn.execute(
                text('ALTER TABLE statutes ADD COLUMN publication_date DATE')
            )
        if 'audio_documents' in table_columns:
            audio_columns_present = table_columns['audio_documents']
            if (
                'is_part' in audio_columns_present
                and 'is_partial' not in audio_columns_present
            ):
                conn.execute(text(
                    'ALTER TABLE audio_documents '
                    'RENAME COLUMN is_part TO is_partial'
                ))
                audio_columns_present.remove('is_part')
                audio_columns_present.add('is_partial')
            elif (
                'is_part' in audio_columns_present
                and 'is_partial' in audio_columns_present
            ):
                conn.execute(text(
                    'UPDATE audio_documents SET is_partial = '
                    'CASE WHEN is_part THEN 1 ELSE is_partial END'
                ))
                conn.execute(text(
                    'ALTER TABLE audio_documents DROP COLUMN is_part'
                ))
                audio_columns_present.remove('is_part')
            elif 'is_partial' not in audio_columns_present:
                conn.execute(text(
                    'ALTER TABLE audio_documents ADD COLUMN '
                    'is_partial BOOLEAN NOT NULL DEFAULT 0'
                ))
                audio_columns_present.add('is_partial')

            audio_columns = {
                'parent_bibliographic_resource_id':
                    'INTEGER REFERENCES bibliographic_resources(id) '
                    'ON DELETE CASCADE',
                'part_start_page': 'VARCHAR(6)',
                'part_end_page': 'VARCHAR(6)',
                'part_volume': 'VARCHAR(15)',
                'part_chapter': 'VARCHAR(15)',
                'consult_start_year': 'INTEGER',
                'consult_end_year': 'INTEGER',
                'seconds': 'INTEGER',
                'physical_details': 'VARCHAR(200)',
                'additional_notes': 'VARCHAR(500)',
            }
            existing_columns = audio_columns_present
            for column_name, column_type in audio_columns.items():
                if column_name not in existing_columns:
                    conn.execute(text(
                        'ALTER TABLE audio_documents ADD COLUMN '
                        f'{column_name} {column_type}'
                    ))
        if 'musical_scores' in table_columns:
            musical_score_columns = {
                'is_partial': 'BOOLEAN NOT NULL DEFAULT 0',
                'parent_bibliographic_resource_id':
                    'INTEGER REFERENCES bibliographic_resources(id) '
                    'ON DELETE CASCADE',
                'part_start_page': 'VARCHAR(6)',
                'part_end_page': 'VARCHAR(6)',
                'part_volume': 'VARCHAR(15)',
                'part_chapter': 'VARCHAR(15)',
                'consult_start_year': 'INTEGER',
                'consult_end_year': 'INTEGER',
                'author_role': 'VARCHAR(50)',
                'physical_description': 'VARCHAR(500)',
            }
            existing_columns = table_columns['musical_scores']
            for column_name, column_type in musical_score_columns.items():
                if column_name not in existing_columns:
                    conn.execute(text(
                        'ALTER TABLE musical_scores ADD COLUMN '
                        f'{column_name} {column_type}'
                    ))
        if 'visual_documents' in table_columns:
            visual_document_columns = {
                'physical_description': 'VARCHAR(500)',
                'additional_notes': 'VARCHAR(500)',
            }
            existing_columns = table_columns['visual_documents']
            for column_name, column_type in visual_document_columns.items():
                if column_name not in existing_columns:
                    conn.execute(text(
                        'ALTER TABLE visual_documents ADD COLUMN '
                        f'{column_name} {column_type}'
                    ))
        if 'cartographic_documents' in table_columns:
            cartographic_columns = {
                'edition': 'INTEGER',
                'physical_description': 'VARCHAR(500)',
                'additional_notes': 'VARCHAR(500)',
            }
            existing_columns = table_columns['cartographic_documents']
            for column_name, column_type in cartographic_columns.items():
                if column_name not in existing_columns:
                    conn.execute(text(
                        'ALTER TABLE cartographic_documents ADD COLUMN '
                        f'{column_name} {column_type}'
                    ))
        if 'three_dimensional_documents' in table_columns:
            three_dimensional_columns = {
                'physical_description': "VARCHAR(500) NOT NULL DEFAULT ''",
                'additional_notes': 'VARCHAR(500)',
            }
            existing_columns = table_columns[
                'three_dimensional_documents'
            ]
            for column_name, column_type in three_dimensional_columns.items():
                if column_name not in existing_columns:
                    conn.execute(text(
                        'ALTER TABLE three_dimensional_documents ADD COLUMN '
                        f'{column_name} {column_type}'
                    ))


def _ensure_compilation_fragment_columns() -> None:
    with engine.begin() as conn:
        tables = {
            row[0]
            for row in conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            )
        }
        if 'compilation_fragments' not in tables:
            return

        columns = {
            row[1]
            for row in conn.execute(
                text('PRAGMA table_info("compilation_fragments")')
            )
        }
        added_position = 'position' not in columns
        if added_position:
            conn.execute(text(
                'ALTER TABLE compilation_fragments ADD COLUMN '
                'position INTEGER NOT NULL DEFAULT 0'
            ))
        if 'work_note' not in columns:
            conn.execute(text(
                'ALTER TABLE compilation_fragments ADD COLUMN work_note TEXT'
            ))

        if added_position and 'fragments' in tables:
            rows = conn.execute(text(
                """
                SELECT cf.id, cf.compilation_id, f.bib_res_id
                FROM compilation_fragments AS cf
                JOIN fragments AS f ON f.id = cf.fragment_id
                ORDER BY cf.compilation_id, f.bib_res_id, cf.fragment_id
                """
            )).fetchall()
            positions: dict[tuple[int, int], int] = {}
            for association_id, compilation_id, bib_res_id in rows:
                key = (compilation_id, bib_res_id)
                position = positions.get(key, 0)
                conn.execute(
                    text(
                        'UPDATE compilation_fragments '
                        'SET position = :position WHERE id = :id'
                    ),
                    {'position': position, 'id': association_id},
                )
                positions[key] = position + 1


def _ensure_compilation_outline_columns() -> None:
    with engine.begin() as conn:
        tables = {
            row[0]
            for row in conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            )
        }
        if 'compilation_fragments' not in tables:
            return
        columns = {
            row[1]
            for row in conn.execute(
                text('PRAGMA table_info("compilation_fragments")')
            )
        }
        if 'section_id' not in columns:
            conn.execute(text(
                'ALTER TABLE compilation_fragments ADD COLUMN '
                'section_id INTEGER REFERENCES compilation_sections(id) '
                'ON DELETE SET NULL'
            ))


def _migrate_periodical_parent_links() -> None:
    """Cria Revistas para registros legados e as vincula como obra-pai."""
    from src.domains import (
        BibliographicResource,
        JournalArticle,
        Magazine,
        PeriodicalCollection,
    )

    try:
        with Session(engine) as session:
            for model in (JournalArticle, PeriodicalCollection):
                magazine_resources = select(Magazine.bib_res_id)
                pending_works = select(model).where(
                    or_(
                        model.parent_bibliographic_resource_id.is_(None),
                        model.parent_bibliographic_resource_id.not_in(
                            magazine_resources
                        ),
                        model.is_partial.is_(False),
                    )
                )
                for work in session.scalars(pending_works).all():
                    parent_id = work.parent_bibliographic_resource_id
                    parent = (
                        session.get(BibliographicResource, parent_id)
                        if parent_id is not None
                        else None
                    )
                    if (
                        parent is not None
                        and isinstance(parent.specific_work, Magazine)
                    ):
                        work.is_partial = True
                        continue

                    title = (work.journal_title or '').strip()
                    if not title:
                        raise ValueError(
                            f'Obra periódica {work.bib_res_id} sem nome '
                            'de revista; não foi possível migrar o vínculo.'
                        )
                    place = (
                        (work.publication_place or '').strip() or '[s.l.]'
                    )
                    magazine = session.scalar(
                        select(Magazine).where(
                            Magazine.title == title,
                            Magazine.publication_place == place,
                        )
                    )
                    if magazine is None:
                        magazine_resource = BibliographicResource()
                        magazine = Magazine(
                            title=title,
                            publication_place=place,
                        )
                        magazine_resource.magazine = magazine
                        session.add(magazine_resource)
                        session.flush()

                    work.parent_bibliographic_resource_id = (
                        magazine.bib_res_id
                    )
                    work.is_partial = True
            session.commit()
    except Exception as error:
        log_exception('Falha ao migrar vínculos de revistas', error)
        raise


def init_db():
    _import_domain_models()
    _rename_legacy_citations_table()
    Base.metadata.create_all(bind=engine)
    _ensure_legacy_columns()
    _ensure_compilation_fragment_columns()
    _ensure_compilation_outline_columns()
    _cleanup_duplicate_specific_works()
    _split_resources_with_multiple_work_types()
    _migrate_periodical_parent_links()


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

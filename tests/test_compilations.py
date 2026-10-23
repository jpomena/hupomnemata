import asyncio
from types import SimpleNamespace

import flet as ft
import pytest
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.exc import IntegrityError

from src.contracts import CompilationRecord
from src.db import db as db_module
from src.domains import (
    BibliographicResource,
    Compilation,
    CompilationWork,
    EditorialMonograph,
    Fragment,
)
from src.repositories.work_repository import WorkRepository
from src.services.compilation_service import CompilationService
from src.services.fragment_service import FragmentService


@pytest.fixture
def compilation_database(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'compilations.db').as_posix()}"
    )
    monkeypatch.setattr(db_module, 'engine', engine)
    db_module.SessionLocal.configure(bind=engine)
    db_module.Base.metadata.create_all(bind=engine)
    yield engine
    db_module.Base.metadata.drop_all(bind=engine)
    engine.dispose()


def create_work(title: str) -> int:
    with db_module.SessionLocal() as session:
        resource = BibliographicResource(
            editorial_monograph=EditorialMonograph(title=title)
        )
        session.add(resource)
        session.commit()
        return resource.id


def test_compilation_crud_membership_and_manual_order(compilation_database):
    service = CompilationService()
    first_work_id = create_work('Primeira obra')
    second_work_id = create_work('Segunda obra')
    first_id = service.create({
        'name': '  Tese  ',
        'description': '  Pesquisa principal  ',
    })
    second_id = service.create({
        'name': 'Artigo',
        'description': None,
    })

    service.add_work(first_id, first_work_id)
    service.add_work(first_id, second_work_id)
    service.add_work(second_id, first_work_id)

    with pytest.raises(ValueError, match='já pertence'):
        service.add_work(first_id, first_work_id)

    records = service.list_compilations()
    assert records[0]['name'] == 'Artigo'
    assert records[0]['works'][0]['id'] == first_work_id
    assert records[1]['name'] == 'Tese'
    assert [work['id'] for work in records[1]['works']] == [
        first_work_id,
        second_work_id,
    ]
    assert records[1]['description'] == 'Pesquisa principal'

    service.reorder_works(first_id, [second_work_id, first_work_id])
    records = service.list_compilations()
    tese = next(record for record in records if record['id'] == first_id)
    assert [work['id'] for work in tese['works']] == [
        second_work_id,
        first_work_id,
    ]

    with pytest.raises(ValueError, match='cada obra'):
        service.reorder_works(first_id, [first_work_id])

    service.remove_work(first_id, second_work_id)
    service.update(first_id, {
        'name': 'Tese revisada',
        'description': '',
    })
    updated = next(
        record
        for record in service.list_compilations()
        if record['id'] == first_id
    )
    assert updated['name'] == 'Tese revisada'
    assert updated['description'] is None
    assert [work['id'] for work in updated['works']] == [first_work_id]

    service.delete(second_id)
    assert [record['id'] for record in service.list_compilations()] == [
        first_id
    ]


def test_database_prevents_duplicate_work_and_position(
    compilation_database,
):
    service = CompilationService()
    compilation_id = service.create({
        'name': 'Coleção',
        'description': None,
    })
    first_work_id = create_work('Obra A')
    second_work_id = create_work('Obra B')
    service.add_work(compilation_id, first_work_id)

    with db_module.SessionLocal() as session:
        session.add(CompilationWork(
            compilation_id=compilation_id,
            bib_res_id=first_work_id,
            position=4,
        ))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        session.add(CompilationWork(
            compilation_id=compilation_id,
            bib_res_id=second_work_id,
            position=0,
        ))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


def test_deleting_compilation_preserves_works_and_fragments(
    compilation_database,
):
    resource_id = create_work('Obra preservada')
    service = CompilationService()
    compilation_id = service.create({
        'name': 'Projeto temporário',
        'description': None,
    })
    service.add_work(compilation_id, resource_id)

    with db_module.SessionLocal() as session:
        session.add(Fragment(
            excerpt='Trecho que deve continuar disponível.',
            fragment_type='quote',
            bib_res_id=resource_id,
            location_type='Página',
            location_value='12',
        ))
        session.commit()

    service.delete(compilation_id)

    with db_module.SessionLocal() as session:
        assert session.get(BibliographicResource, resource_id) is not None
        fragment = session.scalar(
            select(Fragment).where(Fragment.bib_res_id == resource_id)
        )
        assert fragment is not None
        assert fragment.excerpt == 'Trecho que deve continuar disponível.'
        assert session.scalars(select(CompilationWork)).all() == []


def test_deleting_work_removes_membership_but_not_compilation(
    compilation_database,
):
    resource_id = create_work('Obra excluída')
    service = CompilationService()
    compilation_id = service.create({
        'name': 'Projeto mantido',
        'description': None,
    })
    service.add_work(compilation_id, resource_id)

    with db_module.SessionLocal() as session:
        resource = session.get(BibliographicResource, resource_id)
        assert resource is not None
        WorkRepository(session).remove_work(resource)

    record = service.list_compilations()[0]
    assert record['id'] == compilation_id
    assert record['works'] == []


def test_compilation_tables_are_created_for_existing_database(
    compilation_database,
):
    CompilationWork.__table__.drop(compilation_database)
    Compilation.__table__.drop(compilation_database)

    db_module.init_db()

    database_inspector = inspect(compilation_database)
    assert database_inspector.has_table('compilations')
    assert database_inspector.has_table('compilation_works')
    assert database_inspector.has_table('compilation_fragments')
    assert database_inspector.has_table('compilation_sections')


def test_fragment_membership_is_unique_and_scoped_to_compilation(
    compilation_database,
):
    service = CompilationService()
    first_work_id = create_work('Obra vinculada')
    other_work_id = create_work('Obra não vinculada')
    first_id = service.create({'name': 'Projeto A', 'description': None})
    second_id = service.create({'name': 'Projeto B', 'description': None})
    service.add_work(first_id, first_work_id)
    service.add_work(second_id, first_work_id)
    fragment_id = FragmentService().create({
        'fragment_type': 'comment',
        'excerpt': 'Observação compartilhável.',
        'bib_res_id': first_work_id,
        'location_type': None,
        'location_value': None,
    })

    service.add_fragment(first_id, fragment_id)
    service.add_fragment(second_id, fragment_id)
    with pytest.raises(ValueError, match='já pertence'):
        service.add_fragment(first_id, fragment_id)

    with pytest.raises(ValueError, match='Inclua a obra'):
        service.add_fragment(
            first_id,
            FragmentService().create({
                'fragment_type': 'comment',
                'excerpt': 'Fragmento de outra obra.',
                'bib_res_id': other_work_id,
                'location_type': None,
                'location_value': None,
            }),
        )

    service.remove_work(first_id, first_work_id)
    records = service.list_compilations()
    first = next(record for record in records if record['id'] == first_id)
    second = next(record for record in records if record['id'] == second_id)
    assert first['works'] == []
    assert second['works'][0]['fragments'][0]['is_member'] is True
    assert fragment_id in {
        fragment['id'] for fragment in FragmentService().list_fragments()
    }


def test_caderno_notes_and_order_are_scoped_to_each_compilation(
    compilation_database,
):
    service = CompilationService()
    work_id = create_work('Obra com fragmentos ordenáveis')
    first_compilation = service.create({
        'name': 'Projeto A',
        'description': None,
    })
    second_compilation = service.create({
        'name': 'Projeto B',
        'description': None,
    })
    service.add_work(first_compilation, work_id)
    service.add_work(second_compilation, work_id)
    fragment_service = FragmentService()
    first_fragment = fragment_service.create({
        'fragment_type': 'quote',
        'excerpt': 'Primeiro trecho.',
        'bib_res_id': work_id,
        'location_type': 'Página',
        'location_value': '10',
    })
    second_fragment = fragment_service.create({
        'fragment_type': 'comment',
        'excerpt': 'Segundo trecho.',
        'bib_res_id': work_id,
        'location_type': None,
        'location_value': None,
    })
    service.add_fragment(first_compilation, first_fragment)
    service.add_fragment(first_compilation, second_fragment)
    service.add_fragment(second_compilation, first_fragment)
    section_id = service.create_section(first_compilation, 'Introdução')
    service.update_fragment_note(
        first_compilation,
        first_fragment,
        'Usar na introdução.',
    )
    service.assign_fragment_to_section(
        first_compilation,
        first_fragment,
        section_id,
    )
    service.assign_fragment_to_section(
        first_compilation,
        second_fragment,
        section_id,
    )
    service.reorder_section_fragments(
        first_compilation,
        section_id,
        [second_fragment, first_fragment],
    )

    records = service.list_compilations()
    project_a = next(
        record for record in records if record['id'] == first_compilation
    )
    project_b = next(
        record for record in records if record['id'] == second_compilation
    )
    selected_a = [
        fragment
        for fragment in project_a['works'][0]['fragments']
        if fragment['is_member']
    ]
    selected_b = [
        fragment
        for fragment in project_b['works'][0]['fragments']
        if fragment['is_member']
    ]
    assert [fragment['id'] for fragment in selected_a] == [
        second_fragment,
        first_fragment,
    ]
    assert [fragment['project_position'] for fragment in selected_a] == [0, 1]
    assert all(fragment['section_id'] == section_id for fragment in selected_a)
    assert selected_a[1]['work_note'] == 'Usar na introdução.'
    assert selected_b[0]['work_note'] is None

    with pytest.raises(ValueError, match='cada fragmento'):
        service.reorder_section_fragments(
            first_compilation,
            section_id,
            [first_fragment],
        )

    service.remove_fragment(first_compilation, second_fragment)
    project_a = next(
        record
        for record in service.list_compilations()
        if record['id'] == first_compilation
    )
    remaining = next(
        fragment
        for fragment in project_a['works'][0]['fragments']
        if fragment['is_member']
    )
    assert remaining['id'] == first_fragment
    assert remaining['project_position'] == 0
    assert remaining['section_id'] == section_id
    assert remaining['work_note'] == 'Usar na introdução.'
    assert any(
        fragment['id'] == second_fragment
        for fragment in fragment_service.list_fragments()
    )


def test_migrates_existing_caderno_membership_positions(compilation_database):
    service = CompilationService()
    work_id = create_work('Obra com associação antiga')
    compilation_id = service.create({
        'name': 'Projeto legado',
        'description': None,
    })
    service.add_work(compilation_id, work_id)
    fragment_service = FragmentService()
    first_id = fragment_service.create({
        'fragment_type': 'comment',
        'excerpt': 'Primeiro fragmento criado.',
        'bib_res_id': work_id,
        'location_type': None,
        'location_value': None,
    })
    second_id = fragment_service.create({
        'fragment_type': 'comment',
        'excerpt': 'Segundo fragmento criado.',
        'bib_res_id': work_id,
        'location_type': None,
        'location_value': None,
    })

    with compilation_database.begin() as connection:
        connection.execute(text('DROP TABLE compilation_fragments'))
        connection.execute(text(
            """
            CREATE TABLE compilation_fragments (
                id INTEGER PRIMARY KEY,
                compilation_id INTEGER NOT NULL,
                fragment_id INTEGER NOT NULL,
                work_note TEXT,
                CONSTRAINT uq_compilation_fragment
                    UNIQUE (compilation_id, fragment_id),
                FOREIGN KEY(compilation_id) REFERENCES compilations(id),
                FOREIGN KEY(fragment_id) REFERENCES fragments(id)
            )
            """
        ))
        connection.execute(text(
            """
            INSERT INTO compilation_fragments
                (id, compilation_id, fragment_id, work_note)
            VALUES
                (1, :compilation_id, :second_id, 'Nota preservada B'),
                (2, :compilation_id, :first_id, 'Nota preservada A')
            """
        ), {
            'compilation_id': compilation_id,
            'second_id': second_id,
            'first_id': first_id,
        })

    db_module.init_db()

    columns = {
        column['name']
        for column in inspect(compilation_database).get_columns(
            'compilation_fragments'
        )
    }
    assert {'position', 'work_note', 'section_id'} <= columns
    migrated = next(
        record
        for record in service.list_compilations()
        if record['id'] == compilation_id
    )['works'][0]['fragments']
    assert [
        (fragment['id'], fragment['project_position'])
        for fragment in migrated
    ] == [(first_id, 0), (second_id, 1)]
    assert [
        (fragment['id'], fragment['section_id'], fragment['work_note'])
        for fragment in migrated
    ] == [
        (first_id, None, 'Nota preservada A'),
        (second_id, None, 'Nota preservada B'),
    ]


def test_outline_sections_organize_members_without_losing_fragments(
    compilation_database,
):
    service = CompilationService()
    work_id = create_work('Fonte para o argumento')
    compilation_id = service.create({
        'name': 'Projeto de escrita',
        'description': None,
    })
    service.add_work(compilation_id, work_id)
    fragment_service = FragmentService()
    fragment_ids = [
        fragment_service.create({
            'fragment_type': 'quote',
            'excerpt': f'Trecho {index}.',
            'bib_res_id': work_id,
            'location_type': 'Página',
            'location_value': str(index),
        })
        for index in (1, 2)
    ]
    for fragment_id in fragment_ids:
        service.add_fragment(compilation_id, fragment_id)

    first_section = service.create_section(
        compilation_id,
        '  Introdução  ',
        '  Delimitar a questão.  ',
    )
    second_section = service.create_section(
        compilation_id,
        'Desenvolvimento',
    )
    service.update_fragment_note(
        compilation_id,
        fragment_ids[0],
        'Relaciona a fonte ao argumento.',
    )
    service.assign_fragment_to_section(
        compilation_id,
        fragment_ids[0],
        first_section,
    )
    service.assign_fragment_to_section(
        compilation_id,
        fragment_ids[1],
        first_section,
    )
    service.reorder_section_fragments(
        compilation_id,
        first_section,
        list(reversed(fragment_ids)),
    )
    service.reorder_sections(
        compilation_id,
        [second_section, first_section],
    )

    record = service.list_compilations()[0]
    assert [
        (section['id'], section['position'])
        for section in record['sections']
    ] == [(second_section, 0), (first_section, 1)]
    assert record['sections'][1]['title'] == 'Introdução'
    assert record['sections'][1]['central_idea'] == 'Delimitar a questão.'
    selected = [
        fragment
        for fragment in record['works'][0]['fragments']
        if fragment['is_member']
    ]
    assert [fragment['id'] for fragment in selected] == list(
        reversed(fragment_ids)
    )
    assert all(fragment['section_id'] == first_section for fragment in selected)
    assert selected[1]['work_note'] == 'Relaciona a fonte ao argumento.'

    service.assign_fragment_to_section(
        compilation_id,
        fragment_ids[0],
        second_section,
    )
    service.assign_fragment_to_section(
        compilation_id,
        fragment_ids[0],
        first_section,
    )
    service.delete_section(compilation_id, first_section)
    record = service.list_compilations()[0]
    selected = [
        fragment
        for fragment in record['works'][0]['fragments']
        if fragment['is_member']
    ]
    assert all(fragment['section_id'] is None for fragment in selected)
    assert next(
        fragment['work_note']
        for fragment in selected
        if fragment['id'] == fragment_ids[0]
    ) == 'Relaciona a fonte ao argumento.'
    assert len(record['sections']) == 1
    assert {
        fragment['id'] for fragment in fragment_service.list_fragments()
    } == set(fragment_ids)


def test_sections_and_section_assignments_are_compilation_scoped(
    compilation_database,
):
    service = CompilationService()
    work_id = create_work('Obra compartilhada')
    compilation_ids = [
        service.create({'name': name, 'description': None})
        for name in ('Projeto A', 'Projeto B')
    ]
    for compilation_id in compilation_ids:
        service.add_work(compilation_id, work_id)
    fragment_id = FragmentService().create({
        'fragment_type': 'comment',
        'excerpt': 'Comentário reutilizado.',
        'bib_res_id': work_id,
        'location_type': None,
        'location_value': None,
    })
    service.add_fragment(compilation_ids[0], fragment_id)
    section_id = service.create_section(compilation_ids[0], 'Ideia A')

    with pytest.raises(ValueError, match='não pertence'):
        service.assign_fragment_to_section(
            compilation_ids[0],
            fragment_id,
            section_id + 1,
        )
    with pytest.raises(ValueError, match='selecionado'):
        service.assign_fragment_to_section(
            compilation_ids[1],
            fragment_id,
            section_id,
        )
    with pytest.raises(ValueError, match='nome da seção'):
        service.create_section(compilation_ids[0], '   ')


def test_caderno_notes_and_order_are_scoped_to_each_compilation(
    compilation_database,
):
    service = CompilationService()
    work_id = create_work('Obra com fragmentos ordenáveis')
    first_compilation = service.create({
        'name': 'Projeto A',
        'description': None,
    })
    second_compilation = service.create({
        'name': 'Projeto B',
        'description': None,
    })
    service.add_work(first_compilation, work_id)
    service.add_work(second_compilation, work_id)
    fragment_service = FragmentService()
    first_fragment = fragment_service.create({
        'fragment_type': 'quote',
        'excerpt': 'Primeiro trecho.',
        'bib_res_id': work_id,
        'location_type': 'Página',
        'location_value': '10',
    })
    second_fragment = fragment_service.create({
        'fragment_type': 'comment',
        'excerpt': 'Segundo trecho.',
        'bib_res_id': work_id,
        'location_type': None,
        'location_value': None,
    })
    service.add_fragment(first_compilation, first_fragment)
    service.add_fragment(first_compilation, second_fragment)
    service.add_fragment(second_compilation, first_fragment)
    section_id = service.create_section(first_compilation, 'Introdução')
    service.update_fragment_note(
        first_compilation,
        first_fragment,
        'Usar na introdução.',
    )
    service.assign_fragment_to_section(
        first_compilation,
        first_fragment,
        section_id,
    )
    service.assign_fragment_to_section(
        first_compilation,
        second_fragment,
        section_id,
    )
    service.reorder_section_fragments(
        first_compilation,
        section_id,
        [second_fragment, first_fragment],
    )

    records = service.list_compilations()
    project_a = next(
        record for record in records if record['id'] == first_compilation
    )
    project_b = next(
        record for record in records if record['id'] == second_compilation
    )
    selected_a = [
        fragment
        for fragment in project_a['works'][0]['fragments']
        if fragment['is_member']
    ]
    selected_b = [
        fragment
        for fragment in project_b['works'][0]['fragments']
        if fragment['is_member']
    ]
    assert [fragment['id'] for fragment in selected_a] == [
        second_fragment,
        first_fragment,
    ]
    assert [fragment['project_position'] for fragment in selected_a] == [0, 1]
    assert all(fragment['section_id'] == section_id for fragment in selected_a)
    assert selected_a[1]['work_note'] == 'Usar na introdução.'
    assert selected_b[0]['work_note'] is None

    with pytest.raises(ValueError, match='cada fragmento'):
        service.reorder_section_fragments(
            first_compilation,
            section_id,
            [first_fragment],
        )

    service.remove_fragment(first_compilation, second_fragment)
    project_a = next(
        record
        for record in service.list_compilations()
        if record['id'] == first_compilation
    )
    remaining = next(
        fragment
        for fragment in project_a['works'][0]['fragments']
        if fragment['is_member']
    )
    assert remaining['id'] == first_fragment
    assert remaining['project_position'] == 0
    assert remaining['section_id'] == section_id
    assert remaining['work_note'] == 'Usar na introdução.'
    assert any(
        fragment['id'] == second_fragment
        for fragment in fragment_service.list_fragments()
    )


def test_migrates_existing_caderno_membership_positions(compilation_database):
    service = CompilationService()
    work_id = create_work('Obra com associação antiga')
    compilation_id = service.create({
        'name': 'Projeto legado',
        'description': None,
    })
    service.add_work(compilation_id, work_id)
    fragment_service = FragmentService()
    later_id = fragment_service.create({
        'fragment_type': 'comment',
        'excerpt': 'Criado primeiro.',
        'bib_res_id': work_id,
        'location_type': None,
        'location_value': None,
    })
    earlier_id = fragment_service.create({
        'fragment_type': 'comment',
        'excerpt': 'Criado depois.',
        'bib_res_id': work_id,
        'location_type': None,
        'location_value': None,
    })

    with compilation_database.begin() as connection:
        connection.execute(text('DROP TABLE compilation_fragments'))
        connection.execute(text(
            """
            CREATE TABLE compilation_fragments (
                id INTEGER PRIMARY KEY,
                compilation_id INTEGER NOT NULL,
                fragment_id INTEGER NOT NULL,
                work_note TEXT,
                CONSTRAINT uq_compilation_fragment
                    UNIQUE (compilation_id, fragment_id),
                FOREIGN KEY(compilation_id) REFERENCES compilations(id),
                FOREIGN KEY(fragment_id) REFERENCES fragments(id)
            )
            """
        ))
        connection.execute(text(
            """
            INSERT INTO compilation_fragments
                (id, compilation_id, fragment_id, work_note)
            VALUES
                (1, :compilation_id, :later_id, 'Nota preservada B'),
                (2, :compilation_id, :earlier_id, 'Nota preservada A')
            """
        ), {
            'compilation_id': compilation_id,
            'later_id': later_id,
            'earlier_id': earlier_id,
        })

    db_module.init_db()

    columns = {
        column['name']
        for column in inspect(compilation_database).get_columns(
            'compilation_fragments'
        )
    }
    assert {'position', 'work_note', 'section_id'} <= columns
    migrated = next(
        record
        for record in service.list_compilations()
        if record['id'] == compilation_id
    )['works'][0]['fragments']
    assert [
        (fragment['id'], fragment['project_position'])
        for fragment in migrated
    ] == [(later_id, 0), (earlier_id, 1)]
    assert [
        (fragment['id'], fragment['section_id'], fragment['work_note'])
        for fragment in migrated
    ] == [
        (later_id, None, 'Nota preservada B'),
        (earlier_id, None, 'Nota preservada A'),
    ]


def test_creating_compilation_fragment_links_it_to_project(
    compilation_database,
):
    service = CompilationService()
    work_id = create_work('Obra do projeto')
    compilation_id = service.create({
        'name': 'Projeto de leitura',
        'description': None,
    })
    service.add_work(compilation_id, work_id)

    fragment_id = service.create_fragment(compilation_id, {
        'fragment_type': 'comment',
        'excerpt': 'Criado pelo hub.',
        'bib_res_id': work_id,
        'location_type': None,
        'location_value': None,
    })
    record = service.list_compilations()[0]
    assert record['works'][0]['fragments'][0]['id'] == fragment_id
    assert record['works'][0]['fragments'][0]['is_member'] is True

    with pytest.raises(ValueError, match='Inclua a obra'):
        service.create_fragment(compilation_id, {
            'fragment_type': 'comment',
            'excerpt': 'Obra não vinculada.',
            'bib_res_id': create_work('Outra obra'),
            'location_type': None,
            'location_value': None,
        })


def test_compilation_search_and_hub_composition():
    from src.configs.settings import (
        COLORS,
        FONT_FAMILIES,
        FONT_SIZES,
        FONT_WEIGHTS,
        ICON_SIZES,
        MAIN_VIEW_CARDS,
        PAGE_FONTS,
        TEXTS,
        UI,
    )
    from src.utils.types import ViewConfig
    from src.views.compilations import CompilationsComposer

    config = ViewConfig(
        colors=COLORS,
        page_fonts=PAGE_FONTS,
        font_families=FONT_FAMILIES,
        font_sizes=FONT_SIZES,
        icon_sizes=ICON_SIZES,
        font_weights=FONT_WEIGHTS,
        ui=UI,
        texts=TEXTS,
        core_menus={},
        main_view_cards=MAIN_VIEW_CARDS,
    )
    compilation: CompilationRecord = {
        'id': 1,
        'name': 'Tese',
        'description': None,
        'sections': [{
            'id': 30,
            'title': 'Argumento',
            'central_idea': 'Tese a sustentar.',
            'position': 0,
        }],
        'works': [
            {
                'id': 10,
                'title': 'Obra existente',
                'position': 0,
                'fragments': [{
                    'id': 20,
                    'fragment_type': 'quote',
                    'excerpt': 'Trecho destacado.',
                    'bib_res_id': 10,
                    'work_title': 'Obra existente',
                    'citation_author': 'Autor',
                    'display_year': '2024',
                    'location_type': 'Página',
                    'location_value': '12',
                    'is_member': True,
                    'project_position': 0,
                    'work_note': 'Preparar argumento.',
                    'section_id': 30,
                }, {
                    'id': 22,
                    'fragment_type': 'quote',
                    'excerpt': 'Outro trecho selecionado.',
                    'bib_res_id': 10,
                    'work_title': 'Obra existente',
                    'citation_author': 'Autor',
                    'display_year': '2024',
                    'location_type': 'Página',
                    'location_value': '14',
                    'is_member': True,
                    'project_position': 1,
                    'work_note': None,
                    'section_id': None,
                }, {
                    'id': 21,
                    'fragment_type': 'comment',
                    'excerpt': 'Comentário ainda disponível.',
                    'bib_res_id': 10,
                    'work_title': 'Obra existente',
                    'citation_author': 'Autor',
                    'display_year': '2024',
                    'location_type': None,
                    'location_value': None,
                    'is_member': False,
                    'project_position': None,
                    'work_note': None,
                    'section_id': None,
                }],
            },
            {
                'id': 12,
                'title': 'Outra obra',
                'position': 1,
                'fragments': [],
            },
        ],
    }
    dialogs = []
    page = SimpleNamespace(
        update=lambda: None,
        show_dialog=dialogs.append,
        pop_dialog=lambda: None,
    )
    membership_changes = []
    copied_cadernos = []
    note_changes = []
    assigned_sections = []
    created_sections = []

    def assign_section(
        _compilation_id: int,
        fragment_id: int,
        section_id: int | None,
    ) -> bool:
        assigned_sections.append((fragment_id, section_id))
        return True

    def create_section(
        compilation_id: int,
        title: str,
        central_idea: str | None,
    ) -> int:
        created_sections.append((compilation_id, title, central_idea))
        return 40

    def set_fragment_membership(
        compilation_id: int,
        fragment_id: int,
        selected: bool,
    ) -> bool:
        membership_changes.append((compilation_id, fragment_id, selected))
        return True

    async def copy_caderno(text: str) -> None:
        copied_cadernos.append(text)

    def save_fragment_note(
        _compilation_id: int,
        fragment_id: int,
        note: str | None,
    ) -> bool:
        note_changes.append((fragment_id, note))
        return True

    composer = CompilationsComposer(
        page=page,
        config=config,
        compilations=[compilation],
        search_works=lambda _query: [
            (10, 'Obra existente'),
            (11, 'Obra nova'),
        ],
        refresh_compilations=lambda: [compilation],
        on_create=lambda _payload: None,
        on_update=lambda _id, _payload: True,
        on_delete=lambda _id: True,
        on_add_work=lambda _compilation_id, _work_id: True,
        on_remove_work=lambda _compilation_id, _work_id: True,
        on_reorder_works=lambda _compilation_id, _ids: True,
        on_fragment_membership=set_fragment_membership,
        on_fragment_note=save_fragment_note,
        on_create_section=create_section,
        on_update_section=lambda _id, _section, _title, _idea: True,
        on_delete_section=lambda _id, _section: True,
        on_reorder_sections=lambda _id, _sections: True,
        on_assign_fragment_to_section=assign_section,
        on_reorder_section_fragments=lambda _id, _section, _fragments: True,
        on_copy_caderno=copy_caderno,
        on_create_work=lambda _compilation_id: None,
        on_edit_work=lambda _compilation_id, _work_id: None,
        on_create_fragment=lambda _compilation_id, _work_id: None,
        on_edit_fragment=lambda _compilation_id, _fragment: None,
    )

    for field in (
        composer.compilation_search,
        composer.new_name,
        composer.new_description,
    ):
        assert field.color == COLORS['text']
        assert field.text_style.color == COLORS['text']
        assert field.hint_style.color == COLORS['muted']
        assert field.label_style.color == COLORS['muted']
        assert field.bgcolor == COLORS['surface']
        assert field.border_color == COLORS['border']
        assert field.focused_border_color == COLORS['gold']

    composer.compose()
    composer._search_compilations(SimpleNamespace(
        control=SimpleNamespace(value='tese')
    ))
    assert composer._filtered_compilations() == [compilation]
    assert composer.compilation_matches.visible
    assert composer.compilation_matches.controls[0].content.controls[0].value == (
        'Tese'
    )

    composer._open_hub(compilation['id'])
    assert composer.active_hub is not None
    assert composer.active_hub.dialog.modal is True
    compilation['sections'].append({
        'id': 31,
        'title': 'Conclusão',
        'central_idea': None,
        'position': 1,
    })
    hub_content = composer.active_hub._compose_content()
    tabs = hub_content.content.controls[2]
    assert [tab.label for tab in tabs.content.controls[0].tabs] == [
        'Visão geral',
        'Obras e fragmentos',
        'Caderno de trabalho',
    ]
    tab_bar = tabs.content.controls[0]
    for style in (
        tab_bar.label_text_style,
        tab_bar.unselected_label_text_style,
    ):
        assert style.font_family == FONT_FAMILIES['cormorant']
        assert style.size == FONT_SIZES['cormorant_small']
        assert style.weight == FONT_WEIGHTS['cormorant_semibold']
    hub_heading = hub_content.content.controls[0].controls[0].controls
    assert hub_heading[0].size == FONT_SIZES['cormorant_large']
    assert hub_heading[1].size == FONT_SIZES['montserrat_large']
    assert (
        tab_bar.label_text_style.size
        <= min(hub_heading[0].size, hub_heading[1].size)
    )

    hub = composer.active_hub
    assert hub.dialog.bgcolor == COLORS['surface']
    assert hub_content.bgcolor == COLORS['surface']
    button_size = FONT_SIZES['montserrat_medium']
    button_weight = FONT_WEIGHTS['montserrat_normal']
    modal_close_text = hub.dialog.actions[0].content
    assert modal_close_text.font_family == FONT_FAMILIES['montserrat']
    assert modal_close_text.size == button_size
    assert modal_close_text.weight == button_weight
    assert hub.dialog.actions[0].style.text_style.font_family == (
        FONT_FAMILIES['montserrat']
    )
    assert hub.dialog.actions[0].style.text_style.size == button_size
    assert hub.dialog.actions[0].style.text_style.weight == button_weight

    overview = hub._compose_overview()
    save_button = overview.controls[-1].controls[0]
    save_text = save_button.content
    assert save_text.font_family == FONT_FAMILIES['montserrat']
    assert save_text.size == button_size
    assert save_text.weight == button_weight
    assert save_button.style.text_style.font_family == (
        FONT_FAMILIES['montserrat']
    )
    assert save_button.style.text_style.size == button_size
    assert save_button.style.text_style.weight == button_weight
    summary_labels = [
        card.content.controls[1]
        for card in overview.controls[3].controls
    ]
    assert all(label.size >= button_size for label in summary_labels)

    works_view = hub._compose_works_and_fragments()
    create_work_button = works_view.controls[0].controls[1]
    assert len(works_view.controls[0].controls) == 2
    caderno_view = hub._compose_caderno()
    ideas_view = caderno_view.content
    copy_caderno_button = ideas_view.controls[0].controls[1]
    assert copy_caderno_button.content.value == 'Copiar esqueleto'
    assert not copy_caderno_button.disabled
    assert ideas_view.controls[0].controls[2].content.value == (
        'Editar caderno'
    )
    unassigned_group = ideas_view.controls[1]
    assert unassigned_group.controls[0].value == 'A organizar (1)'
    first_idea_card = ideas_view.controls[2]
    first_idea_controls = first_idea_card.content.controls
    assert first_idea_controls[0].controls[0].value == 'Argumento'
    assert first_idea_controls[1].value == 'Tese a sustentar.'
    assert isinstance(first_idea_controls[1], ft.Text)
    assert isinstance(
        first_idea_controls[2].content.controls[0].controls[0],
        ft.Text,
    )
    asyncio.run(copy_caderno_button.on_click(SimpleNamespace()))
    assert copied_cadernos[0].startswith('Tese\n\n## Argumento')
    assert 'Tese a sustentar.' in copied_cadernos[0]
    assert '## Conclusão' in copied_cadernos[0]
    assert 'Citação: Trecho destacado.' in copied_cadernos[0]
    assert 'Outro trecho selecionado.' in copied_cadernos[0]
    assert '(Autor, 2024, p. 12)' in copied_cadernos[0]
    assert 'Nota de articulação: Preparar argumento.' in copied_cadernos[0]
    create_work_text = create_work_button.content
    assert create_work_text.font_family == FONT_FAMILIES['montserrat']
    assert create_work_text.size == button_size
    assert create_work_text.weight == button_weight
    assert create_work_button.style.text_style.font_family == (
        FONT_FAMILIES['montserrat']
    )
    assert create_work_button.style.text_style.size == button_size
    assert create_work_button.style.text_style.weight == button_weight
    work_layout = hub._compose_work(0).content
    fragments_layout = work_layout.controls[1]
    included_group, available_group = fragments_layout.controls
    assert included_group.controls[0].value == (
        'Selecionados para o caderno (2)'
    )
    assert available_group.controls[0].value == (
        'Materiais disponíveis (1)'
    )
    fragment_card = included_group.controls[1]
    fragment_texts = (
        fragment_card.content.controls[0].controls[0].controls
    )
    assert all(text.size >= button_size for text in fragment_texts[:3])
    assignment_control = fragment_card.content.controls[1].content
    assert assignment_control.text_style.color == COLORS['text']
    assert assignment_control.text_style.size >= FONT_SIZES[
        'montserrat_medium'
    ]
    assert assignment_control.bgcolor == COLORS['surface']
    assert all(
        option.content.color == COLORS['text']
        and option.content.size >= FONT_SIZES['montserrat_medium']
        for option in assignment_control.options
    )
    assert assignment_control.value == '30'
    assignment_control.on_select(SimpleNamespace(
        control=SimpleNamespace(value='31')
    ))
    assert assigned_sections == [(20, 31)]
    available_card = available_group.controls[1]
    available_destination = available_card.content.controls[1].content
    assert available_destination.value == 'not_selected'
    assert any(
        option.key == 'create_section'
        and option.content.color == COLORS['text']
        for option in available_destination.options
    )
    available_destination.on_select(SimpleNamespace(
        control=SimpleNamespace(value='create_section')
    ))
    assert len(dialogs) == 2
    section_dialog = dialogs[-1]
    section_dialog.content.controls[0].value = 'Nova ideia'
    section_dialog.content.controls[1].value = 'Argumento novo'
    section_dialog.actions[1].on_click(SimpleNamespace())
    assert membership_changes == [
        (compilation['id'], 21, True),
    ]
    assert created_sections == [
        (compilation['id'], 'Nova ideia', 'Argumento novo')
    ]
    assert assigned_sections == [(20, 31), (21, 40)]
    assert hub._fragment_count_label() == (
        '2 de 3 fragmentos selecionados para o caderno'
    )
    hub._toggle_outline_edit(SimpleNamespace())
    assert hub.editing_outline is True
    edit_view = hub._compose_caderno().content
    assert edit_view.controls[0].controls[2].content.value == (
        'Concluir edição'
    )
    assert isinstance(
        edit_view.controls[3].content.controls[0].controls[0],
        ft.TextField,
    )
    assert isinstance(
        edit_view.controls[3].content.controls[1],
        ft.TextField,
    )
    hub._toggle_outline_edit(SimpleNamespace())
    assert hub.editing_outline is False

    composer._search_compilations(SimpleNamespace(
        control=SimpleNamespace(value='tese')
    ))
    compilation_match = composer.compilation_matches.controls[0].content.controls
    assert compilation_match[0].font_family == FONT_FAMILIES['montserrat']
    assert compilation_match[0].size == button_size
    assert compilation_match[0].weight == button_weight
    match_button = composer.compilation_matches.controls[0]
    assert match_button.style.text_style.font_family == (
        FONT_FAMILIES['montserrat']
    )
    assert match_button.style.text_style.size == button_size
    assert match_button.style.text_style.weight == button_weight
    header_button_text = composer._compose_header().content.controls[1].content
    assert header_button_text.font_family == FONT_FAMILIES['montserrat']
    assert header_button_text.size == button_size
    assert header_button_text.weight == button_weight

import asyncio
from datetime import datetime
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
    assert all(
        fragment['section_id'] == first_section for fragment in selected
    )
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
        'excerpt': 'Paráfrase reutilizado.',
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


def _view_config(colors=None):
    from src.configs.settings import (
        COLORS_LIGHT,
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

    return ViewConfig(
        colors=colors or COLORS_LIGHT,
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


def _children(control):
    for attr in ('content', 'controls', 'actions', 'title', 'items'):
        value = getattr(control, attr, None)
        if isinstance(value, list):
            yield from (child for child in value if isinstance(child, ft.Control))
        elif isinstance(value, ft.Control):
            yield value


def _find_all(control, predicate):
    found = []
    stack = [control]
    while stack:
        current = stack.pop()
        if predicate(current):
            found.append(current)
        stack.extend(reversed(list(_children(current))))
    return found


def _texts(control) -> list[str]:
    return [
        text.value
        for text in _find_all(control, lambda item: isinstance(item, ft.Text))
        if isinstance(text.value, str) and text.value
    ]


def _button(control, label):
    """Botão do kit (Container com ``data['label']``) pelo rótulo."""
    return next(
        item
        for item in _find_all(control, lambda c: isinstance(getattr(c, 'data', None), dict) and 'label' in c.data)
        if item.data['label'].value == label
    )


def _menus(control):
    return _find_all(control, lambda item: isinstance(item, ft.PopupMenuButton))


def _sample_compilation() -> CompilationRecord:
    return {
        'id': 1,
        'name': 'Tese',
        'description': 'Pesquisa principal',
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
                'authors': 'Ana Autora',
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
                    'excerpt': 'Paráfrase ainda disponível.',
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


class _Recorder:
    """Callbacks falsos que registram cada chamada."""

    def __init__(self, compilation: CompilationRecord) -> None:
        self.compilation = compilation
        self.calls: list[tuple] = []
        self.copied: list[str] = []
        self.navigated: list[str] = []
        self.dialogs: list = []
        self.next_section_id = 40
        self.page = SimpleNamespace(
            update=lambda: None,
            show_dialog=self.dialogs.append,
            pop_dialog=lambda: None,
            clipboard=SimpleNamespace(set=self.copy),
            open=lambda *args, **kwargs: None,
        )

    def record(self, name, result=True):
        def callback(*args):
            self.calls.append((name, *args))
            return result
        return callback

    def create_section(self, compilation_id, title, idea):
        self.calls.append(('create_section', compilation_id, title, idea))
        section_id = self.next_section_id
        self.next_section_id += 1
        return section_id

    async def copy(self, text):
        self.copied.append(text)

    def named(self, name):
        return [call[1:] for call in self.calls if call[0] == name]

    def composer(self, config=None, compilations=None):
        from src.utils.types import ReferencePart, TextStyle, ViewReference
        from src.views.compilations import CompilationsComposer

        def references(ids):
            return {
                work_id: ViewReference(parts=[
                    ReferencePart('AUTORA, Ana. '),
                    ReferencePart('Obra existente', TextStyle.BOLD),
                    ReferencePart('. São Paulo: Editora, 2024.'),
                ])
                for work_id in ids
                if work_id == 10
            }

        return CompilationsComposer(
            page=self.page,
            config=config or _view_config(),
            compilations=compilations if compilations is not None else [self.compilation],
            search_works=lambda _query: [(10, 'Obra existente'), (11, 'Obra nova')],
            refresh_compilations=lambda: [self.compilation],
            on_create=self.record('create', 7),
            on_update=self.record('update'),
            on_delete=self.record('delete'),
            on_add_work=self.record('add_work'),
            on_remove_work=self.record('remove_work'),
            on_reorder_works=self.record('reorder_works'),
            on_fragment_membership=self.record('membership'),
            on_fragment_note=self.record('note'),
            on_create_section=self.create_section,
            on_update_section=self.record('update_section'),
            on_delete_section=self.record('delete_section'),
            on_reorder_sections=self.record('reorder_sections'),
            on_assign_fragment_to_section=self.record('assign'),
            on_reorder_section_fragments=self.record('reorder_fragments'),
            on_copy_caderno=self.copy,
            on_create_work=self.record('create_work', None),
            on_edit_work=self.record('edit_work', None),
            on_create_fragment=self.record('create_fragment', None),
            on_edit_fragment=self.record('edit_fragment', None),
            on_navigate=self.navigated.append,
            on_open_work=self.record('open_work', None),
            work_references=references,
        )


def test_compilations_list_page_search_create_and_navigation():
    from src.configs.settings import COLORS_LIGHT

    compilation = _sample_compilation()
    compilation['created_at'] = datetime(2026, 11, 2, 15, 0)
    other = {**_sample_compilation(), 'id': 2, 'name': 'Artigo', 'description': None, 'sections': [], 'works': []}
    recorder = _Recorder(compilation)
    composer = recorder.composer(compilations=[compilation, other])

    root = composer.compose()
    texts = _texts(root)
    assert 'Compilações' in texts
    for column in ('Projeto', 'Obras', 'Fragmentos', 'Ideias', 'Criada', 'Atualizada'):
        assert column in texts
    assert len(composer.rows) == 2
    first_row = _texts(composer.rows[0])
    assert first_row[:2] == ['Tese', 'Pesquisa principal']
    assert first_row[2:5] == ['2', '2', '1']
    assert first_row[5].endswith('nov 2026')
    assert composer.compilation_search.border_color == COLORS_LIGHT['border_strong']
    assert composer.compilation_search.focused_border_color == COLORS_LIGHT['gold']

    composer._search_compilations(SimpleNamespace(control=SimpleNamespace(value='tes')))
    assert composer._filtered_compilations() == [compilation]
    assert len(composer.rows) == 1
    assert composer.count_text.value == '1 de 2'
    composer._search_compilations(SimpleNamespace(control=SimpleNamespace(value='nada disso')))
    assert composer.rows == []
    assert 'Nada encontrado' in _texts(composer.table_host)

    composer._search_compilations(SimpleNamespace(control=SimpleNamespace(value='')))
    composer.rows[0].content.on_click(None)
    assert recorder.navigated == ['compilacao:1']

    composer.new_button.on_click(None)
    create_dialog = recorder.dialogs[-1]
    assert create_dialog.modal is True
    assert _texts(create_dialog.title)[0] == 'Nova compilação'
    composer._create()
    assert recorder.named('create') == []
    assert composer.new_name.error_text
    composer.new_name.value = '  Livro  '
    composer.new_description.value = 'Sobre o livro'
    _button(create_dialog, 'Criar compilação').on_click(None)
    assert recorder.named('create') == [({'name': 'Livro', 'description': 'Sobre o livro'},)]
    assert recorder.navigated[-1] == 'compilacao:7'

    dialogs_before = len(recorder.dialogs)
    recorder.composer().compose(open_create=True)
    assert len(recorder.dialogs) == dialogs_before + 1

    empty = recorder.composer(compilations=[])
    assert 'Nenhuma compilação ainda' in _texts(empty.compose())


def test_compilation_page_header_tabs_and_caderno():
    compilation = _sample_compilation()
    compilation['sections'].append({
        'id': 31,
        'title': 'Conclusão',
        'central_idea': None,
        'position': 1,
    })
    recorder = _Recorder(compilation)
    composer = recorder.composer()
    composer.compose()

    page_control = composer.open_compilation_page(compilation['id'])
    hub = composer.active_hub
    assert composer.open_compilation_page(999) is None
    composer.active_hub = hub
    assert isinstance(page_control, ft.Container)
    assert not _find_all(page_control, lambda item: isinstance(item, ft.AlertDialog))
    assert hub.selected_tab == 'caderno'

    header_texts = _texts(hub._compose_header())
    assert header_texts[:2] == ['Tese', 'Pesquisa principal']
    for badge in ('2 obras', '2 fragmentos', '2 ideias'):
        assert badge in header_texts
    assert hub.copy_button.data['label'].value == 'Copiar esqueleto'
    assert hub.copy_button.on_click is not None
    assert hub.copy_references_button.data['label'].value == 'Copiar Referências do Caderno'
    assert hub.copy_references_button.on_click is not None
    from src.views.compilation_hub.common import menu_labels
    assert menu_labels(hub.header_menu) == ['Editar detalhes', 'Excluir compilação']

    tab_texts = _texts(hub.tab_bar)
    assert tab_texts == ['Visão geral', 'Obras e fragmentos', '2', 'Caderno de trabalho', '2']

    assert [item.data for item in hub.outline_items] == ['Argumento', 'Conclusão']
    assert hub.active_section_id == 30
    assert hub.outline_items[0].bgcolor == hub.config.colors['selected']
    assert _texts(hub.queue_item)[-2:] == ['A organizar', '1']

    first_idea, second_idea, queue = hub.writing_blocks
    first_texts = _texts(first_idea)
    assert first_texts[:2] == ['1', 'Argumento']
    assert 'Ideia central' in first_texts and 'Tese a sustentar.' in first_texts
    assert '“Trecho destacado.”' in first_texts
    assert '(Autor, 2024, p. 12)' in first_texts
    assert 'Preparar argumento.' in first_texts
    assert 'Editar nota' in first_texts
    second_texts = _texts(second_idea)
    assert 'Nenhum fragmento nesta ideia' in second_texts
    _button(second_idea, 'Escolher fragmentos').on_click(None)
    assert hub.selected_tab == 'obras'
    hub._select_tab('caderno')
    assert 'Sem nota de articulação' in _texts(queue)
    assert 'Adicionar nota' in _texts(queue)

    hub._focus_idea(31)
    assert hub.active_section_id == 31
    hub._focus_idea('queue')
    assert hub.active_section_id == 'queue'

    rail_texts = _texts(hub._compose_rail())
    assert 'Copiar esqueleto com referências' in rail_texts
    assert 'Referências' in rail_texts and '1.' in rail_texts
    assert 'Obras do projeto' in rail_texts
    assert 'Outra obra' in rail_texts and '0 fragmentos' in rail_texts
    reference = next(
        text for text in _find_all(hub._compose_rail(), lambda item: isinstance(item, ft.Text) and item.spans)
    )
    assert ''.join(span.text for span in reference.spans).startswith('AUTORA, Ana. Obra existente')

    asyncio.run(hub.copy_button.on_click(SimpleNamespace()))
    skeleton = recorder.copied[-1]
    assert skeleton.startswith('Tese\n\n## Argumento')
    assert 'Tese a sustentar.' in skeleton
    assert '## Conclusão' in skeleton
    assert 'Citação: Trecho destacado.' in skeleton
    assert 'Outro trecho selecionado.' in skeleton
    assert '(Autor, 2024, p. 12)' in skeleton
    assert 'Nota de articulação: Preparar argumento.' in skeleton
    assert '## A organizar' in skeleton
    assert '## Referências' not in skeleton
    asyncio.run(hub.rail_copy_button.on_click(SimpleNamespace()))
    with_references = recorder.copied[-1]
    assert with_references.startswith(skeleton)
    assert with_references.endswith(
        '## Referências\n\n1. AUTORA, Ana. Obra existente. São Paulo: Editora, 2024.'
    )

    asyncio.run(hub.copy_references_button.on_click(SimpleNamespace()))
    assert recorder.copied[-1] == 'AUTORA, Ana. Obra existente. São Paulo: Editora, 2024.'

    hub._select_tab('visao')
    assert hub.copy_references_button.data['label'].value == 'Copiar Referências da Compilação'


def test_compilation_page_section_and_fragment_actions():
    from src.views.compilation_hub.common import menu_labels, run_menu_item

    compilation = _sample_compilation()
    compilation['sections'].append({
        'id': 31,
        'title': 'Conclusão',
        'central_idea': None,
        'position': 1,
    })
    recorder = _Recorder(compilation)
    composer = recorder.composer()
    composer.compose()
    composer.open_compilation_page(1)
    hub = composer.active_hub

    first_idea = hub.writing_blocks[0]
    section_menu, fragment_menu = _menus(first_idea)
    assert menu_labels(section_menu) == ['Mover para baixo', 'Renomear ou editar', 'Remover ideia']
    run_menu_item(section_menu, 'Mover para baixo')
    assert recorder.named('reorder_sections') == [(1, [31, 30])]

    edit_dialog = hub._prompt_edit_section(compilation['sections'][0])
    assert edit_dialog.data['title'].value == 'Argumento'
    edit_dialog.data['title'].value = 'Argumento revisto'
    edit_dialog.data['idea'].value = '  '
    edit_dialog.data['confirm']()
    assert recorder.named('update_section') == [(1, 30, 'Argumento revisto', None)]

    new_dialog = hub._prompt_new_section()
    new_dialog.data['confirm']()
    assert recorder.named('create_section') == []
    new_dialog.data['title'].value = 'Nova ideia'
    new_dialog.data['idea'].value = 'Papel da ideia'
    new_dialog.data['confirm']()
    assert recorder.named('create_section') == [(1, 'Nova ideia', 'Papel da ideia')]

    labels = menu_labels(fragment_menu)
    assert 'Mover para “Conclusão”' in labels
    assert 'Devolver para A organizar' in labels
    assert labels[-1] == 'Retirar do caderno'
    run_menu_item(fragment_menu, 'Mover para “Conclusão”')
    assert recorder.named('assign')[-1] == (1, 20, 31)
    run_menu_item(fragment_menu, 'Devolver para A organizar')
    assert recorder.named('assign')[-1] == (1, 20, None)
    run_menu_item(fragment_menu, 'Editar fragmento')
    assert recorder.named('edit_fragment')[-1][0] == 1
    run_menu_item(fragment_menu, 'Retirar do caderno')
    assert recorder.named('membership')[-1] == (1, 20, False)
    undo_toast = recorder.dialogs[-1]
    assert isinstance(undo_toast, ft.SnackBar)
    compilation['works'][0]['fragments'][0]['is_member'] = False
    undo_toast.action.on_click(None)
    compilation['works'][0]['fragments'][0]['is_member'] = True
    assert recorder.named('membership')[-1] == (1, 20, True)
    assert recorder.named('assign')[-1] == (1, 20, 30)

    hub._move_section_fragment(30, 0, 1)
    assert recorder.named('reorder_fragments') == []
    compilation['works'][0]['fragments'][1]['section_id'] = 30
    hub._move_section_fragment(30, 0, 1)
    assert recorder.named('reorder_fragments') == [(1, 30, [22, 20])]
    compilation['works'][0]['fragments'][1]['section_id'] = None

    hub._delete_section(30)
    assert recorder.named('delete_section') == [(1, 30)]
    delete_toast = recorder.dialogs[-1]
    assert 'Argumento' in _texts(delete_toast.content)[1]
    sections_before = list(recorder.named('create_section'))
    delete_toast.action.on_click(None)
    restored = recorder.named('create_section')[len(sections_before):]
    assert restored == [(1, 'Argumento', 'Tese a sustentar.')]
    restored_id = recorder.next_section_id - 1
    assert recorder.named('assign')[-1] == (1, 20, restored_id)


def test_compilation_page_works_tab_membership_and_destination():
    from src.views.compilation_hub.common import menu_labels, run_menu_item

    compilation = _sample_compilation()
    compilation['sections'].append({
        'id': 31,
        'title': 'Conclusão',
        'central_idea': None,
        'position': 1,
    })
    recorder = _Recorder(compilation)
    composer = recorder.composer()
    composer.compose()
    composer.open_compilation_page(1)
    hub = composer.active_hub
    hub._select_tab('obras')

    assert hub.create_work_button.data['label'].value == 'Criar obra'
    hub.create_work_button.on_click(None)
    assert recorder.named('create_work') == [(1,)]

    work_card = hub._compose_work(0)
    work_texts = _texts(work_card)
    assert work_texts[:2] == ['Obra existente', 'Ana Autora · 3 fragmentos']
    assert 'Sem autoria · 0 fragmentos' in _texts(hub._compose_work(1))
    _button(work_card, 'Fragmento').on_click(None)
    assert recorder.named('create_fragment') == [(1, 10)]
    work_menu = _menus(work_card)[0]
    assert menu_labels(work_menu) == ['Mover para baixo', 'Editar obra', 'Abrir no Acervo', 'Retirar do projeto']
    run_menu_item(work_menu, 'Mover para baixo')
    assert recorder.named('reorder_works') == [(1, [12, 10])]
    run_menu_item(work_menu, 'Editar obra')
    assert recorder.named('edit_work') == [(1, 10)]
    run_menu_item(work_menu, 'Retirar do projeto')
    assert recorder.named('remove_work') == []
    recorder.dialogs[-1].data['confirm']()
    assert recorder.named('remove_work') == [(1, 10)]

    checkboxes = _find_all(work_card, lambda item: isinstance(item, ft.Checkbox))
    selectors = _find_all(work_card, lambda item: isinstance(item, ft.Dropdown))
    assert [box.value for box in checkboxes] == [True, True, False]
    assert [selector.value for selector in selectors] == ['30', 'unassigned', 'unassigned']
    assert [selector.disabled for selector in selectors] == [False, False, True]
    assert [option.key for option in selectors[0].options] == ['unassigned', '30', '31', 'create_section']
    assert all(
        option.content.color == hub.config.colors['text']
        for option in selectors[0].options
    )
    selectors[0].on_select(SimpleNamespace(control=SimpleNamespace(value='31')))
    assert recorder.named('assign') == [(1, 20, 31)]

    checkboxes[2].on_change(SimpleNamespace(control=SimpleNamespace(value=True)))
    assert recorder.named('membership') == [(1, 21, True)]
    checkboxes[1].on_change(SimpleNamespace(control=SimpleNamespace(value=False)))
    assert recorder.named('membership')[-1] == (1, 22, False)

    hub._set_fragment_destination(21, 'create_section')
    section_dialog = recorder.dialogs[-1]
    section_dialog.data['title'].value = 'Nova ideia'
    section_dialog.data['idea'].value = 'Argumento novo'
    section_dialog.data['confirm']()
    assert recorder.named('create_section') == [(1, 'Nova ideia', 'Argumento novo')]
    assert recorder.named('membership')[-1] == (1, 21, True)
    assert recorder.named('assign')[-1] == (1, 21, 40)

    hub._search_work_matches(SimpleNamespace(control=SimpleNamespace(value='o')))
    assert hub.work_matches.visible is False
    hub._search_work_matches(SimpleNamespace(control=SimpleNamespace(value='obra')))
    assert hub.work_matches.visible is True
    assert hub.work_matches_box.visible is True
    assert [row.data for row in hub.work_matches.controls] == ['Obra nova']
    hub.work_matches.controls[0].on_click(None)
    assert recorder.named('add_work') == [(1, 11)]
    assert hub.work_matches.visible is False


def test_compilation_page_overview_details_and_delete():
    from src.views.compilation_hub.common import run_menu_item

    compilation = _sample_compilation()
    compilation['created_at'] = datetime(2026, 3, 4, 15, 0)
    compilation['updated_at'] = datetime(2026, 11, 5, 15, 0)
    recorder = _Recorder(compilation)
    composer = recorder.composer()
    composer.compose()
    composer.open_compilation_page(1)
    hub = composer.active_hub
    hub._select_tab('visao')

    overview = hub._compose_overview()
    texts = _texts(overview)
    for label in ('Roteiro', '#', 'Ideia', 'Ideia central', 'Fragmentos', 'Detalhes', 'Nome', 'Descrição', 'Criada', 'Atualizada', 'Excluir compilação'):
        assert label in texts
    assert '4 mar 2026' in texts and '5 nov 2026' in texts
    assert 'Atualizada em 5 nov 2026' in _texts(hub._compose_header())
    assert len(hub.outline_rows) == 1
    assert _texts(hub.outline_rows[0])[:4] == ['1', 'Argumento', 'Tese a sustentar.', '1']
    hub.outline_rows[0].content.on_click(None)
    assert hub.selected_tab == 'caderno'

    details = hub._open_details_dialog()
    hub.name_field.value = ' '
    details.data['save']()
    assert recorder.named('update') == []
    hub.name_field.value = '  Tese revista '
    hub.description_field.value = ''
    details.data['save']()
    assert recorder.named('update') == [(1, {'name': 'Tese revista', 'description': None})]

    run_menu_item(hub.header_menu, 'Excluir compilação')
    assert recorder.named('delete') == []
    recorder.dialogs[-1].data['confirm']()
    assert recorder.named('delete') == [(1,)]
    assert recorder.navigated[-1] == 'Compilações'
    assert hub.deleted is True

    composer.refresh_compilation_hub(1)
    assert composer.rows


def test_refresh_compilation_hub_redraws_the_open_page():
    compilation = _sample_compilation()
    recorder = _Recorder(compilation)
    composer = recorder.composer()
    composer.compose()
    page_control = composer.open_compilation_page(1)
    hub = composer.active_hub
    previous_body = page_control.content
    compilation['name'] = 'Tese renomeada'
    composer.refresh_compilation_hub(1)
    assert page_control.content is not previous_body
    assert _texts(page_control)[0] == 'Tese renomeada'
    assert composer.compilations[0]['name'] == 'Tese renomeada'
    assert hub is composer.active_hub


def test_fragment_note_preserves_on_removing_from_caderno(
    compilation_database,
):
    service = CompilationService()
    work_id = create_work('Obra para teste de preservação de nota')
    compilation_id = service.create({
        'name': 'Projeto Preservação',
        'description': None,
    })
    service.add_work(compilation_id, work_id)
    fragment_service = FragmentService()
    fragment_id = fragment_service.create({
        'fragment_type': 'quote',
        'excerpt': 'Trecho com nota a ser preservada.',
        'bib_res_id': work_id,
        'location_type': 'Página',
        'location_value': '42',
    })
    service.add_fragment(compilation_id, fragment_id)
    service.update_fragment_note(
        compilation_id,
        fragment_id,
        'Nota essencial para o capítulo 1.',
    )

    # Remover do caderno (desvincular)
    service.remove_fragment(compilation_id, fragment_id)

    records = service.list_compilations()
    compilation = next(
        rec for rec in records if rec['id'] == compilation_id
    )
    fragment = next(
        frag
        for frag in compilation['works'][0]['fragments']
        if frag['id'] == fragment_id
    )
    assert fragment['is_member'] is False
    assert fragment['work_note'] == 'Nota essencial para o capítulo 1.'
    assert fragment['section_id'] is None
    assert fragment['project_position'] is None


def test_fragment_note_auto_links_when_added_to_available_material(
    compilation_database,
):
    service = CompilationService()
    work_id = create_work('Obra para teste de auto-link')
    compilation_id = service.create({
        'name': 'Projeto Auto Link',
        'description': None,
    })
    service.add_work(compilation_id, work_id)
    fragment_service = FragmentService()
    fragment_id = fragment_service.create({
        'fragment_type': 'comment',
        'excerpt': 'Paráfrase disponível mas ainda não no caderno.',
        'bib_res_id': work_id,
        'location_type': None,
        'location_value': None,
    })

    # Adicionar nota a fragmento que ainda não é membro
    service.update_fragment_note(
        compilation_id,
        fragment_id,
        'Nota que ativa o vínculo ao caderno.',
    )

    records = service.list_compilations()
    compilation = next(
        rec for rec in records if rec['id'] == compilation_id
    )
    fragment = next(
        frag
        for frag in compilation['works'][0]['fragments']
        if frag['id'] == fragment_id
    )
    assert fragment['is_member'] is True
    assert fragment['work_note'] == 'Nota que ativa o vínculo ao caderno.'
    assert fragment['project_position'] == 0
    assert fragment['section_id'] is None


def test_fragment_note_cleared_deletes_orphan_record(
    compilation_database,
):
    service = CompilationService()
    work_id = create_work('Obra para teste de limpeza de órfão')
    compilation_id = service.create({
        'name': 'Projeto Órfão',
        'description': None,
    })
    service.add_work(compilation_id, work_id)
    fragment_service = FragmentService()
    fragment_id = fragment_service.create({
        'fragment_type': 'quote',
        'excerpt': 'Trecho para teste de órfão.',
        'bib_res_id': work_id,
        'location_type': 'Página',
        'location_value': '1',
    })
    service.add_fragment(compilation_id, fragment_id)
    service.update_fragment_note(
        compilation_id,
        fragment_id,
        'Nota temporária.',
    )
    service.remove_fragment(compilation_id, fragment_id)

    # Limpar a nota de um fragmento não-membro
    service.update_fragment_note(compilation_id, fragment_id, None)

    records = service.list_compilations()
    compilation = next(
        rec for rec in records if rec['id'] == compilation_id
    )
    fragment = next(
        frag
        for frag in compilation['works'][0]['fragments']
        if frag['id'] == fragment_id
    )
    assert fragment['is_member'] is False
    assert fragment['work_note'] is None


def test_compilation_page_fragment_note_footer_and_dialog():
    compilation = _sample_compilation()
    recorder = _Recorder(compilation)
    composer = recorder.composer()
    composer.compose()
    composer.open_compilation_page(1)
    hub = composer.active_hub
    frag_with_note = compilation['works'][0]['fragments'][0]
    frag_without_note = compilation['works'][0]['fragments'][1]

    # 1. Sem nota: texto neutro e botão de adicionar
    footer = hub._compose_fragment_note(frag_without_note)
    assert _texts(footer)[0] == 'Sem nota de articulação'
    add_button = _button(footer, 'Adicionar nota')
    assert add_button.tooltip == (
        'Nota de articulação: o texto que liga este fragmento à ideia'
    )
    add_button.on_click(None)
    add_dialog = recorder.dialogs[-1]
    assert _texts(add_dialog.title)[0] == 'Nota de articulação'
    assert len(add_dialog.actions) == 2  # Cancelar, Salvar
    assert add_dialog.data['delete'] is None
    add_dialog.data['note'].value = '  Ligar ao argumento.  '
    add_dialog.data['save']()
    assert recorder.named('note')[-1] == (1, 22, 'Ligar ao argumento.')

    # 2. Com nota: o texto aparece no rodapé, com “Editar nota”
    footer = hub._compose_fragment_note(frag_with_note)
    assert _texts(footer)[0] == 'Preparar argumento.'
    _button(footer, 'Editar nota').on_click(None)
    modal = recorder.dialogs[-1]
    assert len(modal.actions) == 3  # Excluir, Cancelar, Salvar
    assert modal.data['note'].value == 'Preparar argumento.'
    assert 'Obra existente' in _texts(modal.title)[1]

    _button(modal, 'Excluir nota').on_click(None)
    assert recorder.named('note')[-1] == (1, 20, None)
    modal.data['note'].value = 'Nova nota salva'
    _button(modal, 'Salvar nota').on_click(None)
    assert recorder.named('note')[-1] == (1, 20, 'Nova nota salva')
    modal.data['note'].value = '   '
    modal.data['save']()
    assert recorder.named('note')[-1] == (1, 20, None)


def test_compilation_copy_references_with_year_disambiguation():
    import asyncio
    from types import SimpleNamespace
    from src.utils.types import ReferencePart, TextStyle, ViewReference

    compilation: CompilationRecord = {
        'id': 100,
        'name': 'Projeto Filosofia',
        'description': 'Estudo',
        'sections': [
            {'id': 1, 'title': 'Seção 1', 'central_idea': 'Ideia', 'position': 0},
        ],
        'works': [
            {
                'id': 10,
                'title': 'Zebra e mente',
                'position': 0,
                'authors': 'Silva, João',
                'citation_author': 'SILVA',
                'display_year': '2019',
                'fragments': [
                    {
                        'id': 101,
                        'fragment_type': 'quote',
                        'excerpt': 'Excerto sobre mente.',
                        'bib_res_id': 10,
                        'work_title': 'Zebra e mente',
                        'citation_author': 'SILVA',
                        'display_year': '2019',
                        'location_type': 'Página',
                        'location_value': '10',
                        'created_at': None,
                        'is_member': True,
                        'section_id': 1,
                        'project_position': 0,
                        'work_note': None,
                    }
                ],
            },
            {
                'id': 11,
                'title': 'Antelope e razão',
                'position': 1,
                'authors': 'Silva, João',
                'citation_author': 'SILVA',
                'display_year': '2019',
                'fragments': [
                    {
                        'id': 102,
                        'fragment_type': 'quote',
                        'excerpt': 'Excerto sobre razão.',
                        'bib_res_id': 11,
                        'work_title': 'Antelope e razão',
                        'citation_author': 'SILVA',
                        'display_year': '2019',
                        'location_type': 'Página',
                        'location_value': '20',
                        'created_at': None,
                        'is_member': True,
                        'section_id': 1,
                        'project_position': 1,
                        'work_note': None,
                    }
                ],
            },
        ],
    }

    recorder = _Recorder(compilation)
    composer = recorder.composer()
    composer.compilations = [compilation]

    def references(ids):
        result = {}
        if 10 in ids:
            result[10] = ViewReference(parts=[
                ReferencePart('SILVA, João. '),
                ReferencePart('Zebra e mente', TextStyle.BOLD),
                ReferencePart('. São Paulo: Atlas, 2019.'),
            ])
        if 11 in ids:
            result[11] = ViewReference(parts=[
                ReferencePart('SILVA, João. '),
                ReferencePart('Antelope e razão', TextStyle.BOLD),
                ReferencePart('. São Paulo: Atlas, 2019.'),
            ])
        return result

    composer.work_references = references
    composer.open_compilation_page(100)
    hub = composer.active_hub
    assert hub is not None

    # Verifica botão na aba caderno
    assert hub.copy_references_button.data['label'].value == 'Copiar Referências do Caderno'

    # Copia referências
    captured_rich = []
    import src.views.compilation_hub.caderno_mixin as cm
    original_copy_refs = cm.copy_references
    cm.copy_references = lambda refs: captured_rich.extend(refs) or True
    try:
        asyncio.run(hub.copy_references_button.on_click(SimpleNamespace()))
    finally:
        cm.copy_references = original_copy_refs

    assert len(captured_rich) == 2
    assert captured_rich[0].parts[1].content == 'Antelope e razão'
    assert captured_rich[0].parts[1].style == TextStyle.BOLD
    assert '2019a' in captured_rich[0].parts[2].content
    assert captured_rich[1].parts[1].content == 'Zebra e mente'
    assert captured_rich[1].parts[1].style == TextStyle.BOLD
    assert '2019b' in captured_rich[1].parts[2].content

    copied_refs = recorder.copied[-1]
    lines = copied_refs.split('\n')
    assert len(lines) == 2
    # Antelope é '2019a', Zebra é '2019b'
    assert lines[0] == 'SILVA, João. Antelope e razão. São Paulo: Atlas, 2019a.'
    assert lines[1] == 'SILVA, João. Zebra e mente. São Paulo: Atlas, 2019b.'

    # Verifica texto do caderno: citações recebem sufixos
    caderno_text = hub._caderno_text(with_references=True)
    assert '(SILVA, 2019a, p. 20)' in caderno_text
    assert '(SILVA, 2019b, p. 10)' in caderno_text
    assert '1. SILVA, João. Zebra e mente. São Paulo: Atlas, 2019b.' in caderno_text
    assert '2. SILVA, João. Antelope e razão. São Paulo: Atlas, 2019a.' in caderno_text

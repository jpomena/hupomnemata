import asyncio
from types import SimpleNamespace

import pytest
import flet as ft
from sqlalchemy import create_engine, select, text

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
from src.db import db as db_module
from src.domains import (
    Author,
    Authorship,
    BibliographicResource,
    EditorialMonograph,
    Fragment,
)
from src.repositories.work_repository import WorkRepository
from src.services.fragment_service import FragmentService
from src.services.work_service import WorkService
from src.utils.types import ViewConfig
from src.views.fragments import FragmentsComposer
from src.utils.clipboard import reference_text


@pytest.fixture
def fragment_database(tmp_path, monkeypatch):
    orig_engine = db_module.engine
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'fragments.db').as_posix()}"
    )
    monkeypatch.setattr(db_module, 'engine', engine)
    db_module.SessionLocal.configure(bind=engine)
    db_module.Base.metadata.create_all(bind=engine)
    yield engine
    db_module.Base.metadata.drop_all(bind=engine)
    engine.dispose()
    db_module.SessionLocal.configure(bind=orig_engine)


def create_work(title: str = 'Obra de teste') -> int:
    with db_module.SessionLocal() as session:
        resource = BibliographicResource(
            editorial_monograph=EditorialMonograph(title=title)
        )
        session.add(resource)
        session.commit()
        return resource.id


def test_fragment_crud_and_optional_comment_location(fragment_database):
    resource_id = create_work()
    service = FragmentService()
    quote_id = service.create({
        'fragment_type': 'quote',
        'excerpt': '  Um trecho citado. ',
        'bib_res_id': str(resource_id),
        'location_type': 'Página',
        'location_value': '42',
    })
    comment_id = service.create({
        'fragment_type': 'comment',
        'excerpt': 'Uma observação sem localização.',
        'bib_res_id': resource_id,
        'location_type': None,
        'location_value': '',
    })

    records = service.list_fragments()
    assert [record['id'] for record in records] == [comment_id, quote_id]
    assert records[0]['location_type'] is None
    assert records[1]['excerpt'] == 'Um trecho citado.'
    assert records[1]['work_title'] == 'Obra de teste'
    assert records[1]['citation_author'] == 'Obra de teste'
    assert records[1]['display_year'] == '[s.d.]'

    service.update(comment_id, {
        'fragment_type': 'comment',
        'excerpt': 'Paráfrase contextualizado.',
        'bib_res_id': resource_id,
        'location_type': 'Capítulo',
        'location_value': 'III',
    })
    service.delete(quote_id)
    records = service.list_fragments()
    assert len(records) == 1
    assert records[0]['excerpt'] == 'Paráfrase contextualizado.'
    assert records[0]['location_value'] == 'III'

    other_location_id = service.create({
        'fragment_type': 'quote',
        'excerpt': 'Referência em formato livre.',
        'bib_res_id': resource_id,
        'location_type': 'Outros',
        'location_value': 'Jo 1: 32-33',
    })
    other_fragment = next(
        record for record in service.list_fragments()
        if record['id'] == other_location_id
    )
    assert other_fragment['location_type'] == 'Outros'
    assert other_fragment['location_value'] == 'Jo 1: 32-33'
    assert FragmentsComposer._abnt_notation(other_fragment).endswith(
        ', Jo 1: 32-33)'
    )


def test_fragment_notation_uses_author_year_and_location(fragment_database):
    with db_module.SessionLocal() as session:
        author = Author(
            given_names='Maria',
            last_name='Silva',
            given_names_initials='M.',
            last_name_initial='S.',
        )
        resource = BibliographicResource(
            editorial_monograph=EditorialMonograph(
                title='Obra de teste',
                display_year='2024',
            ),
            authorships=[Authorship(author=author)],
        )
        session.add(resource)
        session.commit()
        resource_id = resource.id

    FragmentService().create({
        'fragment_type': 'quote',
        'excerpt': 'Trecho citado',
        'bib_res_id': resource_id,
        'location_type': 'Página',
        'location_value': '42',
    })
    fragment = FragmentService().list_fragments()[0]

    assert fragment['citation_author'] == 'Silva'
    assert fragment['display_year'] == '2024'
    assert FragmentsComposer._abnt_notation(fragment) == (
        '(Silva, 2024, p. 42)'
    )


def test_fragment_notation_preserves_title_spelling_without_author(
    fragment_database,
):
    with db_module.SessionLocal() as session:
        resource = BibliographicResource(
            editorial_monograph=EditorialMonograph(
                title='Bíblia King James',
                preserve_title_spelling=True,
                display_year='2024',
            )
        )
        session.add(resource)
        session.flush()
        session.add(Fragment(
            fragment_type='quote',
            excerpt='Citação',
            bib_res_id=resource.id,
            location_type='Página',
            location_value='12',
        ))
        session.commit()

    assert FragmentService().list_fragments()[0]['citation_author'] == (
        'BÍBLIA King James'
    )


def test_fragment_work_search_finds_existing_work(fragment_database):
    resource_id = create_work('Obra pesquisável')

    assert WorkService().search_works(
        'PESQUISÁVEL',
        include_partial=True,
    ) == [(resource_id, 'Obra pesquisável')]


@pytest.mark.parametrize(
    ('fragment_type', 'location_type', 'location_value', 'message'),
    [
        ('quote', None, None, 'Citações exigem'),
        ('comment', 'Seção', None, 'Informe o tipo e o valor'),
        ('quote', 'Página', '123456', 'no máximo 5 caracteres'),
        ('comment', 'Tempo inválido', '12:30', 'tipo de localização válido'),
    ],
)
def test_fragment_validation(
    fragment_database,
    fragment_type,
    location_type,
    location_value,
    message,
):
    service = FragmentService()
    with pytest.raises(ValueError, match=message):
        service.create({
            'fragment_type': fragment_type,
            'excerpt': 'Conteúdo',
            'bib_res_id': create_work(),
            'location_type': location_type,
            'location_value': location_value,
        })


def test_deleting_work_deletes_its_fragments(fragment_database):
    resource_id = create_work()
    service = FragmentService()
    service.create({
        'fragment_type': 'comment',
        'excerpt': 'Observação vinculada.',
        'bib_res_id': resource_id,
        'location_type': None,
        'location_value': None,
    })

    with db_module.SessionLocal() as session:
        resource = session.get(BibliographicResource, resource_id)
        assert resource is not None
        WorkRepository(session).remove_work(resource)

    assert service.list_fragments() == []


def test_init_db_migrates_legacy_citations(fragment_database):
    with fragment_database.begin() as connection:
        connection.execute(text('DROP TABLE fragments'))
        connection.execute(text(
            """
            CREATE TABLE citations (
                id INTEGER PRIMARY KEY,
                excerpt TEXT NOT NULL,
                bib_res_id INTEGER NOT NULL,
                start_page INTEGER,
                end_page INTEGER
            )
            """
        ))
        connection.execute(text(
            """
            INSERT INTO citations
                (id, excerpt, bib_res_id, start_page, end_page)
            VALUES (18, 'Trecho legado', 1, 24, 26)
            """
        ))

    db_module.init_db()

    with db_module.SessionLocal() as session:
        fragment = session.scalar(
            select(Fragment).where(Fragment.id == 18)
        )
        assert fragment is not None
        assert fragment.fragment_type == 'quote'
        assert fragment.excerpt == 'Trecho legado'
        assert fragment.location_type == 'Página'
        assert fragment.location_value == '24-26'
        assert fragment.created_at is not None


def _view_config():
    return ViewConfig(
        colors=COLORS_LIGHT,
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


def _texts(control):
    """Todos os valores de ``ft.Text`` dentro de um controle."""
    found = []
    if isinstance(control, ft.Text) and isinstance(control.value, str):
        found.append(control.value)
    for attr in ('content', 'controls'):
        child = getattr(control, attr, None)
        children = child if isinstance(child, list) else [child]
        for item in children:
            if isinstance(item, ft.Control):
                found.extend(_texts(item))
    return found


SAMPLE_FRAGMENTS = [
    {
        'id': 1,
        'fragment_type': 'quote',
        'excerpt': 'Trecho 1',
        'bib_res_id': 21,
        'work_title': 'Obra encontrada',
        'citation_author': 'Silva',
        'display_year': '2024',
        'location_type': 'Página',
        'location_value': '42',
    },
    {
        'id': 2,
        'fragment_type': 'comment',
        'excerpt': 'Paráfrase 2',
        'bib_res_id': 22,
        'work_title': 'Outra obra',
        'citation_author': 'Souza',
        'display_year': '2023',
        'location_type': None,
        'location_value': None,
    },
    {
        'id': 3,
        'fragment_type': 'quote',
        'excerpt': '“Já entre aspas”',
        'bib_res_id': 22,
        'work_title': 'Outra obra',
        'citation_author': 'Souza',
        'display_year': '2023',
        'location_type': 'Capítulo',
        'location_value': 'III',
    },
]


def _composer(**kwargs):
    page_updates = []
    dialogs = []
    copied_references = []
    deleted = []

    async def capture_reference(reference):
        copied_references.append(reference)

    def show_dialog(dialog):
        dialog.open = True
        dialogs.append(dialog)

    composer = FragmentsComposer(
        page=SimpleNamespace(
            show_dialog=show_dialog,
            update=lambda: page_updates.append(True),
        ),
        config=_view_config(),
        fragments=kwargs.pop('fragments', []),
        search_works=lambda _query: [(21, 'Obra encontrada')],
        on_save=kwargs.pop('on_save', lambda _fragment_id, _data: True),
        on_delete=deleted.append,
        on_copy_reference=capture_reference,
        **kwargs,
    )
    return composer, SimpleNamespace(
        updates=page_updates,
        dialogs=dialogs,
        copied=copied_references,
        deleted=deleted,
    )


def test_fragment_form_applies_location_rules():
    composer, spy = _composer()

    for field in (
        composer.work_search,
        composer.excerpt,
        composer.location_value,
    ):
        assert field.label is None
        assert field.text_style.color == COLORS_LIGHT['text']
        assert field.text_style.font_family == FONT_FAMILIES['montserrat']
        assert field.text_style.letter_spacing is None
        assert field.hint_style.color == COLORS_LIGHT['faint']
        assert field.bgcolor == COLORS_LIGHT['bg']
        assert field.border_color == COLORS_LIGHT['border_strong']
        assert field.focused_border_color == COLORS_LIGHT['gold']
        assert field.border_width == 1
    dropdown = composer.location_type
    assert dropdown.label is None
    assert dropdown.text_style.font_family == FONT_FAMILIES['montserrat']
    assert dropdown.border_color == COLORS_LIGHT['border_strong']
    assert dropdown.focused_border_color == COLORS_LIGHT['gold']
    assert all(
        option.content.font_family == FONT_FAMILIES['montserrat']
        and option.content.style.letter_spacing <= 0
        for option in dropdown.options
    )
    assert any(option.key == 'Outros' for option in dropdown.options)

    # rótulos ficam acima dos campos, como texto
    form_texts = _texts(composer.form)
    for label in ('Tipo', 'Obra do acervo', 'Conteúdo', 'Tipo de localização'):
        assert label in form_texts
    assert composer.form_title.value == 'Novo fragmento'
    assert composer.modal.content is composer.form
    foot_container = composer.form.content.controls[2]
    assert foot_container.bgcolor == COLORS_LIGHT['surface']
    assert composer.save_button.data['variant'] == 'primary'
    assert composer.cancel_button.data['variant'] == 'ghost'

    # alturas padronizadas e alinhamento horizontal
    assert (
        composer.work_search.height
        == composer.location_type.height
        == composer.location_value.height
        == 48
    )
    assert composer.location_value.counter is None
    assert composer.work_search.content_padding.top == 18
    assert composer.work_search.content_padding.bottom == 16
    assert composer.location_value.content_padding.top == 18
    assert composer.location_value.content_padding.bottom == 16
    assert composer.excerpt.content_padding.top == 10
    assert composer.excerpt.content_padding.bottom == 10
    assert (
        composer.work_search_group.horizontal_alignment
        == ft.CrossAxisAlignment.STRETCH
    )
    top_row = composer.form_body.controls[0]
    assert isinstance(top_row, ft.Row)
    assert top_row.controls[0].controls[0].value == 'Obra do acervo'
    assert top_row.controls[0].expand is True
    assert top_row.controls[0].horizontal_alignment == ft.CrossAxisAlignment.STRETCH
    assert top_row.controls[1].controls[0].value == 'Tipo'
    assert top_row.controls[1].horizontal_alignment == ft.CrossAxisAlignment.START
    content_field = composer.form_body.controls[1]
    assert content_field.controls[0].value == 'Conteúdo'
    assert content_field.horizontal_alignment == ft.CrossAxisAlignment.STRETCH
    location_row = composer.form_body.controls[2]
    assert isinstance(location_row, ft.Row)
    assert location_row.controls[0].controls[1] is composer.location_type
    assert location_row.controls[1].controls[1] is composer.location_value
    assert location_row.controls[0].expand is True
    assert location_row.controls[1].expand is True
    assert location_row.vertical_alignment == ft.CrossAxisAlignment.START

    composer._search_works(SimpleNamespace(
        control=SimpleNamespace(value='ob')
    ))
    assert spy.updates
    assert composer.work_results.visible
    assert len(composer.work_results.controls) == 1
    assert 'Obra encontrada' in _texts(composer.work_results)
    composer.work_results.controls[0].on_click(SimpleNamespace())
    assert composer.selected_work_id == 21
    assert composer.work_search.value == 'Obra encontrada'
    assert not composer.work_results.visible

    composer._on_location_type_change(SimpleNamespace(
        control=SimpleNamespace(value='Página')
    ))
    assert composer.location_value.max_length == 5
    assert composer.location_value_label.value.startswith('Página')
    assert composer.location_type.hint_text == 'Obrigatório para citações'
    assert composer.location_value.hint_text == 'Obrigatório para citações'
    assert 'A memória' in composer.excerpt.hint_text
    composer._on_location_type_change(SimpleNamespace(
        control=SimpleNamespace(value='Outros')
    ))
    assert composer.location_value_label.value == (
        'Localização (ex.: Jo 1: 32-33)'
    )
    assert composer.location_value.hint_text == 'Ex.: Jo 1: 32-33'
    assert composer.location_value.max_length == 100
    composer._on_location_type_change(SimpleNamespace(
        control=SimpleNamespace(value='Página')
    ))
    assert composer.location_value.max_length == 5
    composer.location_value.value = '123456789'
    composer._on_location_value_change(SimpleNamespace(
        control=composer.location_value
    ))
    assert composer.location_value.value == '12345'

    composer._set_fragment_type('comment')
    assert composer.fragment_type_value == 'comment'
    assert composer.location_type_label.value == 'Tipo de localização'
    assert composer.location_type.hint_text == 'Opcional'
    assert composer.location_value.hint_text == 'Opcional'
    assert 'O autor relaciona' in composer.excerpt.hint_text
    assert FragmentService._payload({
        'fragment_type': 'comment',
        'excerpt': 'Paráfrase sem localização.',
        'bib_res_id': 21,
        'location_type': None,
        'location_value': '',
    })['location_type'] is None

    composer._on_location_type_change(SimpleNamespace(
        control=SimpleNamespace(value='__none__')
    ))
    assert composer.location_type.value is None
    assert composer.location_value.value == ''


def test_fragment_form_saves_and_edits_through_callbacks():
    saved = []
    composer, spy = _composer(
        on_save=lambda fragment_id, data: saved.append((fragment_id, data)) or True,
    )
    composer.open_create()
    assert composer.modal.open
    assert composer.selected_work_id is None
    composer._select_work(21, 'Obra encontrada')
    composer.excerpt.value = 'Um trecho.'
    composer._on_location_type_change(SimpleNamespace(
        control=SimpleNamespace(value='Página')
    ))
    assert composer.location_value.max_length == 5
    composer.location_value.value = '123456789'
    composer._on_location_value_change(SimpleNamespace(
        control=composer.location_value
    ))
    assert composer.location_value.value == '12345'
    composer.location_value.value = '42'
    composer.save_button.on_click(SimpleNamespace())
    assert saved == [(None, {
        'fragment_type': 'quote',
        'excerpt': 'Um trecho.',
        'bib_res_id': 21,
        'location_type': 'Página',
        'location_value': '42',
    })]
    assert not composer.modal.open
    assert composer.excerpt.value == ''

    composer.open_edit_fragment(SAMPLE_FRAGMENTS[1])
    assert composer.form_title.value == 'Editar fragmento'
    assert composer.fragment_type_value == 'comment'
    assert composer.work_search.value == 'Outra obra'
    composer._save()
    assert saved[-1][0] == 2
    assert saved[-1][1]['fragment_type'] == 'comment'

    restricted, _ = _composer(allowed_work_ids={99})
    with pytest.raises(ValueError, match='compilação'):
        restricted.open_create_for_work(21, 'Obra encontrada')


def test_fragments_screen_groups_filters_and_rows():
    opened_works = []
    composer, spy = _composer(
        fragments=[dict(item) for item in SAMPLE_FRAGMENTS],
        compilations_by_fragment={1: ['O multiplicador punitivo']},
        on_open_work=opened_works.append,
    )
    screen = composer.compose()
    assert isinstance(screen, ft.Container)
    assert screen.bgcolor == COLORS_LIGHT['bg']
    header = screen.content.controls[0]
    header_texts = _texts(header)
    assert header_texts[:2] == [
        'Fragmentos',
        '3 citações e paráfrases de 2 obras do acervo.',
    ]
    assert 'Novo fragmento' in header_texts

    # segmentado com contagens e um grupo (card) por obra, mais recente primeiro
    segment_texts = _texts(composer.segment_host)
    assert segment_texts == ['Todos', '3', 'Citações', '2', 'Paráfrases', '1']
    groups = [
        control for control in composer.fragment_list.controls
        if isinstance(getattr(control, 'data', None), dict)
    ]
    assert [group.data['work_id'] for group in groups] == [22, 21]
    assert composer.count_text.value == '2 obras'
    first_group_texts = _texts(groups[0])
    assert 'Outra obra' in first_group_texts
    assert 'Souza · 2023' in first_group_texts
    assert '2' in first_group_texts
    # citação em serifa com aspas (sem duplicar), paráfrase em Montserrat
    assert '“Já entre aspas”' in first_group_texts
    assert 'Paráfrase 2' in first_group_texts
    assert 'cap. III' in first_group_texts
    rows = groups[0].content.controls[1:]
    assert [row.data['fragment_id'] for row in rows] == [2, 3]
    comment_text = rows[0].content.controls[1].controls[0]
    quote_text = rows[1].content.controls[1].controls[0]
    assert comment_text.font_family == FONT_FAMILIES['montserrat']
    assert comment_text.color == COLORS_LIGHT['muted']
    assert quote_text.font_family == FONT_FAMILIES['cormorant']
    second_group_texts = _texts(groups[1])
    assert '“Trecho 1”' in second_group_texts
    assert 'O multiplicador punitivo' in second_group_texts
    assert 'p. 42' in second_group_texts

    # ferramentas aparecem no hover
    row = rows[1]
    tools = row.data['tools']
    assert tools.opacity == 0
    row.update = lambda: None
    row.on_hover(SimpleNamespace(data='true'))
    assert tools.opacity == 1
    assert row.bgcolor == COLORS_LIGHT['card_hover']
    row.on_hover(SimpleNamespace(data='false'))
    assert tools.opacity == 0
    copy_button, edit_button, delete_button = tools.controls
    asyncio.run(copy_button.on_click(SimpleNamespace()))
    assert reference_text(spy.copied[0]) == (
        '“Já entre aspas”\n(Souza, 2023, cap. III)'
    )
    delete_button.on_click(SimpleNamespace())
    assert spy.deleted == [3]
    edit_button.on_click(SimpleNamespace())
    assert composer.editing_id == 3
    assert composer.modal.open

    # abrir a obra no acervo
    open_button = groups[1].content.controls[0].content.controls[-1]
    open_button.on_click(SimpleNamespace())
    assert opened_works == [21]

    # filtro por tipo
    composer.set_kind_filter('comment')
    assert [fragment['id'] for fragment in composer.visible_fragments()] == [2]
    assert composer.count_text.value == '1 de 3 em 1 obra'
    composer.set_kind_filter('quote')
    assert [fragment['id'] for fragment in composer.visible_fragments()] == [1, 3]
    composer.set_kind_filter('all')

    # filtro de texto: excerto, obra ou autor
    composer._on_search(SimpleNamespace(control=SimpleNamespace(value='SILVA')))
    assert [fragment['id'] for fragment in composer.visible_fragments()] == [1]
    composer._on_search(SimpleNamespace(control=SimpleNamespace(value='outra obra')))
    assert [fragment['id'] for fragment in composer.visible_fragments()] == [2, 3]
    composer._on_search(SimpleNamespace(control=SimpleNamespace(value='inexistente')))
    assert composer.visible_fragments() == []
    assert 'Nenhum fragmento encontrado' in _texts(composer.fragment_list)
    composer.clear_query()
    assert len(composer.visible_fragments()) == 3

    # recolher e expandir
    composer.toggle_group(22)
    collapsed_group = composer.fragment_list.controls[0]
    assert collapsed_group.data == {'work_id': 22, 'collapsed': True}
    assert len(collapsed_group.content.controls) == 1
    composer.toggle_all()
    assert composer.collapsed == {21, 22}
    assert 'Expandir tudo' in _texts(composer.collapse_host)
    composer.toggle_all()
    assert composer.collapsed == set()
    assert 'Recolher tudo' in _texts(composer.collapse_host)


def test_fragments_screen_prefills_query_and_shows_empty_state():
    composer, _ = _composer(
        fragments=[dict(item) for item in SAMPLE_FRAGMENTS],
        initial_query='trecho',
    )
    composer.compose()
    assert composer.search.value == 'trecho'
    assert [fragment['id'] for fragment in composer.visible_fragments()] == [1]

    empty, _ = _composer()
    empty.compose()
    assert 'Nenhum fragmento ainda' in _texts(empty.fragment_list)
    assert empty.count_text.value == '0 obras'

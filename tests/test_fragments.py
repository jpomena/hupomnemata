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
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'fragments.db').as_posix()}"
    )
    monkeypatch.setattr(db_module, 'engine', engine)
    db_module.SessionLocal.configure(bind=engine)
    db_module.Base.metadata.create_all(bind=engine)
    yield engine
    db_module.Base.metadata.drop_all(bind=engine)
    engine.dispose()


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
        'excerpt': 'Comentário contextualizado.',
        'bib_res_id': resource_id,
        'location_type': 'Capítulo',
        'location_value': 'III',
    })
    service.delete(quote_id)
    records = service.list_fragments()
    assert len(records) == 1
    assert records[0]['excerpt'] == 'Comentário contextualizado.'
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


def test_fragment_form_applies_location_rules():
    page_updates = []
    copied_references = []

    async def capture_reference(reference):
        copied_references.append(reference)

    config = ViewConfig(
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
    composer = FragmentsComposer(
        page=SimpleNamespace(
            show_dialog=lambda dialog: setattr(dialog, 'open', True),
            update=lambda: page_updates.append(True),
        ),
        config=config,
        fragments=[],
        search_works=lambda _query: [(21, 'Obra encontrada')],
        on_save=lambda _fragment_id, _data: True,
        on_delete=lambda _fragment_id: None,
        on_copy_reference=capture_reference,
    )

    for field in (
        composer.work_filter,
        composer.work_search,
        composer.excerpt,
        composer.location_value,
    ):
        assert field.color == COLORS_LIGHT['text']
        assert field.text_style.color == COLORS_LIGHT['text']
        assert field.hint_style.color == COLORS_LIGHT['muted']
        assert field.label_style.color == COLORS_LIGHT['muted']
        assert field.bgcolor == COLORS_LIGHT['surface']
        assert field.border_color == COLORS_LIGHT['border']
        assert field.focused_border_color == COLORS_LIGHT['gold']
    for dropdown in (composer.fragment_type, composer.location_type):
        assert dropdown.color == COLORS_LIGHT['text']
        assert dropdown.text_style.color == COLORS_LIGHT['text']
        assert dropdown.label_style.color == COLORS_LIGHT['text']
        assert dropdown.bgcolor == COLORS_LIGHT['surface']
        assert dropdown.border_color == COLORS_LIGHT['border']
        assert dropdown.focused_border_color == COLORS_LIGHT['gold']
        assert all(
            option.content.color == COLORS_LIGHT['text']
            and option.content.font_family == FONT_FAMILIES['montserrat']
            for option in dropdown.options
        )
    assert any(
        option.key == 'Outros'
        for option in composer.location_type.options
    )
    cancel_text = composer.cancel_button.content
    save_text = composer.save_button.content
    for button_text in (cancel_text, save_text):
        assert button_text.font_family == FONT_FAMILIES['montserrat']
        assert button_text.size == FONT_SIZES['montserrat_medium']
        assert button_text.weight == FONT_WEIGHTS['montserrat_normal']
    for button in (composer.cancel_button, composer.save_button):
        assert button.style.text_style.font_family == (
            FONT_FAMILIES['montserrat']
        )
        assert button.style.text_style.size == (
            FONT_SIZES['montserrat_medium']
        )
        assert button.style.text_style.weight == (
            FONT_WEIGHTS['montserrat_normal']
        )

    composer._search_works(SimpleNamespace(
        control=SimpleNamespace(value='ob')
    ))
    assert page_updates
    assert composer.work_results.visible
    assert len(composer.work_results.controls) == 1
    work_match_text = composer.work_results.controls[0].content
    assert work_match_text.font_family == FONT_FAMILIES['montserrat']
    assert work_match_text.size == FONT_SIZES['montserrat_medium']
    assert work_match_text.weight == FONT_WEIGHTS['montserrat_normal']
    assert composer.work_results.controls[0].style.text_style.font_family == (
        FONT_FAMILIES['montserrat']
    )
    composer._select_work(21, 'Obra encontrada')
    assert composer.selected_work_id == 21
    assert composer.work_search.value == 'Obra encontrada'

    composer._on_location_type_change(SimpleNamespace(
        control=SimpleNamespace(value='Página')
    ))
    assert composer.location_value.max_length == 5
    assert composer.location_type.hint_text == 'Obrigatório para citações'
    assert composer.location_value.hint_text == 'Obrigatório para citações'
    assert 'A memória' in composer.excerpt.hint_text
    composer._on_location_type_change(SimpleNamespace(
        control=SimpleNamespace(value='Outros')
    ))
    assert composer.location_value.label == (
        'Localização (ex.: Jo 1: 32-33)'
    )
    assert composer.location_value.hint_text == 'Ex.: Jo 1: 32-33'
    assert composer.location_value.max_length == 100
    composer._on_location_type_change(SimpleNamespace(
        control=SimpleNamespace(value='Página')
    ))

    composer._on_type_change(SimpleNamespace(
        control=SimpleNamespace(value='comment')
    ))
    assert composer.fragment_type.options[1].text == (
        'Comentários/Paráfrases'
    )
    assert composer.location_type.label == 'Tipo de localização'
    assert composer.location_value.label.startswith('Página')
    assert composer.location_type.hint_text == ''
    assert composer.location_value.hint_text == ''
    assert 'O autor relaciona' in composer.excerpt.hint_text
    assert FragmentService._payload({
        'fragment_type': 'comment',
        'excerpt': 'Comentário sem localização.',
        'bib_res_id': 21,
        'location_type': None,
        'location_value': '',
    })['location_type'] is None
    composer.fragments = [
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
            'excerpt': 'Comentário 2',
            'bib_res_id': 22,
            'work_title': 'Outra obra',
            'citation_author': 'Souza',
            'display_year': '2023',
            'location_type': None,
            'location_value': None,
        },
    ]
    screen = composer.compose()
    assert isinstance(screen, ft.Container)
    assert len(screen.content.controls) == 2
    header = screen.content.controls[0]
    header_controls = header.content.controls
    assert header_controls[0].controls[0].value == 'Fragmentos'
    assert header_controls[0].controls[0].size == FONT_SIZES['cormorant_big']
    assert header_controls[0].controls[0].font_family == (
        FONT_FAMILIES['cormorant']
    )
    assert header_controls[0].controls[0].color == COLORS_LIGHT['text']
    assert header.padding.top == UI['header_top_padding']
    assert header_controls[1].content.value == (
        '+ Novo fragmento'
    )
    new_fragment_text = header_controls[1].content
    assert new_fragment_text.font_family == FONT_FAMILIES['montserrat']
    assert new_fragment_text.size == FONT_SIZES['montserrat_small']
    assert new_fragment_text.weight == FONT_WEIGHTS['montserrat_semibold']
    content_area = screen.content.controls[1]
    assert content_area.padding == UI['content_padding']
    assert content_area.bgcolor == COLORS_LIGHT['bg']
    assert content_area.content.controls == [
        composer.work_filter_group,
        composer.fragment_list,
    ]
    assert composer.work_filter_group.controls == [
        composer.work_filter,
        composer.work_matches,
    ]
    assert content_area.content.alignment == ft.MainAxisAlignment.START
    assert composer.fragment_list.alignment == ft.MainAxisAlignment.START
    assert content_area.content.horizontal_alignment == (
        ft.CrossAxisAlignment.STRETCH
    )
    assert not composer.work_filter.expand
    assert composer.work_filter.filled
    assert composer.work_filter.fill_color == COLORS_LIGHT['surface']
    assert composer.work_filter.bgcolor == COLORS_LIGHT['surface']
    assert content_area.content.spacing == UI['modal_gap']
    assert len(composer.fragment_list.controls) == 2
    composer.work_filter.value = 'obra'
    composer._filter_fragments(SimpleNamespace(
        control=SimpleNamespace(value='obra')
    ))
    assert composer.work_matches.visible
    assert [
        match.content.value for match in composer.work_matches.controls
    ] == ['Obra encontrada', 'Outra obra']
    assert len(composer.fragment_list.controls) == 2
    composer.work_matches.controls[0].on_click(SimpleNamespace())
    assert composer.work_filter.value == 'Obra encontrada'
    assert not composer.work_matches.visible
    assert len(composer.fragment_list.controls) == 1
    assert composer.fragment_list.controls[0].content.content.controls[
        0
    ].controls[1].value == (
        'Obra encontrada'
    )
    composer.work_filter.value = 'ENCONTRADA'
    composer._filter_fragments()
    assert len(composer.fragment_list.controls) == 1
    assert composer.fragment_list.controls[0].content.content.controls[
        0
    ].controls[1].value == (
        'Obra encontrada'
    )
    composer.work_filter.value = 'obra inexistente'
    composer._filter_fragments()
    assert composer.fragment_list.controls[0].value == (
        'Nenhum fragmento encontrado para essa obra.'
    )
    assert composer.work_matches.visible
    assert composer.work_matches.controls[0].value == (
        'Nenhuma obra encontrada.'
    )
    composer.work_filter.value = ''
    composer._filter_fragments()
    assert len(composer.fragment_list.controls) == 2
    assert not composer.work_matches.visible
    assert composer.modal.content is not screen
    assert len(composer.modal.actions) == 2
    assert composer.modal.title is composer.form_title
    modal_column = composer.modal.content.content
    modal_controls = modal_column.controls
    assert composer.form_title not in modal_controls
    assert len([
        control
        for control in modal_controls
        if isinstance(control, ft.Text)
        and control.value == 'Novo fragmento'
    ]) == 0
    assert modal_controls.index(composer.excerpt) + 1 == (
        len(modal_controls) - 1
    )
    assert modal_column.spacing == 6
    assert composer.modal.content.width == 680
    assert composer.work_search_group.spacing == 2

    fragment_card = composer._compose_fragment_card({
        'id': 1,
        'fragment_type': 'quote',
        'excerpt': 'Um trecho citado.',
        'bib_res_id': 21,
        'work_title': 'Obra encontrada',
        'citation_author': 'Silva',
        'display_year': '2024',
        'location_type': 'Página',
        'location_value': '42',
    })
    assert callable(fragment_card.on_hover)
    assert fragment_card.bgcolor == COLORS_LIGHT['surface']
    assert fragment_card.border_radius == UI['card_radius']
    assert not fragment_card.expand
    card_content = fragment_card.content
    card_row = card_content.content
    card_text_controls = card_row.controls[0].controls
    action_controls = card_row.controls[1].controls
    title_text = card_text_controls[1]
    excerpt_text = card_text_controls[2]
    notation_text = card_text_controls[3]
    assert card_row.vertical_alignment == ft.CrossAxisAlignment.CENTER
    assert card_content.margin.left == 8
    assert card_content.padding == UI['card_padding']
    assert len(action_controls) == 3
    assert [button.icon for button in action_controls] == [
        ft.Icons.EDIT_OUTLINED,
        ft.Icons.COPY,
        ft.Icons.DELETE_OUTLINE,
    ]
    assert card_row.controls[1].spacing == 0
    assert title_text.font_family == FONT_FAMILIES['cormorant']
    assert title_text.size == FONT_SIZES['cormorant_medium']
    assert title_text.weight == FONT_WEIGHTS['cormorant_semibold']
    assert title_text.color == COLORS_LIGHT['gold']
    assert excerpt_text.font_family == FONT_FAMILIES['montserrat']
    assert excerpt_text.size == FONT_SIZES['montserrat_small']
    assert excerpt_text.weight == FONT_WEIGHTS['montserrat_normal']
    assert notation_text.font_family == FONT_FAMILIES['montserrat']
    assert notation_text.size == FONT_SIZES['montserrat_tiny']
    assert notation_text.value == '(Silva, 2024, p. 42)'
    fragment_card.update = lambda: None
    fragment_card.on_hover(SimpleNamespace(data='true'))
    assert fragment_card.bgcolor == COLORS_LIGHT['card_hover']
    assert title_text.color == COLORS_LIGHT['text']
    fragment_card.on_hover(SimpleNamespace(data=''))
    assert fragment_card.bgcolor == COLORS_LIGHT['surface']
    assert title_text.color == COLORS_LIGHT['gold']
    copy_button = action_controls[1]
    asyncio.run(copy_button.on_click(SimpleNamespace()))
    assert reference_text(copied_references[0]) == (
        'Um trecho citado.\n(Silva, 2024, p. 42)'
    )

    composer._open_create_modal(SimpleNamespace())
    assert composer.modal.open
    assert composer.selected_work_id is None

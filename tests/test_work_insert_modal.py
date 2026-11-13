"""Diálogo "Nova obra" (v2): lista de tipos, prévia ABNT, validação e modos."""

from types import SimpleNamespace

import flet as ft
import pytest

from src.configs.settings import (
    COLORS_DARK,
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
from src.services import reference_preview
from src.services.reference_preview import (
    MSG_AFTER_SAVE,
    MSG_EMPTY,
    build_reference_preview,
)
from src.utils.types import ViewConfig
from src.views import ui_kit as ui
from src.views import work_insert_modal_render
from src.views.work_insert_modal import WorkInsertModalComposer
from src.views.work_insert_specs import WORK_TYPES
from src.views.work_insert_specs.catalog import TYPE_GROUPS, grouped_types


class DummyPage:
    def __init__(self):
        self.tasks = []

    def update(self):
        pass

    def run_task(self, handler, *args, **kwargs):
        self.tasks.append(handler)


def make_config(colors=COLORS_DARK):
    return ViewConfig(
        colors=colors,
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


def make_composer(on_save=lambda data: True, colors=COLORS_DARK, **kwargs):
    composer = WorkInsertModalComposer(
        DummyPage(),
        make_config(colors),
        on_save=on_save,
        search_authors=lambda query: [],
        search_works=lambda query, work_type: [],
        **kwargs,
    )
    composer.compose()
    return composer


def spec_for(key):
    return next(spec for spec in WORK_TYPES if spec.key == key)


def type(composer, key, value):  # noqa: A001 - "digitar" no campo
    control = composer.fields[key]
    control.value = value
    composer._value_changed(key)


def visible_type_keys(composer):
    return [
        row.data
        for group in composer.type_list.controls
        if isinstance(group, ft.Column)
        for row in group.controls
        if isinstance(row.data, str)
    ]


def person(name):
    return {
        'name': name,
        'id': None,
        'corporation': False,
        'acronym': None,
        'jurisdiction_id': None,
        'jurisdiction_name': None,
    }


# ── lista de tipos ─────────────────────────────────────────


def test_every_work_type_belongs_to_exactly_one_group():
    grouped = [key for _title, keys in TYPE_GROUPS for key in keys]
    assert sorted(grouped) == sorted(spec.key for spec in WORK_TYPES)
    assert len(grouped) == len(set(grouped))
    assert [title for title, _ in grouped_types(WORK_TYPES)] == [
        'Textos', 'Periódicos', 'Eventos', 'Jurídico',
        'Mídia e objetos', 'Digital',
    ]


def test_type_list_replaces_icon_grid_and_highlights_selected_type():
    composer = make_composer()
    assert visible_type_keys(composer)[:3] == [
        'editorial_monograph', 'academic_monograph',
        'correspondence_monograph',
    ]
    assert len(visible_type_keys(composer)) == len(WORK_TYPES)
    selected_row = next(
        row
        for group in composer.type_list.controls
        for row in group.controls
        if row.data == 'editorial_monograph'
    )
    icon = selected_row.content.controls[0].content
    assert selected_row.bgcolor == COLORS_DARK['selected']
    assert icon.color == COLORS_DARK['gold']


def test_type_search_filters_without_accents_and_enter_picks_first():
    composer = make_composer()
    composer._filter_types(SimpleNamespace(control=SimpleNamespace(value='audio')))
    assert visible_type_keys(composer) == [
        'audiovisual_document', 'audio_document',
    ]

    composer._filter_types(SimpleNamespace(control=SimpleNamespace(value='JURISP')))
    assert visible_type_keys(composer) == ['caselaw']
    assert composer.type_list.controls[0].controls[0].content.value == (
        'Jurídico'
    )

    composer._choose_first_visible_type()
    assert composer.selected.key == 'caselaw'

    composer._filter_types(SimpleNamespace(control=SimpleNamespace(value='xyz')))
    assert visible_type_keys(composer) == []
    empty = composer.type_list.controls[0].content
    assert empty.value == 'Nenhum tipo encontrado.'


def test_choosing_a_type_rebuilds_intro_and_sections():
    composer = make_composer()
    composer._choose(spec_for('statute'))
    intro_title = composer.form_intro.content.controls[1].controls[0]
    assert intro_title.value == 'Legislação'
    assert 'detalhes' in composer.section_keys
    detail = next(
        control for control in composer.form_body.controls
        if getattr(control, 'data', None) == 'detalhes'
    )
    legend = detail.content.controls[0].content.controls[0]
    assert legend.value == 'Norma'


@pytest.mark.parametrize('colors', [COLORS_DARK, COLORS_LIGHT])
def test_every_type_composes_in_both_themes(colors):
    for spec in WORK_TYPES:
        work_type = spec.key
        composer = make_composer(colors=colors, initial_work_type=work_type)
        assert composer.selected.key == work_type
        assert composer.section_keys[0] == 'identificacao' or (
            work_type == 'periodical_collection'
        )
        # Todo campo obrigatório visível leva o asterisco dourado.
        for key, wrapper in composer.field_wrappers.items():
            label = wrapper.controls[0] if isinstance(wrapper, ft.Column) else None
            if isinstance(label, ft.Text) and label.spans:
                assert label.spans[0].style.color == colors['gold'], key


# ── prévia ao vivo ─────────────────────────────────────────


def test_live_preview_uses_real_monograph_formatter():
    composer = make_composer()
    assert composer.preview_text.value == MSG_EMPTY

    composer.author_references.extend([
        person('Pierre Dardot'), person('Christian Laval'),
    ])
    type(composer, 'title', 'A nova razão do mundo')
    type(composer, 'subtitle', 'ensaio sobre a sociedade neoliberal')
    type(composer, 'date_anchor', '2016')
    type(composer, 'publication_place', 'São Paulo')
    type(composer, 'publisher', 'Boitempo')

    text = ''.join(span.text for span in composer.preview_text.spans)
    assert text == (
        'DARDOT, P.; LAVAL, C. A nova razão do mundo: ensaio sobre a '
        'sociedade neoliberal. São Paulo: Boitempo, 2016.'
    )
    bold = [
        span.text.strip() for span in composer.preview_text.spans
        if span.style is not None and span.style.weight == ft.FontWeight.W_700
    ]
    assert bold == ['A nova razão do mundo']
    assert composer.preview_text.color == COLORS_DARK['text']


def test_preview_tracks_preserve_title_spelling_checkbox():
    composer = make_composer()
    type(composer, 'title', 'memórias póstumas de Brás Cubas')
    type(composer, 'date_anchor', '1881')
    assert 'brás' in composer.preview_result.text.lower()
    lowered = composer.preview_result.text
    composer.fields['preserve_title_spelling'].value = True
    composer._value_changed('preserve_title_spelling')
    assert composer.preview_result.text != lowered
    assert 'Brás Cubas' in composer.preview_result.text


def test_preview_for_partial_works_waits_for_save():
    composer = make_composer(initial_work_type='journal_article')
    type(composer, 'title', 'Um artigo')
    assert composer.preview_text.value == MSG_AFTER_SAVE


def test_preview_never_crashes_the_dialog_and_logs_once(monkeypatch):
    logged = []
    monkeypatch.setattr(
        work_insert_modal_render,
        'build_reference_preview',
        lambda data: (_ for _ in ()).throw(RuntimeError('quebrou')),
    )
    monkeypatch.setattr(
        work_insert_modal_render,
        'log_exception',
        lambda context, error: logged.append(str(error)),
    )
    composer = make_composer()
    type(composer, 'title', 'Livro')
    type(composer, 'title', 'Livro 2')
    assert composer.preview_text.value == 'Não foi possível montar a prévia.'
    assert logged == ['quebrou']


@pytest.mark.parametrize(
    ('data', 'expected'),
    [
        (
            {
                'work_type': 'statute',
                'title': 'Lei nº 8.666',
                'abstract': 'Regulamenta licitações',
                'promulgation_date': '21/06/1993',
                'publication_media': 'Diário Oficial da União',
                'date_anchor': '22/06/1993',
                'date_precision': 'Data exata',
                'authors': [{**person('Brasil'), 'corporation': True}],
            },
            'BRASIL. Lei nº 8.666, de 21 de junho de 1993. Regulamenta '
            'licitações. Diário Oficial da União, 22 jun. 1993.',
        ),
        (
            {
                'work_type': 'musical_score',
                'title': 'Sonata',
                'date_anchor': '1990',
                'physical_description': '1 partitura (12 p.)',
                'publication_place': 'Rio de Janeiro',
                'publisher': 'Irmãos Vitale',
                'authors': [person('Heitor Villa-Lobos')],
            },
            None,
        ),
    ],
)
def test_preview_service_formats_other_types(data, expected):
    result = build_reference_preview(data)
    assert result.reference is not None, result.message
    assert result.error is None
    if expected is not None:
        assert result.text == expected
    assert 'None' not in result.text


def test_preview_service_does_not_touch_the_database(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('a prévia não pode abrir sessão')

    monkeypatch.setattr('src.db.db.SessionLocal', forbidden, raising=False)
    result = build_reference_preview({
        'work_type': 'miscellaneous_digital_document',
        'title': 'Manual',
        'date_anchor': '2024',
        'date_precision': 'Data exata',
        'url': 'https://exemplo.org',
        'viewed_at': '01/02/2025',
    })
    assert result.text.startswith('MANUAL.')
    assert 'Acesso em: 1 fev. 2025' in result.text


def test_preview_waits_for_complete_dates_without_logging(monkeypatch):
    logged = []
    monkeypatch.setattr(
        'src.services.work_form_service.log_exception',
        lambda *args: logged.append(args),
    )
    result = build_reference_preview({
        'work_type': 'newspaper_article',
        'title': 'Matéria',
        'date_anchor': '01/0',
        'date_precision': 'Data exata',
    })
    assert result.reference is None
    assert result.message == reference_preview.MSG_DATE_FORMAT
    assert logged == []


# ── validação e gravação ───────────────────────────────────


def test_save_marks_required_fields_and_focuses_the_first_error():
    saved = []
    composer = make_composer(on_save=lambda data: saved.append(data) or True)
    composer._save(None)

    assert saved == []
    assert list(composer.errors) == ['title', 'date_anchor']
    title_wrapper = composer.field_wrappers['title']
    assert composer.fields['title'].border_color == COLORS_DARK['danger']
    assert title_wrapper.data['message'].visible is True
    assert title_wrapper.data['message_text'].value == (
        'Informe o título da obra.'
    )
    assert composer.page.tasks == [composer.fields['title'].focus]

    type(composer, 'title', 'Livro')
    assert 'title' not in composer.errors
    assert composer.fields['title'].border_color == COLORS_DARK['border_strong']
    assert title_wrapper.data['message'].visible is False


def test_save_requires_parent_for_partial_work():
    composer = make_composer(initial_work_type='journal_article')
    type(composer, 'title', 'Artigo')
    type(composer, 'date_anchor', '03/2024')
    type(composer, 'number', '2')
    composer._save(None)
    assert list(composer.errors) == ['__parent__']
    assert composer.parent_work_field.border_color == COLORS_DARK['danger']

    composer._select_parent_work(7, 'Revista de Estudos')
    assert '__parent__' not in composer.errors


def test_save_shows_loading_state_and_closes_on_success():
    seen = {}

    def on_save(data):
        seen['label'] = composer.save_button.data['label'].value
        seen['data'] = data
        return True

    composer = make_composer(on_save=on_save)
    type(composer, 'title', 'Livro')
    type(composer, 'date_anchor', '2020')
    composer.modal.open = True
    composer._save(None)

    assert seen['label'] == 'Salvando'
    assert seen['data']['title'] == 'Livro'
    assert seen['data']['work_type'] == 'editorial_monograph'
    assert composer.modal.open is False
    assert composer.save_button.data['label'].value == 'Salvar no acervo'
    assert composer.saving is False


def test_failed_save_keeps_dialog_open_and_restores_button():
    composer = make_composer(on_save=lambda data: False)
    type(composer, 'title', 'Livro')
    type(composer, 'date_anchor', '2020')
    composer.modal.open = True
    composer._save(None)
    assert composer.modal.open is True
    assert composer.save_button.data['label'].value == 'Salvar no acervo'
    assert composer.fields['title'].value == 'Livro'


# ── modos ──────────────────────────────────────────────────


def test_edit_mode_prefills_and_hides_type_list():
    composer = make_composer(
        initial_work_type='editorial_monograph',
        edit_mode=True,
        initial_values={
            'title': 'Dom Casmurro',
            'date_anchor': '1899',
            'date_precision': 'Data exata',
            'publication_place': 'Rio de Janeiro',
            'preserve_title_spelling': True,
        },
        initial_author_references=[person('Machado de Assis')],
    )
    dialog_box = composer.modal.content
    header, body, _footer = dialog_box.content.controls
    assert header.content.controls[0].value == 'Editar obra'
    assert len(body.controls) == 1  # sem a coluna de tipos
    assert composer.save_button.data['label'].value == 'Salvar alterações'
    assert composer.fields['title'].value == 'Dom Casmurro'
    assert composer.fields['preserve_title_spelling'].value is True
    assert composer.preview_result.text.startswith('ASSIS, M. Dom Casmurro.')


def test_create_mode_layout_matches_prototype():
    composer = make_composer()
    dialog_box = composer.modal.content
    assert isinstance(dialog_box, ft.Container)
    assert (dialog_box.width, dialog_box.height) == (ui.s(1040), ui.s(740))
    header, body, footer = dialog_box.content.controls
    assert header.height == ui.s(52)
    assert header.content.controls[0].value == 'Nova obra'
    type_column = body.controls[0]
    assert type_column.width == ui.s(248)
    assert type_column.bgcolor == COLORS_DARK['chrome']
    assert footer.bgcolor == COLORS_DARK['chrome']
    preview_label = footer.content.controls[0].controls[0]
    assert preview_label.value == 'Prévia da referência ABNT'
    cancel, save = footer.content.controls[1].controls
    assert cancel.data['label'].value == 'Cancelar'
    assert save.data['label'].value == 'Salvar no acervo'
    assert composer.modal.actions == []


def test_parent_mode_uses_requested_type_and_title():
    composer = make_composer(initial_work_type='magazine', parent_mode=True)
    header = composer.modal.content.content.controls[0]
    assert header.content.controls[0].value == 'Nova revista'
    assert composer.selected.key == 'magazine'
    assert set(composer.fields) >= {'title', 'publication_place'}


# ── autor possivelmente duplicado ──────────────────────────


def test_multiple_authors_popup_offers_existing_or_new(monkeypatch):
    from src.views.general_popups import MultipleAuthorsPopup

    monkeypatch.setattr(ft.AlertDialog, 'update', lambda self: None)
    chosen, created, cancelled = [], [], []
    authors = [
        SimpleNamespace(
            id=3, given_names='Machado de', last_name='Assis',
            given_names_initials='M.', corporation=False,
        ),
        SimpleNamespace(
            id=4, given_names='Universidade de São Paulo',
            last_name='Universidade de São Paulo',
            given_names_initials='', corporation=True,
        ),
    ]
    popup = MultipleAuthorsPopup()
    modal = popup.compose(
        authors=authors,
        on_select=chosen.append,
        on_create_new=lambda: created.append(True),
        on_cancel=lambda: cancelled.append(True),
        config=make_config(COLORS_LIGHT),
    )
    assert modal.title.value == 'Possível autor já cadastrado'
    rows = modal.content.content.controls[1].content.controls
    names = [row.content.controls[1].controls[0].value for row in rows]
    assert names == ['Machado de Assis', 'Universidade de São Paulo']

    rows[0].on_click(None)
    assert chosen == [3]
    cancel, create = modal.actions
    assert cancel.data['label'].value == 'Cancelar'
    create.on_click(None)
    assert created == [True]
    cancel.on_click(None)
    assert cancelled == [True]


def test_switching_type_keeps_shared_fields_and_drops_specific_ones():
    composer = make_composer()
    composer.author_references.append(person('Machado de Assis'))
    type(composer, 'title', 'Dom Casmurro')
    type(composer, 'publisher', 'Garnier')
    composer._choose(spec_for('academic_monograph'))
    assert composer.fields['title'].value == 'Dom Casmurro'
    assert composer.fields['publisher'].value == ''
    assert [a['name'] for a in composer.author_references] == [
        'Machado de Assis'
    ]
    # Audiovisual não tem campo genérico de autoria: os autores saem.
    composer._choose(spec_for('audiovisual_document'))
    assert composer.author_references == []
    assert composer.fields['title'].value == 'Dom Casmurro'


def test_selected_type_row_is_not_clickable():
    composer = make_composer()
    rows = {
        row.data: row
        for group in composer.type_list.controls
        for row in group.controls
        if isinstance(row.data, str)
    }
    assert rows['editorial_monograph'].on_click is None
    assert rows['statute'].on_click is not None

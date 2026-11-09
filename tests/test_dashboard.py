from types import SimpleNamespace

import flet as ft

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
from src.controllers.core_controller import CoreController
from src.utils.types import ViewConfig
from src.views.core_composer import CoreComposer


def test_incomplete_sections_show_wip_dashboard():
    config = ViewConfig(
        colors=COLORS_LIGHT,
        page_fonts=PAGE_FONTS,
        font_families=FONT_FAMILIES,
        font_sizes=FONT_SIZES,
        icon_sizes=ICON_SIZES,
        font_weights=FONT_WEIGHTS,
        ui=UI,
        texts=TEXTS,
        core_menus={
            "Limbo": "thrash",
        },
        main_view_cards=MAIN_VIEW_CARDS,
    )
    composer = CoreComposer.__new__(CoreComposer)
    composer.config = config
    composer.scale = 1
    composer.on_navigate = lambda _destination: None
    composer.content = SimpleNamespace(content=None, update=lambda: None)

    navigated_sections = []
    controller = CoreController.__new__(CoreController)
    controller.application = SimpleNamespace(
        show_view=navigated_sections.append,
    )

    for section in config.core_menus:
        if section not in {
            "Limbo",
        }:
            continue
        controller.navigate(section)
        composer.show_view(section)

        view = composer.content.content
        header = view.content.controls[0]
        heading = header.content.controls[0].controls
        assert heading[0].value == "Oops..."
        assert heading[1].value == section

        body = view.content.controls[1]
        image, message = body.content.controls
        assert image.src == "assets/images/wip.png"
        assert message.value == "Esta seção ainda está em construção."

    assert navigated_sections == list(config.core_menus)


def test_nous_section_shows_nous_view():
    from unittest.mock import MagicMock
    config = ViewConfig(
        colors=COLORS_LIGHT,
        page_fonts=PAGE_FONTS,
        font_families=FONT_FAMILIES,
        font_sizes=FONT_SIZES,
        icon_sizes=ICON_SIZES,
        font_weights=FONT_WEIGHTS,
        ui=UI,
        texts=TEXTS,
        core_menus={
            "Nous": "analytics",
        },
        main_view_cards=MAIN_VIEW_CARDS,
    )
    composer = CoreComposer.__new__(CoreComposer)
    composer.config = config
    composer.scale = 1
    composer.on_navigate = lambda _destination: None
    composer.content = SimpleNamespace(content=None, update=lambda: None)
    mock_nous_service = MagicMock()
    mock_nous_service.get_api_key.return_value = ""
    mock_nous_service.list_works_ai_status.return_value = []
    composer.nous_service = mock_nous_service

    composer.show_view("Nous")
    assert composer.content.content is not None
    assert composer.nous_composer is not None


def test_estruturas_de_saber_shows_knowledge_view():
    config = ViewConfig(
        colors=COLORS_LIGHT,
        page_fonts=PAGE_FONTS,
        font_families=FONT_FAMILIES,
        font_sizes=FONT_SIZES,
        icon_sizes=ICON_SIZES,
        font_weights=FONT_WEIGHTS,
        ui=UI,
        texts=TEXTS,
        core_menus={
            "Estruturas de Saber": "hub_outlined",
        },
        main_view_cards=MAIN_VIEW_CARDS,
    )
    composer = CoreComposer.__new__(CoreComposer)
    composer.config = config
    composer.scale = 1
    composer.on_navigate = lambda _destination: None
    composer.content = SimpleNamespace(content=None, update=lambda: None)

    composer.show_view("Estruturas de Saber")
    assert composer.content.content is not None
    assert composer.knowledge_composer is not None


def test_settings_section_shows_settings_dashboard():
    config = ViewConfig(
        colors=COLORS_LIGHT,
        page_fonts=PAGE_FONTS,
        font_families=FONT_FAMILIES,
        font_sizes=FONT_SIZES,
        icon_sizes=ICON_SIZES,
        font_weights=FONT_WEIGHTS,
        ui=UI,
        texts=TEXTS,
        core_menus={
            "Configurações": "settings",
        },
        main_view_cards=MAIN_VIEW_CARDS,
    )
    composer = CoreComposer.__new__(CoreComposer)
    composer.config = config
    composer.scale = 1.0
    composer.current_theme_mode = "light"
    composer.auto_scale = True
    composer.manual_scale = 1.0
    composer.on_navigate = lambda _destination: None
    composer.on_change_theme = lambda _t: None
    composer.on_toggle_auto_scale = lambda _a: None
    composer.on_change_scale = lambda _s: None
    composer.on_reset_settings = lambda: None
    composer.content = SimpleNamespace(content=None, update=lambda: None)

    composer.show_view("Configurações")
    view = composer.content.content
    assert view is not None

    # Check header
    header = view.content.controls[0]
    heading = header.content.controls[0].controls
    assert heading[0].value == "Configurações"
    assert heading[1].value == "Personalize a aparência, tema e proporções visuais do gabinete."

    # Check cards container and controls
    body = view.content.controls[1]
    scroll_column = body.content
    assert isinstance(scroll_column, ft.Column)
    cards_row = scroll_column.controls[0]
    assert isinstance(cards_row, ft.ResponsiveRow)
    assert len(cards_row.controls) == 3



# ── Início (Gabinete de Leitura) ───────────────────────────

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine

from src.views.dashboard import DashboardComposer, summarize_dashboard


def _config(colors=COLORS_LIGHT):
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


def _texts(control):
    found = []
    if isinstance(control, ft.Text):
        if isinstance(control.value, str) and control.value:
            found.append(control.value)
        found.extend(span.text for span in (control.spans or []) if span.text)
    for attr in ('content', 'controls'):
        child = getattr(control, attr, None)
        for item in child if isinstance(child, list) else [child]:
            if isinstance(item, ft.Control):
                found.extend(_texts(item))
    return found


def _walk(control):
    yield control
    for attr in ('content', 'controls'):
        child = getattr(control, attr, None)
        for item in child if isinstance(child, list) else [child]:
            if isinstance(item, ft.Control):
                yield from _walk(item)


BASE = datetime(2026, 11, 3, 15, 0, tzinfo=timezone.utc)

SAMPLE_DATA = {
    'works': [
        {'id': 1, 'title': 'Vigiar e punir', 'authors': 'Michel Foucault', 'type': 'Livros em geral', 'created_at': BASE},
        {'id': 2, 'title': 'A escrita de si', 'authors': 'Michel Foucault', 'type': 'Livros em geral', 'created_at': BASE + timedelta(hours=1)},
        {'id': 3, 'title': 'Lei 7.210', 'authors': '', 'type': 'Legislação', 'created_at': None},
    ],
    'fragments': [
        {'id': 10, 'kind': 'quote', 'excerpt': 'Trecho citado', 'bib_res_id': 1, 'work_title': 'Vigiar e punir', 'created_at': BASE + timedelta(days=1)},
        {'id': 11, 'kind': 'comment', 'excerpt': 'Um paráfrase', 'bib_res_id': 1, 'work_title': 'Vigiar e punir', 'created_at': BASE + timedelta(days=1, minutes=5)},
        {'id': 12, 'kind': 'quote', 'excerpt': 'Outro trecho', 'bib_res_id': 2, 'work_title': 'A escrita de si', 'created_at': None},
    ],
    'compilations': [
        {'id': 7, 'name': 'O multiplicador punitivo', 'description': 'Tese', 'work_ids': [1, 2], 'fragments': 2, 'ideas': 3, 'updated_at': BASE},
    ],
}


def test_dashboard_summary_counts_real_data():
    summary = summarize_dashboard(SAMPLE_DATA)
    assert summary.works == 3
    assert summary.fragments == 3
    assert summary.quotes == 2
    assert summary.comments == 1
    assert summary.compilations == 1
    assert summary.linked_works == 2
    assert summary.works_without_fragments == 1
    assert summary.types == [('Livros em geral', 2), ('Legislação', 1)]
    # só eventos com data, do mais recente ao mais antigo
    assert [event['title'] for event in summary.events] == [
        'Vigiar e punir', 'Vigiar e punir', 'A escrita de si', 'Vigiar e punir',
    ]
    assert [event['prefix'] for event in summary.events][:2] == ['Paráfrase em ', 'Citação em ']
    assert summary.events[1]['serif'] and not summary.events[0]['serif']

    empty = summarize_dashboard({})
    assert (empty.works, empty.fragments, empty.compilations) == (0, 0, 0)
    assert empty.events == [] and empty.types == []


@pytest.mark.parametrize('colors', [COLORS_LIGHT, COLORS_DARK])
def test_dashboard_compose_shows_kpis_tables_and_shortcuts(colors):
    navigated = []
    navigated_with = []
    new_fragments = []
    palettes = []
    composer = DashboardComposer(
        scale=1,
        config=_config(colors),
        on_navigate=navigated.append,
        get_dashboard_data=lambda: SAMPLE_DATA,
        on_navigate_with=lambda destination, **options: navigated_with.append((destination, options)),
        on_new_fragment=lambda: new_fragments.append(True),
        on_open_palette=lambda: palettes.append(True),
    )
    view = composer.compose()
    assert view.bgcolor == colors['bg']
    texts = _texts(view)
    for expected in (
        'Gabinete de Leitura', 'Novo fragmento', 'Nova obra',
        'Obras', 'Fragmentos', 'Compilações', 'Obras sem fragmentos',
        'em 2 tipos documentais', '2 citações · 1 paráfrase', '2 obras vinculadas',
        'Compilações em andamento', 'O multiplicador punitivo', 'Abrir caderno',
        'Atividade recente', 'Obra cadastrada: ', 'Acervo por tipo', 'Livros em geral',
        'Atalhos', 'Inserir nova obra', 'Registrar fragmento', 'Buscar no gabinete',
        'Importar metadados', 'Exportar referências', 'Planejado',
        'Michel Foucault, A escrita de si',
    ):
        assert expected in texts, expected
    assert any(text.startswith('“Reunir o que se pôde ouvir ou ler') for text in texts)

    kpis = {cell.data['kpi']: cell for cell in composer.kpi_cells}
    assert {label: cell.data['value'] for label, cell in kpis.items()} == {
        'Obras': 3, 'Fragmentos': 3, 'Compilações': 1, 'Obras sem fragmentos': 1,
    }
    kpis['Obras'].on_click(None)
    kpis['Fragmentos'].on_click(None)
    kpis['Compilações'].on_click(None)
    kpis['Obras sem fragmentos'].on_click(None)
    assert navigated == ['Acervo', 'Fragmentos', 'Compilações']
    assert navigated_with[-1] == ('Acervo', {'sort_key': 'frag', 'sort_desc': False})

    rows = [c for c in _walk(view) if isinstance(getattr(c, 'data', None), dict) and 'compilation_id' in c.data]
    rows[0].on_click(None)
    assert navigated[-1] == 'compilacao:7'

    composer.type_rows[1].content.controls[0].on_click(None)
    assert navigated_with[-1] == ('Acervo', {'type_filter': 'Legislação'})

    shortcuts = {row.data['shortcut']: row for row in composer.shortcut_rows}
    shortcuts['Inserir nova obra'].on_click(None)
    shortcuts['Registrar fragmento'].on_click(None)
    shortcuts['Buscar no gabinete'].on_click(None)
    assert navigated[-1] == 'work_insert'
    assert new_fragments == [True] and palettes == [True]
    assert shortcuts['Importar metadados'].data['planned']
    assert shortcuts['Importar metadados'].on_click is None


def test_dashboard_without_data_shows_empty_states():
    composer = DashboardComposer(scale=1, config=_config(), on_navigate=lambda _d: None)
    texts = _texts(composer.compose())
    assert 'Nenhuma compilação ainda.' in texts
    assert 'Nenhuma obra no acervo ainda.' in texts
    assert 'Obras e fragmentos cadastrados aparecem aqui, por data.' in texts
    assert [cell.data['value'] for cell in composer.kpi_cells] == [0, 0, 0, 0]


def test_core_composer_dashboard_uses_controller_data():
    composer = CoreComposer.__new__(CoreComposer)
    composer.config = _config()
    composer.scale = 1
    composer.on_navigate = lambda _destination: None
    composer.get_dashboard_data = lambda: SAMPLE_DATA
    composer.content = SimpleNamespace(content=None, update=lambda: None)
    composer.show_view('dashboard')
    assert 'O multiplicador punitivo' in _texts(composer.content.content)


@pytest.fixture
def dashboard_database(tmp_path, monkeypatch):
    from src.db import db as db_module

    engine = create_engine(f"sqlite:///{(tmp_path / 'dashboard.db').as_posix()}")
    monkeypatch.setattr(db_module, 'engine', engine)
    db_module.SessionLocal.configure(bind=engine)
    db_module.Base.metadata.create_all(bind=engine)
    yield db_module
    db_module.Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_controller_dashboard_data_reads_services(dashboard_database):
    from src.domains import BibliographicResource, EditorialMonograph
    from src.services import CompilationService, FragmentService, WorkService
    from src.utils.normalizers import CoreNormalizer

    with dashboard_database.SessionLocal() as session:
        resource = BibliographicResource(editorial_monograph=EditorialMonograph(title='Obra de teste'))
        other = BibliographicResource(editorial_monograph=EditorialMonograph(title='Obra sem fichamento'))
        session.add_all([resource, other])
        session.commit()
        resource_id = resource.id

    fragments = FragmentService()
    fragment_id = fragments.create({
        'fragment_type': 'quote', 'excerpt': 'Trecho', 'bib_res_id': resource_id,
        'location_type': 'Página', 'location_value': '3',
    })
    compilations = CompilationService()
    compilation_id = compilations.create({'name': 'Projeto', 'description': None})
    compilations.add_work(compilation_id, resource_id)
    compilations.add_fragment(compilation_id, fragment_id)

    controller = CoreController.__new__(CoreController)
    controller.service = WorkService(CoreNormalizer())
    controller.fragment_service = fragments
    controller.compilation_service = compilations
    data = controller.dashboard_data()

    assert {work['title'] for work in data['works']} == {'Obra de teste', 'Obra sem fichamento'}
    assert all(work['type'] == 'Livros em geral' and work['created_at'] for work in data['works'])
    assert data['fragments'][0]['kind'] == 'quote'
    assert data['fragments'][0]['created_at'] is not None
    assert data['compilations'] == [{
        'id': compilation_id, 'name': 'Projeto', 'description': None,
        'work_ids': [resource_id], 'fragments': 1, 'ideas': 0,
        'updated_at': data['compilations'][0]['updated_at'],
    }]
    assert data['compilations'][0]['updated_at'] is not None
    summary = summarize_dashboard(data)
    assert (summary.works, summary.fragments, summary.works_without_fragments) == (2, 1, 1)

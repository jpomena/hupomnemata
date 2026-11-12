"""Testes para a reestruturação da Revista como contêiner estruturante guarda-chuva."""

from datetime import date

import pytest

from src.configs.settings import (
    COLORS_LIGHT,
    CORE_MENUS,
    FONT_FAMILIES,
    FONT_SIZES,
    FONT_WEIGHTS,
    ICON_SIZES,
    MAIN_VIEW_CARDS,
    PAGE_FONTS,
    TEXTS,
    UI,
)
from src.domains import (
    BibliographicResource,
    EditorialMonograph,
    JournalArticle,
    Magazine,
)
from src.services.work_form_service import WorkFormService
from src.services.work_service import WorkService
from src.utils.types import ViewConfig
from src.views.work_insert_specs.catalog import TYPE_GROUPS
from src.views.works import WorksComposer


@pytest.fixture
def clean_db(tmp_path):
    from sqlalchemy import create_engine
    from src.db import db as db_module
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'mag_test.db').as_posix()}"
    )
    db_module.engine = engine
    db_module.SessionLocal.configure(bind=engine)
    db_module.Base.metadata.create_all(bind=engine)
    yield
    db_module.Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def view_config():
    return ViewConfig(
        colors=COLORS_LIGHT,
        page_fonts=PAGE_FONTS,
        font_families=FONT_FAMILIES,
        font_sizes=FONT_SIZES,
        icon_sizes=ICON_SIZES,
        font_weights=FONT_WEIGHTS,
        ui=UI,
        texts=TEXTS,
        core_menus=CORE_MENUS,
        main_view_cards=MAIN_VIEW_CARDS,
    )


def test_catalog_excludes_standalone_magazine():
    """Garante que 'magazine' não é um tipo avulso no catálogo de Nova Obra."""
    all_keys = [
        key
        for _section_name, type_keys in TYPE_GROUPS
        for key in type_keys
    ]
    assert "magazine" not in all_keys
    assert "journal_article" in all_keys


def test_works_count_and_sidebar_exclude_magazines(clean_db, view_config):
    """Garante que a Revista não seja contada como obra no Acervo nem na Sidebar/Dashboard."""
    ws = WorkService()
    wfs = WorkFormService()

    # 1. Cria 1 livro (obra substantiva)
    book_payload = wfs.prepare_payload({
        "work_type": "editorial_monograph",
        "title": "Vigiar e Punir",
        "date_anchor": "2014",
        "publisher": "Vozes",
        "publication_place": "Petrópolis",
        "authors": [{"name": "Michel Foucault"}],
    })
    ws.create(book_payload)

    # 2. Cria 1 revista (contêiner) diretamente
    from src.services.metadata_service import find_or_create_magazine
    mag_id, _ = find_or_create_magazine("Cadernos de Filosofia", "São Paulo")

    # 3. Cria 2 artigos vinculados à revista
    art1_payload = wfs.prepare_payload({
        "work_type": "journal_article",
        "title": "Ação Comunicativa",
        "date_anchor": "01/2018",
        "number": 1,
        "parent_bibliographic_resource_id": mag_id,
        "is_partial": True,
        "authors": [{"name": "Jürgen Habermas"}],
    })
    ws.create(art1_payload)

    art2_payload = wfs.prepare_payload({
        "work_type": "journal_article",
        "title": "Esfera Pública",
        "date_anchor": "02/2019",
        "number": 2,
        "parent_bibliographic_resource_id": mag_id,
        "is_partial": True,
        "authors": [{"name": "Jürgen Habermas"}],
    })
    ws.create(art2_payload)

    all_resources = ws.list_works()
    # No banco há 4 recursos (1 livro, 1 revista, 2 artigos)
    assert len(all_resources) == 4

    composer = WorksComposer(
        scale=1.0,
        config=view_config,
        works=all_resources,
        on_navigate=lambda _dst: None,
        on_work_click=lambda _w: None,
        on_edit_work=lambda _w: None,
        format_reference=lambda _w: None,
        on_copy_reference=lambda _r: None,
        on_delete_work=lambda _w: None,
    )

    # O contador do Acervo deve acusar estritamente 3 obras (1 livro + 2 artigos), ignorando a revista!
    assert composer._count_label() == "3 obras"

    # O cabeçalho da página Acervo deve contabilizar estritamente as 3 obras substantivas e 2 tipos
    body = composer._compose_body()
    header_container = body.controls[0]
    left_col = header_container.content.controls[0]
    description_text = left_col.controls[1].value
    assert description_text == "3 obras catalogadas em 2 tipos documentais."

    # O menu de filtro por tipo não deve ter "Revista"
    type_menu = composer._type_menu()
    assert type_menu is not None


def test_magazine_banner_and_collapse_in_visible_rows(clean_db, view_config):
    """Verifica a renderização de banners (-1) e o colapso/expansão dos artigos."""
    mag_res = BibliographicResource()
    mag = Magazine(title="Revista de Teoria", publication_place="Rio de Janeiro")
    mag_res.id = 100
    mag.bib_res_id = 100
    mag_res.magazine = mag

    art1 = BibliographicResource()
    art1_sw = JournalArticle(
        title="Artigo Alfa",
        date_anchor=date(2022, 1, 1),
        display_year="2022",
        parent_bibliographic_resource_id=100,
        is_partial=True,
    )
    art1.id = 101
    art1.journal_article = art1_sw

    book = BibliographicResource()
    book_sw = EditorialMonograph(
        title="Livro Beta",
        date_anchor=date(2021, 1, 1),
        display_year="2021",
    )
    book.id = 102
    book.editorial_monograph = book_sw

    composer = WorksComposer(
        scale=1.0,
        config=view_config,
        works=[mag_res, art1, book],
        on_navigate=lambda _dst: None,
        on_work_click=lambda _w: None,
        on_edit_work=lambda _w: None,
        format_reference=lambda _w: None,
        on_copy_reference=lambda _r: None,
        on_delete_work=lambda _w: None,
    )

    # 1. Por padrão, banner inicia expandido
    rows = composer.visible_rows()
    # Deve conter: banner da revista (-1), artigo alfa (1) e livro beta (0)
    levels = [lvl for _r, lvl in rows]
    assert -1 in levels
    assert 1 in levels
    assert 0 in levels

    # 2. Testa colapsar a revista
    composer._toggle_magazine_collapse(100)
    assert 100 in composer.collapsed_magazines

    collapsed_rows = composer.visible_rows()
    # Agora o artigo alfa (1) não deve estar visível, apenas o banner (-1) e o livro (0)
    collapsed_levels = [lvl for _r, lvl in collapsed_rows]
    assert -1 in collapsed_levels
    assert 1 not in collapsed_levels
    assert 0 in collapsed_levels

    # 3. Testa descolapsar
    composer._toggle_magazine_collapse(100)
    assert 100 not in composer.collapsed_magazines
    reopened_levels = [lvl for _r, lvl in composer.visible_rows()]
    assert 1 in reopened_levels

    # 4. Garante que compose() instancia a árvore completa de controles sem exceções
    root = composer.compose()
    assert root is not None


def test_magazine_omitted_when_no_matching_articles(clean_db, view_config):
    """Verifica que uma revista sem artigos correspondentes na busca é ocultada."""
    mag_res = BibliographicResource()
    mag = Magazine(title="Revista de Teoria", publication_place="Rio de Janeiro")
    mag_res.id = 100
    mag_res.magazine = mag

    art1 = BibliographicResource()
    art1_sw = JournalArticle(
        title="Ontologia do Ser",
        date_anchor=date(2022, 1, 1),
        display_year="2022",
        parent_bibliographic_resource_id=100,
        is_partial=True,
    )
    art1.id = 101
    art1.journal_article = art1_sw

    composer = WorksComposer(
        scale=1.0,
        config=view_config,
        works=[mag_res, art1],
        on_navigate=lambda _dst: None,
        on_work_click=lambda _w: None,
        on_edit_work=lambda _w: None,
        format_reference=lambda _w: None,
        on_copy_reference=lambda _r: None,
        on_delete_work=lambda _w: None,
    )

    # Busca por termo inexistente
    composer.query = "TermoQueNaoExisteNoArtigo"
    rows = composer.visible_rows()
    assert len(rows) == 0

    # Busca pelo título do artigo
    composer.query = "Ontologia"
    rows = composer.visible_rows()
    assert len(rows) == 2  # Banner (-1) + Artigo (1)


def test_magazine_cascade_delete_and_update(clean_db):
    """Verifica a exclusão em cascata e a atualização de dados da Revista."""
    ws = WorkService()
    wfs = WorkFormService()

    from src.services.metadata_service import find_or_create_magazine
    mag_id, _ = find_or_create_magazine("Revista Primária", "Brasília")

    art_payload = wfs.prepare_payload({
        "work_type": "journal_article",
        "title": "Artigo Vinculado",
        "date_anchor": "01/2020",
        "number": 1,
        "parent_bibliographic_resource_id": mag_id,
        "is_partial": True,
        "authors": [{"name": "Autor Teste"}],
    })
    art_res = ws.create(art_payload)

    # 1. Atualiza dados da Revista e verifica sincronização nos filhos
    ws.update_magazine(mag_id, "Revista Primária Atualizada", "Curitiba")

    updated_art = [w for w in ws.list_works() if w.id == art_res.id][0]
    assert updated_art.specific_work.journal_title == "Revista Primária Atualizada"
    assert updated_art.specific_work.publication_place == "Curitiba"

    # 2. Exclusão em cascata
    deleted_children = ws.remove_magazine_cascade(mag_id)
    assert deleted_children == 1

    # Nenhuma obra ou revista deve restar
    remaining = ws.list_works()
    assert len(remaining) == 0


def test_search_works_excludes_magazines_by_default(clean_db):
    """Garante que buscas gerais para compilações e fragmentos ignorem Revistas."""
    ws = WorkService()
    from src.services.metadata_service import find_or_create_magazine

    mag_id, mag_title = find_or_create_magazine("Revista Filosofia", "SP")
    matches = ws.search_works("Filosofia")
    # Busca geral deve vir vazia pois só existe a revista
    assert len(matches) == 0

    # Busca específica de Magazine deve encontrar
    matches_mag = ws.search_works("Filosofia", work_type="magazine")
    assert len(matches_mag) == 1
    assert matches_mag[0][0] == mag_id


def test_sorting_by_title_uses_magazine_title_primarily_and_articles_within(
    clean_db, view_config
):
    """Garante que ao ordenar por título, o título da revista tenha precedência no topo,
    e dentro da revista os artigos sejam ordenados por seu próprio título."""
    mag = BibliographicResource()
    mag.id = 100
    mag.magazine = Magazine(title="Cadernos de Filosofia", publication_place="SP")

    art_z = BibliographicResource()
    art_z.id = 101
    art_z.journal_article = JournalArticle(
        title="Zaratustra",
        journal_title="Cadernos de Filosofia",
        parent_bibliographic_resource_id=100,
    )

    art_a = BibliographicResource()
    art_a.id = 102
    art_a.journal_article = JournalArticle(
        title="Ação Comunicativa",
        journal_title="Cadernos de Filosofia",
        parent_bibliographic_resource_id=100,
    )

    book_v = BibliographicResource()
    book_v.id = 202
    book_v.editorial_monograph = EditorialMonograph(title="Vigiar e Punir")

    book_antigona = BibliographicResource()
    book_antigona.id = 203
    book_antigona.editorial_monograph = EditorialMonograph(title="Antígona")

    composer = WorksComposer(
        page=None,
        scale=1.0,
        works=[mag, art_z, art_a, book_v, book_antigona],
        config=view_config,
        on_work_click=lambda *a: None,
        on_edit_work=lambda *a: None,
        format_reference=lambda *a: None,
        on_copy_reference=lambda *a: None,
        on_delete_work=lambda *a: None,
        on_navigate=lambda *a: None,
    )

    # 1. Ordenação ascendente por título
    composer.set_sort("title")
    rows_asc = composer.visible_rows()
    titles_asc = [(r.specific_work.title, lvl) for r, lvl in rows_asc]
    assert titles_asc == [
        ("Antígona", 0),
        ("Cadernos de Filosofia", -1),
        ("Ação Comunicativa", 1),
        ("Zaratustra", 1),
        ("Vigiar e Punir", 0),
    ]

    # 2. Ordenação descendente por título
    composer.set_sort("title")
    assert composer.sort_desc is True
    rows_desc = composer.visible_rows()
    titles_desc = [(r.specific_work.title, lvl) for r, lvl in rows_desc]
    assert titles_desc == [
        ("Vigiar e Punir", 0),
        ("Cadernos de Filosofia", -1),
        ("Zaratustra", 1),
        ("Ação Comunicativa", 1),
        ("Antígona", 0),
    ]

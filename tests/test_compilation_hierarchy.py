"""Tests for hierarchical sections (Capítulos & Argumentos) and multi-allocation of fragments."""

import pytest
from src.db.sqlite_runtime import create_sqlite_engine

from src.db import db as db_module
from src.domains import (
    BibliographicResource,
    EditorialMonograph,
)
from src.services.compilation_service import CompilationService
from src.services.fragment_service import FragmentService


@pytest.fixture
def compilation_database(tmp_path, monkeypatch):
    engine = create_sqlite_engine(
        f"sqlite:///{(tmp_path / 'compilations_hierarchy.db').as_posix()}"
    )
    monkeypatch.setattr(db_module, 'engine', engine)
    db_module.SessionLocal.configure(bind=engine)
    db_module.Base.metadata.create_all(bind=engine)
    yield engine
    db_module.Base.metadata.drop_all(bind=engine)
    engine.dispose()


def create_sample_work_and_fragment(title: str = 'Obra de Teste', text: str = 'Trecho do fragmento') -> tuple[int, int]:
    with db_module.SessionLocal() as session:
        resource = BibliographicResource(
            editorial_monograph=EditorialMonograph(title=title)
        )
        session.add(resource)
        session.commit()
        work_id = resource.id

    frag_service = FragmentService()
    fragment_id = frag_service.create({
        'fragment_type': 'quote',
        'excerpt': text,
        'bib_res_id': work_id,
        'location_type': 'Página',
        'location_value': '42',
    })
    return work_id, fragment_id


def test_create_hierarchical_sections(compilation_database):
    """Test 2-level section creation: chapters and arguments, with hierarchy validations."""
    service = CompilationService()
    comp_id = service.create({'name': 'Tese Hierárquica', 'description': 'Teste de capítulos'})

    # 1. Create root chapter
    chap_id = service.create_section(comp_id, 'Capítulo 1: Fundamentação', parent_id=None)
    assert chap_id > 0

    # 2. Create child argument
    arg_id = service.create_section(comp_id, '1.1 Primórdios', parent_id=chap_id)
    assert arg_id > 0

    comp = service.list_compilations()[0]
    sec_map = {s['id']: s for s in comp['sections']}
    assert sec_map[chap_id].get('parent_id') is None
    assert sec_map[arg_id].get('parent_id') == chap_id

    # 3. Validation: creating sub-argument (>2 levels) must fail
    with pytest.raises(ValueError, match='além de capítulos'):
        service.create_section(comp_id, '1.1.1 Sub-nível proibido', parent_id=arg_id)

    # 4. Validation: parent from another compilation must fail
    other_comp_id = service.create({'name': 'Outra Compilação', 'description': None})
    with pytest.raises(ValueError, match='compilação'):
        service.create_section(other_comp_id, 'Tentativa Inválida', parent_id=chap_id)

    # 5. Validation: nonexistent parent must fail
    with pytest.raises(ValueError, match='não pertence a esta compilação'):
        service.create_section(comp_id, 'Sem Pai', parent_id=9999)


def test_transfer_section(compilation_database):
    """Test moving child arguments between chapters and promoting them."""
    service = CompilationService()
    comp_id = service.create({'name': 'Tese Transferência', 'description': None})

    chap1 = service.create_section(comp_id, 'Capítulo 1', parent_id=None)
    chap2 = service.create_section(comp_id, 'Capítulo 2', parent_id=None)
    arg = service.create_section(comp_id, 'Argumento Móvel', parent_id=chap1)

    # Transfer argument to Chapter 2
    service.transfer_section(comp_id, arg, chap2)
    comp = service.list_compilations()[0]
    sec_map = {s['id']: s for s in comp['sections']}
    assert sec_map[arg].get('parent_id') == chap2

    # Promote argument to root chapter
    service.transfer_section(comp_id, arg, None)
    comp = service.list_compilations()[0]
    sec_map = {s['id']: s for s in comp['sections']}
    assert sec_map[arg].get('parent_id') is None

    # Demoting a chapter with children to be a child of another chapter must fail
    child_of_chap1 = service.create_section(comp_id, 'Filho de C1', parent_id=chap1)
    assert child_of_chap1 > 0
    with pytest.raises(ValueError, match='com argumentos não pode'):
        service.transfer_section(comp_id, chap1, chap2)

    # Demoting to self must fail
    with pytest.raises(ValueError, match='não pode ser subordinada a si mesma'):
        service.transfer_section(comp_id, chap1, chap1)


def test_multi_allocation_of_fragment(compilation_database):
    """Test linking a single fragment to multiple sections with independent notes and positions."""
    service = CompilationService()
    comp_id = service.create({'name': 'Compilação Multi-alocação', 'description': None})
    work_id, frag_id = create_sample_work_and_fragment('Obra Central', 'Fragmento compartilhado')

    service.add_work(comp_id, work_id)
    service.add_fragment(comp_id, frag_id)
    chap_id = service.create_section(comp_id, 'Capítulo 1', parent_id=None)
    arg_id = service.create_section(comp_id, 'Argumento 1.1', parent_id=chap_id)

    # 1. Allocate to chapter
    service.assign_fragment_to_section(comp_id, frag_id, chap_id)
    service.update_fragment_note(comp_id, frag_id, 'Nota no capítulo', section_id=chap_id)

    # 2. Multi-allocate to argument
    service.link_fragment_to_section(comp_id, frag_id, arg_id, work_note='Nota no argumento')

    comp = service.list_compilations()[0]
    frag_allocations = [
        f for f in comp['works'][0]['fragments']
        if f['id'] == frag_id and f['is_member']
    ]
    assert len(frag_allocations) == 2

    by_sec = {f['section_id']: f for f in frag_allocations}
    assert by_sec[chap_id]['work_note'] == 'Nota no capítulo'
    assert by_sec[arg_id]['work_note'] == 'Nota no argumento'

    # 3. Update note in argument only
    service.update_fragment_note(comp_id, frag_id, 'Nota no argumento atualizada', section_id=arg_id)
    comp = service.list_compilations()[0]
    by_sec = {
        f['section_id']: f
        for f in comp['works'][0]['fragments']
        if f['id'] == frag_id and f['is_member']
    }
    assert by_sec[chap_id]['work_note'] == 'Nota no capítulo'
    assert by_sec[arg_id]['work_note'] == 'Nota no argumento atualizada'

    # 4. Remove fragment from argument only
    service.remove_fragment(comp_id, frag_id, section_id=arg_id)
    comp = service.list_compilations()[0]
    remaining = [
        f for f in comp['works'][0]['fragments']
        if f['id'] == frag_id and f['is_member']
    ]
    assert len(remaining) == 1
    assert remaining[0]['section_id'] == chap_id

    # 5. Remove fragment globally from compilation
    service.remove_fragment(comp_id, frag_id, section_id=None)
    comp = service.list_compilations()[0]
    active = [
        f for f in comp['works'][0]['fragments']
        if f['id'] == frag_id and f['is_member']
    ]
    assert len(active) == 0


def test_safe_deletion_of_chapter_preserves_fragments(compilation_database):
    """Deleting a chapter must safely reallocate all its fragments and child fragments to unassigned."""
    service = CompilationService()
    comp_id = service.create({'name': 'Tese Remoção Segura', 'description': None})
    work1_id, frag1 = create_sample_work_and_fragment('Obra A', 'Fragmento do capítulo')
    work2_id, frag2 = create_sample_work_and_fragment('Obra B', 'Fragmento do argumento')

    service.add_work(comp_id, work1_id)
    service.add_work(comp_id, work2_id)
    service.add_fragment(comp_id, frag1)
    service.add_fragment(comp_id, frag2)
    chap_id = service.create_section(comp_id, 'Capítulo a Deletar', parent_id=None)
    arg_id = service.create_section(comp_id, 'Argumento Subordinado', parent_id=chap_id)

    service.assign_fragment_to_section(comp_id, frag1, chap_id)
    service.assign_fragment_to_section(comp_id, frag2, arg_id)

    # Delete chapter
    service.delete_section(comp_id, chap_id)

    comp = service.list_compilations()[0]
    # Sections should be empty
    assert len(comp['sections']) == 0

    # Both fragments must be preserved and in section_id = None ("A organizar")
    frags = {}
    for w in comp['works']:
        for f in w['fragments']:
            if f['is_member']:
                frags[f['id']] = f['section_id']
    assert frags[frag1] is None
    assert frags[frag2] is None


def test_caderno_hierarchy_ui_rendering_and_auto_uncollapse(view_config):
    """Test nested card rendering, visual rails, and auto-uncollapse on outline click."""
    from types import SimpleNamespace
    import flet as ft
    from src.views.compilation_hub.hub_composer import CompilationHubComposer

    dummy_page = SimpleNamespace(
        update=lambda: None,
        run_task=lambda fn: None,
        show_dialog=lambda _: None,
        pop_dialog=lambda: None,
    )

    compilation = {
        'id': 1,
        'name': 'Tese Hierárquica',
        'description': None,
        'sections': [
            {
                'id': 100,
                'title': 'Fundamentação',
                'central_idea': 'Ideia base.',
                'parent_id': None,
                'position': 0,
            },
            {
                'id': 101,
                'title': 'Argumento Teórico',
                'central_idea': 'Detalhe analítico.',
                'parent_id': 100,
                'position': 0,
            },
        ],
        'works': [],
    }

    hub = CompilationHubComposer(
        page=dummy_page,
        config=view_config,
        compilation=compilation,
        refresh_compilations=lambda: [compilation],
        search_works=lambda _q: [],
        on_update=lambda *_: True,
        on_add_work=lambda *_: True,
        on_remove_work=lambda *_: True,
        on_reorder_works=lambda *_: True,
        on_fragment_membership=lambda *_: True,
        on_fragment_note=lambda *_: True,
        on_create_section=lambda *_: None,
        on_update_section=lambda *_: True,
        on_delete_section=lambda *_: True,
        on_reorder_sections=lambda *_: True,
        on_assign_fragment_to_section=lambda *_: True,
        on_reorder_section_fragments=lambda *_: True,
        on_copy_caderno=lambda *_: None,
        on_create_work=lambda *_: None,
        on_edit_work=lambda *_: None,
        on_create_fragment=lambda *_: None,
        on_edit_fragment=lambda *_: None,
    )

    # 1. Test Master Card and Child Argument Card rendering
    # Todas as seções iniciam recolhidas por padrão
    assert 100 in hub._collapsed_set()
    assert 101 in hub._collapsed_set()

    chap_ctrl = hub._compose_idea(compilation['sections'][0], 0, 1)
    assert isinstance(chap_ctrl, ft.Container)
    assert chap_ctrl.bgcolor == view_config.colors['surface']
    assert chap_ctrl.border is not None

    # Desrecolhe o argumento para inspecionar os controles internos expandidos
    hub._collapsed_set().discard(101)
    child_ctrl = hub._compose_child_section(compilation['sections'][1], 0, 0, 1, 100)
    assert isinstance(child_ctrl, ft.Container)
    # Check connector rail
    assert child_ctrl.border is not None
    assert child_ctrl.border.left.color == view_config.colors['border_strong']
    assert child_ctrl.border.left.width > 0

    # Check serif title text in child
    title_row = child_ctrl.content.controls[0]
    title_text = title_row.controls[0].content
    assert title_text.value == "1.1 Argumento Teórico"
    assert title_text.font_family == view_config.font_families["cormorant"]

    # Check serif central idea in child
    idea_row = child_ctrl.content.controls[1].content
    idea_text = idea_row.controls[1]
    assert idea_text.value == "Detalhe analítico."
    assert idea_text.font_family == view_config.font_families["cormorant"]
    assert idea_text.style.height == 1.35

    # Check hover support
    assert child_ctrl.on_hover is not None
    assert chap_ctrl.on_hover is not None

    # 2. Test auto-uncollapse when clicking child in outline
    # Collapse parent chapter 100
    hub._collapsed_set().add(100)
    assert 100 in hub._collapsed_set()

    # Trigger outline click on child argument 101
    hub._focus_idea(101)

    # Parent chapter 100 MUST be automatically uncollapsed
    assert 100 not in hub._collapsed_set()
    assert hub.active_section_id == 101


def test_outline_counter_is_additive_across_arguments(view_config):
    """O contador do capítulo soma os fragmentos próprios e os dos argumentos."""
    from types import SimpleNamespace
    from src.views.compilation_hub.hub_composer import CompilationHubComposer

    dummy_page = SimpleNamespace(
        update=lambda: None,
        run_task=lambda fn: None,
        show_dialog=lambda _: None,
        pop_dialog=lambda: None,
    )
    compilation = {
        'id': 1,
        'name': 'Compilação aditiva',
        'sections': [
            {'id': 10, 'title': 'Capítulo', 'central_idea': None, 'parent_id': None, 'position': 0},
            {'id': 11, 'title': 'Argumento', 'central_idea': None, 'parent_id': 10, 'position': 0},
        ],
        'works': [{
            'id': 1,
            'title': 'Obra',
            'position': 0,
            'fragments': [
                {'id': 100, 'is_member': True, 'section_id': 10, 'project_position': 0},
                {'id': 101, 'is_member': True, 'section_id': 11, 'project_position': 0},
            ],
        }],
    }
    hub = CompilationHubComposer(
        page=dummy_page,
        config=view_config,
        compilation=compilation,
        refresh_compilations=lambda: [compilation],
        search_works=lambda _q: [],
        on_update=lambda *_: True,
        on_add_work=lambda *_: True,
        on_remove_work=lambda *_: True,
        on_reorder_works=lambda *_: True,
        on_fragment_membership=lambda *_: True,
        on_fragment_note=lambda *_: True,
        on_create_section=lambda *_: None,
        on_update_section=lambda *_: True,
        on_delete_section=lambda *_: True,
        on_reorder_sections=lambda *_: True,
        on_assign_fragment_to_section=lambda *_: True,
        on_reorder_section_fragments=lambda *_: True,
        on_copy_caderno=lambda *_: None,
        on_create_work=lambda *_: None,
        on_edit_work=lambda *_: None,
        on_create_fragment=lambda *_: None,
        on_edit_fragment=lambda *_: None,
    )

    assert hub._section_total_fragments(10) == 2
    assert hub._section_total_fragments(11) == 1
    hub._compose_outline()
    assert hub.outline_items[0].content.controls[-1].value == '2'


def test_outline_chapters_start_collapsed_and_toggle(view_config):
    """Valida recolhimento pelos botões reais e indentação efetiva dos argumentos."""
    from types import SimpleNamespace
    import flet as ft
    from src.views.compilation_hub.hub_composer import CompilationHubComposer

    dummy_page = SimpleNamespace(
        update=lambda: None,
        run_task=lambda fn: None,
        show_dialog=lambda _: None,
        pop_dialog=lambda: None,
    )

    compilation = {
        'id': 1,
        'name': 'Compilação de Teste',
        'sections': [
            {
                'id': 10,
                'title': 'Capítulo 1',
                'central_idea': 'Ideia 1.',
                'parent_id': None,
                'position': 0,
            },
            {
                'id': 11,
                'title': 'Argumento 1.1',
                'central_idea': 'Sub-ideia 1.',
                'parent_id': 10,
                'position': 0,
            },
            {
                'id': 20,
                'title': 'Capítulo 2',
                'central_idea': 'Ideia 2.',
                'parent_id': None,
                'position': 1,
            },
        ],
        'works': [],
    }

    hub = CompilationHubComposer(
        page=dummy_page,
        config=view_config,
        compilation=compilation,
        refresh_compilations=lambda: [compilation],
        search_works=lambda _q: [],
        on_update=lambda *_: True,
        on_add_work=lambda *_: True,
        on_remove_work=lambda *_: True,
        on_reorder_works=lambda *_: True,
        on_fragment_membership=lambda *_: True,
        on_fragment_note=lambda *_: True,
        on_create_section=lambda *_: None,
        on_update_section=lambda *_: True,
        on_delete_section=lambda *_: True,
        on_reorder_sections=lambda *_: True,
        on_assign_fragment_to_section=lambda *_: True,
        on_reorder_section_fragments=lambda *_: True,
        on_copy_caderno=lambda *_: None,
        on_create_work=lambda *_: None,
        on_edit_work=lambda *_: None,
        on_create_fragment=lambda *_: None,
        on_edit_fragment=lambda *_: None,
    )

    # 1. Por padrão, todos os capítulos iniciam recolhidos no _collapsed_set()
    assert 10 in hub._collapsed_set()
    assert 20 in hub._collapsed_set()

    # Monta a árvore no host real e aciona os botões, não apenas os métodos.
    host = ft.Container()
    hub.outline_host = host
    host.content = hub._compose_outline(host=host)

    def roteiro_group():
        return host.content.content.controls[0]

    def roteiro_toggle():
        header_row = roteiro_group().controls[0].content
        return header_row.controls[0].controls[0]

    assert [item.data for item in hub.outline_items] == ['Capítulo 1', 'Capítulo 2']
    assert len(roteiro_group().controls) == 3  # cabeçalho + dois capítulos

    roteiro_toggle().on_click(None)
    assert hub._outline_roteiro_collapsed is True
    assert len(roteiro_group().controls) == 1

    roteiro_toggle().on_click(None)
    assert hub._outline_roteiro_collapsed is False
    assert len(roteiro_group().controls) == 3

    chapter_box = roteiro_group().controls[1].content
    chapter_box.content.controls[0].on_click(None)
    assert 10 not in hub._collapsed_set()
    assert [item.data for item in hub.outline_items] == [
        'Capítulo 1', 'Argumento 1.1', 'Capítulo 2',
    ]
    assert len(roteiro_group().controls) == 4

    from src.views.ui_kit import s
    child_box = roteiro_group().controls[2].content
    assert child_box.margin.left == s(32)
    assert child_box.padding.left == s(16)
    assert child_box.border.left.color == view_config.colors['border_strong']

    chapter_box = roteiro_group().controls[1].content
    chapter_box.content.controls[0].on_click(None)
    assert 10 in hub._collapsed_set()
    assert [item.data for item in hub.outline_items] == ['Capítulo 1', 'Capítulo 2']
    assert len(roteiro_group().controls) == 3

"""Testes estruturais da decomposição de ``WorksComposer`` em mixins.

Garantem que a fachada pública continua exportada por ``src.views.works``,
que os métodos exigidos permanecem resolvíveis e que a movimentação para os
três mixins não introduziu definições duplicadas na MRO.
"""

import flet as ft

import src.views.works as works_module
from src.views.works import AcervoContext, WorksComposer
from src.views.works_inspector import WorksInspectorMixin
from src.views.works_table import WorksTableMixin
from src.views.works_toolbar import WorksToolbarMixin

MIXINS = (WorksTableMixin, WorksToolbarMixin, WorksInspectorMixin)

TABLE_METHODS = (
    "visible_rows", "_matches", "_sort_value", "_refresh",
    "_refresh_table_only", "select", "toggle_checked", "set_sort",
    "set_type_filter", "set_compilation_filter", "move_selection",
    "handle_key", "_checkbox", "_visible_columns", "_cell", "_header_row",
    "_row", "_compose_table", "_toggle_magazine_collapse",
    "_magazine_banner_row", "_open_edit_magazine_dialog",
    "_save_edited_magazine", "_open_delete_magazine_dialog",
)
TOOLBAR_METHODS = (
    "_on_search", "_copy_reference", "_copy_checked", "_confirm_delete",
    "_type_menu", "_compilation_menu", "_compose_toolbar", "_clear_checked",
    "_add_checked_to", "_add_one_to", "_clear_filters",
)
INSPECTOR_METHODS = (
    "_details_helper", "_reference_text", "_compose_inspector",
    "_set_inspector_tab", "_open_pdf_reader", "_open_attach_pdf_picker",
    "_confirm_detach_pdf", "_inspector_overview", "_inspector_fragments",
    "_copy_fragment", "_section", "_link",
)
# Helpers compartilhados por mais de um mixin permanecem na fachada.
COMPOSER_METHODS = (
    "__init__", "_get_specific_work", "_work", "_type_label",
    "_fragment_count", "_is_magazine", "_work_has_pdf", "_parent_id",
    "_reference", "_count_label", "_popup", "_compose_body", "compose",
)
# Métodos que os testes existentes chamam diretamente pelo ``WorksComposer``.
REQUIRED_METHODS = (
    "_row", "_compose_body", "_compose_inspector",
    "_toggle_magazine_collapse", "_type_menu", "_work_has_pdf",
    "_confirm_detach_pdf", "_inspector_fragments",
)


def test_mro_contains_the_three_mixins():
    mro = WorksComposer.__mro__
    for mixin in MIXINS:
        assert mixin in mro
    assert mro.index(WorksTableMixin) < mro.index(WorksToolbarMixin)
    assert mro.index(WorksToolbarMixin) < mro.index(WorksInspectorMixin)


def test_required_methods_resolve_through_composer():
    for name in REQUIRED_METHODS:
        assert callable(getattr(WorksComposer, name))


def test_methods_live_in_their_designated_classes():
    assert isinstance(works_module.AcervoContext, type)
    assert isinstance(works_module.WorksComposer, type)
    for name in TABLE_METHODS:
        assert name in WorksTableMixin.__dict__, name
    for name in TOOLBAR_METHODS:
        assert name in WorksToolbarMixin.__dict__, name
    for name in INSPECTOR_METHODS:
        assert name in WorksInspectorMixin.__dict__, name
    for name in COMPOSER_METHODS:
        assert name in WorksComposer.__dict__, name


def test_minimal_composer_composes_body(view_config):
    composer = WorksComposer(
        scale=1,
        config=view_config,
        works=[],
        on_navigate=lambda _destination: None,
        on_work_click=lambda _resource: None,
        on_edit_work=lambda _resource: None,
        format_reference=lambda _resource: None,
        on_copy_reference=lambda _reference: None,
        on_delete_work=lambda _resource: None,
    )
    body = composer._compose_body()
    assert isinstance(body, ft.Control)
    assert body.controls


def test_no_method_is_defined_in_more_than_one_mro_class():
    seen: dict[str, type] = {}
    for cls in WorksComposer.__mro__:
        if cls is object:
            continue
        for name in cls.__dict__:
            if name.startswith("__") and name.endswith("__"):
                continue
            assert name not in seen, (
                f"{name} definido em {seen[name].__name__} e {cls.__name__}"
            )
            seen[name] = cls


def test_mixins_have_no_init_and_keep_context_dataclass_intact():
    for mixin in MIXINS:
        assert "__init__" not in mixin.__dict__
    assert AcervoContext().fragments_by_work == {}
    assert AcervoContext().compilations_by_work == {}
    assert AcervoContext().compilations == []

"""Acervo (redesign v2): tabela de obras, filtros, seleção em lote e painel."""

from collections.abc import Awaitable, Callable

import flet as ft

from src.domains import BibliographicResource, WorkMixin
from src.utils.fa import fa_icon
from src.utils.types import (
    ViewConfig,
    ViewReference,
    WORK_TYPE_LABELS,
)
from src.views import ui_kit as ui
from src.views.ui_kit import s

from src.views.works_common import (  # noqa: F401 - reexportados
    COLUMNS,
    MONTHS,
    TYPE_ICONS,
    AcervoContext,
    author_names,
    format_date,
    year_sort_key,
)
from src.views.works_inspector import WorksInspectorMixin
from src.views.works_table import WorksTableMixin
from src.views.works_toolbar import WorksToolbarMixin
from src.utils.control_safety import safe_update


class WorksComposer(WorksTableMixin, WorksToolbarMixin, WorksInspectorMixin):
    """Fachada pública do Acervo; helpers compartilhados vivem nesta classe."""

    def __init__(
            self,
            scale: float,
            config: ViewConfig,
            works: list[BibliographicResource],
            on_navigate,
            on_work_click: Callable[[BibliographicResource], None],
            on_edit_work: Callable[[BibliographicResource], None],
            format_reference: Callable[
                [BibliographicResource], ViewReference | None
            ],
            on_copy_reference: Callable[[ViewReference], Awaitable[None]],
            on_delete_work: Callable[[BibliographicResource], None],
            page: ft.Page | None = None,
            context: AcervoContext | None = None,
            focus_work_id: int | None = None,
            type_filter: str | None = None,
            on_add_to_compilation: Callable[[int, int], bool] | None = None,
            on_delete_works: Callable[[list[BibliographicResource]], None] | None = None,
            on_copy_text: Callable[[str], Awaitable[None]] | None = None,
            nous_service: object | None = None,
            sort_key: str | None = None,
            sort_desc: bool | None = None,
            on_import_work: Callable[[], None] | None = None,
            on_update_magazine: Callable[[int, str, str], None] | None = None,
            on_delete_magazine: Callable[[BibliographicResource], None] | None = None,
    ) -> None:
        self.scale = scale
        self.config = config
        self.works = [work for work in (works or []) if work is not None]
        self.on_navigate = on_navigate
        self.on_work_click = on_work_click
        self.on_edit_work = on_edit_work
        self.format_reference = format_reference
        self.on_copy_reference = on_copy_reference
        self.on_delete_work = on_delete_work
        self.page = page
        self.context = context or AcervoContext()
        self.on_add_to_compilation = on_add_to_compilation
        self.on_delete_works = on_delete_works
        self.on_copy_text = on_copy_text
        self.nous_service = nous_service
        self.on_import_work = on_import_work
        self.on_update_magazine = on_update_magazine
        self.on_delete_magazine = on_delete_magazine
        self.collapsed_magazines: set[int] = set()

        self.query = ""
        self.type_filter = type_filter
        self.compilation_filter: int | None = None
        self.sort_key = sort_key if sort_key in {key for key, *_ in COLUMNS} else "created"
        self.sort_desc = True if sort_desc is None else bool(sort_desc)
        self.selected_id: int | None = focus_work_id
        self.inspector_tab = "geral"
        self.checked: set[int] = set()
        self.root: ft.Container | None = None
        self.search = ui.search_field(
            config, "Buscar por título, autor ou ano",
            on_change=self._on_search, width=280,
        )

    @staticmethod
    def _get_specific_work(resource: BibliographicResource | None) -> WorkMixin | None:
        if resource is None:
            return None
        return resource.specific_work

    def _work(self, resource_id: int | None) -> BibliographicResource | None:
        return next((r for r in self.works if r.id == resource_id), None)

    def _type_label(self, resource) -> str:
        work = self._get_specific_work(resource)
        if work is None:
            return ""
        return WORK_TYPE_LABELS.get(type(work).__name__, type(work).__name__)

    def _fragment_count(self, resource) -> int:
        return len(self.context.fragments_by_work.get(resource.id, []))

    @staticmethod
    def _is_magazine(resource: BibliographicResource | None) -> bool:
        if resource is None:
            return False
        return getattr(resource, "is_magazine", False)

    @staticmethod
    def _work_has_pdf(resource: BibliographicResource | None) -> bool:
        """Verifica se o recurso possui PDF vinculado e com arquivo existente em disco."""
        if resource is None:
            return False
        pdf_rel = getattr(resource, "pdf_path", None)
        if not pdf_rel:
            return False
        from src.services.pdf_service import PdfService
        try:
            return PdfService().resolve_path(pdf_rel).is_file()
        except Exception:
            return False

    def _parent_id(self, resource) -> int | None:
        work = self._get_specific_work(resource)
        return getattr(work, "parent_bibliographic_resource_id", None) if work is not None else None

    def _reference(self, resource) -> ViewReference | None:
        try:
            return self.format_reference(resource)
        except Exception:
            return None

    def _count_label(self) -> str:
        total_substantive = sum(1 for r in self.works if not self._is_magazine(r))
        matching_substantive = sum(
            1 for r in self.works
            if not self._is_magazine(r) and self._matches(r)
        )
        noun = "obra" if total_substantive == 1 else "obras"
        if matching_substantive == total_substantive:
            return f"{total_substantive} {noun}"
        return f"{matching_substantive} de {total_substantive} {noun}"

    def _popup(self, trigger: ft.Control, heading: str | None, items: list) -> ft.PopupMenuButton:
        c = self.config
        menu_items: list[ft.PopupMenuItem] = []
        if heading:
            menu_items.append(ft.PopupMenuItem(content=ui.ui_text(c, heading, size=12, weight=ui.W600, color=c.colors["faint"]), height=s(28)))
        for icon_spec, label, trailing, handler in items:
            if icon_spec is None:
                menu_items.append(ft.PopupMenuItem())
                continue
            name, style = icon_spec
            danger = label.startswith("Excluir")
            color = c.colors["danger"] if danger else c.colors["text"]
            row: list[ft.Control] = [
                fa_icon(name, size=s(12), color=c.colors["danger"] if danger else c.colors["faint"], style=style),
                ui.ui_text(c, label, size=13, color=color, expand=True),
            ]
            if trailing:
                row.append(ui.ui_text(c, trailing, size=12, color=c.colors["faint"], tabular=True))
            menu_items.append(ft.PopupMenuItem(content=ft.Row(row, spacing=s(10), width=s(220)), height=s(34), on_click=handler))
        return ft.PopupMenuButton(
            content=trigger,
            items=menu_items,
            bgcolor=c.colors["surface"],
            menu_position=ft.PopupMenuPosition.UNDER,
            shape=ft.RoundedRectangleBorder(radius=s(8)),
            tooltip="",
        )

    def _compose_body(self) -> ft.Control:
        c = self.config
        total = sum(1 for r in self.works if not self._is_magazine(r))
        types = {
            self._type_label(r)
            for r in self.works
            if not self._is_magazine(r) and self._type_label(r)
        }
        description = (
            f"{total} {'obra catalogada' if total == 1 else 'obras catalogadas'} em {len(types)} {'tipo documental' if len(types) == 1 else 'tipos documentais'}."
            if total else "Nenhuma obra cadastrada ainda."
        )
        header = ui.page_header(
            c, "Acervo", description,
            actions=[
                ui.button(c, "Nova obra", icon_name="plus", variant="primary", on_click=lambda _e: self.on_navigate("work_insert")),
            ],
        )
        self.toolbar_host = ft.Container(self._compose_toolbar())
        self.table_host = ft.Container(self._compose_table(), expand=True)
        self.inspector_host = ft.Container(
            content=self._compose_inspector(framed=False),
            width=self._inspector_width(),
            bgcolor=c.colors["surface"] if self._inspector_visible() else None,
            border=ft.Border.only(left=ft.BorderSide(1, c.colors["border"])) if self._inspector_visible() else None,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            opacity=1.0 if self._inspector_visible() else 0.0,
            animate=ui.motion(ui.MOTION_SLOW),
            animate_opacity=ui.fade(ui.MOTION_SLOW),
        )
        split = ft.Container(
            ft.Row([self.table_host, self.inspector_host], spacing=0, vertical_alignment=ft.CrossAxisAlignment.STRETCH, expand=True),
            expand=True,
            border=ft.Border.only(top=ft.BorderSide(1, c.colors["border"])),
        )
        return ft.Column([header, self.toolbar_host, split], spacing=0, expand=True)

    def _inspector_visible(self) -> bool:
        resource = self._work(self.selected_id)
        return resource is not None and not self._is_magazine(resource)

    def _inspector_width(self) -> float:
        return s(self.config.ui.get("inspector_width", 380)) if self._inspector_visible() else 0

    def _render_inspector(self) -> bool:
        """Atualiza só o painel; devolve ``False`` se os hosts ainda não existem."""
        host = getattr(self, "inspector_host", None)
        if host is None:
            return False
        c = self.config
        visible = self._inspector_visible()
        host.content = self._compose_inspector(framed=False) if visible else host.content
        host.width = self._inspector_width()
        host.opacity = 1.0 if visible else 0.0
        host.bgcolor = c.colors["surface"] if visible else None
        host.border = ft.Border.only(left=ft.BorderSide(1, c.colors["border"])) if visible else None
        safe_update(host)
        return True

    def compose(self) -> ft.Container:
        self.root = ft.Container(content=self._compose_body(), expand=True, bgcolor=self.config.colors["bg"])
        return self.root

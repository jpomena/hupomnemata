"""Acervo (redesign v2): tabela de obras, filtros, seleção em lote e painel."""

import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

import flet as ft

from src.domains import BibliographicResource, WorkMixin
from src.utils.error_log import log_exception
from src.utils.fa import fa_icon
from src.utils.types import (
    ReferencePart,
    TextStyle,
    ViewConfig,
    ViewReference,
    WORK_TYPE_LABELS,
)
from src.views import ui_kit as ui
from src.views.ui_kit import s

TYPE_ICONS = {
    "Livros em geral": ("book-open", "solid"),
    "Trabalho acadêmico": ("graduation-cap", "solid"),
    "Correspondência": ("envelope", "regular"),
    "Artigo de revista": ("file-lines", "regular"),
    "Revista": ("book-open-reader", "solid"),
    "Coleção periódica": ("book", "solid"),
    "Artigo de jornal": ("newspaper", "regular"),
    "Anais de evento em volume único": ("calendar-days", "regular"),
    "Anais de evento em periódico": ("calendar-days", "regular"),
    "Legislação": ("gavel", "solid"),
    "Jurisprudência": ("building-columns", "solid"),
    "Patente": ("lightbulb", "regular"),
    "Documento digital": ("file-lines", "regular"),
    "Audiovisual": ("film", "solid"),
    "Áudio": ("music", "solid"),
    "Partitura": ("music", "solid"),
    "Documento visual": ("image", "regular"),
    "Cartográfico": ("map", "regular"),
    "Tridimensional": ("cube", "solid"),
}
MONTHS = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]

# (chave, rótulo, largura fixa ou None = flexível, alinhado à direita)
COLUMNS = [
    ("title", "Título", None, False),
    ("author", "Autoria", None, False),
    ("type", "Tipo", 150, False),
    ("year", "Ano", 80, True),
    ("frag", "Frag.", 52, True),
    ("created", "Adicionada", 104, True),
]


@dataclass
class AcervoContext:
    """Dados de apoio vindos do controller (fragmentos e compilações por obra)."""

    fragments_by_work: dict[int, list[dict]] = field(default_factory=dict)
    compilations_by_work: dict[int, list[tuple[int, str]]] = field(default_factory=dict)
    compilations: list[tuple[int, str]] = field(default_factory=list)


def author_names(resource: BibliographicResource) -> str:
    """Nomes de autoria como o usuário cadastrou (pessoas e entidades)."""
    names: list[str] = []
    for author in getattr(resource, "authors", None) or []:
        if getattr(author, "corporation", False):
            legal = (author.given_names or author.last_name or "").strip()
            jurisdiction = getattr(author, "jurisdiction", None)
            if jurisdiction is not None:
                place = (jurisdiction.given_names or jurisdiction.last_name or "").strip()
                if place and place != legal:
                    legal = f"{place}. {legal}" if legal else place
            if legal:
                names.append(legal)
            continue
        full = f"{author.given_names or ''} {author.last_name or ''}".strip()
        if full:
            names.append(full)
    return ", ".join(names)


def format_date(value) -> str:
    if value is None or not hasattr(value, "year"):
        return ""
    return f"{value.day} {MONTHS[value.month - 1]} {value.year}"


def year_sort_key(value: str) -> int:
    match = re.search(r"\d+", str(value or ""))
    number = int(match.group()) if match else 99999
    return -number if "a.C" in str(value or "") else number


class WorksComposer:
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

    # ── dados ──────────────────────────────────────────────

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

    def _parent_id(self, resource) -> int | None:
        work = self._get_specific_work(resource)
        return getattr(work, "parent_bibliographic_resource_id", None) if work is not None else None

    def _matches(self, resource) -> bool:
        work = self._get_specific_work(resource)
        if work is None:
            return False
        if self.type_filter and self._type_label(resource) != self.type_filter:
            return False
        if self.compilation_filter is not None:
            ids = [cid for cid, _ in self.context.compilations_by_work.get(resource.id, [])]
            if self.compilation_filter not in ids:
                return False
        query = self.query.strip().lower()
        if query:
            haystack = " ".join(
                str(part) for part in (
                    work.title, getattr(work, "subtitle", "") or "",
                    getattr(work, "display_year", "") or "", author_names(resource),
                    getattr(work, "journal_title", "") or "",
                )
            ).lower()
            return query in haystack
        return True

    def _sort_value(self, resource):
        work = self._get_specific_work(resource)
        key = self.sort_key
        if key == "title":
            return (work.title or "").lower()
        if key == "author":
            return author_names(resource).lower() or "~"
        if key == "type":
            return self._type_label(resource)
        if key == "year":
            return year_sort_key(getattr(work, "display_year", ""))
        if key == "frag":
            return self._fragment_count(resource)
        created = getattr(work, "created_at", None)
        return (created.isoformat() if created else "", resource.id)

    def visible_rows(self) -> list[tuple[BibliographicResource, int]]:
        """Obras filtradas e ordenadas. Revistas formam banners estruturais (-1)."""
        magazines_by_id = {r.id: r for r in self.works if self._is_magazine(r)}

        # Filtra apenas obras substantivas que atendem aos filtros ativos
        matching_substantive = [
            r for r in self.works
            if not self._is_magazine(r) and self._matches(r)
        ]
        matching_substantive.sort(key=self._sort_value, reverse=self.sort_desc)

        # Agrupa artigos por revista e identifica capítulos de monografias
        magazine_articles: dict[int, list[BibliographicResource]] = {}
        standalone_roots: list[BibliographicResource] = []
        non_mag_children: dict[int, list[BibliographicResource]] = {}

        for r in matching_substantive:
            pid = self._parent_id(r)
            if pid is not None and pid in magazines_by_id:
                magazine_articles.setdefault(pid, []).append(r)
            elif pid is not None:
                non_mag_children.setdefault(pid, []).append(r)
            else:
                standalone_roots.append(r)

        # Prepara grupos de topo: obras standalone e grupos de revistas
        top_items = []
        for r in standalone_roots:
            top_items.append(("work", self._sort_value(r), r))

        for mag_id, articles in magazine_articles.items():
            mag_resource = magazines_by_id[mag_id]
            if self.sort_key == "title":
                top_sort_val = self._sort_value(mag_resource)
            else:
                top_sort_val = self._sort_value(articles[0])
            top_items.append(("magazine", top_sort_val, (mag_resource, articles)))

        top_items.sort(key=lambda it: it[1], reverse=self.sort_desc)

        ordered: list[tuple[BibliographicResource, int]] = []
        for kind, _key, data in top_items:
            if kind == "work":
                r = data
                ordered.append((r, 0))
                for child in non_mag_children.get(r.id, []):
                    ordered.append((child, 1))
            elif kind == "magazine":
                mag_res, articles = data
                ordered.append((mag_res, -1))
                if mag_res.id not in self.collapsed_magazines:
                    for art in articles:
                        ordered.append((art, 1))

        return ordered

    # ── ações ──────────────────────────────────────────────

    def _refresh(self) -> None:
        if self.root is None:
            return
        self.root.content = self._compose_body()
        try:
            self.root.update()
        except Exception:
            pass

    def _on_search(self, event) -> None:
        self.query = event.control.value or ""
        self._refresh_table_only()

    def _refresh_table_only(self) -> None:
        if getattr(self, "table_host", None) is None:
            return self._refresh()
        self.table_host.content = self._compose_table()
        self.count_text.value = self._count_label()
        for control in (self.table_host, self.count_text):
            try:
                control.update()
            except Exception:
                pass

    def select(self, resource_id: int | None) -> None:
        self.selected_id = resource_id
        self._refresh()

    def toggle_checked(self, resource_id: int) -> None:
        if resource_id in self.checked:
            self.checked.discard(resource_id)
        else:
            self.checked.add(resource_id)
        self._refresh()

    def set_sort(self, key: str) -> None:
        if self.sort_key == key:
            self.sort_desc = not self.sort_desc
        else:
            self.sort_key = key
            self.sort_desc = key in {"year", "frag", "created"}
        self._refresh()

    def set_type_filter(self, value: str | None) -> None:
        self.type_filter = value
        self._refresh()

    def set_compilation_filter(self, value: int | None) -> None:
        self.compilation_filter = value
        self._refresh()

    def move_selection(self, step: int) -> None:
        ids = [
            r.id for r, lvl in self.visible_rows()
            if not self._is_magazine(r)
        ]
        if not ids:
            return
        if self.selected_id not in ids:
            self.select(ids[0])
            return
        index = max(0, min(len(ids) - 1, ids.index(self.selected_id) + step))
        self.select(ids[index])

    def handle_key(self, key: str, mod: bool) -> bool:
        """Atalhos da tabela: ↑/↓ navegam, espaço marca, Esc fecha/limpa."""
        if key in ("Arrow Down", "Arrow Up") and not mod:
            self.move_selection(1 if key == "Arrow Down" else -1)
            return True
        if key == "Escape":
            if self.checked:
                self.checked.clear()
            elif self.selected_id is not None:
                self.selected_id = None
            else:
                return False
            self._refresh()
            return True
        if mod and key.upper() == "C" and self.selected_id is not None:
            resource = self._work(self.selected_id)
            if resource is not None:
                self._copy_reference(resource)
            return True
        return False

    def _reference(self, resource) -> ViewReference | None:
        try:
            return self.format_reference(resource)
        except Exception:
            return None

    def _copy_reference(self, resource, button: ft.Container | None = None) -> None:
        reference = self._reference(resource)
        if reference is None or self.page is None:
            return

        async def run():
            await self.on_copy_reference(reference)

        self.page.run_task(run)
        if button is not None:
            ui.flash_button(button, "Copiada", "Copiar", self.page)

    def _copy_checked(self, button: ft.Container | None = None) -> None:
        parts: list[ReferencePart] = []
        for resource, _level in self.visible_rows():
            if resource.id not in self.checked:
                continue
            reference = self._reference(resource)
            if reference is None:
                continue
            if parts:
                parts.append(ReferencePart(content="\n\n"))
            parts.extend(reference.parts)
        if not parts or self.page is None:
            return

        async def run():
            await self.on_copy_reference(ViewReference(parts=parts))

        self.page.run_task(run)
        if button is not None:
            ui.flash_button(button, "Copiadas", "Copiar referências", self.page)

    def _confirm_delete(self, resources: list[BibliographicResource]) -> None:
        """Excluir apaga a obra e os fragmentos dela no banco: pede confirmação."""
        if not resources or self.page is None:
            return
        c = self.config
        total_fragments = sum(self._fragment_count(r) for r in resources)
        title = (
            f"Excluir “{self._get_specific_work(resources[0]).title}”?"
            if len(resources) == 1 else f"Excluir {len(resources)} obras?"
        )
        detail = "A obra sai do acervo e das compilações." if len(resources) == 1 else "As obras saem do acervo e das compilações."
        if total_fragments:
            detail += f" {total_fragments} fragmento{'s' if total_fragments != 1 else ''} também {'serão excluídos' if total_fragments != 1 else 'será excluído'}."
        dialog: ft.AlertDialog | None = None

        def close(_e=None):
            self.page.pop_dialog()

        def confirm(_e=None):
            close()
            self.checked.difference_update(r.id for r in resources)
            if self.selected_id in {r.id for r in resources}:
                self.selected_id = None
            if self.on_delete_works is not None:
                self.on_delete_works(resources)
            else:
                for resource in resources:
                    self.on_delete_work(resource)

        dialog = ft.AlertDialog(
            bgcolor=c.colors["surface"],
            shape=ft.RoundedRectangleBorder(radius=s(10)),
            title=ui.ui_text(c, title, size=15, weight=ui.W600, max_lines=2),
            content=ft.Container(ui.ui_text(c, detail + " Essa ação não pode ser desfeita.", size=13, color=c.colors["muted"], max_lines=4), width=s(420)),
            actions=[
                ui.button(c, "Cancelar", on_click=close, variant="ghost"),
                ui.button(c, "Excluir", on_click=confirm, variant="danger", icon_name="trash-can", icon_style="regular"),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.show_dialog(dialog)

    # ── composição ─────────────────────────────────────────

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

    def _type_menu(self) -> ft.Control:
        counts: dict[str, int] = {}
        for resource in self.works:
            if self._is_magazine(resource):
                continue
            label = self._type_label(resource)
            if label:
                counts[label] = counts.get(label, 0) + 1
        if self.type_filter:
            return ui.chip_filter(self.config, "Tipo", active_value=self.type_filter, on_clear=lambda _e: self.set_type_filter(None))
        return self._popup(
            ui.chip_filter(self.config, "Tipo"),
            "Filtrar por tipo",
            [
                (TYPE_ICONS.get(label, ("file-lines", "regular")), label, str(count), (lambda _e, v=label: self.set_type_filter(v)))
                for label, count in sorted(counts.items(), key=lambda item: -item[1])
            ],
        )

    def _compilation_menu(self) -> ft.Control:
        compilations = self.context.compilations
        if self.compilation_filter is not None:
            name = next((n for cid, n in compilations if cid == self.compilation_filter), "")
            return ui.chip_filter(self.config, "Compilação", active_value=name, on_clear=lambda _e: self.set_compilation_filter(None))
        counts = {cid: 0 for cid, _ in compilations}
        for links in self.context.compilations_by_work.values():
            for cid, _ in links:
                counts[cid] = counts.get(cid, 0) + 1
        return self._popup(
            ui.chip_filter(self.config, "Compilação"),
            "Filtrar por compilação",
            [(("folder", "regular"), name, str(counts.get(cid, 0)), (lambda _e, v=cid: self.set_compilation_filter(v))) for cid, name in compilations],
        )

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

    def _compose_toolbar(self) -> ft.Control:
        c = self.config
        if self.checked:
            noun = "obra selecionada" if len(self.checked) == 1 else "obras selecionadas"
            copy_button = ui.button(c, "Copiar referências", icon_name="copy", icon_style="regular", small=True)
            copy_button.on_click = lambda _e: self._copy_checked(copy_button)
            add_items = [
                (("folder", "regular"), name, None, (lambda _e, cid=cid: self._add_checked_to(cid)))
                for cid, name in self.context.compilations
            ]
            add_button = self._popup(ui.button(c, "Adicionar à compilação", icon_name="bookmark", icon_style="regular", small=True), "Escolha a compilação", add_items)
            selected = [r for r in self.works if r.id in self.checked]
            return ft.Container(
                content=ft.Row(
                    [
                        ui.ui_text(c, f"{len(self.checked)} {noun}", size=13, weight=ui.W600),
                        copy_button,
                        add_button,
                        ui.button(c, "Excluir", icon_name="trash-can", icon_style="regular", variant="danger", small=True, on_click=lambda _e: self._confirm_delete(selected)),
                        ft.Container(expand=True),
                        ft.Row([ui.button(c, "Limpar seleção", variant="ghost", small=True, on_click=lambda _e: self._clear_checked()), ui.kbd(c, "esc")], spacing=s(6), tight=True),
                    ],
                    spacing=s(8),
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                height=s(40),
                padding=ft.Padding.only(left=s(12), right=s(8)),
                margin=ft.Margin.only(left=s(32), right=s(32), bottom=s(10), top=s(2)),
                bgcolor=c.colors["surface"],
                border=ft.Border.all(1, c.colors["gold"]),
                border_radius=ft.BorderRadius.all(s(8)),
            )
        self.count_text = ui.ui_text(c, self._count_label(), size=12, color=c.colors["faint"], tabular=True)
        self.search.value = self.query
        return ui.toolbar(c, [self.search, self._type_menu(), self._compilation_menu()], trailing=[self.count_text])

    def _clear_checked(self) -> None:
        self.checked.clear()
        self._refresh()

    def _add_checked_to(self, compilation_id: int) -> None:
        if self.on_add_to_compilation is None:
            return
        for resource_id in list(self.checked):
            self.on_add_to_compilation(compilation_id, resource_id)
        if self.page is not None:
            ui.toast(self.page, self.config, f"{len(self.checked)} obra(s) adicionada(s) à compilação")
        self.checked.clear()
        self._refresh()

    def _checkbox(self, checked: bool, on_click, partial: bool = False) -> ft.Container:
        c = self.config
        mark = None
        if checked:
            mark = fa_icon("check", size=s(9), color=c.colors["on_gold"])
        elif partial:
            mark = fa_icon("minus", size=s(9), color=c.colors["on_gold"])
        return ft.Container(
            content=mark,
            width=s(16), height=s(16),
            alignment=ft.Alignment.CENTER,
            border_radius=ft.BorderRadius.all(s(4)),
            border=ft.Border.all(1, c.colors["gold"] if (checked or partial) else c.colors["faint"]),
            bgcolor=c.colors["gold"] if (checked or partial) else c.colors["bg"],
            on_click=on_click,
        )

    def _visible_columns(self) -> list[tuple[str, str, int | None, bool]]:
        if self.selected_id is not None:
            return [col for col in COLUMNS if col[0] not in {"author", "created"}]
        return COLUMNS

    def _cell(self, key: str, width: int | None, control: ft.Control, right: bool = False) -> ft.Container:
        flex = {"title": 24, "author": 12}.get(key)
        return ft.Container(
            content=control,
            width=s(width) if width else None,
            expand=flex if width is None else None,
            alignment=ft.Alignment.CENTER_RIGHT if right else ft.Alignment.CENTER_LEFT,
            padding=ft.Padding.symmetric(horizontal=s(8)),
        )

    def _header_row(self, rows: list) -> ft.Container:
        c = self.config
        ids = [r.id for r, _ in rows if not self._is_magazine(r)]
        n_checked = len([i for i in ids if i in self.checked])
        all_checked = bool(ids) and n_checked == len(ids)

        def toggle_all(_e):
            if all_checked:
                self.checked.difference_update(ids)
            else:
                self.checked.update(ids)
            self._refresh()

        cells: list[ft.Control] = [
            ft.Container(self._checkbox(all_checked, toggle_all, partial=0 < n_checked < len(ids)), width=s(64), padding=ft.Padding.only(left=s(32)), alignment=ft.Alignment.CENTER_LEFT),
        ]
        for key, label, width, right in self._visible_columns():
            active = self.sort_key == key
            parts: list[ft.Control] = [
                ui.ui_text(
                    c,
                    label,
                    size=12,
                    weight=ui.W600 if active else ui.W500,
                    color=c.colors["gold"] if active else c.colors["faint"],
                )
            ]
            if active:
                parts.append(
                    fa_icon(
                        "arrow-down" if self.sort_desc else "arrow-up",
                        size=s(9),
                        color=c.colors["gold"],
                    )
                )
            header = ft.Container(ft.Row(parts, spacing=s(4), tight=True), on_click=lambda _e, k=key: self.set_sort(k))
            cells.append(self._cell(key, width, header, right))
        return ft.Container(
            content=ft.Row(cells, spacing=0, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            height=s(34),
            padding=ft.Padding.only(right=s(16)),
            bgcolor=c.colors["chrome"],
            border=ft.Border.only(bottom=ft.BorderSide(1, c.colors["gold"])),
        )

    def _row(self, resource, level: int) -> ft.Container:
        c = self.config
        work = self._get_specific_work(resource)
        selected = resource.id == self.selected_id
        checked = resource.id in self.checked
        count = self._fragment_count(resource)
        title_parts: list[ft.Control] = []
        if level:
            title_parts.append(ft.Container(fa_icon("turn-up", size=s(9), color=c.colors["border_strong"]), rotate=ft.Rotate(1.5708), width=s(16), margin=ft.Margin.only(left=s(4 + 12 * (level - 1)))))
        title_text = ui.serif_text(c, work.title or "", size=16.5, weight=ui.W700, color=c.colors["gold"] if selected else c.colors["text"], max_lines=1, expand=True)
        title_text.expand_loose = True
        if work.title:
            title_text.tooltip = work.title
        title_parts.append(title_text)
        if getattr(resource, "pdf_path", None):
            title_parts.append(
                ft.Container(
                    content=ui.badge(c, "PDF", icon_name="file-pdf", variant="gold"),
                    on_click=lambda _e, res=resource: self._open_pdf_reader(res),
                    tooltip="Abrir no Leitor de PDF",
                    ink=True,
                )
            )
        subtitle = getattr(work, "subtitle", None)
        if subtitle:
            sub_text = ui.serif_text(c, subtitle, size=14, weight=ui.W600, color=c.colors["faint"], italic=True, max_lines=1, expand=True)
            sub_text.expand_loose = True
            sub_text.tooltip = subtitle
            title_parts.append(sub_text)
        values = {
            "title": ft.Row(title_parts, spacing=s(8), vertical_alignment=ft.CrossAxisAlignment.CENTER),
            "author": ui.ui_text(c, author_names(resource) or "Sem autoria", size=13, color=c.colors["muted"]),
            "type": ui.ui_text(c, self._type_label(resource), size=13, color=c.colors["muted"]),
            "year": ui.ui_text(c, str(getattr(work, "display_year", "") or ""), size=13, color=c.colors["muted"], tabular=True),
            "frag": ui.ui_text(c, str(count), size=13, color=c.colors["muted"] if count else c.colors["faint"], tabular=True),
            "created": ui.ui_text(c, format_date(getattr(work, "created_at", None)), size=13, color=c.colors["faint"], tabular=True),
        }
        cells: list[ft.Control] = [
            ft.Container(self._checkbox(checked, lambda _e, rid=resource.id: self.toggle_checked(rid)), width=s(64), padding=ft.Padding.only(left=s(32)), alignment=ft.Alignment.CENTER_LEFT),
        ]
        for key, _label, width, right in self._visible_columns():
            cells.append(self._cell(key, width, values[key], right))
        base = ui.alpha(c.colors["gold"], 0.10) if checked else None

        def _on_hover_work(hovering: bool) -> None:
            if not selected:
                title_text.color = c.colors["gold"] if hovering else c.colors["text"]

        row = ui.hover_surface(
            c,
            ft.Row(cells, spacing=0, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            on_click=lambda _e, rid=resource.id: self.select(rid),
            selected=selected,
            height=s(40),
            radius=0,
            base=base,
            padding=ft.Padding.only(right=s(16)),
            border=ft.Border.only(bottom=ft.BorderSide(1, c.colors["border"])),
            accent_left=True,
            on_hover=_on_hover_work,
        )
        row.key = f"work-{resource.id}"
        return row

    def _compose_table(self) -> ft.Control:
        c = self.config
        rows = self.visible_rows()
        if not rows:
            message = f"Nada corresponde a “{self.query}”." if self.query.strip() else "Nenhuma obra com esses filtros."
            has_substantive = any(not self._is_magazine(r) for r in self.works)
            body: ft.Control = ft.Container(
                ui.empty_state(
                    c, "magnifying-glass", "Nenhuma obra encontrada",
                    message + " Busque pelo sobrenome do autor ou pelo ano.",
                    action=ui.button(c, "Limpar filtros", small=True, on_click=lambda _e: self._clear_filters()),
                ) if has_substantive else ui.empty_state(
                    c, "book-open", "Seu acervo está vazio",
                    "Cadastre a primeira obra para começar a registrar fragmentos.",
                    action=ui.button(c, "Nova obra", variant="primary", icon_name="plus", small=True, on_click=lambda _e: self.on_navigate("work_insert")),
                ),
                padding=s(32),
            )
        else:
            magazines_by_id = {r.id: r for r in self.works if self._is_magazine(r)}
            magazine_counts: dict[int, int] = {}
            for r in self.works:
                pid = self._parent_id(r)
                if pid is not None and pid in magazines_by_id:
                    magazine_counts[pid] = magazine_counts.get(pid, 0) + 1

            controls: list[ft.Control] = []
            for resource, level in rows:
                if level == -1 or self._is_magazine(resource):
                    child_count = magazine_counts.get(resource.id, 0)
                    controls.append(self._magazine_banner_row(resource, child_count))
                else:
                    controls.append(self._row(resource, level))

            body = ft.ListView(
                controls=controls,
                expand=True,
                spacing=0,
            )
        footer_text = (
            f"Aberta: {self._get_specific_work(self._work(self.selected_id)).title}"
            if self._work(self.selected_id) is not None and not self._is_magazine(self._work(self.selected_id))
            else "Clique numa obra para ver os detalhes"
        )
        footer = ft.Container(
            content=ft.Row(
                [
                    ui.ui_text(c, footer_text, size=12, color=c.colors["faint"], expand=True),
                    ft.Row([ui.kbd(c, "↑"), ui.kbd(c, "↓"), ui.ui_text(c, "navegar", size=12, color=c.colors["faint"])], spacing=s(4), tight=True),
                    ft.Row([ui.kbd(c, "⌘C"), ui.ui_text(c, "copiar referência", size=12, color=c.colors["faint"])], spacing=s(4), tight=True),
                ],
                spacing=s(16),
            ),
            height=s(36),
            padding=ft.Padding.symmetric(horizontal=s(32)),
            border=ft.Border.only(top=ft.BorderSide(1, c.colors["border"])),
        )
        return ft.Column([self._header_row(rows), body, footer], spacing=0, expand=True)

    def _toggle_magazine_collapse(self, magazine_id: int) -> None:
        if magazine_id in self.collapsed_magazines:
            self.collapsed_magazines.remove(magazine_id)
        else:
            self.collapsed_magazines.add(magazine_id)
        self._refresh()

    def _magazine_banner_row(
        self, resource: BibliographicResource, child_count: int
    ) -> ft.Container:
        c = self.config
        mag = self._get_specific_work(resource)
        mag_title = getattr(mag, "title", "Revista")
        mag_place = getattr(mag, "publication_place", "")

        is_collapsed = resource.id in self.collapsed_magazines
        chevron_icon = fa_icon(
            "chevron-right" if is_collapsed else "chevron-down",
            size=s(9),
            color=c.colors["gold"],
        )
        mag_icon = fa_icon("book-open-reader", size=s(12), color=c.colors["gold"])

        chevron_container = ft.Container(
            content=ft.Row(
                [
                    ft.Container(
                        content=chevron_icon,
                        width=s(32),
                        alignment=ft.Alignment.CENTER,
                    ),
                    ft.Container(
                        content=mag_icon,
                        width=s(16),
                        alignment=ft.Alignment.CENTER,
                    ),
                ],
                spacing=0,
                tight=True,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            width=s(64),
            alignment=ft.Alignment.CENTER_LEFT,
        )

        title_text = ui.serif_text(
            c, mag_title, size=16.5, weight=ui.W700, color=c.colors["text"], max_lines=1, expand=True
        )
        title_text.expand_loose = True
        title_parts: list[ft.Control] = [title_text]
        if mag_place and mag_place != "[s.l.]":
            title_parts.append(
                ui.ui_text(c, f"• {mag_place}", size=12, color=c.colors["faint"])
            )

        title_container = ft.Container(
            content=ft.Row(
                title_parts,
                spacing=s(8),
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding.symmetric(horizontal=s(8)),
            expand=True,
            alignment=ft.Alignment.CENTER_LEFT,
        )

        badge_count = ft.Container(
            content=ui.ui_text(
                c,
                f"{child_count} {'artigo' if child_count == 1 else 'artigos'}",
                size=10.5,
                weight=ui.W600,
                color=c.colors["gold"],
            ),
            bgcolor=ft.Colors.with_opacity(0.10, c.colors["gold"]),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.25, c.colors["gold"])),
            border_radius=s(4),
            padding=ft.Padding.symmetric(horizontal=s(5), vertical=s(1.5)),
        )

        actions_button = ft.PopupMenuButton(
            content=ui.icon_button(c, "ellipsis-vertical", tooltip="Opções do periódico", boxed=False, size=22),
            items=[
                ft.PopupMenuItem(
                    content=ft.Row(
                        [
                            fa_icon("pen-to-square", size=s(12), color=c.colors["faint"]),
                            ui.ui_text(c, "Editar periódico", size=13, color=c.colors["text"]),
                        ],
                        spacing=s(10),
                        tight=True,
                    ),
                    height=s(32),
                    on_click=lambda _e, r=resource: self._open_edit_magazine_dialog(r),
                ),
                ft.PopupMenuItem(
                    content=ft.Row(
                        [
                            fa_icon("trash-can", size=s(12), color=c.colors["danger"]),
                            ui.ui_text(c, "Excluir periódico e artigos", size=13, color=c.colors["danger"]),
                        ],
                        spacing=s(10),
                        tight=True,
                    ),
                    height=s(32),
                    on_click=lambda _e, r=resource, cnt=child_count: (
                        self._open_delete_magazine_dialog(r, cnt)
                    ),
                ),
            ],
            tooltip="Opções do periódico",
            bgcolor=c.colors["surface"],
            elevation=6,
            shape=ft.RoundedRectangleBorder(radius=s(8)),
            menu_position=ft.PopupMenuPosition.UNDER,
        )

        trailing_container = ft.Container(
            content=ft.Row(
                [badge_count, actions_button],
                spacing=s(4),
                tight=True,
                alignment=ft.MainAxisAlignment.END,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            width=s(104),
            padding=ft.Padding.symmetric(horizontal=s(8)),
            alignment=ft.Alignment.CENTER_RIGHT,
        )

        header_content = ft.Row(
            [
                chevron_container,
                title_container,
                trailing_container,
            ],
            spacing=0,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        return ui.hover_surface(
            c,
            header_content,
            on_click=lambda _e, mid=resource.id: self._toggle_magazine_collapse(mid),
            height=s(40),
            radius=0,
            padding=ft.Padding.only(right=s(16)),
            border=ft.Border.only(bottom=ft.BorderSide(1, c.colors["border"])),
        )

    def _open_edit_magazine_dialog(self, resource: BibliographicResource) -> None:
        c = self.config
        mag = self._get_specific_work(resource)
        if mag is None:
            return

        title_input = ft.TextField(
            label="Nome da Revista",
            value=getattr(mag, "title", ""),
            text_size=s(13),
            bgcolor=c.colors.get("surface_variant", c.colors["surface"]),
            border_color=c.colors["border"],
            focused_border_color=c.colors["gold"],
            border_radius=s(6),
            autofocus=True,
        )

        place_input = ft.TextField(
            label="Local de Publicação",
            value=getattr(mag, "publication_place", "[s.l.]"),
            text_size=s(13),
            bgcolor=c.colors.get("surface_variant", c.colors["surface"]),
            border_color=c.colors["border"],
            focused_border_color=c.colors["gold"],
            border_radius=s(6),
        )

        dialog = ft.AlertDialog(
            title=ui.serif_text(c, "Editar Periódico", size=18, weight=ui.W700),
            content=ft.Container(
                content=ft.Column(
                    [
                        ui.ui_text(
                            c,
                            "As alterações serão sincronizadas com todos os artigos vinculados.",
                            size=12,
                            color=c.colors["muted"],
                        ),
                        title_input,
                        place_input,
                    ],
                    spacing=s(12),
                    tight=True,
                ),
                width=s(440),
                padding=s(8),
            ),
            actions=[
                ui.button(
                    c,
                    "Cancelar",
                    variant="ghost",
                    on_click=lambda _e: self.page.pop_dialog() if self.page else None,
                ),
                ui.button(
                    c,
                    "Salvar",
                    variant="primary",
                    icon_name="floppy-disk",
                    on_click=lambda _e: self._save_edited_magazine(
                        resource.id, title_input.value, place_input.value
                    ),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        if self.page:
            self.page.show_dialog(dialog)

    def _save_edited_magazine(
        self, resource_id: int, new_title: str, new_place: str
    ) -> None:
        if self.page:
            self.page.pop_dialog()
        if self.on_update_magazine:
            self.on_update_magazine(resource_id, new_title, new_place)
        else:
            res = self._work(resource_id)
            if res and res.specific_work:
                res.specific_work.title = new_title.strip()
                res.specific_work.publication_place = new_place.strip() or "[s.l.]"
            self._refresh()

    def _open_delete_magazine_dialog(
        self, resource: BibliographicResource, child_count: int
    ) -> None:
        c = self.config
        mag = self._get_specific_work(resource)
        mag_title = getattr(mag, "title", "este periódico")

        def confirm(_e):
            if self.page:
                self.page.pop_dialog()
            if self.on_delete_magazine:
                self.on_delete_magazine(resource)
            else:
                self.on_delete_work(resource)

        msg = (
            f"Tem certeza que deseja excluir o periódico “{mag_title}” e "
            f"TODOS os {child_count} artigos vinculados a ele em cascata?\n\n"
            "Esta ação é irreversível."
            if child_count > 0
            else f"Tem certeza que deseja excluir o periódico “{mag_title}”?"
        )

        dialog = ft.AlertDialog(
            title=ui.serif_text(
                c,
                "Excluir Periódico em Cascata",
                size=18,
                weight=ui.W700,
                color=c.colors.get("danger", "#ef4444"),
            ),
            content=ui.ui_text(c, msg, size=13),
            actions=[
                ui.button(
                    c,
                    "Cancelar",
                    variant="ghost",
                    on_click=lambda _e: self.page.pop_dialog() if self.page else None,
                ),
                ui.button(
                    c,
                    "Excluir Periódico",
                    variant="danger",
                    icon_name="trash-can",
                    on_click=confirm,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        if self.page:
            self.page.show_dialog(dialog)

    def _clear_filters(self) -> None:
        self.query = ""
        self.type_filter = None
        self.compilation_filter = None
        self._refresh()

    # ── painel de detalhes ─────────────────────────────────

    def _details_helper(self, resource):
        from src.views.work_details_popup import WorkDetailsPopup

        return WorkDetailsPopup(
            resource=resource,
            config=self.config,
            on_close=lambda: None,
            page=self.page,
            nous_service=self.nous_service,
            on_open_pdf=lambda _rid, res=resource: self._open_pdf_reader(res),
            on_attach_pdf=lambda res: self._open_attach_pdf_picker(res),
        )

    def _reference_text(self, resource) -> ft.Control:
        c = self.config
        reference = self._reference(resource)
        if reference is None or not reference.parts:
            return ui.ui_text(c, "Este tipo ainda não tem formatador.", size=13, color=c.colors["faint"], max_lines=None)
        spans = [
            ft.TextSpan(
                part.content,
                style=ft.TextStyle(
                    weight=ft.FontWeight.W_700 if part.style == TextStyle.BOLD else None,
                    italic=part.style == TextStyle.ITALIC,
                ),
            )
            for part in reference.parts
        ]
        return ft.Text(
            spans=spans,
            size=s(13),
            color=c.colors["text"],
            font_family=c.font_families["montserrat"],
            selectable=True,
            style=ft.TextStyle(height=1.6),
        )

    def _compose_inspector(self) -> ft.Control | None:
        resource = self._work(self.selected_id)
        if resource is None or self._is_magazine(resource):
            return None
        c = self.config
        work = self._get_specific_work(resource)
        type_label = self._type_label(resource)
        icon_name, icon_style = TYPE_ICONS.get(type_label, ("file-lines", "regular"))
        fragments = self.context.fragments_by_work.get(resource.id, [])

        top = ft.Row(
            [
                ui.badge(c, type_label, icon_name=icon_name),
                ft.Container(expand=True),
                ui.icon_button(c, "chevron-up", on_click=lambda _e: self.move_selection(-1), tooltip="Obra anterior"),
                ui.icon_button(c, "chevron-down", on_click=lambda _e: self.move_selection(1), tooltip="Próxima obra"),
                ui.icon_button(c, "xmark", on_click=lambda _e: self.select(None), tooltip="Fechar (esc)"),
            ],
            spacing=s(2),
        )
        header: list[ft.Control] = [
            top,
            ft.Container(
                ft.Text(work.title, size=s(24), weight=ui.W600, color=c.colors["text"], font_family=c.font_families["cormorant"], style=ft.TextStyle(height=1.15), selectable=True),
                margin=ft.Margin.only(top=s(8)),
            ),
        ]
        if getattr(work, "subtitle", None):
            header.append(ui.ui_text(c, work.subtitle, size=13, color=c.colors["muted"], max_lines=3))
        year = getattr(work, "display_year", "") or ""
        header.append(ui.ui_text(c, " · ".join(filter(None, [author_names(resource) or "Sem autoria", str(year)])), size=13, color=c.colors["muted"], max_lines=2))
        has_pdf = bool(getattr(resource, "pdf_path", None))
        pdf_action = (
            (("book-open", "solid"), "Abrir no Leitor de PDF", None, lambda _e, res=resource: self._open_pdf_reader(res))
            if has_pdf
            else (("paperclip", "solid"), "Anexar arquivo PDF", None, lambda _e, res=resource: self._open_attach_pdf_picker(res))
        )
        more = self._popup(
            ui.icon_button(c, "ellipsis", boxed=True, tooltip="Mais ações"),
            None,
            [
                (("copy", "regular"), "Copiar referência", "⌘C", lambda _e: self._copy_reference(resource)),
                pdf_action,
                *[(("folder", "regular"), f"Adicionar a {name}", None, (lambda _e, cid=cid: self._add_one_to(cid, resource))) for cid, name in self.context.compilations if cid not in {x for x, _ in self.context.compilations_by_work.get(resource.id, [])}],
                (None, "", None, None),
                (("trash-can", "regular"), "Excluir obra", None, lambda _e: self._confirm_delete([resource])),
            ],
        )
        action_buttons = []
        if has_pdf:
            action_buttons.append(
                ui.button(c, "Ler PDF", icon_name="book-open", variant="primary", small=True, on_click=lambda _e, res=resource: self._open_pdf_reader(res))
            )
        action_buttons.extend([
            ui.button(c, "Editar", icon_name="pen", small=True, on_click=lambda _e: self.on_edit_work(resource)),
            ui.button(c, "Ver ficha completa", icon_name="up-right-from-square", small=True, on_click=lambda _e: self.on_work_click(resource)),
            more,
        ])
        header.append(
            ft.Container(
                ft.Row(
                    action_buttons,
                    spacing=s(8),
                ),
                margin=ft.Margin.only(top=s(12)),
            )
        )
        tabs = ui.tabs(
            c,
            [("geral", "Visão geral", None), ("fragmentos", "Fragmentos", len(fragments))],
            self.inspector_tab,
            self._set_inspector_tab,
            padding_left=24,
        )
        body = self._inspector_fragments(fragments) if self.inspector_tab == "fragmentos" else self._inspector_overview(resource)
        return ft.Container(
            width=s(self.config.ui.get("inspector_width", 380)),
            bgcolor=c.colors["surface"],
            border=ft.Border.only(left=ft.BorderSide(1, c.colors["border"])),
            content=ft.Column(
                [
                    ft.Container(ft.Column(header, spacing=s(4), tight=True), padding=ft.Padding.only(left=s(24), right=s(16), top=s(16), bottom=s(12))),
                    tabs,
                    ft.Container(ft.Column(body, spacing=0, scroll=ft.ScrollMode.AUTO, expand=True), expand=True),
                ],
                spacing=0,
                expand=True,
            ),
        )

    def _set_inspector_tab(self, key: str) -> None:
        self.inspector_tab = key
        self._refresh()

    def _open_pdf_reader(self, resource: BibliographicResource) -> None:
        """Abre o leitor imersivo de PDF em janela dedicada independente."""
        from src.views.pdf_reader.standalone import open_pdf_standalone_window

        work = getattr(resource, "specific_work", None)
        title = (
            getattr(work, "title", None) if work else None
        ) or getattr(resource, "pdf_filename", None) or "documento"

        opened = open_pdf_standalone_window(
            resource_id=resource.id,
            page=self.page,
            config=self.config,
            work_title=title,
        )
        if not opened:
            self.on_navigate(f"pdf_reader:{resource.id}")

    def _open_attach_pdf_picker(self, resource: BibliographicResource) -> None:
        """Abre seletor de arquivos para vincular um PDF a esta obra."""
        if not self.page:
            return

        from src.services.pdf_service import PdfService
        from src.utils.file_picker import pick_file

        async def _pick():
            try:
                selected_path = await pick_file(
                    page=self.page,
                    dialog_title="Selecionar PDF para a obra",
                    allowed_extensions=["pdf"],
                )
                if selected_path:
                    svc = PdfService()
                    info = svc.attach_pdf(resource.id, selected_path)
                    resource.pdf_path = info["pdf_path"]
                    resource.pdf_filename = info["pdf_filename"]
                    resource.pdf_page_count = info["pdf_page_count"]
                    if self.page:
                        ui.toast(self.page, self.config, f"PDF anexado: {info['pdf_filename']}")
                    self._refresh()
            except Exception as err:
                log_exception("Falha ao anexar PDF via picker", err)
                if self.page:
                    ui.toast(self.page, self.config, f"Erro ao anexar PDF: {err}")

        self.page.run_task(_pick)

    def _add_one_to(self, compilation_id: int, resource) -> None:
        if self.on_add_to_compilation is None:
            return
        ok = self.on_add_to_compilation(compilation_id, resource.id)
        if ok:
            links = self.context.compilations_by_work.setdefault(resource.id, [])
            name = next((n for cid, n in self.context.compilations if cid == compilation_id), "")
            links.append((compilation_id, name))
            if self.page is not None:
                ui.toast(self.page, self.config, f"Obra adicionada a {name}")
            self._refresh()

    def _section(self, title: str, controls: list[ft.Control], trailing: ft.Control | None = None) -> ft.Container:
        c = self.config
        head = ft.Row([ui.label_text(c, title)] + ([trailing] if trailing else []), alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER)
        return ft.Container(
            ft.Column([head, *controls], spacing=s(8), tight=True),
            padding=ft.Padding.symmetric(horizontal=s(24), vertical=s(16)),
            border=ft.Border.only(bottom=ft.BorderSide(1, c.colors["border"])),
        )

    def _link(self, label: str, on_click) -> ft.Control:
        c = self.config
        text = ft.Text(label, size=s(13), color=c.colors["text"], font_family=c.font_families["montserrat"], style=ft.TextStyle(decoration=ft.TextDecoration.UNDERLINE, decoration_color=c.colors["border_strong"]))
        return ft.Container(text, on_click=on_click)

    def _inspector_overview(self, resource) -> list[ft.Control]:
        c = self.config
        work = self._get_specific_work(resource)
        copy_button = ui.button(c, "Copiar", icon_name="copy", icon_style="regular", small=True)
        copy_button.on_click = lambda _e: self._copy_reference(resource, copy_button)
        reference_box = ft.Container(
            self._reference_text(resource),
            bgcolor=c.colors["bg"],
            border=ft.Border.all(1, c.colors["border"]),
            border_radius=ft.BorderRadius.all(s(6)),
            padding=ft.Padding.symmetric(horizontal=s(12), vertical=s(10)),
        )
        sections = [self._section("Referência ABNT", [reference_box], copy_button)]

        helper = self._details_helper(resource)
        rows: list[tuple[str, ft.Control | str | None]] = [("Tipo", self._type_label(resource)), ("Autoria", author_names(resource) or "Sem autoria")]
        hidden = {"title", "subtitle", "abstract", "is_partial"}
        try:
            for name, value in helper._visible_fields(work):
                if name in hidden:
                    continue
                rows.append((helper._label(name), helper._format_value(value)))
        except Exception:
            pass
        parent_id = self._parent_id(resource)
        parent = self._work(parent_id)
        if parent is not None:
            rows.append(("Parte de", self._link(self._get_specific_work(parent).title, lambda _e, pid=parent.id: self.select(pid))))
        children = [r for r in self.works if self._parent_id(r) == resource.id]
        if children:
            rows.append(("Partes", ft.Column([self._link(self._get_specific_work(ch).title, lambda _e, cid=ch.id: self.select(cid)) for ch in children], spacing=s(4), tight=True)))
        links = self.context.compilations_by_work.get(resource.id, [])
        rows.append((
            "Compilações",
            ft.Column([self._link(name, lambda _e, cid=cid: self.on_navigate(f"compilacao:{cid}")) for cid, name in links], spacing=s(4), tight=True)
            if links else ui.ui_text(c, "Nenhuma", size=13, color=c.colors["faint"]),
        ))
        rows.append(("Adicionada", format_date(getattr(work, "created_at", None))))
        sections.append(self._section("Propriedades", [ui.props(c, rows, label_width=132)]))

        abstract = getattr(work, "abstract", None)
        if abstract:
            sections.append(self._section("Resumo", [ui.serif_text(c, abstract, size=16, selectable=True)]))
        try:
            synthesis = helper._compose_synthesis_section()
            sections.append(ft.Container(synthesis, padding=ft.Padding.symmetric(horizontal=s(24), vertical=s(16))))
        except Exception:
            pass
        return sections

    def _inspector_fragments(self, fragments: list[dict]) -> list[ft.Control]:
        c = self.config
        if not fragments:
            return [ft.Container(
                ui.empty_state(c, "quote-left", "Nenhum fragmento", "Registre uma citação ou um paráfrase desta obra em Fragmentos.", action=ui.button(c, "Ir para Fragmentos", small=True, on_click=lambda _e: self.on_navigate("Fragmentos"))),
                padding=s(24),
            )]
        out: list[ft.Control] = []
        for record in fragments:
            is_quote = record.get("fragment_type") == "quote"
            excerpt = str(record.get("excerpt") or "")
            text = excerpt if not is_quote or excerpt.strip()[:1] in "“\"«" else f"“{excerpt}”"
            meta = ["Citação" if is_quote else "Paráfrase"]
            if record.get("location_value"):
                meta.append(str(record["location_value"]))
            copy_button = ui.icon_button(c, "copy", style="regular", tooltip="Copiar com citação")
            copy_button.on_click = lambda _e, r=record, t=text: self._copy_fragment(r, t)
            out.append(ft.Container(
                ft.Row(
                    [
                        ft.Column(
                            [
                                ui.meta_text(c, " · ".join(meta)),
                                ui.serif_text(c, text, size=16, max_lines=4) if is_quote else ui.ui_text(c, text, size=13, color=c.colors["muted"], max_lines=4),
                            ],
                            spacing=s(4), expand=True, tight=True,
                        ),
                        copy_button,
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.START,
                ),
                padding=ft.Padding.only(left=s(24), right=s(12), top=s(12), bottom=s(12)),
                border=ft.Border.only(bottom=ft.BorderSide(1, c.colors["border"])),
            ))
        return out

    def _copy_fragment(self, record: dict, text: str) -> None:
        if self.page is None:
            return
        cite = f"({record.get('citation_author', '')}, {record.get('display_year', '')}"
        if record.get("location_value"):
            cite += f", {record['location_value']}"
        cite += ")"

        async def run():
            if self.on_copy_text is not None:
                await self.on_copy_text(f"{text} {cite}")
            else:
                await self.page.clipboard.set(f"{text} {cite}")

        self.page.run_task(run)
        ui.toast(self.page, self.config, "Fragmento copiado com a citação")

    # ── montagem ───────────────────────────────────────────

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
        self.table_host = ft.Container(self._compose_table(), expand=True)
        inspector = self._compose_inspector()
        split = ft.Container(
            ft.Row([self.table_host] + ([inspector] if inspector is not None else []), spacing=0, vertical_alignment=ft.CrossAxisAlignment.STRETCH, expand=True),
            expand=True,
            border=ft.Border.only(top=ft.BorderSide(1, c.colors["border"])),
        )
        return ft.Column([header, self._compose_toolbar(), split], spacing=0, expand=True)

    def compose(self) -> ft.Container:
        self.root = ft.Container(content=self._compose_body(), expand=True, bgcolor=self.config.colors["bg"])
        return self.root

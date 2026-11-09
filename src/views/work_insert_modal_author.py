"""Busca de autores e obra-pai para o modal de inserção."""

from collections.abc import Callable

import flet as ft

from src.contracts import AuthorReference, AuthorSearchResult
from src.utils.types import ViewConfig
from src.views import ui_kit as ui
from src.views.work_insert_modal_fields import DropdownStyle, TextFieldStyle
from src.views.work_insert_specs import (
    MAGAZINE_PARENT_TYPES,
    PARENT_WORK_TYPES,
    WorkTypeSpec,
)


def _safe_update(control: ft.Control | None) -> None:
    """Atualiza o controle se ele já estiver na página."""
    if control is None:
        return
    try:
        control.update()
    except (RuntimeError, AssertionError, AttributeError):
        pass


class AuthorSearchMixin:
    """Agrupa os controles de busca por autores e obras-pai."""

    config: ViewConfig
    page: ft.Page
    selected: WorkTypeSpec
    author_references: list[AuthorReference]
    author_search: str
    author_control: ft.Column | None
    author_search_field: ft.TextField | None
    author_results: ft.Row
    author_pills: ft.Row
    parent_work_search: str
    parent_work_id: int | None
    parent_work_field: ft.TextField | None
    parent_work_results: ft.Column
    search_authors: Callable[[str], list[AuthorSearchResult]] | None
    search_works: Callable[
        [str, str | None], list[tuple[int, str]]
    ] | None
    on_create_parent_work: Callable[
        [Callable[[int, str], None], str | None], None
    ] | None

    def _text_field_style(self) -> TextFieldStyle:
        """Hook de estilo compartilhado com o modal completo."""
        raise NotImplementedError

    def _dropdown_style(self, theme: str | None = "dark") -> DropdownStyle:
        """Hook de estilo compartilhado com o modal completo."""
        raise NotImplementedError

    def _value_changed(self, key: str) -> None:
        """Hook: limpa o erro do campo e atualiza a prévia."""
        raise NotImplementedError

    # ── autores ────────────────────────────────────────────

    def _authors_control(self) -> ft.Control:
        if self.author_control is not None:
            return self.author_control

        c = self.config
        search = ui.input_field(
            c,
            value=self.author_search,
            hint="Nome e sobrenome",
            prefix_icon="magnifying-glass",
            on_change=self._search_author_names,
            on_submit=self._add_author_from_search,
        )
        self.author_search_field = search
        self.author_results = ft.Row(wrap=True, spacing=ui.s(6), run_spacing=ui.s(6))
        self.author_pills = ft.Row(wrap=True, spacing=ui.s(6), run_spacing=ui.s(6))
        search_row = ft.Row(
            controls=[
                search,
                ui.icon_button(
                    c,
                    "user-plus",
                    on_click=self._add_author_from_search,
                    tooltip="Cadastrar novo autor com o nome digitado",
                    boxed=True,
                    size=34,
                ),
            ],
            spacing=ui.s(8),
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        self.author_control = ft.Column(
            controls=[search_row, self.author_results, self.author_pills],
            spacing=ui.s(8),
            tight=True,
        )
        self._refresh_author_search(refresh=False)
        return self.author_control

    def _author_suggestion(self, result: AuthorSearchResult) -> ft.Control:
        return ui.button(
            self.config,
            result["name"],
            on_click=lambda e, result=result: self._select_author(result),
            icon_name="plus",
            small=True,
            tooltip="Adicionar autor já cadastrado",
        )

    def _author_pill(self, reference: AuthorReference) -> ft.Control:
        c = self.config
        label = reference["name"]
        if reference.get("corporation"):
            label = (
                f'{label} ({reference["acronym"]})'
                if reference.get("acronym")
                else label
            )
        return ft.Container(
            content=ft.Row(
                [
                    ui.fa_icon(
                        "building-columns"
                        if reference.get("corporation")
                        else "user",
                        size=ui.s(11),
                        color=c.colors.get("faint", c.colors["muted"]),
                        style="regular",
                    ),
                    ui.ui_text(c, label, size=13),
                    ui.icon_button(
                        c,
                        "xmark",
                        on_click=lambda e, reference=reference: (
                            self._remove_author(reference)
                        ),
                        tooltip="Remover autor",
                        size=22,
                    ),
                ],
                spacing=ui.s(6),
                tight=True,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            height=ui.s(30),
            padding=ft.Padding.only(left=ui.s(10), right=ui.s(4)),
            bgcolor=c.colors.get("selected", c.colors["card_hover"]),
            border=ft.Border.all(1, c.colors.get("border_strong", c.colors["border"])),
            border_radius=ft.BorderRadius.all(ui.s(6)),
        )

    def _search_author_names(self, event) -> None:
        self.author_search = event.control.value or ""
        self._refresh_author_search()

    def _refresh_author_search(self, refresh: bool = True) -> None:
        if self.author_control is None:
            return
        results = (
            self.search_authors(self.author_search)
            if self.author_search and self.search_authors is not None
            else []
        )
        self.author_results.controls = [
            self._author_suggestion(result)
            for result in results
            if not any(
                reference["id"] == result["id"]
                for reference in self.author_references
            )
        ]
        self.author_results.visible = bool(self.author_results.controls)
        self.author_pills.controls = [
            self._author_pill(reference)
            for reference in self.author_references
        ]
        self.author_pills.visible = bool(self.author_pills.controls)
        if refresh:
            _safe_update(self.author_control)

    def _select_author(
        self, result: AuthorSearchResult | AuthorReference | str
    ) -> None:
        if isinstance(result, str):
            reference: AuthorReference = {
                "name": result.strip(),
                "id": None,
                "corporation": False,
                "acronym": None,
                "jurisdiction_id": None,
                "jurisdiction_name": None,
            }
        else:
            reference = {
                "name": result["name"],
                "id": result["id"],
                "corporation": result["corporation"],
                "acronym": result["acronym"],
                "jurisdiction_id": result.get("jurisdiction_id"),
                "jurisdiction_name": result.get("jurisdiction_name"),
            }
        if not any(
            reference["id"] == selected["id"]
            and reference["name"] == selected["name"]
            for selected in self.author_references
        ):
            self.author_references.append(reference)
        self.author_search = ""
        if self.author_search_field is not None:
            self.author_search_field.value = ""
        self._refresh_author_search()
        self._value_changed("authors")

    def _add_author_from_search(self, event) -> None:
        name = self.author_search.strip()
        if name:
            self._show_new_author_dialog(name)

    def _show_new_author_dialog(
        self,
        name: str,
        jurisdiction_callback: Callable[[AuthorReference], None] | None = None,
    ) -> None:
        c = self.config
        acronym = ui.input_field(c, hint="Ex.: IBGE", expand=False)
        acronym_field = ui.form_field(
            c, "Sigla (opcional)", acronym, expand=False
        )
        acronym_field.visible = False

        selected_jurisdiction_id: int | None = None
        selected_jurisdiction_name = ""

        jurisdiction = ui.input_field(
            c,
            hint="Buscar instituição ou órgão responsável",
            prefix_icon="magnifying-glass",
        )
        jurisdiction_row = ft.Row(
            controls=[
                jurisdiction,
                ui.icon_button(
                    c,
                    "plus",
                    tooltip="Cadastrar nova jurisdição",
                    boxed=True,
                    size=34,
                    on_click=lambda event: (
                        self._show_new_author_dialog(
                            jurisdiction.value.strip(),
                            jurisdiction_callback=_bind_jurisdiction,
                        )
                        if jurisdiction.value and jurisdiction.value.strip()
                        else None
                    ),
                ),
            ],
            spacing=ui.s(8),
        )
        jurisdiction_field = ui.form_field(
            c,
            "Jurisdição",
            jurisdiction_row,
            help_text="Ex.: Brasil, para órgãos federais.",
            error_target=jurisdiction,
            expand=False,
        )
        jurisdiction_field.visible = False
        jurisdiction_results = ft.Column(spacing=ui.s(2), visible=False)

        def _bind_jurisdiction(reference: AuthorReference) -> None:
            nonlocal selected_jurisdiction_id, selected_jurisdiction_name
            selected_jurisdiction_id = reference["id"]
            selected_jurisdiction_name = reference["name"]
            jurisdiction.value = reference["name"]
            jurisdiction_results.controls = []
            jurisdiction_results.visible = False
            jurisdiction.update()
            jurisdiction_results.update()

        def refresh_jurisdiction_results() -> None:
            query = (jurisdiction.value or "").strip()
            results = (
                self.search_authors(query)
                if query and self.search_authors is not None
                else []
            )
            jurisdiction_results.controls = [
                ui.hover_surface(
                    c,
                    ui.ui_text(c, result["name"], size=13),
                    on_click=lambda e, result=result: (
                        _bind_jurisdiction({
                            "name": result["name"],
                            "id": result["id"],
                            "corporation": result["corporation"],
                            "acronym": result["acronym"],
                            "jurisdiction_id": None,
                            "jurisdiction_name": None,
                        })
                    ),
                    padding=ft.Padding.symmetric(horizontal=ui.s(8), vertical=ui.s(6)),
                )
                for result in results
            ]
            jurisdiction_results.visible = bool(jurisdiction_results.controls)
            jurisdiction_results.update()

        def change_type(event) -> None:
            is_corporation = author_type.value == "corporation"
            acronym_field.visible = is_corporation
            jurisdiction_field.visible = is_corporation
            if not is_corporation:
                jurisdiction_results.visible = False
            acronym_field.update()
            jurisdiction_field.update()
            jurisdiction_results.update()

        author_type = ui.dropdown_field(
            c,
            (("person", "Pessoa"), ("corporation", "Instituição")),
            value="person",
            on_select=change_type,
        )

        jurisdiction.on_change = lambda e: refresh_jurisdiction_results()

        def confirm(event) -> None:
            reference: AuthorReference = {
                "name": name,
                "id": None,
                "corporation": author_type.value == "corporation",
                "acronym": (
                    acronym.value.strip().upper()
                    if acronym.value and author_type.value == "corporation"
                    else None
                ),
                "jurisdiction_id": (
                    selected_jurisdiction_id
                    if author_type.value == "corporation"
                    else None
                ),
                "jurisdiction_name": (
                    selected_jurisdiction_name or jurisdiction.value.strip()
                    if author_type.value == "corporation"
                    else None
                ),
            }
            if jurisdiction_callback is not None:
                jurisdiction_callback(reference)
            else:
                self._select_author(reference)
            dialog.open = False
            self.page.update()

        dialog = ft.AlertDialog()
        dialog.modal = True
        dialog.bgcolor = c.colors["surface"]
        dialog.shape = ft.RoundedRectangleBorder(radius=ui.s(10))
        dialog.title_padding = ft.Padding.only(
            left=ui.s(24), right=ui.s(24), top=ui.s(20), bottom=ui.s(4)
        )
        dialog.content_padding = ft.Padding.only(
            left=ui.s(24), right=ui.s(24), top=ui.s(12), bottom=ui.s(8)
        )
        dialog.actions_padding = ft.Padding.only(
            left=ui.s(24), right=ui.s(16), top=ui.s(8), bottom=ui.s(16)
        )
        dialog.content = ft.Container(
            content=ft.Column(
                controls=[
                    ui.ui_text(
                        c,
                        f"Como “{name}” deve entrar na referência?",
                        size=13,
                        color=c.colors["muted"],
                        max_lines=3,
                    ),
                    ui.form_field(c, "Tipo de autor", author_type, expand=False),
                    acronym_field,
                    jurisdiction_field,
                    jurisdiction_results,
                ],
                tight=True,
                spacing=ui.s(16),
                width=ui.s(400),
            ),
            animate_size=ft.Animation(180, ft.AnimationCurve.EASE_OUT),
        )
        dialog.title = ui.ui_text(c, "Classificar autor", size=15, weight=ui.W600)
        dialog.actions = [
            ui.button(
                c,
                "Cancelar",
                on_click=lambda event: self._close_author_dialog(dialog),
                variant="ghost",
            ),
            ui.button(
                c,
                "Adicionar",
                on_click=confirm,
                icon_name="check",
                variant="primary",
            ),
        ]
        self.page.show_dialog(dialog)

    def _close_author_dialog(self, dialog: ft.AlertDialog) -> None:
        dialog.open = False
        self.page.update()

    def _remove_author(self, reference: AuthorReference) -> None:
        self.author_references.remove(reference)
        self._refresh_author_search()
        self._value_changed("authors")

    # ── obra-pai ───────────────────────────────────────────

    def _parent_is_magazine(self) -> bool:
        return self.selected.key in MAGAZINE_PARENT_TYPES

    def _parent_work_control(self) -> ft.Control:
        c = self.config
        magazine = self._parent_is_magazine()
        search = ui.input_field(
            c,
            value=self.parent_work_search,
            hint=(
                "Buscar revista pelo nome"
                if magazine
                else "Buscar obra-pai pelo título"
            ),
            prefix_icon="magnifying-glass",
            on_change=self._search_parent_works,
        )
        self.parent_work_field = search
        self.parent_work_results = ft.Column(spacing=ui.s(2), tight=True)
        self._refresh_parent_work_search(refresh=False)
        return ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        search,
                        ui.icon_button(
                            c,
                            "plus",
                            on_click=self._create_parent_work,
                            tooltip="Nova revista" if magazine else "Nova obra-pai",
                            boxed=True,
                            size=34,
                        ),
                    ],
                    spacing=ui.s(8),
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                self.parent_work_results,
            ],
            spacing=ui.s(4),
            tight=True,
        )

    def _search_parent_works(self, event) -> None:
        self.parent_work_search = event.control.value or ""
        self.parent_work_id = None
        self._refresh_parent_work_search()

    def _parent_result_row(self, work_id: int, title: str) -> ft.Control:
        c = self.config
        return ui.hover_surface(
            c,
            ft.Row(
                [
                    ui.fa_icon("link", size=ui.s(11), color=c.colors.get("faint", c.colors["muted"])),
                    ui.ui_text(c, title, size=13, expand=True),
                ],
                spacing=ui.s(8),
            ),
            on_click=lambda e, work_id=work_id, title=title: (
                self._select_parent_work(work_id, title)
            ),
            padding=ft.Padding.symmetric(horizontal=ui.s(8), vertical=ui.s(6)),
        )

    def _refresh_parent_work_search(self, refresh: bool = True) -> None:
        if self.parent_work_results is None:
            return
        results = (
            self.search_works(
                self.parent_work_search,
                PARENT_WORK_TYPES.get(self.selected.key),
            )
            if (
                self.parent_work_search.strip()
                and self.search_works is not None
                and self.parent_work_id is None
            )
            else []
        )
        self.parent_work_results.controls = [
            self._parent_result_row(work_id, title)
            for work_id, title in results
        ]
        self.parent_work_results.visible = bool(results)
        if refresh:
            _safe_update(self.parent_work_results)

    def _select_parent_work(self, work_id: int, title: str) -> None:
        self.parent_work_id = work_id
        self.parent_work_search = title
        if self.parent_work_field is not None:
            self.parent_work_field.value = title
        if self.parent_work_results is not None:
            self.parent_work_results.controls = []
            self.parent_work_results.visible = False
        _safe_update(self.parent_work_field)
        _safe_update(self.parent_work_results)
        self._value_changed("__parent__")

    def _create_parent_work(self, event) -> None:
        """Abre o cadastro de uma obra-pai e a seleciona ao salvá-la."""
        if self.on_create_parent_work is not None:
            self.on_create_parent_work(
                self._select_parent_work,
                PARENT_WORK_TYPES.get(self.selected.key),
            )


__all__ = ["AuthorSearchMixin"]

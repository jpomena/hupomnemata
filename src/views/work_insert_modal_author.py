"""Busca de autores e obra-pai para o modal de inserção."""

from collections.abc import Callable

import flet as ft

from src.contracts import AuthorReference, AuthorSearchResult
from src.utils.types import ViewConfig
from src.views.work_insert_modal_fields import DropdownStyle, TextFieldStyle
from src.views.work_insert_specs import PARENT_WORK_TYPES, WorkTypeSpec


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

    def _authors_control(self) -> ft.Control:
        if self.author_control is not None:
            return self.author_control

        search = ft.TextField(
            hint_text="Buscar autor",
            prefix_icon=ft.Icons.SEARCH,
            value=self.author_search,
            on_change=self._search_author_names,
            expand=True,
            **self._text_field_style(),
        )
        self.author_search_field = search
        self.author_results = ft.Row(wrap=True, spacing=4)
        self.author_pills = ft.Row(wrap=True, spacing=4)
        search_row = ft.Row(
            controls=[
                search,
                ft.IconButton(
                    icon=ft.Icons.ADD,
                    tooltip="Adicionar novo autor",
                    on_click=self._add_author_from_search,
                ),
            ],
            spacing=self.config.ui["control_gap"],
            expand=True,
        )
        self.author_control = ft.Column(
            controls=[
                ft.Container(
                    content=search_row,
                    border_radius=self.config.ui["card_radius"],
                    padding=4,
                    expand=True,
                ),
                self.author_results,
                self.author_pills,
            ],
            spacing=4,
            expand=True,
        )
        self._refresh_author_search(refresh=False)
        return self.author_control

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
            ft.TextButton(
                content=result["name"],
                on_click=lambda e, result=result: self._select_author(result),
            )
            for result in results
            if not any(
                reference["id"] == result["id"]
                for reference in self.author_references
            )
        ]
        self.author_results.visible = bool(self.author_results.controls)
        self.author_pills.controls = [
            ft.Chip(
                label=ft.Text(reference["name"]),
                on_delete=lambda e, reference=reference: (
                    self._remove_author(reference)
                ),
            )
            for reference in self.author_references
        ]
        self.author_pills.visible = bool(self.author_pills.controls)
        if refresh:
            self.author_control.update()

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

    def _add_author_from_search(self, event) -> None:
        name = self.author_search.strip()
        if name:
            self._show_new_author_dialog(name)

    def _show_new_author_dialog(
        self,
        name: str,
        jurisdiction_callback: Callable[[AuthorReference], None] | None = None,
    ) -> None:
        acronym = ft.TextField(
            label="Acrônimo ou sigla (opcional)",
            visible=False,
            **self._text_field_style(),
        )

        selected_jurisdiction_id: int | None = None
        selected_jurisdiction_name = ""

        jurisdiction = ft.TextField(
            label="Jurisdicção",
            hint_text="Buscar instituição / órgão responsável",
            visible=False,
            **self._text_field_style(),
        )
        jurisdiction_row = ft.Row(
            controls=[
                jurisdiction,
                ft.IconButton(
                    icon=ft.Icons.ADD,
                    tooltip="Adicionar nova jurisdição",
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
            spacing=self.config.ui["control_gap"],
            visible=False,
            expand=True,
        )
        jurisdiction_results = ft.Column(spacing=2, visible=False)

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
                ft.TextButton(
                    content=result["name"],
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
                )
                for result in results
            ]
            jurisdiction_results.visible = bool(jurisdiction_results.controls)
            jurisdiction_results.update()

        def change_type(event) -> None:
            is_corporation = author_type.value == "corporation"
            acronym.visible = is_corporation
            jurisdiction.visible = is_corporation
            jurisdiction_row.visible = is_corporation
            if not is_corporation:
                jurisdiction_results.visible = False
            acronym.update()
            jurisdiction.update()
            jurisdiction_row.update()
            jurisdiction_results.update()

        author_type = ft.Dropdown(
            label="Tipo de autor",
            value="person",
            options=[
                ft.dropdown.Option(
                    key="person",
                    text="Pessoa Física",
                    content=ft.Text(
                        value="Pessoa",
                        color=self.config.colors["text"],
                        font_family=self.config.font_families["montserrat"],
                        size=self.config.font_sizes["montserrat_tiny"],
                    ),
                ),
                ft.dropdown.Option(
                    key="corporation",
                    text="Pessoa Jurídica",
                    content=ft.Text(
                        value="Instituição",
                        color=self.config.colors["text"],
                        font_family=self.config.font_families["montserrat"],
                        size=self.config.font_sizes["montserrat_tiny"],
                    ),
                ),
            ],
            on_select=change_type,
        )
        dropdown_style = self._dropdown_style("dark")
        author_type.border_color = dropdown_style.get("border_color")
        author_type.focused_border_color = dropdown_style.get(
            "focused_border_color"
        )
        author_type.color = dropdown_style.get("color")
        author_type.label_style = dropdown_style.get("label_style")
        author_type.border_radius = dropdown_style.get("border_radius")
        author_type.content_padding = dropdown_style.get("content_padding")
        author_type.bgcolor = dropdown_style.get("bgcolor")
        border_width = dropdown_style.get("border_width")
        if border_width is not None:
            author_type.border_width = border_width
        author_type.text_style = dropdown_style.get("text_style")

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
        dialog.bgcolor = self.config.colors["surface"]
        dialog.content = ft.Container(
            content=ft.Column(
                controls=[
                    author_type,
                    acronym,
                    jurisdiction_row,
                    jurisdiction_results,
                ],
                tight=True,
                width=360,
                height=200,
            ),
            animate=ft.Animation(180, ft.AnimationCurve.EASE_OUT),
        )
        dialog.title = ft.Text(
            "Classificar autor",
            color=self.config.colors["text"],
            font_family=self.config.font_families["cormorant"],
            weight=self.config.font_weights["cormorant_bold"],
        )
        dialog.actions = [
            ft.TextButton(
                content=ft.Text(
                    "Cancelar",
                    color=self.config.colors["text"],
                    font_family=self.config.font_families["montserrat"],
                ),
                on_click=lambda event: self._close_author_dialog(dialog),
            ),
            ft.ElevatedButton(
                content=ft.Text(
                    "Adicionar",
                    color=self.config.colors["bg"],
                    font_family=self.config.font_families["montserrat"],
                ),
                on_click=confirm,
                bgcolor=self.config.colors["gold"],
            ),
        ]
        self.page.show_dialog(dialog)

    def _close_author_dialog(self, dialog: ft.AlertDialog) -> None:
        dialog.open = False
        self.page.update()

    def _parent_work_control(self) -> ft.Control:
        search = ft.TextField(
            hint_text=(
                "Buscar revista pelo nome"
                if self.selected.key
                in {'journal_article', 'periodical_collection'}
                else "Buscar obra-pai pelo título"
            ),
            prefix_icon=ft.Icons.SEARCH,
            value=self.parent_work_search,
            on_change=self._search_parent_works,
            expand=True,
            **self._text_field_style(),
        )
        self.parent_work_field = search
        self.parent_work_results = ft.Column(spacing=2)
        self._refresh_parent_work_search(refresh=False)
        return ft.Column(
            controls=[search, self.parent_work_results],
            spacing=4,
            expand=True,
        )

    def _search_parent_works(self, event) -> None:
        self.parent_work_search = event.control.value or ""
        self.parent_work_id = None
        self._refresh_parent_work_search()

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
            )
            else []
        )
        self.parent_work_results.controls = [
            ft.TextButton(
                content=title,
                on_click=lambda e, work_id=work_id, title=title: (
                    self._select_parent_work(work_id, title)
                ),
            )
            for work_id, title in results
        ]
        self.parent_work_results.visible = bool(results)
        if refresh:
            self.parent_work_results.update()

    def _select_parent_work(self, work_id: int, title: str) -> None:
        self.parent_work_id = work_id
        self.parent_work_search = title
        if self.parent_work_field is not None:
            self.parent_work_field.value = title
        if self.parent_work_results is not None:
            self.parent_work_results.controls = []
            self.parent_work_results.visible = False
        if self.parent_work_field is not None:
            self.parent_work_field.update()
        if self.parent_work_results is not None:
            self.parent_work_results.update()

    def _create_parent_work(self, event) -> None:
        """Abre o cadastro de uma obra-pai e a seleciona ao salvá-la."""
        if self.on_create_parent_work is not None:
            self.on_create_parent_work(
                self._select_parent_work,
                PARENT_WORK_TYPES.get(self.selected.key),
            )

    def _remove_author(self, reference: AuthorReference) -> None:
        self.author_references.remove(reference)
        self._refresh_author_search()


__all__ = ["AuthorSearchMixin"]

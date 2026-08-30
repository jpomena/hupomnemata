"""Composer stateful do diálogo de inserção de obras."""

from collections.abc import Callable
from typing import TypedDict

import flet as ft

from src.repositories.work_repository import (
    AuthorReference, AuthorSearchResult
)
from src.utils.types import ViewConfig
from src.views.work_insert_modal_author import AuthorSearchMixin
from src.views.work_insert_modal_fields import FieldBuilderMixin
from src.views.work_insert_modal_render import RenderMixin
from src.views.work_insert_specs import WORK_TYPES, WorkTypeSpec


class DropdownStyle(TypedDict):
    border_color: str
    focused_border_color: str
    color: str
    label_style: ft.TextStyle
    border_radius: int | float
    content_padding: int | float
    bgcolor: str
    border_width: int | float
    text_style: ft.TextStyle


class WorkInsertModalComposer(
    FieldBuilderMixin,
    AuthorSearchMixin,
    RenderMixin,
):
    """Orquestra a montagem do modal e o estado do formulário."""

    def __init__(
        self,
        page: ft.Page,
        config: ViewConfig,
        on_save: Callable[[dict[str, object]], bool],
        search_authors: Callable[[str], list[AuthorSearchResult]] | None = None,  # noqa: E501
        search_works: Callable[[str], list[tuple[int, str]]] | None = None,
        on_create_parent_work: Callable[
            [Callable[[int, str], None], str | None], None
        ] | None = None,
        initial_work_type: str | None = None,
        parent_mode: bool = False,
    ):
        self.page = page
        self.config = config
        self.on_save = on_save
        self.search_authors = search_authors
        self.search_works = search_works
        self.on_create_parent_work: Callable[
            [Callable[[int, str], None], str | None], None
        ] | None = on_create_parent_work
        self.parent_mode = parent_mode
        self.selected: WorkTypeSpec = next(
            (spec for spec in WORK_TYPES if spec.key == initial_work_type),
            WORK_TYPES[0],
        )
        self.fields: dict[str, ft.Control] = {}
        self.partial_enabled = False
        self.author_references: list[AuthorReference] = []
        self.author_search = ""
        self.author_control: ft.Column | None = None
        self.author_search_field: ft.TextField | None = None
        self.author_results: ft.Row | None = None
        self.author_pills: ft.Row | None = None
        self.parent_work_search = ""
        self.parent_work_id: int | None = None
        self.parent_work_field: ft.TextField | None = None
        self.parent_work_results: ft.Column | None = None
        self.stored_values: dict[str, object] = {}
        self.type_grid = ft.GridView(
            runs_count=3,
            spacing=self.config.ui["control_gap"] - 4,
            run_spacing=self.config.ui["control_gap"] - 4,
            expand=True,
        )
        self.form = ft.Column(
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            spacing=self.config.ui["modal_gap"],
        )
        self.modal: ft.AlertDialog | None = None

    def _type_card(
        self,
        spec,
        selected: bool,
        on_select: Callable[[], None],
    ) -> ft.Container:
        """Cria um cartão para selecionar o tipo de obra."""
        icon = ft.Icon(
            spec.icon,
            size=36,
            color=self.config.colors["gold"],
            align=ft.Alignment.CENTER,
        )
        card = ft.Container(
            content=ft.Column(
                controls=[
                    icon,
                    ft.Text(
                        value=spec.label,
                        size=self.config.font_sizes["montserrat_tiny"],
                        color=self.config.colors["text"],
                        font_family=self.config.font_families["montserrat"],
                        weight=self.config.font_weights["montserrat_semibold"],
                        text_align=ft.TextAlign.CENTER,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=6,
            ),
            width=120,
            height=260,
            padding=8,
            bgcolor=(
                self.config.colors["card_hover"]
                if selected
                else self.config.colors["surface"]
            ),
            border=ft.Border.all(
                2 if selected else 1,
                self.config.colors["gold"]
                if selected
                else self.config.colors["border"],
            ),
            border_radius=self.config.ui["card_radius"],
            on_click=lambda e: on_select(),
            animate=ft.Animation(
                int(self.config.ui["animation_ms"]),
                ft.AnimationCurve.EASE_OUT,
            ),
        )

        def handle_hover(e: ft.Event[ft.Container]):
            if e.data:
                card.bgcolor = self.config.colors["card_hover"]
                card.border = ft.Border()
                card.border.left = ft.BorderSide(
                    1, self.config.colors["text"]
                )
                card.border.top = ft.BorderSide(
                    1, self.config.colors["text"]
                )
                card.border.right = ft.BorderSide(
                    1, self.config.colors["text"]
                )
                card.border.bottom = ft.BorderSide(
                    4, self.config.colors["text"]
                )
                icon.color = self.config.colors["text"]
            else:
                card.bgcolor = (
                    self.config.colors["card_hover"]
                    if selected
                    else self.config.colors["surface"]
                )
                card.border = ft.Border.all(
                    2 if selected else 1,
                    self.config.colors["gold"]
                    if selected
                    else self.config.colors["border"],
                )
                icon.color = self.config.colors["gold"]
            card.update()

        card.on_hover = handle_hover
        return card

    def _collect(self) -> dict[str, object]:
        """Converte os controles atuais em dados do formulário."""
        data: dict[str, object] = {"work_type": self.selected.key}
        for key, control in self.fields.items():
            if key == "authors":
                data[key] = list(self.author_references)
                continue
            if isinstance(control, ft.Checkbox):
                data[key] = control.value
            elif isinstance(control, ft.Row):
                responsibility_key = getattr(
                    control.controls[0], "value", ""
                ).strip()
                responsibility_names = getattr(
                    control.controls[1], "value", ""
                ).strip()
                data[key] = (
                    {responsibility_key: responsibility_names}
                    if responsibility_key and responsibility_names
                    else {}
                )
            else:
                data[key] = getattr(control, "value", "") or ""
        data["parent_bibliographic_resource_id"] = self.parent_work_id
        return data

    def _toggle_partial(self, event) -> None:
        """Alterna campos parciais preservando valores preenchidos."""
        self.partial_enabled = bool(event.control.value)
        if not self.partial_enabled:
            self.parent_work_search = ""
            self.parent_work_id = None
        self._render()

    def _choose(self, spec) -> None:
        """Seleciona tipo de obra e reinicia estado do formulário."""
        self.selected = spec
        self.partial_enabled = False
        self.author_references.clear()
        self.author_search = ""
        self.author_control = None
        self.author_search_field = None
        self.author_results = None
        self.author_pills = None
        self.parent_work_search = ""
        self.parent_work_id = None
        self.parent_work_field = None
        self.parent_work_results = None
        if self.author_search_field is not None:
            self.author_search_field.value = ""
        self._refresh_author_search()
        self.stored_values.clear()
        self._render()

    def _reset(self) -> None:
        """Reseta formulário e estado do modal."""
        self.selected = WORK_TYPES[0]
        self.partial_enabled = False
        self.author_references.clear()
        self.author_control = None
        self.author_search_field = None
        self.author_results = None
        self.author_pills = None
        self.parent_work_search = ""
        self.parent_work_id = None
        self.parent_work_field = None
        self.parent_work_results = None
        self.stored_values.clear()
        self.fields.clear()
        self._render(update_page=False)

    def _close(self, event) -> None:
        """Fecha o diálogo sem persistir dados."""
        self._reset()
        if self.modal is not None:
            self.modal.open = False
            self.page.update()

    def _save(self, event) -> None:
        """Envia os dados ao controller e fecha o modal."""
        if self.on_save(self._collect()) and self.modal is not None:
            self._reset()
            self.modal.open = False
            self.page.update()

    def compose(self) -> ft.AlertDialog:
        """Montagem final do modal em tela."""
        modal_title = (
            "Cadastrar nova obra-pai"
            if self.parent_mode
            else "Cadastrar nova obra".title()
        )
        type_panel = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        value=(
                            "Tipo da obra-pai"
                            if self.parent_mode
                            else "Tipo de obra"
                        ),
                        size=self.config.font_sizes["montserrat_large"],
                        color=self.config.colors["muted"],
                        font_family=(
                            self.config.font_families["montserrat"]
                        ),
                        weight=(
                            self.config.font_weights["montserrat_semibold"]
                        ),
                    ),
                    (
                        ft.Text(
                            value=f"{self.selected.label}",
                            size=self.config.font_sizes["montserrat_small"],
                            color=self.config.colors["gold"],
                            font_family=(
                                self.config.font_families["montserrat"]
                            ),
                            weight=(
                                self.config.font_weights[
                                    "montserrat_semibold"
                                ]
                            ),
                        )
                        if self.parent_mode
                        else self.type_grid
                    ),
                ],
                spacing=self.config.ui["modal_gap"],
                expand=True,
            ),
            width=(
                self.config.ui["modal_type_panel_width"]
                if not self.parent_mode
                else None
            ),
            expand=False,
        )
        row_controls: list[ft.Control] = [type_panel]
        if not self.parent_mode:
            row_controls.append(
                ft.VerticalDivider(
                    width=1,
                    color=self.config.colors["border"],
                )
            )
        row_controls.append(ft.Container(content=self.form, expand=True))

        modal_width = (
            int(self.config.ui["modal_width"] * 0.7)
            if self.parent_mode
            else self.config.ui["modal_width"]
        )
        modal_height = (
            int(self.config.ui["modal_height"] * 0.7)
            if self.parent_mode
            else self.config.ui["modal_height"]
        )

        modal_content = ft.Column(
            controls=[
                ft.Text(
                    value=modal_title,
                    size=self.config.font_sizes["cormorant_large"],
                    color=self.config.colors["text"],
                    font_family=self.config.font_families["cormorant"],
                    weight=self.config.font_weights["cormorant_bold"],
                ),
                ft.Row(
                    controls=row_controls,
                    spacing=self.config.ui["control_gap"] + 6,
                    expand=True,
                    vertical_alignment=ft.CrossAxisAlignment.STRETCH,
                ),
            ],
            width=modal_width,
            height=modal_height,
            spacing=self.config.ui["modal_gap"],
        )

        dialog_wrapper = ft.Container(content=modal_content)

        cancel_button = ft.TextButton(
            content=ft.Text(
                value="Cancelar",
                font_family=self.config.font_families["montserrat"],
                color=self.config.colors["text"],
            ),
            on_click=self._close,
            style=ft.ButtonStyle(
                color=self.config.colors["text"],
            ),
        )
        save_button = ft.ElevatedButton(
            content=ft.Text(
                value="Salvar acervo",
                font_family=self.config.font_families["montserrat"],
            ),
            on_click=self._save,
            bgcolor=self.config.colors["gold"],
            color=self.config.colors["surface"],
        )
        action_controls: list[ft.Control] = [cancel_button, save_button]

        self.modal = ft.AlertDialog(
            modal=False,
            bgcolor=self.config.colors["surface"],
            on_dismiss=self._close,
            shape=ft.RoundedRectangleBorder(radius=8),
            content_padding=self.config.ui["modal_content_padding"],
            content=dialog_wrapper,
            actions=action_controls,
        )
        self._render()
        return self.modal

"""Helpers de construção dos campos do modal de cadastro."""

import re
from collections.abc import Callable
from typing import Protocol, cast

import flet as ft

from src.contracts import AuthorReference, AuthorSearchResult
from src.utils.types import ViewConfig
from src.utils.view_styles import (
    DropdownStyle,
    TextFieldStyle,
    dropdown_style,
    text_field_base_style,
    text_field_style,
)
from src.views.work_insert_specs import FieldSpec, WorkTypeSpec


class SupportsAuthorsControl(Protocol):
    """Contrato para os mixins que expõem o controle de autores."""

    def _authors_control(self) -> ft.Control:
        """Cria o controle de busca de autores."""
        ...


class FieldBuilderMixin:
    """Métodos para criar e formatar controles do formulário."""

    config: ViewConfig
    page: ft.Page
    selected: WorkTypeSpec
    fields: dict[str, ft.Control]
    partial_enabled: bool
    stored_values: dict[str, object]
    author_references: list[AuthorReference]
    author_search: str
    author_control: ft.Column | None
    author_search_field: ft.TextField | None
    author_results: ft.Row | None
    author_pills: ft.Row | None
    parent_work_search: str
    parent_work_id: int | None
    parent_work_field: ft.TextField | None
    parent_work_results: ft.Column | None
    search_authors: Callable[[str], list[AuthorSearchResult]] | None
    search_works: Callable[
        [str, str | None], list[tuple[int, str]]
    ] | None
    on_create_parent_work: Callable[
        [Callable[[int, str], None], str | None], None
    ] | None
    type_grid: ft.GridView
    form: ft.Column
    modal: ft.AlertDialog | None

    def _style(self) -> TextFieldStyle:
        """Retorna o estilo compartilhado pelos campos do formulário."""
        return text_field_base_style(self.config)

    def _dropdown_style(self, theme: str | None = "dark") -> DropdownStyle:
        """Retorna o estilo dos menus suspensos."""
        return dropdown_style(self.config, theme)

    def _text_field_style(self) -> TextFieldStyle:
        """Retorna a tipografia e as cores dos campos de texto."""
        style = self._style()
        return {**style, **text_field_style(self.config)}

    def _field(
        self,
        spec: FieldSpec,
        initial_value: object = "",
        on_change=None,
    ) -> ft.Control:
        """Cria o controle correspondente a uma especificação de campo."""
        if spec.key == "authors":
            return cast(SupportsAuthorsControl, self)._authors_control()
        if spec.kind == "responsibilities":
            data = initial_value if isinstance(initial_value, dict) else {}
            if self.selected.key in {
                "audio_document",
                "audiovisual_document",
            }:
                role_hint = (
                    "Ex.: direção, produção"
                    if self.selected.key == "audiovisual_document"
                    else (
                        "Ex.: entrevistado, entrevistador"
                        if spec.key == "responsibilities"
                        else "Ex.: intérprete, compositor"
                    )
                )
                controls: list[ft.Control] = []
                controls.extend(
                    self._audio_responsibility_row(
                        role,
                        names,
                        role_hint,
                    )
                    for role, names in data.items()
                )
                if not controls:
                    controls.append(
                        self._audio_responsibility_row(
                            role_hint=role_hint,
                        )
                    )
                fields = ft.Column(
                    controls=controls,
                    spacing=self.config.ui["control_gap"],
                )

                def add_responsibility(
                    event: ft.Event[ft.IconButton],
                ) -> None:
                    del event
                    fields.controls.append(
                        self._audio_responsibility_row(
                            role_hint=role_hint,
                        )
                    )
                    fields.update()

                fields.controls.append(
                    ft.IconButton(
                        icon=ft.Icons.ADD,
                        tooltip="Adicionar responsabilidade",
                        on_click=add_responsibility,
                    )
                )
                return fields
            responsibility_key, responsibility_names = next(
                iter(data.items()), ("", "")
            )
            return ft.Row(
                controls=[
                    ft.TextField(
                        label="Tipo de responsabilidade",
                        hint_text="Ex.: autor, editor, tradutor",
                        value=responsibility_key,
                        expand=True,
                        **self._text_field_style(),
                    ),
                    ft.TextField(
                        label="Pessoa ou entidade",
                        hint_text="Nomes das pessoas ou entidades",
                        value=responsibility_names,
                        expand=True,
                        **self._text_field_style(),
                    ),
                ],
                spacing=self.config.ui["control_gap"],
            )
        if spec.kind == "checkbox":
            checkbox = ft.Checkbox(
                label=spec.label,
                border_side={
                    ft.ControlState.HOVERED: ft.BorderSide(
                        width=2,
                        color=self.config.colors['text']
                    ),
                    ft.ControlState.DEFAULT: ft.BorderSide(
                        width=2,
                        color=self.config.colors["muted"]
                    ),
                },
                label_position=ft.LabelPosition.LEFT,
                value=(
                    initial_value if isinstance(initial_value, bool) else False
                ),
                on_change=on_change,
                label_style=ft.TextStyle(
                    size=12,
                    weight=self.config.font_weights["montserrat_normal"],
                    color=self.config.colors["text"],
                    font_family=self.config.font_families["montserrat"],
                ),
            )
            return checkbox
        if spec.kind == "dropdown":
            selected_value = (
                initial_value
                if isinstance(initial_value, str) and initial_value
                else "Data exata"
            )
            return ft.Dropdown(
                label=spec.label,
                value=selected_value,
                options=[
                    ft.dropdown.Option(
                        key=value,
                        text=value,
                        content=ft.Text(
                            value=value,
                            weight=(
                                self.config.font_weights["montserrat_normal"]
                            ),
                            style=ft.TextStyle(letter_spacing=2),
                            font_family=(
                                self.config.font_families["montserrat"]
                            ),
                            size=self.config.font_sizes["montserrat_tiny"],
                        ),
                    )
                    for value in (
                        "Data exata",
                        "Década",
                        "Século",
                        "Milênio",
                        "Data desconhecida",
                    )
                ],
                **self._dropdown_style(),
            )

        common_args = {
            "label": spec.label + (" *" if spec.required else ""),
            "hint_text": (
                "DD/MM/AAAA"
                if spec.kind == "date"
                else (
                    "MM/AAAA"
                    if spec.kind == "month"
                    else spec.hint if spec.hint else spec.label
                )
            ),
            "multiline": spec.kind == "multiline",
            "min_lines": 3 if spec.kind == "multiline" else 1,
            "expand": True,
            "value": initial_value if isinstance(initial_value, str) else "",
        }
        if spec.kind == "date":
            common_args["on_change"] = self._format_date_input
        elif spec.kind == "month":
            common_args["on_change"] = self._format_month_input
        elif spec.key == "issn":
            common_args["on_change"] = self._format_issn_input
        elif spec.key == "isbn":
            common_args["on_change"] = self._format_isbn_input
        if spec.kind == "number":
            return ft.TextField(
                **common_args,
                keyboard_type=ft.KeyboardType.NUMBER,
                input_filter=ft.NumbersOnlyInputFilter(),
                **self._text_field_style(),
            )
        return ft.TextField(
            **common_args,
            **self._text_field_style(),
        )

    def _audio_responsibility_row(
        self,
        role: str = "",
        names: str = "",
        role_hint: str = "Ex.: entrevistado, entrevistador",
    ) -> ft.Row:
        return ft.Row(
            controls=[
                ft.TextField(
                    label="Tipo de responsabilidade",
                    hint_text=role_hint,
                    value=role,
                    expand=True,
                    **self._text_field_style(),
                ),
                ft.TextField(
                    label="Pessoa ou entidade",
                    hint_text="Nomes das pessoas ou entidades",
                    value=names,
                    expand=True,
                    **self._text_field_style(),
                ),
            ],
            spacing=self.config.ui["control_gap"],
        )

    @staticmethod
    def _format_digits(value: object, groups: tuple[int, ...]) -> str:
        digits = re.sub(r"\D", "", str(value))
        position = 0
        parts = []
        for group_size in groups:
            part = digits[position:position + group_size]
            if not part:
                break
            parts.append(part)
            position += group_size
        return "/".join(parts) if groups == (2, 2, 4) else "-".join(parts)

    def _format_date_input(self, event) -> None:
        event.control.value = self._format_digits(
            event.control.value, (2, 2, 4)
        )
        event.control.update()

    def _format_month_input(self, event) -> None:
        event.control.value = self._format_digits(
            event.control.value, (2, 4)
        )
        event.control.update()

    def _format_issn_input(self, event) -> None:
        event.control.value = self._format_digits(event.control.value, (4, 4))
        event.control.update()

    def _format_isbn_input(self, event) -> None:
        event.control.value = self._format_digits(
            event.control.value, (3, 2, 4, 3, 1)
        )
        event.control.update()


__all__ = ["FieldBuilderMixin"]

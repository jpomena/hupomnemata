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
from src.views import ui_kit as ui
from src.views.work_insert_specs import FieldSpec, WorkTypeSpec

DATE_PRECISION_OPTIONS = (
    "Data exata",
    "Década",
    "Século",
    "Milênio",
    "Data desconhecida",
)


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
    form: ft.Column
    modal: ft.AlertDialog | None

    def _value_changed(self, key: str) -> None:
        """Hook: limpa o erro do campo e atualiza a prévia."""
        raise NotImplementedError

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

    def _change_handler(
        self,
        key: str,
        formatter: Callable[[ft.Event], None] | None = None,
    ) -> Callable[[ft.Event], None]:
        """Encadeia a máscara do campo (se houver) com a prévia ao vivo."""

        def handle(event) -> None:
            if formatter is not None:
                formatter(event)
            self._value_changed(key)

        return handle

    def _field(
        self,
        spec: FieldSpec,
        initial_value: object = "",
        on_change=None,
    ) -> ft.Control:
        """Cria o controle correspondente a uma especificação de campo."""
        c = self.config
        if spec.key == "authors":
            return cast(SupportsAuthorsControl, self)._authors_control()
        if spec.kind == "responsibilities":
            return self._responsibilities_control(spec, initial_value)
        if spec.kind == "checkbox":
            return ui.checkbox(
                c,
                spec.label,
                value=(
                    initial_value if isinstance(initial_value, bool) else False
                ),
                on_change=on_change or self._change_handler(spec.key),
            )
        if spec.kind == "dropdown":
            selected_value = (
                initial_value
                if isinstance(initial_value, str) and initial_value
                else "Data exata"
            )
            return ui.dropdown_field(
                c,
                DATE_PRECISION_OPTIONS,
                value=selected_value,
                on_select=on_change or self._change_handler(spec.key),
            )

        formatter: Callable[[ft.Event], None] | None = None
        if spec.kind == "date":
            formatter = self._format_date_input
        elif spec.kind == "month":
            formatter = self._format_month_input
        elif spec.key == "issn":
            formatter = self._format_issn_input
        elif spec.key == "isbn":
            formatter = self._format_isbn_input
        hint = (
            "DD/MM/AAAA"
            if spec.kind == "date"
            else "MM/AAAA"
            if spec.kind == "month"
            else spec.hint or None
        )
        is_number = spec.kind == "number"
        return ui.input_field(
            c,
            value=initial_value if isinstance(initial_value, str) else "",
            hint=hint,
            on_change=on_change or self._change_handler(spec.key, formatter),
            multiline=spec.kind == "multiline",
            min_lines=3 if spec.kind == "multiline" else 1,
            max_lines=8 if spec.kind == "multiline" else None,
            keyboard_type=ft.KeyboardType.NUMBER if is_number else None,
            input_filter=ft.NumbersOnlyInputFilter() if is_number else None,
            autofocus=spec.key == "title" and getattr(self, "focus_title", True),
            expand=False,
        )

    def _role_hint(self, spec: FieldSpec) -> str:
        if self.selected.key == "audiovisual_document":
            return "Função, ex.: direção, produção"
        if self.selected.key == "audio_document":
            if spec.key == "responsibilities":
                return "Função, ex.: entrevistado, entrevistador"
            return "Função, ex.: intérprete, compositor"
        return "Função, ex.: editor, tradutor"

    def _responsibilities_control(
        self,
        spec: FieldSpec,
        initial_value: object,
    ) -> ft.Control:
        """Linhas "função + nomes". Áudio e audiovisual aceitam várias."""
        data = initial_value if isinstance(initial_value, dict) else {}
        role_hint = self._role_hint(spec)
        if self.selected.key not in {
            "audio_document",
            "audiovisual_document",
        }:
            role, names = next(iter(data.items()), ("", ""))
            return self._audio_responsibility_row(
                role, names, role_hint, key=spec.key
            )

        controls: list[ft.Control] = [
            self._audio_responsibility_row(
                role, names, role_hint, key=spec.key
            )
            for role, names in data.items()
        ]
        if not controls:
            controls.append(
                self._audio_responsibility_row(
                    role_hint=role_hint, key=spec.key
                )
            )
        fields = ft.Column(controls=controls, spacing=ui.s(8))

        def add_responsibility(event) -> None:
            del event
            fields.controls.insert(
                len(fields.controls) - 1,
                self._audio_responsibility_row(
                    role_hint=role_hint, key=spec.key
                ),
            )
            fields.update()

        fields.controls.append(
            ui.button(
                self.config,
                "Adicionar responsabilidade",
                on_click=add_responsibility,
                icon_name="plus",
                variant="ghost",
                small=True,
            )
        )
        return fields

    def _audio_responsibility_row(
        self,
        role: str = "",
        names: str = "",
        role_hint: str = "Função, ex.: entrevistado, entrevistador",
        key: str = "responsibilities",
    ) -> ft.Row:
        handler = self._change_handler(key)
        return ft.Row(
            controls=[
                ui.input_field(
                    self.config,
                    value=role,
                    hint=role_hint,
                    on_change=handler,
                ),
                ui.input_field(
                    self.config,
                    value=names,
                    hint="Pessoa ou entidade",
                    on_change=handler,
                ),
            ],
            spacing=ui.s(16),
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
        digits = re.sub(r"\D", "", str(event.control.value))
        event.control.value = "/".join(
            part for part in (digits[:2], digits[2:6]) if part
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


__all__ = ["FieldBuilderMixin", "DATE_PRECISION_OPTIONS"]

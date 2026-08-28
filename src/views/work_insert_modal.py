"""Composer stateful do dialogo de insercao de obras."""

from collections.abc import Callable
import re
from typing import TypedDict, cast

import flet as ft

from src.views.work_insert_specs import (
    DEFAULTED_FIELDS,
    PARTIAL,
    WORK_TYPES,
    FieldSpec,
)
from src.utils.types import ViewConfig
from src.repositories.work_repository import (
    AuthorReference,
    AuthorSearchResult,
)


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


class WorkInsertModalComposer:
    """Constroi o modal e administra seu estado visual."""

    def __init__(
        self,
        page: ft.Page,
        config: ViewConfig,
        on_save: Callable[[dict[str, object]], bool],
        search_authors: (
            Callable[[str], list[AuthorSearchResult]] | None
        ) = None,
        search_works: Callable[[str], list[tuple[int, str]]] | None = None,
        on_create_parent_work: Callable[
            [Callable[[int, str], None]], None
        ] | None = None,
    ):
        self.page = page
        self.config = config
        self.on_save = on_save
        self.search_authors = search_authors
        self.search_works = search_works
        self.on_create_parent_work = on_create_parent_work
        self.selected = WORK_TYPES[0]
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

    def _style(self):
        """Retorna o estilo compartilhado pelos campos do formulario."""
        return {
            "border_color": self.config.colors["border"],
            "focused_border_color": self.config.colors["gold"],
            "cursor_color": self.config.colors["gold"],
            "color": self.config.colors["text"],
            "label_style": ft.TextStyle(
                color=self.config.colors["muted"],
                weight=self.config.font_weights["montserrat_normal"],
                font_family=self.config.font_families["montserrat"],
                letter_spacing=2,
                size=12
            ),
            "border_radius": self.config.ui["card_radius"],
            "content_padding": self.config.ui["card_padding"],
            "bgcolor": self.config.colors["surface"],
            "border_width": 2
        }

    def _dropdown_style(
        self, theme: str | None = "dark"
    ) -> DropdownStyle:
        """Retorna o estilo dos menus suspensos."""
        text_color = (
            self.config.colors["black"]
            if theme == "light"
            else self.config.colors["muted"]
        )
        text_style = ft.TextStyle(
            color=text_color,
            weight=self.config.font_weights["montserrat_normal"],
            font_family=self.config.font_families["montserrat"],
            letter_spacing=2,
            size=12
        )
        label_style = ft.TextStyle(
            color=text_color,
            weight=self.config.font_weights["montserrat_normal"],
            font_family=self.config.font_families["montserrat"],
            letter_spacing=2,
            size=12
        )
        return {
            "border_color": self.config.colors["border"],
            "focused_border_color": self.config.colors["gold"],
            "color": self.config.colors["text"],
            "label_style": label_style,
            "border_radius": self.config.ui["card_radius"],
            "content_padding": self.config.ui["card_padding"],
            "bgcolor": self.config.colors["surface"],
            "border_width": 2,
            "text_style": text_style,
        }

    def _text_field_style(self):
        """Retorna a tipografia e as cores dos campos de texto."""
        style = self._style()
        style["text_style"] = ft.TextStyle(
            color=self.config.colors["text"],
            size=self.config.font_sizes["cormorant_small"],
            weight=self.config.font_weights["cormorant_semibold"],
            font_family=self.config.font_families["cormorant"],
        )
        style["hint_style"] = ft.TextStyle(
            color=self.config.colors["muted"],
            weight=self.config.font_weights["montserrat_normal"],
            font_family=self.config.font_families["montserrat"],
            letter_spacing=2,
            size=12
        )
        return style

    def _field(
        self,
        spec: FieldSpec,
        initial_value: object = "",
        on_change: Callable | None = None,
    ) -> ft.Control:
        """Cria o controle correspondente a uma especificacao de campo."""
        if spec.key == "authors":
            return self._authors_control()
        if spec.kind == "responsabilities":
            data = initial_value if isinstance(initial_value, dict) else {}
            responsibility_key, responsibility_names = next(
                iter(data.items()), ("", "")
            )
            return ft.Row(
                controls=[
                    ft.TextField(
                        label="Tipo de responsabilidade",
                        hint_text="Ex.: Coord.",
                        value=responsibility_key,
                        expand=True,
                        **self._text_field_style(),
                    ),
                    ft.TextField(
                        label="Nomes",
                        hint_text="Nomes das pessoas ou entidades",
                        value=responsibility_names,
                        expand=True,
                        **self._text_field_style(),
                    ),
                ],
                spacing=self.config.ui["control_gap"],
            )
        if spec.kind == "checkbox":
            return ft.Checkbox(
                label=spec.label,
                value=(
                    initial_value
                    if isinstance(initial_value, bool)
                    else False
                ),
                on_change=on_change,
                label_style=ft.TextStyle(
                    size=12,
                    weight=self.config.font_weights["montserrat_normal"],
                    color=self.config.colors["text"],
                    font_family=self.config.font_families["montserrat"],
                ),
            )
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
                        key=value, text=value,
                        content=ft.Text(
                            value=value,
                            weight=self.config.font_weights[
                                "montserrat_normal"
                            ],
                            style=ft.TextStyle(letter_spacing=2),
                            font_family=self.config.font_families[
                                "montserrat"
                            ],
                            size=self.config.font_sizes["montserrat_tiny"]
                        )
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
                "DD/MM/AAAA" if spec.kind == "date"
                else spec.hint if spec.hint else spec.label
            ),
            "multiline": spec.kind == "multiline",
            "min_lines": 3 if spec.kind == "multiline" else 1,
            "expand": True,
            "value": initial_value if isinstance(initial_value, str) else "",
        }
        if spec.kind == "date":
            common_args["on_change"] = self._format_date_input
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
        self.author_control = ft.Column(
            controls=[
                ft.Container(
                    content=ft.Row(
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
                    ),
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
        if (
            self.author_control is None
            or self.author_results is None
            or self.author_pills is None
        ):
            return
        results = (
            self.search_authors(self.author_search)
            if self.author_search and self.search_authors is not None
            else []
        )
        self.author_results.controls = [
            ft.TextButton(
                content=result['name'],
                on_click=lambda e, result=result: self._select_author(result),
            )
            for result in results
            if not any(
                reference['id'] == result['id']
                for reference in self.author_references
            )
        ]
        self.author_results.visible = bool(self.author_results.controls)
        self.author_pills.controls = [
            ft.Chip(
                label=ft.Text(reference['name']),
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
                'name': result.strip(),
                'id': None,
                'corporation': False,
                'acronym': None,
            }
        else:
            reference = {
                'name': result['name'],
                'id': result['id'],
                'corporation': result['corporation'],
                'acronym': result['acronym'],
            }
        if not any(
            reference['id'] == selected['id']
            and reference['name'] == selected['name']
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

    def _show_new_author_dialog(self, name: str) -> None:
        acronym = ft.TextField(
            label="Acrônimo ou sigla (opcional)",
            visible=False,
            **self._text_field_style(),
        )

        def change_type(event) -> None:
            acronym.visible = author_type.value == "corporation"
            acronym.update()

        author_type = ft.Dropdown(
            label="Tipo de autor",
            value="person",
            options=[
                ft.dropdown.Option(
                    key="person",
                    text="Pessoa",
                    content=ft.Text(
                        value="Pessoa",
                        color=self.config.colors["text"],
                        font_family=self.config.font_families["montserrat"],
                        size=self.config.font_sizes["montserrat_tiny"],
                    ),
                ),
                ft.dropdown.Option(
                    key="corporation",
                    text="Instituição",
                    content=ft.Text(
                        value="Instituição",
                        color=self.config.colors["text"],
                        font_family=self.config.font_families["montserrat"],
                        size=self.config.font_sizes["montserrat_tiny"],
                    ),
                ),
            ],
            on_select=change_type,
            **self._dropdown_style("dark"),
        )

        def confirm(event) -> None:
            reference: AuthorReference = {
                'name': name,
                'id': None,
                'corporation': author_type.value == "corporation",
                'acronym': (
                    acronym.value.strip().upper()
                    if acronym.value and author_type.value == "corporation"
                    else None
                ),
            }
            self._select_author(reference)
            dialog.open = False
            self.page.update()

        dialog = ft.AlertDialog(
            modal=True,
            bgcolor=self.config.colors["surface"],
            title=ft.Text(
                "Classificar autor",
                color=self.config.colors["text"],
                font_family=self.config.font_families["cormorant"],
                weight=self.config.font_weights["cormorant_bold"],
            ),
            content=ft.Column(
                controls=[author_type, acronym],
                tight=True,
                width=360,
            ),
            actions=[
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
                        color=self.config.colors["surface"],
                        font_family=self.config.font_families["montserrat"],
                    ),
                    on_click=confirm,
                    bgcolor=self.config.colors["gold"],
                ),
            ],
        )
        self.page.show_dialog(dialog)

    def _close_author_dialog(self, dialog: ft.AlertDialog) -> None:
        dialog.open = False
        self.page.update()

    def _parent_work_control(self) -> ft.Control:
        search = ft.TextField(
            hint_text="Buscar obra-pai pelo título",
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
            self.search_works(self.parent_work_search)
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
            self.on_create_parent_work(self._select_parent_work)

    def _remove_author(self, reference: AuthorReference) -> None:
        self.author_references.remove(reference)
        self._refresh_author_search()

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

    def _format_issn_input(self, event) -> None:
        event.control.value = self._format_digits(event.control.value, (4, 4))
        event.control.update()

    def _format_isbn_input(self, event) -> None:
        event.control.value = self._format_digits(
            event.control.value, (3, 2, 4, 3, 1)
        )
        event.control.update()

    def _type_card(
        self,
        spec, selected: bool, on_select: Callable[[], None]
    ) -> ft.Container:
        """Cria um cartao selecionavel para um tipo de obra."""
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
                        text_align=ft.TextAlign.CENTER
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
                card.border = ft.Border(
                    left=ft.BorderSide(1, self.config.colors["text"]),
                    top=ft.BorderSide(1, self.config.colors["text"]),
                    right=ft.BorderSide(1, self.config.colors["text"]),
                    bottom=ft.BorderSide(4, self.config.colors["text"]),
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
        """Converte os controles atuais nos dados do formulario."""
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
        data["parent_work_id"] = self.parent_work_id
        return data

    def _toggle_partial(self, event) -> None:
        """Alterna campos parciais preservando os valores preenchidos."""
        self.partial_enabled = bool(event.control.value)
        if not self.partial_enabled:
            self.parent_work_search = ""
            self.parent_work_id = None
        self._render()

    def _choose(self, spec) -> None:
        """Seleciona um tipo novo e reinicia seus valores."""
        self.selected = spec
        self.partial_enabled = False
        self.author_references.clear()
        self.author_search = ""
        if self.author_search_field is not None:
            self.author_search_field.value = ""
        self._refresh_author_search()
        self.stored_values.clear()
        self._render()

    def _render(self, update_page: bool = True) -> None:
        """Reconstrói os campos conforme o tipo e o estado selecionados."""
        if self.fields:
            # Os valores ficam fora dos controles para sobreviver
            # à recriacao sem fechamento do modal.
            self.stored_values.update(self._collect())
        self.fields = {}
        rows: list[ft.Control] = []
        current: list[ft.Control] = []
        partial_keys = {partial.key for partial in PARTIAL}
        for spec in self.selected.fields:
            if spec.key in partial_keys:
                if spec.key != "is_partial" and not self.partial_enabled:
                    continue
            if spec.key in DEFAULTED_FIELDS.get(self.selected.key, set()):
                spec = FieldSpec(
                    key=spec.key,
                    label=spec.label,
                    hint=spec.hint,
                    kind=spec.kind,
                    required=False,
                )
            if spec.key == "date_anchor":
                spec = FieldSpec(
                    key=spec.key,
                    label=(
                        "Data de publicação"
                        if self.selected.date_kind == "date"
                        else spec.label
                    ),
                    hint=spec.hint,
                    kind=self.selected.date_kind,
                    required=spec.required,
                )
            control = self._field(
                spec,
                initial_value=self.stored_values.get(
                    spec.key,
                    (
                        self.partial_enabled
                        if spec.key == "is_partial"
                        else False
                    ),
                ),
                on_change=(
                    self._toggle_partial
                    if spec.key == "is_partial"
                    else None
                ),
            )
            self.fields[spec.key] = control
            if spec.kind in (
                "multiline", "checkbox", "responsabilities"
            ) or spec.key == "authors":
                if current:
                    rows.append(
                        ft.Row(
                            controls=current,
                            spacing=self.config.ui["control_gap"],
                        )
                    )
                    current = []

                if spec.key == "is_partial" and self.partial_enabled:
                    rows.append(
                        ft.Row(
                            controls=[
                                control,
                                self._parent_work_control(),
                                ft.IconButton(
                                    icon=ft.Icons.ADD,
                                    tooltip="Nova obra-pai",
                                    on_click=self._create_parent_work,
                                )
                            ],
                            spacing=self.config.ui["control_gap"],
                            vertical_alignment=ft.CrossAxisAlignment.CENTER
                        )
                    )
                else:
                    rows.append(
                        control
                        if spec.kind in ("responsabilities", "authors")
                        else ft.Row(controls=[control])
                    )
            else:
                current.append(control)
                if len(current) == 2:
                    rows.append(
                        ft.Row(
                            controls=current,
                            spacing=self.config.ui["control_gap"],
                        )
                    )
                    current = []
        if current:
            rows.append(
                ft.Row(
                    controls=current,
                    spacing=self.config.ui["control_gap"],
                )
            )
        self.form.controls = [
            ft.Text(
                value=self.selected.description,
                size=self.config.font_sizes["montserrat_medium"],
                color=self.config.colors["muted"],
                font_family=self.config.font_families["montserrat"],
                weight=self.config.font_weights["montserrat_semibold"],
            ),
            ft.Column(
                controls=rows,
                spacing=self.config.ui["modal_gap"],
            ),
        ]
        self.type_grid.controls = [
            self._type_card(
                spec,
                spec.key == self.selected.key,
                lambda spec=spec: self._choose(spec),
            )
            for spec in WORK_TYPES
        ]
        if update_page:
            self.page.update()

    def _reset(self) -> None:
        """Limpa o formulário e restaura seu estado inicial."""
        self.selected = WORK_TYPES[0]
        self.partial_enabled = False
        self.author_references.clear()
        self.stored_values.clear()
        self.fields.clear()
        self._render(update_page=False)

    def _close(self, event) -> None:
        """Fecha o dialogo sem enviar dados ao controller."""
        self._reset()
        if self.modal is not None:
            self.modal.open = False
            self.page.update()

    def _save(self, event) -> None:
        """Envia os dados ao controller e fecha em caso de sucesso."""
        if self.on_save(self._collect()) and self.modal is not None:
            self._reset()
            self.modal.open = False
            self.page.update()

    def compose(self) -> ft.AlertDialog:
        """Monta e retorna o dialogo pronto para ser exibido."""
        self.modal = ft.AlertDialog(
            modal=False,
            bgcolor=self.config.colors["surface"],
            on_dismiss=self._close,
            shape=ft.RoundedRectangleBorder(radius=8),
            content_padding=self.config.ui["modal_content_padding"],
            content=ft.Column(
                controls=cast(list[ft.Control], [
                    cast(ft.Control, ft.Text(
                        value="Cadastrar nova obra".title(),
                        size=self.config.font_sizes["cormorant_large"],
                        color=self.config.colors["text"],
                        font_family=self.config.font_families["cormorant"],
                        weight=self.config.font_weights["cormorant_bold"],
                    )),
                    cast(ft.Control, ft.Row(
                        controls=cast(list[ft.Control], [
                            cast(ft.Control, ft.Container(
                                content=ft.Column(
                                    controls=cast(list[ft.Control], [
                                        cast(ft.Control, ft.Text(
                                            value="Tipo de obra",
                                            size=self.config.font_sizes[
                                                "montserrat_large"
                                            ],
                                            color=self.config.colors["muted"],
                                            font_family=(
                                                self.config.font_families[
                                                    "montserrat"
                                                ]
                                            ),
                                            weight=self.config.font_weights[
                                                "montserrat_semibold"
                                            ],
                                        )),
                                        cast(ft.Control, self.type_grid),
                                    ]),
                                    spacing=self.config.ui["modal_gap"],
                                    expand=True,
                                ),
                                width=self.config.ui["modal_type_panel_width"],
                                expand=False
                            )),
                            cast(ft.Control, ft.VerticalDivider(
                                width=1,
                                color=self.config.colors["border"],
                            )),
                            cast(ft.Control, ft.Container(
                                content=self.form, expand=True
                            )),
                        ]),
                        spacing=self.config.ui["control_gap"] + 6,
                        expand=True,
                        vertical_alignment=ft.CrossAxisAlignment.STRETCH,
                    )),
                ]),
                width=self.config.ui["modal_width"],
                height=self.config.ui["modal_height"],
                spacing=self.config.ui["modal_gap"],
            ),
            actions=[
                ft.TextButton(
                    content=ft.Text(
                        value="Cancelar",
                        font_family=self.config.font_families["montserrat"],
                    ),
                    on_click=self._close,
                ),
                ft.ElevatedButton(
                    content=ft.Text(
                        value="Salvar acervo",
                        font_family=self.config.font_families["montserrat"],
                    ),
                    on_click=self._save,
                    bgcolor=self.config.colors["gold"],
                    color=self.config.colors["surface"],
                ),
            ],
        )
        self._render()
        return self.modal

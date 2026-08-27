"""Composer stateful do dialogo de insercao de obras."""

from collections.abc import Callable
import re

import flet as ft

from src.views.work_insert_specs import (
    DEFAULTED_FIELDS,
    PARTIAL,
    WORK_TYPES,
    FieldSpec,
)
from src.utils.types import ViewConfig


class WorkInsertModalComposer:
    """Constroi o modal e administra seu estado visual."""

    def __init__(
        self,
        page: ft.Page,
        config: ViewConfig,
        on_save: Callable[[dict[str, object]], bool],
        search_authors: Callable[[str], list[str]] | None = None,
    ):
        self.page = page
        self.config = config
        self.on_save = on_save
        self.search_authors = search_authors
        self.selected = WORK_TYPES[0]
        self.fields: dict[str, ft.Control] = {}
        self.partial_enabled = False
        self.author_names: list[str] = []
        self.author_search = ""
        self.author_control: ft.Column | None = None
        self.author_search_field: ft.TextField | None = None
        self.author_results: ft.Row | None = None
        self.author_pills: ft.Row | None = None
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

    def _dropdown_style(self):
        """Retorna o estilo dos menus suspensos."""
        style = self._style()
        style["text_style"] = ft.TextStyle(
            color=self.config.colors["muted"],
            weight=self.config.font_weights["montserrat_normal"],
            font_family=self.config.font_families["montserrat"],
            letter_spacing=2,
            size=12
        )
        style["label_style"] = ft.TextStyle(
            color=self.config.colors["muted"],
            weight=self.config.font_weights["montserrat_normal"],
            font_family=self.config.font_families["montserrat"],
            letter_spacing=2,
            size=12
        )
        style.pop("cursor_color")
        return style

    def _text_field_style(self):
        """Retorna a tipografia e as cores dos campos de texto."""
        style = self._style()
        style["text_style"] = ft.TextStyle(
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
        names = (
            self.search_authors(self.author_search)
            if self.author_search and self.search_authors is not None
            else []
        )
        self.author_results.controls = [
            ft.TextButton(
                content=name,
                on_click=lambda e, name=name: self._select_author(name),
            )
            for name in names
            if name not in self.author_names
        ]
        self.author_results.visible = bool(self.author_results.controls)
        self.author_pills.controls = [
            ft.Chip(
                label=ft.Text(name),
                on_delete=lambda e, name=name: self._remove_author(name),
            )
            for name in self.author_names
        ]
        self.author_pills.visible = bool(self.author_pills.controls)
        if refresh:
            self.author_control.update()

    def _select_author(self, name: str) -> None:
        if name not in self.author_names:
            self.author_names.append(name)
        self.author_search = ""
        if self.author_search_field is not None:
            self.author_search_field.value = ""
        self._refresh_author_search()

    def _add_author_from_search(self, event) -> None:
        name = self.author_search.strip()
        if name:
            self._select_author(name)

    def _remove_author(self, name: str) -> None:
        self.author_names.remove(name)
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
                data[key] = "; ".join(self.author_names)
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
        return data

    def _toggle_partial(self, event) -> None:
        """Alterna campos parciais preservando os valores preenchidos."""
        self.partial_enabled = bool(event.control.value)
        self._render()

    def _choose(self, spec) -> None:
        """Seleciona um tipo novo e reinicia seus valores."""
        self.selected = spec
        self.partial_enabled = False
        self.author_names.clear()
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
                                ft.TextField(
                                    hint_text="Nome da obra-pai",
                                    prefix_icon=ft.Icons.SEARCH,
                                    expand=True,
                                    **self._text_field_style()
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.ADD,
                                    tooltip="Nova obra-pai",
                                    # on_click=...
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
                controls=[
                    ft.Text(
                        value="Cadastrar nova obra".title(),
                        size=self.config.font_sizes["cormorant_large"],
                        color=self.config.colors["text"],
                        font_family=self.config.font_families["cormorant"],
                        weight=self.config.font_weights["cormorant_bold"],
                    ),
                    ft.Row(
                        controls=[
                            ft.Container(
                                content=ft.Column(
                                    controls=[
                                        ft.Text(
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
                                        ),
                                        self.type_grid,
                                    ],
                                    spacing=self.config.ui["modal_gap"],
                                    expand=True,
                                ),
                                width=self.config.ui["modal_type_panel_width"],
                                expand=False
                            ),
                            ft.VerticalDivider(
                                width=1,
                                color=self.config.colors["border"],
                            ),
                            ft.Container(
                                content=self.form, expand=True
                            ),
                        ],
                        spacing=self.config.ui["control_gap"] + 6,
                        expand=True,
                        vertical_alignment=ft.CrossAxisAlignment.STRETCH,
                    ),
                ],
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

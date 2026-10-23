"""Renderização do formulário do modal de cadastro."""

from collections.abc import Callable

import flet as ft

from src.utils.types import ViewConfig
from src.views.work_insert_specs import (
    DEFAULTED_FIELDS,
    INHERITED_FROM_PARENT_FIELDS,
    MAGAZINE_PARENT_TYPES,
    PARTIAL_FIELDS_BY_TYPE,
    PARTIAL_FORM_FIELDS,
    WORK_TYPES,
    FieldSpec,
    WorkTypeSpec,
)


class RenderMixin:
    """Agrupa a lógica do montagem do formulário e das rows."""

    config: ViewConfig
    selected: WorkTypeSpec
    partial_enabled: bool
    stored_values: dict[str, object]
    fields: dict[str, ft.Control]
    type_grid: ft.GridView
    form: ft.Column
    page: ft.Page

    def _field(
        self,
        spec: FieldSpec,
        initial_value: object = "",
        on_change=None,
    ) -> ft.Control:
        """Hook para construir controles do formulário."""
        raise NotImplementedError

    def _toggle_partial(self, event) -> None:
        """Hook para alternar o modo de obra parcial."""
        raise NotImplementedError

    def _collect(self) -> dict[str, object]:
        """Hook para consolidar os valores do formulário."""
        raise NotImplementedError

    def _type_card(
        self,
        spec: WorkTypeSpec,
        selected: bool,
        on_select: Callable[[], None],
    ) -> ft.Container:
        """Hook para criar o cartão de seleção do tipo."""
        raise NotImplementedError

    def _create_parent_work(self, event) -> None:
        """Hook para abrir o cadastro de obra-pai."""
        raise NotImplementedError

    def _choose(self, spec: WorkTypeSpec) -> None:
        """Hook para trocar o tipo de obra."""
        raise NotImplementedError

    def _parent_work_control(self) -> ft.Control:
        """Hook para tornar o controle de obra-pai acessível."""
        raise NotImplementedError

    def _checkbox_group(
        self,
        label: str,
        control: ft.Control,
        trailing_controls: list[ft.Control] | None = None,
    ) -> list[ft.Control]:
        """Cria a sequência de controles de uma linha com checkbox."""
        controls: list[ft.Control] = [control]
        if trailing_controls:
            controls.extend(trailing_controls)
        return controls

    def _spec_for_render(self, spec: FieldSpec) -> FieldSpec:
        """Normaliza a spec antes da montagem final do formulário."""
        if (
            self.selected.key == "musical_score"
            and self.partial_enabled
            and spec.key == "physical_description"
        ):
            return FieldSpec(
                key=spec.key,
                label="Descrição física da parte (se houver)",
                hint=spec.hint,
                kind=spec.kind,
                required=False,
            )
        if spec.key in DEFAULTED_FIELDS.get(self.selected.key, set()):
            return FieldSpec(
                key=spec.key,
                label=spec.label,
                hint=spec.hint,
                kind=spec.kind,
                required=False,
            )
        if spec.key == "date_anchor":
            return FieldSpec(
                key=spec.key,
                label=(
                    "Data de publicação"
                    if self.selected.date_kind in {"date", "month"}
                    else spec.label
                ),
                hint=spec.hint,
                kind=self.selected.date_kind,
                required=spec.required,
            )
        return spec

    def _field_for_render(self, spec: FieldSpec) -> ft.Control:
        """Constrói o controle mantendo o valor persistido do estado atual."""
        return self._field(
            spec,
            initial_value=self.stored_values.get(
                spec.key,
                self.partial_enabled if spec.key == "is_partial" else False,
            ),
            on_change=(
                self._toggle_partial if spec.key == "is_partial" else None
            ),
        )

    def _flush_current_row(
        self,
        rows: list[ft.Control],
        current: list[ft.Control],
    ) -> tuple[list[ft.Control], list[ft.Control]]:
        """Fecha a row atual de campos em duas colunas e a devolve."""
        if current:
            rows.append(
                ft.Row(
                    controls=current,
                    spacing=self.config.ui["control_gap"],
                )
            )
            return rows, []
        return rows, current

    def _render_form_rows(self) -> list[ft.Control]:
        """Montagem do corpo do formulário em blocos independentes."""
        rows: list[ft.Control] = []
        current: list[ft.Control] = []
        checkbox_controls: list[ft.Control] = []
        partial_keys = {
            partial.key
            for partial in PARTIAL_FIELDS_BY_TYPE.get(
                self.selected.key, ()
            )
        } | {
            partial.key
            for partial in self.selected.fields
            if partial.key in {
                "consult_start_year",
                "consult_end_year",
                "part_start_page",
                "part_end_page",
            }
        }

        for spec in self.selected.fields:
            spec = self._spec_for_render(spec)
            allowed_partial_fields = PARTIAL_FORM_FIELDS.get(
                self.selected.key
            )
            if (
                self.partial_enabled
                and allowed_partial_fields is not None
                and spec.key not in allowed_partial_fields
            ):
                continue
            if (
                self.partial_enabled
                and self.selected.key not in MAGAZINE_PARENT_TYPES
                and spec.key in INHERITED_FROM_PARENT_FIELDS
                and not spec.required
            ):
                continue
            if (
                self.selected.key == "audio_document"
                and self.partial_enabled
                and spec.key in {
                    "authors",
                    "carrier_type",
                    "date_anchor",
                    "date_precision",
                    "publication_place",
                    "publisher",
                    "display_year",
                    "responsibilities",
                }
            ):
                continue
            if (
                self.selected.key == "musical_score"
                and self.partial_enabled
                and spec.key in {
                    "date_anchor",
                    "date_precision",
                    "publication_place",
                    "publisher",
                    "display_year",
                    "instrumentation",
                }
            ):
                continue
            if spec.key in partial_keys:
                if spec.key != "is_partial" and not self.partial_enabled:
                    continue

            control = self._field_for_render(spec)
            self.fields[spec.key] = control

            if spec.key == "title":
                rows, current = self._flush_current_row(rows, current)
                rows.append(ft.Row(controls=[control]))
                preserve_title = ft.Checkbox(
                    label=(
                        "Manter a grafia informada do título "
                        "(evita que o aplicativo deixe nomes "
                        "próprios em caixa baixa)"
                    ),
                    value=bool(
                        self.stored_values.get(
                            "preserve_title_spelling",
                            False,
                        )
                    ),
                    label_position=ft.LabelPosition.LEFT,
                    label_style=ft.TextStyle(
                        size=self.config.font_sizes["montserrat_tiny"],
                        weight=self.config.font_weights["montserrat_normal"],
                        color=self.config.colors["text"],
                        font_family=self.config.font_families["montserrat"],
                    ),
                )
                self.fields["preserve_title_spelling"] = preserve_title
                rows.append(
                    ft.Row(
                        controls=[preserve_title],
                        alignment=ft.MainAxisAlignment.START,
                    )
                )
                continue

            if spec.key == "is_partial" and self.partial_enabled:
                checkbox_controls.extend(
                    self._checkbox_group(
                        spec.label,
                        control,
                        [
                            self._parent_work_control(),
                            ft.IconButton(
                                icon=ft.Icons.ADD,
                                tooltip="Nova obra-pai",
                                on_click=self._create_parent_work,
                            ),
                        ],
                    )
                )
                continue

            if spec.kind == "checkbox":
                checkbox_controls.extend(
                    self._checkbox_group(spec.label, control)
                )
                continue

            if (
                spec.kind in ("multiline", "responsibilities")
                or spec.key == "authors"
            ):
                rows, current = self._flush_current_row(rows, current)
                rows.append(
                    control
                    if spec.kind in ("responsibilities", "authors")
                    else ft.Row(controls=[control])
                )
                continue

            current.append(control)
            if len(current) == 2:
                rows, current = self._flush_current_row(rows, current)

        rows, current = self._flush_current_row(rows, current)

        if self.selected.key in MAGAZINE_PARENT_TYPES:
            checkbox_controls.extend(
                [
                    ft.Text(
                        "Revista *",
                        color=self.config.colors["text"],
                        size=self.config.font_sizes["montserrat_tiny"],
                    ),
                    self._parent_work_control(),
                    ft.IconButton(
                        icon=ft.Icons.ADD,
                        tooltip="Nova revista",
                        on_click=self._create_parent_work,
                    ),
                ]
            )

        if checkbox_controls:
            rows.insert(
                0,
                ft.Row(
                    controls=checkbox_controls,
                    spacing=self.config.ui["control_gap"],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.START,
                ),
            )

        return rows

    def _render(self, update_page: bool = True) -> None:
        """Reconstrói os campos conforme o tipo e o estado selecionados."""
        if self.fields:
            self.stored_values.update(self._collect())
        self.fields = {}
        rows = self._render_form_rows()

        self.form.controls = [
            ft.Text(
                value=self.selected.description,
                size=self.config.font_sizes["montserrat_large"],
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


__all__ = ["RenderMixin"]

"""Renderização do diálogo "Nova obra": lista de tipos, seções e prévia."""

from dataclasses import dataclass

import flet as ft

from src.services.reference_preview import PreviewResult, build_reference_preview
from src.utils.error_log import log_exception
from src.utils.types import TextStyle, ViewConfig, ViewReference
from src.views import ui_kit as ui
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
from src.views.work_insert_specs import catalog
from src.views.work_insert_specs.catalog import (
    FULL_WIDTH_FIELDS,
    IDENTIFICATION,
    PARENT,
    SECTION_ORDER,
)

PARENT_KEY = "__parent__"
PRESERVE_TITLE_HELP = (
    "Evita que nomes próprios fiquem em caixa baixa na referência."
)
AUTHORS_HELP = (
    "Sugere autores já cadastrados. Enter cadastra um novo com o nome digitado."
)


@dataclass
class _FormItem:
    key: str
    control: ft.Control
    full: bool = False
    checkbox: bool = False


def _safe_update(control: ft.Control | None) -> None:
    if control is None:
        return
    try:
        control.update()
    except (RuntimeError, AssertionError, AttributeError):
        pass


class RenderMixin:
    """Agrupa a montagem da lista de tipos, do formulário e da prévia."""

    config: ViewConfig
    selected: WorkTypeSpec
    partial_enabled: bool
    stored_values: dict[str, object]
    fields: dict[str, ft.Control]
    field_wrappers: dict[str, ft.Control]
    field_order: list[str]
    form: ft.Column
    form_body: ft.Column
    form_intro: ft.Container
    type_list: ft.Column
    type_query: str
    preview_text: ft.Text
    preview_result: PreviewResult | None
    page: ft.Page
    edit_mode: bool
    parent_mode: bool
    _logged_preview_errors: set[str]

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

    def _create_parent_work(self, event) -> None:
        """Hook para abrir o cadastro de obra-pai."""
        raise NotImplementedError

    def _choose(self, spec: WorkTypeSpec) -> None:
        """Hook para trocar o tipo de obra."""
        raise NotImplementedError

    def _parent_work_control(self) -> ft.Control:
        """Hook para tornar o controle de obra-pai acessível."""
        raise NotImplementedError

    def _parent_is_magazine(self) -> bool:
        """Hook: a obra-pai deste tipo é uma revista."""
        raise NotImplementedError

    # ── lista de tipos ─────────────────────────────────────

    def _visible_type_groups(self) -> list[tuple[str, list[WorkTypeSpec]]]:
        return catalog.grouped_types(WORK_TYPES, self.type_query)

    def _type_row(self, spec: WorkTypeSpec) -> ft.Control:
        c = self.config
        selected = spec.key == self.selected.key
        icon_name, icon_style = catalog.type_icon(spec)
        row = ui.hover_surface(
            c,
            ft.Row(
                [
                    ft.Container(
                        ui.fa_icon(
                            icon_name,
                            size=ui.s(13),
                            color=c.colors["gold"] if selected else c.colors.get("faint", c.colors["muted"]),
                            style=icon_style,
                        ),
                        width=ui.s(18),
                        alignment=ft.Alignment.CENTER,
                    ),
                    ui.ui_text(
                        c,
                        spec.label,
                        size=13,
                        weight=ui.W600 if selected else ui.W500,
                        color=c.colors["text"] if selected else c.colors["muted"],
                        expand=True,
                    ),
                ],
                spacing=ui.s(10),
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            on_click=None if selected else (lambda e, spec=spec: self._choose(spec)),
            selected=selected,
            padding=ft.Padding.symmetric(horizontal=ui.s(8)),
            height=ui.s(30),
        )
        row.tooltip = spec.description
        row.data = spec.key
        return row

    def _render_type_list(self) -> None:
        c = self.config
        groups = self._visible_type_groups()
        controls: list[ft.Control] = []
        for title, specs in groups:
            controls.append(
                ft.Column(
                    [
                        ft.Container(
                            ui.ui_text(
                                c, title, size=12, weight=ui.W600,
                                color=c.colors.get("faint", c.colors["muted"]),
                            ),
                            height=ui.s(26),
                            padding=ft.Padding.only(left=ui.s(8)),
                            alignment=ft.Alignment.CENTER_LEFT,
                        ),
                        *[self._type_row(spec) for spec in specs],
                    ],
                    spacing=1,
                    tight=True,
                )
            )
        if not controls:
            controls.append(
                ft.Container(
                    ui.ui_text(
                        c,
                        "Nenhum tipo encontrado.",
                        size=13,
                        color=c.colors.get("faint", c.colors["muted"]),
                    ),
                    padding=ft.Padding.symmetric(horizontal=ui.s(8), vertical=ui.s(6)),
                )
            )
        self.type_list.controls = controls

    def _filter_types(self, event) -> None:
        self.type_query = event.control.value or ""
        self._render_type_list()
        _safe_update(self.type_list)

    def _choose_first_visible_type(self, event=None) -> None:
        groups = self._visible_type_groups()
        if groups:
            self._choose(groups[0][1][0])

    # ── formulário ─────────────────────────────────────────

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

    def _visible_field_specs(self) -> list[FieldSpec]:
        """Campos do tipo atual depois das regras de parte e herança."""
        visible: list[FieldSpec] = []
        partial_keys = {
            partial.key
            for partial in PARTIAL_FIELDS_BY_TYPE.get(self.selected.key, ())
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
        allowed_partial_fields = PARTIAL_FORM_FIELDS.get(self.selected.key)
        for spec in self.selected.fields:
            spec = self._spec_for_render(spec)
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
            if (
                spec.key in partial_keys
                and spec.key != "is_partial"
                and not self.partial_enabled
            ):
                continue
            visible.append(spec)
        return visible

    def _shows_parent_control(self, visible_keys: set[str]) -> bool:
        if self.selected.key in MAGAZINE_PARENT_TYPES:
            return True
        return self.partial_enabled and "is_partial" in visible_keys

    def _wrap(
        self,
        key: str,
        label: str | None,
        control: ft.Control,
        required: bool = False,
        help_text: str | None = None,
        error_target: ft.Control | None = None,
    ) -> ft.Control:
        wrapper = ui.form_field(
            self.config,
            label,
            control,
            required=required,
            help_text=help_text,
            error_target=error_target,
        )
        self.field_wrappers[key] = wrapper
        return wrapper

    def _checkbox_item(
        self,
        key: str,
        control: ft.Checkbox,
        help_text: str | None = None,
    ) -> ft.Control:
        if not help_text:
            self.field_wrappers[key] = control
            return control
        wrapper = ft.Column(
            [
                control,
                ft.Container(
                    ui.ui_text(
                        self.config,
                        help_text,
                        size=12,
                        color=self.config.colors.get("faint", self.config.colors["muted"]),
                        max_lines=2,
                    ),
                    padding=ft.Padding.only(left=ui.s(34)),
                ),
            ],
            spacing=0,
            tight=True,
        )
        self.field_wrappers[key] = wrapper
        return wrapper

    def _collect_items(self) -> dict[str, list[_FormItem]]:
        """Distribui os campos visíveis pelas seções do formulário."""
        buckets: dict[str, list[_FormItem]] = {
            key: [] for key in SECTION_ORDER
        }
        specs = self._visible_field_specs()
        visible_keys = {spec.key for spec in specs}

        if self._shows_parent_control(visible_keys):
            parent_control = self._parent_work_control()
            buckets[PARENT].append(
                _FormItem(
                    PARENT_KEY,
                    self._wrap(
                        PARENT_KEY,
                        "Revista" if self._parent_is_magazine() else "Obra-pai",
                        parent_control,
                        required=True,
                        error_target=getattr(self, "parent_work_field", None),
                    ),
                    full=True,
                )
            )

        for spec in specs:
            control = self._field_for_render(spec)
            self.fields[spec.key] = control
            section = catalog.field_section(spec.key)
            if spec.key == "title":
                buckets[section].append(
                    _FormItem(
                        spec.key,
                        self._wrap(spec.key, spec.label, control, spec.required),
                        full=True,
                    )
                )
                preserve_title = ui.checkbox(
                    self.config,
                    "Manter a grafia do título",
                    value=bool(
                        self.stored_values.get(
                            "preserve_title_spelling", False
                        )
                    ),
                    on_change=lambda e: self._value_changed(
                        "preserve_title_spelling"
                    ),
                )
                self.fields["preserve_title_spelling"] = preserve_title
                buckets[IDENTIFICATION].append(
                    _FormItem(
                        "preserve_title_spelling",
                        self._checkbox_item(
                            "preserve_title_spelling",
                            preserve_title,
                            PRESERVE_TITLE_HELP,
                        ),
                        checkbox=True,
                    )
                )
                continue
            if spec.kind == "checkbox":
                buckets[section].append(
                    _FormItem(
                        spec.key,
                        self._checkbox_item(spec.key, control),
                        checkbox=True,
                    )
                )
                continue
            if spec.key == "authors":
                wrapper = self._wrap(
                    spec.key,
                    spec.label,
                    control,
                    spec.required,
                    help_text=AUTHORS_HELP,
                    error_target=getattr(self, "author_search_field", None),
                )
            else:
                wrapper = self._wrap(
                    spec.key,
                    spec.label.rstrip(": "),
                    control,
                    spec.required,
                )
            buckets[section].append(
                _FormItem(
                    spec.key,
                    wrapper,
                    full=(
                        spec.key in FULL_WIDTH_FIELDS
                        or spec.kind in ("multiline", "responsibilities")
                    ),
                )
            )
        return buckets

    def _grid(self, items: list[_FormItem], columns: int) -> list[ft.Control]:
        """Grade de 2 (ou 3) colunas; campos largos ocupam a linha toda."""
        rows: list[ft.Control] = []
        current: list[ft.Control] = []
        gap = ui.s(16)

        def flush() -> None:
            nonlocal current
            if current:
                while len(current) < columns:
                    current.append(ft.Container(expand=True))
                rows.append(
                    ft.Row(
                        current,
                        spacing=gap,
                        vertical_alignment=ft.CrossAxisAlignment.START,
                    )
                )
                current = []

        checkboxes = [item for item in items if item.checkbox]
        for item in items:
            if item.checkbox:
                continue
            if item.full:
                flush()
                rows.append(ft.Row([item.control], spacing=gap))
                continue
            current.append(item.control)
            if len(current) == columns:
                flush()
        flush()
        if checkboxes:
            rows.append(
                ft.Row(
                    [item.control for item in checkboxes],
                    spacing=ui.s(24),
                    run_spacing=ui.s(8),
                    wrap=True,
                    vertical_alignment=ft.CrossAxisAlignment.START,
                )
            )
        return rows

    def _section(
        self,
        key: str,
        items: list[_FormItem],
    ) -> ft.Container:
        c = self.config
        meta = catalog.section_for(
            key, self.selected, self._parent_is_magazine()
        )
        legend: list[ft.Control] = [
            ui.ui_text(c, meta.title, size=13, weight=ui.W600)
        ]
        if meta.helper:
            legend.append(
                ui.ui_text(
                    c,
                    meta.helper,
                    size=12,
                    weight=ui.W400,
                    color=c.colors.get("faint", c.colors["muted"]),
                    max_lines=4,
                )
            )
        columns = 3 if key in catalog.THREE_COLUMN_SECTIONS else 2
        section = ft.Container(
            content=ft.Row(
                [
                    ft.Container(
                        ft.Column(legend, spacing=ui.s(3), tight=True),
                        width=ui.s(180),
                    ),
                    ft.Column(
                        self._grid(items, columns),
                        spacing=ui.s(16),
                        expand=True,
                    ),
                ],
                spacing=ui.s(24),
                vertical_alignment=ft.CrossAxisAlignment.START,
            ),
            padding=ft.Padding.only(top=ui.s(24)),
            border=ft.Border.only(top=ft.BorderSide(1, c.colors["border"])),
        )
        section.data = key
        return section

    def _render_intro(self) -> None:
        c = self.config
        icon_name, icon_style = catalog.type_icon(self.selected)
        self.form_intro.content = ft.Row(
            [
                ft.Container(
                    ui.fa_icon(icon_name, size=ui.s(15), color=c.colors["gold"], style=icon_style),
                    width=ui.s(36),
                    height=ui.s(36),
                    border_radius=ft.BorderRadius.all(ui.s(6)),
                    bgcolor=c.colors["card_hover"],
                    alignment=ft.Alignment.CENTER,
                ),
                ft.Column(
                    [
                        ui.ui_text(c, self.selected.label, size=15, weight=ui.W600),
                        ui.ui_text(
                            c,
                            self.selected.description,
                            size=12,
                            color=c.colors.get("faint", c.colors["muted"]),
                        ),
                    ],
                    spacing=ui.s(1),
                    tight=True,
                    expand=True,
                ),
            ],
            spacing=ui.s(12),
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    def _render_sections(self) -> list[ft.Control]:
        buckets = self._collect_items()
        self.field_order = [
            item.key for key in SECTION_ORDER for item in buckets[key]
        ]
        return [
            self._section(key, buckets[key])
            for key in SECTION_ORDER
            if buckets[key]
        ]

    @property
    def section_keys(self) -> list[str]:
        """Seções exibidas, na ordem (útil para testes e atalhos)."""
        return [
            control.data
            for control in self.form_body.controls[1:]
            if isinstance(control, ft.Container)
        ]

    # ── prévia ABNT ────────────────────────────────────────

    def _preview_spans(self, reference: ViewReference) -> list[ft.TextSpan]:
        spans: list[ft.TextSpan] = []
        for part in reference.parts:
            style = None
            if part.style == TextStyle.BOLD:
                style = ft.TextStyle(weight=ui.W700)
            elif part.style == TextStyle.ITALIC:
                style = ft.TextStyle(italic=True)
            spans.append(ft.TextSpan(part.content, style=style))
        if spans and isinstance(spans[0].text, str):
            spans[0].text = spans[0].text.lstrip()
        return spans

    def _refresh_preview(self, update: bool = True) -> None:
        """Recalcula a prévia com os valores atuais. Nunca levanta exceção."""
        c = self.config
        try:
            result = build_reference_preview(self._collect())
        except Exception as error:  # noqa: BLE001 - prévia nunca derruba o diálogo
            result = PreviewResult(
                None, "Não foi possível montar a prévia.", error
            )
        self.preview_result = result
        if result.error is not None:
            signature = f"{self.selected.key}:{type(result.error).__name__}:{result.error}"
            if signature not in self._logged_preview_errors:
                self._logged_preview_errors.add(signature)
                log_exception(
                    "Falha ao montar a prévia ABNT do cadastro "
                    f"({self.selected.key})",
                    result.error,
                )
        if result.reference is not None:
            self.preview_text.value = ""
            self.preview_text.spans = self._preview_spans(result.reference)
            self.preview_text.color = c.colors["text"]
        else:
            self.preview_text.spans = []
            self.preview_text.value = result.message
            self.preview_text.color = c.colors.get("faint", c.colors["muted"])
        if update:
            _safe_update(self.preview_text)

    # ── montagem ───────────────────────────────────────────

    def _render(self, update_page: bool = True) -> None:
        """Reconstrói os campos conforme o tipo e o estado selecionados."""
        if self.fields:
            self.stored_values.update(self._collect())
        self.fields = {}
        self.field_wrappers = {}
        self._render_intro()
        self.form_body.controls = [self.form_intro, *self._render_sections()]
        self._render_type_list()
        self._refresh_preview(update=False)
        if update_page:
            self.page.update()


__all__ = ["RenderMixin", "PARENT_KEY"]

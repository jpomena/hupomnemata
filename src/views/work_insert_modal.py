"""Composer stateful do diálogo "Nova obra" / "Editar obra" (v2).

Layout (``design/prototype/index.html``, ``renderNewWork``): cabeçalho de 52 px,
lista de tipos agrupada com busca à esquerda (248 px, fundo ``chrome``),
formulário em seções com a legenda à esquerda e rodapé fixo com a prévia ABNT
ao vivo, Cancelar e Salvar. A validação acontece ao salvar: o campo fica com
borda vermelha, a mensagem aparece abaixo e o foco vai para o primeiro erro.
"""

from collections.abc import Callable
from typing import TypedDict

import flet as ft

from src.contracts import AuthorReference, AuthorSearchResult
from src.services.metadata_service import (
    IdentifierType,
    MetadataService,
    check_local_duplicate,
    detect_identifier,
)
from src.services.reference_preview import PreviewResult
from src.utils.fa import fa_icon
from src.utils.types import ViewConfig
from src.views import ui_kit as ui
from src.views.work_insert_modal_author import AuthorSearchMixin
from src.views.work_insert_modal_fields import FieldBuilderMixin
from src.views.work_insert_modal_render import PARENT_KEY, RenderMixin
from src.views.work_insert_specs import (
    ALWAYS_PARTIAL_TYPES,
    MAGAZINE_PARENT_TYPES,
    WORK_TYPES,
    WorkTypeSpec,
)

DIALOG_WIDTH = 1040
DIALOG_HEIGHT = 740
TYPE_COLUMN_WIDTH = 248
SINGLE_TYPE_WIDTH = 820
PARENT_DIALOG_WIDTH = 780
PARENT_DIALOG_HEIGHT = 680

CARRY_OVER_FIELDS = {
    "title",
    "subtitle",
    "abstract",
    "url",
    "viewed_at",
    "preserve_title_spelling",
}

SAVE_LABEL = "Salvar no acervo"
SAVE_EDIT_LABEL = "Salvar alterações"
SAVING_LABEL = "Salvando"

# Rótulos que ``WorkSubmissionController._missing_required_fields`` devolve
# fora das specs, mapeados para o campo do formulário.
SPECIAL_MISSING_LABELS = {
    "Obra-pai": PARENT_KEY,
    "Página inicial da parte": "part_start_page",
    "Página final da parte": "part_end_page",
    "Identificador da parte": "part_identifier",
    "Data de acesso": "viewed_at",
    "Tipo de suporte": "carrier_type",
    "URL": "url",
}


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


def _safe_update(control: ft.Control | None) -> None:
    if control is None:
        return
    try:
        control.update()
    except (RuntimeError, AssertionError, AttributeError):
        pass


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
        search_works: (
            Callable[[str, str | None], list[tuple[int, str]]] | None
        ) = None,
        on_create_parent_work: Callable[
            [Callable[[int, str], None], str | None], None
        ] | None = None,
        initial_work_type: str | None = None,
        parent_mode: bool = False,
        edit_mode: bool = False,
        initial_values: dict[str, object] | None = None,
        initial_author_references: list[AuthorReference] | None = None,
        initial_parent_work_id: int | None = None,
        initial_parent_work_title: str = "",
        on_navigate_to_work: Callable[[int], None] | None = None,
    ):
        self.page = page
        self.config = config
        self.on_save = on_save
        self.search_authors = search_authors
        self.search_works = search_works
        self.on_create_parent_work: Callable[
            [Callable[[int, str], None], str | None], None
        ] | None = on_create_parent_work
        self.on_navigate_to_work = on_navigate_to_work
        self.parent_mode = parent_mode
        self.edit_mode = edit_mode
        self.initial_work_type = initial_work_type
        self.selected: WorkTypeSpec = self._initial_spec()
        self.fields: dict[str, ft.Control] = {}
        self.field_wrappers: dict[str, ft.Control] = {}
        self.field_order: list[str] = []
        self.errors: dict[str, str] = {}
        self.stored_values: dict[str, object] = dict(initial_values or {})
        self.partial_enabled = (
            self.selected.key in ALWAYS_PARTIAL_TYPES
            or self.selected.key in MAGAZINE_PARENT_TYPES
            or bool(self.stored_values.get("is_partial"))
        )
        self.author_references: list[AuthorReference] = list(
            initial_author_references or []
        )
        self.author_search = ""
        self.author_control: ft.Column | None = None
        self.author_search_field: ft.TextField | None = None
        self.author_results: ft.Row | None = None
        self.author_pills: ft.Row | None = None
        self.parent_work_search = initial_parent_work_title
        self.parent_work_id = initial_parent_work_id
        self.parent_work_field: ft.TextField | None = None
        self.parent_work_results: ft.Column | None = None
        self.saving = False
        self.focus_title = True
        self.type_query = ""
        self._logged_preview_errors: set[str] = set()
        self.preview_result: PreviewResult | None = None

        # Estado da barra de importação inline
        self.import_bar_visible = False
        self._import_loading = False
        self._import_ignore_duplicate = False
        self.import_service = MetadataService()
        self.import_input: ft.TextField | None = None
        self.import_badge_container: ft.Container | None = None
        self.import_error_box: ft.Container | None = None
        self.import_error_text: ft.Text | None = None
        self.import_duplicate_box: ft.Container | None = None
        self.import_loading_box: ft.Container | None = None
        self.import_submit_button: ft.Container | None = None
        self.import_bar: ft.Container | None = None

        c = self.config
        self.type_search = ui.search_field(
            c,
            "Buscar tipo",
            on_change=self._filter_types,
            on_submit=self._choose_first_visible_type,
            width=None,
            expand=False,
        )
        self.type_list = ft.Column(
            spacing=ui.s(8),
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )
        self.form_intro = ft.Container()
        self.form_body = ft.Column(spacing=ui.s(24), tight=True)
        self.form = ft.Column(
            controls=[
                ft.Container(
                    content=self.form_body,
                    padding=ft.Padding.only(
                        left=ui.s(32), right=ui.s(32),
                        top=ui.s(24), bottom=ui.s(32),
                    ),
                )
            ],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            spacing=0,
        )
        self.preview_text = ft.Text(
            "",
            size=ui.s(13),
            weight=ui.W500,
            color=c.colors.get("faint", c.colors["muted"]),
            font_family=c.font_families["montserrat"],
            max_lines=3,
            overflow=ft.TextOverflow.ELLIPSIS,
            selectable=True,
            style=ft.TextStyle(height=1.55),
        )
        self.save_button: ft.Container | None = None
        self.modal: ft.AlertDialog | None = None

    def _initial_spec(self) -> WorkTypeSpec:
        return next(
            (spec for spec in WORK_TYPES if spec.key == self.initial_work_type),
            WORK_TYPES[0],
        )

    @property
    def shows_type_list(self) -> bool:
        """A troca de tipo só existe no cadastro novo."""
        return not self.parent_mode and not self.edit_mode

    @property
    def title(self) -> str:
        if self.edit_mode:
            return "Editar obra"
        if self.parent_mode:
            return (
                "Nova revista"
                if self.selected.key == "magazine"
                else "Nova obra-pai"
            )
        return "Nova obra"

    # ── estado do formulário ───────────────────────────────

    def _collect(self) -> dict[str, object]:
        """Converte os controles atuais em dados do formulário."""
        data: dict[str, object] = {"work_type": self.selected.key}
        for key, control in self.fields.items():
            if key == "authors":
                data[key] = list(self.author_references)
                continue
            if isinstance(control, ft.Checkbox):
                data[key] = control.value
            elif (
                isinstance(control, ft.Column)
                and key in {"responsibilities", "part_responsibilities"}
            ):
                responsibilities = {}
                for row in control.controls:
                    if not isinstance(row, ft.Row) or len(row.controls) < 2:
                        continue
                    role = (getattr(row.controls[0], "value", "") or "").strip()
                    names = (getattr(row.controls[1], "value", "") or "").strip()
                    if role and names:
                        responsibilities[role] = names
                data[key] = responsibilities
            elif isinstance(control, ft.Row):
                responsibility_key = (getattr(
                    control.controls[0], "value", ""
                ) or "").strip()
                responsibility_names = (getattr(
                    control.controls[1], "value", ""
                ) or "").strip()
                data[key] = (
                    {responsibility_key: responsibility_names}
                    if responsibility_key and responsibility_names
                    else {}
                )
            else:
                data[key] = getattr(control, "value", "") or ""
        data["parent_bibliographic_resource_id"] = self.parent_work_id
        return data

    def _value_changed(self, key: str) -> None:
        """Qualquer edição limpa o erro do campo e atualiza a prévia."""
        self._clear_error(key)
        self._refresh_preview()

    def _toggle_partial(self, event) -> None:
        """Alterna campos parciais preservando valores preenchidos."""
        self.partial_enabled = bool(event.control.value)
        if not self.partial_enabled:
            self.parent_work_search = ""
            self.parent_work_id = None
        self.focus_title = False
        try:
            self._render()
        finally:
            self.focus_title = True

    def _choose(self, spec) -> None:
        """Seleciona tipo de obra e reinicia o formulário.

        Título, subtítulo, resumo, URL, data de acesso, grafia do título e
        autores passam para o novo tipo quando ele também tem esses campos;
        o resto é específico de cada tipo e recomeça vazio.
        """
        if spec.key == self.selected.key:
            return
        carried = {
            key: value
            for key, value in (self._collect() if self.fields else {}).items()
            if key in CARRY_OVER_FIELDS and value not in ("", None)
        }
        keep_authors = any(field.key == "authors" for field in spec.fields)
        self.selected = spec
        self.partial_enabled = (
            spec.key in ALWAYS_PARTIAL_TYPES
            or spec.key in MAGAZINE_PARENT_TYPES
        )
        if not keep_authors:
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
        self.errors.clear()
        self.stored_values.clear()
        self.stored_values.update(carried)
        self.fields = {}
        self._render()

    def _reset(self) -> None:
        """Reseta formulário e estado do modal."""
        self.selected = WORK_TYPES[0]
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
        self.errors.clear()
        self.stored_values.clear()
        self.fields.clear()
        self.type_query = ""
        self.type_search.value = ""
        self.import_bar_visible = False
        if self.import_bar is not None:
            self.import_bar.visible = False
        if self.import_input is not None:
            self.import_input.value = ""
            self.import_input.disabled = False
        if self.import_badge_container is not None:
            self.import_badge_container.visible = False
            self.import_badge_container.content = None
        if self.import_error_box is not None:
            self.import_error_box.visible = False
        if self.import_duplicate_box is not None:
            self.import_duplicate_box.visible = False
        if self.import_loading_box is not None:
            self.import_loading_box.visible = False
        self._import_loading = False
        self._import_ignore_duplicate = False
        self._set_saving(False, update=False)
        self._render(update_page=False)

    # ── validação ──────────────────────────────────────────

    def _error_message(self, key: str) -> str:
        if key == PARENT_KEY:
            return (
                "Escolha a revista na busca ou cadastre uma nova."
                if self._parent_is_magazine()
                else "Escolha a obra-pai na busca ou cadastre uma nova."
            )
        if key == "title":
            return "Informe o título da obra."
        if key == "date_anchor":
            if "date_precision" in self.fields:
                return "Informe a data ou escolha “Data desconhecida” na precisão."
            return "Informe a data."
        if key == "viewed_at":
            return "Com URL, informe a data de acesso."
        if key == "carrier_type" and self.selected.key == "audio_document":
            return "Informe o suporte ou preencha a URL."
        if key == "url":
            return "Para conteúdo on-line, informe a URL."
        return "Campo obrigatório."

    def _validation_errors(
        self, data: dict[str, object]
    ) -> dict[str, str]:
        """Mesma regra do controller, devolvida por campo e na ordem da tela."""
        from src.controllers.work_submission_controller import (
            WorkSubmissionController,
        )

        missing = WorkSubmissionController._missing_required_fields(data)
        label_to_key = {
            field.label.rstrip(" *"): field.key
            for field in self.selected.fields
        }
        keys: set[str] = set()
        for label in missing:
            key = label_to_key.get(label) or SPECIAL_MISSING_LABELS.get(label)
            if key is not None:
                keys.add(key)
        return {
            key: self._error_message(key)
            for key in self.field_order
            if key in keys and key in self.field_wrappers
        }

    def _clear_error(self, key: str) -> None:
        if key not in self.errors:
            return
        self.errors.pop(key, None)
        wrapper = self.field_wrappers.get(key)
        if wrapper is not None:
            ui.set_field_error(self.config, wrapper, None)
            _safe_update(wrapper)

    def _apply_errors(self, errors: dict[str, str]) -> None:
        for key in list(self.errors):
            if key not in errors:
                self._clear_error(key)
        self.errors = dict(errors)
        for key, message in errors.items():
            wrapper = self.field_wrappers.get(key)
            if wrapper is not None:
                ui.set_field_error(self.config, wrapper, message)
                _safe_update(wrapper)

    def _focus_first_error(self) -> None:
        if not self.errors:
            return
        wrapper = self.field_wrappers.get(next(iter(self.errors)))
        data = getattr(wrapper, "data", None)
        target = data.get("error_target") if isinstance(data, dict) else wrapper
        focus = getattr(target, "focus", None)
        run_task = getattr(self.page, "run_task", None)
        if focus is None or run_task is None:
            return
        try:
            run_task(focus)
        except Exception:  # noqa: BLE001 - foco é conveniência
            pass

    # ── ações ──────────────────────────────────────────────

    def _set_saving(self, saving: bool, update: bool = True) -> None:
        self.saving = saving
        button = self.save_button
        if button is None:
            return
        data = button.data or {}
        label = data.get("label")
        if label is not None:
            label.value = (
                SAVING_LABEL
                if saving
                else SAVE_EDIT_LABEL if self.edit_mode else SAVE_LABEL
            )
        button.opacity = 0.7 if saving else 1.0
        if update:
            _safe_update(button)

    def _close(self, event=None) -> None:
        """Fecha o diálogo sem persistir dados."""
        self._reset()
        if self.modal is not None:
            self.modal.open = False
            self.page.update()

    def _save(self, event) -> None:
        """Valida, mostra o estado de gravação e envia ao controller."""
        if self.saving:
            return
        data = self._collect()
        errors = self._validation_errors(data)
        if errors:
            self._apply_errors(errors)
            self._focus_first_error()
            return
        self._apply_errors({})
        self._set_saving(True)
        try:
            saved = self.on_save(data)
        finally:
            self._set_saving(False)
        if saved and self.modal is not None:
            self._reset()
            self.modal.open = False
            self.page.update()

    # ── montagem ───────────────────────────────────────────

    # ── importação de metadados inline ─────────────────────

    def _open_import_dialog(self, _e=None) -> None:
        """Abre a barra inline de importação de metadados por DOI, ISBN ou ISSN."""
        self.toggle_import_bar(True)

    def toggle_import_bar(self, visible: bool | None = None) -> None:
        """Exibe ou oculta a barra inline de importação de metadados."""
        if visible is None:
            self.import_bar_visible = not self.import_bar_visible
        else:
            self.import_bar_visible = visible

        if self.import_bar is not None:
            self.import_bar.visible = self.import_bar_visible
            _safe_update(self.import_bar)

        if self.import_bar_visible:
            if self.import_error_box is not None:
                self.import_error_box.visible = False
                _safe_update(self.import_error_box)
            if self.import_duplicate_box is not None:
                self.import_duplicate_box.visible = False
                _safe_update(self.import_duplicate_box)
            self._import_ignore_duplicate = False

            if self.import_input is not None:
                run_task = getattr(self.page, "run_task", None)
                focus = getattr(self.import_input, "focus", None)
                if run_task is not None and focus is not None:
                    try:
                        run_task(focus)
                    except Exception:
                        pass
        if self.page:
            try:
                self.page.update()
            except Exception:
                pass

    def _on_import_input_change(self, event: ft.ControlEvent) -> None:
        raw = event.control.value or ""
        id_type, _ = detect_identifier(raw)
        c = self.config

        if self.import_badge_container is not None:
            if not raw.strip():
                self.import_badge_container.visible = False
                self.import_badge_container.content = None
            elif id_type == IdentifierType.DOI:
                self.import_badge_container.visible = True
                self.import_badge_container.content = ui.badge(c, "DOI Detectado")
            elif id_type == IdentifierType.ISBN:
                self.import_badge_container.visible = True
                self.import_badge_container.content = ui.badge(c, "ISBN Detectado")
            elif id_type == IdentifierType.ISSN:
                self.import_badge_container.visible = True
                self.import_badge_container.content = ui.badge(c, "ISSN Detectado")
            else:
                self.import_badge_container.visible = True
                self.import_badge_container.content = ui.badge(c, "Formato desconhecido")
            _safe_update(self.import_badge_container)

        if self.import_error_box is not None and self.import_error_box.visible:
            self.import_error_box.visible = False
            _safe_update(self.import_error_box)
        if self.import_duplicate_box is not None and self.import_duplicate_box.visible:
            self.import_duplicate_box.visible = False
            _safe_update(self.import_duplicate_box)
        self._import_ignore_duplicate = False

    def _set_import_loading(self, loading: bool) -> None:
        self._import_loading = loading
        if self.import_loading_box is not None:
            self.import_loading_box.visible = loading
            _safe_update(self.import_loading_box)
        if self.import_submit_button is not None:
            self.import_submit_button.disabled = loading
            _safe_update(self.import_submit_button)
        if self.import_input is not None:
            self.import_input.disabled = loading
            _safe_update(self.import_input)

    def _show_import_error(self, message: str) -> None:
        if self.import_error_text is not None:
            self.import_error_text.value = message
        if self.import_error_box is not None:
            self.import_error_box.visible = True
            _safe_update(self.import_error_box)
        if self.import_duplicate_box is not None:
            self.import_duplicate_box.visible = False
            _safe_update(self.import_duplicate_box)

    def _show_import_duplicate_warning(self, work_id: int, work_title: str) -> None:
        c = self.config

        def _on_view_existing(_e):
            self._close(None)
            if self.on_navigate_to_work is not None:
                self.on_navigate_to_work(work_id)

        def _on_force_continue(_e):
            self._import_ignore_duplicate = True
            if self.import_duplicate_box is not None:
                self.import_duplicate_box.visible = False
                _safe_update(self.import_duplicate_box)
            raw = (self.import_input.value or "").strip() if self.import_input else ""
            self._execute_import_search(raw)

        if self.import_duplicate_box is not None:
            self.import_duplicate_box.content = ft.Container(
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                fa_icon(
                                    "triangle-exclamation",
                                    size=ui.s(14),
                                    color=c.colors.get("warning", "#eab308"),
                                ),
                                ui.ui_text(
                                    c,
                                    "Identificador já cadastrado no Acervo:",
                                    size=12,
                                    weight=ui.W600,
                                    color=c.colors.get("warning", "#eab308"),
                                ),
                            ],
                            spacing=ui.s(6),
                        ),
                        ui.ui_text(
                            c,
                            f"“{work_title}”",
                            size=12,
                            color=c.colors["text"],
                            weight=ui.W500,
                        ),
                        ft.Row(
                            [
                                ui.button(
                                    c,
                                    "Ver obra cadastrada",
                                    variant="default",
                                    small=True,
                                    on_click=_on_view_existing,
                                ),
                                ui.button(
                                    c,
                                    "Importar como nova",
                                    variant="ghost",
                                    small=True,
                                    on_click=_on_force_continue,
                                ),
                            ],
                            spacing=ui.s(6),
                        ),
                    ],
                    spacing=ui.s(6),
                    tight=True,
                ),
                bgcolor=ui.alpha(c.colors.get("warning", "#eab308"), 0.12),
                border=ft.Border.all(
                    1, ui.alpha(c.colors.get("warning", "#eab308"), 0.3)
                ),
                border_radius=ft.BorderRadius.all(ui.s(6)),
                padding=ui.s(10),
            )
            self.import_duplicate_box.visible = True
            _safe_update(self.import_duplicate_box)

    def _on_import_search_clicked(self) -> None:
        if self._import_loading:
            return

        raw = (self.import_input.value or "").strip() if self.import_input else ""
        if not raw:
            self._show_import_error("Por favor, digite um DOI, ISBN ou ISSN.")
            return

        id_type, clean_id = detect_identifier(raw)
        if id_type == IdentifierType.UNKNOWN:
            self._show_import_error(
                "Identificador não reconhecido. Certifique-se de inserir um DOI (10.xxxx), ISBN ou ISSN."
            )
            return

        if not self._import_ignore_duplicate:
            duplicate = check_local_duplicate(id_type, clean_id)
            if duplicate:
                work_id, work_title = duplicate
                self._show_import_duplicate_warning(work_id, work_title)
                return

        self._execute_import_search(raw)

    def _execute_import_search(self, raw: str) -> None:
        self._set_import_loading(True)
        if self.import_error_box is not None:
            self.import_error_box.visible = False
            _safe_update(self.import_error_box)

        async def _async_search():
            import asyncio

            try:
                metadata = await asyncio.to_thread(self.import_service.resolve, raw)
                self._set_import_loading(False)
                self.toggle_import_bar(False)
                self.apply_imported_metadata(metadata)
            except Exception as exc:
                err_msg = str(exc)
                if "não foi encontrado" in err_msg.lower():
                    clean_msg = err_msg
                else:
                    clean_msg = f"Falha ao consultar metadados: {err_msg}"
                self._set_import_loading(False)
                self._show_import_error(clean_msg)

        run_task = getattr(self.page, "run_task", None)
        if run_task is not None:
            run_task(_async_search)
        else:
            try:
                metadata = self.import_service.resolve(raw)
                self._set_import_loading(False)
                self.toggle_import_bar(False)
                self.apply_imported_metadata(metadata)
            except Exception as exc:
                self._set_import_loading(False)
                self._show_import_error(str(exc))

    def _build_import_bar(self) -> ft.Container:
        c = self.config
        self.import_input = ui.input_field(
            c,
            hint="Ex.: 10.1038/nature.2014.14583, 978-85-7559-484-1 ou 0101-3300",
            prefix_icon="barcode",
            on_change=self._on_import_input_change,
            on_submit=lambda _e: self._on_import_search_clicked(),
            expand=True,
        )
        self.import_badge_container = ft.Container(content=None, visible=False)
        self.import_error_text = ui.ui_text(
            c, "", size=12, color=c.colors.get("danger", "#ef4444")
        )
        self.import_error_box = ft.Container(
            content=ft.Row(
                [
                    fa_icon(
                        "circle-exclamation",
                        size=ui.s(14),
                        color=c.colors.get("danger", "#ef4444"),
                    ),
                    ft.Container(content=self.import_error_text, expand=True),
                ],
                spacing=ui.s(8),
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            visible=False,
            padding=ft.Padding.symmetric(vertical=ui.s(4)),
        )
        self.import_duplicate_box = ft.Container(
            visible=False, padding=ft.Padding.symmetric(vertical=ui.s(4))
        )
        loading_ring = ft.ProgressRing(
            width=ui.s(16),
            height=ui.s(16),
            stroke_width=2,
            color=c.colors["gold"],
        )
        loading_label = ui.ui_text(
            c, "Consultando bases abertas...", size=12, color=c.colors["muted"]
        )
        self.import_loading_box = ft.Container(
            content=ft.Row(
                [loading_ring, loading_label],
                spacing=ui.s(8),
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            visible=False,
            padding=ft.Padding.symmetric(vertical=ui.s(4)),
        )
        self.import_submit_button = ui.button(
            c,
            "Buscar e Preencher",
            icon_name="magnifying-glass",
            variant="primary",
            small=True,
            on_click=lambda _e: self._on_import_search_clicked(),
        )
        cancel_btn = ui.button(
            c,
            "Cancelar",
            variant="ghost",
            small=True,
            on_click=lambda _e: self.toggle_import_bar(False),
        )

        bar_header = ft.Row(
            [
                fa_icon("file-import", size=ui.s(14), color=c.colors["gold"]),
                ui.ui_text(
                    c,
                    "Importar metadados por DOI, ISBN ou ISSN",
                    size=13,
                    weight=ui.W600,
                ),
                ui.ui_text(
                    c,
                    "— preenche automaticamente tipo, dados da obra, autores e revista vinculada.",
                    size=12,
                    color=c.colors.get("faint", c.colors["muted"]),
                    expand=True,
                ),
                ui.icon_button(
                    c,
                    "xmark",
                    on_click=lambda _e: self.toggle_import_bar(False),
                    tooltip="Ocultar importação",
                ),
            ],
            spacing=ui.s(8),
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        input_row = ft.Row(
            [
                self.import_input,
                self.import_badge_container,
                self.import_submit_button,
                cancel_btn,
            ],
            spacing=ui.s(8),
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        content_col = ft.Column(
            [
                bar_header,
                input_row,
                self.import_loading_box,
                self.import_error_box,
                self.import_duplicate_box,
            ],
            spacing=ui.s(8),
            tight=True,
        )

        return ft.Container(
            content=content_col,
            padding=ft.Padding.only(
                left=ui.s(24), right=ui.s(16), top=ui.s(12), bottom=ui.s(12)
            ),
            bgcolor=c.colors.get("chrome", c.colors["surface"]),
            border=ft.Border.only(bottom=ft.BorderSide(1, c.colors["border"])),
            visible=self.import_bar_visible,
        )

    def apply_imported_metadata(self, metadata) -> None:
        """Aplica os metadados importados aos campos do modal e re-renderiza."""
        target_spec = next(
            (spec for spec in WORK_TYPES if spec.key == metadata.work_type),
            None,
        )
        if target_spec is not None:
            self.selected = target_spec
            self.partial_enabled = (
                target_spec.key in ALWAYS_PARTIAL_TYPES
                or target_spec.key in MAGAZINE_PARENT_TYPES
            )
        self.fields = {}
        self.stored_values.update(metadata.values)
        self.author_references = list(metadata.authors)
        self.author_search = ""
        self.author_control = None
        self.author_search_field = None
        self.author_results = None
        self.author_pills = None

        # Vinculação automática com a Revista (obra-pai)
        parent_id = getattr(metadata, "parent_work_id", None)
        parent_title = getattr(metadata, "parent_work_title", "")
        if not parent_id and self._parent_is_magazine():
            j_title = metadata.values.get("journal_title")
            if j_title:
                try:
                    from src.services.metadata_service import find_or_create_magazine

                    pub_place = str(
                        metadata.values.get("publication_city")
                        or metadata.values.get("publication_place")
                        or "[s.l.]"
                    )
                    parent_id, parent_title = find_or_create_magazine(str(j_title), pub_place)
                except Exception:
                    pass

        if parent_id:
            self.parent_work_id = parent_id
            self.parent_work_search = parent_title or str(metadata.values.get("journal_title", ""))
            self._clear_error(PARENT_KEY)
        else:
            self.parent_work_search = ""
            self.parent_work_id = None

        self.parent_work_field = None
        self.parent_work_results = None
        self.errors.clear()
        self._render(update_page=True)
        if self.page:
            try:
                self.page.update()
            except Exception:
                pass

    def _header(self) -> ft.Container:
        c = self.config
        actions: list[ft.Control] = []
        if not self.edit_mode and not self.parent_mode:
            actions.append(
                ui.button(
                    c,
                    "Importar",
                    icon_name="file-import",
                    variant="default",
                    small=True,
                    on_click=lambda _e: self.toggle_import_bar(),
                    tooltip="Importar metadados por DOI, ISBN ou ISSN",
                )
            )
        actions.append(
            ui.icon_button(
                c, "xmark", on_click=self._close, tooltip="Fechar (Esc)"
            )
        )
        return ft.Container(
            content=ft.Row(
                [
                    ui.ui_text(c, self.title, size=15, weight=ui.W600, expand=True),
                    *actions,
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=ui.s(8),
            ),
            height=ui.s(52),
            padding=ft.Padding.only(left=ui.s(24), right=ui.s(12)),
            border=ft.Border.only(bottom=ft.BorderSide(1, c.colors["border"])),
        )

    def _type_column(self) -> ft.Container:
        c = self.config
        return ft.Container(
            content=ft.Column(
                [self.type_search, self.type_list],
                spacing=ui.s(8),
                expand=True,
            ),
            width=ui.s(TYPE_COLUMN_WIDTH),
            padding=ui.s(8),
            bgcolor=c.colors.get("chrome", c.colors["surface"]),
            border=ft.Border.only(right=ft.BorderSide(1, c.colors["border"])),
        )

    def _footer(self) -> ft.Container:
        c = self.config
        self.save_button = ui.button(
            c,
            SAVE_EDIT_LABEL if self.edit_mode else SAVE_LABEL,
            on_click=self._save,
            icon_name="check",
            variant="primary",
        )
        return ft.Container(
            content=ft.Row(
                [
                    ft.Column(
                        [
                            ui.ui_text(
                                c,
                                "Prévia da referência ABNT",
                                size=12,
                                weight=ui.W600,
                                color=c.colors.get("faint", c.colors["muted"]),
                            ),
                            self.preview_text,
                        ],
                        spacing=ui.s(2),
                        expand=True,
                        tight=True,
                    ),
                    ft.Row(
                        [
                            ui.button(
                                c, "Cancelar", on_click=self._close, variant="ghost"
                            ),
                            self.save_button,
                        ],
                        spacing=ui.s(8),
                        tight=True,
                    ),
                ],
                spacing=ui.s(24),
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding.only(
                left=ui.s(24), right=ui.s(12), top=ui.s(12), bottom=ui.s(12)
            ),
            bgcolor=c.colors.get("chrome", c.colors["surface"]),
            border=ft.Border.only(top=ft.BorderSide(1, c.colors["border"])),
        )

    def _dialog_size(self) -> tuple[float, float]:
        if self.parent_mode:
            return PARENT_DIALOG_WIDTH, PARENT_DIALOG_HEIGHT
        if self.edit_mode:
            return SINGLE_TYPE_WIDTH, DIALOG_HEIGHT
        return DIALOG_WIDTH, DIALOG_HEIGHT

    def compose(self) -> ft.AlertDialog:
        """Montagem final do modal em tela."""
        c = self.config
        self.import_bar = self._build_import_bar()
        form_panel = ft.Container(
            content=ft.Column(
                [self.import_bar, self.form],
                spacing=0,
                expand=True,
            ),
            expand=True,
        )
        body_controls: list[ft.Control] = []
        if self.shows_type_list:
            body_controls.append(self._type_column())
        body_controls.append(form_panel)
        width, height = self._dialog_size()
        dialog_box = ft.Container(
            content=ft.Column(
                [
                    self._header(),
                    ft.Row(
                        body_controls,
                        spacing=0,
                        expand=True,
                        vertical_alignment=ft.CrossAxisAlignment.STRETCH,
                    ),
                    self._footer(),
                ],
                spacing=0,
                expand=True,
            ),
            width=ui.s(width),
            height=ui.s(height),
            bgcolor=c.colors["surface"],
            border_radius=ft.BorderRadius.all(ui.s(10)),
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        )
        self.modal = ft.AlertDialog(
            modal=False,
            bgcolor=c.colors["surface"],
            on_dismiss=self._close,
            shape=ft.RoundedRectangleBorder(radius=ui.s(10)),
            content_padding=0,
            inset_padding=ft.Padding.symmetric(horizontal=ui.s(24), vertical=ui.s(24)),
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            content=dialog_box,
            actions=[],
        )
        self.modal.composer = self
        self._render(update_page=False)
        return self.modal

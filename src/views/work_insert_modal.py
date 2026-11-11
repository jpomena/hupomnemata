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
from src.services.reference_preview import PreviewResult
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

    def _close(self, event) -> None:
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

    def _open_import_dialog(self, _e=None) -> None:
        """Abre o diálogo de importação de metadados por DOI, ISBN ou ISSN."""
        from src.views.import_modal import ImportModalDialog

        def on_nav(wid: int) -> None:
            self._close()
            if self.on_navigate_to_work is not None:
                self.on_navigate_to_work(wid)

        dialog = ImportModalDialog(
            page=self.page,
            config=self.config,
            on_success=self.apply_imported_metadata,
            on_navigate_to_work=on_nav,
        )
        dialog.show()

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
                    on_click=self._open_import_dialog,
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
        body_controls: list[ft.Control] = []
        if self.shows_type_list:
            body_controls.append(self._type_column())
        body_controls.append(ft.Container(content=self.form, expand=True))
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

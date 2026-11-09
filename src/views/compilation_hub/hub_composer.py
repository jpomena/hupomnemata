"""Página de uma compilação (destino ``compilacao:<id>``).

Cabeçalho com nome, descrição, selos e ações; abas Visão geral, Obras e
fragmentos e Caderno de trabalho. Depois de cada mudança a página se redesenha
no lugar com ``refresh()``.
"""

from collections.abc import Awaitable, Callable

import flet as ft

from src.contracts import (
    CompilationPayload,
    CompilationRecord,
    FragmentRecord,
)
from src.utils.types import ViewConfig, ViewReference
from src.views import ui_kit as ui
from src.views.ui_kit import s
from .caderno_mixin import CompilationHubCadernoMixin
from .common import EventControl, more_menu, plural
from .notes_mixin import CompilationHubNotesMixin
from .overview_mixin import CompilationHubOverviewMixin
from .works_mixin import CompilationHubWorksMixin

TABS = ('visao', 'obras', 'caderno')


class CompilationHubComposer(
    CompilationHubOverviewMixin,
    CompilationHubWorksMixin,
    CompilationHubCadernoMixin,
    CompilationHubNotesMixin,
):
    """Compõe a página da compilação e guarda o estado da tela (aba, ideia ativa)."""

    def __init__(
        self,
        page: ft.Page,
        config: ViewConfig,
        compilation: CompilationRecord,
        refresh_compilations: Callable[[], list[CompilationRecord]],
        search_works: Callable[[str], list[tuple[int, str]]],
        on_update: Callable[[int, CompilationPayload], bool],
        on_add_work: Callable[[int, int], bool],
        on_remove_work: Callable[[int, int], bool],
        on_reorder_works: Callable[[int, list[int]], bool],
        on_fragment_membership: Callable[[int, int, bool], bool],
        on_fragment_note: Callable[[int, int, str | None], bool],
        on_create_section: Callable[[int, str, str | None], int | None],
        on_update_section: Callable[[int, int, str, str | None], bool],
        on_delete_section: Callable[[int, int], bool],
        on_reorder_sections: Callable[[int, list[int]], bool],
        on_assign_fragment_to_section: Callable[[int, int, int | None], bool],
        on_reorder_section_fragments: Callable[[int, int, list[int]], bool],
        on_copy_caderno: Callable[[str], Awaitable[None]],
        on_create_work: Callable[[int], None],
        on_edit_work: Callable[[int, int], None],
        on_create_fragment: Callable[[int, int], None],
        on_edit_fragment: Callable[[int, FragmentRecord], None],
        on_close: Callable[[], None] | None = None,
        on_data_changed: Callable[[CompilationRecord], None] | None = None,
        on_delete: Callable[[int], bool] | None = None,
        on_navigate: Callable[[str], None] | None = None,
        on_open_work: Callable[[int], None] | None = None,
        on_chrome_changed: Callable[[], None] | None = None,
        work_references: Callable[[list[int]], dict[int, ViewReference]] | None = None,
        initial_tab: str = 'caderno',
    ) -> None:
        self.page = page
        self.config = config
        self.compilation = compilation
        self.refresh_compilations = refresh_compilations
        self.search_works = search_works
        self.on_update = on_update
        self.on_add_work = on_add_work
        self.on_remove_work = on_remove_work
        self.on_reorder_works = on_reorder_works
        self.on_fragment_membership = on_fragment_membership
        self.on_fragment_note = on_fragment_note
        self.on_create_section = on_create_section
        self.on_update_section = on_update_section
        self.on_delete_section = on_delete_section
        self.on_reorder_sections = on_reorder_sections
        self.on_assign_fragment_to_section = on_assign_fragment_to_section
        self.on_reorder_section_fragments = on_reorder_section_fragments
        self.on_copy_caderno = on_copy_caderno
        self.on_create_work = on_create_work
        self.on_edit_work = on_edit_work
        self.on_create_fragment = on_create_fragment
        self.on_edit_fragment = on_edit_fragment
        self.on_close = on_close
        self.on_data_changed = on_data_changed
        self.on_delete = on_delete
        self.on_navigate = on_navigate
        self.on_open_work = on_open_work
        self.on_chrome_changed = on_chrome_changed
        self.work_references = work_references
        self.selected_tab = initial_tab if initial_tab in TABS else 'caderno'
        self.active_section_id: int | str | None = None
        self.deleted = False
        self.root: ft.Container | None = None
        self.outline_host: ft.Container | None = None
        self.writing_column: ft.Column | None = None
        self.work_search: ft.TextField | None = None
        self.work_matches = ft.Column(spacing=s(1), tight=True, visible=False)
        self.work_matches_box: ft.Container | None = None

    def _run_click_action(
        self,
        event: ft.Event[EventControl],
        action: Callable[[], object],
    ) -> None:
        del event
        action()

    # ── ciclo de vida ──────────────────────────────────────

    def compose(self) -> ft.Container:
        self.root = ft.Container(
            content=self._compose_body(),
            expand=True,
            bgcolor=self.config.colors['bg'],
        )
        return self.root

    def _reload(self) -> bool:
        for item in self.refresh_compilations():
            if item['id'] == self.compilation['id']:
                self.compilation = item
                return True
        return False

    def refresh(self) -> None:
        """Relê a compilação do banco e redesenha a página no lugar."""
        if not self._reload():
            self.deleted = True
            if self.on_navigate is not None:
                self.on_navigate('Compilações')
            return
        valid_ids = {section['id'] for section in self.compilation['sections']}
        if isinstance(self.active_section_id, int) and self.active_section_id not in valid_ids:
            self.active_section_id = None
        self.work_matches.controls = []
        self.work_matches.visible = False
        if self.work_search is not None:
            self.work_search.value = ''
        if self.on_data_changed is not None:
            self.on_data_changed(self.compilation)
        self._render()

    def _render(self) -> None:
        if self.root is not None:
            self.root.content = self._compose_body()
        self.page.update()

    def _select_tab(self, key: str) -> None:
        if key not in TABS:
            return
        self.selected_tab = key
        self._render()

    # ── composição ─────────────────────────────────────────

    def _compose_header(self) -> ft.Container:
        c = self.config
        compilation = self.compilation
        meta = [
            ui.badge(c, plural(len(compilation['works']), 'obra', 'obras')),
            ui.badge(c, plural(self._member_count(), 'fragmento', 'fragmentos')),
            ui.badge(c, plural(len(compilation['sections']), 'ideia', 'ideias')),
        ]
        updated = self._updated_label()
        if updated:
            meta.append(ui.badge(c, f'Atualizada em {updated}'))
        self.copy_button = ui.button(
            c,
            'Copiar esqueleto',
            on_click=self._copy_caderno,
            icon_name='copy',
            icon_style='regular',
            disabled=not self._has_caderno_content(),
            tooltip='Copia o roteiro com as ideias, os fragmentos e as notas',
        )
        menu_items = [('pen', 'Editar detalhes', self._open_details_dialog, False)]
        if self.on_delete is not None:
            menu_items += [None, ('trash-can', 'Excluir compilação', self._confirm_delete, True)]
        self.header_menu = more_menu(c, menu_items, boxed=True, size=32)
        return ui.page_header(
            c,
            compilation['name'],
            compilation['description'],
            actions=[self.copy_button, self.header_menu],
            meta=meta,
        )

    def _compose_tabs(self) -> ft.Container:
        c = self.config
        self.tab_bar = ui.tabs(
            c,
            [
                ('visao', 'Visão geral', None),
                ('obras', 'Obras e fragmentos', len(self.compilation['works'])),
                ('caderno', 'Caderno de trabalho', len(self.compilation['sections'])),
            ],
            self.selected_tab,
            self._select_tab,
        )
        return self.tab_bar

    def _compose_tab_content(self) -> ft.Control:
        if self.selected_tab == 'caderno':
            return self._compose_caderno()
        body = self._compose_works_and_fragments() if self.selected_tab == 'obras' else self._compose_overview()
        return ft.Column([body], scroll=ft.ScrollMode.AUTO, expand=True)

    def _compose_body(self) -> ft.Column:
        self.tab_content = self._compose_tab_content()
        return ft.Column(
            [self._compose_header(), self._compose_tabs(), self.tab_content],
            spacing=0,
            expand=True,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )

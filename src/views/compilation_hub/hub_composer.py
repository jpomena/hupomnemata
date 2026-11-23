"""Página de uma compilação (destino ``compilacao:<id>``).

Cabeçalho com nome, descrição, selos e ações; abas Visão geral, Obras e
fragmentos e Caderno de trabalho. Depois de cada mudança a página se redesenha
no lugar com ``refresh()``.
"""

import asyncio
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
from src.utils.control_safety import safe_execute, safe_update, set_control_prop
from src.utils.scroll_restore import register_scroll_restorer

TABS = ('visao', 'obras', 'caderno')

# A rota de diálogo é dispensada no cliente em duas etapas (animação e
# remoção). Reaplicar a rolagem logo após a dispensa e em mais dois instantes
# curtos cobre a remontagem do ScrollController sem depender do frame exato.
SCROLL_RESTORE_DELAYS = (0.0, 0.10, 0.28)


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
        on_transfer_section: Callable[[int, int, int | None], bool] | None = None,
        on_link_fragment_to_section: Callable[[int, int, int, str | None], bool] | None = None,
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
        self.on_transfer_section = on_transfer_section
        self.on_delete_section = on_delete_section
        self.on_reorder_sections = on_reorder_sections
        self.on_assign_fragment_to_section = on_assign_fragment_to_section
        self.on_link_fragment_to_section = on_link_fragment_to_section
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
        self.show_rail = False
        self.root: ft.Container | None = None
        self.outline_host: ft.Container | None = None
        self.outline_scroll_offset: float = 0.0
        self.writing_column: ft.Column | None = None
        self.writing_scroll: ft.Column | None = None
        self.writing_scroll_offset: float = 0.0
        self.overview_scroll: ft.Column | None = None
        self.overview_scroll_offset: float = 0.0
        self.work_search: ft.TextField | None = None
        self.work_matches = ft.Column(spacing=s(1), tight=True, visible=False)
        self.work_matches_box: ft.Container | None = None
        self.work_hosts: dict[int, dict] = {}
        self._collapsed_works: set[int] = set()
        self._known_work_ids: set[int] | None = None
        self.works_scroll: ft.Column | None = None
        self.works_scroll_offset: float = 0.0
        self.works_outline_host: ft.Container | None = None

    def _run_click_action(
        self,
        event: ft.Event[EventControl],
        action: Callable[[], object],
    ) -> None:
        del event
        action()

    def _toggle_rail(self, _e: ft.ControlEvent | None = None) -> None:
        self.show_rail = not getattr(self, 'show_rail', False)
        row = getattr(self, 'caderno_row', None)
        host = getattr(self, 'rail_host', None)
        if row is None or host is None:
            self.refresh()
            return
        if self.show_rail:
            if host not in row.controls:
                row.controls.append(host)
            host.width = s(320)
            host.padding = s(16)
            host.opacity = 1.0
            host.border = ft.Border.only(left=ft.BorderSide(1, self.config.colors['border']))
        else:
            host.width = 0
            host.padding = 0
            host.opacity = 0.0
            host.border = None
        safe_update(row)

    # ── ciclo de vida ──────────────────────────────────────

    def compose(self) -> ft.Container:
        register_scroll_restorer(self.page, self.preserve_scroll)
        self.root = ft.Container(
            content=self._compose_body(),
            expand=True,
            bgcolor=self.config.colors['bg'],
        )
        return self.root

    def preserve_scroll(self) -> None:
        """Reaplica a rolagem depois que um diálogo é aberto ou dispensado.

        O cliente Flet remonta os ``ScrollController`` da tela ao trocar a rota
        de um diálogo. O compositor registra esta rotina em
        ``src.utils.scroll_restore``; as posições vêm do último evento de
        rolagem de cada coluna.
        """
        positions = self._capture_scroll_positions()
        if not any(value > 0 for value in positions.values()):
            return
        self._restore_scroll_positions(
            positions,
            delays=SCROLL_RESTORE_DELAYS,
        )

    def _reload(self) -> bool:
        for item in self.refresh_compilations():
            if item['id'] == self.compilation['id']:
                self.compilation = item
                return True
        return False

    def refresh(self) -> None:
        """Relê a compilação sem devolver a aba atual ao topo.

        As posições são registradas pelos próprios handlers de rolagem. A
        restauração ocorre depois de ``page.update()``, para alcançar os
        controles recém-criados já montados pelo Flet.
        """
        scroll_positions = self._capture_scroll_positions()
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
        if self.selected_tab == 'obras':
            refreshed = self._refresh_works_in_place()
        elif self.selected_tab == 'caderno':
            refreshed = self._refresh_caderno_in_place()
        else:
            refreshed = False

        if refreshed:
            # Manter a identidade do Column preserva o ScrollController:
            # não enviar scroll_to concorrente ao patch de conteúdo.
            return
        self._render()
        self._restore_scroll_positions(scroll_positions)

    def _capture_scroll_positions(self) -> dict[str, float]:
        """Lê as últimas posições efetivamente percorridas pelo usuário."""
        if self.selected_tab == 'caderno':
            main = self.writing_scroll_offset
        elif self.selected_tab == 'obras':
            main = self.works_scroll_offset
        else:
            main = self.overview_scroll_offset
        return {
            'main': main,
            'outline': self.outline_scroll_offset,
        }

    @staticmethod
    def _outline_scroll_of(host: ft.Container | None) -> ft.Column | None:
        """Acessa ``host.content.content`` sem supor a árvore montada."""
        host_view = getattr(host, 'content', None)
        scroll = getattr(host_view, 'content', None)
        return scroll if isinstance(scroll, ft.Column) else None

    def _restore_scroll_positions(
        self,
        positions: dict[str, float],
        delays: tuple[float, ...] = (0.08,),
    ) -> None:
        """Restaura a rolagem da aba ativa sem animação visível."""
        if self.selected_tab == 'caderno':
            main = self.writing_scroll
            outline = self._outline_scroll_of(self.outline_host)
        elif self.selected_tab == 'obras':
            main = self.works_scroll
            outline = self._outline_scroll_of(self.works_outline_host)
        elif self.selected_tab == 'visao':
            main = self.overview_scroll
            outline = None
        else:
            return

        targets = [
            (control, positions.get(name, 0.0))
            for name, control in (('main', main), ('outline', outline))
        ]
        pending = [
            (control, offset)
            for control, offset in targets
            if control is not None and offset > 0
        ]
        if not pending:
            return
        run_task = getattr(self.page, 'run_task', None)
        if not callable(run_task):
            return

        async def restore() -> None:
            # page.update() não espera o layout do Flutter. Cada tentativa
            # extra cobre a remontagem do ScrollController disparada pela
            # troca de rota do diálogo.
            previous = 0.0
            for delay in delays:
                await asyncio.sleep(max(delay - previous, 0))
                previous = delay
                for control, offset in pending:
                    try:
                        await control.scroll_to(offset=offset, duration=0)
                    except Exception:
                        # A rolagem é conveniência visual; não invalida os dados.
                        continue

        safe_execute(
            'restaurar rolagem da compilação',
            run_task,
            restore,
        )

    def _render(self) -> None:
        if self.root is not None:
            set_control_prop(
                self.root,
                'content',
                self._compose_body(),
            )
        self.page.update()

    def _select_tab(self, key: str) -> None:
        if key not in TABS:
            return
        self.selected_tab = key
        tab_bar_host = getattr(self, "tab_bar_host", None)
        switcher = getattr(self, "tab_switcher", None)
        header_host = getattr(self, "header_host", None)
        if tab_bar_host is None or switcher is None or header_host is None:
            self._render()
            return
        set_control_prop(
            header_host,
            'content',
            self._compose_header(),
        )
        set_control_prop(
            tab_bar_host,
            'content',
            self._compose_tabs(),
        )
        self.tab_content = self._compose_tab_content()
        set_control_prop(switcher, 'content', self.tab_content)
        for control in (header_host, tab_bar_host, switcher):
            safe_update(control)

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
        is_caderno = self.selected_tab == 'caderno'
        has_refs = bool(
            self._used_works() if is_caderno else compilation['works']
        )
        refs_label = (
            'Copiar Referências do Caderno'
            if is_caderno
            else 'Copiar Referências da Compilação'
        )
        refs_tooltip = (
            'Copia as referências das obras utilizadas no caderno em ordem alfabética'
            if is_caderno
            else 'Copia todas as referências da compilação em ordem alfabética'
        )
        self.copy_references_button = ui.button(
            c,
            refs_label,
            on_click=self._copy_references,
            icon_name='book-bookmark',
            icon_style='solid',
            disabled=not has_refs,
            tooltip=refs_tooltip,
        )
        self.rail_toggle_button = ui.icon_button(
            c,
            'table-columns',
            on_click=self._toggle_rail,
            tooltip='Ocultar / Exibir referências do caderno',
        )
        menu_items = [('pen', 'Editar detalhes', self._open_details_dialog, False)]
        if self.on_delete is not None:
            menu_items += [None, ('trash-can', 'Excluir compilação', self._confirm_delete, True)]
        self.header_menu = more_menu(c, menu_items, boxed=True, size=32)
        actions = [self.copy_button, self.copy_references_button]
        if is_caderno:
            actions.append(self.rail_toggle_button)
        actions.append(self.header_menu)
        return ui.page_header(
            c,
            compilation['name'],
            compilation['description'],
            actions=actions,
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
        if self.selected_tab == 'obras':
            return self._compose_works_and_fragments()
        self.overview_scroll = ft.Column(
            [self._compose_overview()],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            on_scroll=self._on_overview_scroll,
        )
        return self.overview_scroll

    def _compose_body(self) -> ft.Column:
        self.tab_content = self._compose_tab_content()
        self.header_host = ft.Container(self._compose_header())
        self.tab_bar_host = ft.Container(self._compose_tabs())
        self.tab_switcher = ft.AnimatedSwitcher(
            content=self.tab_content,
            duration=ui.MOTION_SLOW,
            reverse_duration=ui.MOTION_FAST,
            switch_in_curve=ft.AnimationCurve.EASE_OUT,
            switch_out_curve=ft.AnimationCurve.EASE_IN,
            transition=ft.AnimatedSwitcherTransition.FADE,
            expand=True,
        )
        return ft.Column(
            [self.header_host, self.tab_bar_host, self.tab_switcher],
            spacing=0,
            expand=True,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )

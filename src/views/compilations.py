"""Compilações: a lista de projetos (destino ``Compilações``) e a porta para a
página de cada um (destino ``compilacao:<id>``).

A lista é uma tabela em card: Projeto, Obras, Fragmentos, Ideias, Criada e
Atualizada. Clicar numa linha navega para a página da compilação, composta por
``CompilationHubComposer``.
"""

from collections.abc import Awaitable, Callable
from typing import TypeVar

import flet as ft

from src.contracts import (
    CompilationPayload,
    CompilationRecord,
    FragmentRecord,
)
from src.utils.types import ViewConfig, ViewReference
from src.views import ui_kit as ui
from src.views.compilation_hub import CompilationHubComposer
from src.views.compilation_hub.common import dialog, fmt_date, form_field, text_input
from src.views.ui_kit import s

EventControl = TypeVar('EventControl', bound=ft.Control)

COLUMN_WIDTHS = {'works': 72, 'fragments': 96, 'ideas': 72, 'created': 112, 'updated': 112}


def member_count(compilation: CompilationRecord) -> int:
    return sum(
        1
        for work in compilation['works']
        for fragment in work['fragments']
        if fragment['is_member']
    )


class CompilationsComposer:
    def __init__(
        self,
        page: ft.Page,
        config: ViewConfig,
        compilations: list[CompilationRecord],
        search_works: Callable[[str], list[tuple[int, str]]],
        refresh_compilations: Callable[[], list[CompilationRecord]],
        on_create: Callable[[CompilationPayload], int | None],
        on_update: Callable[[int, CompilationPayload], bool],
        on_delete: Callable[[int], bool],
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
        on_navigate: Callable[[str], None] | None = None,
        on_open_work: Callable[[int], None] | None = None,
        on_chrome_changed: Callable[[], None] | None = None,
        work_references: Callable[[list[int]], dict[int, ViewReference]] | None = None,
    ) -> None:
        self.page = page
        self.config = config
        self.compilations = compilations
        self.search_works = search_works
        self.refresh_compilations = refresh_compilations
        self.on_create = on_create
        self.on_update = on_update
        self.on_delete = on_delete
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
        self.on_navigate = on_navigate
        self.on_open_work = on_open_work
        self.on_chrome_changed = on_chrome_changed
        self.work_references = work_references
        self.active_hub: CompilationHubComposer | None = None
        self.root: ft.Container | None = None
        self.table_host: ft.Container | None = None
        self.count_text: ft.Text | None = None
        self.rows: list[ft.Container] = []
        self.compilation_search = ui.search_field(
            config,
            'Buscar por nome ou descrição',
            on_change=self._search_compilations,
        )
        self.new_name = text_input(config, hint='Ex.: Tese', max_length=150, autofocus=True, on_submit=lambda _e: self._create())
        self.new_description = text_input(
            config,
            hint='Qual é o tema ou o objetivo deste projeto?',
            multiline=True,
            min_lines=2,
            max_lines=4,
        )
        self.create_dialog: ft.AlertDialog | None = None

    # ── busca ──────────────────────────────────────────────

    def _search_compilations(self, event) -> None:
        self.compilation_search.value = event.control.value or ''
        self._render_table()
        self.page.update()

    def _filtered_compilations(self) -> list[CompilationRecord]:
        query = (self.compilation_search.value or '').strip().casefold()
        if not query:
            return self.compilations
        return [
            compilation
            for compilation in self.compilations
            if query in compilation['name'].casefold()
            or query in (compilation['description'] or '').casefold()
        ]

    # ── criar ──────────────────────────────────────────────

    def open_create_dialog(self) -> ft.AlertDialog:
        c = self.config
        self.new_name.value = ''
        self.new_name.error_text = None
        self.new_description.value = ''
        self.create_dialog = dialog(
            c,
            'Nova compilação',
            [
                form_field(c, 'Nome', self.new_name),
                form_field(c, 'Descrição (opcional)', self.new_description),
            ],
            [
                ui.button(c, 'Cancelar', on_click=lambda _e: self._cancel_create(), variant='ghost'),
                ui.button(c, 'Criar compilação', on_click=lambda _e: self._create(), variant='primary'),
            ],
            subtitle='Um projeto de escrita reúne obras, fragmentos e o roteiro de ideias.',
        )
        self.page.show_dialog(self.create_dialog)
        return self.create_dialog

    def _close_create_dialog(self) -> None:
        """Fecha o diálogo de criação de compilação com segurança garantida."""
        if hasattr(self, 'create_dialog') and self.create_dialog is not None:
            self.create_dialog.open = False
            try:
                self.create_dialog.update()
            except Exception:
                pass
        try:
            self.page.pop_dialog()
        except Exception:
            pass
        try:
            self.page.update()
        except Exception:
            pass

    def _create(self) -> None:
        name = (self.new_name.value or '').strip()
        if not name:
            self.new_name.error_text = 'Dê um nome à compilação.'
            try:
                self.new_name.update()
            except Exception:
                pass
            return

        # Fecha o diálogo ANTES do on_create, impedindo que o toast sobreponha a pilha de modais
        self._close_create_dialog()

        compilation_id = self.on_create({
            'name': name,
            'description': self.new_description.value,
        })
        if compilation_id is None:
            # Se a criação falhou, reabre o modal com a mensagem
            if hasattr(self, 'create_dialog') and self.create_dialog is not None:
                self.create_dialog.open = True
                self.page.show_dialog(self.create_dialog)
            return

        self.new_name.value = ''
        self.new_description.value = ''
        self.compilations = self.refresh_compilations()
        if self.on_navigate is not None:
            self.on_navigate(f'compilacao:{compilation_id}')
            return
        self._render_table()
        self.page.update()

    def _cancel_create(self) -> None:
        self._close_create_dialog()
        self.new_name.value = ''
        self.new_description.value = ''

    # ── página da compilação ───────────────────────────────

    def _make_hub(self, compilation: CompilationRecord) -> CompilationHubComposer:
        return CompilationHubComposer(
            page=self.page,
            config=self.config,
            compilation=compilation,
            refresh_compilations=self.refresh_compilations,
            search_works=self.search_works,
            on_update=self.on_update,
            on_add_work=self.on_add_work,
            on_remove_work=self.on_remove_work,
            on_reorder_works=self.on_reorder_works,
            on_fragment_membership=self.on_fragment_membership,
            on_fragment_note=self.on_fragment_note,
            on_create_section=self.on_create_section,
            on_update_section=self.on_update_section,
            on_delete_section=self.on_delete_section,
            on_reorder_sections=self.on_reorder_sections,
            on_assign_fragment_to_section=self.on_assign_fragment_to_section,
            on_reorder_section_fragments=self.on_reorder_section_fragments,
            on_copy_caderno=self.on_copy_caderno,
            on_create_work=self.on_create_work,
            on_edit_work=self.on_edit_work,
            on_create_fragment=self.on_create_fragment,
            on_edit_fragment=self.on_edit_fragment,
            on_data_changed=self._update_compilation,
            on_delete=self.on_delete,
            on_navigate=self.on_navigate,
            on_open_work=self.on_open_work,
            on_chrome_changed=self.on_chrome_changed,
            work_references=self.work_references,
        )

    def open_compilation_page(self, compilation_id: int) -> ft.Control | None:
        """Monta a página da compilação. ``None`` se ela não existe mais."""
        compilation = next((item for item in self.compilations if item['id'] == compilation_id), None)
        if compilation is None:
            self.active_hub = None
            return None
        self.active_hub = self._make_hub(compilation)
        return self.active_hub.compose()

    def _open(self, compilation_id: int) -> None:
        if self.on_navigate is not None:
            self.on_navigate(f'compilacao:{compilation_id}')

    def _update_compilation(self, compilation: CompilationRecord) -> None:
        self.compilations = [
            compilation if current['id'] == compilation['id'] else current
            for current in self.compilations
        ]

    def refresh_compilation_hub(self, compilation_id: int) -> None:
        """Ponto de entrada do controlador depois de mudanças vindas de fora
        (obra ou fragmento criados e editados a partir da página)."""
        self.compilations = self.refresh_compilations()
        hub = self.active_hub
        if hub is not None and hub.compilation['id'] == compilation_id and not hub.deleted:
            hub.refresh()
            return
        self._render_table()
        self.page.update()

    # ── lista ──────────────────────────────────────────────

    def _cell(self, control: ft.Control, key: str) -> ft.Container:
        return ft.Container(control, width=s(COLUMN_WIDTHS[key]), alignment=ft.Alignment.CENTER_RIGHT)

    def _compose_table_header(self) -> ft.Container:
        c = self.config

        def label(value: str) -> ft.Text:
            return ui.ui_text(c, value, size=12, color=c.colors['faint'])

        return ft.Container(
            content=ft.Row(
                [
                    ft.Container(label('Projeto'), expand=True),
                    self._cell(label('Obras'), 'works'),
                    self._cell(label('Fragmentos'), 'fragments'),
                    self._cell(label('Ideias'), 'ideas'),
                    self._cell(label('Criada'), 'created'),
                    self._cell(label('Atualizada'), 'updated'),
                ],
                spacing=s(12),
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            height=s(34),
            padding=ft.Padding.symmetric(horizontal=s(16)),
            border=ft.Border.only(bottom=ft.BorderSide(1, c.colors['border'])),
        )

    def _compose_row(self, compilation: CompilationRecord, last: bool) -> ft.Container:
        c = self.config
        name_ctrl = ui.ui_text(c, compilation['name'], size=13, weight=ui.W600)
        name_column: list[ft.Control] = [name_ctrl]
        if compilation['description']:
            name_column.append(ui.ui_text(c, compilation['description'], size=12, color=c.colors['faint']))
        number = lambda value: ui.ui_text(c, str(value), size=13, tabular=True)  # noqa: E731
        date = lambda value: ui.ui_text(c, fmt_date(value), size=13, color=c.colors['faint'], tabular=True)  # noqa: E731

        def _on_hover_row(hovering: bool) -> None:
            name_ctrl.color = c.colors['gold'] if hovering else c.colors['text']

        row = ui.hover_surface(
            c,
            ft.Row(
                [
                    ft.Column(name_column, spacing=s(1), expand=True, tight=True),
                    self._cell(number(len(compilation['works'])), 'works'),
                    self._cell(number(member_count(compilation)), 'fragments'),
                    self._cell(number(len(compilation['sections'])), 'ideas'),
                    self._cell(date(compilation.get('created_at')), 'created'),
                    self._cell(date(compilation.get('updated_at') or compilation.get('created_at')), 'updated'),
                ],
                spacing=s(12),
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            on_click=lambda _e, cid=compilation['id']: self._open(cid),
            padding=ft.Padding.symmetric(horizontal=s(16), vertical=s(10)),
            radius=0,
            on_hover=_on_hover_row,
            accent_left=True,
        )
        row.data = compilation['id']
        return ft.Container(row, border=None if last else ft.Border.only(bottom=ft.BorderSide(1, self.config.colors['border'])), data=compilation['id'])

    def _render_table(self) -> None:
        if self.table_host is None:
            return
        c = self.config
        visible = self._filtered_compilations()
        self.rows = [self._compose_row(item, index == len(visible) - 1) for index, item in enumerate(visible)]
        if self.count_text is not None:
            self.count_text.value = (
                f'{len(visible)} de {len(self.compilations)}'
                if len(visible) != len(self.compilations)
                else str(len(self.compilations))
            )
        if not self.compilations:
            self.table_host.content = ui.empty_state(
                c,
                'folder-open',
                'Nenhuma compilação ainda',
                'Crie uma compilação para reunir as obras e os fragmentos de um projeto de escrita.',
                action=ui.button(c, 'Nova compilação', on_click=lambda _e: self.open_create_dialog(), icon_name='plus', small=True),
            )
        elif not visible:
            self.table_host.content = ui.empty_state(c, 'magnifying-glass', 'Nada encontrado', 'Nenhuma compilação corresponde à busca.')
        else:
            self.table_host.content = ui.card(c, [self._compose_table_header(), *self.rows])

    def _compose_header(self) -> ft.Container:
        c = self.config
        self.new_button = ui.button(c, 'Nova compilação', on_click=lambda _e: self.open_create_dialog(), icon_name='plus', variant='primary')
        return ui.page_header(
            c,
            'Compilações',
            'Projetos de escrita, com as obras e os fragmentos de cada um.',
            actions=[self.new_button],
        )

    def compose(self, open_create: bool = False) -> ft.Container:
        c = self.config
        self.count_text = ui.ui_text(c, '', size=12, color=c.colors['faint'], tabular=True)
        self.table_host = ft.Container()
        self.root = ft.Container(
            content=ft.Column(
                [
                    self._compose_header(),
                    ui.toolbar(c, [self.compilation_search], trailing=[self.count_text]),
                    ft.Column(
                        [ft.Container(self.table_host, padding=ft.Padding.only(left=s(32), right=s(32), bottom=s(48)))],
                        scroll=ft.ScrollMode.AUTO,
                        expand=True,
                    ),
                ],
                spacing=0,
                expand=True,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
            expand=True,
            bgcolor=c.colors['bg'],
        )
        self._render_table()
        if open_create:
            self.open_create_dialog()
        return self.root

"""Aba Obras e fragmentos: obras do projeto e o que entra no caderno.

Um card por obra (título, autoria, contagem, “Fragmento” e ``⋯``) com uma
linha por fragmento: checkbox “Incluir no caderno”, citação em Cormorant e o
seletor “Destino no caderno”, desabilitado enquanto o fragmento está fora.
"""

import flet as ft

from src.contracts import CompilationFragmentRecord, CompilationWorkRecord
from src.utils.fa import fa_icon
from src.utils.fragment_reference import fragment_abnt_notation
from src.views import ui_kit as ui
from src.views.ui_kit import s
from .common import MenuItem, dialog, form_field, max_width_box, more_menu, plural, select_input
from .caderno_mixin import quoted


class CompilationHubWorksMixin:
    """Busca, inclusão, ordem e remoção de obras; vínculo dos fragmentos."""

    # ── ações ──────────────────────────────────────────────

    def _search_work_matches(self, event) -> None:
        query = (event.control.value or '').strip()
        c = self.config
        if len(query) < 2:
            self.work_matches.controls = []
            self.work_matches.visible = False
            self._sync_matches_box()
            self.page.update()
            return
        linked_ids = {work['id'] for work in self.compilation['works']}
        matches = [(work_id, title) for work_id, title in self.search_works(query) if work_id not in linked_ids][:8]
        rows: list[ft.Control] = []
        for work_id, title in matches:
            row = ui.hover_surface(
                c,
                ft.Row(
                    [fa_icon('plus', size=s(11), color=c.colors['faint']), ui.ui_text(c, title, size=13, expand=True)],
                    spacing=s(10),
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                on_click=lambda _e, resource_id=work_id: self._add_work(resource_id),
                padding=ft.Padding.symmetric(horizontal=s(10)),
                height=s(32),
            )
            row.data = title
            rows.append(row)
        if not rows:
            rows.append(ft.Container(ui.meta_text(c, 'Nenhuma obra do Acervo disponível para adicionar.'), padding=ft.Padding.symmetric(horizontal=s(10), vertical=s(8))))
        self.work_matches.controls = rows
        self.work_matches.visible = True
        self._sync_matches_box()
        self.page.update()

    def _sync_matches_box(self) -> None:
        box = getattr(self, 'work_matches_box', None)
        if box is not None:
            box.visible = self.work_matches.visible

    def _add_work(self, bib_res_id: int) -> None:
        if self.on_add_work(self.compilation['id'], bib_res_id):
            self.refresh()

    def _remove_work(self, bib_res_id: int) -> None:
        if self.on_remove_work(self.compilation['id'], bib_res_id):
            self.refresh()

    def _confirm_remove_work(self, work: CompilationWorkRecord) -> ft.AlertDialog:
        c = self.config

        def confirm(_event=None) -> None:
            self.page.pop_dialog()
            self._remove_work(work['id'])

        modal = dialog(
            c,
            'Retirar obra do projeto?',
            [
                ui.ui_text(
                    c,
                    f'“{work["title"]}” sai desta compilação, junto com os vínculos e as notas de articulação dos fragmentos dela. A obra e os fragmentos continuam no Acervo.',
                    size=13,
                    color=c.colors['muted'],
                    max_lines=None,
                )
            ],
            [
                ui.button(c, 'Cancelar', on_click=lambda _e: self.page.pop_dialog(), variant='ghost'),
                ui.button(c, 'Retirar obra', on_click=confirm, variant='danger', icon_name='circle-minus'),
            ],
            width=440,
        )
        modal.data = {'confirm': confirm}
        self.page.show_dialog(modal)
        return modal

    def _move_work(self, index: int, offset: int) -> None:
        work_ids = [work['id'] for work in self.compilation['works']]
        target_index = index + offset
        if target_index < 0 or target_index >= len(work_ids):
            return
        work_ids[index], work_ids[target_index] = work_ids[target_index], work_ids[index]
        if self.on_reorder_works(self.compilation['id'], work_ids):
            self.refresh()

    def _toggle_membership(self, fragment_id: int, selected: bool) -> None:
        self._set_fragment_destination(fragment_id, 'unassigned' if selected else 'not_selected')

    # ── composição ─────────────────────────────────────────

    def _destination_options(self) -> list[tuple[str, str]]:
        return (
            [('unassigned', 'A organizar')]
            + [(str(section['id']), section['title']) for section in self._sorted_sections()]
            + [('create_section', '+ Nova ideia…')]
        )

    def _compose_fragment(self, fragment: CompilationFragmentRecord, last: bool = False) -> ft.Container:
        c = self.config
        is_member = fragment['is_member']
        destination = (str(fragment['section_id']) if fragment['section_id'] is not None else 'unassigned') if is_member else 'unassigned'
        selector = select_input(
            c,
            destination,
            self._destination_options(),
            on_select=lambda event, current_id=fragment['id']: (
                self._set_fragment_destination(current_id, event.control.value)
                if event.control.value is not None
                else None
            ),
            disabled=not is_member,
        )
        checkbox = ft.Checkbox(
            value=is_member,
            tooltip='Incluir no caderno',
            active_color=c.colors['gold'],
            check_color=c.colors['on_gold'],
            border_side=ft.BorderSide(1, c.colors['border_strong']),
            shape=ft.RoundedRectangleBorder(radius=s(4)),
            on_change=lambda event, current_id=fragment['id']: self._toggle_membership(current_id, bool(event.control.value)),
        )
        if fragment['fragment_type'] == 'quote':
            body = ui.serif_text(c, quoted(fragment['excerpt']), size=17, max_lines=3, height=1.45)
        else:
            body = ui.ui_text(c, fragment['excerpt'], size=13, color=c.colors['muted'], max_lines=3)
        meta = [fragment_abnt_notation(fragment)]
        if fragment.get('work_note'):
            meta.append('com nota de articulação')
        menu_items: list[MenuItem] = [
            ('pen', 'Editar fragmento', lambda current=fragment: self.on_edit_fragment(self.compilation['id'], current), False),
            ('note-sticky', 'Editar nota de articulação' if fragment.get('work_note') else 'Adicionar nota de articulação', lambda current=fragment: self._prompt_fragment_note(current), False),
        ]
        return ft.Container(
            content=ft.Row(
                [
                    ft.Container(checkbox, width=s(28), padding=ft.Padding.only(top=s(2))),
                    ft.Column([body, ui.meta_text(c, ' · '.join(meta), max_lines=2)], spacing=s(4), expand=True, tight=True),
                    ft.Container(form_field(c, 'Destino no caderno', selector), width=s(200)),
                    more_menu(c, menu_items, tooltip='Editar fragmento ou nota'),
                ],
                spacing=s(12),
                vertical_alignment=ft.CrossAxisAlignment.START,
            ),
            padding=ft.Padding.symmetric(horizontal=s(16), vertical=s(12)),
            border=None if last else ft.Border.only(bottom=ft.BorderSide(1, c.colors['border'])),
            data=fragment['id'],
        )

    def _work_menu(self, work: CompilationWorkRecord, index: int) -> ft.PopupMenuButton:
        total = len(self.compilation['works'])
        items: list[MenuItem] = []
        if index > 0:
            items.append(('arrow-up', 'Mover para cima', lambda: self._move_work(index, -1), False))
        if index < total - 1:
            items.append(('arrow-down', 'Mover para baixo', lambda: self._move_work(index, 1), False))
        items.append(('pen', 'Editar obra', lambda: self.on_edit_work(self.compilation['id'], work['id']), False))
        if self.on_open_work is not None:
            items.append(('book', 'Abrir no Acervo', lambda: self.on_open_work(work['id']), False))
        items.append(None)
        items.append(('circle-minus', 'Retirar do projeto', lambda: self._confirm_remove_work(work), True))
        return more_menu(self.config, items, tooltip='Reordenar, editar ou retirar')

    def _compose_work(self, index: int) -> ft.Container:
        c = self.config
        work = self.compilation['works'][index]
        fragments = work['fragments']
        meta = ' · '.join(part for part in (work.get('authors') or 'Sem autoria', plural(len(fragments), 'fragmento', 'fragmentos')) if part)
        head = ft.Container(
            content=ft.Row(
                [
                    ft.Column(
                        [ui.ui_text(c, work['title'], size=13, weight=ui.W600, selectable=True), ui.meta_text(c, meta)],
                        spacing=s(2),
                        expand=True,
                        tight=True,
                    ),
                    ui.button(
                        c,
                        'Fragmento',
                        on_click=lambda _e, work_id=work['id']: self.on_create_fragment(self.compilation['id'], work_id),
                        icon_name='plus',
                        small=True,
                        tooltip='Novo fragmento desta obra',
                    ),
                    self._work_menu(work, index),
                ],
                spacing=s(8),
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding.only(left=s(16), right=s(12), top=s(8), bottom=s(8)),
            border=ft.Border.only(bottom=ft.BorderSide(1, c.colors['border'])),
        )
        rows: list[ft.Control] = [
            self._compose_fragment(fragment, last=position == len(fragments) - 1)
            for position, fragment in enumerate(fragments)
        ]
        if not rows:
            rows.append(ft.Container(ui.ui_text(c, 'Nenhum fragmento desta obra ainda.', size=13, color=c.colors['faint']), padding=s(16)))
        box = ui.card(c, [head, *rows])
        box.data = work['id']
        return box

    def _compose_works_and_fragments(self) -> ft.Control:
        c = self.config
        self.work_search = ui.search_field(
            c,
            'Adicionar obra do Acervo a este projeto',
            on_change=self._search_work_matches,
            value=self.work_search.value if getattr(self, 'work_search', None) is not None else '',
            width=None,
            expand=True,
        )
        matches_box = ft.Container(
            content=self.work_matches,
            bgcolor=c.colors['surface'],
            border=ft.Border.all(1, c.colors['border']),
            border_radius=ft.BorderRadius.all(s(8)),
            padding=s(4),
            visible=self.work_matches.visible,
        )
        self.work_matches_box = matches_box
        self.create_work_button = ui.button(
            c,
            'Criar obra',
            on_click=lambda _e: self.on_create_work(self.compilation['id']),
            icon_name='plus',
        )
        controls: list[ft.Control] = [
            ft.Row(
                [ft.Column([ft.Row([self.work_search]), matches_box], spacing=s(4), expand=True, tight=True), self.create_work_button],
                spacing=s(8),
                vertical_alignment=ft.CrossAxisAlignment.START,
            )
        ]
        if not self.compilation['works']:
            controls.append(
                ui.empty_state(
                    c,
                    'book',
                    'Nenhuma obra neste projeto',
                    'Adicione uma obra do Acervo pela busca acima ou crie uma nova para começar a reunir fontes.',
                )
            )
        else:
            controls.extend(self._compose_work(index) for index in range(len(self.compilation['works'])))
        self.works_column = ft.Column(controls, spacing=s(12), tight=True)
        return ft.Container(
            max_width_box(c, self.works_column, 1040),
            padding=ft.Padding.only(left=s(32), right=s(32), top=s(24), bottom=s(48)),
        )

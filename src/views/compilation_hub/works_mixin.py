"""Aba Obras e fragmentos: obras do projeto e o que entra no caderno.

Um card recolhível por obra e uma linha por fragmento, com inclusão no
caderno, alocação por busca e arrasto para o roteiro lateral. Atualizações de
dados preservam as colunas roláveis para não devolver a tela ao início.
"""

import flet as ft

from src.contracts import CompilationFragmentRecord, CompilationWorkRecord
from src.utils.fa import fa_icon
from src.utils.fragment_reference import fragment_abnt_notation
from src.views import ui_kit as ui
from src.views.ui_kit import s
from .caderno_common import FRAGMENT_DRAG_GROUP
from .common import (
    MenuItem,
    close_dialog,
    dialog,
    max_width_box,
    more_menu,
    open_dialog,
    plural,
)
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
            collapsed = getattr(self, '_collapsed_works', None)
            if collapsed is not None:
                collapsed.add(bib_res_id)
            self.refresh()

    def _remove_work(self, bib_res_id: int) -> None:
        if self.on_remove_work(self.compilation['id'], bib_res_id):
            collapsed = getattr(self, '_collapsed_works', None)
            if collapsed is not None:
                collapsed.discard(bib_res_id)
            self.refresh()

    def _confirm_remove_work(self, work: CompilationWorkRecord) -> ft.AlertDialog:
        c = self.config

        def confirm(_event=None) -> None:
            close_dialog(self.page)
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
                ui.button(c, 'Cancelar', on_click=lambda _e: close_dialog(self.page), variant='ghost'),
                ui.button(c, 'Retirar obra', on_click=confirm, variant='danger', icon_name='circle-minus'),
            ],
            width=440,
        )
        modal.data = {'confirm': confirm}
        open_dialog(self.page, modal)
        return modal

    def _move_work(self, index: int, offset: int) -> None:
        work_ids = [work['id'] for work in self.compilation['works']]
        target_index = index + offset
        if target_index < 0 or target_index >= len(work_ids):
            return
        work_ids[index], work_ids[target_index] = work_ids[target_index], work_ids[index]
        if self.on_reorder_works(self.compilation['id'], work_ids):
            self.refresh()

    def _toggle_membership(
        self,
        fragment_id: int,
        selected: bool,
        current_section_id: int | None = None,
    ) -> None:
        self._set_fragment_destination(
            fragment_id,
            'unassigned' if selected else 'not_selected',
            current_section_id=current_section_id,
        )

    # ── composição ─────────────────────────────────────────

    def _sync_work_collapse_state(self) -> None:
        current = {work['id'] for work in self.compilation['works']}
        known = getattr(self, '_known_work_ids', None)
        if known is None:
            self._known_work_ids = set(current)
            self._collapsed_works = set(current)
            return
        for new_id in current - known:
            self._collapsed_works.add(new_id)
        self._known_work_ids = current

    def _work_collapsed(self, work_id: int) -> bool:
        collapsed = getattr(self, '_collapsed_works', None)
        if collapsed is None:
            self._sync_work_collapse_state()
            collapsed = self._collapsed_works
        return work_id in collapsed

    def _toggle_work_collapse(self, work_id: int) -> None:
        state = getattr(self, 'work_hosts', {}).get(work_id)
        if work_id in self._collapsed_works:
            self._collapsed_works.discard(work_id)
            collapsed = False
        else:
            self._collapsed_works.add(work_id)
            collapsed = True
        if state is None:
            self.refresh()
            return
        state['body'].content = (
            ft.Container(height=0)
            if collapsed
            else ft.Column(state['rows'], spacing=0, tight=True)
        )
        state['chevron'].rotate = 0 if collapsed else 3.141592653589793 / 2
        state['card'].data = {'work_id': work_id, 'collapsed': collapsed}
        for control in (state['body'], state['chevron']):
            try:
                control.update()
            except Exception:
                pass

    def _on_works_scroll(self, event) -> None:
        self.works_scroll_offset = float(getattr(event, 'pixels', 0) or 0)

    def _refresh_works_in_place(self) -> bool:
        """Atualiza os filhos sem destruir os controles que detêm a rolagem."""
        if self.selected_tab != 'obras' or self.root is None:
            return False
        current_scroll = getattr(self, 'works_scroll', None)
        current_outline = getattr(self, 'works_outline_host', None)
        if current_scroll is None or current_outline is None:
            return False
        current_outline_scroll = current_outline.content.content
        self._compose_works_and_fragments()
        new_scroll = self.works_scroll

        # A identidade dos Columns roláveis é preservada; só seus filhos mudam.
        current_scroll.controls = list(new_scroll.controls)
        rebuilt_outline = self._compose_outline(
            on_focus=self._focus_idea_in_works,
            host=current_outline,
        )
        current_outline_scroll.controls = list(rebuilt_outline.content.controls)
        self.works_scroll = current_scroll
        self.works_outline_host = current_outline

        header_host = getattr(self, 'header_host', None)
        tab_bar_host = getattr(self, 'tab_bar_host', None)
        if header_host is not None:
            header_host.content = self._compose_header()
        if tab_bar_host is not None:
            tab_bar_host.content = self._compose_tabs()
        self.page.update()
        return True

    def _compose_fragment(
        self,
        fragment: CompilationFragmentRecord,
        section_ids: list[int],
        last: bool = False,
    ) -> ft.Container:
        c = self.config
        is_member = fragment['is_member'] or bool(section_ids)
        destination = self._destination_label(fragment)
        alloc_button = ui.button(
            c,
            destination,
            icon_name='location-dot',
            small=True,
            tooltip='Alocar em uma ou várias ideias',
            on_click=lambda _e, current=fragment: self._prompt_allocate_fragment(current),
        )
        checkbox = ft.Checkbox(
            value=is_member,
            tooltip='Incluir no caderno',
            active_color=c.colors['gold'],
            check_color=c.colors['on_gold'],
            border_side=ft.BorderSide(1, c.colors['border_strong']),
            shape=ft.RoundedRectangleBorder(radius=s(4)),
            on_change=lambda event, current_id=fragment['id']: self._toggle_membership(
                current_id,
                bool(event.control.value),
            ),
        )
        if fragment['fragment_type'] == 'quote':
            body = ui.serif_text(c, quoted(fragment['excerpt']), size=16, max_lines=3, height=1.45, align=ft.TextAlign.JUSTIFY)
        else:
            body = ui.ui_text(c, fragment['excerpt'], size=13, color=c.colors['muted'], max_lines=3, align=ft.TextAlign.JUSTIFY)
        meta = [fragment_abnt_notation(fragment)]
        if len(section_ids) > 1:
            meta.append(f'{len(section_ids)} ideias')
        elif fragment.get('work_note'):
            meta.append('com nota de articulação')
        menu_items: list[MenuItem] = [
            ('location-dot', 'Alocar em ideias…', lambda current=fragment: self._prompt_allocate_fragment(current), False),
            ('pen', 'Editar fragmento', lambda current=fragment: self.on_edit_fragment(self.compilation['id'], current), False),
            ('note-sticky', 'Editar nota de articulação' if fragment.get('work_note') else 'Adicionar nota de articulação', lambda current=fragment: self._prompt_fragment_note(current), False),
        ]
        drag = ft.Draggable(
            group=FRAGMENT_DRAG_GROUP,
            data=fragment['id'],
            content=ft.Container(
                fa_icon('grip-vertical', size=s(12), color=c.colors['faint']),
                width=s(16),
                alignment=ft.Alignment.CENTER,
                tooltip='Arraste para uma ideia no roteiro',
            ),
            content_feedback=ft.Container(
                ui.ui_text(c, fragment['excerpt'][:80], size=12, max_lines=2, color=c.colors['text']),
                width=s(240),
                padding=s(10),
                bgcolor=c.colors['surface'],
                border=ft.Border.all(1, c.colors['gold']),
                border_radius=ft.BorderRadius.all(s(6)),
            ),
        )
        normal_border = None if last else ft.Border.only(bottom=ft.BorderSide(1, c.colors['border']))
        row = ft.Container(
            content=ft.Row(
                [
                    ft.Container(checkbox, width=s(28), padding=ft.Padding.only(top=s(2))),
                    drag,
                    ft.Column([body, ui.meta_text(c, ' · '.join(meta), max_lines=2)], spacing=s(4), expand=True, tight=True),
                    ft.Container(alloc_button, width=s(184)),
                    more_menu(c, menu_items, tooltip='Alocar, editar fragmento ou nota'),
                ],
                spacing=s(10),
                vertical_alignment=ft.CrossAxisAlignment.START,
            ),
            padding=ft.Padding.symmetric(horizontal=s(16), vertical=s(12)),
            border=normal_border,
            animate=ui.motion(ui.MOTION_FAST),
            data=fragment['id'],
        )

        def _hover(event) -> None:
            hovering = event.data in (True, 'true')
            row.bgcolor = c.colors['card_hover'] if hovering else None
            try:
                row.update()
            except Exception:
                pass

        row.on_hover = _hover
        return row

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
        self._sync_work_collapse_state()
        work = self.compilation['works'][index]
        entries = self._unique_work_fragments(work)
        collapsed = self._work_collapsed(work['id'])
        meta = ' · '.join(part for part in (work.get('authors') or 'Sem autoria', plural(len(entries), 'fragmento', 'fragmentos')) if part)
        chevron_btn = ui.icon_button(
            c,
            'chevron-right',
            on_click=lambda _e, work_id=work['id']: self._toggle_work_collapse(work_id),
            tooltip='Expandir fragmentos' if collapsed else 'Recolher fragmentos',
            size=22,
        )
        chevron = chevron_btn.content
        chevron.animate_rotation = ui.motion(ui.MOTION_BASE)
        chevron.rotate = 0 if collapsed else 3.141592653589793 / 2
        title_text = ui.serif_text(
            c,
            work['title'],
            size=18.5,
            weight=ui.W600,
            max_lines=1,
            selectable=True,
        )
        title_host = ft.Container(
            content=ft.Column(
                [title_text, ui.meta_text(c, meta)],
                spacing=s(2),
                expand=True,
                tight=True,
            ),
            padding=ft.Padding.symmetric(vertical=s(2)),
            expand=True,
        )
        head = ft.Container(
            content=ft.Row(
                [
                    chevron_btn,
                    title_host,
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
            padding=ft.Padding.only(left=s(12), right=s(12), top=s(8), bottom=s(8)),
            border=ft.Border.only(bottom=ft.BorderSide(1, c.colors['border'])),
        )
        rows: list[ft.Control] = [
            self._compose_fragment(fragment, section_ids, last=position == len(entries) - 1)
            for position, (fragment, section_ids) in enumerate(entries)
        ]
        if not rows:
            rows.append(ft.Container(ui.ui_text(c, 'Nenhum fragmento desta obra ainda.', size=13, color=c.colors['faint']), padding=s(16)))
        body = ft.Container(
            content=ft.Container(height=0) if collapsed else ft.Column(rows, spacing=0, tight=True),
            animate_size=ui.motion(ui.MOTION_BASE),
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        )
        box = ui.card(c, [head, body], interactive=True)
        box.data = {'work_id': work['id'], 'collapsed': collapsed}
        hosts = getattr(self, 'work_hosts', None)
        if hosts is None:
            hosts = self.work_hosts = {}
        hosts[work['id']] = {
            'body': body,
            'rows': rows,
            'chevron': chevron,
            'card': box,
        }
        return box

    def _compose_works_and_fragments(self) -> ft.Control:
        c = self.config
        self._sync_work_collapse_state()
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
        list_body = ft.Container(
            max_width_box(c, self.works_column, 1040),
            padding=ft.Padding.only(left=s(32), right=s(32), top=s(24), bottom=s(48)),
        )
        self.works_scroll = ft.Column(
            [list_body],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            on_scroll=self._on_works_scroll,
        )
        self.works_outline_host = ft.Container()
        self.works_outline_host.content = self._compose_outline(
            on_focus=self._focus_idea_in_works,
            host=self.works_outline_host,
        )
        return ft.Row(
            [
                self.works_outline_host,
                ft.Container(self.works_scroll, expand=True),
            ],
            spacing=0,
            expand=True,
            vertical_alignment=ft.CrossAxisAlignment.STRETCH,
        )

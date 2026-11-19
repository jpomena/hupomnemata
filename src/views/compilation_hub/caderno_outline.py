"""CadernoOutlineMixin extraído de ``caderno_mixin.py``.

Movimentação literal: sem ``__init__``, colabora com o hub via ``self``.
"""

from collections.abc import Callable

import flet as ft

from src.contracts import CompilationSectionRecord
from src.utils.fa import fa_icon
from src.views import ui_kit as ui
from src.views.ui_kit import s
from .caderno_common import QUEUE_KEY


class CadernoOutlineMixin:
    """Coluna de roteiro: navegação, colapso e foco das ideias."""

    def _nav_head(
        self,
        label: str,
        trailing: ft.Control | None = None,
        is_collapsed: bool = False,
        on_toggle: Callable | None = None,
    ) -> ft.Container:
        c = self.config
        label_ctrl = ui.ui_text(c, label, size=12, weight=ui.W600, color=c.colors['faint'])
        if on_toggle:
            chevron = ui.icon_button(
                c,
                'chevron-right' if is_collapsed else 'chevron-down',
                on_click=on_toggle,
                tooltip='Expandir seção' if is_collapsed else 'Recolher seção',
                size=18,
                small=True,
            )
            title_part = ft.Row([chevron, label_ctrl], spacing=s(2), vertical_alignment=ft.CrossAxisAlignment.CENTER)
        else:
            title_part = label_ctrl

        return ft.Container(
            content=ft.Row(
                [title_part] + ([trailing] if trailing else []),
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            height=s(26),
            padding=ft.Padding.only(left=s(2) if on_toggle else s(8), right=s(2)),
        )

    def _outline_chapter_item(
        self,
        chap_idx: int,
        chapter: CompilationSectionRecord,
        has_children: bool,
        is_collapsed: bool,
        active: bool,
        frag_count: int,
    ) -> ft.Container:
        c = self.config

        if has_children:
            chevron = ui.icon_button(
                c,
                'chevron-right' if is_collapsed else 'chevron-down',
                on_click=lambda _e, sid=chapter['id']: self._toggle_outline_chapter(sid),
                tooltip='Expandir argumentos' if is_collapsed else 'Recolher argumentos',
                size=18,
                small=True,
            )
        else:
            chevron = ft.Container(width=s(18))

        row = ft.Row(
            [
                chevron,
                ft.Container(
                    ui.ui_text(
                        c,
                        str(chap_idx + 1),
                        size=12,
                        weight=ui.W600,
                        color=c.colors['gold'] if active else c.colors['faint'],
                        tabular=True,
                    ),
                    width=s(16),
                ),
                ui.ui_text(
                    c,
                    chapter['title'],
                    size=13,
                    weight=ui.W600 if active else ui.W500,
                    color=c.colors['text'] if active else c.colors['muted'],
                    expand=True,
                ),
                ui.ui_text(c, str(frag_count), size=12, color=c.colors['faint'], tabular=True),
            ],
            spacing=s(4),
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        box = ui.hover_surface(
            c,
            row,
            on_click=lambda _e, sid=chapter['id']: self._focus_idea(sid),
            selected=active,
            padding=ft.Padding.symmetric(horizontal=s(6)),
            height=s(30),
        )
        box.data = chapter['title']
        return box

    def _toggle_outline_chapter(self, sid: int) -> None:
        """Alterna recolhimento de um capítulo na árvore do roteiro."""
        collapsed = self._collapsed_set()
        if sid in collapsed:
            collapsed.discard(sid)
        else:
            collapsed.add(sid)
        if getattr(self, 'outline_host', None) is not None:
            self.outline_host.content = self._compose_outline()
            self.page.update()
        elif hasattr(self, '_render'):
            self._render()

    def _toggle_outline_roteiro(self, _e=None) -> None:
        """Alterna recolhimento do bloco inteiro do Roteiro."""
        self._outline_roteiro_collapsed = not getattr(self, '_outline_roteiro_collapsed', False)
        if getattr(self, 'outline_host', None) is not None:
            self.outline_host.content = self._compose_outline()
            self.page.update()

    def _toggle_outline_fila(self, _e=None) -> None:
        """Alterna recolhimento do bloco inteiro da Fila."""
        self._outline_fila_collapsed = not getattr(self, '_outline_fila_collapsed', False)
        if getattr(self, 'outline_host', None) is not None:
            self.outline_host.content = self._compose_outline()
            self.page.update()

    def _outline_item(
        self,
        lead: ft.Control,
        title: str,
        count: int,
        active: bool,
        on_click: Callable,
    ) -> ft.Container:
        c = self.config
        row = ft.Row(
            [
                ft.Container(lead, width=s(20)),
                ui.ui_text(c, title, size=13, weight=ui.W600 if active else ui.W500, color=c.colors['text'] if active else c.colors['muted'], expand=True),
                ui.ui_text(c, str(count), size=12, color=c.colors['faint'], tabular=True),
            ],
            spacing=s(6),
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        box = ui.hover_surface(c, row, on_click=on_click, selected=active, padding=ft.Padding.symmetric(horizontal=s(8)), height=s(30))
        box.data = title
        return box

    def _compose_outline(self) -> ft.Container:
        c = self.config
        chapters = self._root_chapters()
        items: list[ft.Control] = []
        for chap_idx, chapter in enumerate(chapters):
            active = self.active_section_id == chapter['id']
            frag_count = len(self._section_fragments(chapter['id']))
            children = self._child_sections(chapter['id'])
            has_children = bool(children)
            is_collapsed = chapter['id'] in self._collapsed_set()

            items.append(
                self._outline_chapter_item(
                    chap_idx=chap_idx,
                    chapter=chapter,
                    has_children=has_children,
                    is_collapsed=is_collapsed,
                    active=active,
                    frag_count=frag_count,
                )
            )

            # Argumentos subordinados: exibidos apenas quando o capítulo pai estiver expandido
            if not is_collapsed:
                for child_idx, child in enumerate(children):
                    child_active = self.active_section_id == child['id']
                    child_count = len(self._section_fragments(child['id']))
                    items.append(
                        ft.Container(
                            self._outline_item(
                                ui.ui_text(
                                    c,
                                    f"{chap_idx + 1}.{child_idx + 1}",
                                    size=11,
                                    weight=ui.W600,
                                    color=c.colors['gold'] if child_active else c.colors['faint'],
                                    tabular=True,
                                ),
                                child['title'],
                                child_count,
                                child_active,
                                lambda _e, sid=child['id']: self._focus_idea(sid),
                            ),
                            padding=ft.Padding.only(left=s(20)),
                            data=child['title'],
                        )
                    )
        if not chapters:
            items.append(
                ft.Container(
                    ui.meta_text(c, 'Nenhum capítulo ainda.'),
                    padding=ft.Padding.symmetric(horizontal=s(8), vertical=s(6)),
                )
            )
        queue_active = self.active_section_id == QUEUE_KEY
        queue = self._outline_item(
            fa_icon('inbox', size=s(12), color=c.colors['gold'] if queue_active else c.colors['faint']),
            'A organizar',
            len(self._unassigned_fragments()),
            queue_active,
            lambda _e: self._focus_idea(QUEUE_KEY),
        )
        self.outline_items = items
        self.queue_item = queue

        roteiro_collapsed = getattr(self, '_outline_roteiro_collapsed', False)
        fila_collapsed = getattr(self, '_outline_fila_collapsed', False)

        roteiro_head = self._nav_head(
            'Roteiro',
            trailing=ui.icon_button(
                c,
                'plus',
                on_click=lambda _e: self._prompt_new_section(),
                tooltip='Novo capítulo ou argumento',
                size=22,
            ),
            is_collapsed=roteiro_collapsed,
            on_toggle=self._toggle_outline_roteiro,
        )

        fila_head = self._nav_head(
            'Fila',
            is_collapsed=fila_collapsed,
            on_toggle=self._toggle_outline_fila,
        )

        return ft.Container(
            content=ft.Column(
                [
                    ft.Column(
                        [roteiro_head] + ([] if roteiro_collapsed else items),
                        spacing=s(1),
                        tight=True,
                    ),
                    ft.Column(
                        [fila_head] + ([] if fila_collapsed else [queue]),
                        spacing=s(1),
                        tight=True,
                    ),
                    ft.Container(
                        ui.ui_text(
                            c,
                            'Estrutura em capítulos e argumentos. Fragmentos podem ser vinculados a mais de uma ideia.',
                            size=12,
                            color=c.colors['faint'],
                            max_lines=None,
                        ),
                        padding=ft.Padding.symmetric(horizontal=s(8)),
                    ),
                ],
                spacing=s(16),
                scroll=ft.ScrollMode.AUTO,
                expand=True,
            ),
            width=s(248),
            bgcolor=c.colors['chrome'],
            padding=ft.Padding.symmetric(horizontal=s(12), vertical=s(16)),
            border=ft.Border.only(right=ft.BorderSide(1, c.colors['border'])),
        )

    def _focus_idea(self, key: int | str) -> None:
        uncollapsed = False
        if isinstance(key, int):
            if key in self._collapsed_set():
                self._collapsed_set().discard(key)
                uncollapsed = True
            target_sec = next(
                (s for s in self.compilation.get('sections', []) if s['id'] == key),
                None,
            )
            if target_sec and target_sec.get('parent_id'):
                parent_id = target_sec['parent_id']
                if parent_id in self._collapsed_set():
                    self._collapsed_set().discard(parent_id)
                    uncollapsed = True

        self.active_section_id = key
        if self.selected_tab != 'caderno' or uncollapsed:
            self.selected_tab = 'caderno'
            self._render()
        elif getattr(self, 'outline_host', None) is not None:
            self.outline_host.content = self._compose_outline()
            self.page.update()
        self._scroll_writing(f'idea-{key}')

    def _scroll_writing(self, key: str) -> None:
        column = getattr(self, 'writing_column', None)
        run_task = getattr(self.page, 'run_task', None)
        if column is None or run_task is None:
            return

        async def scroll() -> None:
            try:
                await column.scroll_to(scroll_key=key, duration=250)
            except Exception:
                pass

        try:
            run_task(scroll)
        except Exception:
            pass

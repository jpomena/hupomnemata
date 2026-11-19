"""CadernoWritingMixin extraído de ``caderno_mixin.py``.

Movimentação literal: sem ``__init__``, colabora com o hub via ``self``.
"""

import flet as ft

from src.contracts import (
    CompilationFragmentRecord,
    CompilationSectionRecord,
)
from src.utils.fa import fa_icon
from src.utils.fragment_reference import fragment_abnt_notation
from src.utils.reference_disambiguation import (
    apply_year_suffix_to_view_reference,
    build_disambiguated_references,
    extract_work_year,
)
from src.views import ui_kit as ui
from src.views.ui_kit import s
from .caderno_common import QUEUE_KEY, kind_label, quoted
from .common import MenuItem, more_menu, plural, reference_text


class CadernoWritingMixin:
    """Coluna de escrita: blocos de fragmento, ideias e lateral."""

    def _caderno_text(self, with_references: bool = False) -> str:
        lines = [self.compilation['name']]
        year_suffixes = self._year_suffixes()
        chapters = self._root_chapters()
        for chapter in chapters:
            lines.extend(('', f"## {chapter['title']}", ''))
            if chapter['central_idea']:
                lines.extend((chapter['central_idea'], ''))
            for fragment in self._section_fragments(chapter['id']):
                year_override = year_suffixes.get(fragment['bib_res_id'])
                notation = fragment_abnt_notation(
                    fragment, display_year_override=year_override
                )
                lines.extend((
                    f"{kind_label(fragment)}: {fragment['excerpt']}",
                    notation,
                ))
                if fragment['work_note']:
                    lines.append(f"Nota de articulação: {fragment['work_note']}")
                lines.append('')
            children = self._child_sections(chapter['id'])
            for child in children:
                lines.extend(('', f"### {child['title']}", ''))
                if child['central_idea']:
                    lines.extend((child['central_idea'], ''))
                for fragment in self._section_fragments(child['id']):
                    year_override = year_suffixes.get(fragment['bib_res_id'])
                    notation = fragment_abnt_notation(
                        fragment, display_year_override=year_override
                    )
                    lines.extend((
                        f"{kind_label(fragment)}: {fragment['excerpt']}",
                        notation,
                    ))
                    if fragment['work_note']:
                        lines.append(f"Nota de articulação: {fragment['work_note']}")
                    lines.append('')
        unassigned = self._unassigned_fragments()
        if unassigned:
            lines.extend(('', '## A organizar', ''))
            for work, fragment in unassigned:
                year_override = year_suffixes.get(fragment['bib_res_id'])
                notation = fragment_abnt_notation(
                    fragment, display_year_override=year_override
                )
                lines.extend((
                    f"### {work['title']}",
                    f"{fragment['excerpt']}",
                    notation,
                ))
                if fragment['work_note']:
                    lines.append(f"Nota de articulação: {fragment['work_note']}")
                lines.append('')
        if with_references:
            used = self._used_works()
            if used:
                references = self._work_references([work['id'] for work in used])
                lines.extend(('', '## Referências', ''))
                disambiguated = build_disambiguated_references(used, references)
                for position, text in enumerate(disambiguated, start=1):
                    lines.append(f'{position}. {text}')
        return '\n'.join(lines).strip()

    def _fragment_menu(
        self,
        fragment: CompilationFragmentRecord,
        section_id: int | None,
        index: int,
        total: int,
    ) -> ft.PopupMenuButton:
        items: list[MenuItem] = []
        if section_id is not None and total > 1:
            if index > 0:
                items.append(('arrow-up', 'Mover para cima', lambda: self._move_section_fragment(section_id, index, -1), False))
            if index < total - 1:
                items.append(('arrow-down', 'Mover para baixo', lambda: self._move_section_fragment(section_id, index, 1), False))
            items.append(None)
        for section in self._sorted_sections():
            if section['id'] == section_id:
                continue
            items.append((
                'arrow-right',
                f'Mover para “{section["title"]}”',
                lambda sid=section['id']: self._set_fragment_destination(
                    fragment['id'],
                    str(sid),
                    current_section_id=section_id,
                ),
                False,
            ))
        items.append(('plus', 'Mover para uma nova ideia', lambda: self._prompt_create_section(fragment['id']), False))
        items.append(('link', 'Vincular também a...', lambda: self._prompt_link_fragment_to_section(fragment), False))
        if section_id is not None:
            items.append((
                'inbox',
                'Devolver para A organizar',
                lambda: self._set_fragment_destination(
                    fragment['id'],
                    'unassigned',
                    current_section_id=section_id,
                ),
                False,
            ))
        items.append(None)
        items.append((
            'note-sticky',
            'Editar nota de articulação' if fragment['work_note'] else 'Adicionar nota de articulação',
            lambda: self._prompt_fragment_note(fragment, section_id=section_id),
            False,
        ))
        items.append(('pen', 'Editar fragmento', lambda: self.on_edit_fragment(self.compilation['id'], fragment), False))
        items.append(None)
        items.append((
            'circle-minus',
            'Retirar do caderno',
            lambda: self._remove_from_caderno(fragment, section_id=section_id),
            True,
        ))
        return more_menu(self.config, items, tooltip='Mover, editar ou retirar')

    def _fragment_body(self, fragment: CompilationFragmentRecord, size: float = 18) -> ft.Text:
        c = self.config
        if fragment['fragment_type'] == 'quote':
            return ui.serif_text(c, quoted(fragment['excerpt']), size=size, selectable=True, align=ft.TextAlign.JUSTIFY)
        return ui.ui_text(c, fragment['excerpt'], size=13, color=c.colors['muted'], max_lines=None, selectable=True, align=ft.TextAlign.JUSTIFY)

    def _compose_fragment_block(
        self,
        fragment: CompilationFragmentRecord,
        section_id: int | None,
        index: int,
        total: int,
    ) -> ft.Container:
        c = self.config
        work_title = ui.ui_text(c, self._work_title_of(fragment), size=12, weight=ui.W600, expand=1)
        work_title.expand_loose = True
        head = ft.Container(
            content=ft.Row(
                [
                    fa_icon('grip-vertical', size=s(12), color=c.colors['faint']),
                    work_title,
                    ui.badge(c, kind_label(fragment)),
                    ft.Container(expand=True),
                    ui.icon_button(c, 'copy', on_click=self._copy_fragment_handler(fragment), tooltip='Copiar com citação', style='regular'),
                    self._fragment_menu(fragment, section_id, index, total),
                ],
                spacing=s(8),
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            height=s(40),
            padding=ft.Padding.only(left=s(8), right=s(6)),
            border=ft.Border.only(bottom=ft.BorderSide(1, c.colors['border'])),
        )
        year_override = self._year_suffixes().get(fragment['bib_res_id'])
        body = ft.Container(
            content=ft.Column(
                [
                    self._fragment_body(fragment),
                    ui.meta_text(
                        c,
                        fragment_abnt_notation(
                            fragment, display_year_override=year_override
                        ),
                        max_lines=2,
                    ),
                ],
                spacing=s(8),
                tight=True,
            ),
            padding=ft.Padding.symmetric(horizontal=s(16), vertical=s(12)),
        )
        normal_border = ft.Border.all(1, c.colors['border'])
        hover_border = ft.Border.all(1, c.colors['border_strong'])
        box = ft.Container(
            content=ft.Column([head, body, self._compose_fragment_note(fragment)], spacing=0, tight=True),
            bgcolor=c.colors['surface'],
            border=normal_border,
            border_radius=ft.BorderRadius.all(s(8)),
            animate=ui.motion(ui.MOTION_BASE),
            data=fragment['id'],
        )

        def _hover(e: ft.ControlEvent) -> None:
            hovering = e.data in (True, 'true')
            box.bgcolor = c.colors['card_hover'] if hovering else c.colors['surface']
            box.border = hover_border if hovering else normal_border
            try:
                box.update()
            except Exception:
                pass

        box.on_hover = _hover
        return box

    def _section_menu(
        self,
        section: CompilationSectionRecord,
        index: int,
        total: int,
        is_child: bool = False,
        parent_id: int | None = None,
    ) -> ft.PopupMenuButton:
        items: list[MenuItem] = []
        if index > 0:
            items.append((
                'arrow-up',
                'Mover para cima',
                lambda: self._move_section(index, -1, parent_id=parent_id if is_child else None),
                False,
            ))
        if index < total - 1:
            items.append((
                'arrow-down',
                'Mover para baixo',
                lambda: self._move_section(index, 1, parent_id=parent_id if is_child else None),
                False,
            ))
        if is_child:
            items.append((
                'folder-tree',
                'Transferir para outro capítulo…',
                lambda: self._prompt_transfer_section(section),
                False,
            ))
        items.append(('pen', 'Renomear ou editar', lambda: self._prompt_edit_section(section), False))
        items.append(None)
        items.append(('trash-can', 'Remover ideia', lambda: self._delete_section(section['id']), True))
        return more_menu(self.config, items, tooltip='Mover, renomear ou remover')

    def _compose_child_section(
        self,
        child: CompilationSectionRecord,
        chap_idx: int,
        child_idx: int,
        total_children: int,
        parent_id: int,
    ) -> ft.Container:
        c = self.config
        fragments = self._section_fragments(child['id'])
        is_collapsed = child['id'] in self._collapsed_set()

        def toggle_collapse(_e=None) -> None:
            if is_collapsed:
                self._collapsed_set().discard(child['id'])
            else:
                self._collapsed_set().add(child['id'])
            self.refresh()

        collapse_btn = ui.icon_button(
            c,
            'chevron-right' if is_collapsed else 'chevron-down',
            on_click=toggle_collapse,
            tooltip='Expandir / Recolher argumento',
            size=20,
        )

        title_text = ui.serif_text(
            c,
            f"{chap_idx + 1}.{child_idx + 1} {child['title']}",
            size=17.5,
            weight=ui.W600,
            height=1.2,
        )
        title_row = ft.Row(
            [
                ft.Container(
                    title_text,
                    expand=True,
                ),
                collapse_btn,
                ui.icon_button(
                    c,
                    'pen',
                    on_click=lambda _e, current=child: self._prompt_edit_section(current),
                    tooltip='Editar argumento',
                ),
                self._section_menu(child, child_idx, total_children, is_child=True, parent_id=parent_id),
            ],
            spacing=s(4),
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        controls: list[ft.Control] = [title_row]
        central_idea_text = None
        if is_collapsed:
            summary = (
                plural(len(fragments), 'fragmento', 'fragmentos')
                if fragments
                else "Sem fragmentos"
            )
            controls.append(ui.meta_text(c, summary))
        else:
            if child['central_idea']:
                central_idea_text = ui.serif_text(
                    c,
                    child['central_idea'],
                    size=15,
                    height=1.35,
                    color=c.colors['text'],
                    selectable=True,
                    align=ft.TextAlign.JUSTIFY,
                    expand=True,
                )
                controls.append(
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.Container(
                                    ui.ui_text(c, 'Ideia central', size=12, color=c.colors['faint']),
                                    width=s(90),
                                ),
                                central_idea_text,
                            ],
                            spacing=s(10),
                            vertical_alignment=ft.CrossAxisAlignment.START,
                        ),
                        padding=ft.Padding.symmetric(vertical=s(6)),
                    )
                )
            if fragments:
                controls.extend(
                    self._compose_fragment_block(fragment, child['id'], position, len(fragments))
                    for position, fragment in enumerate(fragments)
                )
            else:
                controls.append(
                    ui.empty_state(
                        c,
                        'inbox',
                        'Nenhum fragmento neste argumento',
                        'Use “Vincular também a...” em fragmentos existentes ou marque fragmentos em Obras.',
                        action=ui.button(
                            c,
                            'Ir para Obras e Fragmentos',
                            on_click=lambda _e: self._select_tab('obras'),
                            small=True,
                        ),
                    )
                )
        normal_border = ft.Border(
            left=ft.BorderSide(s(2), c.colors['border_strong']),
            top=ft.BorderSide(1, c.colors['border']),
            right=ft.BorderSide(1, c.colors['border']),
            bottom=ft.BorderSide(1, c.colors['border']),
        )
        hover_border = ft.Border(
            left=ft.BorderSide(s(3), c.colors['gold']),
            top=ft.BorderSide(1, c.colors['border_strong']),
            right=ft.BorderSide(1, c.colors['border_strong']),
            bottom=ft.BorderSide(1, c.colors['border_strong']),
        )
        box = ft.Container(
            content=ft.Column(
                controls,
                spacing=s(10),
                tight=True,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
            padding=s(16),
            bgcolor=c.colors['bg'],
            border=normal_border,
            border_radius=ft.BorderRadius.all(s(8)),
            animate=ui.motion(ui.MOTION_BASE),
            key=ft.ScrollKey(f'idea-{child["id"]}'),
            data=child['id'],
        )

        def _hover(e: ft.ControlEvent) -> None:
            hovering = e.data in (True, 'true')
            box.border = hover_border if hovering else normal_border
            box.bgcolor = c.colors['card_hover'] if hovering else c.colors['bg']
            title_text.color = c.colors['gold'] if hovering else c.colors['text']
            if central_idea_text is not None:
                central_idea_text.color = c.colors['gold'] if hovering else c.colors['text']
            try:
                box.update()
            except Exception:
                pass

        box.on_hover = _hover
        return box

    def _compose_idea(
        self,
        section: CompilationSectionRecord,
        index: int,
        total: int,
    ) -> ft.Container:
        """Renderiza um capítulo principal e seus argumentos subordinados (modo foco / expansível)."""
        c = self.config
        fragments = self._section_fragments(section['id'])
        children = self._child_sections(section['id'])
        is_collapsed = section['id'] in self._collapsed_set()

        def toggle_collapse(_e=None) -> None:
            if is_collapsed:
                self._collapsed_set().remove(section['id'])
            else:
                self._collapsed_set().add(section['id'])
            self.refresh()

        collapse_btn = ui.icon_button(
            c,
            'chevron-right' if is_collapsed else 'chevron-down',
            on_click=toggle_collapse,
            tooltip='Expandir / Recolher capítulo',
            size=22,
        )

        title_row = ft.Row(
            [
                ft.Row(
                    [
                        ui.ui_text(c, str(index + 1), size=14, weight=ui.W600, color=c.colors['faint'], tabular=True),
                        ft.Container(
                            ui.serif_text(c, section['title'], size=21, weight=ui.W600, height=1.15),
                            expand=True,
                        ),
                        collapse_btn,
                    ],
                    spacing=s(10),
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    expand=True,
                ),
                ui.icon_button(
                    c,
                    'plus',
                    on_click=lambda _e, cid=section['id']: self._prompt_new_argument(cid),
                    tooltip='Novo argumento neste capítulo',
                    size=22,
                ),
                ui.icon_button(
                    c,
                    'pen',
                    on_click=lambda _e, current=section: self._prompt_edit_section(current),
                    tooltip='Editar ideia',
                ),
                self._section_menu(section, index, total, is_child=False),
            ],
            spacing=s(4),
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        controls: list[ft.Control] = [title_row]

        if is_collapsed:
            total_fragments = self._section_total_fragments(section['id'])
            summary_desc = " · ".join(
                [
                    plural(len(children), 'argumento', 'argumentos')
                    if children
                    else 'Sem argumentos',
                    plural(total_fragments, 'fragmento', 'fragmentos')
                    if total_fragments
                    else 'Sem fragmentos',
                ]
            )
            controls.append(
                ft.Container(
                    content=ui.meta_text(c, summary_desc),
                    padding=ft.Padding.only(left=s(32)),
                )
            )
        else:
            if section['central_idea']:
                controls.append(
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.Container(
                                    ui.ui_text(c, 'Ideia central', size=13, color=c.colors['faint']),
                                    width=s(104),
                                ),
                                ui.serif_text(
                                    c,
                                    section['central_idea'],
                                    size=15,
                                    height=1.35,
                                    color=c.colors['text'],
                                    selectable=True,
                                    align=ft.TextAlign.JUSTIFY,
                                    expand=True,
                                ),
                            ],
                            spacing=s(12),
                            vertical_alignment=ft.CrossAxisAlignment.START,
                        ),
                        padding=ft.Padding.symmetric(vertical=s(10)),
                        border=ft.Border.only(
                            top=ft.BorderSide(1, c.colors['border']),
                            bottom=ft.BorderSide(1, c.colors['border']),
                        ),
                    )
                )
            if fragments:
                controls.extend(
                    self._compose_fragment_block(fragment, section['id'], position, len(fragments))
                    for position, fragment in enumerate(fragments)
                )
            if children:
                for child_idx, child in enumerate(children):
                    controls.append(
                        self._compose_child_section(child, index, child_idx, len(children), section['id'])
                    )
            elif not fragments:
                controls.append(
                    ui.empty_state(
                        c,
                        'lightbulb',
                        'Nenhum fragmento nesta ideia',
                        'Adicione argumentos ou associe fragmentos a este capítulo.',
                        action=ui.button(
                            c,
                            'Ir para Obras e Fragmentos',
                            on_click=lambda _e: self._select_tab('obras'),
                            small=True,
                        ),
                    )
                )

        normal_border = ft.Border.all(1, c.colors['border'])
        hover_border = ft.Border.all(1, c.colors['border_strong'])
        box = ft.Container(
            content=ft.Column(
                controls,
                spacing=s(14),
                tight=True,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
            bgcolor=c.colors['surface'],
            border=normal_border,
            border_radius=ft.BorderRadius.all(s(8)),
            padding=s(18),
            animate=ui.motion(ui.MOTION_BASE),
            key=ft.ScrollKey(f'idea-{section["id"]}'),
            data=section['id'],
        )

        def _hover(e: ft.ControlEvent) -> None:
            hovering = e.data in (True, 'true')
            box.border = hover_border if hovering else normal_border
            try:
                box.update()
            except Exception:
                pass

        box.on_hover = _hover
        return box

    def _compose_queue(self) -> ft.Container | None:
        c = self.config
        unassigned = self._unassigned_fragments()
        if not unassigned:
            return None
        controls: list[ft.Control] = [
            ft.Row(
                [
                    fa_icon('inbox', size=s(14), color=c.colors['faint']),
                    ui.serif_text(c, 'A organizar', size=21, weight=ui.W600, height=1.15),
                    ui.ui_text(c, str(len(unassigned)), size=13, color=c.colors['faint'], tabular=True),
                ],
                spacing=s(10),
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            ui.ui_text(
                c,
                'Fragmentos do caderno ainda sem capítulo ou argumento. Use o menu de cada um para alocá-lo.',
                size=13,
                color=c.colors['muted'],
                max_lines=2,
            ),
        ]
        controls.extend(
            self._compose_fragment_block(fragment, None, position, len(unassigned))
            for position, (_work, fragment) in enumerate(unassigned)
        )
        return ft.Container(
            content=ft.Column(controls, spacing=s(12), tight=True),
            key=ft.ScrollKey(f'idea-{QUEUE_KEY}'),
            data=QUEUE_KEY,
        )

    def _compose_writing(self) -> ft.Container:
        c = self.config
        chapters = self._root_chapters()
        blocks: list[ft.Control] = [
            self._compose_idea(chapter, index, len(chapters))
            for index, chapter in enumerate(chapters)
        ]
        queue = self._compose_queue()
        if queue is not None:
            blocks.append(queue)
        if not chapters:
            blocks.insert(
                0,
                ui.empty_state(
                    c,
                    'book',
                    'Ainda não há capítulos',
                    'Crie o primeiro capítulo do roteiro de escrita para estruturar ideias e argumentos.',
                    action=ft.Row(
                        [
                            ui.button(
                                c,
                                'Novo Capítulo',
                                on_click=lambda _e: self._prompt_new_chapter(),
                                icon_name='plus',
                                small=True,
                                variant='primary',
                            ),
                            ui.button(
                                c,
                                'Ir para Obras e Fragmentos',
                                on_click=lambda _e: self._select_tab('obras'),
                                small=True,
                                variant='ghost',
                            ),
                        ],
                        spacing=s(8),
                        tight=True,
                    ),
                ),
            )
        self.writing_blocks = blocks
        self.writing_column = ft.Column(
            blocks,
            spacing=s(28),
            tight=True,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )
        scroll_wrapper = ft.Column(
            [
                ft.Container(
                    content=self.writing_column,
                    padding=ft.Padding.only(left=s(32), right=s(32), top=s(32), bottom=s(64)),
                    expand=True,
                )
            ],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )
        return ft.Container(content=scroll_wrapper, expand=True, bgcolor=c.colors['bg'])

    def _sec_head(self, label: str, count: int | None = None) -> ft.Row:
        c = self.config
        controls: list[ft.Control] = [ui.ui_text(c, label, size=12, weight=ui.W600, color=c.colors['muted'])]
        if count is not None:
            controls.append(ui.ui_text(c, str(count), size=12, color=c.colors['faint'], tabular=True))
        return ft.Row(controls, alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER, height=s(28))

    def _compose_rail(self) -> ft.Container:
        c = self.config
        used = self._used_works()
        references = self._work_references([work['id'] for work in used])
        year_suffixes = self._year_suffixes()
        reference_rows: list[ft.Control] = []
        for position, work in enumerate(used, start=1):
            reference = references.get(work['id'])
            if reference is not None and work['id'] in year_suffixes:
                orig_year = extract_work_year(work)
                if orig_year:
                    reference = apply_year_suffix_to_view_reference(
                        reference, orig_year, year_suffixes[work['id']]
                    )
            text = (
                reference_text(c, reference)
                if reference is not None
                else ui.ui_text(
                    c, work['title'], size=12, color=c.colors['muted'], max_lines=None
                )
            )
            reference_rows.append(
                ft.Row(
                    [
                        ft.Container(
                            ui.ui_text(
                                c, f'{position}.', size=12, color=c.colors['faint'], tabular=True
                            ),
                            width=s(18),
                        ),
                        ft.Container(text, expand=True),
                    ],
                    spacing=s(6),
                    vertical_alignment=ft.CrossAxisAlignment.START,
                )
            )
        if not reference_rows:
            reference_rows.append(ui.meta_text(c, 'As obras aparecem aqui quando um fragmento delas entra no caderno.', max_lines=3))

        work_rows: list[ft.Control] = []
        for work in self.compilation['works']:
            title = ui.ui_text(c, work['title'], size=13, expand=True)
            row = ft.Container(
                content=ft.Row(
                    [title, ui.meta_text(c, plural(len(work['fragments']), 'fragmento', 'fragmentos'))],
                    spacing=s(12),
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.Padding.symmetric(vertical=s(7)),
                border=ft.Border.only(bottom=ft.BorderSide(1, c.colors['border'])),
                on_click=(lambda _e, wid=work['id']: self.on_open_work(wid)) if self.on_open_work else None,
                tooltip='Abrir no Acervo' if self.on_open_work else None,
            )

            def _hover(event, text=title, box=row) -> None:
                hovering = event.data in (True, 'true')
                text.color = c.colors['gold'] if hovering else c.colors['text']
                box.update()

            if self.on_open_work:
                row.on_hover = _hover
            work_rows.append(row)
        if not work_rows:
            work_rows.append(ui.meta_text(c, 'Nenhuma obra no projeto.'))

        copy_button = ui.button(
            c,
            'Copiar esqueleto com referências',
            on_click=self._copy_caderno_with_references,
            icon_name='copy',
            icon_style='regular',
            variant='primary',
            disabled=not self._has_caderno_content(),
        )
        self.rail_copy_button = copy_button
        return ft.Container(
            content=ft.Column(
                [
                    copy_button,
                    ft.Column([self._sec_head('Referências', len(used)), ft.Column(reference_rows, spacing=s(12), tight=True)], spacing=s(8), tight=True),
                    ft.Column([self._sec_head('Obras do projeto', len(self.compilation['works'])), ft.Column(work_rows, spacing=0, tight=True)], spacing=s(8), tight=True),
                ],
                spacing=s(24),
                scroll=ft.ScrollMode.AUTO,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                expand=True,
            ),
            width=s(320),
            bgcolor=c.colors['surface'],
            padding=s(16),
            border=ft.Border.only(left=ft.BorderSide(1, c.colors['border'])),
        )

    def _compose_caderno(self) -> ft.Row:
        if self.active_section_id is None:
            sections = self._sorted_sections()
            if sections:
                self.active_section_id = sections[0]['id']
            elif self._unassigned_fragments():
                self.active_section_id = QUEUE_KEY
        self.outline_host = ft.Container()
        self.outline_host.content = self._compose_outline(
            on_focus=self._focus_idea,
            host=self.outline_host,
        )
        self._restore_outline_scroll(self.outline_host)
        controls: list[ft.Control] = [self.outline_host, self._compose_writing()]
        if getattr(self, 'show_rail', False):
            self.rail_host = self._compose_rail()
            self.rail_host.clip_behavior = ft.ClipBehavior.ANTI_ALIAS
            self.rail_host.animate = ui.motion(ui.MOTION_SLOW)
            self.rail_host.animate_opacity = ui.fade(ui.MOTION_SLOW)
            controls.append(self.rail_host)
        self.caderno_row = ft.Row(
            controls,
            spacing=0,
            expand=True,
            vertical_alignment=ft.CrossAxisAlignment.STRETCH,
        )
        return self.caderno_row

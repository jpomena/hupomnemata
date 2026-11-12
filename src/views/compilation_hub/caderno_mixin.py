"""Aba Caderno de trabalho: roteiro, escrita e lateral de referências.

Três colunas, como no protótipo (``caderno`` em ``design/prototype/index.html``):

* **Roteiro** (248, fundo ``chrome``): ideias numeradas com contagem de
  fragmentos, a ideia ativa em destaque, o botão ``+`` de nova ideia e a fila
  “A organizar”.
* **Escrita** (até 700, centralizada): cada ideia com número, título em
  Cormorant 24, linha “Ideia central” e os blocos de fragmento.
* **Lateral** (320, fundo ``surface``): copiar o esqueleto com referências,
  referências ABNT numeradas das obras usadas e a lista de obras do projeto.

Reordenar ideias e fragmentos fica nos menus ``⋯`` (mover para cima e para
baixo); ainda não há arrastar e soltar.
"""

from collections.abc import Callable

import flet as ft

from src.contracts import (
    CompilationFragmentRecord,
    CompilationSectionRecord,
    CompilationWorkRecord,
)
from src.utils.clipboard import copy_references
from src.utils.fa import fa_icon
from src.utils.fragment_reference import fragment_abnt_notation
from src.utils.reference_disambiguation import (
    apply_year_suffix_to_view_reference,
    build_disambiguated_references,
    build_disambiguated_view_references,
    compute_year_suffixes,
    extract_work_year,
    reference_plain_text,
)
from src.views import ui_kit as ui
from src.views.ui_kit import s
from .common import (
    MenuItem,
    dialog,
    form_field,
    max_width_box,
    more_menu,
    plural,
    reference_text,
    text_input,
)

QUEUE_KEY = 'queue'


def kind_label(fragment: CompilationFragmentRecord) -> str:
    return 'Citação' if fragment['fragment_type'] == 'quote' else 'Paráfrase'


def quoted(text: str) -> str:
    text = (text or '').strip()
    return text if text[:1] in '“"«' else f'“{text}”'


class CompilationHubCadernoMixin:
    """Ideias (seções), ordem dos fragmentos e o texto do esqueleto."""

    # ── dados ──────────────────────────────────────────────

    def _sorted_sections(self) -> list[CompilationSectionRecord]:
        return sorted(
            self.compilation['sections'],
            key=lambda section: (section['position'], section['id']),
        )

    def _all_fragments(self) -> list[tuple[CompilationWorkRecord, CompilationFragmentRecord]]:
        return [
            (work, fragment)
            for work in self.compilation['works']
            for fragment in work['fragments']
        ]

    def _find_fragment(self, fragment_id: int) -> CompilationFragmentRecord | None:
        return next(
            (fragment for _work, fragment in self._all_fragments() if fragment['id'] == fragment_id),
            None,
        )

    def _work_title_of(self, fragment: CompilationFragmentRecord) -> str:
        for work, current in self._all_fragments():
            if current['id'] == fragment['id']:
                return work['title']
        return fragment.get('work_title') or ''

    def _member_count(self) -> int:
        return sum(1 for _work, fragment in self._all_fragments() if fragment['is_member'])

    def _has_caderno_content(self) -> bool:
        return bool(self.compilation['sections']) or self._member_count() > 0

    def _section_fragments(self, section_id: int) -> list[CompilationFragmentRecord]:
        fragments = [
            fragment
            for _work, fragment in self._all_fragments()
            if fragment['is_member'] and fragment['section_id'] == section_id
        ]
        return sorted(
            fragments,
            key=lambda fragment: (
                fragment['project_position']
                if fragment['project_position'] is not None
                else fragment['id']
            ),
        )

    def _unassigned_fragments(self) -> list[tuple[CompilationWorkRecord, CompilationFragmentRecord]]:
        return [
            (work, fragment)
            for work, fragment in self._all_fragments()
            if fragment['is_member'] and fragment['section_id'] is None
        ]

    def _used_works(self) -> list[CompilationWorkRecord]:
        """Obras com pelo menos um fragmento no caderno, na ordem do projeto."""
        return [
            work
            for work in self.compilation['works']
            if any(fragment['is_member'] for fragment in work['fragments'])
        ]

    def _work_references(self, work_ids: list[int]) -> dict:
        if not work_ids or self.work_references is None:
            return {}
        try:
            return self.work_references(work_ids) or {}
        except Exception:
            return {}

    # ── ações: ideias ──────────────────────────────────────

    def _create_section(
        self,
        title: str,
        central_idea: str | None,
        after_create: Callable[[int], None] | None = None,
    ) -> int | None:
        section_id = self.on_create_section(
            self.compilation['id'],
            title or '',
            central_idea,
        )
        if section_id is not None:
            if after_create is not None:
                after_create(section_id)
            self.active_section_id = section_id
            self.refresh()
        return section_id

    def _update_section(self, section_id: int, title: str, central_idea: str | None) -> bool:
        if self.on_update_section(self.compilation['id'], section_id, title, central_idea):
            self.refresh()
            return True
        return False

    def _delete_section(self, section_id: int) -> None:
        sections = self._sorted_sections()
        index = next((i for i, item in enumerate(sections) if item['id'] == section_id), None)
        if index is None:
            return
        section = sections[index]
        fragment_ids = [fragment['id'] for fragment in self._section_fragments(section_id)]
        if not self.on_delete_section(self.compilation['id'], section_id):
            return
        if self.active_section_id == section_id:
            self.active_section_id = None
        self.refresh()
        ui.toast(
            self.page,
            self.config,
            f'Ideia “{section["title"]}” removida. Os fragmentos voltaram para A organizar.',
            icon_name='trash-can',
            on_undo=lambda: self._restore_section(section, index, fragment_ids),
        )

    def _restore_section(
        self,
        section: CompilationSectionRecord,
        index: int,
        fragment_ids: list[int],
    ) -> None:
        """Desfaz a remoção: recria a ideia na mesma posição, com os mesmos fragmentos."""
        compilation_id = self.compilation['id']
        new_id = self.on_create_section(compilation_id, section['title'], section['central_idea'])
        if new_id is None:
            return
        for fragment_id in fragment_ids:
            self.on_assign_fragment_to_section(compilation_id, fragment_id, new_id)
        if len(fragment_ids) > 1:
            self.on_reorder_section_fragments(compilation_id, new_id, fragment_ids)
        self._reload()
        order = [item['id'] for item in self._sorted_sections() if item['id'] != new_id]
        order.insert(min(index, len(order)), new_id)
        if len(order) > 1:
            self.on_reorder_sections(compilation_id, order)
        self.active_section_id = new_id
        self.refresh()

    def _move_section(self, index: int, offset: int) -> None:
        sections = self._sorted_sections()
        target_index = index + offset
        if target_index < 0 or target_index >= len(sections):
            return
        section_ids = [section['id'] for section in sections]
        section_ids[index], section_ids[target_index] = section_ids[target_index], section_ids[index]
        if self.on_reorder_sections(self.compilation['id'], section_ids):
            self.refresh()

    # ── ações: fragmentos ──────────────────────────────────

    def _move_section_fragment(self, section_id: int, current_index: int, offset: int) -> None:
        if not any(item['id'] == section_id for item in self.compilation['sections']):
            return
        members = self._section_fragments(section_id)
        target_index = current_index + offset
        if not (0 <= current_index < len(members)) or not (0 <= target_index < len(members)):
            return
        fragment_ids = [fragment['id'] for fragment in members]
        fragment_ids[current_index], fragment_ids[target_index] = fragment_ids[target_index], fragment_ids[current_index]
        if self.on_reorder_section_fragments(self.compilation['id'], section_id, fragment_ids):
            self.refresh()

    def _set_fragment_destination(self, fragment_id: int, destination: str) -> None:
        """Destinos: ``not_selected`` (fora do caderno), ``unassigned``
        (A organizar), o id de uma ideia ou ``create_section`` (nova ideia)."""
        if destination == 'create_section':
            self._prompt_create_section(fragment_id)
            return
        if destination == 'not_selected':
            if self.on_fragment_membership(self.compilation['id'], fragment_id, False):
                self.refresh()
            return
        section_id = None if destination == 'unassigned' else int(destination)
        fragment = self._find_fragment(fragment_id)
        if fragment is None:
            return
        if not fragment['is_member']:
            if not self.on_fragment_membership(self.compilation['id'], fragment_id, True):
                return
        if section_id is None and not fragment['is_member']:
            self.refresh()
            return
        if self.on_assign_fragment_to_section(self.compilation['id'], fragment_id, section_id):
            self.refresh()
        elif not fragment['is_member']:
            self.refresh()

    def _remove_from_caderno(self, fragment: CompilationFragmentRecord) -> None:
        previous = str(fragment['section_id']) if fragment['section_id'] is not None else 'unassigned'
        if not self.on_fragment_membership(self.compilation['id'], fragment['id'], False):
            return
        self.refresh()
        ui.toast(
            self.page,
            self.config,
            'Fragmento retirado do caderno. A nota de articulação foi mantida.',
            icon_name='circle-minus',
            on_undo=lambda: self._set_fragment_destination(fragment['id'], previous),
        )

    def _year_suffixes(self) -> dict[int, str]:
        is_caderno = getattr(self, 'selected_tab', 'caderno') == 'caderno'
        works = self._used_works() if is_caderno else self.compilation['works']
        return compute_year_suffixes(works)

    async def _copy_fragment(self, fragment: CompilationFragmentRecord) -> None:
        year_override = self._year_suffixes().get(fragment['bib_res_id'])
        notation = fragment_abnt_notation(
            fragment, display_year_override=year_override
        )
        text = f"{quoted(fragment['excerpt']) if fragment['fragment_type'] == 'quote' else fragment['excerpt']} {notation}"
        try:
            await self.page.clipboard.set(text)
        except Exception:
            return
        ui.toast(self.page, self.config, 'Fragmento copiado com a citação.', icon_name='copy')

    def _copy_fragment_handler(self, fragment: CompilationFragmentRecord) -> Callable:
        async def handler(_event=None) -> None:
            await self._copy_fragment(fragment)

        return handler

    # ── diálogos ───────────────────────────────────────────

    def _section_dialog(
        self,
        title: str,
        confirm_label: str,
        on_confirm: Callable[[str, str | None], None],
        section: CompilationSectionRecord | None = None,
        subtitle: str | None = None,
    ) -> ft.AlertDialog:
        c = self.config
        title_field = text_input(c, value=section['title'] if section else '', hint='Ex.: Argumento central', max_length=150, autofocus=True)
        idea_field = text_input(
            c,
            value=(section['central_idea'] or '') if section else '',
            hint='Que papel esta ideia terá no texto?',
            multiline=True,
            min_lines=2,
            max_lines=5,
            max_length=2000,
        )

        def confirm(_event=None) -> None:
            value = (title_field.value or '').strip()
            if not value:
                title_field.error_text = 'Dê um nome à ideia.'
                try:
                    title_field.update()
                except Exception:
                    pass
                return
            idea = (idea_field.value or '').strip() or None
            self.page.pop_dialog()
            on_confirm(value, idea)

        title_field.on_submit = confirm
        modal = dialog(
            c,
            title,
            [form_field(c, 'Nome da ideia', title_field), form_field(c, 'Ideia central (opcional)', idea_field)],
            [
                ui.button(c, 'Cancelar', on_click=lambda _e: self.page.pop_dialog(), variant='ghost'),
                ui.button(c, confirm_label, on_click=confirm, variant='primary'),
            ],
            subtitle=subtitle,
        )
        modal.data = {'title': title_field, 'idea': idea_field, 'confirm': confirm}
        self.page.show_dialog(modal)
        return modal

    def _prompt_new_section(self) -> ft.AlertDialog:
        return self._section_dialog(
            'Nova ideia',
            'Criar ideia',
            lambda title, idea: self._create_section(title, idea),
            subtitle='A ideia entra no fim do roteiro.',
        )

    def _prompt_edit_section(self, section: CompilationSectionRecord) -> ft.AlertDialog:
        return self._section_dialog(
            'Editar ideia',
            'Salvar ideia',
            lambda title, idea: self._update_section(section['id'], title, idea),
            section=section,
        )

    def _prompt_create_section(self, fragment_id: int) -> ft.AlertDialog:
        def create(title: str, idea: str | None) -> None:
            def assign(section_id: int) -> None:
                fragment = self._find_fragment(fragment_id)
                if fragment is None:
                    return
                ready = fragment['is_member'] or self.on_fragment_membership(self.compilation['id'], fragment_id, True)
                if ready:
                    self.on_assign_fragment_to_section(self.compilation['id'], fragment_id, section_id)

            self._create_section(title, idea, after_create=assign)

        return self._section_dialog(
            'Nova ideia com este fragmento',
            'Criar e adicionar fragmento',
            create,
            subtitle='O fragmento entra no caderno dentro da nova ideia.',
        )

    # ── texto do esqueleto ─────────────────────────────────

    def _caderno_text(self, with_references: bool = False) -> str:
        lines = [self.compilation['name']]
        year_suffixes = self._year_suffixes()
        for section in self._sorted_sections():
            lines.extend(('', f"## {section['title']}", ''))
            if section['central_idea']:
                lines.extend((section['central_idea'], ''))
            for fragment in self._section_fragments(section['id']):
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

    async def _copy_caderno(self, event=None) -> None:
        del event
        if not self._has_caderno_content():
            return
        await self.on_copy_caderno(self._caderno_text())

    async def _copy_caderno_with_references(self, event=None) -> None:
        del event
        if not self._has_caderno_content():
            return
        await self.on_copy_caderno(self._caderno_text(with_references=True))

    async def _copy_references(self, event=None) -> None:
        del event
        is_caderno = getattr(self, 'selected_tab', 'caderno') == 'caderno'
        works = self._used_works() if is_caderno else self.compilation['works']
        if not works:
            return
        references = self._work_references([work['id'] for work in works])
        disambiguated = build_disambiguated_view_references(works, references)
        disambiguated.sort(key=lambda ref: reference_plain_text(ref).casefold())
        text = '\n'.join(reference_plain_text(ref) for ref in disambiguated)

        copied = copy_references(disambiguated)
        if not copied or not isinstance(self.page, ft.Page):
            try:
                if hasattr(self.page, 'clipboard') and self.page.clipboard:
                    await self.page.clipboard.set(text)
            except Exception:
                if not copied:
                    return
        ui.toast(self.page, self.config, 'Referências copiadas.', icon_name='book-bookmark')

    # ── coluna 1: roteiro ──────────────────────────────────

    def _nav_head(self, label: str, trailing: ft.Control | None = None) -> ft.Container:
        c = self.config
        return ft.Container(
            content=ft.Row(
                [ui.ui_text(c, label, size=12, weight=ui.W600, color=c.colors['faint'])] + ([trailing] if trailing else []),
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            height=s(26),
            padding=ft.Padding.only(left=s(8), right=s(2)),
        )

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
        sections = self._sorted_sections()
        items: list[ft.Control] = []
        for index, section in enumerate(sections):
            active = self.active_section_id == section['id']
            items.append(
                self._outline_item(
                    ui.ui_text(c, str(index + 1), size=12, weight=ui.W600, color=c.colors['gold'] if active else c.colors['faint'], tabular=True),
                    section['title'],
                    len(self._section_fragments(section['id'])),
                    active,
                    lambda _e, sid=section['id']: self._focus_idea(sid),
                )
            )
        if not sections:
            items.append(ft.Container(ui.meta_text(c, 'Nenhuma ideia ainda.'), padding=ft.Padding.symmetric(horizontal=s(8), vertical=s(6))))
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
        return ft.Container(
            content=ft.Column(
                [
                    ft.Column(
                        [self._nav_head('Roteiro', ui.icon_button(c, 'plus', on_click=lambda _e: self._prompt_new_section(), tooltip='Nova ideia', size=22))] + items,
                        spacing=s(1),
                        tight=True,
                    ),
                    ft.Column([self._nav_head('Fila'), queue], spacing=s(1), tight=True),
                    ft.Container(
                        ui.ui_text(
                            c,
                            'Use o menu de cada ideia para reordenar. Remover uma ideia devolve os fragmentos dela para “A organizar”.',
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
        self.active_section_id = key
        if self.selected_tab != 'caderno':
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

    # ── coluna 2: escrita ──────────────────────────────────

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
            items.append(('arrow-right', f'Mover para “{section["title"]}”', lambda sid=section['id']: self._set_fragment_destination(fragment['id'], str(sid)), False))
        items.append(('plus', 'Mover para uma nova ideia', lambda: self._prompt_create_section(fragment['id']), False))
        if section_id is not None:
            items.append(('inbox', 'Devolver para A organizar', lambda: self._set_fragment_destination(fragment['id'], 'unassigned'), False))
        items.append(None)
        items.append(('note-sticky', 'Editar nota de articulação' if fragment['work_note'] else 'Adicionar nota de articulação', lambda: self._prompt_fragment_note(fragment), False))
        items.append(('pen', 'Editar fragmento', lambda: self.on_edit_fragment(self.compilation['id'], fragment), False))
        items.append(None)
        items.append(('circle-minus', 'Retirar do caderno', lambda: self._remove_from_caderno(fragment), True))
        return more_menu(self.config, items, tooltip='Mover, editar ou retirar')

    def _fragment_body(self, fragment: CompilationFragmentRecord, size: float = 18) -> ft.Text:
        c = self.config
        if fragment['fragment_type'] == 'quote':
            return ui.serif_text(c, quoted(fragment['excerpt']), size=size, selectable=True)
        return ui.ui_text(c, fragment['excerpt'], size=13, color=c.colors['muted'], max_lines=None, selectable=True)

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
        return ft.Container(
            content=ft.Column([head, body, self._compose_fragment_note(fragment)], spacing=0, tight=True),
            bgcolor=c.colors['surface'],
            border=ft.Border.all(1, c.colors['border']),
            border_radius=ft.BorderRadius.all(s(8)),
            data=fragment['id'],
        )

    def _section_menu(self, section: CompilationSectionRecord, index: int, total: int) -> ft.PopupMenuButton:
        items: list[MenuItem] = []
        if index > 0:
            items.append(('arrow-up', 'Mover para cima', lambda: self._move_section(index, -1), False))
        if index < total - 1:
            items.append(('arrow-down', 'Mover para baixo', lambda: self._move_section(index, 1), False))
        items.append(('pen', 'Renomear ou editar', lambda: self._prompt_edit_section(section), False))
        items.append(None)
        items.append(('trash-can', 'Remover ideia', lambda: self._delete_section(section['id']), True))
        return more_menu(self.config, items, tooltip='Mover, renomear ou remover')

    def _compose_idea(self, section: CompilationSectionRecord, index: int, total: int) -> ft.Container:
        c = self.config
        fragments = self._section_fragments(section['id'])
        title_row = ft.Row(
            [
                ft.Row(
                    [
                        ui.ui_text(c, str(index + 1), size=13, weight=ui.W600, color=c.colors['faint'], tabular=True),
                        ft.Container(ui.serif_text(c, section['title'], size=24, weight=ui.W600, height=1.15), expand=True),
                    ],
                    spacing=s(10),
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    expand=True,
                ),
                ui.icon_button(c, 'pen', on_click=lambda _e, current=section: self._prompt_edit_section(current), tooltip='Editar ideia'),
                self._section_menu(section, index, total),
            ],
            spacing=s(4),
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        controls: list[ft.Control] = [title_row]
        if section['central_idea']:
            controls.append(
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Container(ui.ui_text(c, 'Ideia central', size=13, color=c.colors['faint']), width=s(104)),
                            ui.ui_text(c, section['central_idea'], size=13, max_lines=None, expand=True, selectable=True),
                        ],
                        spacing=s(12),
                        vertical_alignment=ft.CrossAxisAlignment.START,
                    ),
                    padding=ft.Padding.symmetric(vertical=s(10)),
                    border=ft.Border.only(top=ft.BorderSide(1, c.colors['border']), bottom=ft.BorderSide(1, c.colors['border'])),
                )
            )
        if fragments:
            controls.extend(
                self._compose_fragment_block(fragment, section['id'], position, len(fragments))
                for position, fragment in enumerate(fragments)
            )
        else:
            controls.append(
                ui.empty_state(
                    c,
                    'inbox',
                    'Nenhum fragmento nesta ideia',
                    'Marque fragmentos em Obras e fragmentos e escolha esta ideia como destino.',
                    action=ui.button(c, 'Escolher fragmentos', on_click=lambda _e: self._select_tab('obras'), small=True),
                )
            )
        return ft.Container(
            content=ft.Column(controls, spacing=s(12), tight=True),
            key=ft.ScrollKey(f'idea-{section["id"]}'),
            data=section['id'],
        )

    def _compose_queue(self) -> ft.Container | None:
        c = self.config
        unassigned = self._unassigned_fragments()
        if not unassigned:
            return None
        controls: list[ft.Control] = [
            ft.Row(
                [
                    fa_icon('inbox', size=s(14), color=c.colors['faint']),
                    ui.serif_text(c, 'A organizar', size=24, weight=ui.W600, height=1.15),
                    ui.ui_text(c, str(len(unassigned)), size=13, color=c.colors['faint'], tabular=True),
                ],
                spacing=s(10),
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            ui.ui_text(c, 'Fragmentos do caderno ainda sem ideia. Use o menu de cada um para levá-lo a uma ideia.', size=13, color=c.colors['muted'], max_lines=2),
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
        sections = self._sorted_sections()
        blocks: list[ft.Control] = [self._compose_idea(section, index, len(sections)) for index, section in enumerate(sections)]
        queue = self._compose_queue()
        if queue is not None:
            blocks.append(queue)
        if not sections:
            blocks.insert(
                0,
                ui.empty_state(
                    c,
                    'lightbulb',
                    'Ainda não há ideias',
                    'Crie a primeira ideia do roteiro ou escolha fragmentos em Obras e fragmentos para começar.',
                    action=ft.Row(
                        [
                            ui.button(c, 'Nova ideia', on_click=lambda _e: self._prompt_new_section(), icon_name='plus', small=True),
                            ui.button(c, 'Escolher fragmentos', on_click=lambda _e: self._select_tab('obras'), small=True, variant='ghost'),
                        ],
                        spacing=s(8),
                        tight=True,
                    ),
                ),
            )
        self.writing_blocks = blocks
        self.writing_column = ft.Column(
            [
                ft.Container(
                    max_width_box(c, ft.Column(blocks, spacing=s(48), tight=True), 700),
                    padding=ft.Padding.only(left=s(32), right=s(32), top=s(32), bottom=s(64)),
                )
            ],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )
        return ft.Container(content=self.writing_column, expand=True, bgcolor=c.colors['bg'])

    # ── coluna 3: lateral ──────────────────────────────────

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
        self.outline_host = ft.Container(content=self._compose_outline())
        return ft.Row(
            [self.outline_host, self._compose_writing(), self._compose_rail()],
            spacing=0,
            expand=True,
            vertical_alignment=ft.CrossAxisAlignment.STRETCH,
        )

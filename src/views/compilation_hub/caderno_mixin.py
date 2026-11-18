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
    close_dialog,
    dialog,
    form_field,
    more_menu,
    open_dialog,
    plural,
    reference_text,
    select_input,
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

    def _root_chapters(self) -> list[CompilationSectionRecord]:
        return sorted(
            [s for s in self.compilation['sections'] if not s.get('parent_id')],
            key=lambda section: (section['position'], section['id']),
        )

    def _child_sections(self, parent_id: int) -> list[CompilationSectionRecord]:
        return sorted(
            [s for s in self.compilation['sections'] if s.get('parent_id') == parent_id],
            key=lambda section: (section['position'], section['id']),
        )

    def _sorted_sections(self) -> list[CompilationSectionRecord]:
        ordered: list[CompilationSectionRecord] = []
        chapters = self._root_chapters()
        for chapter in chapters:
            ordered.append(chapter)
            ordered.extend(self._child_sections(chapter['id']))
        known_ids = {s['id'] for s in ordered}
        orphans = [s for s in self.compilation['sections'] if s['id'] not in known_ids]
        if orphans:
            ordered.extend(sorted(orphans, key=lambda s: (s['position'], s['id'])))
        return ordered

    def _section_label(self, section: CompilationSectionRecord) -> str:
        parent_id = section.get('parent_id')
        chapters = self._root_chapters()
        if not parent_id:
            idx = next((i for i, c in enumerate(chapters) if c['id'] == section['id']), -1)
            return str(idx + 1) if idx >= 0 else '•'
        chap_idx = next((i for i, c in enumerate(chapters) if c['id'] == parent_id), -1)
        children = self._child_sections(parent_id)
        child_idx = next((i for i, ch in enumerate(children) if ch['id'] == section['id']), -1)
        if chap_idx >= 0 and child_idx >= 0:
            return f"{chap_idx + 1}.{child_idx + 1}"
        return '•'

    def _collapsed_set(self) -> set[int]:
        if not hasattr(self, '_collapsed_sections'):
            self._collapsed_sections = {
                s['id'] for s in self.compilation.get('sections', [])
            }
        return self._collapsed_sections

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

    # ── ações: ideias e capítulos ──────────────────────────

    def _create_section(
        self,
        title: str,
        central_idea: str | None,
        parent_id: int | None = None,
        after_create: Callable[[int], None] | None = None,
    ) -> int | None:
        if parent_id is not None:
            try:
                section_id = self.on_create_section(
                    self.compilation['id'],
                    title or '',
                    central_idea,
                    parent_id=parent_id,
                )
            except TypeError:
                section_id = self.on_create_section(
                    self.compilation['id'],
                    title or '',
                    central_idea,
                )
        else:
            section_id = self.on_create_section(
                self.compilation['id'],
                title or '',
                central_idea,
            )
        if section_id is not None:
            if after_create is not None:
                after_create(section_id)
            self.active_section_id = section_id
            self._collapsed_set().discard(section_id)
            if parent_id is not None:
                self._collapsed_set().discard(parent_id)
            self.refresh()
        return section_id

    def _update_section(self, section_id: int, title: str, central_idea: str | None) -> bool:
        if self.on_update_section(self.compilation['id'], section_id, title, central_idea):
            self.refresh()
            return True
        return False

    def _transfer_section(self, section_id: int, new_parent_id: int | None) -> bool:
        on_transfer = getattr(self, 'on_transfer_section', None)
        if on_transfer is not None:
            success = on_transfer(self.compilation['id'], section_id, new_parent_id)
        else:
            success = self.on_update_section(
                self.compilation['id'],
                section_id,
                next(s['title'] for s in self.compilation['sections'] if s['id'] == section_id),
                next(s['central_idea'] for s in self.compilation['sections'] if s['id'] == section_id),
                parent_id=new_parent_id,
            )
        if success:
            self.refresh()
            return True
        return False

    def _link_fragment_to_section(self, fragment_id: int, section_id: int) -> bool:
        on_link = getattr(self, 'on_link_fragment_to_section', None)
        if on_link is not None:
            success = on_link(self.compilation['id'], fragment_id, section_id)
            if success:
                self.refresh()
                ui.toast(
                    self.page,
                    self.config,
                    'Fragmento também vinculado à seção.',
                    icon_name='link',
                )
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
            f'“{section["title"]}” removida. Os fragmentos voltaram para A organizar.',
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
        if section.get('parent_id') is not None:
            try:
                new_id = self.on_create_section(
                    compilation_id,
                    section['title'],
                    section['central_idea'],
                    parent_id=section['parent_id'],
                )
            except TypeError:
                new_id = self.on_create_section(
                    compilation_id,
                    section['title'],
                    section['central_idea'],
                )
        else:
            new_id = self.on_create_section(
                compilation_id,
                section['title'],
                section['central_idea'],
            )
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

    def _move_section(self, index: int, offset: int, parent_id: int | None = None) -> None:
        if parent_id is None:
            sections = self._root_chapters()
        else:
            sections = self._child_sections(parent_id)
        target_index = index + offset
        if target_index < 0 or target_index >= len(sections):
            return
        section_ids = [section['id'] for section in sections]
        section_ids[index], section_ids[target_index] = section_ids[target_index], section_ids[index]
        all_ordered = []
        if parent_id is None:
            for sec_id in section_ids:
                all_ordered.append(sec_id)
                all_ordered.extend(ch['id'] for ch in self._child_sections(sec_id))
        else:
            for ch in self._root_chapters():
                all_ordered.append(ch['id'])
                if ch['id'] == parent_id:
                    all_ordered.extend(section_ids)
                else:
                    all_ordered.extend(c['id'] for c in self._child_sections(ch['id']))
        if self.on_reorder_sections(self.compilation['id'], all_ordered):
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

    def _set_fragment_destination(
        self,
        fragment_id: int,
        destination: str,
        current_section_id: int | None = None,
    ) -> None:
        """Destinos: ``not_selected`` (fora do caderno), ``unassigned``
        (A organizar), o id de uma ideia ou ``create_section`` (nova ideia)."""
        if destination == 'create_section':
            self._prompt_create_section(fragment_id)
            return
        if destination == 'not_selected':
            try:
                removed = self.on_fragment_membership(
                    self.compilation['id'],
                    fragment_id,
                    False,
                    section_id=current_section_id,
                )
            except TypeError:
                removed = self.on_fragment_membership(
                    self.compilation['id'],
                    fragment_id,
                    False,
                )
            if removed:
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
        try:
            assigned = self.on_assign_fragment_to_section(
                self.compilation['id'],
                fragment_id,
                section_id,
                current_section_id=current_section_id,
            )
        except TypeError:
            assigned = self.on_assign_fragment_to_section(
                self.compilation['id'],
                fragment_id,
                section_id,
            )
        if assigned:
            self.refresh()
        elif not fragment['is_member']:
            self.refresh()

    def _remove_from_caderno(
        self,
        fragment: CompilationFragmentRecord,
        section_id: int | None = None,
    ) -> None:
        target_section = section_id if section_id is not None else fragment.get('section_id')
        previous = str(target_section) if target_section is not None else 'unassigned'
        try:
            removed = self.on_fragment_membership(
                self.compilation['id'],
                fragment['id'],
                False,
                section_id=target_section,
            )
        except TypeError:
            removed = self.on_fragment_membership(
                self.compilation['id'],
                fragment['id'],
                False,
            )
        if not removed:
            return
        self.refresh()
        msg = (
            'Fragmento removido desta seção.'
            if target_section is not None
            else 'Fragmento retirado do caderno.'
        )
        ui.toast(
            self.page,
            self.config,
            f'{msg} A nota de articulação foi mantida.',
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
        title_hint: str = 'Ex.: Argumento central',
        name_label: str = 'Nome da ideia',
        idea_label: str = 'Ideia central (opcional)',
        extra_fields: list[ft.Control] | None = None,
    ) -> ft.AlertDialog:
        c = self.config
        title_field = text_input(
            c,
            value=section['title'] if section else '',
            hint=title_hint,
            max_length=150,
            autofocus=True,
            expand=True,
        )
        idea_field = text_input(
            c,
            value=(section['central_idea'] or '') if section else '',
            hint='Que papel esta seção terá no texto?',
            multiline=True,
            min_lines=2,
            max_lines=5,
            max_length=2000,
            expand=True,
        )

        def confirm(_event=None) -> None:
            value = (title_field.value or '').strip()
            if not value:
                title_field.error_text = 'Dê um nome à seção.'
                try:
                    title_field.update()
                except Exception:
                    pass
                return
            idea = (idea_field.value or '').strip() or None
            close_dialog(self.page)
            on_confirm(value, idea)

        title_field.on_submit = confirm
        fields = [
            form_field(c, name_label, title_field),
            form_field(c, idea_label, idea_field),
        ]
        if extra_fields:
            fields.extend(extra_fields)
        modal = dialog(
            c,
            title,
            fields,
            [
                ui.button(c, 'Cancelar', on_click=lambda _e: close_dialog(self.page), variant='ghost'),
                ui.button(c, confirm_label, on_click=confirm, variant='primary'),
            ],
            subtitle=subtitle,
        )
        modal.data = {'title': title_field, 'idea': idea_field, 'confirm': confirm}
        open_dialog(self.page, modal)
        return modal

    def _prompt_new_chapter(self) -> ft.AlertDialog:
        return self._section_dialog(
            'Novo Capítulo',
            'Criar capítulo',
            lambda title, idea: self._create_section(title, idea, parent_id=None),
            title_hint='Ex.: Capítulo 1: Fundamentação Teórica',
            name_label='Título do capítulo',
            idea_label='Ideia central do capítulo (opcional)',
            subtitle='O capítulo é uma divisão principal no roteiro de escrita.',
        )

    def _prompt_new_argument(self, default_parent_id: int | None = None) -> ft.AlertDialog:
        chapters = self._root_chapters()
        if not chapters:
            return self._prompt_new_chapter()
        selected_parent = default_parent_id or chapters[0]['id']
        c = self.config
        parent_options = [(str(ch['id']), ch['title']) for ch in chapters]
        parent_selector = select_input(
            c,
            str(selected_parent),
            parent_options,
            on_select=lambda e: setattr(parent_selector, 'value', e.control.value),
        )
        parent_container = form_field(c, 'Capítulo pai', parent_selector)

        def create_arg(title: str, idea: str | None) -> None:
            chosen_parent = int(parent_selector.value) if parent_selector.value else chapters[0]['id']
            self._create_section(title, idea, parent_id=chosen_parent)

        return self._section_dialog(
            'Novo Argumento / Ideia',
            'Criar argumento',
            create_arg,
            title_hint='Ex.: 1.1 Contexto histórico',
            name_label='Nome do argumento',
            idea_label='Ideia central (opcional)',
            subtitle='O argumento fica estruturado dentro do capítulo selecionado.',
            extra_fields=[parent_container],
        )

    def _prompt_new_section(self) -> ft.AlertDialog:
        chapters = self._root_chapters()
        if not chapters:
            return self._section_dialog(
                'Nova Ideia',
                'Criar ideia',
                lambda title, idea: self._create_section(title, idea),
            )
        c = self.config
        options = [ft.dropdown.Option('root', 'Capítulo principal')] + [
            ft.dropdown.Option(str(ch['id']), f"Argumento em: {ch['title']}")
            for ch in chapters
        ]
        parent_select = ft.Dropdown(
            options=options,
            value='root',
            border_color=c.colors['border'],
            color=c.colors['text'],
            bgcolor=c.colors['surface'],
            text_size=13,
            dense=True,
            content_padding=ft.Padding.symmetric(horizontal=s(10), vertical=s(8)),
        )
        parent_field = ft.Container(
            content=ft.Column(
                [
                    ui.ui_text(c, 'Nível estrutural', size=12, color=c.colors['muted'], weight=ui.W500),
                    parent_select,
                ],
                spacing=s(4),
                tight=True,
            ),
            margin=ft.Margin.only(bottom=s(8)),
        )
        return self._section_dialog(
            'Nova Ideia',
            'Criar ideia',
            lambda title, idea: self._create_section(
                title,
                idea,
                parent_id=(None if parent_select.value == 'root' else int(parent_select.value)),
            ),
            extra_fields=[parent_field],
        )

    def _prompt_edit_section(self, section: CompilationSectionRecord) -> ft.AlertDialog:
        is_chapter = not section.get('parent_id')
        name_lbl = 'Nome do capítulo' if is_chapter else 'Nome do argumento'
        title = 'Editar Capítulo' if is_chapter else 'Editar Argumento'
        return self._section_dialog(
            title,
            'Salvar alterações',
            lambda title_val, idea: self._update_section(section['id'], title_val, idea),
            section=section,
            name_label=name_lbl,
        )

    def _prompt_transfer_section(self, section: CompilationSectionRecord) -> ft.AlertDialog:
        c = self.config
        chapters = [ch for ch in self._root_chapters() if ch['id'] != section.get('parent_id')]
        options = [('root', 'Promover a Capítulo principal')] + [
            (str(ch['id']), f"Capítulo: {ch['title']}") for ch in chapters
        ]
        selector = select_input(c, options[0][0], options)

        def confirm(_e=None) -> None:
            close_dialog(self.page)
            val = selector.value
            new_parent = None if val == 'root' else int(val)
            self._transfer_section(section['id'], new_parent)
            ui.toast(
                self.page,
                self.config,
                'Argumento transferido com sucesso.',
                icon_name='folder-tree',
            )

        modal = dialog(
            c,
            f'Transferir “{section["title"]}”',
            [
                ui.ui_text(
                    c,
                    'Selecione o novo destino para este argumento:',
                    size=13,
                    color=c.colors['muted'],
                ),
                form_field(c, 'Novo destino', selector),
            ],
            [
                ui.button(c, 'Cancelar', on_click=lambda _e: close_dialog(self.page), variant='ghost'),
                ui.button(c, 'Transferir', on_click=confirm, variant='primary'),
            ],
            width=460,
        )
        open_dialog(self.page, modal)
        return modal

    def _prompt_link_fragment_to_section(
        self,
        fragment: CompilationFragmentRecord,
    ) -> ft.AlertDialog | None:
        c = self.config
        member_section_ids = {
            f['section_id']
            for _w, f in self._all_fragments()
            if f['id'] == fragment['id'] and f['is_member']
        }
        available_sections = [
            s for s in self._sorted_sections()
            if s['id'] not in member_section_ids
        ]
        if not available_sections:
            ui.toast(
                self.page,
                self.config,
                'Este fragmento já está vinculado a todas as seções existentes.',
                icon_name='circle-info',
            )
            return None
        options = [
            (str(s['id']), f"{self._section_label(s)}. {s['title']}")
            for s in available_sections
        ]
        selector = select_input(c, options[0][0], options)

        def confirm(_e=None) -> None:
            if not selector.value:
                return
            target_sid = int(selector.value)
            close_dialog(self.page)
            self._link_fragment_to_section(fragment['id'], target_sid)

        modal = dialog(
            c,
            'Vincular também a outra seção',
            [
                ui.ui_text(
                    c,
                    'O fragmento aparecerá também na seção escolhida, com ordenação e nota próprias.',
                    size=13,
                    color=c.colors['muted'],
                ),
                form_field(c, 'Vincular a', selector),
            ],
            [
                ui.button(c, 'Cancelar', on_click=lambda _e: close_dialog(self.page), variant='ghost'),
                ui.button(c, 'Vincular', on_click=confirm, variant='primary'),
            ],
            width=460,
        )
        open_dialog(self.page, modal)
        return modal

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
            'Novo capítulo com este fragmento',
            'Criar e adicionar fragmento',
            create,
            subtitle='O fragmento entra no caderno dentro da nova seção.',
        )

    # ── texto do esqueleto ─────────────────────────────────

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
            animate=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
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
            size=20,
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
            meta_summary = (
                plural(len(fragments), 'fragmento', 'fragmentos')
                if fragments
                else "Sem fragmentos"
            )
            controls.append(
                ui.meta_text(c, f"Argumento recolhido ({meta_summary})")
            )
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
                            'Escolher fragmentos',
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
            animate=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
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
                            ui.serif_text(c, section['title'], size=24, weight=ui.W600, height=1.15),
                            expand=True,
                        ),
                        collapse_btn,
                    ],
                    spacing=s(10),
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    expand=True,
                ),
                ui.button(
                    c,
                    '+ Argumento',
                    on_click=lambda _e, cid=section['id']: self._prompt_new_argument(cid),
                    variant='ghost',
                    small=True,
                    tooltip='Adicionar argumento neste capítulo',
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
            meta_summary = []
            if children:
                meta_summary.append(plural(len(children), 'argumento', 'argumentos'))
            if fragments:
                meta_summary.append(plural(len(fragments), 'fragmento', 'fragmentos'))
            summary_desc = " • ".join(meta_summary) if meta_summary else "Vazio"
            controls.append(
                ft.Container(
                    content=ui.meta_text(c, f"Capítulo recolhido ({summary_desc})"),
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
                            'Escolher fragmentos',
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
            animate=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
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
                    ui.serif_text(c, 'A organizar', size=24, weight=ui.W600, height=1.15),
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
                                'Escolher fragmentos',
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
        controls: list[ft.Control] = [self.outline_host, self._compose_writing()]
        if getattr(self, 'show_rail', False):
            controls.append(self._compose_rail())
        return ft.Row(
            controls,
            spacing=0,
            expand=True,
            vertical_alignment=ft.CrossAxisAlignment.STRETCH,
        )

    _caderno_layout = _compose_caderno

"""CadernoActionsMixin extraído de ``caderno_mixin.py``.

Movimentação literal: sem ``__init__``, colabora com o hub via ``self``.
"""

from collections.abc import Callable

from src.contracts import (
    CompilationFragmentRecord,
    CompilationSectionRecord,
)
from src.utils.fragment_reference import fragment_abnt_notation
from src.views import ui_kit as ui
from .caderno_common import quoted


class CadernoActionsMixin:
    """Mutações de seções e vínculos do Caderno.

Delegam aos callbacks do hub e atualizam o estado via ``self``.
"""

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

"""CadernoDataMixin extraído de ``caderno_mixin.py``.

Movimentação literal: sem ``__init__``, colabora com o hub via ``self``.
"""

from src.contracts import (
    CompilationFragmentRecord,
    CompilationSectionRecord,
    CompilationWorkRecord,
)
from src.utils.reference_disambiguation import compute_year_suffixes


class CadernoDataMixin:
    """Consultas e agregações do Caderno de trabalho.

Somente leitura sobre ``self.compilation``; sem ``__init__``.
"""

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

    def _year_suffixes(self) -> dict[int, str]:
        is_caderno = getattr(self, 'selected_tab', 'caderno') == 'caderno'
        works = self._used_works() if is_caderno else self.compilation['works']
        return compute_year_suffixes(works)

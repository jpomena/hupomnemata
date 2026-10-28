from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from src.contracts import (
    CompilationFragmentRecord,
    CompilationPayload,
    CompilationRecord,
    FragmentRecord,
    FragmentPayload,
)
from src.domains import (
    BibliographicResource,
    Compilation,
    CompilationFragment,
    CompilationSection,
    CompilationWork,
    Fragment,
)
from src.repositories.fragment_repository import FragmentRepository


class CompilationRepository:
    def __init__(self, session: Session):
        self.session = session

    def list_compilations(self) -> list[CompilationRecord]:
        compilations = self.session.scalars(
            select(Compilation)
            .options(
                selectinload(Compilation.items)
                .selectinload(CompilationWork.bibliographic_resource),
                selectinload(Compilation.fragment_items),
                selectinload(Compilation.sections),
            )
            .order_by(Compilation.name.collate('NOCASE'), Compilation.id)
        ).all()
        fragment_records = FragmentRepository(
            self.session
        ).list_fragments()
        fragments_by_resource: dict[int, list[FragmentRecord]] = {}
        for fragment in fragment_records:
            fragments_by_resource.setdefault(
                fragment['bib_res_id'], []
            ).append(fragment)
        records: list[CompilationRecord] = []
        for compilation in compilations:
            member_fragments = {
                item.fragment_id: item
                for item in compilation.fragment_items
            }
            section_positions = {
                section.id: section.position
                for section in compilation.sections
            }
            works = []
            for item in compilation.items:
                work = item.bibliographic_resource.specific_work
                if work is None:
                    continue
                work_fragments: list[CompilationFragmentRecord] = []
                for fragment in fragments_by_resource.get(item.bib_res_id, []):
                    fragment_item = member_fragments.get(fragment['id'])
                    is_member = bool(fragment_item and fragment_item.is_member)
                    work_fragments.append({
                        **fragment,
                        'is_member': is_member,
                        'project_position': (
                            fragment_item.position
                            if is_member and fragment_item is not None
                            else None
                        ),
                        'work_note': (
                            fragment_item.work_note
                            if fragment_item is not None
                            else None
                        ),
                        'section_id': (
                            fragment_item.section_id
                            if is_member and fragment_item is not None
                            else None
                        ),
                    })
                work_fragments.sort(key=lambda fragment: (
                    not fragment['is_member'],
                    (
                        section_positions.get(
                            fragment['section_id'],
                            len(section_positions),
                        )
                        if fragment['section_id'] is not None
                        else len(section_positions)
                    ),
                    fragment['project_position']
                    if fragment['project_position'] is not None
                    else fragment['id'],
                    fragment['id'],
                ))
                works.append({
                    'id': item.bib_res_id,
                    'title': work.title,
                    'position': item.position,
                    'fragments': work_fragments,
                })
            records.append({
                'id': compilation.id,
                'name': compilation.name,
                'description': compilation.description,
                'works': works,
                'sections': [
                    {
                        'id': section.id,
                        'title': section.title,
                        'central_idea': section.central_idea,
                        'position': section.position,
                    }
                    for section in compilation.sections
                ],
            })
        return records

    def create(self, payload: CompilationPayload) -> int:
        name, description = self._validated_values(payload)
        compilation = Compilation(name=name, description=description)
        self.session.add(compilation)
        self.session.commit()
        return compilation.id

    def update(self, compilation_id: int, payload: CompilationPayload) -> None:
        compilation = self.session.get(Compilation, compilation_id)
        if compilation is None:
            raise ValueError('A compilação não está mais disponível.')
        compilation.name, compilation.description = self._validated_values(
            payload
        )
        self.session.commit()

    def delete(self, compilation_id: int) -> None:
        compilation = self.session.get(Compilation, compilation_id)
        if compilation is None:
            raise ValueError('A compilação não está mais disponível.')
        self.session.delete(compilation)
        self.session.commit()

    def add_work(self, compilation_id: int, bib_res_id: int) -> None:
        compilation = self.session.get(Compilation, compilation_id)
        if compilation is None:
            raise ValueError('A compilação não está mais disponível.')
        resource = self.session.get(BibliographicResource, bib_res_id)
        if resource is None or resource.specific_work is None:
            raise ValueError('A obra selecionada não está mais disponível.')
        if any(item.bib_res_id == bib_res_id for item in compilation.items):
            raise ValueError('Esta obra já pertence à compilação.')

        next_position = self.session.scalar(
            select(func.coalesce(func.max(CompilationWork.position), -1))
            .where(CompilationWork.compilation_id == compilation_id)
        )
        position = (
            next_position if next_position is not None else -1
        ) + 1
        self.session.add(CompilationWork(
            compilation_id=compilation_id,
            bib_res_id=bib_res_id,
            position=position,
        ))
        try:
            self.session.commit()
        except IntegrityError as error:
            self.session.rollback()
            raise ValueError(
                'Esta obra já pertence à compilação.'
            ) from error

    def remove_work(self, compilation_id: int, bib_res_id: int) -> None:
        item = self.session.scalar(
            select(CompilationWork).where(
                CompilationWork.compilation_id == compilation_id,
                CompilationWork.bib_res_id == bib_res_id,
            )
        )
        if item is None:
            raise ValueError('A obra não pertence a esta compilação.')
        self.session.execute(
            delete(CompilationFragment).where(
                CompilationFragment.compilation_id == compilation_id,
                CompilationFragment.fragment_id.in_(
                    select(Fragment.id).where(
                        Fragment.bib_res_id == bib_res_id
                    )
                ),
            )
        )
        self.session.delete(item)
        self.session.flush()
        self._rewrite_positions(compilation_id, self._ordered_resource_ids(
            compilation_id
        ))
        self.session.commit()

    def reorder_works(
        self,
        compilation_id: int,
        ordered_resource_ids: list[int],
    ) -> None:
        if self.session.get(Compilation, compilation_id) is None:
            raise ValueError('A compilação não está mais disponível.')
        current_ids = self._ordered_resource_ids(compilation_id)
        if set(current_ids) != set(ordered_resource_ids) or (
            len(current_ids) != len(ordered_resource_ids)
        ):
            raise ValueError(
                'A ordenação precisa incluir cada obra da compilação '
                'uma única vez.'
            )
        self._rewrite_positions(compilation_id, ordered_resource_ids)
        self.session.commit()

    def add_fragment(self, compilation_id: int, fragment_id: int) -> None:
        if self.session.get(Compilation, compilation_id) is None:
            raise ValueError('A compilação não está mais disponível.')
        fragment = self.session.get(Fragment, fragment_id)
        if fragment is None:
            raise ValueError('O fragmento não está mais disponível.')
        if self.session.scalar(
            select(CompilationWork.id).where(
                CompilationWork.compilation_id == compilation_id,
                CompilationWork.bib_res_id == fragment.bib_res_id,
            )
        ) is None:
            raise ValueError(
                'Inclua a obra do fragmento na compilação antes de '
                'adicionar o fragmento.'
            )
        item = self.session.scalar(
            select(CompilationFragment).where(
                CompilationFragment.compilation_id == compilation_id,
                CompilationFragment.fragment_id == fragment_id,
            )
        )
        if item is not None and item.is_member:
            raise ValueError('Este fragmento já pertence à compilação.')

        current_position = self.session.scalar(
            select(func.max(CompilationFragment.position))
            .join(
                Fragment,
                Fragment.id == CompilationFragment.fragment_id,
            )
            .where(
                CompilationFragment.compilation_id == compilation_id,
                CompilationFragment.section_id.is_(None),
                CompilationFragment.is_member.is_(True),
                Fragment.bib_res_id == fragment.bib_res_id,
            )
        )
        new_position = (
            current_position if current_position is not None else -1
        ) + 1

        if item is not None:
            item.is_member = True
            item.section_id = None
            item.position = new_position
        else:
            self.session.add(CompilationFragment(
                compilation_id=compilation_id,
                fragment_id=fragment_id,
                position=new_position,
                is_member=True,
            ))
        try:
            self.session.commit()
        except IntegrityError as error:
            self.session.rollback()
            raise ValueError(
                'Este fragmento já pertence à compilação.'
            ) from error

    def remove_fragment(
        self,
        compilation_id: int,
        fragment_id: int,
    ) -> None:
        item = self.session.scalar(
            select(CompilationFragment).where(
                CompilationFragment.compilation_id == compilation_id,
                CompilationFragment.fragment_id == fragment_id,
            )
        )
        if item is None or not item.is_member:
            raise ValueError('O fragmento não pertence a esta compilação.')
        fragment = self.session.get(Fragment, fragment_id)
        if fragment is None:
            raise ValueError('O fragmento não está mais disponível.')
        section_id = item.section_id
        if item.work_note:
            item.is_member = False
            item.section_id = None
            item.position = 0
        else:
            self.session.delete(item)
        self.session.flush()
        if section_id is None:
            self._normalize_fragment_positions(
                compilation_id,
                fragment.bib_res_id,
            )
        else:
            self._normalize_section_fragment_positions(
                compilation_id,
                section_id,
            )
        self.session.commit()

    def update_fragment_note(
        self,
        compilation_id: int,
        fragment_id: int,
        note: str | None,
    ) -> None:
        if self.session.get(Compilation, compilation_id) is None:
            raise ValueError('A compilação não está mais disponível.')
        fragment = self.session.get(Fragment, fragment_id)
        if fragment is None:
            raise ValueError('O fragmento não está mais disponível.')
        clean_note = note.strip() if isinstance(note, str) else ''
        if len(clean_note) > 2000:
            raise ValueError(
                'A nota de articulação deve ter no máximo 2000 caracteres.'
            )
        clean_note = clean_note or None

        item = self.session.scalar(
            select(CompilationFragment).where(
                CompilationFragment.compilation_id == compilation_id,
                CompilationFragment.fragment_id == fragment_id,
            )
        )

        if clean_note is not None:
            if not self.contains_work(compilation_id, fragment.bib_res_id):
                raise ValueError(
                    'Inclua a obra do fragmento na compilação antes de '
                    'adicionar notas.'
                )
            if item is None:
                current_position = self.session.scalar(
                    select(func.max(CompilationFragment.position))
                    .join(
                        Fragment,
                        Fragment.id == CompilationFragment.fragment_id,
                    )
                    .where(
                        CompilationFragment.compilation_id == compilation_id,
                        CompilationFragment.section_id.is_(None),
                        CompilationFragment.is_member.is_(True),
                        Fragment.bib_res_id == fragment.bib_res_id,
                    )
                )
                new_position = (
                    current_position if current_position is not None else -1
                ) + 1
                self.session.add(CompilationFragment(
                    compilation_id=compilation_id,
                    fragment_id=fragment_id,
                    position=new_position,
                    work_note=clean_note,
                    is_member=True,
                ))
            else:
                item.work_note = clean_note
                if not item.is_member:
                    current_position = self.session.scalar(
                        select(func.max(CompilationFragment.position))
                        .join(
                            Fragment,
                            Fragment.id == CompilationFragment.fragment_id,
                        )
                        .where(
                            CompilationFragment.compilation_id
                            == compilation_id,
                            CompilationFragment.section_id.is_(None),
                            CompilationFragment.is_member.is_(True),
                            Fragment.bib_res_id == fragment.bib_res_id,
                        )
                    )
                    new_position = (
                        current_position
                        if current_position is not None
                        else -1
                    ) + 1
                    item.is_member = True
                    item.section_id = None
                    item.position = new_position
        else:
            if item is not None:
                item.work_note = None
                if not item.is_member:
                    self.session.delete(item)
        self.session.commit()

    def create_section(
        self,
        compilation_id: int,
        title: str,
        central_idea: str | None,
    ) -> int:
        if self.session.get(Compilation, compilation_id) is None:
            raise ValueError('A compilação não está mais disponível.')
        title, central_idea = self._validated_section_values(
            title,
            central_idea,
        )
        next_position = self.session.scalar(
            select(func.coalesce(func.max(CompilationSection.position), -1))
            .where(CompilationSection.compilation_id == compilation_id)
        )
        section = CompilationSection(
            compilation_id=compilation_id,
            title=title,
            central_idea=central_idea,
            position=(next_position if next_position is not None else -1) + 1,
        )
        self.session.add(section)
        self.session.commit()
        return section.id

    def update_section(
        self,
        compilation_id: int,
        section_id: int,
        title: str,
        central_idea: str | None,
    ) -> None:
        section = self.session.scalar(
            select(CompilationSection).where(
                CompilationSection.compilation_id == compilation_id,
                CompilationSection.id == section_id,
            )
        )
        if section is None:
            raise ValueError('A seção não pertence a esta compilação.')
        section.title, section.central_idea = self._validated_section_values(
            title,
            central_idea,
        )
        self.session.commit()

    def delete_section(self, compilation_id: int, section_id: int) -> None:
        section = self.session.scalar(
            select(CompilationSection).where(
                CompilationSection.compilation_id == compilation_id,
                CompilationSection.id == section_id,
            )
        )
        if section is None:
            raise ValueError('A seção não pertence a esta compilação.')
        items = self.session.scalars(
            select(CompilationFragment)
            .where(
                CompilationFragment.compilation_id == compilation_id,
                CompilationFragment.section_id == section_id,
            )
            .order_by(CompilationFragment.position, CompilationFragment.id)
        ).all()
        next_positions: dict[int, int] = {}
        for item in items:
            fragment = self.session.get(Fragment, item.fragment_id)
            if fragment is None:
                continue
            bib_res_id = fragment.bib_res_id
            if bib_res_id not in next_positions:
                current_max = self.session.scalar(
                    select(func.max(CompilationFragment.position))
                    .join(
                        Fragment,
                        Fragment.id == CompilationFragment.fragment_id,
                    )
                    .where(
                        CompilationFragment.compilation_id == compilation_id,
                        CompilationFragment.section_id.is_(None),
                        CompilationFragment.is_member.is_(True),
                        Fragment.bib_res_id == bib_res_id,
                    )
                )
                next_positions[bib_res_id] = (
                    current_max if current_max is not None else -1
                ) + 1
            item.section_id = None
            item.position = next_positions[bib_res_id]
            next_positions[bib_res_id] += 1
        self.session.delete(section)
        self.session.flush()
        self._normalize_section_positions(compilation_id)
        self.session.commit()

    def reorder_sections(
        self,
        compilation_id: int,
        ordered_section_ids: list[int],
    ) -> None:
        if self.session.get(Compilation, compilation_id) is None:
            raise ValueError('A compilação não está mais disponível.')
        sections = self.session.scalars(
            select(CompilationSection)
            .where(CompilationSection.compilation_id == compilation_id)
            .order_by(CompilationSection.position, CompilationSection.id)
        ).all()
        current_ids = [section.id for section in sections]
        if (
            len(current_ids) != len(ordered_section_ids)
            or set(current_ids) != set(ordered_section_ids)
        ):
            raise ValueError(
                'A ordenação precisa incluir cada seção da compilação '
                'uma única vez.'
            )
        by_id = {section.id: section for section in sections}
        for position, section in enumerate(sections, start=1):
            section.position = -position
        self.session.flush()
        for position, section_id in enumerate(ordered_section_ids):
            by_id[section_id].position = position
        self.session.commit()

    def assign_fragment_to_section(
        self,
        compilation_id: int,
        fragment_id: int,
        section_id: int | None,
    ) -> None:
        item = self.session.scalar(
            select(CompilationFragment).where(
                CompilationFragment.compilation_id == compilation_id,
                CompilationFragment.fragment_id == fragment_id,
            )
        )
        if item is None or not item.is_member:
            raise ValueError('O fragmento não está selecionado no caderno.')
        old_section_id = item.section_id
        if old_section_id == section_id:
            return
        if section_id is not None:
            section = self.session.scalar(
                select(CompilationSection).where(
                    CompilationSection.compilation_id == compilation_id,
                    CompilationSection.id == section_id,
                )
            )
            if section is None:
                raise ValueError('A seção não pertence a esta compilação.')
            next_position = self.session.scalar(
                select(func.coalesce(
                    func.max(CompilationFragment.position),
                    -1,
                )).where(
                    CompilationFragment.compilation_id == compilation_id,
                    CompilationFragment.section_id == section_id,
                )
            )
        else:
            fragment = self.session.get(Fragment, fragment_id)
            if fragment is None:
                raise ValueError('O fragmento não está mais disponível.')
            next_position = self.session.scalar(
                select(func.coalesce(
                    func.max(CompilationFragment.position),
                    -1,
                ))
                .join(Fragment, Fragment.id == CompilationFragment.fragment_id)
                .where(
                    CompilationFragment.compilation_id == compilation_id,
                    CompilationFragment.section_id.is_(None),
                    CompilationFragment.is_member.is_(True),
                    Fragment.bib_res_id == fragment.bib_res_id,
                    CompilationFragment.id != item.id,
                )
            )
        item.section_id = section_id
        item.position = (
            next_position if next_position is not None else -1
        ) + 1
        self.session.flush()
        if old_section_id is not None and old_section_id != section_id:
            self._normalize_section_fragment_positions(
                compilation_id,
                old_section_id,
            )
        self.session.commit()

    def reorder_section_fragments(
        self,
        compilation_id: int,
        section_id: int,
        ordered_fragment_ids: list[int],
    ) -> None:
        section = self.session.scalar(
            select(CompilationSection).where(
                CompilationSection.compilation_id == compilation_id,
                CompilationSection.id == section_id,
            )
        )
        if section is None:
            raise ValueError('A seção não pertence a esta compilação.')
        items = self.session.scalars(
            select(CompilationFragment).where(
                CompilationFragment.compilation_id == compilation_id,
                CompilationFragment.section_id == section_id,
                CompilationFragment.is_member.is_(True),
            )
        ).all()
        current_ids = [item.fragment_id for item in items]
        if (
            len(current_ids) != len(ordered_fragment_ids)
            or set(current_ids) != set(ordered_fragment_ids)
        ):
            raise ValueError(
                'A ordenação precisa incluir cada fragmento da seção '
                'uma única vez.'
            )
        by_fragment_id = {item.fragment_id: item for item in items}
        for position, fragment_id in enumerate(ordered_fragment_ids):
            by_fragment_id[fragment_id].position = position
        self.session.commit()

    def _normalize_fragment_positions(
        self,
        compilation_id: int,
        bib_res_id: int,
    ) -> None:
        items = self.session.scalars(
            select(CompilationFragment)
            .join(Fragment, Fragment.id == CompilationFragment.fragment_id)
            .where(
                CompilationFragment.compilation_id == compilation_id,
                CompilationFragment.section_id.is_(None),
                CompilationFragment.is_member.is_(True),
                Fragment.bib_res_id == bib_res_id,
            )
            .order_by(
                CompilationFragment.position,
                CompilationFragment.id,
            )
        ).all()
        for position, item in enumerate(items):
            item.position = position

    def _normalize_section_positions(self, compilation_id: int) -> None:
        sections = self.session.scalars(
            select(CompilationSection)
            .where(CompilationSection.compilation_id == compilation_id)
            .order_by(CompilationSection.position, CompilationSection.id)
        ).all()
        for index, section in enumerate(sections, start=1):
            section.position = -index
        self.session.flush()
        for position, section in enumerate(sections):
            section.position = position

    def _normalize_section_fragment_positions(
        self,
        compilation_id: int,
        section_id: int,
    ) -> None:
        items = self.session.scalars(
            select(CompilationFragment)
            .where(
                CompilationFragment.compilation_id == compilation_id,
                CompilationFragment.section_id == section_id,
                CompilationFragment.is_member.is_(True),
            )
            .order_by(CompilationFragment.position, CompilationFragment.id)
        ).all()
        for position, item in enumerate(items):
            item.position = position

    def create_fragment(
        self,
        compilation_id: int,
        payload: FragmentPayload,
    ) -> int:
        if self.session.get(Compilation, compilation_id) is None:
            raise ValueError('A compilação não está mais disponível.')
        if self.session.scalar(
            select(CompilationWork.id).where(
                CompilationWork.compilation_id == compilation_id,
                CompilationWork.bib_res_id == payload['bib_res_id'],
            )
        ) is None:
            raise ValueError(
                'Inclua a obra do fragmento na compilação antes de '
                'adicionar o fragmento.'
            )
        fragment = Fragment(
            fragment_type=payload['fragment_type'],
            excerpt=payload['excerpt'],
            bib_res_id=payload['bib_res_id'],
            location_type=payload['location_type'],
            location_value=payload['location_value'],
        )
        current_position = self.session.scalar(
            select(func.max(CompilationFragment.position))
            .join(
                Fragment,
                Fragment.id == CompilationFragment.fragment_id,
            )
            .where(
                CompilationFragment.compilation_id == compilation_id,
                CompilationFragment.section_id.is_(None),
                CompilationFragment.is_member.is_(True),
                Fragment.bib_res_id == payload['bib_res_id'],
            )
        )
        self.session.add(fragment)
        self.session.flush()
        self.session.add(CompilationFragment(
            compilation_id=compilation_id,
            fragment_id=fragment.id,
            position=(current_position if current_position is not None else -1)
            + 1,
            is_member=True,
        ))
        self.session.commit()
        return fragment.id

    def contains_work(self, compilation_id: int, bib_res_id: int) -> bool:
        return self.session.scalar(
            select(CompilationWork.id).where(
                CompilationWork.compilation_id == compilation_id,
                CompilationWork.bib_res_id == bib_res_id,
            )
        ) is not None

    @staticmethod
    def _validated_values(
        payload: CompilationPayload,
    ) -> tuple[str, str | None]:
        name = payload['name'].strip()
        if not name:
            raise ValueError('Informe o nome da compilação.')
        description = (payload.get('description') or '').strip() or None
        return name, description

    @staticmethod
    def _validated_section_values(
        title: str,
        central_idea: str | None,
    ) -> tuple[str, str | None]:
        normalized_title = title.strip()
        if not normalized_title:
            raise ValueError('Informe o nome da seção.')
        if len(normalized_title) > 150:
            raise ValueError('O nome da seção deve ter até 150 caracteres.')
        normalized_idea = (
            central_idea.strip()
            if isinstance(central_idea, str)
            else ''
        ) or None
        if normalized_idea is not None and len(normalized_idea) > 2000:
            raise ValueError(
                'A ideia central deve ter no máximo 2000 caracteres.'
            )
        return normalized_title, normalized_idea

    def _ordered_resource_ids(self, compilation_id: int) -> list[int]:
        return list(self.session.scalars(
            select(CompilationWork.bib_res_id)
            .where(CompilationWork.compilation_id == compilation_id)
            .order_by(CompilationWork.position, CompilationWork.id)
        ))

    def _rewrite_positions(
        self,
        compilation_id: int,
        ordered_resource_ids: list[int],
    ) -> None:
        items = self.session.scalars(
            select(CompilationWork).where(
                CompilationWork.compilation_id == compilation_id
            )
        ).all()
        by_resource_id = {item.bib_res_id: item for item in items}
        for index, item in enumerate(items, start=1):
            item.position = -index
        self.session.flush()
        for position, resource_id in enumerate(ordered_resource_ids):
            by_resource_id[resource_id].position = position

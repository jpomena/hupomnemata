from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from src.utils.abnt import ABNTUtils
from src.contracts import FragmentPayload, FragmentRecord
from src.domains import (
    BibliographicResource,
    CompilationFragment,
    Fragment,
)


class FragmentRepository:
    """Persists fragments and resolves their associated work titles."""

    def __init__(self, session: Session):
        self.session = session

    @staticmethod
    def _citation_name(value: str) -> str:
        value = value.strip()
        if not value:
            return value
        return value[0].upper() + value[1:].lower()

    def list_fragments(self) -> list[FragmentRecord]:
        fragments = self.session.scalars(
            select(Fragment).order_by(
                Fragment.created_at.desc(),
                Fragment.id.desc(),
            )
        ).all()
        records: list[FragmentRecord] = []
        for fragment in fragments:
            resource = fragment.bibliographic_resource
            work = resource.specific_work
            authors = resource.authors
            citation_author = '; '.join(
                (
                    self._citation_name(author.last_name)
                    if not author.corporation
                    else (
                        self._citation_name(
                            author.jurisdiction.given_names
                        )
                        + '. '
                        + self._citation_name(author.given_names)
                        if author.jurisdiction is not None
                        else self._citation_name(author.given_names)
                    )
                )
                for author in authors
            )
            if not citation_author and work is not None:
                citation_author = ABNTUtils.format_title_without_author(
                    work.title,
                    preserve_title_spelling=(
                        work.preserve_title_spelling
                    ),
                )
                if not work.preserve_title_spelling:
                    citation_author = self._citation_name(citation_author)
            records.append({
                'id': fragment.id,
                'fragment_type': fragment.fragment_type,
                'excerpt': fragment.excerpt,
                'bib_res_id': fragment.bib_res_id,
                'work_title': (
                    work.title if work is not None else 'Obra sem detalhes'
                ),
                'citation_author': citation_author,
                'display_year': work.display_year if work is not None else '',
                'location_type': fragment.location_type,
                'location_value': fragment.location_value,
            })
        return records

    def create(self, payload: FragmentPayload) -> int:
        resource = self.session.get(
            BibliographicResource, payload['bib_res_id']
        )
        if resource is None:
            raise ValueError('A obra selecionada não está mais disponível.')

        fragment = Fragment(
            fragment_type=payload['fragment_type'],
            excerpt=payload['excerpt'],
            bib_res_id=payload['bib_res_id'],
            location_type=payload['location_type'],
            location_value=payload['location_value'],
        )
        self.session.add(fragment)
        self.session.commit()
        return fragment.id

    def update(self, fragment_id: int, payload: FragmentPayload) -> None:
        fragment = self.session.get(Fragment, fragment_id)
        if fragment is None:
            raise ValueError('O fragmento selecionado não está disponível.')
        if self.session.get(
            BibliographicResource,
            payload['bib_res_id'],
        ) is None:
            raise ValueError('A obra selecionada não está mais disponível.')

        fragment.fragment_type = payload['fragment_type']
        fragment.excerpt = payload['excerpt']
        fragment.bib_res_id = payload['bib_res_id']
        fragment.location_type = payload['location_type']
        fragment.location_value = payload['location_value']
        self.session.commit()

    def delete(self, fragment_id: int) -> None:
        fragment = self.session.get(Fragment, fragment_id)
        if fragment is None:
            raise ValueError('O fragmento selecionado não está disponível.')
        self.session.execute(
            delete(CompilationFragment).where(
                CompilationFragment.fragment_id == fragment_id
            )
        )
        self.session.delete(fragment)
        self.session.commit()

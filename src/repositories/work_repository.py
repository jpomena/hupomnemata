from collections.abc import Iterable
from typing import TypedDict

from sqlalchemy import or_, select, delete
from sqlalchemy.orm import Session, selectinload

from src.domains import Author, Authorship, BibliographicResource, WorkMixin
from src.strategies import CoreNormalizer


class AuthorReference(TypedDict):
    name: str
    id: int | None
    corporation: bool
    acronym: str | None
    jurisdiction_id: int | None
    jurisdiction_name: str | None


class AuthorSearchResult(TypedDict):
    id: int
    name: str
    corporation: bool
    acronym: str | None


class WorkCreationPayload(TypedDict):
    work_model: type[WorkMixin]
    relationship_name: str
    author_names: list[AuthorReference]
    resource_data: dict[str, object]
    work_data: dict[str, object]


class WorkRepository:
    """Persiste um recurso bibliografico e sua obra especifica."""

    def __init__(
        self,
        session: Session,
        normalizer: CoreNormalizer | None = None,
    ):
        self.session = session
        self.normalizer = normalizer or CoreNormalizer()

    def create(
        self,
        payload: WorkCreationPayload,
        author_ids: dict[int, int] | None = None,
    ) -> BibliographicResource:
        work_model = payload['work_model']
        author_names = payload['author_names']
        resource_data = payload['resource_data']
        work_data = payload['work_data']
        relationship_name = payload['relationship_name']

        resource = BibliographicResource(**resource_data)
        work = work_model(**work_data)
        setattr(resource, relationship_name, work)
        if resource.specific_work is None:
            raise ValueError(
                'Uma BibliographicResource precisa ter um specific_work '
                'associado antes de ser persistida.'
            )
        self.session.add(resource)

        attached_author_ids: set[int] = set()
        for index, author_reference in enumerate(author_names):
            author_id = (author_ids or {}).get(index)
            if author_reference['id'] is not None:
                author_id = author_reference['id']
            author = (
                self._author_by_id(author_id)
                if author_id is not None
                else self._find_or_create_author(author_reference)
            )
            if author.id in attached_author_ids:
                continue
            resource.authorships.append(Authorship(author=author))
            attached_author_ids.add(author.id)

        try:
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        self.session.refresh(resource)
        return resource

    def _find_or_create_author(self, reference: AuthorReference) -> Author:
        if reference['corporation']:
            name = self.normalizer.legal_entity_name_normalizer(
                reference['name']
            )
            elements = {
                'given_names': name,
                'last_name': name,
                'given_names_initials': '',
                'last_name_initial': '',
            }
        else:
            parsed = self.normalizer.natural_name_parser(reference['name'])
            elements = {
                'given_names': parsed.given_names,
                'last_name': parsed.last_name,
                'given_names_initials': parsed.given_names_initials,
                'last_name_initial': parsed.last_name_initial,
            }

        jurisdiction = None
        jurisdiction_name = (reference.get('jurisdiction_name') or '').strip()
        if jurisdiction_name:
            jurisdiction = self._find_or_create_author({
                'name': jurisdiction_name,
                'id': reference.get('jurisdiction_id'),
                'corporation': True,
                'acronym': None,
                'jurisdiction_id': None,
                'jurisdiction_name': None,
            })

        statement = select(Author).where(
            Author.given_names == elements['given_names'],
            Author.last_name == elements['last_name'],
        )
        author = self.session.scalars(statement).first()
        if author is not None:
            if (
                jurisdiction is not None
                and author.jurisdiction_id != jurisdiction.id
            ):
                author.jurisdiction = jurisdiction
            return author

        author = Author(
            given_names=elements['given_names'],
            last_name=elements['last_name'],
            given_names_initials=elements['given_names_initials'],
            last_name_initial=elements['last_name_initial'],
            corporation=reference['corporation'],
            acronym=reference['acronym'],
            jurisdiction=jurisdiction,
        )
        self.session.add(author)
        self.session.flush()
        return author

    def find_possible_duplicate_authors(self, name: str) -> list[Author]:
        """Retorna homônimos parciais que precisam de confirmação humana."""
        elements = self.normalizer.natural_name_parser(name)
        if not elements.given_names:
            return []
        first_given_name = elements.given_names.split(maxsplit=1)[0]
        statement = select(Author).where(
            Author.last_name == elements.last_name,
            or_(
                Author.given_names == first_given_name,
                Author.given_names.like(f'{first_given_name} %'),
            ),
            Author.given_names != elements.given_names,
        ).order_by(Author.given_names)
        return list(self.session.scalars(statement))

    def search_authors(
        self, query: str, limit: int = 8
    ) -> list[AuthorSearchResult]:
        """Busca autores existentes pelo nome para o formulario."""
        query = query.strip()
        if not query:
            return []
        statement = (
            select(Author)
            .where(
                or_(
                    Author.given_names.ilike(f"%{query}%"),
                    Author.last_name.ilike(f"%{query}%"),
                    Author.acronym.ilike(f"%{query}%"),
                )
            )
            .order_by(Author.last_name, Author.given_names)
            .limit(limit)
        )
        return [
            {
                'id': author.id,
                'name': (
                    author.given_names
                    if author.corporation
                    else f"{author.given_names} {author.last_name}"
                ),
                'corporation': author.corporation,
                'acronym': author.acronym,
            }
            for author in self.session.scalars(statement)
        ]

    def list_works(self) -> list[BibliographicResource]:
        """Lista todas as obras cadastradas, da mais recente à mais antiga."""
        statement = (
            select(BibliographicResource)
            .options(
                selectinload(BibliographicResource.authorships)
                .selectinload(Authorship.author)
                .selectinload(Author.jurisdiction),
                selectinload(BibliographicResource.editorial_monograph),
                selectinload(BibliographicResource.academic_monograph),
                selectinload(BibliographicResource.correspondence_monograph),
                selectinload(BibliographicResource.periodical_collection),
                selectinload(BibliographicResource.journal_article),
                selectinload(BibliographicResource.newspaper_article),
                selectinload(BibliographicResource.monographic_proceeding),
                selectinload(BibliographicResource.periodical_proceeding),
                selectinload(BibliographicResource.patent),
                selectinload(BibliographicResource.statute),
                selectinload(BibliographicResource.caselaw),
                selectinload(BibliographicResource.audiovisual_document),
                selectinload(BibliographicResource.audio_document),
                selectinload(BibliographicResource.visual_document),
                selectinload(BibliographicResource.three_dimensional_document),
                selectinload(BibliographicResource.cartographic_document),
                selectinload(BibliographicResource.musical_score),
                selectinload(
                    BibliographicResource.miscellaneous_digital_document
                ),
            )
            .order_by(BibliographicResource.id.desc())
        )
        works = list(self.session.scalars(statement))
        for resource in works:
            for authorship in resource.authorships:
                author = authorship.author
                if author.jurisdiction_id is not None:
                    _ = author.jurisdiction
            work = resource.specific_work
            if work is None:
                continue
            _ = work.bibliographic_resource
            _ = work.authors
            if getattr(work, 'is_partial', False):
                parent = getattr(work, 'parent_bibliographic_resource', None)
                if parent is not None:
                    parent.id
        return works

    def search_works(
        self, query: str, limit: int = 8
    ) -> list[BibliographicResource]:
        """Busca obras pelo titulo para seletores relacionados."""
        query = query.strip().casefold()
        if not query:
            return []
        matches = []
        for resource in self.list_works():
            work = resource.specific_work
            if work is not None and query in work.title.casefold():
                matches.append(resource)
                if len(matches) == limit:
                    break
        return matches

    def _author_by_id(self, author_id: int) -> Author:
        author = self.session.get(Author, author_id)
        if author is None:
            raise ValueError('O autor selecionado não está mais disponível.')
        return author

    def create_many(
        self, payloads: Iterable[WorkCreationPayload]
    ) -> list[BibliographicResource]:
        return [self.create(payload) for payload in payloads]

    def remove_work(self, work: BibliographicResource) -> None:
        author_ids = list(
            self.session.scalars(
                select(Authorship.author_id).where(
                    Authorship.bib_res_id == work.id
                )
            )
        )

        try:
            self.session.execute(
                delete(BibliographicResource).where(
                    BibliographicResource.id == work.id
                )
            )

            for author_id in author_ids:
                remaining_authorship = self.session.scalar(
                    select(Authorship.id)
                    .where(Authorship.author_id == author_id)
                    .limit(1)
                )
                if remaining_authorship is None:
                    self.session.execute(
                        delete(Author).where(Author.id == author_id)
                    )

            self.session.commit()
        except Exception:
            self.session.rollback()
            raise

from collections.abc import Iterable
from typing import TypedDict

from sqlalchemy import inspect, or_, select
from sqlalchemy.orm import Session

from src.domains import Author, Authorship, BibliographicResource, WorkMixin
from src.strategies import CoreNormalizer


class WorkCreationPayload(TypedDict):
    work_model: type[WorkMixin]
    relationship_name: str
    author_names: list[str]
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
        self.session.add(resource)

        attached_author_ids: set[int] = set()
        for index, author_name in enumerate(author_names):
            author_id = (author_ids or {}).get(index)
            author = (
                self._author_by_id(author_id)
                if author_id is not None
                else self._find_or_create_author(author_name)
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

    def _find_or_create_author(self, name: str) -> Author:
        elements = self.normalizer.natural_name_parser(name)
        statement = select(Author).where(
            Author.given_names == elements.given_names,
            Author.last_name == elements.last_name,
        )
        author = self.session.scalars(statement).first()
        if author is not None:
            return author

        author = Author(
            given_names=elements.given_names,
            last_name=elements.last_name,
            given_names_initials=elements.given_names_initials,
            last_name_initial=elements.last_name_initial,
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

    def search_authors(self, query: str, limit: int = 8) -> list[str]:
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
                )
            )
            .order_by(Author.last_name, Author.given_names)
            .limit(limit)
        )
        return [
            f"{author.given_names} {author.last_name}"
            for author in self.session.scalars(statement)
        ]

    def list_works(self) -> list[BibliographicResource]:
        """Lista todas as obras cadastradas, da mais recente à mais antiga."""
        statement = select(BibliographicResource).order_by(
            BibliographicResource.id.desc()
        )
        works = list(self.session.scalars(statement))
        relationships = inspect(BibliographicResource).relationships
        for resource in works:
            for relationship in relationships:
                related = getattr(resource, relationship.key)
                if relationship.key == "authorships":
                    for authorship in related:
                        authorship.author
                elif related is not None and hasattr(
                    related, "bibliographic_resource"
                ):
                    related.bibliographic_resource
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

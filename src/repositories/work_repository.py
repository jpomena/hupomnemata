from collections.abc import Iterable
from typing import TypedDict

from sqlalchemy import select
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

    def create(self, payload: WorkCreationPayload) -> BibliographicResource:
        work_model = payload['work_model']
        author_names = payload['author_names']
        resource_data = payload['resource_data']
        work_data = payload['work_data']
        relationship_name = payload['relationship_name']

        resource = BibliographicResource(**resource_data)
        work = work_model(**work_data)
        setattr(resource, relationship_name, work)
        self.session.add(resource)

        for author_name in author_names:
            author = self._find_or_create_author(author_name)
            resource.authorships.append(Authorship(author=author))

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
            Author.given_names == elements.given_name,
            Author.last_name == elements.last_name,
        )
        author = self.session.scalar(statement)
        if author is not None:
            return author

        author = Author(
            given_names=elements.given_name,
            last_name=elements.last_name,
            given_names_initials=elements.given_name_initials,
            last_name_initial=elements.last_name_initial,
        )
        self.session.add(author)
        self.session.flush()
        return author

    def create_many(
        self, payloads: Iterable[WorkCreationPayload]
    ) -> list[BibliographicResource]:
        return [self.create(payload) for payload in payloads]

from datetime import date
from typing import Literal, TypedDict

from src.db.db import SessionLocal
from src.domains import (
    Author,
    DatePrecision,
    WorkMixin,
)
from src.contracts import (
    AuthorReference,
    WorkCreationPayload,
)
from src.repositories import (
    WorkRepository,
)
from src.services.work_form_service import WorkFormService
from src.utils.normalizers import CoreNormalizer


class RequiresChoiceResult(TypedDict):
    requires_choice: Literal[True]
    index: int
    candidates: list[Author]


class CreatedResourceResult(TypedDict):
    requires_choice: Literal[False]
    resource_id: int
    work_title: str


class WorkService:
    """Centraliza regras de negócio de criação, busca e validação de obras."""

    def __init__(self, normalizer: CoreNormalizer | None = None):
        self.normalizer = normalizer or CoreNormalizer()

    def create(
        self,
        payload: WorkCreationPayload,
        author_ids: dict[int, int] | None = None,
    ):
        with SessionLocal() as session:
            return WorkRepository(session, self.normalizer).create(
                payload,
                author_ids=author_ids,
            )

    def update(self, resource_id: int, payload: WorkCreationPayload) -> str:
        with SessionLocal() as session:
            resource = WorkRepository(session, self.normalizer).update(
                resource_id,
                payload,
            )
            work = resource.specific_work
            if work is None:
                raise ValueError(
                    'A obra atualizada não possui detalhes disponíveis.'
                )
            return work.title

    def search_authors(self, query: str):
        with SessionLocal() as session:
            return WorkRepository(session, self.normalizer).search_authors(
                query
            )

    def search_works(
        self,
        query: str,
        work_type: str | None = None,
    ) -> list[tuple[int, str]]:
        work_model = (
            self.work_model_for(work_type) if work_type is not None else None
        )
        with SessionLocal() as session:
            resources = WorkRepository(session, self.normalizer).search_works(
                query,
                work_model=work_model,
            )
        return [
            (resource.id, resource.specific_work.title)
            for resource in resources
            if resource.specific_work is not None
        ]

    def list_works(self):
        with SessionLocal() as session:
            return WorkRepository(session, self.normalizer).list_works()

    def get_work_title(self, resource_id: int) -> str | None:
        with SessionLocal() as session:
            return WorkRepository(
                session, self.normalizer
            ).get_work_title(resource_id)

    def remove_work(self, resource):
        with SessionLocal() as session:
            WorkRepository(session, self.normalizer).remove_work(resource)

    def resolve_and_create(
        self,
        payload: WorkCreationPayload,
        author_ids: dict[int, int] | None = None,
        new_author_indexes: set[int] | None = None,
    ) -> RequiresChoiceResult | CreatedResourceResult:
        with SessionLocal() as session:
            repository = WorkRepository(session, self.normalizer)
            pending_author_ids = author_ids or {}
            pending_new_author_indexes = new_author_indexes or set()

            author_names: list[AuthorReference] = payload['author_names']
            for index, author_reference in enumerate(author_names):
                if (
                    index in pending_author_ids
                    or index in pending_new_author_indexes
                ):
                    continue
                if author_reference['id'] is not None:
                    continue
                candidates = repository.find_possible_duplicate_authors(
                    author_reference['name']
                )
                if candidates:
                    return {
                        'requires_choice': True,
                        'index': index,
                        'candidates': candidates,
                    }

            resource = repository.create(
                payload,
                author_ids=pending_author_ids,
            )
            work = resource.specific_work
            if work is None:
                raise ValueError('A obra cadastrada não possui detalhes.')
            return {
                'requires_choice': False,
                'resource_id': resource.id,
                'work_title': work.title,
            }

    @staticmethod
    def work_model_for(work_type: str) -> type[WorkMixin]:
        return WorkFormService.work_model_for(work_type)

    @staticmethod
    def parse_date(value: str, year_only: bool, unknown: bool = False) -> date:
        return WorkFormService.parse_date(value, year_only, unknown)

    @staticmethod
    def parse_date_precision(value: str) -> DatePrecision:
        return WorkFormService.parse_date_precision(value)

    @staticmethod
    def convert_model_values(
        form_data: dict[str, object],
        include_empty: bool = False,
    ) -> dict[str, object]:
        return WorkFormService.convert_model_values(
            form_data, include_empty
        )

    @staticmethod
    def author_references(value: object) -> list[AuthorReference]:
        return WorkFormService.author_references(value)

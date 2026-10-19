from typing import TypedDict

from src.domains import WorkMixin


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

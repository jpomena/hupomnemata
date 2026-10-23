from typing import TypedDict

from src.domains import WorkMixin

FRAGMENT_TYPE_LABELS = {
    'quote': 'Citação',
    'comment': 'Comentários/Paráfrases',
}

FRAGMENT_LOCATION_TYPES = (
    'Página',
    'Capítulo',
    'Seção',
    'Localizador/posição',
    'Tempo (ex.: 12:30)',
    'Outros',
)


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


class FragmentRecord(TypedDict):
    id: int
    fragment_type: str
    excerpt: str
    bib_res_id: int
    work_title: str
    citation_author: str
    display_year: str
    location_type: str | None
    location_value: str | None


class CompilationFragmentRecord(FragmentRecord):
    is_member: bool
    project_position: int | None
    work_note: str | None
    section_id: int | None


class CompilationSectionRecord(TypedDict):
    id: int
    title: str
    central_idea: str | None
    position: int


class FragmentPayload(TypedDict):
    fragment_type: str
    excerpt: str
    bib_res_id: int
    location_type: str | None
    location_value: str | None


class CompilationSearchRecord(TypedDict):
    id: int
    name: str
    description: str | None


class CompilationWorkRecord(TypedDict):
    id: int
    title: str
    position: int
    fragments: list[CompilationFragmentRecord]


class CompilationRecord(TypedDict):
    id: int
    name: str
    description: str | None
    works: list[CompilationWorkRecord]
    sections: list[CompilationSectionRecord]


class CompilationPayload(TypedDict):
    name: str
    description: str | None

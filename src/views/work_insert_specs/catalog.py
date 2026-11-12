"""Catálogo visual do diálogo "Nova obra": grupos de tipos, ícones e seções.

Os tipos e os campos continuam declarados nas specs. Este módulo só diz como
eles aparecem: em que grupo da lista lateral cada tipo fica, com que estilo de
ícone, e em que seção do formulário cada campo entra.
"""

import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass

from .base import WorkTypeSpec

TYPE_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "Textos",
        (
            "editorial_monograph",
            "academic_monograph",
            "correspondence_monograph",
        ),
    ),
    (
        "Periódicos",
        (
            "journal_article",
            "periodical_collection",
            "newspaper_article",
        ),
    ),
    (
        "Eventos",
        ("monographic_proceedings", "periodical_proceedings"),
    ),
    ("Jurídico", ("statute", "caselaw", "patent")),
    (
        "Mídia e objetos",
        (
            "audiovisual_document",
            "audio_document",
            "musical_score",
            "visual_document",
            "cartographic_document",
            "three_dimensional_document",
        ),
    ),
    ("Digital", ("miscellaneous_digital_document",)),
)
FALLBACK_GROUP = "Digital"

# Ícones que existem no estilo regular do Font Awesome Free.
REGULAR_TYPE_ICONS = {
    "correspondence_monograph",
    "journal_article",
    "newspaper_article",
    "monographic_proceedings",
    "periodical_proceedings",
    "patent",
    "miscellaneous_digital_document",
    "visual_document",
    "cartographic_document",
}


def type_icon(spec: WorkTypeSpec) -> tuple[str, str]:
    """Retorna ``(nome, estilo)`` do ícone do tipo."""
    style = "regular" if spec.key in REGULAR_TYPE_ICONS else "solid"
    return spec.icon or "file-lines", style


def _fold(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def type_matches(spec: WorkTypeSpec, query: str) -> bool:
    """Busca sem acento e sem caixa no nome e na descrição do tipo."""
    needle = _fold(query.strip())
    if not needle:
        return True
    return needle in _fold(spec.label) or needle in _fold(spec.description)


def grouped_types(
    specs: Iterable[WorkTypeSpec],
    query: str = "",
) -> list[tuple[str, list[WorkTypeSpec]]]:
    """Agrupa os tipos na ordem da lista lateral, já filtrados pela busca."""
    by_key = {spec.key: spec for spec in specs}
    placed: set[str] = set()
    groups: list[tuple[str, list[WorkTypeSpec]]] = []
    for title, keys in TYPE_GROUPS:
        items = [by_key[key] for key in keys if key in by_key]
        placed.update(spec.key for spec in items)
        if title == FALLBACK_GROUP:
            items.extend(
                spec for key, spec in by_key.items() if key not in placed
            )
        items = [spec for spec in items if type_matches(spec, query)]
        if items:
            groups.append((title, items))
    return groups


# ── seções do formulário ──────────────────────────────────


@dataclass(frozen=True)
class SectionSpec:
    key: str
    title: str
    helper: str = ""


IDENTIFICATION = "identificacao"
PARENT = "parte"
AUTHORSHIP = "autoria"
DETAILS = "detalhes"
PUBLICATION_SECTION = "publicacao"
PHYSICAL = "descricao_fisica"
ONLINE = "acesso"
NOTES = "notas"
ABSTRACT = "resumo"

SECTION_ORDER = (
    IDENTIFICATION,
    PARENT,
    AUTHORSHIP,
    DETAILS,
    PUBLICATION_SECTION,
    PHYSICAL,
    ONLINE,
    NOTES,
    ABSTRACT,
)

BASE_SECTIONS = {
    IDENTIFICATION: SectionSpec(
        IDENTIFICATION, "Identificação", "Como a obra aparece na referência."
    ),
    PARENT: SectionSpec(
        PARENT, "Obra-pai", "A obra que contém esta parte."
    ),
    AUTHORSHIP: SectionSpec(
        AUTHORSHIP, "Autoria", "Sem autor, a referência começa pelo título."
    ),
    DETAILS: SectionSpec(DETAILS, "Detalhes"),
    PUBLICATION_SECTION: SectionSpec(PUBLICATION_SECTION, "Publicação"),
    PHYSICAL: SectionSpec(PHYSICAL, "Descrição física"),
    ONLINE: SectionSpec(ONLINE, "Acesso online", "Opcional."),
    NOTES: SectionSpec(NOTES, "Notas"),
    ABSTRACT: SectionSpec(ABSTRACT, "Resumo", "Alimenta a síntese do Nous."),
}

DETAIL_SECTIONS = {
    "academic_monograph": ("Trabalho acadêmico", "Dados da defesa."),
    "correspondence_monograph": ("Correspondência", ""),
    "journal_article": ("Fascículo", "Volume e número em que o artigo saiu."),
    "periodical_collection": ("Periódico", ""),
    "newspaper_article": ("Jornal", "Onde a matéria foi publicada."),
    "monographic_proceedings": ("Evento", ""),
    "periodical_proceedings": ("Evento", ""),
    "statute": ("Norma", "Promulgação e veículo oficial."),
    "caselaw": ("Decisão", "Órgão julgador, processo e relator."),
    "patent": ("Registro", "Depósito e concessão."),
}

PARENT_SECTIONS_MAGAZINE = (
    "Revista",
    "A revista que publicou o texto.",
)

FIELD_SECTIONS: dict[str, str] = {
    # identificação
    "title": IDENTIFICATION,
    "subtitle": IDENTIFICATION,
    "preserve_title_spelling": IDENTIFICATION,
    "is_partial": IDENTIFICATION,
    "original_full_title": IDENTIFICATION,
    # parte de outra obra
    "part_volume": PARENT,
    "part_chapter": PARENT,
    "part_start_page": PARENT,
    "part_end_page": PARENT,
    "part_identifier": PARENT,
    "part_responsibilities": PARENT,
    "consult_start_year": PARENT,
    "consult_end_year": PARENT,
    # autoria
    "authors": AUTHORSHIP,
    "responsibilities": AUTHORSHIP,
    "author_role": AUTHORSHIP,
    "recipient": AUTHORSHIP,
    "applicant": AUTHORSHIP,
    "representative": AUTHORSHIP,
    # detalhes do tipo
    "thesis_type": DETAILS,
    "education_level": DETAILS,
    "course": DETAILS,
    "faculty": DETAILS,
    "defense_year": DETAILS,
    "correspondence_type": DETAILS,
    "journal_title": DETAILS,
    "journal_subtitle": DETAILS,
    "volume": DETAILS,
    "year_season": DETAILS,
    "number": DETAILS,
    "section": DETAILS,
    "start_page": DETAILS,
    "end_page": DETAILS,
    "issn": DETAILS,
    "event_name": DETAILS,
    "event_number": DETAILS,
    "event_year": DETAILS,
    "event_place": DETAILS,
    "vol_or_year": DETAILS,
    "promulgation_date": DETAILS,
    "publication_media": DETAILS,
    "publication_number": DETAILS,
    "decision_type": DETAILS,
    "decision_date": DETAILS,
    "case_number": DETAILS,
    "panel": DETAILS,
    "region": DETAILS,
    "rapporteur": DETAILS,
    "filing_date": DETAILS,
    "grant_date": DETAILS,
    # publicação
    "date_anchor": PUBLICATION_SECTION,
    "date_precision": PUBLICATION_SECTION,
    "publication_place": PUBLICATION_SECTION,
    "publisher": PUBLICATION_SECTION,
    "edition": PUBLICATION_SECTION,
    "version": PUBLICATION_SECTION,
    "publication_date": PUBLICATION_SECTION,
    "first_volume_year": PUBLICATION_SECTION,
    "last_volume_year": PUBLICATION_SECTION,
    "manufacturing_place": PUBLICATION_SECTION,
    "manufacturer": PUBLICATION_SECTION,
    "collection_name": PUBLICATION_SECTION,
    "collection_number": PUBLICATION_SECTION,
    "isbn": PUBLICATION_SECTION,
    "published": PUBLICATION_SECTION,
    # descrição física
    "page_quantity": PHYSICAL,
    "volumes": PHYSICAL,
    "illustrations": PHYSICAL,
    "dimensions": PHYSICAL,
    "carrier_type": PHYSICAL,
    "seconds": PHYSICAL,
    "sound": PHYSICAL,
    "colorized": PHYSICAL,
    "physical_details": PHYSICAL,
    "physical_description": PHYSICAL,
    "instrumentation": PHYSICAL,
    # acesso online
    "doi": ONLINE,
    "url": ONLINE,
    "viewed_at": ONLINE,
    # notas
    "translation_notes": NOTES,
    "additional_notes": NOTES,
    # resumo
    "abstract": ABSTRACT,
}

FULL_WIDTH_FIELDS = {
    "title",
    "subtitle",
    "original_full_title",
    "authors",
    "responsibilities",
    "part_responsibilities",
    "journal_title",
    "event_name",
    "physical_description",
    "translation_notes",
    "additional_notes",
    "abstract",
}

# Seções curtas em três colunas, como "Descrição física" no protótipo.
THREE_COLUMN_SECTIONS = {PHYSICAL}


def field_section(key: str) -> str:
    return FIELD_SECTIONS.get(key, DETAILS)


def section_for(key: str, spec: WorkTypeSpec, magazine_parent: bool) -> SectionSpec:
    """Título e ajuda de uma seção, ajustados ao tipo selecionado."""
    if key == DETAILS and spec.key in DETAIL_SECTIONS:
        title, helper = DETAIL_SECTIONS[spec.key]
        return SectionSpec(key, title, helper)
    if key == PARENT and magazine_parent:
        title, helper = PARENT_SECTIONS_MAGAZINE
        return SectionSpec(key, title, helper)
    return BASE_SECTIONS[key]


__all__ = [
    "TYPE_GROUPS",
    "REGULAR_TYPE_ICONS",
    "SectionSpec",
    "SECTION_ORDER",
    "FULL_WIDTH_FIELDS",
    "THREE_COLUMN_SECTIONS",
    "type_icon",
    "type_matches",
    "grouped_types",
    "field_section",
    "section_for",
]

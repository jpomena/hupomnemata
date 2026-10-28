"""Estruturas base e campos comuns para especificações de cadastro de obras."""

from dataclasses import dataclass
import flet as ft


@dataclass(frozen=True)
class FieldSpec:
    """Descreve um campo exibido no formulário de cadastro."""

    key: str
    label: str
    hint: str | None = None
    kind: str = "text"
    required: bool = False


@dataclass(frozen=True)
class WorkTypeSpec:
    """Descreve um tipo de obra e os campos que ele disponibiliza."""

    key: str
    label: str
    description: str
    icon: ft.IconData
    fields: tuple[FieldSpec, ...]
    date_kind: str = "year"


COMMON = (
    FieldSpec(
        key="title",
        label="Título da obra",
        hint="Ex.: A nova razão do mundo",
        required=True
    ),
    FieldSpec(
        key="subtitle",
        label="Subtítulo",
        hint="Ex.: ensaio sobre a sociedade neoliberal"
    ),
    FieldSpec(
        key="authors",
        label="Autores / responsáveis (se houver)",
        hint="Separe vários nomes por ponto e vírgula",
    ),
    FieldSpec(
        key="abstract",
        label="Resumo / descrição (se houver)",
        hint="Ex.: análise das transformações do trabalho contemporâneo",
        kind="multiline"
    ),
    FieldSpec(
        key="date_anchor",
        label="Ano de publicação (ou estimado)",
        hint="Ex.: 2024",
        kind="year",
        required=True
    ),
    FieldSpec(key="date_precision", label="Precisão da data", kind="dropdown"),
    FieldSpec(key="url", label="URL", hint="https://z-library.gs/..."),
    FieldSpec(
        key="viewed_at",
        label="Data de acesso",
        hint="DD/MM/AAAA",
        kind="date"
    ),
)

PARTIAL_WORK_TYPES = {
    "editorial_monograph",
    "academic_monograph",
    "correspondence_monograph",
    "periodical_collection",
    "journal_article",
    "monographic_proceedings",
    "periodical_proceedings",
    "audio_document",
    "musical_score",
}
MAGAZINE_PARENT_TYPES = {"journal_article", "periodical_collection"}
NO_GENERIC_AUTHORS_TYPES = {"audiovisual_document"}
OPTIONAL_AUTHORS_TYPES = {
    "cartographic_document",
    "three_dimensional_document",
}
MULTIMEDIA_WORK_TYPES = {
    "audiovisual_document",
    "audio_document",
    "musical_score",
    "visual_document",
    "cartographic_document",
    "three_dimensional_document",
}

PARTIAL = (
    FieldSpec(
        key="is_partial",
        label="É parte de outra obra",
        kind="checkbox"
    ),
)
PARTIAL_PAGE_LOCATION = (
    FieldSpec(
        key="part_start_page",
        label="Página inicial da parte (se houver)",
        hint="Ex.: 45",
    ),
    FieldSpec(
        key="part_end_page",
        label="Página final da parte (se houver)",
        hint="Ex.: 68",
    ),
)
PARTIAL_BOOK_LOCATION = (
    FieldSpec(
        key="part_volume",
        label="Volume da parte (se houver)",
        hint="Ex.: 2",
    ),
    FieldSpec(
        key="part_chapter",
        label="Capítulo da parte (se houver)",
        hint="Ex.: 3",
    ),
    *PARTIAL_PAGE_LOCATION,
)
PARTIAL_FIELDS_BY_TYPE = {
    "editorial_monograph": PARTIAL + PARTIAL_BOOK_LOCATION,
    "academic_monograph": PARTIAL + PARTIAL_BOOK_LOCATION,
    "correspondence_monograph": PARTIAL + PARTIAL_BOOK_LOCATION,
    "monographic_proceedings": PARTIAL + PARTIAL_PAGE_LOCATION,
    "periodical_proceedings": PARTIAL + PARTIAL_PAGE_LOCATION,
    "audio_document": PARTIAL + (
        FieldSpec(
            key="part_identifier",
            label="Identificador da parte",
            hint="Ex.: faixa 3",
        ),
        FieldSpec(
            key="part_responsibilities",
            label="Responsabilidades da parte",
            hint="Ex.: intérprete Maria Bethânia",
            kind="responsibilities",
        ),
    ),
    "musical_score": PARTIAL + (
        PARTIAL_PAGE_LOCATION[0],
        PARTIAL_PAGE_LOCATION[1],
        PARTIAL_BOOK_LOCATION[0],
    ),
}
PERIODICAL_COLLECTION_PARTIAL = (
    FieldSpec(
        key="consult_start_year",
        label="Ano inicial consultado",
        hint="Ex.: 2019",
        kind="number",
    ),
    FieldSpec(
        key="consult_end_year",
        label="Ano final consultado (se houver)",
        hint="Ex.: 2024",
        kind="number",
    ),
)

JOURNAL_ARTICLE_PARTIAL = (
    FieldSpec(
        key="part_start_page",
        label="Página inicial do artigo (se houver)",
        hint="Ex.: 45",
    ),
    FieldSpec(
        key="part_end_page",
        label="Página final do artigo (se houver)",
        hint="Ex.: 68",
    ),
)

INHERITED_FROM_PARENT_FIELDS = {
    "publication_place",
    "publisher",
    "edition",
    "volumes",
    "illustrations",
    "dimensions",
    "collection_name",
    "collection_number",
    "translation_notes",
    "original_full_title",
    "isbn",
    "journal_title",
    "journal_subtitle",
    "volume",
    "year_season",
    "number",
    "issn",
    "event_name",
    "event_number",
    "event_year",
    "event_place",
    "publication_year",
    "page_quantity",
    "section",
    "start_page",
    "end_page",
    "vol_or_year",
}
PARTIAL_FORM_FIELDS = {
    "editorial_monograph": {
        "title", "subtitle", "authors", "is_partial",
        "part_volume", "part_chapter", "part_start_page", "part_end_page",
    },
    "academic_monograph": {
        "title", "subtitle", "authors", "is_partial",
        "part_volume", "part_chapter", "part_start_page", "part_end_page",
    },
    "correspondence_monograph": {
        "title", "subtitle", "authors", "is_partial",
        "part_volume", "part_chapter", "part_start_page", "part_end_page",
    },
    "monographic_proceedings": {
        "title", "subtitle", "authors", "is_partial",
        "part_start_page", "part_end_page",
    },
    "periodical_proceedings": {
        "title", "subtitle", "authors", "url", "viewed_at", "is_partial",
        "part_start_page", "part_end_page",
    },
    "audio_document": {
        "title", "subtitle", "is_partial", "seconds",
        "physical_details", "additional_notes", "url", "viewed_at",
        "part_identifier", "part_responsibilities",
    },
    "musical_score": {
        "title", "subtitle", "authors", "is_partial",
        "author_role", "physical_description", "additional_notes",
        "url", "viewed_at", "part_volume", "part_start_page",
        "part_end_page",
    },
    "journal_article": {
        "title", "subtitle", "authors", "date_anchor",
        "url", "viewed_at", "journal_subtitle", "volume", "year_season",
        "number", "part_start_page", "part_end_page", "issn",
        "additional_notes",
    },
    "periodical_collection": {
        "journal_subtitle", "publisher", "first_volume_year",
        "last_volume_year", "issn", "additional_notes", "url", "viewed_at",
        "consult_start_year", "consult_end_year",
    },
}
ALWAYS_PARTIAL_TYPES = {
    "journal_article",
    "periodical_collection",
}
PARENT_WORK_TYPES = {
    "editorial_monograph": "editorial_monograph",
    "academic_monograph": "academic_monograph",
    "correspondence_monograph": "correspondence_monograph",
    "monographic_proceedings": "monographic_proceedings",
    "periodical_proceedings": "periodical_proceedings",
    "audio_document": "audio_document",
    "musical_score": "musical_score",
    "journal_article": "magazine",
    "periodical_collection": "magazine",
}

PUBLICATION = (
    FieldSpec(
        key="publication_place",
        label="Local de publicação (se houver)",
        hint="Ex.: São Paulo",
        required=True
    ),
    FieldSpec(
        key="publisher",
        label="Editora / produtor (se houver)",
        hint="Ex.: Boitempo",
        required=True
    ),
)

DEFAULTED_FIELDS = {
    "editorial_monograph": {"publication_place", "publisher"},
    "academic_monograph": {"publication_place"},
    "correspondence_monograph": {"publication_place"},
    "periodical_collection": {"publication_place", "publisher"},
    "journal_article": {"publication_place"},
    "newspaper_article": {
        "publication_place",
        "publisher",
        "start_page",
        "end_page",
    },
    "monographic_proceedings": {
        "title",
        "publication_place",
        "publisher",
        "published",
    },
    "periodical_proceedings": {
        "title",
        "publication_place",
        "publisher",
        "start_page",
        "end_page",
    },
    "patent": {"title"},
    "miscellaneous_digital_document": {"publication_place"},
    "audiovisual_document": {"publication_place", "publisher"},
    "audio_document": {"publication_place", "publisher"},
    "musical_score": {"publication_place", "publisher"},
    "cartographic_document": {"publication_place", "publisher"},
    "three_dimensional_document": {"manufacturing_place", "manufacturer"},
}


def _spec(key, label, description, icon, *fields):
    date_kind = (
        "month"
        if key == "journal_article"
        else "date"
        if key in {
            "newspaper_article",
            "statute",
            "caselaw",
        }
        else "year"
    )
    partial_fields = (
        JOURNAL_ARTICLE_PARTIAL
        if key == "journal_article"
        else PERIODICAL_COLLECTION_PARTIAL
        if key == "periodical_collection"
        else PARTIAL_FIELDS_BY_TYPE.get(key, ())
    )

    common_fields = tuple(
        (
            FieldSpec(
                key="authors",
                label=(
                    "Autor(es) / entidade responsável (se houver)"
                    if key == "cartographic_document"
                    else "Autores / criadores / inventores (se houver)"
                ),
                hint="Ex.: Cláudia França",
                required=False,
            )
            if (
                key in OPTIONAL_AUTHORS_TYPES
                and field.key == "authors"
            )
            else field
        )
        for field in COMMON
        if (
            (key not in NO_GENERIC_AUTHORS_TYPES or field.key != "authors")
            and not (
                key in MULTIMEDIA_WORK_TYPES
                and field.key in {"abstract", "date_precision"}
            )
        )
    )
    if key in MULTIMEDIA_WORK_TYPES:
        common_fields = tuple(
            FieldSpec(
                key="date_anchor",
                label="Ano de publicação (como consta no documento)",
                hint="Ex.: 2018, c2003, [ca. 1470-1475], [200-] ou [s.d.]",
                kind="year",
                required=True,
            )
            if field.key == "date_anchor"
            else field
            for field in common_fields
        )
    if key == "periodical_collection":
        common_fields = tuple(
            field for field in common_fields
            if field.key in {"url", "viewed_at"}
        )
    if key == "periodical_proceedings":
        common_fields = tuple(
            field for field in common_fields
            if field.key not in {"date_anchor", "date_precision"}
        )
    if key == "three_dimensional_document":
        common_fields = tuple(
            FieldSpec(
                key="title",
                label="Título ou denominação do objeto",
                hint=(
                    "Se não houver título, descreva o objeto "
                    "entre colchetes"
                ),
                required=True,
            )
            if field.key == "title"
            else field
            for field in common_fields
        )
    base_fields = () if key == "magazine" else common_fields + partial_fields
    fields_dict = {f.key: f for f in base_fields}
    if key == "visual_document":
        fields_dict["title"] = FieldSpec(
            key="title",
            label="Título (se houver)",
            hint="Deixe em branco se o documento não tiver título",
            required=False,
        )
        fields_dict["authors"] = FieldSpec(
            key="authors",
            label="Autor(es), se houver",
            hint="Ex.: Rosaly Senra",
            required=False,
        )
    for field in fields:
        fields_dict[field.key] = field

    if key == "statute":
        statute_fields = tuple(
            field for field in COMMON if field.key != "date_anchor"
        ) + (
            FieldSpec(
                key="promulgation_date",
                label="Data de promulgação",
                hint="DD/MM/AAAA",
                kind="date",
                required=True,
            ),
            FieldSpec(
                key="publication_media",
                label="Veículo / mídia de publicação",
                hint="Ex.: Diário Oficial da União",
                required=True,
            ),
            FieldSpec(
                key="publication_place",
                label="Local de publicação",
                hint="Ex.: Brasília",
            ),
            FieldSpec(
                key="date_anchor",
                label="Data de publicação",
                hint="DD/MM/AAAA",
                kind="date",
                required=True,
            ),
            FieldSpec(
                key="publication_number",
                label="Número da publicação",
                hint="Ex.: 123",
                kind="number",
            ),
            FieldSpec(key="additional_notes", label="Notas adicionais"),
        )
        return WorkTypeSpec(
            key=key,
            label=label,
            description=description,
            icon=icon,
            fields=statute_fields,
            date_kind=date_kind,
        )
    return WorkTypeSpec(
        key=key,
        label=label,
        description=description,
        icon=icon,
        fields=tuple(fields_dict.values()),
        date_kind=date_kind,
    )

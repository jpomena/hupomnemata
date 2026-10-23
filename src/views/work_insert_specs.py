"""Especificacoes declarativas dos tipos e campos do cadastro de obras."""

from dataclasses import dataclass

import flet as ft


@dataclass(frozen=True)
class FieldSpec:
    """Descreve um campo exibido no formulario de cadastro."""

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
    if key == "periodical_collection":
        common_fields = tuple(
            field for field in common_fields
            if field.key in {"url", "viewed_at"}
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


WORK_TYPES = (
    _spec(
        "editorial_monograph",
        "Livros em geral",
        "Livro, enciclopédia ou catálogo",
        ft.Icons.BOOK_OUTLINED,
        *PUBLICATION,
        FieldSpec(key="edition", label="Edição", kind="number"),
        FieldSpec(
            key="page_quantity",
            label="Quantidade de páginas",
            hint='Ex.: 416',
            kind="number"
        ),
        FieldSpec(
            key="volumes",
            label="Quantidade de volumes, se mais de um",
            kind="number"
        ),
        FieldSpec(
            key="illustrations",
            label="Possui ilustrações",
            kind="checkbox"
        ),
        FieldSpec(
            key="dimensions",
            label="Dimensões",
            hint="Ex.: 21 x 14 x 2 cm"
        ),
        FieldSpec(
            key="collection_name",
            label="Nome da coleção",
            hint="Ex.: Estado de sítio"
        ),
        FieldSpec(
            key="collection_number",
            label="Número da obra na coleção",
            kind="number"
        ),
        FieldSpec(
            key="translation_notes",
            label="Notas de tradução",
            hint="Ex.: tradução Mariana Echalar"
        ),
        FieldSpec(
            key="original_full_title",
            label="Título original completo",
            hint=(
                "Ex.: La Nouvelle raison du monde"
                ": essai sur la société néolibérale"
            )
        ),
        FieldSpec(
            key="additional_notes",
            label="Notas adicionais",
            hint="Quaisquer outras notas sobre a obra"
        ),
        FieldSpec(key="isbn", label="ISBN", hint="Ex.: 978-85-7559-484-1"),
        FieldSpec(
            key="responsibilities",
            label="Notas de responsabilidade:",
            kind="responsibilities",
        )
    ),
    _spec(
        "journal_article",
        "Artigo de revista",
        "Artigo ou comunicação científica",
        ft.Icons.ARTICLE_OUTLINED,
        FieldSpec(
            key="journal_subtitle",
            label="Subtítulo do periódico",
            hint="Ex.: revista de estudos sociais"
        ),
        FieldSpec(
            key="volume", label="Volume", hint="Ex.: 12", kind="number"
        ),
        FieldSpec(
            key="year_season",
            label="Ano da revista",
            hint="Ex.: 4",
            kind="number"
        ),
        FieldSpec(
            key="number",
            label="Número do fascículo",
            hint="Ex.: 3",
            kind="number",
            required=True
        ),
        FieldSpec(key="issn", label="ISSN", hint="Ex.: 2317-1782"),
        FieldSpec(key="additional_notes", label="Notas adicionais")
    ),
    _spec(
        "academic_monograph",
        "Trabalho acadêmico",
        "Trabalho acadêmico",
        ft.Icons.SCHOOL_OUTLINED,
        *PUBLICATION,
        FieldSpec(
            key="page_quantity",
            label="Quantidade de páginas",
            hint="Ex.: 120",
            kind="number",
            required=True
        ),
        FieldSpec(
            key="thesis_type",
            label="Tipo de trabalho",
            hint="Ex.: Dissertação",
            required=True
        ),
        FieldSpec(
            key="education_level",
            label="Nível de formação",
            hint="Ex.: Mestrado",
            required=True
        ),
        FieldSpec(
            key="course",
            label="Curso",
            hint="Ex.: Sociologia",
            required=True
        ),
        FieldSpec(
            key="faculty",
            label="Faculdade / instituição",
            hint="Ex.: Universidade de São Paulo",
            required=True
        ),
        FieldSpec(
            key="defense_year",
            label="Ano de defesa",
            kind="number",
            required=True,
        ),
        FieldSpec(key="additional_notes", label="Notas adicionais")
    ),
    _spec(
        "monographic_proceedings",
        "Anais de evento em volume único",
        "Anais de evento em volume único",
        ft.Icons.EVENT,
        FieldSpec(
            key="event_name",
            label="Nome do evento",
            hint="Ex.: Congresso Brasileiro de Sociologia",
            required=True
        ),
        FieldSpec(
            key="event_number",
            label="Número do evento",
            hint="Ex.: 20",
            kind="number"
        ),
        FieldSpec(
            key="event_year",
            label="Ano do evento",
            kind="number",
            required=True
        ),
        FieldSpec(
            key="event_place", label="Local do evento", hint="Ex.: São Paulo"
        ),
        *PUBLICATION,
        FieldSpec(
            key="page_quantity", label="Quantidade de páginas", kind="number"
        ),
        FieldSpec(key="isbn", label="ISBN", hint="Ex.: 978-85-0000-000-0"),
        FieldSpec(key="published", label="Publicado", kind="checkbox")
    ),
    _spec(
        "periodical_proceedings",
        "Anais de evento em periódico",
        "Anais de evento periódico",
        ft.Icons.EVENT_NOTE,
        FieldSpec(
            key="event_name",
            label="Nome do evento",
            hint="Ex.: Congresso Brasileiro de Sociologia",
            required=True
        ),
        FieldSpec(
            key="event_number",
            label="Número do evento",
            hint="Ex.: 20",
            kind="number"
        ),
        FieldSpec(
            key="event_year",
            label="Ano do evento",
            kind="number",
            required=True
        ),
        FieldSpec(
            key="event_place", label="Local do evento", hint="Ex.: São Paulo"
        ),
        FieldSpec(
            key="publication_place",
            label="Local de publicação (se houver)",
            hint="Ex.: São Paulo",
            required=True,
        ),
        FieldSpec(key="vol_or_year", label="Volume / ano", kind="number"),
        FieldSpec(key="number", label="Número", kind="number", required=True),
        FieldSpec(key="start_page", label="Página inicial", required=True),
        FieldSpec(key="end_page", label="Página final", required=True),
        FieldSpec(
            key="publication_date",
            label="Data de publicação",
            kind="date",
            required=True,
        ),
        FieldSpec(key="issn", label="ISSN", hint="Ex.: 2317-1782")
    ),
    _spec(
        "newspaper_article",
        "Artigo de jornal",
        "Reportagem, entrevista ou editorial",
        ft.Icons.NEWSPAPER_OUTLINED,
        FieldSpec(
            key="journal_title",
            label="Título do jornal",
            hint="Ex.: Folha de S.Paulo",
            required=True
        ),
        FieldSpec(
            key="journal_subtitle",
            label="Subtítulo do jornal",
            hint="Ex.: edição de domingo"
        ),
        *PUBLICATION,
        FieldSpec(key="volume", label="Volume", kind="number"),
        FieldSpec(key="year_season", label="Ano / estação", kind="number"),
        FieldSpec(key="number", label="Número", kind="number"),
        FieldSpec(key="section", label="Seção", hint="Ex.: Política"),
        FieldSpec(key="start_page", label="Página inicial", required=True),
        FieldSpec(key="end_page", label="Página final", required=True),
        FieldSpec(key="issn", label="ISSN", hint="Ex.: 0101-3300")
    ),
    _spec(
        "statute",
        "Legislação",
        "Lei, decreto ou norma",
        ft.Icons.GAVEL,
    ),
    _spec(
        "caselaw",
        "Jurisprudência",
        "Acórdão, sentença ou decisão",
        ft.Icons.ACCOUNT_BALANCE,
        FieldSpec(
            key="publication_media",
            label="Veículo / mídia de publicação",
            hint="Ex.: Tribunal Regional Federal",
            required=True,
        ),
        FieldSpec(
            key="publication_place",
            label="Local de publicação",
            hint="Ex.: São Paulo",
        ),
        FieldSpec(
            key="panel",
            label="Tribunal / órgão julgador",
            hint="Ex.: Segunda Turma",
        ),
        FieldSpec(
            key="region",
            label="Região / instância",
            hint="Ex.: Tribunal Regional Federal 4ª Região",
        ),
        FieldSpec(
            key="decision_type",
            label="Tipo de decisão",
            hint="Ex.: Acórdão",
            required=True
        ),
        FieldSpec(
            key="decision_date",
            label="Data da decisão",
            kind="date",
            required=True,
        ),
        FieldSpec(
            key="case_number",
            label="Número do processo",
            hint="Ex.: 0001234-56.2024.8.26.0000",
        ),
        FieldSpec(
            key="rapporteur", label="Relator", hint="Ex.: Min. Cármen Lúcia"
        ),
        FieldSpec(key="additional_notes", label="Notas adicionais"),
    ),
    _spec(
        "miscellaneous_digital_document",
        "Documento digital",
        "Documento digital diverso",
        ft.Icons.INSERT_DRIVE_FILE_OUTLINED,
        FieldSpec(
            key="version", label="Versão", hint="Ex.: 2", kind="number"
        ),
        FieldSpec(
            key="publication_place",
            label="Local de publicação (se houver)",
            hint="Ex.: São Paulo",
            required=False
        ),
        FieldSpec(key="additional_notes", label="Notas adicionais")
    ),
    _spec(
        "audiovisual_document",
        "Audiovisual",
        "Filme, vídeo ou gravação",
        ft.Icons.VIDEO_LIBRARY_OUTLINED,
        FieldSpec(
            key="carrier_type",
            label="Tipo de suporte",
            hint="Ex.: DVD",
            required=True
        ),
        FieldSpec(
            key="seconds",
            label="Duração em segundos",
            hint="Ex.: 5400",
            kind="number",
            required=True,
        ),
        FieldSpec(key="sound", label="Possui som", kind="checkbox"),
        FieldSpec(key="colorized", label="Colorizado", kind="checkbox"),
        *PUBLICATION,
        FieldSpec(
            key="responsibilities",
            label="Responsabilidades (direção, produção etc.)",
            kind="responsibilities",
        ),
        FieldSpec(key="additional_notes", label="Notas adicionais")
    ),
    _spec(
        "audio_document",
        "Áudio",
        "Disco, podcast ou gravação sonora",
        ft.Icons.AUDIOTRACK,
        FieldSpec(
            key="carrier_type",
            label="Tipo de suporte (obrigatório se não houver URL)",
            required=False,
        ),
        FieldSpec(
            key="seconds",
            label="Duração em segundos (se houver)",
            hint="Ex.: 1034",
            kind="number",
            required=False,
        ),
        FieldSpec(
            key="physical_details",
            label="Detalhes físicos (se houver)",
            hint="Ex.: 33 rpm, estéreo",
        ),
        FieldSpec(
            key="additional_notes",
            label="Notas adicionais",
            hint="Ex.: App Google Play Livros",
        ),
        FieldSpec(
            key="responsibilities",
            label="Responsabilidades (compositor, intérprete, ledor etc.)",
            kind="responsibilities",
        ),
        FieldSpec(
            key="authors",
            label="Autoria (se houver; para audiolivro)",
            hint="Autor da obra, como indicado no audiolivro",
            required=False,
        ),
        *PUBLICATION
    ),
    _spec(
        "correspondence_monograph",
        "Correspondência",
        "Carta, telegrama ou e-mail",
        ft.Icons.MAIL_OUTLINE,
        *PUBLICATION,
        FieldSpec(
            key="recipient", label="Destinatário", hint="Ex.: Machado de Assis"
        ),
        FieldSpec(
            key="correspondence_type",
            label="Tipo de correspondência",
            hint="Ex.: Carta",
            required=True,
        ),
        FieldSpec(key="additional_notes", label="Notas adicionais")
    ),
    _spec(
        "periodical_collection",
        "Coleção periódica",
        "Coleção de volumes ou fascículos de uma revista",
        ft.Icons.MENU_BOOK,
        FieldSpec(
            key="journal_subtitle",
            label="Subtítulo do periódico",
            hint="Ex.: revista de estudos sociais"
        ),
        FieldSpec(
            key="first_volume_year",
            label="Ano do primeiro volume",
            kind="number",
            required=True,
        ),
        FieldSpec(
            key="last_volume_year",
            label="Ano do último volume",
            hint="Ex.: 2024",
            kind="number"
        ),
        FieldSpec(
            key="publisher",
            label="Editora / produtor (se houver)",
            hint="Ex.: Boitempo",
        ),
        FieldSpec(key="issn", label="ISSN", hint="Ex.: 2317-1782"),
        FieldSpec(key="additional_notes", label="Notas adicionais")
    ),
    _spec(
        "magazine",
        "Revista",
        "Cadastro de uma revista",
        ft.Icons.MENU_BOOK,
        FieldSpec(
            key="title",
            label="Nome da revista",
            hint="Ex.: Revista Brasileira de Ciências Sociais",
            required=True,
        ),
        FieldSpec(
            key="publication_place",
            label="Local de publicação",
            hint="Ex.: São Paulo",
            required=True,
        ),
    ),
    _spec(
        "patent",
        "Patente",
        "Documento de propriedade industrial",
        ft.Icons.LIGHTBULB_OUTLINE,
        FieldSpec(
            key="applicant",
            label="Requerente",
            hint="Ex.: Instituto Butantan",
            required=True,
        ),
        FieldSpec(
            key="representative", label="Representante", hint="Ex.: Ana Souza"
        ),
        FieldSpec(
            key="number",
            label="Número da patente",
            hint="Ex.: BR1020240001234",
            required=True,
        ),
        FieldSpec(
            key="filing_date",
            label="Data de depósito",
            hint="DD/MM/AAAA",
            kind="date",
            required=True,
        ),
        FieldSpec(
            key="grant_date",
            label="Data de concessão",
            hint="DD/MM/AAAA",
            kind="date"
        ),
    ),
    _spec(
        "musical_score",
        "Partitura",
        "Partitura ou obra musical",
        ft.Icons.MUSIC_NOTE,
        FieldSpec(
            key="instrumentation",
            label="Instrumentação",
            hint="Ex.: piano e voz (não repetir se já constar no título)",
            required=False,
        ),
        FieldSpec(
            key="author_role",
            label="Função da autoria (se houver)",
            hint="Ex.: comp. ou ed.",
        ),
        FieldSpec(
            key="physical_description",
            label="Descrição física",
            hint="Ex.: 1 partitura (86 p.) + 1 parte (34 p.)",
            required=True,
        ),
        FieldSpec(key="authors", label="Compositor(es), se houver"),
        *PUBLICATION,
        FieldSpec(key="additional_notes", label="Notas adicionais")
    ),
    _spec(
        "visual_document",
        "Documento visual",
        "Fotografia, cartaz ou imagem",
        ft.Icons.IMAGE_OUTLINED,
        FieldSpec(
            key="physical_description",
            label="Especificação do suporte",
            hint="Ex.: 3 fotografias, color., 10 cm x 8 cm",
            required=True,
        ),
        FieldSpec(key="additional_notes", label="Notas adicionais"),
    ),
    _spec(
        "cartographic_document",
        "Cartográfico",
        "Mapa, atlas ou carta",
        ft.Icons.MAP_OUTLINED,
        FieldSpec(
            key="edition", label="Edição", hint="Ex.: 2", kind="number"
        ),
        FieldSpec(
            key="physical_description",
            label="Descrição física",
            hint="Ex.: xiv, 135 p., il. col., 30 cm",
            required=True,
        ),
        *PUBLICATION,
        FieldSpec(
            key="additional_notes",
            label="Elementos complementares",
            hint="Ex.: escala, coordenadas, cores ou outras representações",
        ),
    ),
    _spec(
        "three_dimensional_document",
        "Tridimensional",
        "Objeto tridimensional",
        ft.Icons.VIEW_IN_AR,
        FieldSpec(
            key="manufacturing_place",
            label="Local (se houver)",
            hint="Ex.: Portugal",
        ),
        FieldSpec(
            key="manufacturer",
            label="Produtor ou fabricante (se houver)",
            hint="Ex.: Editora Abril",
        ),
        FieldSpec(
            key="physical_description",
            label="Descrição física",
            hint=(
                "Ex.: 1 escultura, estruturas tensionadas,"
                " color., 400 x 250 x 250 cm"
            ),
            required=True,
        ),
        FieldSpec(key="additional_notes", label="Elementos complementares"),
    ),
)

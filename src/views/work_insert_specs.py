"""Especificacoes declarativas dos tipos e campos do cadastro de obras."""

from dataclasses import dataclass

import flet as ft


@dataclass(frozen=True)
class FieldSpec:
    """Descreve um campo exibido no formulario de cadastro."""

    key: str
    label: str
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
    FieldSpec("title", "Título da obra", required=True),
    FieldSpec("subtitle", "Subtítulo"),
    FieldSpec(
        "authors",
        "Autores / responsáveis, separados por ponto e vírgula",
        required=True,
    ),
    FieldSpec("abstract", "Resumo / descrição (se houver)", "multiline"),
    FieldSpec("date_anchor", "Ano de publicação (ou estimado)", "year", True),
    FieldSpec("date_precision", "Precisão da data", "dropdown"),
    FieldSpec("url", "URL"),
    FieldSpec("viewed_at", "Data de acesso", "date"),
)

PARTIAL = (
    FieldSpec("is_partial", "É parte de outra obra", "checkbox"),
    FieldSpec("part_volume", "Volume da parte (se houver)"),
    FieldSpec("part_chapter", "Capítulo da parte (se houver)"),
    FieldSpec("part_start_page", "Página inicial da parte (se houver)"),
    FieldSpec("part_end_page", "Página final da parte (se houver)"),
    FieldSpec(
        "consult_start_year",
        "Ano inicial consultado (para coleções de periódicos)",
        "number",
    ),
    FieldSpec(
        "consult_end_year",
        "Ano final consultado (se houver, para coleções de periódicos)",
        "number",
    ),
)

PUBLICATION = (
    FieldSpec(
        "publication_place", "Local de publicação (se houver)", required=True
    ),
    FieldSpec("publisher", "Editora / produtor (se houver)", required=True),
)

DEFAULTED_FIELDS = {
    "editorial_monograph": {"publication_place", "publisher"},
    "academic_monograph": {"publication_place"},
    "correspondence_monograph": {"publication_place"},
    "periodical_collection": {"publication_place", "publisher"},
    "journal_article": {"publication_place", "publisher"},
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
    "audio_document": {"publication_place", "publisher", "is_part"},
    "musical_score": {"publication_place", "publisher"},
    "cartographic_document": {"publication_place", "publisher"},
    "three_dimensional_document": {"manufacturing_place", "manufacturer"},
}


def _spec(key, label, description, icon, *fields):
    date_kind = (
        "date" if key in {"journal_article", "newspaper_article"} else "year"
    )
    return WorkTypeSpec(
        key, label, description, icon, COMMON + PARTIAL + fields, date_kind
    )


WORK_TYPES = (
    _spec(
        "editorial_monograph",
        "Livro",
        "Livro, enciclopédia ou catálogo",
        ft.Icons.BOOK_OUTLINED,
        *PUBLICATION,
        FieldSpec("edition", "Edição", "number"),
        FieldSpec("page_quantity", "Quantidade de páginas", "number"),
        FieldSpec("volumes", "Quantidade de volumes, se mais de um", "number"),
        FieldSpec("illustrations", "Possui ilustrações", "checkbox"),
        FieldSpec("dimensions", "Dimensões"),
        FieldSpec("collection_name", "Nome da coleção"),
        FieldSpec("collection_number", "Número da obra na coleção", "number"),
        FieldSpec("translation_notes", "Notas de tradução"),
        FieldSpec("original_full_title", "Título original completo"),
        FieldSpec("additional_notes", "Notas adicionais"),
        FieldSpec("isbn", "ISBN"),
        FieldSpec(
            "responsabilities",
            "Notas de responsabilidade:",
            "responsabilities",
        )
    ),
    _spec(
        "journal_article",
        "Artigo de revista",
        "Artigo ou comunicação científica",
        ft.Icons.ARTICLE_OUTLINED,
        FieldSpec("journal_title", "Título do periódico", required=True),
        FieldSpec("journal_subtitle", "Subtítulo do periódico"),
        *PUBLICATION,
        FieldSpec("volume", "Volume", "number"),
        FieldSpec("year_season", "Ano / estação", "number"),
        FieldSpec("number", "Número", "number", True),
        FieldSpec("issn", "ISSN"),
        FieldSpec("additional_notes", "Notas adicionais")
    ),
    _spec(
        "academic_monograph",
        "Tese / dissertação",
        "Trabalho acadêmico",
        ft.Icons.SCHOOL_OUTLINED,
        *PUBLICATION,
        FieldSpec("page_quantity", "Quantidade de páginas", "number", True),
        FieldSpec("thesis_type", "Tipo de trabalho", required=True),
        FieldSpec("education_level", "Nível de formação", required=True),
        FieldSpec("course", "Curso", required=True),
        FieldSpec("faculty", "Faculdade / instituição", required=True),
        FieldSpec("defense_year", "Ano de defesa", "number", True),
        FieldSpec("additional_notes", "Notas adicionais")
    ),
    _spec(
        "monographic_proceedings",
        "Anais monográficos de evento",
        "Anais de evento em volume único",
        ft.Icons.EVENT,
        FieldSpec("event_name", "Nome do evento", required=True),
        FieldSpec("event_number", "Número do evento", "number"),
        FieldSpec("event_year", "Ano do evento", "number", True),
        FieldSpec("event_place", "Local do evento"),
        *PUBLICATION,
        FieldSpec("publication_year", "Ano de publicação", "number", True),
        FieldSpec("page_quantity", "Quantidade de páginas", "number"),
        FieldSpec("isbn", "ISBN"),
        FieldSpec("published", "Publicado", "checkbox")
    ),
    _spec(
        "periodical_proceedings",
        "Anais periódicos de evento",
        "Anais de evento periódico",
        ft.Icons.EVENT_NOTE,
        FieldSpec("event_name", "Nome do evento", required=True),
        FieldSpec("event_number", "Número do evento", "number"),
        FieldSpec("event_year", "Ano do evento", "number", True),
        FieldSpec("event_place", "Local do evento"),
        *PUBLICATION,
        FieldSpec("publication_year", "Ano de publicação", "number", True),
        FieldSpec("page_quantity", "Quantidade de páginas", "number"),
        FieldSpec("vol_or_year", "Volume / ano", "number"),
        FieldSpec("number", "Número", "number", True),
        FieldSpec("start_page", "Página inicial", required=True),
        FieldSpec("end_page", "Página final", required=True),
        FieldSpec("publication_date", "Data de publicação", "date", True),
        FieldSpec("issn", "ISSN")
    ),
    _spec(
        "newspaper_article",
        "Artigo de jornal",
        "Reportagem, entrevista ou editorial",
        ft.Icons.NEWSPAPER_OUTLINED,
        FieldSpec("journal_title", "Título do jornal", required=True),
        FieldSpec("journal_subtitle", "Subtítulo do jornal"),
        *PUBLICATION,
        FieldSpec("volume", "Volume", "number"),
        FieldSpec("year_season", "Ano / estação", "number"),
        FieldSpec("number", "Número", "number"),
        FieldSpec("section", "Seção"),
        FieldSpec("start_page", "Página inicial", required=True),
        FieldSpec("end_page", "Página final", required=True),
        FieldSpec("issn", "ISSN")
    ),
    _spec(
        "statute",
        "Legislação",
        "Lei, decreto ou norma",
        ft.Icons.GAVEL,
        FieldSpec("additional_notes", "Notas adicionais"),
    ),
    _spec(
        "caselaw",
        "Jurisprudência",
        "Acórdão, sentença ou decisão",
        ft.Icons.ACCOUNT_BALANCE,
        FieldSpec("decision_type", "Tipo de decisão", required=True),
        FieldSpec("decision_date", "Data da decisão", "date", True),
        FieldSpec("case_number", "Número do processo"),
        FieldSpec("rapporteur", "Relator"),
        FieldSpec("additional_notes", "Notas adicionais"),
    ),
    _spec(
        "administrative_act",
        "Ato administrativo",
        "Portaria, edital ou parecer",
        ft.Icons.ACCOUNT_BALANCE_OUTLINED,
        FieldSpec("additional_notes", "Notas adicionais"),
    ),
    _spec(
        "miscellaneous_digital_document",
        "Documento digital",
        "Documento digital diverso",
        ft.Icons.INSERT_DRIVE_FILE_OUTLINED,
        FieldSpec("version", "Versão", "number"),
        *PUBLICATION,
        FieldSpec("additional_notes", "Notas adicionais")
    ),
    _spec(
        "audiovisual_document",
        "Audiovisual",
        "Filme, vídeo ou gravação",
        ft.Icons.VIDEO_LIBRARY_OUTLINED,
        FieldSpec("carrier_type", "Tipo de suporte", required=True),
        FieldSpec("seconds", "Duração em segundos", "number", True),
        FieldSpec("sound", "Possui som", "checkbox"),
        FieldSpec("colorized", "Colorizado", "checkbox"),
        *PUBLICATION,
        FieldSpec("responsabilities", "Responsabilidades", "responsabilities"),
        FieldSpec("additional_notes", "Notas adicionais")
    ),
    _spec(
        "audio_document",
        "Áudio",
        "Disco, podcast ou gravação sonora",
        ft.Icons.AUDIOTRACK,
        FieldSpec("carrier_type", "Tipo de suporte", required=True),
        FieldSpec("is_part", "É parte de uma obra sonora", "checkbox"),
        FieldSpec(
            "part_responsabilities",
            "Responsabilidades da parte",
            "responsabilities",
        ),
        FieldSpec("part_identifier", "Identificador da parte", required=True),
        FieldSpec("responsabilities", "Responsabilidades", "responsabilities"),
        *PUBLICATION
    ),
    _spec(
        "correspondence_monograph",
        "Correspondência",
        "Carta, telegrama ou e-mail",
        ft.Icons.MAIL_OUTLINE,
        *PUBLICATION,
        FieldSpec("recipient", "Destinatário"),
        FieldSpec(
            "correspondence_type", "Tipo de correspondência", required=True
        ),
        FieldSpec("additional_notes", "Notas adicionais")
    ),
    _spec(
        "periodical_collection",
        "Coleção periódica",
        "Revista ou jornal completo",
        ft.Icons.MENU_BOOK,
        FieldSpec("journal_title", "Título do periódico", required=True),
        FieldSpec("journal_subtitle", "Subtítulo do periódico"),
        FieldSpec(
            "first_volume_year", "Ano do primeiro volume", "number", True
        ),
        FieldSpec("last_volume_year", "Ano do último volume", "number"),
        *PUBLICATION,
        FieldSpec("issn", "ISSN"),
        FieldSpec("additional_notes", "Notas adicionais")
    ),
    _spec(
        "patent",
        "Patente",
        "Documento de propriedade industrial",
        ft.Icons.LIGHTBULB_OUTLINE,
        FieldSpec("applicant", "Requerente", required=True),
        FieldSpec("representative", "Representante"),
        FieldSpec("number", "Número da patente", required=True),
        FieldSpec("filing_date", "Data de depósito", "date", True),
        FieldSpec("grant_date", "Data de concessão", "date"),
    ),
    _spec(
        "musical_score",
        "Partitura",
        "Partitura ou obra musical",
        ft.Icons.MUSIC_NOTE,
        FieldSpec("instrumentation", "Instrumentação", required=True),
        *PUBLICATION,
        FieldSpec("additional_notes", "Notas adicionais")
    ),
    _spec(
        "visual_document",
        "Documento visual",
        "Fotografia, cartaz ou imagem",
        ft.Icons.IMAGE_OUTLINED,
    ),
    _spec(
        "cartographic_document",
        "Cartográfico",
        "Mapa, atlas ou carta",
        ft.Icons.MAP_OUTLINED,
        FieldSpec("edition", "Edição", "number"),
        *PUBLICATION,
        FieldSpec("additional_notes", "Notas adicionais")
    ),
    _spec(
        "three_dimensional_document",
        "Tridimensional",
        "Objeto tridimensional",
        ft.Icons.VIEW_IN_AR,
        FieldSpec(
            "responsability_type", "Tipo de responsabilidade", required=True
        ),
        FieldSpec("manufacturing_place", "Local de fabricação", required=True),
        FieldSpec("manufacturer", "Fabricante", required=True),
    ),
)

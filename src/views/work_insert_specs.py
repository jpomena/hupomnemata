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
        label="Autores / responsáveis, separados por ponto e vírgula",
        hint="Ex.: Pierre Dardot; Christian Laval",
        required=True,
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

PARTIAL = (
    FieldSpec(
        key="is_partial",
        label="É parte de outra obra",
        kind="checkbox"
    ),
    FieldSpec(
        key="part_volume",
        label="Volume da parte (se houver)",
        hint="Ex.: 2"
    ),
    FieldSpec(
        key="part_chapter",
        label="Capítulo da parte (se houver)",
        hint="Ex.: 3"
    ),
    FieldSpec(
        key="part_start_page",
        label="Página inicial da parte (se houver)",
        hint="Ex.: 45"
    ),
    FieldSpec(
        key="part_end_page",
        label="Página final da parte (se houver)",
        hint="Ex.: 68"
    ),
    FieldSpec(
        key="consult_start_year",
        label="Ano inicial consultado (para coleções de periódicos)",
        hint="Ex.: 2019",
        kind="number",
    ),
    FieldSpec(
        key="consult_end_year",
        label="Ano final consultado (se houver, para coleções de periódicos)",
        hint="Ex.: 2024",
        kind="number",
    ),
)

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
        key=key,
        label=label,
        description=description,
        icon=icon,
        fields=COMMON + PARTIAL + fields,
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
            key="responsabilities",
            label="Notas de responsabilidade:",
            kind="responsabilities",
        )
    ),
    _spec(
        "journal_article",
        "Artigo de revista",
        "Artigo ou comunicação científica",
        ft.Icons.ARTICLE_OUTLINED,
        FieldSpec(
            key="journal_title",
            label="Título do periódico",
            hint="Ex.: Revista Brasileira de Ciências Sociais",
            required=True
        ),
        FieldSpec(
            key="journal_subtitle",
            label="Subtítulo do periódico",
            hint="Ex.: revista de estudos sociais"
        ),
        *PUBLICATION,
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
            key="publication_year",
            label="Ano de publicação",
            kind="number",
            required=True,
        ),
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
        *PUBLICATION,
        FieldSpec(
            key="publication_year",
            label="Ano de publicação",
            kind="number",
            required=True,
        ),
        FieldSpec(
            key="page_quantity", label="Quantidade de páginas", kind="number"
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
        FieldSpec(key="additional_notes", label="Notas adicionais"),
    ),
    _spec(
        "caselaw",
        "Jurisprudência",
        "Acórdão, sentença ou decisão",
        ft.Icons.ACCOUNT_BALANCE,
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
        "administrative_act",
        "Ato administrativo",
        "Portaria, edital ou parecer",
        ft.Icons.ACCOUNT_BALANCE_OUTLINED,
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
        *PUBLICATION,
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
            key="responsabilities",
            label="Responsabilidades",
            kind="responsabilities",
        ),
        FieldSpec(key="additional_notes", label="Notas adicionais")
    ),
    _spec(
        "audio_document",
        "Áudio",
        "Disco, podcast ou gravação sonora",
        ft.Icons.AUDIOTRACK,
        FieldSpec(key="carrier_type", label="Tipo de suporte", required=True),
        FieldSpec(
            key="is_part", label="É parte de uma obra sonora", kind="checkbox"
        ),
        FieldSpec(
            key="part_responsabilities",
            label="Responsabilidades da parte",
            hint="Ex.: intérprete Maria Bethânia",
            kind="responsabilities",
        ),
        FieldSpec(
            key="part_identifier",
            label="Identificador da parte",
            hint="Ex.: faixa 3",
            required=True,
        ),
        FieldSpec(
            key="responsabilities",
            label="Responsabilidades",
            kind="responsabilities",
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
        "Revista ou jornal completo",
        ft.Icons.MENU_BOOK,
        FieldSpec(
            key="journal_title",
            label="Título do periódico",
            hint="Ex.: Revista Brasileira de Ciências Sociais",
            required=True
        ),
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
        *PUBLICATION,
        FieldSpec(key="issn", label="ISSN", hint="Ex.: 2317-1782"),
        FieldSpec(key="additional_notes", label="Notas adicionais")
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
            hint="Ex.: piano e voz",
            required=True
        ),
        *PUBLICATION,
        FieldSpec(key="additional_notes", label="Notas adicionais")
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
        FieldSpec(
            key="edition", label="Edição", hint="Ex.: 2", kind="number"
        ),
        *PUBLICATION,
        FieldSpec(key="additional_notes", label="Notas adicionais")
    ),
    _spec(
        "three_dimensional_document",
        "Tridimensional",
        "Objeto tridimensional",
        ft.Icons.VIEW_IN_AR,
        FieldSpec(
            key="responsability_type",
            label="Tipo de responsabilidade",
            hint="Ex.: fabricante",
            required=True,
        ),
        FieldSpec(
            key="manufacturing_place",
            label="Local de fabricação",
            hint="Ex.: São Paulo",
            required=True,
        ),
        FieldSpec(
            key="manufacturer",
            label="Fabricante",
            hint="Ex.: Editora Abril",
            required=True,
        ),
    ),
)

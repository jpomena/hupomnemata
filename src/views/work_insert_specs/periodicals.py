"""Especificações para periódicos (artigos de revista, jornais, coleções, revistas)."""

import flet as ft
from .base import FieldSpec, PUBLICATION, _spec

JOURNAL_ARTICLE_SPEC = _spec(
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
)

NEWSPAPER_ARTICLE_SPEC = _spec(
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
)

PERIODICAL_COLLECTION_SPEC = _spec(
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
)

MAGAZINE_SPEC = _spec(
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
)

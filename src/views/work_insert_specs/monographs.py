"""Especificações para obras monográficas (livros, trabalhos acadêmicos, correspondências)."""

import flet as ft
from .base import FieldSpec, PUBLICATION, _spec

EDITORIAL_MONOGRAPH_SPEC = _spec(
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
)

ACADEMIC_MONOGRAPH_SPEC = _spec(
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
)

CORRESPONDENCE_MONOGRAPH_SPEC = _spec(
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
)

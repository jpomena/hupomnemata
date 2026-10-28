"""Especificações para documentos legais e patentes."""

import flet as ft
from .base import FieldSpec, _spec

STATUTE_SPEC = _spec(
    "statute",
    "Legislação",
    "Lei, decreto ou norma",
    ft.Icons.GAVEL,
)

CASELAW_SPEC = _spec(
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
)

PATENT_SPEC = _spec(
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
)

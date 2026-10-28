"""Especificações para anais de eventos (volume único e em periódico)."""

import flet as ft
from .base import FieldSpec, PUBLICATION, _spec

MONOGRAPHIC_PROCEEDINGS_SPEC = _spec(
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
)

PERIODICAL_PROCEEDINGS_SPEC = _spec(
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
)

from collections.abc import Callable
from datetime import date, datetime
from enum import Enum
from typing import Any

import flet as ft
from sqlalchemy import inspect

from src.domains import (
    BibliographicResource,
    JournalArticle,
    Magazine,
    PeriodicalCollection,
)
from src.utils import ABNTUtils
from src.utils.types import ViewConfig, WORK_TYPE_LABELS


class WorkDetailsPopup:
    WORK_FIELDS = {
        "title", "subtitle", "abstract", "date_anchor", "display_year",
        "date_precision", "url", "viewed_at",
    }
    RESOURCE_FIELDS = {
        "part_start_page", "part_end_page", "part_volume",
        "part_chapter", "consult_start_year", "consult_end_year",
    }
    HIDDEN_FIELDS = {
        "id", "bib_res_id", "parent_bibliographic_resource_id",
        "created_at", "updated_at", "date_anchor", "date_precision",
    }
    LABELS = {
        "id": "Identificador",
        "bib_res_id": "Identificador bibliográfico",
        "title": "Título",
        "subtitle": "Subtítulo",
        "abstract": "Resumo",
        "display_year": "Ano",
        "date_anchor": "Data de referência",
        "date_precision": "Precisão da data",
        "url": "Endereço eletrônico",
        "viewed_at": "Data de acesso",
        "created_at": "Cadastrado em",
        "updated_at": "Atualizado em",
        "is_partial": "É parte de outra obra",
        "parent_bibliographic_resource_id": "Obra principal",
        "part_start_page": "Página inicial da parte",
        "part_end_page": "Página final da parte",
        "part_volume": "Volume da parte",
        "part_chapter": "Capítulo da parte",
        "consult_start_year": "Ano inicial consultado",
        "consult_end_year": "Ano final consultado",
        "publication_place": "Local de publicação",
        "publisher": "Editora ou produtor",
        "edition": "Edição",
        "page_quantity": "Quantidade de páginas",
        "volumes": "Quantidade de volumes",
        "illustrations": "Possui ilustrações",
        "dimensions": "Dimensões",
        "collection_name": "Nome da coleção",
        "collection_number": "Número na coleção",
        "translation_notes": "Notas de tradução",
        "original_full_title": "Título original completo",
        "additional_notes": "Notas adicionais",
        "responsibilities": "Notas de responsabilidade",
        "part_responsibilities": "Notas de responsabilidade da parte",
        "isbn": "ISBN",
        "issn": "ISSN",
        "journal_title": "Título do periódico",
        "journal_subtitle": "Subtítulo do periódico",
        "volume": "Volume",
        "year_season": "Ano ou estação",
        "number": "Número",
        "start_page": "Página inicial",
        "end_page": "Página final",
        "publication_year": "Ano de publicação",
        "publication_date": "Data de publicação",
        "event_name": "Nome do evento",
        "event_number": "Número do evento",
        "event_year": "Ano do evento",
        "event_place": "Local do evento",
        "thesis_type": "Tipo de trabalho",
        "education_level": "Nível de formação",
        "course": "Curso",
        "faculty": "Faculdade ou instituição",
        "defense_year": "Ano de defesa",
        "carrier_type": "Tipo de suporte",
        "seconds": "Duração em segundos",
        "physical_details": "Detalhes físicos",
        "sound": "Possui som",
        "colorized": "Colorizado",
        "part_identifier": "Identificador da parte",
        "recipient": "Destinatário",
        "applicant": "Requerente",
        "representative": "Representante",
        "filing_date": "Data de depósito",
        "grant_date": "Data de concessão",
        "instrumentation": "Instrumentação",
        "responsiblity_type": "Tipo de responsabilidade",
        "manufacturing_place": "Local",
        "manufacturer": "Produtor ou fabricante",
        "physical_description": "Descrição física",
    }

    def __init__(
        self,
        resource: BibliographicResource,
        config: ViewConfig,
        on_close: Callable[[], None],
    ) -> None:
        self.resource = resource
        self.config = config
        self.on_close = on_close

    def compose(self) -> ft.AlertDialog:
        work = self.resource.specific_work
        if work is None:
            raise ValueError(
                "A obra cadastrada não possui detalhes disponíveis."
            )

        detail_controls = []
        overview_controls = [
            self._detail_row(
                "Tipo",
                WORK_TYPE_LABELS.get(
                    type(work).__name__, type(work).__name__
                ),
            ),
            self._detail_row("Autores", self._authors_value()),
        ]
        if type(work).__name__ in {"JournalArticle", "NewspaperArticle"}:
            publication_date = work.date_anchor
            if isinstance(work, JournalArticle):
                publication_date = ABNTUtils.format_abbrev_month_year(
                    publication_date
                )
            overview_controls.append(
                self._detail_row("Data de publicação", publication_date)
            )
        if isinstance(work, (JournalArticle, PeriodicalCollection)):
            parent = work.parent_bibliographic_resource
            magazine = parent.specific_work if parent is not None else None
            magazine_name = (
                magazine.title if magazine is not None else "Não informado"
            )
            overview_controls.append(
                self._detail_row("Revista", magazine_name)
            )
        detail_controls.append(self._section_title("Visão geral"))
        detail_controls.append(
            ft.ResponsiveRow(
                overview_controls,
                spacing=self.config.ui["control_gap"],
                run_spacing=self.config.ui["control_gap"],
            )
        )
        detail_controls.extend(self._section("Dados da obra", work))
        resource_fields = self._visible_fields(
            self.resource, self.RESOURCE_FIELDS
        )
        if resource_fields:
            detail_controls.extend(
                self._section(
                    "Parte da obra", self.resource, self.RESOURCE_FIELDS
                )
            )

        content = ft.Column(
            detail_controls,
            tight=True,
            scroll=ft.ScrollMode.AUTO,
            width=760,
            height=650,
        )
        return ft.AlertDialog(
            modal=False,
            title=ft.Text(
                work.title,
                size=self.config.font_sizes["cormorant_large"],
                weight=self.config.font_weights["cormorant_bold"],
                font_family=self.config.font_families["cormorant"],
                color=self.config.colors['gold']
            ),
            content=ft.Container(
                content=content,
                animate=ft.Animation(180, ft.AnimationCurve.EASE_OUT),
            ),
            bgcolor=self.config.colors["bg"],
            actions=[
                ft.TextButton(
                    content=ft.Text(
                        "Fechar",
                        font_family=self.config.font_families["montserrat"],
                    ),
                    on_click=lambda e: self.on_close(),
                )
            ],
        )

    def _section(
        self,
        title: str,
        model: object,
        allowed_fields: set[str] | None = None,
    ) -> list[ft.Control]:
        controls: list[ft.Control] = [self._section_title(title)]
        fields = []
        for name, value in self._visible_fields(model, allowed_fields):
            fields.append(
                self._detail_row(
                    name,
                    value,
                    full_width=name in self.FULL_WIDTH_FIELDS,
                )
            )
        controls.append(
            ft.ResponsiveRow(
                controls=fields,
                spacing=self.config.ui["control_gap"],
                run_spacing=self.config.ui["control_gap"],
            )
        )
        return controls

    def _visible_fields(
        self, model: object, allowed_fields: set[str] | None = None
    ) -> list[tuple[str, Any]]:
        fields = []
        inspection = inspect(model)
        if inspection is None:
            return fields
        for column in inspection.mapper.column_attrs:
            if column.key in self.HIDDEN_FIELDS:
                continue
            if isinstance(model, Magazine) and column.key == "display_year":
                continue
            if (
                isinstance(model, (JournalArticle, PeriodicalCollection))
                and column.key in {
                    "journal_title",
                    "publication_place",
                }
            ):
                continue
            if isinstance(model, JournalArticle) and column.key == "publisher":
                continue
            if allowed_fields is not None and column.key not in allowed_fields:
                continue
            value = getattr(model, column.key)
            if value is None or value == "":
                continue
            if (
                value is False
                and column.key not in self.MEANINGFUL_FALSE_FIELDS
            ):
                continue
            fields.append((column.key, value))
        return fields

    MEANINGFUL_FALSE_FIELDS = {
        "is_partial", "illustrations", "published", "sound", "colorized",
    }

    def _authors_value(self) -> str:
        names: list[str] = []
        for author in self.resource.authors:
            if author.corporation:
                legal_name = (
                    author.given_names or author.last_name or ''
                ).strip()
                if not legal_name:
                    continue
                if author.jurisdiction:
                    jurisdiction_name = (
                        author.jurisdiction.given_names
                        or author.jurisdiction.last_name
                        or ''
                    ).strip()
                    if jurisdiction_name and jurisdiction_name != legal_name:
                        legal_name = f"{jurisdiction_name}. {legal_name}"
                names.append(legal_name)
                continue
            names.append(f"{author.given_names} {author.last_name}".strip())
        return "; ".join(names) or "Não informado"

    def _section_title(self, title: str) -> ft.Control:
        return ft.Text(
            title,
            size=self.config.font_sizes["montserrat_medium"],
            weight=self.config.font_weights["montserrat_semibold"],
            color=self.config.colors["gold"],
            font_family=self.config.font_families["montserrat"],
        )

    def _detail_row(
        self, label: str, value: object, full_width: bool = False
    ) -> ft.Control:
        text_value = self._format_value(value)
        value_control: ft.Control

        if label == "url" and isinstance(value, str) and value:
            value_control = ft.Text(
                value="",
                size=self.config.font_sizes["montserrat_small"],
                color=self.config.colors["gold"],
                font_family=self.config.font_families["montserrat"],
                selectable=True,
                spans=[
                    ft.TextSpan(
                        text=text_value,
                        url=value,
                        style=ft.TextStyle(
                            color=self.config.colors["gold"],
                            decoration=ft.TextDecoration.UNDERLINE,
                        ),
                    )
                ],
            )
        else:
            value_control = ft.Text(
                text_value,
                size=self.config.font_sizes["montserrat_small"],
                color=self.config.colors["text"],
                font_family=self.config.font_families["montserrat"],
                selectable=True,
            )

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        self._label(label),
                        size=self.config.font_sizes["montserrat_tiny"],
                        weight=self.config.font_weights["montserrat_semibold"],
                        color=self.config.colors["muted"],
                        font_family=self.config.font_families["montserrat"],
                        text_align=ft.TextAlign.JUSTIFY,
                    ),
                    value_control,
                ],
                spacing=4,
            ),
            col={"xs": 12, "md": 12 if full_width else 6},
            padding=self.config.ui["card_padding"],
            bgcolor=self.config.colors["surface"],
            border=ft.Border.all(1, self.config.colors["border"]),
            border_radius=self.config.ui["card_radius"],
        )

    @property
    def FULL_WIDTH_FIELDS(self) -> set[str]:
        return {
            "abstract",
            "subtitle",
            "url",
            "original_full_title",
            "translation_notes",
        }

    def _label(self, name: str) -> str:
        work = self.resource.specific_work
        if isinstance(work, Magazine) and name == "title":
            return "Nome da revista"
        return WorkDetailsPopup.LABELS.get(
            name, name.replace("_", " ").capitalize()
        )

    @staticmethod
    def _format_value(value: object) -> str:
        if value is None:
            return "Não informado"
        if isinstance(value, bool):
            return "Sim" if value else "Não"
        if isinstance(value, Enum):
            return str(value.value)
        if isinstance(value, (date, datetime)):
            return value.strftime("%d/%m/%Y")
        if isinstance(value, dict):
            return "; ".join(f"{key}: {item}" for key, item in value.items())
        return str(value)

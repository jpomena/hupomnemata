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
        page: ft.Page | None = None,
        nous_service: object | None = None,
    ) -> None:
        self.resource = resource
        self.config = config
        self.on_close = on_close
        self.page = page
        self.nous_service = nous_service
        self._is_generating = False
        self.synthesis_container = None

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
        detail_controls.append(self._compose_synthesis_section())
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

    def _compose_synthesis_section(self) -> ft.Control:
        self.synthesis_container = ft.Container(
            content=self._build_synthesis_body(),
            bgcolor=self.config.colors["surface"],
            border=ft.Border.all(
                1,
                self.config.colors["gold"]
                if (
                    self.resource.llm_description
                    or self.resource.custom_description
                )
                else self.config.colors["border"],
            ),
            border_radius=self.config.ui["card_radius"],
            padding=self.config.ui["card_padding"],
        )
        return ft.Column(
            controls=[
                self._section_title("Síntese Epistemológica (Nous)"),
                self.synthesis_container,
            ],
            spacing=8,
        )

    def _build_synthesis_body(self) -> ft.Control:
        has_custom = bool(
            self.resource.custom_description
            and self.resource.custom_description.strip()
        )
        has_llm = bool(
            self.resource.llm_description
            and self.resource.llm_description.strip()
        )

        if has_custom:
            badge_text = "Personalizada pelo Usuário"
            badge_icon = ft.Icons.EDIT_NOTE
            badge_color = "#5A6B7C"
        elif has_llm:
            badge_text = "Síntese IA (Gemini)"
            badge_icon = ft.Icons.AUTO_AWESOME
            badge_color = self.config.colors["gold"]
        else:
            badge_text = "Pendente de Síntese"
            badge_icon = ft.Icons.HELP_OUTLINE
            badge_color = self.config.colors["muted"]

        effective_text = self.resource.effective_description
        has_any_text = bool(effective_text and effective_text.strip())

        text_widget = ft.Text(
            effective_text
            if has_any_text
            else "Nenhuma síntese epistemológica formulada ainda. Use o Nous para extrair os núcleos conceituais da obra.",
            size=self.config.font_sizes["montserrat_small"],
            color=(
                self.config.colors["text"]
                if has_any_text
                else self.config.colors["muted"]
            ),
            font_family=self.config.font_families["montserrat"],
            italic=not has_any_text,
            selectable=True,
        )

        badge_control = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(badge_icon, size=13, color=badge_color),
                    ft.Text(
                        badge_text,
                        size=self.config.font_sizes["montserrat_tiny"],
                        weight=self.config.font_weights["montserrat_semibold"],
                        color=badge_color,
                        font_family=self.config.font_families["montserrat"],
                    ),
                ],
                spacing=5,
                tight=True,
            ),
            padding=ft.Padding(8, 3, 8, 3),
            border_radius=6,
            bgcolor=self.config.colors["surface"],
            border=ft.Border.all(1, badge_color),
        )

        buttons = []
        if self.nous_service is not None:
            if self._is_generating:
                buttons.append(
                    ft.Container(
                        bgcolor=self.config.colors["surface"],
                        border=ft.Border.all(1, self.config.colors["border"]),
                        border_radius=6,
                        padding=ft.Padding(12, 8, 12, 8),
                        content=ft.Row(
                            controls=[
                                ft.ProgressRing(
                                    width=16,
                                    height=16,
                                    stroke_width=2.5,
                                    color=self.config.colors["gold"],
                                ),
                                ft.Text(
                                    "Nous está processando os conceitos com IA...",
                                    size=self.config.font_sizes["montserrat_small"],
                                    weight=self.config.font_weights["montserrat_semibold"],
                                    color=self.config.colors["text"],
                                    font_family=self.config.font_families["montserrat"],
                                ),
                            ],
                            spacing=10,
                            tight=True,
                        ),
                    )
                )
            else:
                generate_label = "Regenerar com IA" if has_llm else "Gerar com Nous"
                buttons.append(
                    ft.FilledButton(
                        content=ft.Row(
                            controls=[
                                ft.Icon(
                                    ft.Icons.AUTO_AWESOME,
                                    size=14,
                                    color=self.config.colors["surface"],
                                ),
                                ft.Text(
                                    generate_label,
                                    size=self.config.font_sizes["montserrat_tiny"],
                                    weight=self.config.font_weights["montserrat_semibold"],
                                    color=self.config.colors["surface"],
                                    font_family=self.config.font_families["montserrat"],
                                ),
                            ],
                            spacing=6,
                            tight=True,
                        ),
                        style=ft.ButtonStyle(
                            bgcolor=self.config.colors["gold"],
                            shape=ft.RoundedRectangleBorder(radius=6),
                            padding=ft.Padding(12, 6, 12, 6),
                        ),
                        on_click=self._handle_generate_click,
                    )
                )

                buttons.append(
                    ft.OutlinedButton(
                        content=ft.Row(
                            controls=[
                                ft.Icon(
                                    ft.Icons.EDIT,
                                    size=13,
                                    color=self.config.colors["gold"],
                                ),
                                ft.Text(
                                    "Sobrepor / Editar",
                                    size=self.config.font_sizes["montserrat_tiny"],
                                    color=self.config.colors["gold"],
                                    font_family=self.config.font_families["montserrat"],
                                ),
                            ],
                            spacing=6,
                            tight=True,
                        ),
                        style=ft.ButtonStyle(
                            side=ft.BorderSide(1, self.config.colors["gold"]),
                            shape=ft.RoundedRectangleBorder(radius=6),
                            padding=ft.Padding(12, 6, 12, 6),
                        ),
                        on_click=self._handle_edit_click,
                    )
                )

        return ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Row(
                            controls=[
                                ft.Icon(
                                    ft.Icons.PSYCHOLOGY,
                                    size=18,
                                    color=self.config.colors["gold"],
                                ),
                                ft.Text(
                                    "Síntese Conceitual",
                                    size=self.config.font_sizes["montserrat_small"],
                                    weight=self.config.font_weights["montserrat_semibold"],
                                    color=self.config.colors["gold"],
                                    font_family=self.config.font_families["montserrat"],
                                ),
                            ],
                            spacing=6,
                            tight=True,
                        ),
                        badge_control,
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                text_widget,
                ft.Row(controls=buttons, spacing=8) if buttons else ft.Container(),
            ],
            spacing=10,
        )

    def _handle_generate_click(self, e) -> None:
        if self.nous_service is None or self._is_generating:
            return
        self._is_generating = True
        if self.synthesis_container is not None:
            self.synthesis_container.content = self._build_synthesis_body()
        if self.page:
            self.page.update()

        ok, msg = self.nous_service.generate_work_description(self.resource.id)
        self._is_generating = False

        if ok:
            self.resource.llm_description = msg
            if self.page:
                self.page.show_dialog(
                    ft.SnackBar(
                        content=ft.Text(
                            "Síntese epistemológica gerada e salva com sucesso!",
                            color=self.config.colors["surface"],
                        ),
                        bgcolor=self.config.colors["gold"],
                    )
                )
        else:
            if self.page:
                self.page.show_dialog(
                    ft.SnackBar(
                        content=ft.Text(f"Erro ao gerar síntese: {msg}"),
                        bgcolor="#B00020",
                    )
                )

        if self.synthesis_container is not None:
            self.synthesis_container.content = self._build_synthesis_body()
            self.synthesis_container.border = ft.Border.all(
                1,
                self.config.colors["gold"]
                if (
                    self.resource.llm_description
                    or self.resource.custom_description
                )
                else self.config.colors["border"],
            )
        if self.page:
            self.page.update()

    def _handle_edit_click(self, e) -> None:
        if self.nous_service is None or not self.page:
            return

        initial_value = (
            self.resource.custom_description
            or self.resource.llm_description
            or ""
        )
        edit_field = ft.TextField(
            value=initial_value,
            multiline=True,
            min_lines=4,
            max_lines=8,
            border_color=self.config.colors["border"],
            bgcolor=self.config.colors["surface"],
            hint_text="Redija sua síntese ou interpretação particular da obra...",
        )

        def save_edit(_):
            new_text = edit_field.value.strip() if edit_field.value else ""
            self.nous_service.override_work_description(
                self.resource.id, new_text if new_text else None
            )
            self.resource.custom_description = new_text if new_text else None
            edit_modal.open = False
            if self.synthesis_container is not None:
                self.synthesis_container.content = self._build_synthesis_body()
            self.page.update()

        def restore_ai(_):
            self.nous_service.override_work_description(self.resource.id, None)
            self.resource.custom_description = None
            edit_modal.open = False
            if self.synthesis_container is not None:
                self.synthesis_container.content = self._build_synthesis_body()
            self.page.update()

        actions = [
            ft.TextButton(
                content=ft.Text(
                    "Cancelar",
                    color=self.config.colors["text"],
                ),
                on_click=lambda _: setattr(edit_modal, "open", False)
                or self.page.update(),
            ),
        ]
        if self.resource.custom_description and self.resource.llm_description:
            actions.append(
                ft.TextButton(
                    content=ft.Text(
                        "Restaurar Síntese IA",
                        color=self.config.colors["gold"],
                    ),
                    on_click=restore_ai,
                )
            )
        actions.append(
            ft.FilledButton(
                content=ft.Text(
                    "Salvar",
                    color=self.config.colors["surface"],
                ),
                style=ft.ButtonStyle(bgcolor=self.config.colors["gold"]),
                on_click=save_edit,
            )
        )

        edit_modal = ft.AlertDialog(
            title=ft.Text(
                "Personalizar Síntese Epistemológica",
                size=self.config.font_sizes["montserrat_medium"],
                weight=self.config.font_weights["montserrat_semibold"],
                color=self.config.colors["gold"],
                font_family=self.config.font_families["montserrat"],
            ),
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(
                            "Sua síntese manual terá precedência sobre a gerada por IA na malha de conhecimento.",
                            size=self.config.font_sizes["montserrat_tiny"],
                            italic=True,
                            color=self.config.colors["muted"],
                            font_family=self.config.font_families["montserrat"],
                        ),
                        edit_field,
                    ],
                    tight=True,
                    spacing=10,
                ),
                width=550,
            ),
            actions=actions,
            bgcolor=self.config.colors["bg"],
        )
        self.page.show_dialog(edit_modal)

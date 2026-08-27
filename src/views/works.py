import flet as ft

from src.domains import BibliographicResource
from src.strategies import MonographFormatter, PeriodicalFormatter
from src.utils.types import ViewConfig, WORK_TYPE_LABELS
from collections.abc import Callable


class WorksComposer:
    def __init__(
            self,
            scale: float,
            config: ViewConfig,
            works: list[BibliographicResource],
            on_navigate,
            on_work_click: Callable[[BibliographicResource], None],
    ) -> None:
        self.scale = scale
        self.config = config
        self.works = works
        self.on_navigate = on_navigate
        self.on_work_click = on_work_click
        self.board: ft.Column | None = None

    def _compose_header(self) -> ft.Container:

        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Column(
                        controls=[
                            ft.Text(
                                value="Obras & Livros",
                                weight=self.config.font_weights[
                                    "cormorant_semibold"
                                ],
                                color=self.config.colors["text"],
                                font_family=self.config.font_families[
                                    "cormorant"
                                ],
                                size=self.config.font_sizes["cormorant_big"],
                            ),
                            ft.Text(
                                value=(
                                    "Aqui estão todas as obras "
                                    "que você já cadastrou"
                                ),
                                weight=self.config.font_weights[
                                    "montserrat_semibold"
                                ],
                                color=self.config.colors["muted"],
                                font_family=self.config.font_families[
                                    "montserrat"
                                ],
                                size=self.config.font_sizes["montserrat_tiny"],
                            ),
                        ],
                        spacing=2,
                        alignment=ft.MainAxisAlignment.CENTER,
                    ),
                    ft.FilledButton(
                        content=ft.Text(
                            "+ Adicionar nova obra",
                            font_family=(
                                self.config.font_families['montserrat']
                            ),
                            weight=(
                                self.config.font_weights['montserrat_semibold']
                            ),
                            size=self.config.font_sizes['montserrat_small'],
                            color=self.config.colors['text']
                        ),
                        align=ft.Alignment.CENTER_RIGHT,
                        on_click=lambda e: self.on_navigate("work_insert"),
                        bgcolor=self.config.colors['gold']
                    )
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding.only(
                left=self.config.ui["header_horizontal_padding"],
                right=self.config.ui["header_horizontal_padding"],
                top=self.config.ui["header_top_padding"],
                bottom=self.config.ui["header_bottom_padding"],
            ),
        )

    def _compose_board(self) -> ft.Column:
        type_options = {"Todos os tipos"}
        for resource in self.works:
            if resource.specific_work is not None:
                type_options.add(
                    WORK_TYPE_LABELS.get(
                        type(resource.specific_work).__name__,
                        type(resource.specific_work).__name__,
                    )
                )
        selected_type = "Todos os tipos"
        type_filter = ft.Dropdown(
            value=selected_type,
            options=[
                ft.dropdown.Option(value) for value in sorted(type_options)
            ],
            on_select=lambda e: self._filter_board(
                e.control.value or "Todos os tipos"
            ),
            width=260,
        )
        self.board = ft.Column(
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            spacing=self.config.ui["grid_gap"],
        )
        self._filter_board(selected_type, refresh=False)
        return ft.Column(
            controls=[type_filter, self.board],
            spacing=self.config.ui["modal_gap"],
            expand=True,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )

    def _filter_board(self, selected_type: str, refresh: bool = True) -> None:
        if self.board is None:
            return
        cards = []
        for resource in self.works:
            work = resource.specific_work
            if work is None:
                continue
            if selected_type != "Todos os tipos":
                current_type = type(work).__name__
                if selected_type not in {
                    current_type,
                    WORK_TYPE_LABELS.get(current_type, current_type),
                }:
                    continue
            authors = "; ".join(
                f"{author.given_names} {author.last_name}"
                for author in resource.authors
            )
            reference = self._format_reference(resource)
            cards.append(
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Text(
                                value=work.title,
                                size=self.config.font_sizes[
                                    "cormorant_medium"
                                ],
                                font_family=self.config.font_families[
                                    "cormorant"
                                ],
                                weight=self.config.font_weights[
                                    "cormorant_semibold"
                                ],
                            ),
                            ft.Text(
                                value=authors or "Autor não informado",
                                size=self.config.font_sizes[
                                    "montserrat_small"
                                ],
                                font_family=self.config.font_families[
                                    "montserrat"
                                ],
                                color=self.config.colors["muted"],
                            ),
                            ft.Text(
                                value=reference,
                                size=self.config.font_sizes[
                                    "montserrat_tiny"
                                ],
                                font_family=self.config.font_families[
                                    "montserrat"
                                ],
                                color=self.config.colors["text"],
                                max_lines=3,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                            ft.Text(
                                value=(
                                    f"{work.display_year} · "
                                    f"{WORK_TYPE_LABELS.get(
                                        type(work).__name__,
                                        type(work).__name__,
                                    )}"
                                ),
                                size=self.config.font_sizes[
                                    "montserrat_tiny"
                                ],
                                font_family=self.config.font_families[
                                    "montserrat"
                                ],
                                color=self.config.colors["muted"],
                            ),
                        ],
                        spacing=4,
                        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                    ),
                    padding=self.config.ui["card_padding"],
                    bgcolor=self.config.colors["surface"],
                    border=ft.Border.all(1, self.config.colors["border"]),
                    border_radius=self.config.ui["card_radius"],
                    expand=True,
                    on_click=lambda e, resource=resource: (
                        self.on_work_click(resource)
                    ),
                )
            )
        self.board.controls = cards or [
            ft.Text(
                value="Nenhuma obra encontrada.",
                color=self.config.colors["muted"],
            )
        ]
        if refresh:
            self.board.update()

    @staticmethod
    def _reference_text(reference) -> str:
        return "".join(part.content for part in reference.parts).strip()

    def _format_reference(self, resource: BibliographicResource) -> str:
        work_name = type(resource.specific_work).__name__
        monograph_types = {
            "EditorialMonograph",
            "AcademicMonograph",
            "CorrespondenceMonograph",
        }
        periodical_types = {
            "PeriodicalCollection",
            "JournalArticle",
            "NewspaperArticle",
        }
        if work_name in monograph_types:
            return self._reference_text(MonographFormatter.formatter(resource))
        if work_name in periodical_types:
            return self._reference_text(
                PeriodicalFormatter.formatter(resource)
            )
        return "Detalhes disponíveis no popup"

    def compose(self) -> ft.Container:
        """Monta a area de conteudo que ocupa o lado principal."""
        return ft.Container(
            expand=True,
            padding=ft.Padding(
                top=self.config.ui["content_top_padding"],
                right=0,
                bottom=0,
                left=0,
            ),
            bgcolor=self.config.colors["surface"],
            content=ft.Column(
                controls=[
                    self._compose_header(),
                    ft.Container(
                        content=self._compose_board(),
                        border=ft.Border(
                            top=ft.BorderSide(1, self.config.colors["border"])
                        ),
                        padding=self.config.ui["content_padding"],
                        expand=True,
                        alignment=ft.Alignment.TOP_LEFT,
                        bgcolor=self.config.colors["bg"],
                    ),
                ],
                spacing=self.config.ui["modal_gap"],
                expand=True,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
        )

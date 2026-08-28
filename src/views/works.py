import flet as ft

from src.domains import BibliographicResource
from src.strategies import MonographFormatter, PeriodicalFormatter
from src.utils.types import (
    TextStyle,
    ViewConfig,
    ViewReference,
    WORK_TYPE_LABELS,
)
from collections.abc import Awaitable, Callable


class WorksComposer:
    def __init__(
            self,
            scale: float,
            config: ViewConfig,
            works: list[BibliographicResource],
            on_navigate,
            on_work_click: Callable[[BibliographicResource], None],
            on_copy_reference: Callable[[ViewReference], Awaitable[None]],
            on_delete_work: Callable[[BibliographicResource], None],
    ) -> None:
        self.scale = scale
        self.config = config
        self.works = works
        self.on_navigate = on_navigate
        self.on_work_click = on_work_click
        self.on_copy_reference = on_copy_reference
        self.on_delete_work = on_delete_work
        self.board: ft.Column | None = None

    def _compose_header(self) -> ft.Container:

        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Column(
                        controls=[
                            ft.Text(
                                value="Acervo",
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
                            "+ Inserir nova obra",
                            font_family=(
                                self.config.font_families['montserrat']
                            ),
                            weight=(
                                self.config.font_weights['montserrat_semibold']
                            ),
                            size=self.config.font_sizes['montserrat_small'],
                            color=self.config.colors['black']
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
                ft.dropdown.Option(
                    key=value,
                    text=value,
                    content=ft.Text(
                        value=value,
                        weight=self.config.font_weights[
                            "montserrat_normal"
                        ],
                        style=ft.TextStyle(letter_spacing=2),
                        font_family=self.config.font_families[
                            "montserrat"
                        ],
                        size=self.config.font_sizes["montserrat_tiny"],
                        color=self.config.colors['text']
                    )
                )
                for value in [
                    selected_type,
                    *sorted(type_options - {selected_type}),
                ]
            ],
            on_select=lambda e: self._filter_board(
                e.control.value or "Todos os tipos"
            ),
            width=260,
            filled=True,
            fill_color=self.config.colors["surface"],
            bgcolor=self.config.colors['surface'],
            hint_style=ft.TextStyle(
                color=self.config.colors["text"],
                weight=self.config.font_weights["montserrat_normal"],
                font_family=self.config.font_families["montserrat"],
                letter_spacing=2,
                size=12
            ),
            label_style=ft.TextStyle(
                color=self.config.colors["text"],
                weight=self.config.font_weights["montserrat_normal"],
                font_family=self.config.font_families["montserrat"],
                letter_spacing=2,
                size=12
            ),
            text_style=ft.TextStyle(
                color=self.config.colors["text"],
                weight=self.config.font_weights["montserrat_normal"],
                font_family=self.config.font_families["montserrat"],
                letter_spacing=2,
                size=12
            ),
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

            async def copy_reference(event, value=reference):
                await self.on_copy_reference(value)

            cards.append(
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Column(
                                controls=[
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
                                        color=self.config.colors['gold']
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
                                        spans=self._reference_spans(reference),
                                        size=self.config.font_sizes[
                                            "montserrat_tiny"
                                        ],
                                        font_family=self.config.font_families[
                                            "montserrat"
                                        ],
                                        color=self.config.colors["text"],
                                        max_lines=3,
                                        overflow=ft.TextOverflow.ELLIPSIS,
                                        text_align=ft.TextAlign.LEFT,
                                    ),
                                ],
                                spacing=4,
                                horizontal_alignment=(
                                    ft.CrossAxisAlignment.STRETCH
                                ),
                                expand=True,
                            ),
                            ft.Column(
                                controls=[
                                    ft.IconButton(
                                        icon=ft.Icons.COPY,
                                        tooltip="Copiar referência",
                                        on_click=copy_reference,
                                        icon_size=20,
                                        icon_color=self.config.colors['text']
                                    ),
                                    ft.IconButton(
                                        icon=ft.Icons.DELETE_OUTLINE,
                                        icon_color=ft.Colors.RED_400,
                                        tooltip="Excluir obra",
                                        on_click=lambda e, resource=resource: (
                                            self.on_delete_work(resource)
                                        ),
                                        icon_size=24
                                    ),
                                ],
                                spacing=0,
                                horizontal_alignment=(
                                    ft.CrossAxisAlignment.CENTER
                                ),
                            ),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
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

    def _reference_spans(
        self, reference: ViewReference
    ) -> list[ft.TextSpan]:
        return [
            ft.TextSpan(
                text=part.content,
                style=ft.TextStyle(
                    weight=(
                        self.config.font_weights["cormorant_semibold"]
                        if part.style == TextStyle.BOLD
                        else self.config.font_weights["cormorant_normal"]
                    ),
                    italic=part.style == TextStyle.ITALIC,
                ),
            )
            for part in reference.parts
        ]

    def _format_reference(
        self, resource: BibliographicResource
    ) -> ViewReference:
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
            return MonographFormatter.formatter(resource)
        if work_name in periodical_types:
            return PeriodicalFormatter.formatter(resource)
        return ViewReference(parts=[])

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

"""Orquestrador principal da janela modal do Hub de Compilações."""

from collections.abc import Awaitable, Callable
import flet as ft

from src.contracts import (
    CompilationPayload,
    CompilationRecord,
    FragmentRecord,
)
from src.utils.types import ViewConfig
from src.utils.view_styles import button_text_style, text_field_style
from .common import EventControl, _control_list
from .notes_mixin import CompilationHubNotesMixin
from .overview_mixin import CompilationHubOverviewMixin
from .works_mixin import CompilationHubWorksMixin
from .caderno_mixin import CompilationHubCadernoMixin


class CompilationHubComposer(
    CompilationHubOverviewMixin,
    CompilationHubWorksMixin,
    CompilationHubCadernoMixin,
    CompilationHubNotesMixin,
):
    """
    Compositor visual do menu Compilações integrando visões e mixins
    especializados.
    """

    def __init__(
        self,
        page: ft.Page,
        config: ViewConfig,
        compilation: CompilationRecord,
        refresh_compilations: Callable[[], list[CompilationRecord]],
        search_works: Callable[[str], list[tuple[int, str]]],
        on_update: Callable[[int, CompilationPayload], bool],
        on_add_work: Callable[[int, int], bool],
        on_remove_work: Callable[[int, int], bool],
        on_reorder_works: Callable[[int, list[int]], bool],
        on_fragment_membership: Callable[[int, int, bool], bool],
        on_fragment_note: Callable[[int, int, str | None], bool],
        on_create_section: Callable[
            [int, str, str | None], int | None
        ],
        on_update_section: Callable[[int, int, str, str | None], bool],
        on_delete_section: Callable[[int, int], bool],
        on_reorder_sections: Callable[[int, list[int]], bool],
        on_assign_fragment_to_section: Callable[
            [int, int, int | None], bool
        ],
        on_reorder_section_fragments: Callable[
            [int, int, list[int]], bool
        ],
        on_copy_caderno: Callable[[str], Awaitable[None]],
        on_create_work: Callable[[int], None],
        on_edit_work: Callable[[int, int], None],
        on_create_fragment: Callable[[int, int], None],
        on_edit_fragment: Callable[[int, FragmentRecord], None],
        on_close: Callable[[], None],
        on_data_changed: Callable[[CompilationRecord], None],
    ) -> None:
        self.page = page
        self.config = config
        self.compilation = compilation
        self.refresh_compilations = refresh_compilations
        self.search_works = search_works
        self.on_update = on_update
        self.on_add_work = on_add_work
        self.on_remove_work = on_remove_work
        self.on_reorder_works = on_reorder_works
        self.on_fragment_membership = on_fragment_membership
        self.on_fragment_note = on_fragment_note
        self.on_create_section = on_create_section
        self.on_update_section = on_update_section
        self.on_delete_section = on_delete_section
        self.on_reorder_sections = on_reorder_sections
        self.on_assign_fragment_to_section = on_assign_fragment_to_section
        self.on_reorder_section_fragments = on_reorder_section_fragments
        self.on_copy_caderno = on_copy_caderno
        self.on_create_work = on_create_work
        self.on_edit_work = on_edit_work
        self.on_create_fragment = on_create_fragment
        self.on_edit_fragment = on_edit_fragment
        self.on_close = on_close
        self.on_data_changed = on_data_changed
        self.selected_tab = 1
        self.editing_outline = False
        self.expanded_note_fragment_ids: set[int] = set()
        self.new_section_title = ft.TextField(
            label='Nome da seção/ideia *',
            hint_text='Ex.: Argumento central',
            filled=True,
            fill_color=config.colors['surface'],
            expand=True,
            max_length=150,
            **text_field_style(config),
        )
        self.new_section_idea = ft.TextField(
            label='Ideia central (opcional)',
            hint_text='Que papel esta seção terá no texto?',
            filled=True,
            fill_color=config.colors['surface'],
            expand=True,
            max_length=2000,
            **text_field_style(config),
        )
        self.work_search = ft.TextField(
            label='Adicionar obra existente',
            hint_text='Busque pelo título no Acervo',
            filled=True,
            fill_color=config.colors['surface'],
            expand=True,
            on_change=self._search_work_matches,
            **text_field_style(config),
        )
        self.work_matches = ft.Column(
            spacing=2,
            tight=True,
            visible=False,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )
        self.name_field = ft.TextField(
            label='Nome da compilação *',
            value=compilation['name'],
            filled=True,
            fill_color=config.colors['surface'],
            expand=True,
            **text_field_style(config),
        )
        self.description_field = ft.TextField(
            label='Descrição (opcional)',
            value=compilation['description'] or '',
            multiline=True,
            min_lines=3,
            max_lines=6,
            filled=True,
            fill_color=config.colors['surface'],
            expand=True,
            **text_field_style(config),
        )
        dialog_actions: list[ft.Control] = [
            ft.TextButton(
                content=ft.Text(
                    'Fechar',
                    color=config.colors['text'],
                    font_family=config.font_families['montserrat'],
                    size=config.font_sizes['montserrat_medium'],
                    weight=config.font_weights['montserrat_normal'],
                ),
                style=ft.ButtonStyle(
                    text_style=button_text_style(config),
                ),
                on_click=self._close,
            )
        ]
        self.dialog = ft.AlertDialog(
            modal=True,
            bgcolor=config.colors['surface'],
            content=self._compose_content(),
            actions=dialog_actions,
            actions_alignment=ft.MainAxisAlignment.END,
            shape=ft.RoundedRectangleBorder(
                radius=config.ui['card_radius']
            ),
            content_padding=config.ui['modal_content_padding'],
            on_dismiss=self.on_close,
        )

    def _close(self) -> None:
        self.dialog.open = False
        self.on_close()
        self.page.update()

    def _run_click_action(
        self,
        event: ft.Event[EventControl],
        action: Callable[[], object],
    ) -> None:
        del event
        action()

    def open(self) -> None:
        self.page.show_dialog(self.dialog)

    def refresh(self) -> None:
        for item in self.refresh_compilations():
            if item['id'] == self.compilation['id']:
                self.compilation = item
                break
        self.name_field.value = self.compilation['name']
        self.description_field.value = self.compilation['description'] or ''
        self.work_search.value = ''
        self.work_matches.controls = []
        self.work_matches.visible = False
        self.new_section_title.value = ''
        self.new_section_idea.value = ''
        self.dialog.content = self._compose_content()
        self.on_data_changed(self.compilation)
        self.page.update()

    def _compose_content(self) -> ft.Container:
        tab_bar = ft.TabBar(
            tabs=[
                ft.Tab(label='Visão geral'),
                ft.Tab(label='Obras e fragmentos'),
                ft.Tab(label='Caderno de trabalho'),
            ],
            label_text_style=ft.TextStyle(
                font_family=self.config.font_families['cormorant'],
                size=self.config.font_sizes['cormorant_small'],
                weight=self.config.font_weights['cormorant_semibold'],
            ),
            unselected_label_text_style=ft.TextStyle(
                font_family=self.config.font_families['cormorant'],
                size=self.config.font_sizes['cormorant_small'],
                weight=self.config.font_weights['cormorant_semibold'],
            ),
            label_color=self.config.colors['gold'],
            unselected_label_color=self.config.colors['muted'],
            indicator_color=self.config.colors['gold'],
            divider_color=self.config.colors['border'],
        )
        tab_views = ft.TabBarView(
            expand=True,
            controls=[
                ft.Container(
                    content=self._compose_overview(),
                    padding=ft.Padding.only(top=12),
                    expand=True,
                ),
                ft.Container(
                    content=self._compose_works_and_fragments(),
                    padding=ft.Padding.only(top=12),
                    expand=True,
                ),
                ft.Container(
                    content=self._compose_caderno(),
                    padding=ft.Padding.only(top=12),
                    expand=True,
                ),
            ],
        )
        tabs = ft.Tabs(
            length=3,
            selected_index=self.selected_tab,
            on_change=lambda event: setattr(
                self,
                'selected_tab',
                event.control.selected_index,
            ),
            content=ft.Column(
                controls=[tab_bar, tab_views],
                expand=True,
                spacing=0,
            ),
            expand=True,
        )
        return ft.Container(
            content=ft.Column(
                controls=_control_list(
                    ft.Row(
                        controls=_control_list(
                            ft.Column(
                                controls=[
                                    ft.Text(
                                        value=self.compilation['name'],
                                        size=self.config.font_sizes[
                                            'cormorant_large'
                                        ],
                                        font_family=(
                                            self.config.font_families[
                                                'cormorant'
                                            ]
                                        ),
                                        weight=(
                                            self.config.font_weights[
                                                'cormorant_semibold'
                                            ]
                                        ),
                                        color=self.config.colors['gold'],
                                    ),
                                    ft.Text(
                                        value=(
                                            'Hub de obras, fragmentos e '
                                            'relações deste projeto'
                                        ),
                                        color=self.config.colors['muted'],
                                        size=self.config.font_sizes[
                                            'montserrat_large'
                                        ],
                                        font_family=(
                                            self.config.font_families[
                                                'montserrat'
                                            ]
                                        ),
                                    ),
                                ],
                                spacing=2,
                                expand=True,
                            ),
                            ft.IconButton(
                                icon=ft.Icons.CLOSE,
                                tooltip='Fechar hub',
                                icon_color=self.config.colors['text'],
                                on_click=self._close,
                            ),
                        ),
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Divider(
                        color=self.config.colors['border'],
                        height=1,
                    ),
                    tabs,
                ),
                spacing=self.config.ui['modal_gap'],
                expand=True,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
            width=min(self.config.ui['modal_width'], 1200),
            height=min(self.config.ui['modal_height'], 820),
            padding=self.config.ui['card_padding'],
            bgcolor=self.config.colors['surface'],
        )

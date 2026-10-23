from collections.abc import Awaitable, Callable
from typing import TypeVar

import flet as ft

from src.contracts import (
    CompilationPayload,
    CompilationRecord,
    FragmentRecord,
)
from src.utils.types import ViewConfig
from src.utils.view_styles import button_text_style, text_field_style
from src.views.compilation_hub import CompilationHubComposer

EventControl = TypeVar('EventControl', bound=ft.Control)


class CompilationsComposer:
    def __init__(
        self,
        page: ft.Page,
        config: ViewConfig,
        compilations: list[CompilationRecord],
        search_works: Callable[[str], list[tuple[int, str]]],
        refresh_compilations: Callable[[], list[CompilationRecord]],
        on_create: Callable[[CompilationPayload], int | None],
        on_update: Callable[[int, CompilationPayload], bool],
        on_delete: Callable[[int], bool],
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
        on_reorder_section_fragments: Callable[[int, int, list[int]], bool],
        on_copy_caderno: Callable[[str], Awaitable[None]],
        on_create_work: Callable[[int], None],
        on_edit_work: Callable[[int, int], None],
        on_create_fragment: Callable[[int, int], None],
        on_edit_fragment: Callable[[int, FragmentRecord], None],
    ) -> None:
        self.page = page
        self.config = config
        self.compilations = compilations
        self.search_works = search_works
        self.refresh_compilations = refresh_compilations
        self.on_create = on_create
        self.on_update = on_update
        self.on_delete = on_delete
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
        self.creating = False
        self.selected_compilation_id: int | None = None
        self.active_hub: CompilationHubComposer | None = None
        self.root: ft.Container | None = None
        self.card_list: ft.Column | None = None
        self.compilation_search = ft.TextField(
            label='Buscar compilação',
            hint_text='Digite nome ou descrição',
            on_change=self._search_compilations,
            filled=True,
            fill_color=config.colors['surface'],
            expand=True,
            **text_field_style(config),
        )
        self.compilation_matches = ft.Column(
            spacing=2,
            tight=True,
            visible=False,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )
        self.new_name = ft.TextField(
            label='Nome da compilação *',
            hint_text='Ex.: Tese',
            filled=True,
            fill_color=config.colors['surface'],
            expand=True,
            **text_field_style(config),
        )
        self.new_description = ft.TextField(
            label='Descrição (opcional)',
            hint_text='Qual é o tema ou objetivo deste projeto?',
            multiline=True,
            min_lines=2,
            max_lines=4,
            filled=True,
            fill_color=config.colors['surface'],
            expand=True,
            **text_field_style(config),
        )

    def _search_compilations(
        self,
        event: ft.Event[ft.TextField],
    ) -> None:
        query = (event.control.value or '').strip().casefold()
        self.selected_compilation_id = None
        if len(query) < 2:
            self.compilation_matches.controls = []
            self.compilation_matches.visible = False
        else:
            matches = [
                compilation
                for compilation in self.compilations
                if query in compilation['name'].casefold()
                or query in (compilation['description'] or '').casefold()
            ]
            self.compilation_matches.controls = [
                ft.TextButton(
                    content=ft.Column(
                        controls=[
                            ft.Text(
                                value=compilation['name'],
                                color=self.config.colors['text'],
                                font_family=self.config.font_families[
                                    'montserrat'
                                ],
                                size=self.config.font_sizes[
                                    'montserrat_medium'
                                ],
                                weight=self.config.font_weights[
                                    'montserrat_normal'
                                ],
                            ),
                            ft.Text(
                                value=compilation['description'] or '',
                                color=self.config.colors['muted'],
                                font_family=self.config.font_families[
                                    'montserrat'
                                ],
                                size=self.config.font_sizes[
                                    'montserrat_small'
                                ],
                                weight=self.config.font_weights[
                                    'montserrat_normal'
                                ],
                                visible=bool(compilation['description']),
                            ),
                        ],
                        spacing=0,
                        horizontal_alignment=ft.CrossAxisAlignment.START,
                    ),
                    style=ft.ButtonStyle(
                        text_style=button_text_style(self.config),
                    ),
                    on_click=lambda event, current=compilation: (
                        self._run_click_action(
                            event,
                            lambda: self._select_compilation(current),
                        )
                    ),
                )
                for compilation in matches[:8]
            ]
            if not matches:
                self.compilation_matches.controls = [
                    ft.Text(
                        value='Nenhuma compilação encontrada.',
                        color=self.config.colors['muted'],
                    )
                ]
            self.compilation_matches.visible = True
        self._render_cards()
        self.page.update()

    @staticmethod
    def _run_click_action(
        event: ft.Event[EventControl],
        action: Callable[[], object],
    ) -> None:
        del event
        action()

    def _select_compilation(
        self,
        compilation: CompilationRecord,
    ) -> None:
        self.selected_compilation_id = compilation['id']
        self.compilation_search.value = compilation['name']
        self.compilation_matches.controls = []
        self.compilation_matches.visible = False
        self._render_cards()
        self.page.update()

    def _filtered_compilations(self) -> list[CompilationRecord]:
        if self.selected_compilation_id is not None:
            return [
                compilation
                for compilation in self.compilations
                if compilation['id'] == self.selected_compilation_id
            ]
        query = (self.compilation_search.value or '').strip().casefold()
        if not query:
            return self.compilations
        return [
            compilation
            for compilation in self.compilations
            if query in compilation['name'].casefold()
            or query in (compilation['description'] or '').casefold()
        ]

    def _toggle_create(self) -> None:
        self.creating = not self.creating
        self._render_cards()
        self.page.update()

    def _create(self) -> None:
        compilation_id = self.on_create({
            'name': self.new_name.value or '',
            'description': self.new_description.value,
        })
        if compilation_id is None:
            return
        self.creating = False
        self.new_name.value = ''
        self.new_description.value = ''
        self.compilations = self.refresh_compilations()
        self._render_cards()
        self.page.update()
        self._open_hub(compilation_id)

    def _cancel_create(self) -> None:
        self.creating = False
        self.new_name.value = ''
        self.new_description.value = ''
        self._render_cards()
        self.page.update()

    def _delete_compilation(self, compilation_id: int) -> None:
        if not self.on_delete(compilation_id):
            return
        self.compilations = self.refresh_compilations()
        if self.selected_compilation_id == compilation_id:
            self.selected_compilation_id = None
            self.compilation_search.value = ''
        self._render_cards()
        self.page.update()

    def _open_hub(self, compilation_id: int) -> None:
        compilation = next(
            (
                item
                for item in self.compilations
                if item['id'] == compilation_id
            ),
            None,
        )
        if compilation is None:
            return

        hub: CompilationHubComposer

        def close_hub() -> None:
            if self.active_hub is hub:
                self.active_hub = None

        hub = CompilationHubComposer(
            page=self.page,
            config=self.config,
            compilation=compilation,
            refresh_compilations=self.refresh_compilations,
            search_works=self.search_works,
            on_update=self.on_update,
            on_add_work=self.on_add_work,
            on_remove_work=self.on_remove_work,
            on_reorder_works=self.on_reorder_works,
            on_fragment_membership=self.on_fragment_membership,
            on_fragment_note=self.on_fragment_note,
            on_create_section=self.on_create_section,
            on_update_section=self.on_update_section,
            on_delete_section=self.on_delete_section,
            on_reorder_sections=self.on_reorder_sections,
            on_assign_fragment_to_section=self.on_assign_fragment_to_section,
            on_reorder_section_fragments=self.on_reorder_section_fragments,
            on_copy_caderno=self.on_copy_caderno,
            on_create_work=self.on_create_work,
            on_edit_work=self.on_edit_work,
            on_create_fragment=self.on_create_fragment,
            on_edit_fragment=self.on_edit_fragment,
            on_close=close_hub,
            on_data_changed=self._update_compilation,
        )
        self.active_hub = hub
        hub.open()

    def _update_compilation(self, compilation: CompilationRecord) -> None:
        self.compilations = [
            compilation if current['id'] == compilation['id'] else current
            for current in self.compilations
        ]
        self._render_cards()

    def refresh_compilation_hub(self, compilation_id: int) -> None:
        self.compilations = self.refresh_compilations()
        if (
            self.active_hub is not None
            and self.active_hub.compilation['id'] == compilation_id
        ):
            self.active_hub.refresh()
        else:
            self._render_cards()
        self.page.update()

    def _compose_create_card(self) -> ft.Container:
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        value='Nova compilação',
                        size=self.config.font_sizes['cormorant_medium'],
                        font_family=self.config.font_families['cormorant'],
                        weight=self.config.font_weights['cormorant_semibold'],
                        color=self.config.colors['text'],
                    ),
                    self.new_name,
                    self.new_description,
                    ft.Row(
                        controls=[
                            ft.TextButton(
                                content=ft.Text(
                                    'Cancelar',
                                    color=self.config.colors['text'],
                                    font_family=(
                                        self.config.font_families[
                                            'montserrat'
                                        ]
                                    ),
                                    size=self.config.font_sizes[
                                        'montserrat_medium'
                                    ],
                                    weight=self.config.font_weights[
                                        'montserrat_normal'
                                    ],
                                ),
                                style=ft.ButtonStyle(
                                    text_style=button_text_style(self.config),
                                ),
                                on_click=self._cancel_create,
                            ),
                            ft.FilledButton(
                                content=ft.Text(
                                    'Criar compilação',
                                    color=self.config.colors['bg'],
                                    font_family=(
                                        self.config.font_families[
                                            'montserrat'
                                        ]
                                    ),
                                    size=self.config.font_sizes[
                                        'montserrat_medium'
                                    ],
                                    weight=self.config.font_weights[
                                        'montserrat_normal'
                                    ],
                                ),
                                bgcolor=self.config.colors['gold'],
                                style=ft.ButtonStyle(
                                    text_style=button_text_style(self.config),
                                ),
                                on_click=self._create,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.END,
                    ),
                ],
                spacing=self.config.ui['modal_gap'],
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
            padding=self.config.ui['card_padding'],
            bgcolor=self.config.colors['surface'],
            border=ft.Border.all(1, self.config.colors['border']),
            border_radius=self.config.ui['card_radius'],
        )

    def _compose_compilation_card(
        self,
        compilation: CompilationRecord,
    ) -> ft.Container:
        fragments = [
            fragment
            for work in compilation['works']
            for fragment in work['fragments']
        ]
        member_count = sum(fragment['is_member'] for fragment in fragments)
        work_count = len(compilation['works'])
        work_label = 'obra' if work_count == 1 else 'obras'
        title = ft.Text(
            value=compilation['name'],
            size=self.config.font_sizes['cormorant_medium'],
            font_family=self.config.font_families['cormorant'],
            weight=self.config.font_weights['cormorant_semibold'],
            color=self.config.colors['gold'],
        )
        card = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Column(
                        controls=[
                            title,
                            ft.Text(
                                value=(
                                    compilation['description']
                                    or 'Sem descrição'
                                ),
                                size=self.config.font_sizes[
                                    'montserrat_small'
                                ],
                                font_family=self.config.font_families[
                                    'montserrat'
                                ],
                                color=self.config.colors['muted'],
                            ),
                            ft.Text(
                                value=(
                                    f'{work_count} {work_label} '
                                    f'· {member_count} fragmentos'
                                ),
                                size=self.config.font_sizes[
                                    'montserrat_small'
                                ],
                                font_family=self.config.font_families[
                                    'montserrat'
                                ],
                                color=self.config.colors['muted'],
                            ),
                        ],
                        spacing=4,
                        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                        expand=True,
                    ),
                    ft.Icon(
                        ft.Icons.ARROW_FORWARD,
                        color=self.config.colors['gold'],
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=self.config.ui['card_padding'],
            bgcolor=self.config.colors['surface'],
            border=ft.Border.all(1, self.config.colors['border']),
            border_radius=self.config.ui['card_radius'],
            expand=True,
            on_click=lambda event, current_id=compilation['id']: (
                self._run_click_action(
                    event,
                    lambda: self._open_hub(current_id),
                )
            ),
            animate=ft.Animation(180, ft.AnimationCurve.EASE_OUT),
        )

        def handle_hover(event: ft.Event[ft.Container]) -> None:
            card.bgcolor = (
                self.config.colors['card_hover']
                if event.data
                else self.config.colors['surface']
            )
            card.border = (
                ft.Border(
                    left=ft.BorderSide(8, self.config.colors['text']),
                    top=ft.BorderSide(1, self.config.colors['text']),
                    right=ft.BorderSide(1, self.config.colors['text']),
                    bottom=ft.BorderSide(1, self.config.colors['text']),
                )
                if event.data
                else ft.Border.all(1, self.config.colors['border'])
            )
            title.color = (
                self.config.colors['text']
                if event.data
                else self.config.colors['gold']
            )
            card.update()

        card.on_hover = handle_hover
        return ft.Container(
            content=ft.Row(
                controls=[
                    card,
                    ft.IconButton(
                        icon=ft.Icons.DELETE_OUTLINE,
                        tooltip='Excluir compilação',
                        icon_color=ft.Colors.RED_400,
                        on_click=lambda event, current_id=compilation['id']: (
                            self._run_click_action(
                                event,
                                lambda: self._delete_compilation(current_id),
                            )
                        ),
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=self.config.ui['modal_gap'],
            ),
        )

    def _render_cards(self) -> None:
        if self.root is None:
            return
        cards: list[ft.Control] = []
        if self.creating:
            cards.append(self._compose_create_card())
        visible_compilations = self._filtered_compilations()
        cards.extend(
            self._compose_compilation_card(compilation)
            for compilation in visible_compilations
        )
        if not cards:
            message = (
                'Nenhuma compilação corresponde à busca.'
                if self.compilations
                else (
                    'Ainda não há compilações. Crie uma para começar '
                    'a organizar suas obras e fragmentos.'
                )
            )
            cards.append(
                ft.Text(
                    value=message,
                    color=self.config.colors['muted'],
                    size=self.config.font_sizes[
                        'montserrat_small'
                    ],
                    font_family=self.config.font_families['montserrat'],
                )
            )
        if self.card_list is not None:
            self.card_list.controls = cards

    def _compose_header(self) -> ft.Container:
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Column(
                        controls=[
                            ft.Text(
                                value='Compilações',
                                weight=self.config.font_weights[
                                    'cormorant_semibold'
                                ],
                                color=self.config.colors['text'],
                                font_family=self.config.font_families[
                                    'cormorant'
                                ],
                                size=self.config.font_sizes['cormorant_big'],
                            ),
                            ft.Text(
                                value=(
                                    'Hubs de trabalho com obras e fragmentos '
                                    'relacionados'
                                ),
                                weight=self.config.font_weights[
                                    'montserrat_normal'
                                ],
                                color=self.config.colors['muted'],
                                font_family=self.config.font_families[
                                    'montserrat'
                                ],
                                size=self.config.font_sizes[
                                    'montserrat_small'
                                ],
                            ),
                        ],
                        spacing=2,
                    ),
                    ft.FilledButton(
                        content=ft.Text(
                            '+ Nova compilação',
                            font_family=self.config.font_families[
                                'montserrat'
                            ],
                            weight=self.config.font_weights[
                                'montserrat_normal'
                            ],
                            size=self.config.font_sizes['montserrat_medium'],
                            color=self.config.colors['bg'],
                        ),
                        on_click=self._toggle_create,
                        bgcolor=self.config.colors['gold'],
                        style=ft.ButtonStyle(
                            text_style=button_text_style(
                                self.config,
                                size='montserrat_medium',
                                weight='montserrat_normal',
                            ),
                        ),
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding.only(
                left=self.config.ui['header_horizontal_padding'],
                right=self.config.ui['header_horizontal_padding'],
                top=self.config.ui['header_top_padding'],
                bottom=self.config.ui['header_bottom_padding'],
            ),
        )

    def compose(self) -> ft.Container:
        self.card_list = ft.Column(
            spacing=self.config.ui['grid_gap'],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )
        self.root = ft.Container(
            content=ft.Column(
                controls=[
                    self._compose_header(),
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Column(
                                    controls=[
                                        self.compilation_search,
                                        self.compilation_matches,
                                    ],
                                    spacing=2,
                                    tight=True,
                                    horizontal_alignment=(
                                        ft.CrossAxisAlignment.STRETCH
                                    ),
                                ),
                                self.card_list,
                            ],
                            spacing=self.config.ui['modal_gap'],
                            expand=True,
                            horizontal_alignment=(
                                ft.CrossAxisAlignment.STRETCH
                            ),
                        ),
                        border=ft.Border.only(
                            top=ft.BorderSide(
                                1,
                                self.config.colors['border'],
                            )
                        ),
                        padding=self.config.ui['content_padding'],
                        expand=True,
                        alignment=ft.Alignment.TOP_LEFT,
                        bgcolor=self.config.colors['bg'],
                    ),
                ],
                spacing=self.config.ui['modal_gap'],
                expand=True,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
            expand=True,
            padding=ft.Padding.only(
                top=self.config.ui['content_top_padding'],
            ),
            bgcolor=self.config.colors['surface'],
        )
        self._render_cards()
        return self.root

"""Mixin para a aba de Obras e Fragmentos no hub de compilações."""

import flet as ft

from src.contracts import CompilationFragmentRecord, CompilationWorkRecord
from src.utils.view_styles import button_text_style, dropdown_style
from .common import _control_list


class CompilationHubWorksMixin:
    """Responsável pela gestão, busca e listagem de obras e fragmentos da compilação."""

    def _outline_dropdown_option(
        self,
        key: str,
        label: str,
    ) -> ft.DropdownOption:
        return ft.DropdownOption(
            key=key,
            text=label,
            content=ft.Text(
                value=label,
                color=self.config.colors['text'],
                font_family=self.config.font_families['montserrat'],
                size=self.config.font_sizes['montserrat_medium'],
                weight=self.config.font_weights['montserrat_normal'],
            ),
        )

    def _search_work_matches(
        self,
        event: ft.Event[ft.TextField],
    ) -> None:
        query = (event.control.value or '').strip()
        if len(query) < 2:
            self.work_matches.controls = []
            self.work_matches.visible = False
            self.page.update()
            return
        linked_ids = {
            work['id'] for work in self.compilation['works']
        }
        matches = [
            (work_id, title)
            for work_id, title in self.search_works(query)
            if work_id not in linked_ids
        ][:8]
        self.work_matches.controls = [
            ft.TextButton(
                content=ft.Text(
                    value=title,
                    color=self.config.colors['text'],
                    font_family=self.config.font_families[
                        'montserrat'
                    ],
                    size=self.config.font_sizes['montserrat_medium'],
                    weight=self.config.font_weights['montserrat_normal'],
                ),
                style=ft.ButtonStyle(
                    text_style=button_text_style(self.config),
                ),
                on_click=lambda event, resource_id=work_id: (
                    self._run_click_action(
                        event,
                        lambda: self._add_work(resource_id),
                    )
                ),
            )
            for work_id, title in matches
        ]
        if not matches:
            self.work_matches.controls = [
                ft.Text(
                    value='Nenhuma obra disponível para adicionar.',
                    color=self.config.colors['muted'],
                )
            ]
        self.work_matches.visible = True
        self.page.update()

    def _add_work(self, bib_res_id: int) -> None:
        if self.on_add_work(self.compilation['id'], bib_res_id):
            self.refresh()

    def _remove_work(self, bib_res_id: int) -> None:
        if self.on_remove_work(self.compilation['id'], bib_res_id):
            self.refresh()

    def _move_work(self, index: int, offset: int) -> None:
        work_ids = [work['id'] for work in self.compilation['works']]
        target_index = index + offset
        if target_index < 0 or target_index >= len(work_ids):
            return
        work_ids[index], work_ids[target_index] = (
            work_ids[target_index],
            work_ids[index],
        )
        if self.on_reorder_works(self.compilation['id'], work_ids):
            self.refresh()

    def _compose_fragment(
        self,
        fragment: CompilationFragmentRecord,
    ) -> ft.Container:
        location = ', '.join(
            part
            for part in (
                fragment['location_type'],
                fragment['location_value'],
            )
            if part
        )
        fragment_type = (
            'Citação' if fragment['fragment_type'] == 'quote' else 'Comentário'
        )
        is_member = fragment['is_member']
        destination_value = (
            str(fragment['section_id'])
            if fragment['section_id'] is not None
            else 'unassigned'
        ) if is_member else 'not_selected'
        section_options = [
            self._outline_dropdown_option(
                str(section['id']),
                section['title'],
            )
            for section in sorted(
                self.compilation['sections'],
                key=lambda item: (item['position'], item['id']),
            )
        ]
        destination_control = ft.Dropdown(
            label='Destino no caderno',
            value=destination_value,
            options=[
                self._outline_dropdown_option(
                    'not_selected',
                    'Fora do caderno',
                ),
                self._outline_dropdown_option(
                    'unassigned',
                    'A organizar',
                ),
                *section_options,
                self._outline_dropdown_option(
                    'create_section',
                    '+ Criar nova ideia…',
                ),
            ],
            on_select=lambda event, current_id=fragment['id']: (
                self._set_fragment_destination(
                    current_id,
                    event.control.value,
                )
                if event.control.value is not None
                else None
            ),
            expand=True,
            **{
                **dropdown_style(self.config),
                'text_style': ft.TextStyle(
                    color=self.config.colors['text'],
                    font_family=self.config.font_families['montserrat'],
                    size=self.config.font_sizes['montserrat_medium'],
                    weight=self.config.font_weights['montserrat_normal'],
                ),
                'label_style': ft.TextStyle(
                    color=self.config.colors['muted'],
                    font_family=self.config.font_families['montserrat'],
                    size=self.config.font_sizes['montserrat_small'],
                    weight=self.config.font_weights['montserrat_normal'],
                ),
            },
        )
        fragment_details: list[ft.Control] = [
            ft.Text(
                value=fragment_type,
                color=self.config.colors['gold'],
                size=self.config.font_sizes['montserrat_medium'],
                font_family=self.config.font_families['montserrat'],
            ),
            ft.Text(
                value=fragment['excerpt'],
                color=self.config.colors['text'],
                size=self.config.font_sizes['montserrat_medium'],
                font_family=self.config.font_families['montserrat'],
                selectable=True,
            ),
            ft.Text(
                value=location,
                color=self.config.colors['muted'],
                size=self.config.font_sizes['montserrat_medium'],
                font_family=self.config.font_families['montserrat'],
                visible=bool(location),
            ),
            self._compose_fragment_note(fragment),
        ]
        return ft.Container(
            content=ft.Column(
                controls=_control_list(
                    ft.Row(
                        controls=_control_list(
                            ft.Column(
                                controls=fragment_details,
                                spacing=3,
                                expand=True,
                                horizontal_alignment=(
                                    ft.CrossAxisAlignment.STRETCH
                                ),
                            ),
                            ft.IconButton(
                                icon=ft.Icons.EDIT_OUTLINED,
                                tooltip='Editar fragmento',
                                icon_color=self.config.colors['text'],
                                on_click=lambda event, current=fragment: (
                                    self._run_click_action(
                                        event,
                                        lambda: self.on_edit_fragment(
                                            self.compilation['id'],
                                            current,
                                        ),
                                    )
                                ),
                            ),
                        ),
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Container(
                        content=destination_control,
                        width=460,
                        padding=ft.Padding.only(top=4),
                    ),
                ),
                spacing=self.config.ui['control_gap'],
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
            padding=self.config.ui['card_padding'],
            bgcolor=self.config.colors['bg'],
            border=ft.Border.all(1, self.config.colors['border']),
            border_radius=self.config.ui['card_radius'],
        )

    def _compose_work(self, index: int) -> ft.Container:
        work = self.compilation['works'][index]
        fragments = work['fragments']
        fragment_count_label = (
            'fragmento' if len(fragments) == 1 else 'fragmentos'
        )
        resource_id = work['id']
        fragment_sections: list[ft.Control] = []
        if fragments:
            for is_member, title in (
                (True, 'Selecionados para o caderno'),
                (False, 'Materiais disponíveis'),
            ):
                section_fragments = [
                    fragment
                    for fragment in fragments
                    if fragment['is_member'] is is_member
                ]
                if section_fragments:
                    rendered_fragments = [
                        self._compose_fragment(
                            fragment,
                        )
                        for fragment in section_fragments
                    ]
                    fragment_sections.append(
                        ft.Column(
                            controls=[
                                ft.Text(
                                    value=(
                                        title
                                        + f' ({len(section_fragments)})'
                                    ),
                                    color=self.config.colors['muted'],
                                    size=self.config.font_sizes[
                                        'montserrat_medium'
                                    ],
                                    weight=self.config.font_weights[
                                        'montserrat_semibold'
                                    ],
                                    font_family=self.config.font_families[
                                        'montserrat'
                                    ],
                                ),
                                *rendered_fragments,
                            ],
                            spacing=max(
                                2,
                                int(self.config.ui['grid_gap'] / 8),
                            ),
                            horizontal_alignment=(
                                ft.CrossAxisAlignment.STRETCH
                            ),
                        )
                    )
        else:
            fragment_sections.append(
                ft.Text(
                    value='Ainda não há fragmentos para esta obra.',
                    color=self.config.colors['muted'],
                    size=self.config.font_sizes['montserrat_small'],
                    font_family=self.config.font_families['montserrat'],
                )
            )
        return ft.Container(
            content=ft.Column(
                controls=_control_list(
                    ft.Row(
                        controls=_control_list(
                            ft.Column(
                                controls=[
                                    ft.Text(
                                        value=work['title'],
                                        size=self.config.font_sizes[
                                            'cormorant_medium'
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
                                        selectable=True,
                                    ),
                                    ft.Text(
                                        value=(
                                            f'{len(fragments)} '
                                            f'{fragment_count_label}'
                                        ),
                                        color=self.config.colors['muted'],
                                        size=self.config.font_sizes[
                                            'montserrat_small'
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
                                icon=ft.Icons.ARROW_UPWARD,
                                tooltip='Mover obra para cima',
                                disabled=index == 0,
                                on_click=lambda event, current=index: (
                                    self._run_click_action(
                                        event,
                                        lambda: self._move_work(
                                            current,
                                            -1,
                                        ),
                                    )
                                ),
                            ),
                            ft.IconButton(
                                icon=ft.Icons.ARROW_DOWNWARD,
                                tooltip='Mover obra para baixo',
                                disabled=(
                                    index == len(self.compilation['works']) - 1
                                ),
                                on_click=lambda event, current=index: (
                                    self._run_click_action(
                                        event,
                                        lambda: self._move_work(
                                            current,
                                            1,
                                        ),
                                    )
                                ),
                            ),
                            ft.IconButton(
                                icon=ft.Icons.EDIT_OUTLINED,
                                tooltip='Editar obra',
                                icon_color=self.config.colors['text'],
                                on_click=lambda event, work_id=resource_id: (
                                    self._run_click_action(
                                        event,
                                        lambda: self.on_edit_work(
                                            self.compilation['id'],
                                            work_id,
                                        ),
                                    )
                                ),
                            ),
                            ft.IconButton(
                                icon=ft.Icons.ADD_COMMENT_OUTLINED,
                                tooltip='Novo fragmento nesta obra',
                                icon_color=self.config.colors['gold'],
                                on_click=lambda event, work_id=resource_id: (
                                    self._run_click_action(
                                        event,
                                        lambda: self.on_create_fragment(
                                            self.compilation['id'],
                                            work_id,
                                        ),
                                    )
                                ),
                            ),
                            ft.IconButton(
                                icon=ft.Icons.DELETE_OUTLINE,
                                tooltip='Retirar obra e seus vínculos',
                                icon_color=ft.Colors.RED_400,
                                on_click=lambda event, work_id=resource_id: (
                                    self._run_click_action(
                                        event,
                                        lambda: self._remove_work(work_id),
                                    )
                                ),
                            ),
                        ),
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Column(
                        controls=fragment_sections,
                        spacing=max(
                            2,
                            int(self.config.ui['grid_gap'] / 8),
                        ),
                        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                    ),
                ),
                spacing=self.config.ui['modal_gap'],
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
            padding=self.config.ui['card_padding'],
            bgcolor=self.config.colors['surface'],
            border=ft.Border.all(1, self.config.colors['border']),
            border_radius=self.config.ui['card_radius'],
        )

    def _compose_works_and_fragments(self) -> ft.Control:
        search_group = ft.Column(
            controls=[self.work_search, self.work_matches],
            spacing=2,
            tight=True,
            expand=True,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )
        controls: list[ft.Control] = [
            ft.Row(
                controls=[
                    search_group,
                    ft.FilledButton(
                        content=ft.Text(
                            '+ Criar obra',
                            color=self.config.colors['bg'],
                            font_family=(
                                self.config.font_families['montserrat']
                            ),
                            size=self.config.font_sizes['montserrat_medium'],
                            weight=self.config.font_weights[
                                'montserrat_normal'
                            ],
                        ),
                        bgcolor=self.config.colors['gold'],
                        style=ft.ButtonStyle(
                            text_style=button_text_style(self.config),
                        ),
                        on_click=lambda event: self._run_click_action(
                            event,
                            lambda: self.on_create_work(
                                self.compilation['id']
                            ),
                        ),
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.START,
                spacing=self.config.ui['control_gap'],
            )
        ]
        if not self.compilation['works']:
            controls.append(
                ft.Container(
                    content=ft.Text(
                        value=(
                            'Adicione uma obra existente ou crie uma nova '
                            'para começar a reunir fontes neste projeto.'
                        ),
                        color=self.config.colors['muted'],
                        size=self.config.font_sizes['montserrat_small'],
                        font_family=self.config.font_families['montserrat'],
                    ),
                    padding=self.config.ui['card_padding'],
                    bgcolor=self.config.colors['surface'],
                    border_radius=self.config.ui['card_radius'],
                )
            )
        else:
            controls.extend(
                self._compose_work(index)
                for index in range(len(self.compilation['works']))
            )
        return ft.Column(
            controls=controls,
            spacing=self.config.ui['grid_gap'],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )

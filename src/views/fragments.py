from collections.abc import Awaitable, Callable
from typing import TypeVar

import flet as ft

from src.contracts import (
    FRAGMENT_LOCATION_TYPES,
    FRAGMENT_TYPE_LABELS,
    FragmentRecord,
)
from src.utils.types import ReferencePart, ViewConfig, ViewReference
from src.utils.fragment_reference import fragment_abnt_notation
from src.utils.view_styles import (
    button_text_style,
    dropdown_style,
    text_field_style,
)

EventControl = TypeVar('EventControl', bound=ft.Control)


def _control_list(*controls: ft.Control) -> list[ft.Control]:
    return list(controls)


class FragmentsComposer:
    def __init__(
        self,
        page: ft.Page,
        config: ViewConfig,
        fragments: list[FragmentRecord],
        search_works: Callable[[str], list[tuple[int, str]]],
        on_save: Callable[[int | None, dict[str, object]], bool],
        on_delete: Callable[[int], None],
        on_copy_reference: Callable[[ViewReference], Awaitable[None]],
        allowed_work_ids: set[int] | None = None,
    ) -> None:
        self.page = page
        self.config = config
        self.fragments = fragments
        self.search_works = search_works
        self.on_save = on_save
        self.on_delete = on_delete
        self.on_copy_reference = on_copy_reference
        self.allowed_work_ids = allowed_work_ids
        self.work_filter = ft.TextField(
            label='Filtrar por obra',
            hint_text='Digite o título da obra',
            on_change=self._filter_fragments,
            filled=True,
            fill_color=self.config.colors['surface'],
            **text_field_style(self.config),
        )
        self.work_matches = ft.Column(
            spacing=2,
            tight=True,
            visible=False,
        )
        self.work_filter_group = ft.Column(
            controls=[self.work_filter, self.work_matches],
            spacing=2,
            tight=True,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )
        self.fragment_list = ft.Column(
            spacing=self.config.ui['grid_gap'],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            alignment=ft.MainAxisAlignment.START,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )
        self.editing_id: int | None = None
        self.selected_work_id: int | None = None
        self.root: ft.Container | None = None
        self.fragment_type = ft.Dropdown(
            label='Tipo de fragmento',
            options=[
                self._dropdown_option(key, label)
                for key, label in FRAGMENT_TYPE_LABELS.items()
            ],
            value='quote',
            on_select=self._on_type_change,
            expand=True,
            **{
                **dropdown_style(self.config),
                'text_style': self._dropdown_text_style(),
                'label_style': self._dropdown_text_style(),
            },
        )
        self.work_search = ft.TextField(
            label='Buscar obra no Acervo',
            hint_text='Digite parte do título da obra',
            on_change=self._search_works,
            expand=True,
            **text_field_style(self.config),
        )
        self.work_results = ft.Column(
            spacing=4,
            tight=True,
            visible=False,
        )
        self.work_search_group = ft.Column(
            controls=[self.work_search, self.work_results],
            spacing=2,
            tight=True,
        )
        self.excerpt = ft.TextField(
            label='Conteúdo do fragmento',
            hint_text=(
                'Ex.: “A memória também se constrói pelo que preservamos.”'
            ),
            multiline=True,
            min_lines=3,
            max_lines=8,
            expand=True,
            **text_field_style(self.config),
        )
        self.location_type = ft.Dropdown(
            label='Tipo de localização',
            hint_text='Obrigatório para citações',
            options=[
                self._dropdown_option('__none__', 'Sem localização'),
                *[
                    self._dropdown_option(value, value)
                    for value in FRAGMENT_LOCATION_TYPES
                ],
            ],
            on_select=self._on_location_type_change,
            expand=True,
            **{
                **dropdown_style(self.config),
                'text_style': self._dropdown_text_style(),
                'label_style': self._dropdown_text_style(),
            },
        )
        self.location_value = ft.TextField(
            label='Valor da localização',
            hint_text='Obrigatório para citações',
            max_length=100,
            expand=True,
            **text_field_style(self.config),
        )
        self.form_title = ft.Text(
            value='Novo fragmento',
            size=config.font_sizes['cormorant_medium'],
            font_family=config.font_families['cormorant'],
            color=config.colors['text'],
        )
        self.cancel_button = ft.TextButton(
            content=ft.Text(
                value='Cancelar',
                color=config.colors['text'],
                font_family=config.font_families['montserrat'],
                size=config.font_sizes['montserrat_medium'],
                weight=config.font_weights['montserrat_normal'],
            ),
            on_click=self._close_modal,
            style=ft.ButtonStyle(
                color=config.colors['text'],
                text_style=button_text_style(config),
            ),
        )
        self.save_button = ft.FilledButton(
            content=ft.Text(
                value='Salvar fragmento',
                color=config.colors['bg'],
                font_family=config.font_families['montserrat'],
                size=config.font_sizes['montserrat_medium'],
                weight=config.font_weights['montserrat_normal'],
            ),
            on_click=self._save,
            bgcolor=config.colors['gold'],
            style=ft.ButtonStyle(
                text_style=button_text_style(config),
            ),
        )
        self.modal = ft.AlertDialog(
            modal=False,
            bgcolor=config.colors['surface'],
            title=self.form_title,
            content=self._compose_form(),
            actions=_control_list(self.cancel_button, self.save_button),
            shape=ft.RoundedRectangleBorder(radius=8),
            content_padding=20,
        )

    @staticmethod
    def _run_click_action(
        event: ft.Event[EventControl],
        action: Callable[[], object],
    ) -> None:
        del event
        action()

    def _dropdown_text_style(self) -> ft.TextStyle:
        return ft.TextStyle(
            color=self.config.colors['text'],
            weight=self.config.font_weights['montserrat_normal'],
            font_family=self.config.font_families['montserrat'],
            letter_spacing=2,
            size=self.config.font_sizes['montserrat_tiny'],
        )

    def _dropdown_option(self, key: str, text: str) -> ft.dropdown.Option:
        return ft.dropdown.Option(
            key=key,
            text=text,
            content=ft.Text(
                value=text,
                color=self.config.colors['text'],
                weight=self.config.font_weights['montserrat_normal'],
                font_family=self.config.font_families['montserrat'],
                size=self.config.font_sizes['montserrat_tiny'],
                style=ft.TextStyle(letter_spacing=2),
            ),
        )

    def _on_type_change(self, event: ft.Event[ft.Dropdown]) -> None:
        self.fragment_type.value = event.control.value
        self._update_location_fields()
        self.update()

    def _update_location_fields(self) -> None:
        is_quote = self.fragment_type.value == 'quote'
        self.excerpt.hint_text = (
            'Ex.: “A memória também se constrói pelo que preservamos.”'
            if is_quote
            else (
                'Ex.: O autor relaciona a memória à construção da identidade.'
            )
        )
        self.location_type.label = 'Tipo de localização'
        self.location_type.hint_text = (
            'Obrigatório para citações' if is_quote else ''
        )
        location_label = (
            'Página (máximo de 5 caracteres)'
            if self.location_type.value == 'Página'
            else (
                'Valor da localização'
                if self.location_type.value != 'Outros'
                else 'Localização (ex.: Jo 1: 32-33)'
            )
        )
        self.location_value.label = location_label
        self.location_value.hint_text = (
            'Ex.: Jo 1: 32-33'
            if self.location_type.value == 'Outros'
            else 'Obrigatório para citações' if is_quote else ''
        )

    def _on_location_type_change(self, event: ft.Event[ft.Dropdown]) -> None:
        selected_location = (
            None
            if event.control.value == '__none__'
            else event.control.value
        )
        self.location_type.value = selected_location
        if selected_location is None:
            self.location_value.value = ''
        is_page = selected_location == 'Página'
        self.location_value.max_length = 5 if is_page else 100
        self._update_location_fields()
        self.update()

    def _search_works(self, event: ft.Event[ft.TextField]) -> None:
        query = (event.control.value or '').strip()
        self.selected_work_id = None
        if len(query) < 2:
            self.work_results.controls = []
            self.work_results.visible = False
            self.update()
            return

        matches = self.search_works(query)
        if self.allowed_work_ids is not None:
            matches = [
                match
                for match in matches
                if match[0] in self.allowed_work_ids
            ]
        self.work_results.controls = [
            ft.TextButton(
                content=ft.Text(
                    value=title,
                    color=self.config.colors['text'],
                    font_family=self.config.font_families['montserrat'],
                    size=self.config.font_sizes['montserrat_medium'],
                    weight=self.config.font_weights['montserrat_normal'],
                ),
                style=ft.ButtonStyle(
                    text_style=button_text_style(self.config),
                ),
                on_click=lambda event, resource_id=resource_id, title=title: (
                    self._run_click_action(
                        event,
                        lambda: self._select_work(resource_id, title),
                    )
                ),
            )
            for resource_id, title in matches
        ]
        if not matches:
            self.work_results.controls = [
                ft.Text(
                    value='Nenhuma obra encontrada.',
                    color=self.config.colors['muted'],
                    font_family=self.config.font_families['montserrat']
                )
            ]
        self.work_results.visible = True
        self.update()

    def _select_work(self, resource_id: int, title: str) -> None:
        self.selected_work_id = resource_id
        self.work_search.value = title
        self.work_results.controls = []
        self.work_results.visible = False
        self.update()

    def _save(self, _event: ft.Event[ft.Button]) -> None:
        del _event
        payload: dict[str, object] = {
            'fragment_type': self.fragment_type.value or '',
            'excerpt': self.excerpt.value or '',
            'bib_res_id': self.selected_work_id,
            'location_type': self.location_type.value,
            'location_value': self.location_value.value or '',
        }
        if self.on_save(self.editing_id, payload):
            self._reset_form()
            self.modal.open = False
            self.page.update()

    def _reset_form(self) -> None:
        self.editing_id = None
        self.form_title.value = 'Novo fragmento'
        self.fragment_type.value = 'quote'
        self.selected_work_id = None
        self.work_search.value = ''
        self.work_results.controls = []
        self.work_results.visible = False
        self.excerpt.value = ''
        self.location_type.value = None
        self.location_value.value = ''
        self.location_value.max_length = 100
        self._update_location_fields()

    def _start_edit(self, fragment: FragmentRecord) -> None:
        self.editing_id = fragment['id']
        self.form_title.value = 'Editar fragmento'
        self.fragment_type.value = fragment['fragment_type']
        self.selected_work_id = fragment['bib_res_id']
        self.work_search.value = fragment['work_title']
        self.excerpt.value = fragment['excerpt']
        self.location_type.value = fragment['location_type']
        self.location_value.value = fragment['location_value'] or ''
        self.location_value.max_length = (
            5 if fragment['location_type'] == 'Página' else 100
        )
        self._update_location_fields()
        self.page.show_dialog(self.modal)
        self.update()

    def _close_modal(self, event: ft.Event[ft.TextButton]) -> None:
        del event
        self._reset_form()
        self.modal.open = False
        self.page.update()

    def _open_create_modal(self, event: ft.Event[ft.Button]) -> None:
        del event
        self._reset_form()
        self.page.show_dialog(self.modal)

    def open_create_for_work(self, bib_res_id: int, title: str) -> None:
        if (
            self.allowed_work_ids is not None
            and bib_res_id not in self.allowed_work_ids
        ):
            raise ValueError(
                'A obra do fragmento deve pertencer à compilação.'
            )
        self._reset_form()
        self.selected_work_id = bib_res_id
        self.work_search.value = title
        self.page.show_dialog(self.modal)

    def open_edit_fragment(self, fragment: FragmentRecord) -> None:
        if (
            self.allowed_work_ids is not None
            and fragment['bib_res_id'] not in self.allowed_work_ids
        ):
            raise ValueError(
                'A obra do fragmento deve pertencer à compilação.'
            )
        self._start_edit(fragment)

    def _compose_form(self) -> ft.Container:
        return ft.Container(
            content=ft.Column(
                controls=_control_list(
                    ft.Row(
                        controls=[self.fragment_type],
                        vertical_alignment=ft.CrossAxisAlignment.START,
                    ),
                    self.work_search_group,
                    self.excerpt,
                    ft.Row(
                        controls=[self.location_type, self.location_value],
                        vertical_alignment=ft.CrossAxisAlignment.START,
                    ),
                ),
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
            width=680,
            height=480
        )

    def _compose_fragment_card(
        self, fragment: FragmentRecord
    ) -> ft.Container:
        label = FRAGMENT_TYPE_LABELS.get(
            fragment['fragment_type'],
            'Citação' if fragment['fragment_type'] == 'quote' else 'Comentários/Paráfrases'
        )
        notation = self._abnt_notation(fragment)

        async def copy_fragment(
            event: ft.Event[ft.IconButton],
        ) -> None:
            del event
            await self.on_copy_reference(ViewReference(parts=[
                ReferencePart(fragment['excerpt']),
                ReferencePart('\n'),
                ReferencePart(notation),
            ]))

        label_text = ft.Text(
            value=label,
            color=self.config.colors['muted'],
            size=self.config.font_sizes['montserrat_tiny'],
            font_family=self.config.font_families['montserrat'],
        )
        title_text = ft.Text(
            value=fragment['work_title'],
            size=self.config.font_sizes['cormorant_medium'],
            font_family=self.config.font_families['cormorant'],
            weight=self.config.font_weights['cormorant_semibold'],
            color=self.config.colors['gold'],
        )
        card = ft.Container(
            content=ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Column(
                            controls=[
                                label_text,
                                title_text,
                                ft.Text(
                                    value=fragment['excerpt'],
                                    size=self.config.font_sizes[
                                        'montserrat_small'
                                    ],
                                    color=self.config.colors['text'],
                                    font_family=self.config.font_families[
                                        'montserrat'
                                    ],
                                    weight=self.config.font_weights[
                                        'montserrat_normal'
                                    ],
                                    selectable=True,
                                ),
                                ft.Text(
                                    value=notation,
                                    color=self.config.colors['muted'],
                                    size=self.config.font_sizes[
                                        'montserrat_tiny'
                                    ],
                                    font_family=self.config.font_families[
                                        'montserrat'
                                    ],
                                ),
                            ],
                            spacing=6,
                            horizontal_alignment=(
                                ft.CrossAxisAlignment.STRETCH
                            ),
                            expand=True,
                        ),
                        ft.Column(
                            controls=[
                                ft.IconButton(
                                    icon=ft.Icons.EDIT_OUTLINED,
                                    tooltip='Editar fragmento',
                                    on_click=lambda event, item=fragment: (
                                        self._run_click_action(
                                            event,
                                            lambda: self._start_edit(item),
                                        )
                                    ),
                                    icon_size=20,
                                    icon_color=self.config.colors['text'],
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.COPY,
                                    tooltip='Copiar citação e notação ABNT',
                                    on_click=copy_fragment,
                                    icon_size=20,
                                    icon_color=self.config.colors['text'],
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.DELETE_OUTLINE,
                                    tooltip='Excluir fragmento',
                                    icon_color=ft.Colors.RED_400,
                                    on_click=lambda event, item=fragment: (
                                        self._run_click_action(
                                            event,
                                            lambda: self.on_delete(
                                                item['id']
                                            ),
                                        )
                                    ),
                                    icon_size=24,
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
                margin=ft.Margin(left=8),
                padding=self.config.ui['card_padding'],
            ),
            bgcolor=self.config.colors['surface'],
            border=ft.Border.all(1, self.config.colors['border']),
            border_radius=self.config.ui['card_radius'],
            animate=ft.Animation(180, ft.AnimationCurve.EASE_OUT),
        )

        def handle_hover(event: ft.Event[ft.Container]) -> None:
            if event.data:
                card.bgcolor = self.config.colors['card_hover']
                card.border = ft.Border(
                    left=ft.BorderSide(8, self.config.colors['text']),
                    top=ft.BorderSide(1, self.config.colors['text']),
                    right=ft.BorderSide(1, self.config.colors['text']),
                    bottom=ft.BorderSide(1, self.config.colors['text']),
                )
                title_text.color = self.config.colors['text']
            else:
                card.bgcolor = self.config.colors['surface']
                card.border = ft.Border.all(
                    1, self.config.colors['border']
                )
                title_text.color = self.config.colors['gold']
            card.update()

        card.on_hover = handle_hover
        return card

    @staticmethod
    def _abnt_notation(fragment: FragmentRecord) -> str:
        return fragment_abnt_notation(fragment)

    def update(self) -> None:
        self.page.update()

    def _filter_fragments(
        self, _event: ft.Event[ft.TextField] | None = None
    ) -> None:
        query = (self.work_filter.value or '').strip().casefold()
        matching_titles = list(dict.fromkeys(
            fragment['work_title']
            for fragment in self.fragments
            if query and query in fragment['work_title'].casefold()
        ))
        if len(query) < 2:
            self.work_matches.controls = []
            self.work_matches.visible = False
        else:
            self.work_matches.controls = [
                ft.TextButton(
                    content=ft.Text(
                        value=title,
                        color=self.config.colors['text'],
                        font_family=self.config.font_families['montserrat'],
                        size=self.config.font_sizes['montserrat_medium'],
                        weight=self.config.font_weights[
                            'montserrat_normal'
                        ],
                    ),
                    style=ft.ButtonStyle(
                        text_style=button_text_style(self.config),
                    ),
                    on_click=(
                        lambda event, selected_title=title: (
                            self._run_click_action(
                                event,
                                lambda: self._select_filter_work(
                                    selected_title
                                ),
                            )
                        )
                    ),
                )
                for title in matching_titles[:8]
            ]
            if not matching_titles:
                self.work_matches.controls = [
                    ft.Text(
                        value='Nenhuma obra encontrada.',
                        color=self.config.colors['muted'],
                    )
                ]
            self.work_matches.visible = True
        self._update_fragment_cards(query)
        if _event is not None:
            self.page.update()

    def _update_fragment_cards(self, query: str) -> None:
        filtered_fragments = [
            fragment
            for fragment in self.fragments
            if query in fragment['work_title'].casefold()
        ]
        self.fragment_list.controls = [
            self._compose_fragment_card(fragment)
            for fragment in filtered_fragments
        ]
        if not self.fragment_list.controls:
            empty_message = (
                'Nenhum fragmento encontrado para essa obra.'
                if query
                else 'Ainda não há fragmentos cadastrados.'
            )
            self.fragment_list.controls.append(
                ft.Text(
                    value=empty_message,
                    color=self.config.colors['muted'],
                    size=self.config.font_sizes['montserrat_small'],
                    font_family=self.config.font_families['montserrat'],
                )
            )

    def _select_filter_work(self, title: str) -> None:
        self.work_filter.value = title
        self.work_matches.controls = []
        self.work_matches.visible = False
        self._update_fragment_cards(title.casefold())
        self.page.update()

    def compose(self) -> ft.Container:
        self._filter_fragments()

        self.root = ft.Container(
            expand=True,
            padding=ft.Padding(
                top=self.config.ui['content_top_padding'],
                right=0,
                bottom=0,
                left=0,
            ),
            bgcolor=self.config.colors['surface'],
            content=ft.Column(
                controls=[
                    self._compose_header(),
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                self.work_filter_group,
                                self.fragment_list,
                            ],
                            spacing=self.config.ui['modal_gap'],
                            alignment=ft.MainAxisAlignment.START,
                            expand=True,
                            horizontal_alignment=(
                                ft.CrossAxisAlignment.STRETCH
                            ),
                        ),
                        border=ft.Border(
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
        )
        return self.root

    def _compose_header(self) -> ft.Container:
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Column(
                        controls=[
                            ft.Text(
                                value='Fragmentos',
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
                                    'Citações e comentários de obras do '
                                    'seu Acervo'
                                ),
                                weight=self.config.font_weights[
                                    'montserrat_semibold'
                                ],
                                color=self.config.colors['muted'],
                                font_family=self.config.font_families[
                                    'montserrat'
                                ],
                                size=self.config.font_sizes['montserrat_tiny'],
                            ),
                        ],
                        spacing=2,
                        alignment=ft.MainAxisAlignment.CENTER,
                    ),
                    ft.FilledButton(
                        content=ft.Text(
                            '+ Novo fragmento',
                            font_family=self.config.font_families[
                                'montserrat'
                            ],
                            weight=self.config.font_weights[
                                'montserrat_semibold'
                            ],
                            size=self.config.font_sizes['montserrat_small'],
                            color=self.config.colors['bg'],
                        ),
                        style=ft.ButtonStyle(
                            text_style=button_text_style(
                                self.config,
                                size='montserrat_small',
                                weight='montserrat_semibold',
                            ),
                        ),
                        align=ft.Alignment.CENTER_RIGHT,
                        on_click=self._open_create_modal,
                        bgcolor=self.config.colors['gold'],
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

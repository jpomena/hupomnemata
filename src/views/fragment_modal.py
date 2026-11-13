"""Diálogo padronizado de criação e edição de fragmento.

Componente unificado consumido pela tela de Fragmentos, pelas Compilações
e pelo Leitor de PDF, garantindo conformidade visual absoluta e
reaproveitamento integral de regras e geometria.
"""

from collections.abc import Callable
from typing import TypeVar

import flet as ft

from src.contracts import FRAGMENT_LOCATION_TYPES, FragmentRecord
from src.utils.error_log import log_exception
from src.utils.types import ViewConfig
from src.views import ui_kit as ui
from src.views.ui_kit import W500, W600, s

EventControl = TypeVar('EventControl', bound=ft.Control)
NO_LOCATION = '__none__'


class LocationValueField(ft.TextField):
    """Campo de valor de localização com altura geométrica preservada.

    No Flutter/Flet, atribuir `max_length` ou `counter=''` força o `InputDecorator`
    a alocar espaço para a linha do contador (`_HelperError`), comprimindo a
    caixa com borda útil para 32px e criando discrepância visual em relação ao
    `Dropdown` vizinho (48px). Além disso, com `dense=True`, o `InputDecorator`
    colapsa a caixa para a dimensão intrínseca do conteúdo salvo quando o
    `content_padding` vertical preenche a altura até os exatos 48px do padrão
    Material 3. Esta classe preserva `max_length` em Python para validação e
    controle de tamanho sem registrar atributos de counter no Flutter.
    """

    def __init__(self, *args, max_length: int | None = None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._custom_max_length = max_length
        self.counter = None

    @property
    def max_length(self) -> int | None:
        return getattr(self, '_custom_max_length', None)

    @max_length.setter
    def max_length(self, value: int | None) -> None:
        self._custom_max_length = value


# Alias para retrocompatibilidade
_LocationValueField = LocationValueField


class FragmentModal:
    """Modal unificado para inserção e edição de fragmentos textuais."""

    def __init__(
        self,
        page: ft.Page,
        config: ViewConfig,
        on_save: Callable[[int | None, dict[str, object]], bool] | None = None,
        search_works: Callable[[str], list[tuple[int, str]]] | None = None,
        allowed_work_ids: set[int] | None = None,
        on_saved: Callable[[], None] | None = None,
    ) -> None:
        self.page = page
        self.config = config
        self.on_save = on_save or self._default_on_save
        self.search_works = search_works or self._default_search_works
        self.allowed_work_ids = allowed_work_ids
        self.on_saved = on_saved

        # Estado do formulário
        self.editing_id: int | None = None
        self.selected_work_id: int | None = None
        self.fragment_type_value = 'quote'
        self._build_form()

    def _default_on_save(self, editing_id: int | None, payload: dict[str, object]) -> bool:
        from src.services.fragment_service import FragmentService

        try:
            svc = FragmentService()
            if editing_id is not None:
                svc.update(editing_id, payload)
            else:
                svc.create(payload)
            return True
        except Exception as error:
            log_exception('Falha ao persistir fragmento pelo modal unificado', error)
            if self.page:
                ui.toast(self.page, self.config, f'Erro ao salvar: {error}')
            return False

    def _default_search_works(self, query: str) -> list[tuple[int, str]]:
        try:
            from src.services.work_service import WorkService
            from src.utils.normalizers import CoreNormalizer

            service = WorkService(CoreNormalizer())
            return service.search_works(query, include_partial=True)
        except Exception as error:
            log_exception('Falha ao buscar obras para o modal de fragmento', error)
            return []

    def _input_style(self, multiline: bool = False) -> dict:
        c = self.config
        colors = c.colors
        family = c.font_families['montserrat']
        padding = (
            ft.Padding.symmetric(horizontal=s(10), vertical=s(10))
            if multiline
            else ft.Padding.only(left=s(10), right=s(10), top=s(18), bottom=s(16))
        )
        return {
            'text_size': s(13),
            'text_style': ft.TextStyle(font_family=family, color=colors['text'], weight=W500),
            'hint_style': ft.TextStyle(font_family=family, color=colors['faint'], weight=W500),
            'color': colors['text'],
            'bgcolor': colors['bg'],
            'border_color': colors['border_strong'],
            'focused_border_color': colors['gold'],
            'border_width': 1,
            'focused_border_width': 1,
            'border_radius': ft.BorderRadius.all(s(6)),
            'content_padding': padding,
            'dense': True,
        }

    def _text_input(self, hint: str, multiline: bool = False, **kwargs) -> ft.TextField:
        return ft.TextField(
            hint_text=hint,
            cursor_color=self.config.colors['gold'],
            multiline=multiline,
            **{**self._input_style(multiline=multiline), **kwargs},
        )

    def _field(
        self,
        label: ft.Text | str,
        control: ft.Control,
        expand: bool | int | None = None,
        stretch: bool = False,
    ) -> ft.Column:
        label_control = label if isinstance(label, ft.Text) else self._label(label)
        return ft.Column(
            [label_control, control],
            spacing=s(6),
            tight=True,
            expand=expand,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH if stretch else ft.CrossAxisAlignment.START,
        )

    def _label(self, value: str) -> ft.Text:
        return ui.ui_text(self.config, value, size=12, weight=W600, color=self.config.colors['muted'])

    def _dropdown_option(self, key: str, text: str) -> ft.dropdown.Option:
        return ft.dropdown.Option(
            key=key,
            text=text,
            content=ui.ui_text(self.config, text, size=13),
        )

    def _build_form(self) -> None:
        c = self.config
        colors = c.colors
        style = self._input_style()
        self.kind_host = ft.Container()
        self.work_search = self._text_input(
            'Digite parte do título da obra',
            on_change=self._search_works,
            height=s(48),
        )
        self.work_results = ft.Column(spacing=0, tight=True, visible=False)
        self.work_search_group = ft.Column(
            controls=[self.work_search, self.work_results],
            spacing=s(4),
            tight=True,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )
        self.excerpt = self._text_input(
            'Ex.: “A memória também se constrói pelo que preservamos.”',
            multiline=True,
            min_lines=4,
            max_lines=10,
        )
        self.location_type_label = self._label('Tipo de localização')
        self.location_type = ft.Dropdown(
            options=[
                self._dropdown_option(NO_LOCATION, 'Sem localização'),
                *[self._dropdown_option(value, value) for value in FRAGMENT_LOCATION_TYPES],
            ],
            on_select=self._on_location_type_change,
            expand=True,
            height=s(48),
            expanded_insets=ft.Padding.all(0),
            text_size=style['text_size'],
            text_style=style['text_style'],
            hint_style=style['hint_style'],
            color=colors['text'],
            bgcolor=colors['surface'],
            fill_color=colors['bg'],
            filled=True,
            border_color=colors['border_strong'],
            focused_border_color=colors['gold'],
            border_width=1,
            focused_border_width=1,
            border_radius=style['border_radius'],
            content_padding=ft.Padding.symmetric(horizontal=s(10), vertical=s(10)),
            dense=True,
            trailing_icon=ui.icon(c, 'chevron-down', size=11),
            selected_trailing_icon=ui.icon(c, 'chevron-up', size=11),
        )
        self.location_value_label = self._label('Valor da localização')
        self.location_value = LocationValueField(
            hint_text='Obrigatório para citações',
            cursor_color=colors['gold'],
            max_length=100,
            height=s(48),
            on_change=self._on_location_value_change,
            **style,
        )
        self.form_title = ui.ui_text(c, 'Novo fragmento', size=15, weight=W600)
        self.cancel_button = ui.button(c, 'Cancelar', on_click=self._close_modal, variant='ghost')
        self.save_button = ui.button(c, 'Salvar fragmento', icon_name='check', on_click=self._save, variant='primary')

        head = ft.Container(
            content=ft.Row(
                [self.form_title, ui.icon_button(c, 'xmark', on_click=self._close_modal, tooltip='Fechar')],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            height=s(52),
            padding=ft.Padding.only(left=s(24), right=s(12)),
            border=ft.Border.only(bottom=ft.BorderSide(1, colors['border'])),
        )
        self.form_body = ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        self._field('Obra do acervo', self.work_search_group, expand=True, stretch=True),
                        self._field('Tipo', self.kind_host),
                    ],
                    spacing=s(16),
                    vertical_alignment=ft.CrossAxisAlignment.START,
                ),
                self._field('Conteúdo', self.excerpt, stretch=True),
                ft.Row(
                    controls=[
                        self._field(self.location_type_label, self.location_type, expand=True, stretch=True),
                        self._field(self.location_value_label, self.location_value, expand=True, stretch=True),
                    ],
                    spacing=s(16),
                    vertical_alignment=ft.CrossAxisAlignment.START,
                ),
            ],
            spacing=s(16),
            tight=True,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )
        foot = ft.Container(
            content=ft.Row(
                [self.cancel_button, self.save_button],
                alignment=ft.MainAxisAlignment.END,
                spacing=s(8),
            ),
            padding=ft.Padding.only(left=s(24), right=s(12), top=s(10), bottom=s(10)),
            bgcolor=colors['surface'],
            border=ft.Border.only(top=ft.BorderSide(1, colors['border'])),
        )
        self.form = ft.Container(
            content=ft.Column(
                [head, ft.Container(self.form_body, padding=s(24)), foot],
                spacing=0,
                tight=True,
            ),
            width=s(640),
        )
        self.modal = ft.AlertDialog(
            modal=False,
            bgcolor=colors['surface'],
            content=self.form,
            content_padding=0,
            inset_padding=s(24),
            shape=ft.RoundedRectangleBorder(radius=s(10)),
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        )
        self._render_kind_selector()
        self._update_location_fields()

    def _render_kind_selector(self) -> None:
        self.kind_host.content = ui.segmented(
            self.config,
            [('quote', 'Citação', None), ('comment', 'Paráfrase', None)],
            self.fragment_type_value,
            self._set_fragment_type,
        )

    def _set_fragment_type(self, kind: str) -> None:
        self.fragment_type_value = kind
        self._render_kind_selector()
        self._update_location_fields()
        self.update()

    @staticmethod
    def _run_click_action(
        event: ft.Event[EventControl],
        action: Callable[[], object],
    ) -> None:
        del event
        action()

    def _update_location_fields(self) -> None:
        is_quote = self.fragment_type_value == 'quote'
        self.excerpt.hint_text = (
            'Ex.: “A memória também se constrói pelo que preservamos.”'
            if is_quote
            else 'Ex.: O autor relaciona a memória à construção da identidade.'
        )
        self.location_type.hint_text = (
            'Obrigatório para citações' if is_quote else 'Opcional'
        )
        if self.location_type.value == 'Página':
            value_label = 'Página (máximo de 5 caracteres)'
        elif self.location_type.value == 'Outros':
            value_label = 'Localização (ex.: Jo 1: 32-33)'
        else:
            value_label = 'Valor da localização'
        self.location_value_label.value = value_label
        self.location_value.hint_text = (
            'Ex.: Jo 1: 32-33'
            if self.location_type.value == 'Outros'
            else 'Obrigatório para citações' if is_quote else 'Opcional'
        )

    def _on_location_value_change(self, event: ft.Event[ft.TextField]) -> None:
        value = event.control.value or ''
        limit = self.location_value.max_length
        if limit and len(value) > limit:
            event.control.value = value[:limit]
            try:
                event.control.update()
            except (RuntimeError, AssertionError, AttributeError):
                pass

    def _on_location_type_change(self, event: ft.Event[ft.Dropdown]) -> None:
        selected_location = (
            None if event.control.value == NO_LOCATION else event.control.value
        )
        self.location_type.value = selected_location
        if selected_location is None:
            self.location_value.value = ''
        self.location_value.max_length = 5 if selected_location == 'Página' else 100
        if (
            self.location_value.value
            and self.location_value.max_length
            and len(self.location_value.value) > self.location_value.max_length
        ):
            self.location_value.value = self.location_value.value[:self.location_value.max_length]
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
            matches = [match for match in matches if match[0] in self.allowed_work_ids]
        c = self.config
        if matches:
            self.work_results.controls = [
                ui.hover_surface(
                    c,
                    ui.ui_text(c, title, size=13),
                    on_click=lambda event, resource_id=resource_id, title=title: (
                        self._run_click_action(
                            event,
                            lambda: self._select_work(resource_id, title),
                        )
                    ),
                    padding=ft.Padding.symmetric(horizontal=s(10), vertical=s(8)),
                )
                for resource_id, title in matches[:8]
            ]
        else:
            self.work_results.controls = [
                ft.Container(
                    ui.ui_text(c, 'Nenhuma obra encontrada.', size=13, color=c.colors['muted']),
                    padding=ft.Padding.symmetric(horizontal=s(10), vertical=s(8)),
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

    def _payload(self) -> dict[str, object]:
        return {
            'fragment_type': self.fragment_type_value or '',
            'excerpt': self.excerpt.value or '',
            'bib_res_id': self.selected_work_id,
            'location_type': self.location_type.value,
            'location_value': self.location_value.value or '',
        }

    def _save(self, _event: ft.Event[ft.Container] | None = None) -> None:
        del _event
        if self.on_save(self.editing_id, self._payload()):
            self._reset_form()
            self.modal.open = False
            self.page.update()
            if self.on_saved:
                self.on_saved()

    def _reset_form(self) -> None:
        self.editing_id = None
        self.form_title.value = 'Novo fragmento'
        self.fragment_type_value = 'quote'
        self.selected_work_id = None
        self.work_search.value = ''
        self.work_results.controls = []
        self.work_results.visible = False
        self.excerpt.value = ''
        self.location_type.value = None
        self.location_value.value = ''
        self.location_value.max_length = 100
        self._render_kind_selector()
        self._update_location_fields()

    def _start_edit(self, fragment: FragmentRecord, on_saved: Callable[[], None] | None = None) -> None:
        if on_saved:
            self.on_saved = on_saved
        self.editing_id = fragment['id']
        self.form_title.value = 'Editar fragmento'
        self.fragment_type_value = fragment['fragment_type']
        self.selected_work_id = fragment['bib_res_id']
        self.work_search.value = fragment['work_title']
        self.excerpt.value = fragment['excerpt']
        self.location_type.value = fragment['location_type']
        self.location_value.value = fragment['location_value'] or ''
        self.location_value.max_length = 5 if fragment['location_type'] == 'Página' else 100
        self._render_kind_selector()
        self._update_location_fields()
        self.page.show_dialog(self.modal)
        self.update()

    def _close_modal(self, event: ft.Event[ft.Container] | None = None) -> None:
        del event
        self._reset_form()
        self.modal.open = False
        self.page.update()

    def _open_create_modal(self, event: ft.Event[ft.Container] | None = None) -> None:
        del event
        self._reset_form()
        self.page.show_dialog(self.modal)

    def open_create(self, on_saved: Callable[[], None] | None = None) -> None:
        """Abre o diálogo de novo fragmento."""
        if on_saved:
            self.on_saved = on_saved
        self._open_create_modal()

    def open_create_for_work(
        self,
        bib_res_id: int,
        title: str,
        initial_location_type: str | None = None,
        initial_location_value: str | None = None,
        initial_excerpt: str | None = None,
        on_saved: Callable[[], None] | None = None,
    ) -> None:
        """Abre o diálogo pré-vinculando à obra informada."""
        if (
            self.allowed_work_ids is not None
            and bib_res_id not in self.allowed_work_ids
        ):
            raise ValueError('A obra do fragmento deve pertencer à compilação.')
        if on_saved:
            self.on_saved = on_saved
        self._reset_form()
        self.selected_work_id = bib_res_id
        self.work_search.value = title
        if initial_location_type:
            self.location_type.value = initial_location_type
            self._update_location_fields()
        if initial_location_value:
            self.location_value.value = initial_location_value
        if initial_excerpt:
            self.excerpt.value = initial_excerpt
        self.page.show_dialog(self.modal)

    def open_edit(self, fragment: FragmentRecord, on_saved: Callable[[], None] | None = None) -> None:
        """Abre o diálogo preenchido com os dados do fragmento a editar."""
        if (
            self.allowed_work_ids is not None
            and fragment['bib_res_id'] not in self.allowed_work_ids
        ):
            raise ValueError('A obra do fragmento deve pertencer à compilação.')
        self._start_edit(fragment, on_saved=on_saved)

    def update(self) -> None:
        if self.page:
            try:
                self.page.update()
            except (RuntimeError, AssertionError, AttributeError):
                pass

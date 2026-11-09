"""Tela Fragmentos e diálogo de criar/editar fragmento.

O layout segue ``viewFragmentos`` e ``fragRow`` do protótipo
(``design/prototype/index.html``): segmentado Todos/Citações/Paráfrases,
filtro de texto, grupos por obra que recolhem e linhas com as ações no hover.
O diálogo também é usado pelas compilações (``open_create_for_work`` e
``open_edit_fragment``), por isso é montado já no construtor.
"""

from collections.abc import Awaitable, Callable
from typing import TypeVar

import flet as ft

from src.contracts import FRAGMENT_LOCATION_TYPES, FragmentRecord
from src.utils.display_dates import format_date
from src.utils.fragment_reference import fragment_abnt_notation
from src.utils.types import ReferencePart, ViewConfig, ViewReference
from src.views import ui_kit as ui
from src.views.ui_kit import W500, W600, s

EventControl = TypeVar('EventControl', bound=ft.Control)

KIND_LABELS = {'quote': 'Citação', 'comment': 'Paráfrase'}
KIND_FILTERS = (('all', 'Todos'), ('quote', 'Citações'), ('comment', 'Paráfrases'))
LOCATION_PREFIXES = {
    'Página': 'p.',
    'Capítulo': 'cap.',
    'Seção': 'seção',
    'Localizador/posição': 'localizador',
}
QUOTE_OPENERS = ('“', '"', '«', '‘', "'")
NO_LOCATION = '__none__'


def _plural(count: int, singular: str, plural_form: str) -> str:
    return f'{count} {singular if count == 1 else plural_form}'


def quoted(text: str) -> str:
    """Coloca aspas curvas na citação quando ela ainda não tem aspas."""
    value = (text or '').strip()
    if not value or value.startswith(QUOTE_OPENERS):
        return value
    return f'“{value}”'


def location_label(fragment: FragmentRecord) -> str:
    location_type = fragment.get('location_type')
    value = fragment.get('location_value')
    if not value:
        return ''
    prefix = LOCATION_PREFIXES.get(location_type or '')
    return f'{prefix} {value}' if prefix else str(value)


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
        compilations_by_fragment: dict[int, list[str]] | None = None,
        on_open_work: Callable[[int], None] | None = None,
        initial_query: str = '',
    ) -> None:
        self.page = page
        self.config = config
        self.fragments = fragments
        self.search_works = search_works
        self.on_save = on_save
        self.on_delete = on_delete
        self.on_copy_reference = on_copy_reference
        self.allowed_work_ids = allowed_work_ids
        self.compilations_by_fragment = compilations_by_fragment or {}
        self.on_open_work = on_open_work

        # estado da lista
        self.kind_filter = 'all'
        self.query = initial_query or ''
        self.collapsed: set[int] = set()
        self.root: ft.Container | None = None

        colors = config.colors
        self.search = ui.search_field(
            config,
            'Filtrar por texto, obra ou autor',
            on_change=self._on_search,
            value=self.query,
            width=300,
        )
        self.segment_host = ft.Container()
        self.count_text = ui.ui_text(config, '', size=12, color=colors['faint'], tabular=True)
        self.collapse_host = ft.Container()
        self.fragment_list = ft.Column(
            spacing=s(8),
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )

        # estado do formulário
        self.editing_id: int | None = None
        self.selected_work_id: int | None = None
        self.fragment_type_value = 'quote'
        self._build_form()

    # ── formulário ─────────────────────────────────────────

    def _input_style(self) -> dict:
        c = self.config
        colors = c.colors
        family = c.font_families['montserrat']
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
            'content_padding': ft.Padding.symmetric(horizontal=s(10), vertical=s(10)),
            'dense': True,
        }

    def _text_input(self, hint: str, **kwargs) -> ft.TextField:
        return ft.TextField(
            hint_text=hint,
            cursor_color=self.config.colors['gold'],
            counter=ft.Container(width=0, height=0),
            **{**self._input_style(), **kwargs},
        )

    def _field(self, label: ft.Text | str, control: ft.Control, expand: bool | int | None = None) -> ft.Column:
        label_control = label if isinstance(label, ft.Text) else self._label(label)
        return ft.Column([label_control, control], spacing=s(6), tight=True, expand=expand)

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
        )
        self.work_results = ft.Column(spacing=0, tight=True, visible=False)
        self.work_search_group = ft.Column(
            controls=[self.work_search, self.work_results],
            spacing=s(4),
            tight=True,
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
            content_padding=style['content_padding'],
            dense=True,
            trailing_icon=ui.icon(c, 'chevron-down', size=11),
            selected_trailing_icon=ui.icon(c, 'chevron-up', size=11),
        )
        self.location_value_label = self._label('Valor da localização')
        self.location_value = self._text_input('Obrigatório para citações', max_length=100)
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
                self._field('Tipo', self.kind_host),
                self._field('Obra do acervo', self.work_search_group),
                self._field('Conteúdo', self.excerpt),
                ft.Row(
                    controls=[
                        self._field(self.location_type_label, self.location_type, expand=True),
                        self._field(self.location_value_label, self.location_value, expand=True),
                    ],
                    spacing=s(12),
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
            bgcolor=colors['chrome'],
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

    def _on_location_type_change(self, event: ft.Event[ft.Dropdown]) -> None:
        selected_location = (
            None if event.control.value == NO_LOCATION else event.control.value
        )
        self.location_type.value = selected_location
        if selected_location is None:
            self.location_value.value = ''
        self.location_value.max_length = 5 if selected_location == 'Página' else 100
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

    def _start_edit(self, fragment: FragmentRecord) -> None:
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

    def open_create(self) -> None:
        """Abre o diálogo de novo fragmento (usado pela tela Início)."""
        self._open_create_modal()

    def open_create_for_work(self, bib_res_id: int, title: str) -> None:
        if (
            self.allowed_work_ids is not None
            and bib_res_id not in self.allowed_work_ids
        ):
            raise ValueError('A obra do fragmento deve pertencer à compilação.')
        self._reset_form()
        self.selected_work_id = bib_res_id
        self.work_search.value = title
        self.page.show_dialog(self.modal)

    def open_edit_fragment(self, fragment: FragmentRecord) -> None:
        if (
            self.allowed_work_ids is not None
            and fragment['bib_res_id'] not in self.allowed_work_ids
        ):
            raise ValueError('A obra do fragmento deve pertencer à compilação.')
        self._start_edit(fragment)

    @staticmethod
    def _abnt_notation(fragment: FragmentRecord) -> str:
        return fragment_abnt_notation(fragment)

    def update(self) -> None:
        self.page.update()

    # ── lista ──────────────────────────────────────────────

    def visible_fragments(self) -> list[FragmentRecord]:
        """Fragmentos que passam pelo segmentado e pelo filtro de texto."""
        query = self.query.strip().casefold()
        return [
            fragment
            for fragment in self.fragments
            if (self.kind_filter == 'all' or fragment['fragment_type'] == self.kind_filter)
            and (
                not query
                or query in ' '.join((
                    fragment.get('excerpt') or '',
                    fragment.get('work_title') or '',
                    fragment.get('citation_author') or '',
                )).casefold()
            )
        ]

    @staticmethod
    def group_by_work(fragments: list[FragmentRecord]) -> list[tuple[int, list[FragmentRecord]]]:
        """Agrupa por obra: obras mais recentes primeiro, fragmentos em ordem de cadastro."""
        groups: dict[int, list[FragmentRecord]] = {}
        for fragment in fragments:
            groups.setdefault(fragment['bib_res_id'], []).append(fragment)
        return [
            (work_id, sorted(items, key=lambda item: item['id']))
            for work_id, items in sorted(groups.items(), key=lambda item: -item[0])
        ]

    def set_kind_filter(self, kind: str) -> None:
        self.kind_filter = kind
        self._refresh()

    def _on_search(self, event: ft.Event[ft.TextField]) -> None:
        self.query = event.control.value or ''
        self._refresh()

    def clear_query(self) -> None:
        self.query = ''
        self.search.value = ''
        self._refresh()

    def toggle_group(self, work_id: int) -> None:
        if work_id in self.collapsed:
            self.collapsed.discard(work_id)
        else:
            self.collapsed.add(work_id)
        self._refresh()

    def toggle_all(self) -> None:
        work_ids = [work_id for work_id, _ in self.group_by_work(self.visible_fragments())]
        if work_ids and all(work_id in self.collapsed for work_id in work_ids):
            self.collapsed.difference_update(work_ids)
        else:
            self.collapsed.update(work_ids)
        self._refresh()

    def _refresh(self, update: bool = True) -> None:
        c = self.config
        total = len(self.fragments)
        quotes = sum(1 for fragment in self.fragments if fragment['fragment_type'] == 'quote')
        visible = self.visible_fragments()
        groups = self.group_by_work(visible)

        self.segment_host.content = ui.segmented(
            c,
            [
                (key, label, {'all': total, 'quote': quotes, 'comment': total - quotes}[key])
                for key, label in KIND_FILTERS
            ],
            self.kind_filter,
            self.set_kind_filter,
        )
        if len(visible) == total:
            self.count_text.value = _plural(len(groups), 'obra', 'obras')
        else:
            self.count_text.value = f"{len(visible)} de {total} em {_plural(len(groups), 'obra', 'obras')}"
        all_collapsed = bool(groups) and all(work_id in self.collapsed for work_id, _ in groups)
        self.collapse_host.content = ui.button(
            c,
            'Expandir tudo' if all_collapsed else 'Recolher tudo',
            icon_name='angles-down' if all_collapsed else 'angles-up',
            variant='ghost',
            small=True,
            disabled=not groups,
            on_click=lambda _e: self.toggle_all(),
        )

        if groups:
            controls: list[ft.Control] = [self._compose_group(work_id, items) for work_id, items in groups]
        elif not self.fragments:
            controls = [
                ui.empty_state(
                    c,
                    'quote-left',
                    'Nenhum fragmento ainda',
                    'Registre citações e paráfrases das obras do acervo para reunir aqui o que você leu.',
                    action=ui.button(c, 'Novo fragmento', icon_name='plus', small=True, on_click=self._open_create_modal),
                )
            ]
        else:
            body = (
                f'Nada corresponde a “{self.query.strip()}”.'
                if self.query.strip()
                else 'Nenhum fragmento deste tipo.'
            )
            controls = [
                ui.empty_state(
                    c,
                    'magnifying-glass',
                    'Nenhum fragmento encontrado',
                    body,
                    action=ui.button(c, 'Limpar filtro', small=True, on_click=lambda _e: self._clear_filters()),
                )
            ]
        controls.append(ft.Container(height=s(40)))
        self.fragment_list.controls = controls
        if update:
            self.update()

    def _clear_filters(self) -> None:
        self.kind_filter = 'all'
        self.clear_query()

    def _compose_group(self, work_id: int, items: list[FragmentRecord]) -> ft.Container:
        c = self.config
        colors = c.colors
        first = items[0]
        title = first.get('work_title') or 'Obra sem título'
        collapsed = work_id in self.collapsed
        byline = ' · '.join(
            part for part in (first.get('citation_author'), first.get('display_year')) if part
        )
        title_text = ui.ui_text(c, title, size=13, weight=W600)
        title_text.expand = True
        title_text.expand_loose = True
        title_line: list[ft.Control] = [title_text]
        if byline:
            title_line.append(ui.ui_text(c, byline, size=12, color=colors['faint']))
        head_controls: list[ft.Control] = [
            ui.icon_button(
                c,
                'chevron-right' if collapsed else 'chevron-down',
                on_click=lambda _e, wid=work_id: self.toggle_group(wid),
                tooltip=f"{'Expandir' if collapsed else 'Recolher'} {title}",
            ),
            ft.Container(
                ft.Row(title_line, spacing=s(8), vertical_alignment=ft.CrossAxisAlignment.CENTER),
                expand=True,
            ),
            ui.badge(c, str(len(items))),
        ]
        if self.on_open_work is not None:
            head_controls.append(
                ui.icon_button(
                    c,
                    'arrow-up-right-from-square',
                    on_click=lambda _e, wid=work_id: self.on_open_work(wid),
                    tooltip='Abrir obra no acervo',
                )
            )
        head = ft.Container(
            content=ft.Row(head_controls, spacing=s(8), vertical_alignment=ft.CrossAxisAlignment.CENTER),
            height=s(44),
            padding=ft.Padding.only(left=s(8), right=s(8)),
            border=None if collapsed else ft.Border.only(bottom=ft.BorderSide(1, colors['border'])),
            on_click=lambda _e, wid=work_id: self.toggle_group(wid),
        )
        rows: list[ft.Control] = [head]
        if not collapsed:
            rows.extend(
                self._compose_fragment_row(fragment, last=index == len(items) - 1)
                for index, fragment in enumerate(items)
            )
        group = ui.card(c, rows)
        group.data = {'work_id': work_id, 'collapsed': collapsed}
        return group

    def _compose_fragment_row(self, fragment: FragmentRecord, last: bool = False) -> ft.Container:
        c = self.config
        colors = c.colors
        is_quote = fragment['fragment_type'] == 'quote'
        notation = self._abnt_notation(fragment)

        async def copy_fragment(event) -> None:
            del event
            await self.on_copy_reference(ViewReference(parts=[
                ReferencePart(fragment['excerpt']),
                ReferencePart('\n'),
                ReferencePart(notation),
            ]))

        if is_quote:
            body = ui.serif_text(c, quoted(fragment['excerpt']), size=18, selectable=True)
        else:
            body = ui.ui_text(c, fragment['excerpt'], size=13, color=colors['muted'], max_lines=None, selectable=True)
            body.style = ft.TextStyle(letter_spacing=ui.UI_TRACKING, height=1.6)

        meta: list[ft.Control] = [ui.ui_text(c, KIND_LABELS.get(fragment['fragment_type'], 'Fragmento'), size=12, weight=W600, color=colors['muted'])]
        for part in (location_label(fragment), format_date(fragment.get('created_at'))):
            if part:
                meta.append(ui.ui_text(c, '·', size=12, color=colors['faint']))
                meta.append(ui.meta_text(c, part))
        for name in self.compilations_by_fragment.get(fragment['id'], []):
            meta.append(ui.badge(c, name, icon_name='folder', accent=True))

        tools = ft.Row(
            controls=[
                ui.icon_button(c, 'copy', on_click=copy_fragment, tooltip='Copiar com citação', style='regular'),
                ui.icon_button(
                    c, 'pen',
                    on_click=lambda event, item=fragment: self._run_click_action(event, lambda: self._start_edit(item)),
                    tooltip='Editar',
                ),
                ui.icon_button(
                    c, 'trash-can',
                    on_click=lambda event, item=fragment: self._run_click_action(event, lambda: self.on_delete(item['id'])),
                    tooltip='Excluir',
                    style='regular',
                    hover_color=colors['danger'],
                ),
            ],
            spacing=s(2),
            tight=True,
            opacity=0,
        )
        row = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        ui.icon(c, 'quote-left' if is_quote else 'comment', size=12.5, style='solid' if is_quote else 'regular'),
                        width=s(24),
                        padding=ft.Padding.only(top=s(5) if is_quote else s(3)),
                    ),
                    ft.Column(
                        [body, ft.Row(meta, spacing=s(6), wrap=True, vertical_alignment=ft.CrossAxisAlignment.CENTER)],
                        spacing=s(6),
                        tight=True,
                        expand=True,
                    ),
                    tools,
                ],
                spacing=s(8),
                vertical_alignment=ft.CrossAxisAlignment.START,
            ),
            padding=ft.Padding.only(left=s(16), right=s(8), top=s(10), bottom=s(10)),
            border=None if last else ft.Border.only(bottom=ft.BorderSide(1, colors['border'])),
        )
        row.data = {'fragment_id': fragment['id'], 'tools': tools}

        def _hover(event) -> None:
            hovering = event.data in (True, 'true')
            row.bgcolor = colors['card_hover'] if hovering else None
            tools.opacity = 1 if hovering else 0
            row.update()

        row.on_hover = _hover
        return row

    def _page_description(self) -> str:
        total = len(self.fragments)
        if not total:
            return 'Citações e paráfrases das obras do seu acervo.'
        works = len({fragment['bib_res_id'] for fragment in self.fragments})
        what = 'citação ou paráfrase' if total == 1 else 'citações e paráfrases'
        return f"{total} {what} de {_plural(works, 'obra', 'obras')} do acervo."

    def compose(self) -> ft.Container:
        c = self.config
        self._refresh(update=False)
        header = ui.page_header(
            c,
            'Fragmentos',
            self._page_description(),
            actions=[
                ui.button(c, 'Novo fragmento', icon_name='plus', variant='primary', on_click=self._open_create_modal),
            ],
        )
        self.header = header
        self.toolbar = ui.toolbar(
            c,
            [self.segment_host, self.search],
            trailing=[self.count_text, self.collapse_host],
        )
        self.root = ft.Container(
            expand=True,
            bgcolor=c.colors['bg'],
            content=ft.Column(
                controls=[
                    header,
                    self.toolbar,
                    ft.Container(
                        self.fragment_list,
                        expand=True,
                        padding=ft.Padding.only(left=s(32), right=s(32), top=s(4)),
                    ),
                ],
                spacing=0,
                expand=True,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
        )
        return self.root

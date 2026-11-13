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

from src.contracts import FragmentRecord
from src.utils.display_dates import format_date
from src.utils.fragment_reference import fragment_abnt_notation
from src.utils.types import ReferencePart, ViewConfig, ViewReference
from src.views import ui_kit as ui
from src.views.fragment_modal import FragmentModal, LocationValueField
from src.views.ui_kit import W600, W700, s

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

        # componente padronizado do formulário/modal
        self.modal_component = FragmentModal(
            page=self.page,
            config=self.config,
            on_save=self.on_save,
            search_works=self.search_works,
            allowed_work_ids=self.allowed_work_ids,
        )

    @staticmethod
    def _run_click_action(
        event: ft.Event[EventControl],
        action: Callable[[], object],
    ) -> None:
        del event
        action()

    # ── delegação do formulário para FragmentModal ─────────

    @property
    def editing_id(self) -> int | None:
        return self.modal_component.editing_id

    @editing_id.setter
    def editing_id(self, value: int | None) -> None:
        self.modal_component.editing_id = value

    @property
    def selected_work_id(self) -> int | None:
        return self.modal_component.selected_work_id

    @selected_work_id.setter
    def selected_work_id(self, value: int | None) -> None:
        self.modal_component.selected_work_id = value

    @property
    def fragment_type_value(self) -> str:
        return self.modal_component.fragment_type_value

    @fragment_type_value.setter
    def fragment_type_value(self, value: str) -> None:
        self.modal_component.fragment_type_value = value

    @property
    def work_search(self) -> ft.TextField:
        return self.modal_component.work_search

    @property
    def work_results(self) -> ft.Column:
        return self.modal_component.work_results

    @property
    def work_search_group(self) -> ft.Column:
        return self.modal_component.work_search_group

    @property
    def excerpt(self) -> ft.TextField:
        return self.modal_component.excerpt

    @property
    def location_type_label(self) -> ft.Text:
        return self.modal_component.location_type_label

    @property
    def location_type(self) -> ft.Dropdown:
        return self.modal_component.location_type

    @property
    def location_value_label(self) -> ft.Text:
        return self.modal_component.location_value_label

    @property
    def location_value(self) -> LocationValueField:
        return self.modal_component.location_value

    @property
    def form_title(self) -> ft.Text:
        return self.modal_component.form_title

    @property
    def cancel_button(self) -> ft.Control:
        return self.modal_component.cancel_button

    @property
    def save_button(self) -> ft.Control:
        return self.modal_component.save_button

    @property
    def form_body(self) -> ft.Column:
        return self.modal_component.form_body

    @property
    def form(self) -> ft.Container:
        return self.modal_component.form

    @property
    def modal(self) -> ft.AlertDialog:
        return self.modal_component.modal

    @property
    def kind_host(self) -> ft.Container:
        return self.modal_component.kind_host

    def _render_kind_selector(self) -> None:
        self.modal_component._render_kind_selector()

    def _set_fragment_type(self, kind: str) -> None:
        self.modal_component._set_fragment_type(kind)

    def _update_location_fields(self) -> None:
        self.modal_component._update_location_fields()

    def _on_location_value_change(self, event: ft.Event[ft.TextField]) -> None:
        self.modal_component._on_location_value_change(event)

    def _on_location_type_change(self, event: ft.Event[ft.Dropdown]) -> None:
        self.modal_component._on_location_type_change(event)

    def _search_works(self, event: ft.Event[ft.TextField]) -> None:
        self.modal_component._search_works(event)

    def _select_work(self, resource_id: int, title: str) -> None:
        self.modal_component._select_work(resource_id, title)

    def _save(self, event: ft.Event[ft.Container] | None = None) -> None:
        self.modal_component._save(event)

    def _reset_form(self) -> None:
        self.modal_component._reset_form()

    def _start_edit(self, fragment: FragmentRecord) -> None:
        self.modal_component._start_edit(fragment)

    def _close_modal(self, event: ft.Event[ft.Container] | None = None) -> None:
        self.modal_component._close_modal(event)

    def _open_create_modal(self, event: ft.Event[ft.Container] | None = None) -> None:
        self.modal_component._open_create_modal(event)

    def open_create(self) -> None:
        """Abre o diálogo de novo fragmento (usado pela tela Início)."""
        self.modal_component.open_create()

    def open_create_for_work(
        self,
        bib_res_id: int,
        title: str,
        initial_location_type: str | None = None,
        initial_location_value: str | None = None,
        initial_excerpt: str | None = None,
    ) -> None:
        self.modal_component.open_create_for_work(
            bib_res_id=bib_res_id,
            title=title,
            initial_location_type=initial_location_type,
            initial_location_value=initial_location_value,
            initial_excerpt=initial_excerpt,
        )

    def open_edit_fragment(self, fragment: FragmentRecord) -> None:
        self.modal_component.open_edit(fragment)

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
        title_text = ui.serif_text(c, title, size=18.5, weight=W700)
        title_text.expand = True
        title_text.expand_loose = True
        title_line: list[ft.Control] = [title_text]
        if byline:
            title_line.append(ui.ui_text(c, byline, size=12.5, color=colors['faint']))
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
            animate=ft.Animation(120, ft.AnimationCurve.EASE_OUT),
            on_click=lambda _e, wid=work_id: self.toggle_group(wid),
        )

        def _head_hover(e) -> None:
            hovering = e.data in (True, 'true')
            head.bgcolor = colors['card_hover'] if hovering else None
            title_text.color = colors['gold'] if hovering else colors['text']
            try:
                head.update()
            except Exception:
                pass

        head.on_hover = _head_hover
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
            animate=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
        )
        row.data = {'fragment_id': fragment['id'], 'tools': tools}

        def _hover(event) -> None:
            hovering = event.data in (True, 'true')
            row.bgcolor = colors['card_hover'] if hovering else None
            if hovering:
                row.border = ft.Border(
                    left=ft.BorderSide(s(3), colors['gold']),
                    top=ft.BorderSide(1, colors['border_strong']),
                    right=ft.BorderSide(1, colors['border_strong']),
                    bottom=ft.BorderSide(1, colors['border'] if not last else colors['border_strong']),
                )
            else:
                row.border = None if last else ft.Border.only(bottom=ft.BorderSide(1, colors['border']))
            tools.opacity = 1 if hovering else 0
            body.color = colors['gold'] if hovering else (colors['text'] if is_quote else colors['muted'])
            try:
                row.update()
            except Exception:
                pass

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

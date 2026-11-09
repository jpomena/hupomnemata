"""Tela Início (Gabinete de Leitura) e tela provisória de seções incompletas.

O layout segue ``viewInicio`` do protótipo (``design/prototype/index.html``):
cabeçalho, faixa de quatro KPIs clicáveis e duas colunas (compilações e
atividade recente à esquerda; acervo por tipo, atalhos e epígrafe à direita).
Os números vêm do banco por ``get_dashboard_data``; nada é inventado.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

import flet as ft

from src.utils import ViewConfig
from src.utils.display_dates import (
    format_date,
    format_day,
    format_time,
    sort_key,
)
from src.views import ui_kit as ui
from src.views.ui_kit import W500, W600, s

FEED_LIMIT = 8
LEFT_SPAN = 17
RIGHT_SPAN = 10

TYPE_ICONS: dict[str, tuple[str, str]] = {
    'Livros em geral': ('book-open', 'solid'),
    'Trabalho acadêmico': ('graduation-cap', 'solid'),
    'Correspondência': ('envelope', 'regular'),
    'Artigo de revista': ('file-lines', 'regular'),
    'Revista': ('book-open-reader', 'solid'),
    'Coleção periódica': ('book', 'solid'),
    'Artigo de jornal': ('newspaper', 'regular'),
    'Anais de evento em volume único': ('calendar-days', 'regular'),
    'Anais de evento em periódico': ('calendar-days', 'regular'),
    'Legislação': ('gavel', 'solid'),
    'Jurisprudência': ('building-columns', 'solid'),
    'Patente': ('lightbulb', 'regular'),
    'Documento digital': ('file-lines', 'regular'),
    'Audiovisual': ('film', 'solid'),
    'Áudio': ('music', 'solid'),
    'Partitura': ('music', 'solid'),
    'Documento visual': ('image', 'regular'),
    'Cartográfico': ('map', 'regular'),
    'Tridimensional': ('cube', 'solid'),
}

EPIGRAPH_FALLBACK = (
    'Reunir o que se pôde ouvir ou ler, e isso com uma finalidade que nada '
    'mais é que a constituição de si.'
)
EPIGRAPH_SOURCE = 'Michel Foucault, A escrita de si'


def plural(count: int, singular: str, plural_form: str) -> str:
    return f'{count} {singular if count == 1 else plural_form}'


@dataclass
class DashboardSummary:
    """Números e listas da tela Início, calculados a partir dos dados reais."""

    works: int = 0
    fragments: int = 0
    quotes: int = 0
    comments: int = 0
    compilations: int = 0
    linked_works: int = 0
    works_without_fragments: int = 0
    types: list[tuple[str, int]] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)
    compilation_rows: list[dict] = field(default_factory=list)


def summarize_dashboard(data: dict | None) -> DashboardSummary:
    """Calcula KPIs, tipos e a atividade recente a partir do dicionário do controlador.

    ``data`` traz ``works`` (id, title, authors, type, created_at),
    ``fragments`` (id, kind, excerpt, bib_res_id, work_title, created_at) e
    ``compilations`` (id, name, description, work_ids, fragments, ideas,
    updated_at). Chaves ausentes contam como listas vazias.
    """
    data = data or {}
    works = list(data.get('works') or [])
    fragments = list(data.get('fragments') or [])
    compilations = list(data.get('compilations') or [])

    quotes = sum(1 for item in fragments if item.get('kind') == 'quote')
    fragment_work_ids = {item.get('bib_res_id') for item in fragments}
    type_counts: dict[str, int] = {}
    for work in works:
        label = work.get('type') or 'Sem tipo'
        type_counts[label] = type_counts.get(label, 0) + 1
    types = sorted(type_counts.items(), key=lambda item: (-item[1], item[0]))
    linked = {
        work_id
        for compilation in compilations
        for work_id in compilation.get('work_ids') or []
    }

    events: list[dict] = []
    for work in works:
        if not work.get('created_at'):
            continue
        icon_name, icon_style = TYPE_ICONS.get(
            work.get('type') or '', ('file-lines', 'regular')
        )
        events.append({
            'at': work['created_at'],
            'icon': icon_name,
            'icon_style': icon_style,
            'prefix': 'Obra cadastrada: ',
            'title': work.get('title') or 'Obra sem título',
            'snippet': work.get('authors') or 'Sem autoria',
            'serif': False,
        })
    for fragment in fragments:
        if not fragment.get('created_at'):
            continue
        is_quote = fragment.get('kind') == 'quote'
        events.append({
            'at': fragment['created_at'],
            'icon': 'quote-left' if is_quote else 'comment',
            'icon_style': 'solid' if is_quote else 'regular',
            'prefix': 'Citação em ' if is_quote else 'Paráfrase em ',
            'title': fragment.get('work_title') or 'Obra sem título',
            'snippet': ' '.join(str(fragment.get('excerpt') or '').split()),
            'serif': is_quote,
        })
    events.sort(key=lambda event: sort_key(event['at']), reverse=True)

    return DashboardSummary(
        works=len(works),
        fragments=len(fragments),
        quotes=quotes,
        comments=len(fragments) - quotes,
        compilations=len(compilations),
        linked_works=len(linked),
        works_without_fragments=sum(
            1 for work in works if work.get('id') not in fragment_work_ids
        ),
        types=types,
        events=events[:FEED_LIMIT],
        compilation_rows=compilations,
    )


def epigraph_text(config: ViewConfig) -> str:
    """Trecho curto da epígrafe de Foucault guardada em ``texts.yaml``."""
    source = ' '.join(
        str(config.texts.get('messages', {}).get('placeholder_citation', '')).split()
    )
    start = source.lower().find('reunir o que')
    end = source.find('constituição de si', start)
    if start < 0 or end < 0:
        return EPIGRAPH_FALLBACK
    excerpt = source[start:end + len('constituição de si')]
    return excerpt[0].upper() + excerpt[1:] + '.'


class DashboardComposer:
    """Compõe a tela Início e a tela provisória de seções incompletas."""

    def __init__(
        self,
        scale: float,
        config: ViewConfig,
        on_navigate: Callable[[str], None],
        get_dashboard_data: Callable[[], dict] | None = None,
        on_navigate_with: Callable[..., None] | None = None,
        on_new_fragment: Callable[[], None] | None = None,
        on_open_palette: Callable[[], None] | None = None,
    ):
        self.scale = scale
        self.config = config
        self.on_navigate = on_navigate
        self.get_dashboard_data = get_dashboard_data
        self.on_navigate_with = on_navigate_with or (
            lambda destination, **_options: on_navigate(destination)
        )
        self.on_new_fragment = on_new_fragment or (
            lambda: self.on_navigate_with('Fragmentos', create=True)
        )
        self.on_open_palette = on_open_palette
        self.summary = DashboardSummary()

    # ── dados ──────────────────────────────────────────────

    def _load_summary(self) -> DashboardSummary:
        data: dict = {}
        if self.get_dashboard_data is not None:
            try:
                data = self.get_dashboard_data() or {}
            except Exception:
                data = {}
        return summarize_dashboard(data)

    # ── peças ──────────────────────────────────────────────

    def _kpi(
        self,
        icon_name: str,
        label: str,
        value: int,
        caption: str,
        on_click: Callable,
        icon_style: str = 'solid',
        last: bool = False,
    ) -> ft.Container:
        c = self.config
        colors = c.colors
        kpi_icon = ui.icon(c, icon_name, size=12, style=icon_style)
        kpi_label = ui.ui_text(c, label, size=12, color=colors['muted'])
        normal_border = None if last else ft.Border.only(right=ft.BorderSide(1, colors['border']))
        hover_border = ft.Border(
            left=ft.BorderSide(s(3), colors['gold']),
            top=ft.BorderSide(1, colors['border_strong']),
            right=ft.BorderSide(1, colors['border'] if not last else colors['border_strong']),
            bottom=ft.BorderSide(1, colors['border_strong']),
        )
        cell = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            kpi_icon,
                            kpi_label,
                        ],
                        spacing=s(6),
                        tight=True,
                    ),
                    ft.Container(
                        ui.ui_text(c, str(value), size=24, weight=W600, tabular=True),
                        margin=ft.Margin.only(top=s(4)),
                    ),
                    ui.ui_text(c, caption, size=12, color=colors['faint']),
                ],
                spacing=s(2),
                tight=True,
            ),
            padding=s(16),
            expand=True,
            border=normal_border,
            animate=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
            on_click=on_click,
        )
        cell.data = {'kpi': label, 'value': value}

        def _hover(e):
            hovering = e.data in (True, 'true')
            cell.bgcolor = colors['card_hover'] if hovering else None
            cell.border = hover_border if hovering else normal_border
            kpi_icon.color = colors['gold'] if hovering else colors['faint']
            kpi_label.color = colors['text'] if hovering else colors['muted']
            try:
                cell.update()
            except Exception:
                pass

        cell.on_hover = _hover
        return cell

    def _compose_kpis(self) -> ft.Container:
        c = self.config
        summary = self.summary
        types = len(summary.types)
        cells = [
            self._kpi(
                'book', 'Obras', summary.works,
                f"em {plural(types, 'tipo documental', 'tipos documentais')}",
                lambda _e: self.on_navigate('Acervo'),
            ),
            self._kpi(
                'quote-left', 'Fragmentos', summary.fragments,
                f"{plural(summary.quotes, 'citação', 'citações')} · "
                f"{plural(summary.comments, 'paráfrase', 'paráfrases')}",
                lambda _e: self.on_navigate('Fragmentos'),
            ),
            self._kpi(
                'folder-open', 'Compilações', summary.compilations,
                plural(summary.linked_works, 'obra vinculada', 'obras vinculadas'),
                lambda _e: self.on_navigate('Compilações'),
                icon_style='regular',
            ),
            self._kpi(
                'pen-to-square', 'Obras sem fragmentos', summary.works_without_fragments,
                'ainda não fichadas',
                lambda _e: self.on_navigate_with('Acervo', sort_key='frag', sort_desc=False),
                icon_style='regular',
                last=True,
            ),
        ]
        self.kpi_cells = cells
        return ft.Container(
            # Altura fixa: STRETCH dentro de uma coluna com rolagem não tem
            # altura limitada e quebra o layout da página inteira.
            content=ft.Row(cells, spacing=0, vertical_alignment=ft.CrossAxisAlignment.STRETCH),
            height=s(112),
            bgcolor=c.colors['surface'],
            border=ft.Border.all(1, c.colors['border']),
            border_radius=ft.BorderRadius.all(s(8)),
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            margin=ft.Margin.only(left=s(32), right=s(32), bottom=s(24)),
        )

    def _column_head(self, label: str, width: float | None = None, right: bool = False) -> ft.Container:
        c = self.config
        return ft.Container(
            ui.ui_text(c, label, size=12, weight=W500, color=c.colors['faint'], align=ft.TextAlign.RIGHT if right else None),
            width=s(width) if width else None,
            expand=width is None,
            alignment=ft.Alignment.CENTER_RIGHT if right else ft.Alignment.CENTER_LEFT,
        )

    def _cell(self, value: str, width: float, faint: bool = False) -> ft.Container:
        c = self.config
        return ft.Container(
            ui.ui_text(c, value, size=13 if not faint else 12, color=c.colors['faint'] if faint else c.colors['text'], tabular=True, align=ft.TextAlign.RIGHT),
            width=s(width),
            alignment=ft.Alignment.CENTER_RIGHT,
        )

    def _open_compilation(self, compilation_id: int) -> None:
        self.on_navigate(f'compilacao:{compilation_id}')

    def _compose_compilations_card(self) -> ft.Container:
        c = self.config
        colors = c.colors
        rows = self.summary.compilation_rows
        head = ui.card_head(
            c,
            'Compilações em andamento',
            trailing=ui.link_button(c, 'Ver todas', on_click=lambda _e: self.on_navigate('Compilações')),
        )
        if not rows:
            return ui.card(c, [
                head,
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ui.ui_text(c, 'Nenhuma compilação ainda.', size=13, weight=W600),
                            ui.ui_text(c, 'Reúna obras e fragmentos de um projeto de escrita em uma compilação.', size=13, color=colors['muted'], max_lines=2),
                            ft.Container(
                                ui.button(c, 'Nova compilação', icon_name='plus', small=True, on_click=lambda _e: self.on_navigate_with('Compilações', create=True)),
                                margin=ft.Margin.only(top=s(4)),
                            ),
                        ],
                        spacing=s(6),
                        tight=True,
                    ),
                    padding=s(16),
                ),
            ])

        widths = {'works': 48, 'fragments': 80, 'ideas': 48, 'updated': 92, 'action': 116}
        header = ft.Container(
            content=ft.Row(
                controls=[
                    self._column_head('Projeto'),
                    self._column_head('Obras', widths['works'], right=True),
                    self._column_head('Fragmentos', widths['fragments'], right=True),
                    self._column_head('Ideias', widths['ideas'], right=True),
                    self._column_head('Atualizada', widths['updated'], right=True),
                    ft.Container(width=s(widths['action'])),
                ],
                spacing=s(12),
            ),
            height=s(34),
            padding=ft.Padding.symmetric(horizontal=s(16)),
            border=ft.Border.only(bottom=ft.BorderSide(1, colors['border'])),
        )
        table_rows: list[ft.Control] = [header]
        for index, row in enumerate(rows):
            last = index == len(rows) - 1
            name_column: list[ft.Control] = [ui.ui_text(c, row.get('name') or 'Sem nome', size=13, weight=W600, max_lines=2)]
            if row.get('description'):
                name_column.append(ui.ui_text(c, row['description'], size=12, color=colors['faint'], max_lines=2))
            content = ft.Row(
                controls=[
                    ft.Column(name_column, spacing=s(1), tight=True, expand=True),
                    self._cell(str(len(row.get('work_ids') or [])), widths['works']),
                    self._cell(str(row.get('fragments', 0)), widths['fragments']),
                    self._cell(str(row.get('ideas', 0)), widths['ideas']),
                    self._cell(format_date(row.get('updated_at')), widths['updated'], faint=True),
                    ft.Container(
                        ui.button(c, 'Abrir caderno', small=True, on_click=lambda _e, cid=row['id']: self._open_compilation(cid)),
                        width=s(widths['action']),
                        alignment=ft.Alignment.CENTER_RIGHT,
                    ),
                ],
                spacing=s(12),
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
            row_box = ui.hover_surface(
                c,
                content,
                on_click=lambda _e, cid=row['id']: self._open_compilation(cid),
                padding=ft.Padding.symmetric(horizontal=s(16), vertical=s(10)),
                radius=0,
            )
            row_box.data = {'compilation_id': row['id']}
            table_rows.append(
                ft.Container(
                    row_box,
                    border=None if last else ft.Border.only(bottom=ft.BorderSide(1, colors['border'])),
                )
            )
        return ui.card(c, [head, ft.Column(table_rows, spacing=0, tight=True)])

    def _feed_item(self, event: dict) -> ft.Container:
        c = self.config
        colors = c.colors
        family = c.font_families['montserrat']
        what = ft.Text(
            spans=[
                ft.TextSpan(event['prefix'], style=ft.TextStyle(color=colors['muted'], weight=W500, font_family=family, size=s(13), letter_spacing=ui.UI_TRACKING)),
                ft.TextSpan(event['title'], style=ft.TextStyle(color=colors['text'], weight=W600, font_family=family, size=s(13), letter_spacing=ui.UI_TRACKING)),
            ],
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
        )
        if event['serif']:
            snippet = ui.serif_text(c, event['snippet'], size=16, color=colors['muted'], max_lines=1, height=1.3)
        else:
            snippet = ui.ui_text(c, event['snippet'], size=12, color=colors['faint'])
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        ui.icon(c, event['icon'], size=12.5, color=colors['muted'], style=event['icon_style']),
                        width=s(28),
                        height=s(28),
                        bgcolor=colors['card_hover'],
                        border_radius=ft.BorderRadius.all(s(6)),
                        alignment=ft.Alignment.CENTER,
                    ),
                    ft.Column([what, snippet], spacing=s(1), tight=True, expand=True),
                    ft.Container(
                        ui.ui_text(c, format_time(event['at']), size=12, color=colors['faint'], tabular=True),
                        padding=ft.Padding.only(top=s(2)),
                    ),
                ],
                spacing=s(8),
                vertical_alignment=ft.CrossAxisAlignment.START,
            ),
            padding=ft.Padding.symmetric(horizontal=s(16), vertical=s(10)),
        )

    def _compose_activity_card(self) -> ft.Container:
        c = self.config
        colors = c.colors
        events = self.summary.events
        trailing = ui.ui_text(c, f'Últimos {len(events)} registros' if len(events) != 1 else 'Último registro', size=12, color=colors['faint']) if events else None
        head = ui.card_head(c, 'Atividade recente', trailing=trailing)
        if not events:
            return ui.card(c, [
                head,
                ft.Container(
                    ui.ui_text(c, 'Obras e fragmentos cadastrados aparecem aqui, por data.', size=13, color=colors['muted'], max_lines=2),
                    padding=s(16),
                ),
            ])
        items: list[ft.Control] = []
        last_day = None
        for index, event in enumerate(events):
            day = format_day(event['at'])
            if day != last_day:
                items.append(
                    ft.Container(
                        ui.ui_text(c, day, size=12, weight=W600, color=colors['faint']),
                        bgcolor=colors['bg'],
                        padding=ft.Padding.only(left=s(16), right=s(16), top=s(7), bottom=s(5)),
                        border=ft.Border.only(bottom=ft.BorderSide(1, colors['border'])),
                        data={'feed_day': day},
                    )
                )
                last_day = day
            item = self._feed_item(event)
            if index + 1 < len(events):
                item.border = ft.Border.only(bottom=ft.BorderSide(1, colors['border']))
            items.append(item)
        self.feed_column = ft.Column(items, spacing=0, tight=True)
        return ui.card(c, [head, self.feed_column])

    def _type_bar(self, label: str, count: int, maximum: int) -> ft.Container:
        c = self.config
        colors = c.colors
        track_width = s(90)
        ratio = max(0.04, count / maximum) if maximum else 0.04
        name = ui.ui_text(c, label, size=13, color=colors['muted'])
        name_box = ft.Container(name, expand=True, on_click=lambda _e, t=label: self.on_navigate_with('Acervo', type_filter=t), tooltip=f'Ver {label} no acervo')

        def _hover(e):
            hovering = e.data in (True, 'true')
            name.color = colors['text'] if hovering else colors['muted']
            name.style = ft.TextStyle(
                letter_spacing=ui.UI_TRACKING,
                decoration=ft.TextDecoration.UNDERLINE if hovering else ft.TextDecoration.NONE,
            )
            try:
                name_box.update()
            except Exception:
                pass

        name_box.on_hover = _hover
        row = ft.Container(
            content=ft.Row(
                controls=[
                    name_box,
                    ft.Container(
                        content=ft.Container(width=round(track_width * ratio, 2), height=s(6), bgcolor=colors['faint'], border_radius=ft.BorderRadius.all(s(3))),
                        width=track_width,
                        height=s(6),
                        bgcolor=colors['card_hover'],
                        border_radius=ft.BorderRadius.all(s(3)),
                        alignment=ft.Alignment.CENTER_LEFT,
                        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                    ),
                    ft.Container(
                        ui.ui_text(c, str(count), size=12, color=colors['muted'], tabular=True, align=ft.TextAlign.RIGHT),
                        width=s(28),
                        alignment=ft.Alignment.CENTER_RIGHT,
                    ),
                ],
                spacing=s(8),
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding.symmetric(horizontal=s(16), vertical=s(5)),
        )
        row.data = {'type': label, 'count': count}
        return row

    def _compose_types_card(self) -> ft.Container:
        c = self.config
        types = self.summary.types
        head = ui.card_head(c, 'Acervo por tipo', trailing=ui.link_button(c, 'Abrir acervo', on_click=lambda _e: self.on_navigate('Acervo')))
        if not types:
            body: ft.Control = ft.Container(
                ui.ui_text(c, 'Nenhuma obra no acervo ainda.', size=13, color=c.colors['muted']),
                padding=s(16),
            )
        else:
            maximum = types[0][1]
            self.type_rows = [self._type_bar(label, count, maximum) for label, count in types]
            body = ft.Container(ft.Column(self.type_rows, spacing=0, tight=True), padding=ft.Padding.symmetric(vertical=s(4)))
        return ui.card(c, [head, body])

    def _shortcut(
        self,
        icon_name: str,
        label: str,
        on_click: Callable | None = None,
        shortcut: str | None = None,
        planned: bool = False,
        tooltip: str | None = None,
    ) -> ft.Container:
        c = self.config
        colors = c.colors
        trailing: list[ft.Control] = []
        if planned:
            trailing.append(ui.badge(c, 'Planejado'))
        elif shortcut:
            trailing.append(ui.kbd(c, shortcut))
        icon_ctrl = ui.icon(c, icon_name, size=14)
        label_ctrl = ui.ui_text(c, label, size=13, color=colors['faint'] if planned else colors['text'], expand=True)
        content = ft.Row(
            controls=[
                icon_ctrl,
                label_ctrl,
                *trailing,
            ],
            spacing=s(10),
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        if planned:
            box = ft.Container(content, height=s(34), padding=ft.Padding.symmetric(horizontal=s(8)), tooltip=tooltip)
        else:
            def _on_hover_sc(hovering: bool) -> None:
                icon_ctrl.color = colors['gold'] if hovering else colors['faint']

            box = ui.hover_surface(c, content, on_click=on_click, padding=ft.Padding.symmetric(horizontal=s(8)), height=s(34), on_hover=_on_hover_sc)
            box.tooltip = tooltip
        box.data = {'shortcut': label, 'planned': planned}
        return box

    def _compose_shortcuts_card(self) -> ft.Container:
        c = self.config
        self.shortcut_rows = [
            self._shortcut('file-circle-plus', 'Inserir nova obra', lambda _e: self.on_navigate('work_insert'), shortcut='⌘N'),
            self._shortcut('quote-left', 'Registrar fragmento', lambda _e: self.on_new_fragment()),
            self._shortcut('magnifying-glass', 'Buscar no gabinete', lambda _e: self.on_open_palette() if self.on_open_palette else None, shortcut='⌘K'),
            self._shortcut('file-import', 'Importar metadados', planned=True, tooltip='Inserir obra por BibTeX, ISBN, ISSN, DOI ou PDF'),
            self._shortcut('file-export', 'Exportar referências', planned=True, tooltip='Exportar referências e dados'),
        ]
        return ui.card(c, [
            ui.card_head(c, 'Atalhos'),
            ft.Container(ft.Column(self.shortcut_rows, spacing=0, tight=True), padding=s(4)),
        ])

    def _compose_epigraph(self) -> ft.Container:
        c = self.config
        return ft.Container(
            content=ft.Column(
                controls=[
                    ui.serif_text(c, f'“{epigraph_text(c)}”', size=16, color=c.colors['faint'], italic=True),
                    ui.ui_text(c, EPIGRAPH_SOURCE, size=12, color=c.colors['faint']),
                ],
                spacing=s(6),
                tight=True,
            ),
            padding=ft.Padding.symmetric(horizontal=s(4)),
        )

    # ── tela ───────────────────────────────────────────────

    def compose(self) -> ft.Container:
        """Monta a tela Início."""
        c = self.config
        self.summary = self._load_summary()
        header = ui.page_header(
            c,
            c.texts['app']['main_view_title'],
            c.texts['app']['main_view_subtitle'],
            actions=[
                ui.button(c, 'Novo fragmento', icon_name='quote-left', on_click=lambda _e: self.on_new_fragment()),
                ui.button(c, 'Nova obra', icon_name='plus', variant='primary', on_click=lambda _e: self.on_navigate('work_insert')),
            ],
        )
        gap = s(24)
        left = ft.Column(
            [self._compose_compilations_card(), self._compose_activity_card()],
            spacing=gap,
            tight=True,
            col={'xs': LEFT_SPAN + RIGHT_SPAN, 'lg': LEFT_SPAN},
        )
        right = ft.Column(
            [self._compose_types_card(), self._compose_shortcuts_card(), self._compose_epigraph()],
            spacing=gap,
            tight=True,
            col={'xs': LEFT_SPAN + RIGHT_SPAN, 'lg': RIGHT_SPAN},
        )
        grid = ft.Container(
            content=ft.ResponsiveRow(
                [left, right],
                columns=LEFT_SPAN + RIGHT_SPAN,
                spacing=gap,
                run_spacing=gap,
                vertical_alignment=ft.CrossAxisAlignment.START,
            ),
            padding=ft.Padding.only(left=s(32), right=s(32), bottom=s(48)),
        )
        return ft.Container(
            expand=True,
            bgcolor=c.colors['bg'],
            content=ft.Column(
                controls=[header, self._compose_kpis(), grid],
                spacing=0,
                expand=True,
                scroll=ft.ScrollMode.AUTO,
            ),
        )

    # ── tela provisória ───────────────────────────────────

    def _compose_header(
        self,
        title: str | None = None,
        subtitle: str | None = None,
    ) -> ft.Container:
        """Cabeçalho simples da tela provisória."""
        c = self.config
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Column(
                        controls=[
                            ft.Text(
                                value=title if title is not None else c.texts['app']['main_view_title'],
                                size=s(30),
                                weight=W600,
                                color=c.colors['text'],
                                font_family=c.font_families['cormorant'],
                                style=ft.TextStyle(height=1.1),
                            ),
                            ui.ui_text(
                                c,
                                subtitle if subtitle is not None else c.texts['app']['main_view_subtitle'],
                                size=13,
                                color=c.colors['muted'],
                            ),
                        ],
                        spacing=s(4),
                        tight=True,
                    )
                ],
                vertical_alignment=ft.CrossAxisAlignment.END,
            ),
            padding=ft.Padding.only(left=s(32), right=s(32), top=s(32), bottom=s(16)),
        )

    def compose_placeholder(self, section: str) -> ft.Container:
        """Monta uma tela provisória para uma seção ainda incompleta."""
        c = self.config
        return ft.Container(
            expand=True,
            bgcolor=c.colors['bg'],
            content=ft.Column(
                controls=[
                    self._compose_header(title='Oops...', subtitle=section),
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Image(
                                    src='assets/images/wip.png',
                                    width=460,
                                    height=307,
                                    fit=ft.BoxFit.CONTAIN,
                                    semantics_label='Ilustração de seção em construção',
                                ),
                                ui.ui_text(
                                    c,
                                    'Esta seção ainda está em construção.',
                                    size=13,
                                    color=c.colors['muted'],
                                    align=ft.TextAlign.CENTER,
                                ),
                            ],
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            alignment=ft.MainAxisAlignment.CENTER,
                            spacing=s(16),
                        ),
                        border=ft.Border(top=ft.BorderSide(1, c.colors['border'])),
                        padding=s(32),
                        expand=True,
                        alignment=ft.Alignment.CENTER,
                    ),
                ],
                spacing=0,
                expand=True,
            ),
        )

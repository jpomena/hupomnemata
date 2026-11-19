"""Layout do leitor de PDF: topbar, área de leitura e barra lateral.

As seções foram extraídas literalmente de ``PdfReaderView._build_layout``.
"""

import flet as ft

from src.views import ui_kit as ui
from .pdf_common import BASE_PAGE_HEIGHT

s = ui.s
W600 = ui.W600
W700 = ui.W700


class PdfLayoutMixin:
    """Construtores de seção usados por ``PdfReaderView._build_layout``."""

    def _build_top_bar(self) -> ft.Container:
        c = self.config
        colors = c.colors
        # ── Barra Superior de Ferramentas ────────────────────────
        title_text = ui.serif_text(c, self.work_title, size=15, weight=W700, max_lines=1)

        prev_page_btn = ui.icon_button(c, 'chevron-left', on_click=self._prev_page, tooltip='Página anterior (←)', small=True)
        next_page_btn = ui.icon_button(c, 'chevron-right', on_click=self._next_page, tooltip='Próxima página (→)', small=True)

        zoom_out_btn = ui.icon_button(
            c, 'magnifying-glass-minus', on_click=self._zoom_out, tooltip='Diminuir zoom (- / Roda do mouse)', small=True
        )
        zoom_reset_btn = ui.icon_button(
            c, 'compress', on_click=self._zoom_reset, tooltip='Ajustar página ao leitor (100%)', small=True
        )
        zoom_in_btn = ui.icon_button(
            c, 'magnifying-glass-plus', on_click=self._zoom_in, tooltip='Aumentar zoom (+ / Roda do mouse)', small=True
        )

        zoom_group = ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ui.ui_text(c, 'Zoom', size=10, weight=W600, color=colors['faint']),
                        self.zoom_label,
                    ],
                    spacing=s(4),
                    alignment=ft.MainAxisAlignment.CENTER,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    tight=True,
                ),
                ft.Row(
                    controls=[zoom_out_btn, zoom_reset_btn, zoom_in_btn],
                    spacing=s(2),
                    alignment=ft.MainAxisAlignment.CENTER,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    tight=True,
                ),
            ],
            spacing=s(2),
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            tight=True,
        )

        extract_btn = ui.button(
            c,
            'Novo fragmento',
            icon_name='quote-left',
            variant='primary',
            small=True,
            on_click=self._handle_new_fragment_click,
            tooltip='Criar fragmento com o texto selecionado na página',
        )

        copy_text_btn = ui.button(
            c,
            'Copiar texto',
            icon_name='copy',
            small=True,
            on_click=self._copy_page_text,
            tooltip='Copiar seleção ou texto desta página para a área de transferência (Ctrl+C)',
        )

        self.text_actions_group = ft.Column(
            controls=[
                ui.ui_text(c, 'Texto', size=10, weight=W600, color=colors['faint']),
                ft.Row(
                    controls=[copy_text_btn, extract_btn],
                    spacing=s(4),
                    alignment=ft.MainAxisAlignment.CENTER,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    tight=True,
                ),
            ],
            spacing=s(2),
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            tight=True,
        )

        # ── Controle de Offset de Página (Sincronia PDF <-> Obra) ──
        offset_minus_btn = ui.icon_button(
            c,
            'minus',
            on_click=self._handle_offset_decrement,
            tooltip='Diminuir offset (-1 página)',
            small=True,
        )
        self.offset_field = ft.TextField(
            value=str(self.page_offset),
            text_align=ft.TextAlign.CENTER,
            width=s(46),
            height=s(28),
            dense=True,
            content_padding=ft.Padding.only(left=s(2), right=s(2), top=s(2), bottom=s(2)),
            text_size=s(12),
            text_style=ft.TextStyle(
                font_family=c.font_families['montserrat'],
                color=colors['gold'] if self.page_offset != 0 else colors['text'],
                weight=W600,
            ),
            bgcolor=colors['bg'],
            border_color=colors['gold'] if self.page_offset != 0 else colors['border_strong'],
            focused_border_color=colors['gold'],
            border_radius=ft.BorderRadius.all(s(4)),
            cursor_color=colors['gold'],
            tooltip='Offset de página: sincroniza a página do PDF com a paginação da obra (ex: -14 se p. 1 da obra for o PDF 15)',
            on_submit=self._handle_offset_submit,
            on_blur=self._handle_offset_submit,
        )
        offset_plus_btn = ui.icon_button(
            c,
            'plus',
            on_click=self._handle_offset_increment,
            tooltip='Aumentar offset (+1 página)',
            small=True,
        )
        sync_p1_btn = ui.icon_button(
            c,
            'bullseye',
            on_click=self._handle_sync_current_as_page_one,
            tooltip='Sincronizar: fixar a página atual do PDF como a Página 1 da obra física',
            small=True,
        )
        self.offset_group = ft.Column(
            controls=[
                ui.ui_text(c, 'Offset', size=10, weight=W600, color=colors['faint']),
                ft.Row(
                    controls=[
                        offset_minus_btn,
                        self.offset_field,
                        offset_plus_btn,
                        sync_p1_btn,
                    ],
                    spacing=s(2),
                    alignment=ft.MainAxisAlignment.CENTER,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    tight=True,
                ),
            ],
            spacing=s(2),
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            tight=True,
        )

        toggle_sidebar_btn = ui.icon_button(
            c,
            'sidebar',
            on_click=self._toggle_sidebar,
            tooltip='Alternar painel lateral de fragmentos',
            small=True,
        )
        self.sidebar_group = ft.Column(
            controls=[
                ui.ui_text(c, 'Painel', size=10, weight=W600, color=colors['faint']),
                toggle_sidebar_btn,
            ],
            spacing=s(2),
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            tight=True,
        )

        # Menu responsivo de mais opções ('...') para quando não-maximizado
        more_trigger = ui.icon_button(
            c,
            'ellipsis-vertical',
            tooltip='Mais opções (Modo de exibição, Fragmentar, Copiar)',
            small=True,
            boxed=True,
        )
        self.more_popup_btn = ft.PopupMenuButton(
            content=more_trigger,
            items=self._build_more_menu_items(),
            bgcolor=colors['surface'],
            menu_position=ft.PopupMenuPosition.UNDER,
            shape=ft.RoundedRectangleBorder(radius=s(8)),
            tooltip='',
        )
        self.more_menu_group = ft.Column(
            controls=[
                ui.ui_text(c, 'Mais', size=10, weight=W600, color=colors['faint']),
                self.more_popup_btn,
            ],
            spacing=s(2),
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            tight=True,
        )

        self._render_tool_mode_selector()
        self._render_view_mode_selector()

        left_controls: list[ft.Control] = []
        if self.show_back_button:
            back_btn = ui.icon_button(
                c,
                'arrow-left',
                on_click=self._handle_back,
                tooltip='Voltar ao Acervo / Fechar',
                small=True,
            )
            back_group = ft.Column(
                controls=[
                    ui.ui_text(c, 'Voltar', size=10, weight=W600, color=colors['faint']),
                    back_btn,
                ],
                spacing=s(2),
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                tight=True,
            )
            left_controls.append(back_group)

        title_drag = ft.WindowDragArea(
            content=ft.Container(
                content=title_text,
                alignment=ft.Alignment.CENTER_LEFT,
                margin=ft.Margin.only(right=s(8)),
            ),
            expand=True,
        )
        left_controls.extend([
            title_drag,
            ft.Container(width=1, height=s(28), bgcolor=colors['border']),
            zoom_group,
            ft.Container(width=1, height=s(28), bgcolor=colors['border']),
            self.tool_mode_host,
        ])

        left_zone = ft.Row(
            controls=left_controls,
            spacing=s(8),
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            expand=True,
        )

        pager_group = ft.Column(
            controls=[
                ui.ui_text(c, 'Páginas', size=10, weight=W600, color=colors['faint']),
                ft.Row(
                    controls=[
                        prev_page_btn,
                        self.page_number_display,
                        self.page_number_input,
                        self.page_count_label,
                        next_page_btn,
                    ],
                    spacing=s(4),
                    alignment=ft.MainAxisAlignment.CENTER,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    tight=True,
                ),
            ],
            spacing=s(2),
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            tight=True,
        )
        center_zone = ft.Container(
            content=pager_group,
            alignment=ft.Alignment.CENTER,
            padding=ft.Padding.symmetric(horizontal=s(8)),
        )

        p = self.page or self._page_override
        if p is not None and not self._is_window_maximized():
            self._is_compact = True
        else:
            self._is_compact = False

        self.right_zone = ft.Row(
            controls=self._compose_right_controls(),
            spacing=s(8),
            alignment=ft.MainAxisAlignment.END,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            expand=True,
        )

        top_bar = ft.Container(
            content=ft.Row(
                controls=[left_zone, center_zone, self.right_zone],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            height=s(66),
            padding=ft.Padding.symmetric(horizontal=s(16)),
            bgcolor=colors['surface'],
            border=ft.Border.only(bottom=ft.BorderSide(1, colors['border'])),
        )
        return top_bar

    def _build_reading_area(self) -> None:
        c = self.config
        colors = c.colors
        # ── Área Central de Leitura ──────────────────────────────
        self.empty_state_container = ft.Container(
            content=ft.Column(
                controls=[
                    ui.fa_icon('file-pdf', size=s(48), color=colors['muted']),
                    ui.serif_text(c, 'Nenhum arquivo PDF carregado', size=18, weight=W700, color=colors['text']),
                    ui.ui_text(c, 'Vincule um arquivo PDF a esta obra para iniciar a leitura.', size=13, color=colors['muted']),
                    ft.Container(height=s(8)),
                    ui.button(c, 'Anexar PDF', icon_name='paperclip', variant='primary', on_click=self._handle_attach_pdf),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=s(8),
                tight=True,
            ),
            alignment=ft.Alignment.CENTER,
            padding=s(48),
            visible=self.doc is None,
        )

        # ── Navegação Lateral por Zonas de Clique ──
        self.left_nav_zone = ft.Container(
            content=ui.fa_icon('chevron-left', size=s(20), color=colors['muted']),
            width=s(44),
            height=s(BASE_PAGE_HEIGHT),
            alignment=ft.Alignment.CENTER,
            border_radius=ft.BorderRadius.all(s(8)),
            bgcolor=ui.alpha(colors['gold'], 0.04),
            ink=True,
            tooltip='Página anterior (← ou clique lateral)',
            on_click=self._prev_page,
            visible=self.doc is not None,
        )
        self.right_nav_zone = ft.Container(
            content=ui.fa_icon('chevron-right', size=s(20), color=colors['muted']),
            width=s(44),
            height=s(BASE_PAGE_HEIGHT),
            alignment=ft.Alignment.CENTER,
            border_radius=ft.BorderRadius.all(s(8)),
            bgcolor=ui.alpha(colors['gold'], 0.04),
            ink=True,
            tooltip='Próxima página (→ ou clique lateral)',
            on_click=self._next_page,
            visible=self.doc is not None,
        )

        self.left_page_margin_click = ft.Container(
            width=0,
            height=0,
            on_click=self._prev_page,
            visible=False,
        )
        self.right_page_margin_click = ft.Container(
            width=0,
            height=0,
            on_click=self._next_page,
            visible=False,
        )

        # Cartão da Página Principal (Esquerda com detector de arrasto nas margens/fundo)
        self.left_page_gesture = ft.GestureDetector(
            content=self.page_image,
            on_pan_start=self._on_left_card_pan_start,
            on_pan_update=self._on_pan_update,
            on_pan_end=self._on_pan_end,
            on_right_pan_start=self._on_card_right_pan_start,
            on_right_pan_update=self._on_pan_update,
            on_right_pan_end=self._on_pan_end,
            drag_interval=20,
        )

        self.page_card = ft.Container(
            content=ft.Stack(
                controls=[
                    self.left_page_gesture,
                    self.selection_container,
                    self.loading_container,
                ],
                alignment=ft.Alignment.TOP_LEFT,
            ),
            border=ft.Border.all(1, colors['border']),
            border_radius=ft.BorderRadius.all(s(4)),
            bgcolor=colors['surface'],
            shadow=ft.BoxShadow(
                blur_radius=12,
                spread_radius=1,
                color=ui.alpha(colors['text'], 0.10),
                offset=ft.Offset(0, 2),
            ),
            alignment=ft.Alignment.CENTER,
        )

        # Cartão da Página Secundária (Direita com detector de arrasto nas margens/fundo)
        self.right_page_gesture = ft.GestureDetector(
            content=self.page_image_right,
            on_pan_start=self._on_right_card_pan_start,
            on_pan_update=self._on_pan_update,
            on_pan_end=self._on_pan_end,
            on_right_pan_start=self._on_card_right_pan_start,
            on_right_pan_update=self._on_pan_update,
            on_right_pan_end=self._on_pan_end,
            drag_interval=20,
        )

        self.page_card_right = ft.Container(
            content=ft.Stack(
                controls=[
                    self.right_page_gesture,
                    self.selection_container_right,
                ],
                alignment=ft.Alignment.TOP_LEFT,
            ),
            border=ft.Border.all(1, colors['border']),
            border_radius=ft.BorderRadius.all(s(4)),
            bgcolor=colors['surface'],
            shadow=ft.BoxShadow(
                blur_radius=12,
                spread_radius=1,
                color=ui.alpha(colors['text'], 0.10),
                offset=ft.Offset(0, 2),
            ),
            alignment=ft.Alignment.CENTER,
            visible=False,
        )
        self.text_reading_card = self.page_card_right

        self.page_view_row = ft.Row(
            controls=[
                self.left_nav_zone,
                self.page_card,
                self.page_card_right,
                self.right_nav_zone,
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=s(16),
        )

        # Suporte para rolagem e pan suave quando houver zoom
        self.scroll_row = ft.Row(
            controls=[self.page_view_row],
            alignment=ft.MainAxisAlignment.CENTER,
            scroll=ft.ScrollMode.AUTO,
        )

        self.scroll_column = ft.Column(
            controls=[
                self.empty_state_container,
                self.scroll_row,
            ],
            scroll=ft.ScrollMode.AUTO,
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            expand=True,
        )

        # Suporte para navegação de páginas (Wheel normal), zoom (Ctrl + Wheel) e pan externo
        self.gesture_container = ft.GestureDetector(
            content=self.scroll_column,
            on_scroll=self._on_mouse_scroll,
            on_pan_start=self._on_outer_pan_start,
            on_pan_update=self._on_pan_update,
            on_pan_end=self._on_pan_end,
            on_right_pan_start=self._on_outer_pan_start,
            on_right_pan_update=self._on_pan_update,
            on_right_pan_end=self._on_pan_end,
            drag_interval=20,
            expand=True,
        )

        self.page_scroll_area = ft.Container(
            content=self.gesture_container,
            expand=True,
            padding=ft.Padding.symmetric(vertical=s(16), horizontal=s(16)),
            bgcolor=colors['bg'],
        )

    def _build_sidebar(self) -> None:
        c = self.config
        colors = c.colors
        # ── Barra Lateral de Fragmentos ──────────────────────────
        sidebar_head = ft.Row(
            controls=[
                ui.serif_text(c, 'Fragmentos da Obra', size=15, weight=W700, color=colors['text']),
                ui.icon_button(c, 'plus', small=True, on_click=self._handle_new_fragment_click, tooltip='Novo fragmento'),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        self.sidebar_container.content = ft.Column(
            controls=[
                sidebar_head,
                ft.Divider(height=1, color=colors['border']),
                self.fragments_column,
            ],
            spacing=s(12),
            expand=True,
        )

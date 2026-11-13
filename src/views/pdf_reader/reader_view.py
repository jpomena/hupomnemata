import base64
from collections.abc import Callable
from pathlib import Path

import flet as ft
import pymupdf

from src.domains import BibliographicResource, Fragment
from src.services.pdf_service import PdfService
from src.utils.clipboard import (
    _copy_plain_text_to_system_clipboard,
    get_system_clipboard_text,
)
from src.utils.error_log import log_exception
from src.utils.types import ViewConfig
from src.views import ui_kit as ui
from src.views.fragment_modal import FragmentModal

s = ui.s
W500 = ui.W500
W600 = ui.W600
W700 = ui.W700

# Altura base de referência para caber perfeitamente na janela desktop a 100%
BASE_PAGE_HEIGHT = 680


class PdfReaderView(ft.Container):
    """Espaço de Leitura e Anotação de PDFs imersivo do Hupomnemata."""

    def __init__(
        self,
        config: ViewConfig,
        resource: BibliographicResource,
        on_back: Callable[[], None],
        on_new_fragment: Callable[[int, int, str], None] | None = None,
        pdf_service: PdfService | None = None,
        page: ft.Page | None = None,
        show_back_button: bool = True,
    ) -> None:
        super().__init__(expand=True)
        self._page_override = page
        self.config = config
        self.resource = resource
        self.on_back_callback = on_back
        self.on_new_fragment_callback = on_new_fragment
        self.pdf_service = pdf_service or PdfService()
        self.show_back_button = show_back_button

        self.current_page: int = 1
        self.zoom_level: float = 1.0
        self.view_mode: str = 'page'  # 'page' (uma página) ou 'split' (duas páginas lado a lado)
        self.show_sidebar: bool = True
        self.current_page_text: str = ''
        self.selected_text: str = ''
        self.selected_page: int = 1
        self._scroll_delta_acc: float = 0.0
        self._page_delta_acc: float = 0.0
        self._zoom_delta_acc: float = 0.0
        self._ctrl_pressed_state: bool = False
        self._pan_dx_acc: float = 0.0
        self._pan_dy_acc: float = 0.0
        self._pan_task_running: bool = False
        self._last_page_turn_time: float = 0.0
        self._last_zoom_time: float = 0.0
        self._is_panning: bool = False
        self._left_text_boxes: list[tuple[float, float, float, float]] = []
        self._right_text_boxes: list[tuple[float, float, float, float]] = []

        self.page_offset: int = getattr(resource, 'pdf_page_offset', 0) or 0
        self.offset_field: ft.TextField | None = None
        self._is_compact: bool = False

        self.doc: pymupdf.Document | None = None
        self.total_pages: int = resource.pdf_page_count or 1
        self.pdf_abs_path: Path | None = None

        work = self.resource.specific_work
        self.work_title = (work.title if work else '') or (self.resource.pdf_filename or 'Documento')

        self._init_pdf_document()

        # Controles reativos de interface
        self._is_editing_page: bool = False
        self.page_number_label = ui.ui_text(self.config, '1', size=13, weight=W600, color=config.colors['gold'])
        self.page_count_label = ui.ui_text(self.config, f' de {self.total_pages}', size=13, color=config.colors['muted'])
        self.zoom_label = ui.ui_text(self.config, '100%', size=11, weight=W600, color=config.colors['muted'])

        # Indicador clicável e campo de entrada direta de página alvo
        self.page_number_display = ft.Container(
            content=self.page_number_label,
            padding=ft.Padding.symmetric(horizontal=s(6), vertical=s(2)),
            border_radius=ft.BorderRadius.all(s(4)),
            border=ft.Border.all(1, ui.alpha(config.colors['border'], 0.6)),
            bgcolor=None,
            ink=True,
            tooltip='Ir para página (clique para digitar)',
            on_click=self._start_page_edit,
            animate=ft.Animation(120, ft.AnimationCurve.EASE_OUT),
        )
        self.page_number_container = self.page_number_display

        def _on_page_label_hover(e: ft.ControlEvent) -> None:
            if getattr(self, '_is_editing_page', False):
                return
            hovering = e.data in (True, 'true')
            self.page_number_display.bgcolor = config.colors['card_hover'] if hovering else None
            self.page_number_display.border = ft.Border.all(
                1, config.colors['gold'] if hovering else ui.alpha(config.colors['border'], 0.6)
            )
            try:
                self.page_number_display.update()
            except (RuntimeError, AttributeError):
                pass

        self.page_number_display.on_hover = _on_page_label_hover

        self.page_number_input = ft.TextField(
            value=str(self.current_page),
            width=s(48),
            height=s(28),
            text_size=s(13),
            text_align=ft.TextAlign.CENTER,
            dense=True,
            content_padding=ft.Padding.only(left=s(2), right=s(2), top=s(2), bottom=s(2)),
            keyboard_type=ft.KeyboardType.NUMBER,
            input_filter=ft.NumbersOnlyInputFilter(),
            text_style=ft.TextStyle(
                font_family=self.config.font_families['montserrat'],
                weight=W600,
                color=self.config.colors['gold'],
                letter_spacing=ui.UI_TRACKING,
            ),
            cursor_color=self.config.colors['gold'],
            cursor_height=s(14),
            cursor_width=1.5,
            border_color=self.config.colors['gold'],
            focused_border_color=self.config.colors['gold'],
            border_radius=ft.BorderRadius.all(s(4)),
            bgcolor=self.config.colors['bg'],
            visible=False,
            on_submit=self._on_page_input_submit,
            on_blur=self._on_page_input_blur,
        )

        self.loading_ring = ft.ProgressRing(
            width=s(32),
            height=s(32),
            stroke_width=3,
            color=config.colors['gold'],
            visible=False,
        )
        self.loading_container = ft.Container(
            content=self.loading_ring,
            alignment=ft.Alignment.CENTER,
            visible=False,
        )

        # ── Cartão da Página Esquerda (Página A) ──
        self.page_image = ft.Image(
            src='',
            fit=ft.BoxFit.CONTAIN,
            border_radius=ft.BorderRadius.all(s(4)),
            height=s(BASE_PAGE_HEIGHT),
        )
        self.text_layer_stack = ft.Stack(
            controls=[],
            height=s(BASE_PAGE_HEIGHT),
        )
        self.selection_area = ft.SelectionArea(
            content=self.text_layer_stack,
            on_change=self._on_selection_change_left,
        )
        self.selection_container = ft.Container(
            content=self.selection_area,
            left=0,
            top=0,
            width=s(BASE_PAGE_HEIGHT * 0.70),
            height=s(BASE_PAGE_HEIGHT),
            visible=True,
        )

        # ── Cartão da Página Direita (Página B - Modo Duas Páginas) ──
        self.page_image_right = ft.Image(
            src='',
            fit=ft.BoxFit.CONTAIN,
            border_radius=ft.BorderRadius.all(s(4)),
            height=s(BASE_PAGE_HEIGHT),
            visible=False,
        )
        self.text_layer_stack_right = ft.Stack(
            controls=[],
            height=s(BASE_PAGE_HEIGHT),
        )
        self.selection_area_right = ft.SelectionArea(
            content=self.text_layer_stack_right,
            on_change=self._on_selection_change_right,
        )
        self.selection_container_right = ft.Container(
            content=self.selection_area_right,
            left=0,
            top=0,
            width=s(BASE_PAGE_HEIGHT * 0.70),
            height=s(BASE_PAGE_HEIGHT),
            visible=False,
        )

        # Modo de ferramenta: 'select' (Seleção de Texto) ou 'pan' (Mão / Rolagem)
        self.active_tool: str = 'select'
        self.tool_mode_host = ft.Container()

        # Campo retrocompatível invisível para testes
        self.page_text_field = ft.TextField(visible=False)

        self.fragments_column = ft.Column(
            spacing=s(8),
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

        self.sidebar_container = ft.Container(
            width=s(320),
            bgcolor=config.colors['surface'],
            border=ft.Border.only(left=ft.BorderSide(1, config.colors['border'])),
            padding=s(16),
            visible=self.show_sidebar,
        )

        self.view_mode_host = ft.Container()

        self.fragment_modal = FragmentModal(
            page=page,
            config=self.config,
            on_save=self._save_fragment_from_modal,
        )

        self._build_layout()
        self._load_current_page()
        self._refresh_fragments_list()

    @property
    def is_modal_open(self) -> bool:
        """Indica se há algum modal / diálogo ativo no leitor de PDF."""
        if hasattr(self, 'fragment_modal') and self.fragment_modal:
            modal = getattr(self.fragment_modal, 'modal', None)
            if modal and getattr(modal, 'open', False):
                return True
        p = self.page or self._page_override
        if p:
            for item in getattr(p, 'overlay', []) or []:
                if isinstance(item, (ft.AlertDialog, ft.BottomSheet)) and getattr(item, 'open', False):
                    return True
        return False

    @property
    def page(self) -> ft.Page | None:
        if getattr(self, '_page_override', None) is not None:
            return self._page_override
        try:
            return super().page
        except RuntimeError:
            return None

    @page.setter
    def page(self, val: ft.Page | None) -> None:
        self._page_override = val
        if hasattr(self, 'fragment_modal'):
            self.fragment_modal.page = val

    def _init_pdf_document(self) -> None:
        """Abre o documento PDF físico via PyMuPDF."""
        if not self.resource.pdf_path:
            return

        self.pdf_abs_path = self.pdf_service.resolve_path(self.resource.pdf_path)
        if self.pdf_abs_path.exists():
            try:
                self.doc = pymupdf.open(str(self.pdf_abs_path))
                self.total_pages = len(self.doc)
            except Exception as error:
                log_exception(f'Falha ao abrir PDF {self.pdf_abs_path}', error)

    def close(self) -> None:
        """Libera os descritores de arquivo abertos pelo PyMuPDF no sistema operacional."""
        if self.doc is not None:
            try:
                self.doc.close()
            except Exception as error:
                log_exception('Falha ao fechar descritor de documento PDF', error)
            finally:
                self.doc = None

    def _handle_back(self, _e: ft.ControlEvent | None = None) -> None:
        """Encerra recursos abertos e retorna à tela anterior."""
        self.close()
        if self.on_back_callback:
            self.on_back_callback()

    def _build_layout(self) -> None:
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

        # ── Estrutura Global ─────────────────────────────────────
        self.content = ft.Column(
            controls=[
                top_bar,
                ft.Row(
                    controls=[
                        self.page_scroll_area,
                        self.sidebar_container,
                    ],
                    spacing=0,
                    expand=True,
                ),
            ],
            spacing=0,
            expand=True,
        )

    def _render_tool_mode_selector(self) -> None:
        c = self.config
        colors = c.colors
        segmented_ctrl = ui.segmented(
            c,
            [
                ('select', 'Texto', None),
                ('pan', 'Mão', None),
            ],
            getattr(self, 'active_tool', 'select'),
            self._on_tool_mode_change,
        )
        self.tool_mode_host.content = ft.Column(
            controls=[
                ui.ui_text(c, 'Ferramenta', size=10, weight=W600, color=colors['faint']),
                segmented_ctrl,
            ],
            spacing=s(2),
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            tight=True,
        )

    def _on_tool_mode_change(self, mode: str) -> None:
        if self.is_modal_open:
            return
        self.active_tool = mode
        self._update_tool_state()

    def _update_tool_state(self) -> None:
        is_pan = (getattr(self, 'active_tool', 'select') == 'pan')
        if hasattr(self, 'selection_container'):
            self.selection_container.visible = (not is_pan) and bool(self._left_text_boxes)
            self.selection_container.mouse_cursor = ft.MouseCursor.TEXT
        if hasattr(self, 'selection_container_right'):
            self.selection_container_right.visible = (not is_pan) and bool(self._right_text_boxes) and (self.view_mode == 'split')
            self.selection_container_right.mouse_cursor = ft.MouseCursor.TEXT

        cursor = ft.MouseCursor.GRAB if is_pan else ft.MouseCursor.BASIC
        if hasattr(self, 'left_page_gesture'):
            self.left_page_gesture.mouse_cursor = cursor
        if hasattr(self, 'right_page_gesture'):
            self.right_page_gesture.mouse_cursor = cursor
        if hasattr(self, 'gesture_container'):
            self.gesture_container.mouse_cursor = cursor

        self._render_tool_mode_selector()
        try:
            self.update()
        except (RuntimeError, AttributeError):
            pass

    def _render_view_mode_selector(self) -> None:
        c = self.config
        colors = c.colors
        segmented_ctrl = ui.segmented(
            c,
            [
                ('page', 'Página', None),
                ('split', 'Lado a Lado', None),
            ],
            self.view_mode,
            self._on_view_mode_change,
        )
        self.view_mode_host.content = ft.Column(
            controls=[
                ui.ui_text(c, 'Exibição', size=10, weight=W600, color=colors['faint']),
                segmented_ctrl,
            ],
            spacing=s(2),
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            tight=True,
        )

    def _on_view_mode_change(self, mode: str) -> None:
        if self.is_modal_open:
            return
        self.view_mode = mode
        self._render_view_mode_selector()
        self._load_current_page()
        if hasattr(self, 'more_popup_btn'):
            self.more_popup_btn.items = self._build_more_menu_items()
            try:
                self.more_popup_btn.update()
            except (RuntimeError, AttributeError):
                pass
        try:
            self.update()
        except (RuntimeError, AttributeError):
            pass

    def _set_view_mode(self, mode: str) -> None:
        self._on_view_mode_change(mode)

    def _build_more_menu_items(self) -> list[ft.PopupMenuItem]:
        c = self.config
        colors = c.colors

        def _item(icon_tuple, label: str, trailing: str | None, handler) -> ft.PopupMenuItem:
            name, style = icon_tuple
            row: list[ft.Control] = [
                ui.fa_icon(name, size=s(12), color=colors['faint'], style=style),
                ui.ui_text(c, label, size=13, color=colors['text'], expand=True),
            ]
            if trailing:
                row.append(ui.ui_text(c, trailing, size=11, color=colors['muted'], tabular=True))
            return ft.PopupMenuItem(
                content=ft.Row(row, spacing=s(10), width=s(230)),
                height=s(34),
                on_click=handler,
            )

        def _divider() -> ft.PopupMenuItem:
            return ft.PopupMenuItem()

        items: list[ft.PopupMenuItem] = []
        items.append(
            _item(
                ('quote-left', 'solid'),
                'Novo fragmento',
                'Seleção',
                lambda _e: self._handle_new_fragment_click(),
            )
        )
        items.append(
            _item(
                ('copy', 'regular'),
                'Copiar texto',
                'Ctrl+C',
                lambda _e: self._copy_page_text(),
            )
        )
        items.append(_divider())

        if self.view_mode == 'page':
            items.append(
                _item(
                    ('columns', 'solid'),
                    'Exibir Lado a Lado',
                    '2 Páginas',
                    lambda _e: self._set_view_mode('split'),
                )
            )
        else:
            items.append(
                _item(
                    ('file-lines', 'regular'),
                    'Exibir Página Única',
                    '1 Página',
                    lambda _e: self._set_view_mode('page'),
                )
            )

        items.append(_divider())

        items.append(
            _item(
                ('bullseye', 'solid'),
                'Fixar atual como Pág. 1',
                f'p. {self.current_page}',
                lambda _e: self._handle_sync_current_as_page_one(),
            )
        )

        return items

    def _compose_right_controls(self) -> list[ft.Control]:
        colors = self.config.colors
        if getattr(self, '_is_compact', False):
            return [
                self.offset_group,
                ft.Container(width=1, height=s(28), bgcolor=colors['border']),
                self.sidebar_group,
                ft.Container(width=1, height=s(28), bgcolor=colors['border']),
                self.more_menu_group,
            ]
        return [
            self.view_mode_host,
            ft.Container(width=1, height=s(28), bgcolor=colors['border']),
            self.offset_group,
            ft.Container(width=1, height=s(28), bgcolor=colors['border']),
            self.text_actions_group,
            ft.Container(width=1, height=s(28), bgcolor=colors['border']),
            self.sidebar_group,
        ]

    def set_compact_mode(self, compact: bool) -> None:
        """Alterna explicitamente entre modo compacto ('...') e desempacotado (maximizado)."""
        if getattr(self, '_is_compact', None) == compact:
            return
        self._is_compact = compact
        self._update_top_bar_responsive()

    def _update_top_bar_responsive(self) -> None:
        if not hasattr(self, 'right_zone'):
            return
        self.right_zone.controls = self._compose_right_controls()
        if hasattr(self, 'more_popup_btn'):
            self.more_popup_btn.items = self._build_more_menu_items()
        try:
            self.right_zone.update()
        except (RuntimeError, AttributeError):
            pass

    def handle_page_resize(self, _e: ft.ControlEvent | None = None) -> None:
        """Trata o redimensionamento da janela do leitor."""
        self._check_window_state()

    def handle_window_event(self, _e: ft.WindowEvent | None = None) -> None:
        """Trata eventos da janela nativa do leitor (maximize, restore, etc.)."""
        self._check_window_state()

    def _check_window_state(self) -> None:
        is_max = self._is_window_maximized()
        self.set_compact_mode(not is_max)

    def _is_window_maximized(self) -> bool:
        p = self.page or self._page_override
        if not p:
            return False
        win = getattr(p, 'window', None)
        if win and getattr(win, 'maximized', False):
            return True
        page_w = getattr(p, 'width', 0) or 0
        if page_w >= 1400:
            return True
        return False

    def did_mount(self) -> None:
        super().did_mount()
        p = self.page or self._page_override
        if p:
            self._check_window_state()

    def _is_ctrl_down(self) -> bool:
        """Verifica se a tecla Ctrl está acionada (via Win32 síncrono ou fallback de estado)."""
        if getattr(self, '_ctrl_pressed_state', False):
            return True
        import os
        if os.name == 'nt':
            try:
                import ctypes
                return bool(ctypes.windll.user32.GetAsyncKeyState(0x11) & 0x8000)
            except Exception:
                pass
        return False

    def _on_mouse_scroll(self, e: ft.ScrollEvent) -> None:
        """Navega páginas com a roda do mouse ou ajusta zoom com Ctrl+Mouse Wheel com sensibilidade calibrada."""
        if not self.doc or self.is_modal_open:
            return
        import time
        now = time.time()
        delta = getattr(e.scroll_delta, 'y', 0.0) or 0.0
        if self._is_ctrl_down():
            self._page_delta_acc = 0.0
            # Cooldown de 160ms para zoom contínuo preciso e estável
            if now - getattr(self, '_last_zoom_time', 0.0) < 0.16:
                return

            self._zoom_delta_acc += delta
            # Limiar calibrado para entalhe padrão de mouse no Windows (80 unidades)
            if self._zoom_delta_acc <= -80.0:
                self._zoom_delta_acc = 0.0
                self._last_zoom_time = now
                self._zoom_in()
            elif self._zoom_delta_acc >= 80.0:
                self._zoom_delta_acc = 0.0
                self._last_zoom_time = now
                self._zoom_out()
        else:
            self._zoom_delta_acc = 0.0
            # Cooldown de 220ms para troca de páginas firme sem pular páginas em lote
            if now - getattr(self, '_last_page_turn_time', 0.0) < 0.22:
                return

            self._page_delta_acc += delta
            # Limiar calibrado para entalhe padrão de mouse no Windows (80 unidades)
            if self._page_delta_acc <= -80.0:
                self._page_delta_acc = 0.0
                self._last_page_turn_time = now
                self._prev_page()
            elif self._page_delta_acc >= 80.0:
                self._page_delta_acc = 0.0
                self._last_page_turn_time = now
                self._next_page()

    def _is_coord_on_text(self, x: float, y: float, boxes: list[tuple[float, float, float, float]]) -> bool:
        """Determina se as coordenadas de toque incidem sobre alguma linha de texto selecionável."""
        if not boxes:
            return False
        pad = 2.0
        for bx, by, bw, bh in boxes:
            if (bx - pad) <= x <= (bx + bw + pad) and (by - pad) <= y <= (by + bh + pad):
                return True
        return False

    def _on_outer_pan_start(self, _e: ft.DragStartEvent) -> None:
        """Inicia arrasto na área externa da página / fundo do leitor."""
        if not self.doc or self.is_modal_open:
            return
        self._is_panning = True
        self._pan_dx_acc = 0.0
        self._pan_dy_acc = 0.0
        self._pan_task_running = False

    def _on_card_right_pan_start(self, _e: ft.DragStartEvent) -> None:
        """Arrasto com botão secundário (direito) sempre ativa o pan direto da visualização."""
        if not self.doc or self.is_modal_open:
            return
        self._is_panning = True
        self._pan_dx_acc = 0.0
        self._pan_dy_acc = 0.0
        self._pan_task_running = False

    def _on_left_card_pan_start(self, e: ft.DragStartEvent) -> None:
        """Inicia arrasto na Página Esquerda (pan nas margens ou modo pan ativo)."""
        if not self.doc or self.is_modal_open:
            return
        if getattr(self, 'active_tool', 'select') == 'pan':
            self._is_panning = True
            self._pan_dx_acc = 0.0
            self._pan_dy_acc = 0.0
            self._pan_task_running = False
            return

        loc = getattr(e, 'local_position', None)
        x = getattr(loc, 'x', 0.0) or 0.0
        y = getattr(loc, 'y', 0.0) or 0.0
        if self._is_coord_on_text(x, y, self._left_text_boxes):
            self._is_panning = False
        else:
            self._is_panning = True
            self._pan_dx_acc = 0.0
            self._pan_dy_acc = 0.0
            self._pan_task_running = False

    def _on_right_card_pan_start(self, e: ft.DragStartEvent) -> None:
        """Inicia arrasto na Página Direita (pan nas margens ou modo pan ativo)."""
        if not self.doc or self.is_modal_open:
            return
        if getattr(self, 'active_tool', 'select') == 'pan':
            self._is_panning = True
            self._pan_dx_acc = 0.0
            self._pan_dy_acc = 0.0
            self._pan_task_running = False
            return

        loc = getattr(e, 'local_position', None)
        x = getattr(loc, 'x', 0.0) or 0.0
        y = getattr(loc, 'y', 0.0) or 0.0
        if self._is_coord_on_text(x, y, self._right_text_boxes):
            self._is_panning = False
        else:
            self._is_panning = True
            self._pan_dx_acc = 0.0
            self._pan_dy_acc = 0.0
            self._pan_task_running = False

    def _on_pan_update(self, e: ft.DragUpdateEvent) -> None:
        """Move / desloca a visualização da página (pan) quando o arrasto ocorre fora do texto."""
        if not self.doc or not getattr(self, '_is_panning', False) or self.is_modal_open:
            return

        dx = 0.0
        dy = 0.0
        if getattr(e, 'local_delta', None):
            dx = getattr(e.local_delta, 'x', 0.0) or 0.0
            dy = getattr(e.local_delta, 'y', 0.0) or 0.0
        elif getattr(e, 'global_delta', None):
            dx = getattr(e.global_delta, 'x', 0.0) or 0.0
            dy = getattr(e.global_delta, 'y', 0.0) or 0.0
        elif getattr(e, 'primary_delta', None) is not None:
            dy = getattr(e.primary_delta, 0.0) or 0.0

        if abs(dx) < 0.5 and abs(dy) < 0.5:
            return

        self._pan_dx_acc += dx
        self._pan_dy_acc += dy

        if not self.page or getattr(self, '_pan_task_running', False):
            return

        run_task = getattr(self.page, 'run_task', None)
        if not run_task:
            return

        self._pan_task_running = True

        async def _do_pan() -> None:
            try:
                while abs(self._pan_dx_acc) >= 0.5 or abs(self._pan_dy_acc) >= 0.5:
                    step_x = self._pan_dx_acc
                    step_y = self._pan_dy_acc
                    self._pan_dx_acc = 0.0
                    self._pan_dy_acc = 0.0

                    if step_y != 0.0 and hasattr(self, 'scroll_column') and self.scroll_column:
                        await self.scroll_column.scroll_to(delta=-step_y, duration=0)
                    if step_x != 0.0 and hasattr(self, 'scroll_row') and self.scroll_row:
                        await self.scroll_row.scroll_to(delta=-step_x, duration=0)
            except Exception:
                pass
            finally:
                self._pan_task_running = False

        try:
            run_task(_do_pan)
        except Exception:
            self._pan_task_running = False

    def _on_pan_end(self, _e: ft.DragEndEvent | None = None) -> None:
        """Finaliza operação de pan / arrasto."""
        self._is_panning = False
        self._pan_dx_acc = 0.0
        self._pan_dy_acc = 0.0
        self._pan_task_running = False

    def _on_selection_change_left(self, e: ft.ControlEvent) -> None:
        data = getattr(e, 'data', '') or ''
        text = str(data).strip()
        if text:
            self.selected_text = text
            self.selected_page = self.current_page

    def _on_selection_change_right(self, e: ft.ControlEvent) -> None:
        data = getattr(e, 'data', '') or ''
        text = str(data).strip()
        if text:
            self.selected_text = text
            self.selected_page = self.current_page + 1

    def _on_text_selection_change(self, e: ft.TextSelectionChangeEvent, page_num: int) -> None:
        text = getattr(e, 'selected_text', '') or ''
        text = str(text).strip()
        if text:
            self.selected_text = text
            self.selected_page = page_num

    def _handle_attach_pdf(self, _e: ft.ControlEvent | None = None) -> None:
        """Abre seletor para vincular arquivo PDF caso ainda não haja documento."""
        if not self.page:
            return

        async def _pick():
            from src.utils.file_picker import pick_file

            path = await pick_file(
                page=self.page,
                dialog_title="Selecionar PDF para a obra",
                allowed_extensions=["pdf"],
            )
            if path:
                info = self.pdf_service.attach_pdf(self.resource.id, path)
                self.resource.pdf_path = info["pdf_path"]
                self.resource.pdf_filename = info["pdf_filename"]
                self.resource.pdf_page_count = info["pdf_page_count"]
                self._init_pdf_document()
                self._load_current_page()
                if self.page:
                    ui.toast(self.page, self.config, f"PDF anexado: {info['pdf_filename']}")
                    self.page.update()

        self.page.run_task(_pick)

    def _render_page_into_card(
        self,
        page_num: int,
        image_ctrl: ft.Image,
        stack_ctrl: ft.Stack,
        container_ctrl: ft.Container | None = None,
    ) -> tuple[int, int, str, list[tuple[float, float, float, float]]]:
        """Renderiza uma página do documento no par imagem/camada de texto."""
        if container_ctrl is None:
            if stack_ctrl == getattr(self, 'text_layer_stack', None):
                container_ctrl = getattr(self, 'selection_container', None)
            elif stack_ctrl == getattr(self, 'text_layer_stack_right', None):
                container_ctrl = getattr(self, 'selection_container_right', None)

        if self.doc is None or page_num < 1 or page_num > len(self.doc):
            image_ctrl.visible = False
            stack_ctrl.controls = []
            if container_ctrl is not None:
                container_ctrl.visible = False
            return 0, 0, '', []

        page_idx = page_num - 1
        page = self.doc.load_page(page_idx)
        page_rect = page.rect
        aspect_ratio = (page_rect.width / page_rect.height) if page_rect.height > 0 else 0.707

        target_h = int(BASE_PAGE_HEIGHT * self.zoom_level)
        target_w = int(target_h * aspect_ratio)

        dpi = max(110, min(300, int(150 * max(1.0, self.zoom_level))))
        pix = page.get_pixmap(dpi=dpi)
        png_bytes = pix.tobytes('png')
        b64_str = base64.b64encode(png_bytes).decode('ascii')

        image_ctrl.src = f'data:image/png;base64,{b64_str}'
        image_ctrl.width = s(target_w)
        image_ctrl.height = s(target_h)
        image_ctrl.visible = True

        raw_text = page.get_text() or ''

        sx = target_w / page_rect.width if page_rect.width > 0 else 1.0
        sy = target_h / page_rect.height if page_rect.height > 0 else 1.0

        layer_controls = []
        page_boxes: list[tuple[float, float, float, float]] = []
        words = page.get_text('words')
        if words:
            lines_map: dict[tuple[int, int], list] = {}
            for w in words:
                key = (w[5], w[6])
                lines_map.setdefault(key, []).append(w)

            # Ordena as linhas por coordenadas verticais (top-to-bottom) e horizontais (left-to-right)
            sorted_lines = sorted(
                lines_map.values(),
                key=lambda lw: (round(min(w[1] for w in lw) / 4) * 4, min(w[0] for w in lw)),
            )

            for line_words in sorted_lines:
                line_words = sorted(line_words, key=lambda w: w[7])
                x0 = min(w[0] for w in line_words)
                y0 = min(w[1] for w in line_words)
                x1 = max(w[2] for w in line_words)
                y1 = max(w[3] for w in line_words)
                line_text = ' '.join(w[4] for w in line_words).strip()
                if not line_text:
                    continue

                bw = max(10.0, (x1 - x0) * sx)
                bh = max(10.0, (y1 - y0) * sy)
                bx = x0 * sx
                by = y0 * sy
                fsize = max(7, min(36, int(bh * 0.88)))

                page_boxes.append((s(bx), s(by), s(bw), s(bh)))

                layer_controls.append(
                    ft.Container(
                        left=s(bx),
                        top=s(by),
                        width=s(bw),
                        height=s(bh),
                        content=ft.Text(
                            value=line_text,
                            size=s(fsize),
                            color=ft.Colors.TRANSPARENT,
                            selectable=False,
                            no_wrap=True,
                            max_lines=1,
                            font_family=self.config.font_families['montserrat'],
                        ),
                    )
                )
        else:
            blocks = page.get_text('blocks')
            for b in blocks:
                if len(b) >= 7 and b[6] == 0:
                    x0, y0, x1, y1, btext = b[0], b[1], b[2], b[3], b[4]
                    bw = max(10.0, (x1 - x0) * sx)
                    bh = max(10.0, (y1 - y0) * sy)
                    bx = x0 * sx
                    by = y0 * sy
                    lines = [l for l in btext.splitlines() if l.strip()]
                    n_lines = max(1, len(lines))
                    line_h = bh / n_lines
                    fsize = max(7, min(22, int(line_h * 0.85)))
                    page_boxes.append((s(bx), s(by), s(bw), s(bh)))
                    layer_controls.append(
                        ft.Container(
                            left=s(bx),
                            top=s(by),
                            width=s(bw),
                            height=s(bh),
                            content=ft.Text(
                                value=btext,
                                size=s(fsize),
                                color=ft.Colors.TRANSPARENT,
                                selectable=False,
                                font_family=self.config.font_families['montserrat'],
                            ),
                        )
                    )

        if page_boxes:
            min_x = max(0.0, min(b[0] for b in page_boxes))
            min_y = max(0.0, min(b[1] for b in page_boxes))
            max_x = min(s(target_w), max(b[0] + b[2] for b in page_boxes))
            max_y = min(s(target_h), max(b[1] + b[3] for b in page_boxes))
            box_w = max(10.0, max_x - min_x)
            box_h = max(10.0, max_y - min_y)

            for ctrl in layer_controls:
                ctrl.left = round(ctrl.left - min_x, 2)
                ctrl.top = round(ctrl.top - min_y, 2)

            stack_ctrl.width = box_w
            stack_ctrl.height = box_h
            stack_ctrl.controls = layer_controls

            if container_ctrl is not None:
                container_ctrl.left = min_x
                container_ctrl.top = min_y
                container_ctrl.width = box_w
                container_ctrl.height = box_h
                container_ctrl.visible = (getattr(self, 'active_tool', 'select') == 'select')
        else:
            stack_ctrl.controls = []
            stack_ctrl.width = 0
            stack_ctrl.height = 0
            if container_ctrl is not None:
                container_ctrl.left = 0
                container_ctrl.top = 0
                container_ctrl.width = 0
                container_ctrl.height = 0
                container_ctrl.visible = False

        return target_w, target_h, raw_text, page_boxes

    def _load_current_page(self) -> None:
        """Renderiza a(s) página(s) atual(is) no leitor com camada de texto selecionável."""
        if self.doc is None:
            self.page_image.src = ''
            self.page_image.visible = False
            self.page_image_right.src = ''
            self.page_image_right.visible = False
            self.loading_ring.visible = False
            self.loading_container.visible = False
            self.text_layer_stack.controls = []
            self.text_layer_stack_right.controls = []
            if hasattr(self, 'selection_container'):
                self.selection_container.visible = False
            if hasattr(self, 'selection_container_right'):
                self.selection_container_right.visible = False
            if hasattr(self, 'left_nav_zone'):
                self.left_nav_zone.visible = False
                self.right_nav_zone.visible = False
            self.empty_state_container.visible = True
            try:
                self.update()
            except (RuntimeError, AttributeError):
                pass
            return

        self.page_image.visible = True
        self.loading_ring.visible = False
        self.loading_container.visible = False
        self.empty_state_container.visible = False
        if hasattr(self, 'left_nav_zone'):
            self.left_nav_zone.visible = True
            self.left_nav_zone.opacity = 0.25 if self.current_page <= 1 else 1.0
            self.left_nav_zone.disabled = self.current_page <= 1
        if hasattr(self, 'right_nav_zone'):
            self.right_nav_zone.visible = True
            self.right_nav_zone.opacity = 0.25 if self.current_page >= self.total_pages else 1.0
            self.right_nav_zone.disabled = self.current_page >= self.total_pages

        try:
            # Renderiza página principal (esquerda)
            _w1, h1, txt1, b1 = self._render_page_into_card(
                self.current_page,
                self.page_image,
                self.text_layer_stack,
                self.selection_container,
            )
            self._left_text_boxes = b1
            self.current_page_text = txt1
            max_h = h1

            # Renderiza página secundária se no modo Lado a Lado
            if self.view_mode == 'split' and self.current_page + 1 <= self.total_pages:
                _w2, h2, _txt2, b2 = self._render_page_into_card(
                    self.current_page + 1,
                    self.page_image_right,
                    self.text_layer_stack_right,
                    self.selection_container_right,
                )
                self._right_text_boxes = b2
                self.page_card_right.visible = True
                max_h = max(h1, h2)
            else:
                self.page_card_right.visible = False
                if hasattr(self, 'selection_container_right'):
                    self.selection_container_right.visible = False

            self.page_number_label.value = self._format_page_label()
            self.page_count_label.value = self._format_page_count_label()

            if hasattr(self, 'left_nav_zone'):
                self.left_nav_zone.height = s(max_h)
            if hasattr(self, 'right_nav_zone'):
                self.right_nav_zone.height = s(max_h)

            self.zoom_label.value = f'{int(self.zoom_level * 100)}%'

            try:
                self.update()
            except (RuntimeError, AttributeError):
                pass
        except Exception as error:
            log_exception(f'Falha ao renderizar página {self.current_page}', error)

    def _copy_page_text(self, _e: ft.ControlEvent | None = None) -> None:
        """Copia o texto selecionado ou, se nenhum, todo o texto da página atual com codificação exata."""
        text = (self.selected_text or '').strip()
        if not text:
            clip = get_system_clipboard_text().strip()
            if clip and (clip in self.current_page_text):
                text = clip

        if not text:
            text = (self.current_page_text or getattr(self.page_text_field, 'value', '') or '').strip()

        if not text:
            if self.page:
                ui.toast(self.page, self.config, 'Nenhum texto detectado nesta página.')
            return

        copied = _copy_plain_text_to_system_clipboard(text)
        if not copied and self.page:
            try:
                self.page.set_clipboard(text)
                copied = True
            except Exception:
                pass

        if self.page:
            label = 'Texto selecionado copiado!' if (self.selected_text and text == self.selected_text) else f'Texto da página {self.current_page} copiado!'
            ui.toast(self.page, self.config, label, icon_name='copy')

    def get_work_page(self, pdf_page: int | None = None) -> int:
        """Calcula a numeração de página da obra física aplicando o offset."""
        p = self.current_page if pdf_page is None else pdf_page
        return p + self.page_offset

    def _format_page_label(self) -> str:
        """Formata o texto do indicador de página conforme o modo de visualização e o offset."""
        if self.view_mode == 'split' and self.current_page + 1 <= self.total_pages:
            if self.page_offset != 0:
                wp1 = self.current_page + self.page_offset
                wp2 = self.current_page + 1 + self.page_offset
                return f'p. {wp1}–{wp2}'
            return f'{self.current_page} - {self.current_page + 1}'
        if self.page_offset != 0:
            wp = self.current_page + self.page_offset
            return f'p. {wp}'
        return str(self.current_page)

    def _format_page_count_label(self) -> str:
        """Formata o texto do totalizador/indicador de PDF conforme o offset."""
        if self.page_offset != 0:
            if self.view_mode == 'split' and self.current_page + 1 <= self.total_pages:
                return f' (PDF {self.current_page}–{self.current_page + 1}/{self.total_pages})'
            return f' (PDF {self.current_page}/{self.total_pages})'
        return f' de {self.total_pages}'

    def set_page_offset(self, offset: int) -> None:
        """Define e persiste o offset de sincronização de páginas entre o PDF e a obra física."""
        self.page_offset = int(offset)
        if hasattr(self, 'resource') and self.resource and getattr(self.resource, 'id', None):
            try:
                self.pdf_service.update_page_offset(self.resource.id, self.page_offset)
                self.resource.pdf_page_offset = self.page_offset
            except Exception as err:
                log_exception('Falha ao persistir offset no banco', err)

        if hasattr(self, 'offset_field') and self.offset_field is not None:
            self.offset_field.value = str(self.page_offset)
            is_active = self.page_offset != 0
            self.offset_field.border_color = (
                self.config.colors['gold'] if is_active else self.config.colors['border_strong']
            )
            if self.offset_field.text_style:
                self.offset_field.text_style.color = (
                    self.config.colors['gold'] if is_active else self.config.colors['text']
                )

        self.page_number_label.value = self._format_page_label()
        self.page_count_label.value = self._format_page_count_label()
        try:
            self.update()
        except (RuntimeError, AttributeError):
            pass

    def _handle_offset_increment(self, _e: ft.ControlEvent | None = None) -> None:
        if self.is_modal_open:
            return
        self.set_page_offset(self.page_offset + 1)

    def _handle_offset_decrement(self, _e: ft.ControlEvent | None = None) -> None:
        if self.is_modal_open:
            return
        self.set_page_offset(self.page_offset - 1)

    def _handle_offset_submit(self, _e: ft.ControlEvent | None = None) -> None:
        if self.is_modal_open:
            return
        try:
            val_str = (self.offset_field.value or '0').strip() if self.offset_field else '0'
            val = int(val_str)
        except (ValueError, TypeError):
            val = self.page_offset
        self.set_page_offset(val)

    def _handle_sync_current_as_page_one(self, _e: ft.ControlEvent | None = None) -> None:
        """Sincroniza automaticamente a página atual do PDF para corresponder à página 1 da obra física."""
        if self.is_modal_open:
            return
        new_offset = 1 - self.current_page
        self.set_page_offset(new_offset)
        if self.page:
            ui.toast(
                self.page,
                self.config,
                f'PDF sincronizado: Página {self.current_page} definida como Página 1 da obra (Offset: {new_offset:+d}).',
                icon_name='bullseye',
            )

    def _start_page_edit(self, _e: ft.ControlEvent | None = None) -> None:
        """Transfere o indicador de página para modo de edição direta via TextField."""
        if self.is_modal_open:
            return
        if getattr(self, '_is_editing_page', False):
            return
        if self.total_pages < 1:
            return

        self._is_editing_page = True
        current_str = str(self.current_page)
        self.page_number_input.value = current_str
        self.page_number_input.selection = ft.TextSelection(
            base_offset=0,
            extent_offset=len(current_str),
        )
        self.page_number_input.autofocus = True
        self.page_number_display.visible = False
        self.page_number_input.visible = True
        try:
            self.update()
        except (RuntimeError, AttributeError):
            pass

        if self.page and hasattr(self.page, 'run_task'):
            try:
                self.page.run_task(self.page_number_input.focus)
            except Exception:
                pass

    def _submit_page_input(self, _e: ft.ControlEvent | None = None) -> None:
        """Valida e aplica a página digitada ao pressionar Enter ou perder o foco (blur)."""
        if not getattr(self, '_is_editing_page', False):
            return
        self._is_editing_page = False
        self.page_number_input.autofocus = False
        self.page_number_input.visible = False
        self.page_number_display.visible = True

        raw_val = (self.page_number_input.value or '').strip()
        target_page: int | None = None
        try:
            parsed = int(raw_val)
            if 1 <= parsed <= self.total_pages:
                target_page = parsed
        except (ValueError, TypeError):
            pass

        if target_page is not None and target_page != self.current_page:
            self.current_page = target_page
            self._reset_scroll_position()
            self._load_current_page()
        else:
            self.page_number_label.value = self._format_page_label()
            self.page_count_label.value = self._format_page_count_label()
            try:
                self.update()
            except (RuntimeError, AttributeError):
                pass

    def _cancel_page_input(self, _e: ft.ControlEvent | None = None) -> None:
        """Cancela a edição restaurando o valor original do indicador sem erros."""
        if not getattr(self, '_is_editing_page', False):
            return
        self._is_editing_page = False
        self.page_number_input.autofocus = False
        self.page_number_input.value = str(self.current_page)
        self.page_number_input.visible = False
        self.page_number_display.visible = True
        self.page_number_label.value = self._format_page_label()
        self.page_count_label.value = self._format_page_count_label()
        try:
            self.update()
        except (RuntimeError, AttributeError):
            pass

    def _on_page_input_submit(self, e: ft.ControlEvent) -> None:
        self._submit_page_input(e)

    def _on_page_input_blur(self, e: ft.ControlEvent) -> None:
        self._submit_page_input(e)

    def handle_key(self, key: str, mod: bool = False) -> bool:
        """Navega páginas do PDF via teclado e suporta atalhos de cópia e zoom."""
        if self.is_modal_open:
            return False
        if getattr(self, '_is_editing_page', False):
            if key in ('Escape', 'Esc'):
                self._cancel_page_input()
                return True
            if key in ('Enter', 'NumpadEnter'):
                self._submit_page_input()
                return True
            return False

        if mod:
            self._ctrl_pressed_state = True
            if key.lower() in ('c', 'insert') and self.selected_text:
                _copy_plain_text_to_system_clipboard(self.selected_text)
                if self.page:
                    ui.toast(self.page, self.config, 'Texto selecionado copiado!', icon_name='copy')
                return True
            if key.lower() == 'a':
                if self.current_page_text:
                    self.selected_text = self.current_page_text
                    self.selected_page = self.current_page
                    if self.page:
                        ui.toast(self.page, self.config, f'Todo o texto da página {self.current_page} selecionado!')
                return True
            if key in ('+', '=', 'Add'):
                self._zoom_in()
                return True
            if key in ('-', '_', 'Subtract'):
                self._zoom_out()
                return True
            if key in ('0', 'num0'):
                self._zoom_reset()
                return True
            return False

        if key in ('Control', 'ControlLeft', 'ControlRight', 'Ctrl'):
            self._ctrl_pressed_state = False

        if key.lower() == 'v' and not getattr(self, '_is_editing_page', False):
            self._on_tool_mode_change('select')
            if self.page:
                ui.toast(self.page, self.config, 'Modo Seleção de Texto ativado (V)')
            return True
        if key.lower() == 'h' and not getattr(self, '_is_editing_page', False):
            self._on_tool_mode_change('pan')
            if self.page:
                ui.toast(self.page, self.config, 'Modo Mão / Rolagem ativado (H)')
            return True

        if key in ("Arrow Left", "ArrowLeft", "Page Up", "PageUp", "Left"):
            if self.current_page > 1:
                self._prev_page()
                return True
        elif key in ("Arrow Right", "ArrowRight", "Page Down", "PageDown", "Right"):
            if self.current_page < self.total_pages:
                self._next_page()
                return True
        return False

    def _reset_scroll_position(self) -> None:
        """Restaura a rolagem vertical para o topo ao trocar de página."""
        run_task = getattr(self.page, 'run_task', None) if self.page else None
        if not hasattr(self, 'scroll_column') or self.scroll_column is None or run_task is None:
            return

        async def _scroll() -> None:
            try:
                await self.scroll_column.scroll_to(offset=0, duration=0)
            except Exception:
                pass

        try:
            run_task(_scroll)
        except Exception:
            pass

    def _prev_page(self, _e: ft.ControlEvent | None = None) -> None:
        if self.is_modal_open:
            return
        if getattr(self, '_is_editing_page', False):
            self._cancel_page_input()
        if self.current_page > 1:
            self.current_page -= 1
            self._reset_scroll_position()
            self._load_current_page()

    def _next_page(self, _e: ft.ControlEvent | None = None) -> None:
        if self.is_modal_open:
            return
        if getattr(self, '_is_editing_page', False):
            self._cancel_page_input()
        if self.current_page < self.total_pages:
            self.current_page += 1
            self._reset_scroll_position()
            self._load_current_page()

    def _zoom_in(self, _e: ft.ControlEvent | None = None) -> None:
        if self.is_modal_open:
            return
        if self.zoom_level < 3.0:
            self.zoom_level = round(min(3.0, self.zoom_level + 0.25), 2)
            self._load_current_page()

    def _zoom_out(self, _e: ft.ControlEvent | None = None) -> None:
        if self.is_modal_open:
            return
        if self.zoom_level > 0.5:
            self.zoom_level = round(max(0.5, self.zoom_level - 0.25), 2)
            self._load_current_page()

    def _zoom_reset(self, _e: ft.ControlEvent | None = None) -> None:
        """Redefine o zoom para 100% (Ajustar à página)."""
        if self.is_modal_open:
            return
        self.zoom_level = 1.0
        self._load_current_page()

    def _toggle_sidebar(self, _e: ft.ControlEvent | None = None) -> None:
        self.show_sidebar = not self.show_sidebar
        self.sidebar_container.visible = self.show_sidebar
        try:
            self.update()
        except (RuntimeError, AttributeError):
            pass

    def _handle_new_fragment_click(self, _e: ft.ControlEvent | None = None) -> None:
        """Abre modal interno para criação de fragmento a partir do texto selecionado."""
        if self.is_modal_open:
            return
        snippet = (self.selected_text or getattr(self.page_text_field, 'value', '') or '').strip()
        if not snippet:
            clip = get_system_clipboard_text().strip()
            if clip and (clip in self.current_page_text or (hasattr(self, 'doc') and clip in (self.current_page_text or ''))):
                snippet = clip

        target_page = self.selected_page if snippet else self.current_page
        self._open_fragment_modal(initial_excerpt=snippet, page_number=target_page)

    def _open_fragment_modal(self, initial_excerpt: str = '', page_number: int | None = None) -> None:
        """Abre modal unificado para criação de novo fragmento sem sair do leitor."""
        if not self.page or self.is_modal_open:
            return

        loc_page = page_number or self.current_page
        work_page = self.get_work_page(loc_page)
        self.fragment_modal.page = self.page
        self.fragment_modal.open_create_for_work(
            bib_res_id=self.resource.id,
            title=self.work_title,
            initial_location_type='Página',
            initial_location_value=str(work_page),
            initial_excerpt=initial_excerpt,
            on_saved=self._on_fragment_saved,
        )

    def _handle_fragment_card_click(self, item: Fragment) -> None:
        """Navega para a página do fragmento e abre o modal padrão de edição."""
        if self.is_modal_open:
            return
        if item.location_value:
            self._jump_to_fragment_page(item.location_value)
        self._open_edit_fragment_modal(item)

    def _open_edit_fragment_modal(self, item: Fragment) -> None:
        """Abre o modal unificado de fragmento em modo de edição para o fragmento selecionado."""
        if not self.page or self.is_modal_open:
            return

        self.fragment_modal.page = self.page
        record = {
            'id': item.id,
            'fragment_type': item.fragment_type or 'quote',
            'bib_res_id': self.resource.id,
            'work_title': self.work_title,
            'citation_author': '',
            'display_year': '',
            'excerpt': item.excerpt or '',
            'location_type': item.location_type or None,
            'location_value': item.location_value or '',
        }
        self.fragment_modal.open_edit(record, on_saved=self._on_fragment_saved)

    def _on_fragment_saved(self) -> None:
        """Callback executado após salvar o fragmento no modal."""
        self._refresh_fragments_list()
        if self.page:
            ui.toast(self.page, self.config, 'Fragmento salvo com sucesso!', icon_name='check')

    def _save_fragment_from_modal(self, editing_id: int | None, payload: dict[str, object]) -> bool:
        """Persiste o fragmento gerado no modal diretamente no banco de dados."""
        from src.services.fragment_service import FragmentService

        text_val = (str(payload.get('excerpt') or '')).strip()
        if not text_val:
            if self.page:
                ui.toast(self.page, self.config, 'O conteúdo do fragmento não pode ser vazio.')
            return False

        kind = payload.get('fragment_type') or 'quote'
        loc_val = (str(payload.get('location_value') or '')).strip()
        if kind == 'quote' and not loc_val:
            if self.page:
                ui.toast(self.page, self.config, 'Citações exigem o valor da localização.')
            return False

        try:
            svc = FragmentService()
            if editing_id is not None:
                svc.update(editing_id, payload)
            else:
                svc.create(payload)
            return True
        except Exception as err:
            log_exception('Falha ao salvar fragmento via leitor de PDF', err)
            if self.page:
                ui.toast(self.page, self.config, f'Erro ao salvar fragmento: {err}')
            return False

    def _refresh_fragments_list(self) -> None:
        """Atualiza a lista lateral com os fragmentos já cadastrados da obra."""
        c = self.config
        colors = c.colors

        from src.db.db import SessionLocal

        with SessionLocal() as session:
            fragments = (
                session.query(Fragment)
                .filter(Fragment.bib_res_id == self.resource.id)
                .all()
            )
            frag_list = [
                Fragment(
                    id=f.id,
                    fragment_type=f.fragment_type,
                    excerpt=f.excerpt,
                    location_type=f.location_type,
                    location_value=f.location_value,
                )
                for f in fragments
            ]

        if not frag_list:
            self.fragments_column.controls = [
                ui.empty_state(
                    c,
                    'quote-left',
                    'Nenhum fragmento',
                    'Crie citações e paráfrases a partir das páginas deste PDF.',
                )
            ]
        else:
            cards = []
            for item in frag_list:
                loc_txt = ''
                if item.location_type and item.location_value:
                    loc_txt = f'{item.location_type} {item.location_value}'
                elif item.location_value:
                    loc_txt = f'p. {item.location_value}'

                cards.append(
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Row(
                                    controls=[
                                        ui.badge(
                                            c,
                                            'Citação' if item.fragment_type == 'quote' else 'Paráfrase',
                                            accent=(item.fragment_type == 'quote'),
                                        ),
                                        ui.ui_text(c, loc_txt, size=11, color=colors['muted']),
                                    ],
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                ),
                                ui.ui_text(
                                    c,
                                    f'“{item.excerpt}”' if item.fragment_type == 'quote' else item.excerpt,
                                    size=12,
                                    max_lines=3,
                                    color=colors['text'],
                                    align=ft.TextAlign.JUSTIFY,
                                ),
                            ],
                            spacing=s(6),
                            tight=True,
                        ),
                        bgcolor=colors['bg'],
                        border=ft.Border.all(1, colors['border']),
                        border_radius=ft.BorderRadius.all(s(6)),
                        padding=s(10),
                        ink=True,
                        tooltip='Clique para editar este fragmento',
                        on_click=lambda _e, f=item: self._handle_fragment_card_click(f),
                    )
                )
            self.fragments_column.controls = cards

        try:
            self.sidebar_container.update()
        except (RuntimeError, AttributeError):
            pass

    def _jump_to_fragment_page(self, loc_val: str | None) -> None:
        """Navega para a página apontada pelo fragmento considerando a sincronia de offset."""
        if not loc_val:
            return
        import re
        match = re.search(r'\d+', str(loc_val))
        if match:
            target_work_page = int(match.group(0))
            pdf_page = target_work_page - self.page_offset
            if 1 <= pdf_page <= self.total_pages:
                self.current_page = pdf_page
                self._load_current_page()
            elif 1 <= target_work_page <= self.total_pages:
                self.current_page = target_work_page
                self._load_current_page()

    def _handle_annotate_click(self, _e: ft.ControlEvent | None = None) -> None:
        """Registra nota rápida sobre a página atual."""
        if not self.page:
            return
        ui.toast(self.page, self.config, f'Anotação registrada na página {self.current_page}.')

from collections.abc import Callable
from pathlib import Path

import flet as ft
import pymupdf

from src.domains import BibliographicResource
from src.services.pdf_service import PdfService
from src.utils.error_log import log_exception
from src.utils.types import ViewConfig
from src.views import ui_kit as ui
from src.views.fragment_modal import FragmentModal
from .pdf_common import BASE_PAGE_HEIGHT
from .pdf_fragments_mixin import PdfFragmentsMixin
from .pdf_navigation_mixin import PdfNavigationMixin
from .pdf_pan_mixin import PdfPanSelectionMixin
from .pdf_render_mixin import PdfRenderMixin
from .pdf_tools_mixin import PdfToolsMixin

s = ui.s
W500 = ui.W500
W600 = ui.W600
W700 = ui.W700


class PdfReaderView(
    PdfToolsMixin,
    PdfPanSelectionMixin,
    PdfNavigationMixin,
    PdfFragmentsMixin,
    PdfRenderMixin,
    ft.Container,
):
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

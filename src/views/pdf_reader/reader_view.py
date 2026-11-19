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
from .pdf_layout_mixin import PdfLayoutMixin
from .pdf_navigation_mixin import PdfNavigationMixin
from .pdf_pan_mixin import PdfPanSelectionMixin
from .pdf_render_mixin import PdfRenderMixin
from .pdf_tools_mixin import PdfToolsMixin

s = ui.s
W500 = ui.W500
W600 = ui.W600
W700 = ui.W700


class PdfReaderView(
    PdfLayoutMixin,
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
        top_bar = self._build_top_bar()
        self._build_reading_area()
        self._build_sidebar()
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

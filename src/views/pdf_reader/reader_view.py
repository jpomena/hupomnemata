import base64
import webbrowser
from collections.abc import Callable
from pathlib import Path

import flet as ft
import pymupdf

from src.domains import BibliographicResource, Fragment
from src.services.pdf_service import PdfService
from src.utils.error_log import log_exception
from src.utils.types import ViewConfig
from src.views import ui_kit as ui
from src.views.fragment_modal import FragmentModal
from src.views.pdf_reader.pdf_template import generate_pdf_viewer_html

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
    ) -> None:
        super().__init__(expand=True)
        self._page_override = page
        self.config = config
        self.resource = resource
        self.on_back_callback = on_back
        self.on_new_fragment_callback = on_new_fragment
        self.pdf_service = pdf_service or PdfService()

        self.current_page: int = 1
        self.zoom_level: float = 1.0
        self.view_mode: str = 'page'  # 'page', 'split', 'text'
        self.show_sidebar: bool = True
        self.show_text_panel: bool = False
        self.current_page_text: str = ''

        self.doc: pymupdf.Document | None = None
        self.total_pages: int = resource.pdf_page_count or 1
        self.pdf_abs_path: Path | None = None

        work = self.resource.specific_work
        self.work_title = (work.title if work else '') or (self.resource.pdf_filename or 'Documento')

        self._init_pdf_document()

        # Controles reativos de interface
        self.page_number_label = ui.ui_text(self.config, '1', size=13, weight=W600, color=config.colors['gold'])
        self.page_count_label = ui.ui_text(self.config, f' de {self.total_pages}', size=13, color=config.colors['muted'])
        self.zoom_label = ui.ui_text(self.config, '100%', size=13, color=config.colors['muted'])

        self.loading_ring = ft.ProgressRing(
            width=s(32),
            height=s(32),
            stroke_width=3,
            color=config.colors['gold'],
            visible=False,
        )

        # Imagem dimensionada explicitamente para caber no leitor
        self.page_image = ft.Image(
            src='',
            fit=ft.BoxFit.CONTAIN,
            border_radius=ft.BorderRadius.all(s(4)),
            height=s(BASE_PAGE_HEIGHT),
        )

        # Camada de texto sobreposta sobre a imagem para seleção de caracteres com mouse
        self.text_layer_stack = ft.Stack(
            controls=[],
            height=s(BASE_PAGE_HEIGHT),
        )
        self.selection_area = ft.SelectionArea(
            content=self.text_layer_stack,
        )

        # Campo de texto para retrocompatibilidade
        self.page_text_field = ft.TextField(
            multiline=True,
            min_lines=4,
            max_lines=8,
            read_only=False,
            text_size=s(13),
            hint_text='Texto extraído da página atual para seleção rápida de fragmentos...',
            border_color=config.colors['border_strong'],
            focused_border_color=config.colors['gold'],
            bgcolor=config.colors['bg'],
        )

        self.text_reading_column = ft.Column(
            spacing=s(12),
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

        self.text_reading_card = ft.Container(
            padding=s(20),
            bgcolor=config.colors['surface'],
            border=ft.Border.all(1, config.colors['border']),
            border_radius=ft.BorderRadius.all(s(6)),
            visible=False,
        )

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

        self.text_panel_container = ft.Container(
            bgcolor=config.colors['surface'],
            border=ft.Border.only(top=ft.BorderSide(1, config.colors['border'])),
            padding=s(12),
            visible=self.show_text_panel,
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
    def page(self) -> ft.Page | None:
        return getattr(self, '_page_override', None) or super().page

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

    def _build_layout(self) -> None:
        c = self.config
        colors = c.colors

        # ── Barra Superior de Ferramentas ────────────────────────
        back_btn = ui.icon_button(c, 'arrow-left', on_click=lambda _: self.on_back_callback(), tooltip='Voltar ao Acervo / Fechar Janela')
        title_text = ui.serif_text(c, self.work_title, size=15, weight=W700, max_lines=1)

        prev_page_btn = ui.icon_button(c, 'chevron-left', on_click=self._prev_page, tooltip='Página anterior (←)')
        next_page_btn = ui.icon_button(c, 'chevron-right', on_click=self._next_page, tooltip='Próxima página (→)')

        zoom_out_btn = ui.icon_button(c, 'magnifying-glass-minus', on_click=self._zoom_out, tooltip='Diminuir zoom (-)')
        zoom_reset_btn = ui.icon_button(c, 'compress', on_click=self._zoom_reset, tooltip='Ajustar página ao leitor (100%)')
        zoom_in_btn = ui.icon_button(c, 'magnifying-glass-plus', on_click=self._zoom_in, tooltip='Aumentar zoom (+)')

        extract_btn = ui.button(
            c,
            'Novo fragmento',
            icon_name='quote-left',
            variant='primary',
            small=True,
            on_click=self._handle_new_fragment_click,
            tooltip='Criar fragmento com referência a esta página',
        )

        copy_text_btn = ui.button(
            c,
            'Copiar texto',
            icon_name='copy',
            small=True,
            on_click=self._copy_page_text,
            tooltip='Copiar todo o texto desta página para a área de transferência',
        )

        browser_btn = ui.icon_button(
            c,
            'arrow-up-right-from-square',
            on_click=self._handle_open_browser_viewer,
            tooltip='Abrir leitor com PDF.js no navegador',
        )

        toggle_sidebar_btn = ui.icon_button(
            c,
            'sidebar',
            on_click=self._toggle_sidebar,
            tooltip='Alternar painel lateral de fragmentos',
        )

        self._render_view_mode_selector()

        top_bar = ft.Container(
            content=ft.Row(
                controls=[
                    back_btn,
                    ft.Container(content=title_text, expand=True, margin=ft.Margin.only(right=s(12))),
                    ft.Row(
                        controls=[prev_page_btn, self.page_number_label, self.page_count_label, next_page_btn],
                        spacing=s(4),
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Container(width=1, height=s(20), bgcolor=colors['border']),
                    ft.Row(
                        controls=[zoom_out_btn, self.zoom_label, zoom_in_btn, zoom_reset_btn],
                        spacing=s(4),
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Container(width=1, height=s(20), bgcolor=colors['border']),
                    self.view_mode_host,
                    ft.Container(width=1, height=s(20), bgcolor=colors['border']),
                    copy_text_btn,
                    extract_btn,
                    browser_btn,
                    toggle_sidebar_btn,
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            height=s(52),
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

        # ── Navegação Lateral por Clique nas laterais ──
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
            left=0,
            top=0,
            bottom=0,
            width=0,
            bgcolor=ft.Colors.TRANSPARENT,
            on_click=self._prev_page,
            tooltip='Página anterior (←)',
            ink=True,
        )
        self.right_page_margin_click = ft.Container(
            right=0,
            top=0,
            bottom=0,
            width=0,
            bgcolor=ft.Colors.TRANSPARENT,
            on_click=self._next_page,
            tooltip='Próxima página (→)',
            ink=True,
        )

        # Cartão da Página com Imagem e Camada de Texto Selecionável
        self.page_card = ft.Container(
            content=ft.Stack(
                controls=[
                    self.page_image,
                    self.selection_area,
                    self.left_page_margin_click,
                    self.right_page_margin_click,
                    ft.Container(
                        content=self.loading_ring,
                        alignment=ft.Alignment.CENTER,
                    ),
                ],
                alignment=ft.Alignment.CENTER,
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

        self.page_view_row = ft.Row(
            controls=[
                self.left_nav_zone,
                self.page_card,
                self.right_nav_zone,
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        # Montagem do Cartão de Leitura de Texto
        text_card_head = ft.Row(
            controls=[
                ui.serif_text(c, 'Transcrição Selecionável da Página', size=14, weight=W700, color=colors['text']),
                ft.Row(
                    controls=[
                        ui.button(c, 'Copiar texto', icon_name='copy', small=True, on_click=self._copy_page_text),
                        ui.button(c, 'Usar no fragmento', icon_name='quote-left', small=True, variant='primary', on_click=self._use_selected_text_in_fragment),
                    ],
                    spacing=s(6),
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

        self.text_reading_card.content = ft.Column(
            controls=[
                text_card_head,
                ft.Divider(height=1, color=colors['border']),
                ft.SelectionArea(
                    content=self.text_reading_column,
                ),
            ],
            spacing=s(10),
            expand=True,
        )

        self.central_display_row = ft.Row(
            controls=[
                self.page_view_row,
                self.text_reading_card,
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            vertical_alignment=ft.CrossAxisAlignment.START,
            spacing=s(20),
        )

        self.page_scroll_area = ft.Container(
            content=ft.Column(
                controls=[
                    self.empty_state_container,
                    self.central_display_row,
                    self.text_panel_container,
                ],
                scroll=ft.ScrollMode.AUTO,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                expand=True,
            ),
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

    def _render_view_mode_selector(self) -> None:
        self.view_mode_host.content = ui.segmented(
            self.config,
            [
                ('page', 'Página', None),
                ('split', 'Lado a Lado', None),
                ('text', 'Texto', None),
            ],
            self.view_mode,
            self._on_view_mode_change,
        )

    def _on_view_mode_change(self, mode: str) -> None:
        self.view_mode = mode
        self._render_view_mode_selector()
        self._apply_view_mode_layout()
        try:
            self.update()
        except (RuntimeError, AttributeError):
            pass

    def _apply_view_mode_layout(self) -> None:
        """Ajusta a visibilidade e largura dos containers conforme o modo ativo."""
        if self.view_mode == 'page':
            self.page_view_row.visible = True
            self.text_reading_card.visible = False
        elif self.view_mode == 'split':
            self.page_view_row.visible = True
            self.text_reading_card.visible = True
            self.text_reading_card.width = s(460)
            self.text_reading_card.height = self.page_image.height or s(BASE_PAGE_HEIGHT)
        elif self.view_mode == 'text':
            self.page_view_row.visible = False
            self.text_reading_card.visible = True
            self.text_reading_card.width = s(760)
            self.text_reading_card.height = s(BASE_PAGE_HEIGHT)

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

    def _load_current_page(self) -> None:
        """Renderiza a página reduzida no tamanho do leitor com camada de texto selecionável."""
        if self.doc is None:
            self.page_image.src = ''
            self.page_image.visible = False
            self.loading_ring.visible = False
            self.text_layer_stack.controls = []
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
            page_idx = max(0, min(self.current_page - 1, len(self.doc) - 1))
            page = self.doc.load_page(page_idx)
            page_rect = page.rect

            # Proporção geométrica real da página (A4, carta, paisagem, etc.)
            aspect_ratio = (page_rect.width / page_rect.height) if page_rect.height > 0 else 0.707

            # Altura e largura reduzidas para caber perfeitamente no leitor com zoom
            target_h = int(BASE_PAGE_HEIGHT * self.zoom_level)
            target_w = int(target_h * aspect_ratio)

            # Resolução nítida (Retina/HiDPI) adaptada ao zoom
            dpi = max(110, min(300, int(150 * max(1.0, self.zoom_level))))
            pix = page.get_pixmap(dpi=dpi)
            png_bytes = pix.tobytes('png')
            b64_str = base64.b64encode(png_bytes).decode('ascii')

            self.page_image.src = f'data:image/png;base64,{b64_str}'
            self.page_image.width = s(target_w)
            self.page_image.height = s(target_h)

            self.text_layer_stack.width = s(target_w)
            self.text_layer_stack.height = s(target_h)

            if hasattr(self, 'left_nav_zone'):
                self.left_nav_zone.height = s(target_h)
            if hasattr(self, 'right_nav_zone'):
                self.right_nav_zone.height = s(target_h)

            raw_text = page.get_text() or ''
            self.current_page_text = raw_text
            self.page_text_field.value = raw_text or '(Nenhum texto vetorial detectado nesta página)'

            # Geração da camada de texto transparente sobreposta para seleção de caracteres
            blocks = page.get_text('blocks')
            sx = target_w / page_rect.width if page_rect.width > 0 else 1.0
            sy = target_h / page_rect.height if page_rect.height > 0 else 1.0
            layer_controls = []
            for b in blocks:
                if len(b) >= 7 and b[6] == 0:  # Bloco de texto
                    x0, y0, x1, y1, btext = b[0], b[1], b[2], b[3], b[4]
                    bw = max(10.0, (x1 - x0) * sx)
                    bh = max(12.0, (y1 - y0) * sy)
                    bx = x0 * sx
                    by = y0 * sy
                    lines = [l for l in btext.splitlines() if l.strip()]
                    n_lines = max(1, len(lines))
                    line_h = bh / n_lines
                    fsize = max(7, min(22, int(line_h * 0.85)))
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
                                selectable=True,
                                font_family=self.config.font_families['montserrat'],
                            ),
                        )
                    )
            self.text_layer_stack.controls = layer_controls

            # Atualização da coluna de leitura textual
            self._update_text_reading_view(raw_text)
            self._apply_view_mode_layout()

            self.page_number_label.value = str(self.current_page)
            self.zoom_label.value = f'{int(self.zoom_level * 100)}%'

            try:
                self.update()
            except (RuntimeError, AttributeError):
                pass
        except Exception as error:
            log_exception(f'Falha ao renderizar página {self.current_page}', error)

    def _update_text_reading_view(self, text: str) -> None:
        """Formata o texto extraído da página em parágrafos selecionáveis e legíveis."""
        c = self.config
        colors = c.colors
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        if not paragraphs:
            paragraphs = [p.strip() for p in text.splitlines() if p.strip()]

        controls = []
        if paragraphs:
            for p in paragraphs:
                controls.append(
                    ft.Text(
                        value=p,
                        size=s(13.5),
                        color=colors['text'],
                        font_family=c.font_families['montserrat'],
                        selectable=True,
                        style=ft.TextStyle(height=1.55),
                    )
                )
        else:
            controls.append(
                ft.Text(
                    value='(Nenhum texto vetorial detectado nesta página. O documento pode ser uma digitalização ou imagem).',
                    size=s(13),
                    color=colors['muted'],
                    italic=True,
                    selectable=True,
                )
            )

        self.text_reading_column.controls = controls

    def _copy_page_text(self, _e: ft.ControlEvent | None = None) -> None:
        """Copia todo o texto vetorial da página atual para a área de transferência."""
        text = (self.current_page_text or self.page_text_field.value or '').strip()
        if not text:
            if self.page:
                ui.toast(self.page, self.config, 'Nenhum texto detectado nesta página.')
            return

        copied = False
        if self.page:
            try:
                self.page.set_clipboard(text)
                copied = True
            except Exception:
                pass

        if not copied:
            from src.utils.clipboard import _copy_plain_text_to_system_clipboard
            _copy_plain_text_to_system_clipboard(text)

        if self.page:
            ui.toast(self.page, self.config, f'Texto da página {self.current_page} copiado!', icon_name='copy')

    def handle_key(self, key: str, mod: bool = False) -> bool:
        """Navega páginas do PDF via teclado (setas esquerda/direita, PageUp/PageDown)."""
        if mod:
            return False
        if key in ("Arrow Left", "ArrowLeft", "Page Up", "PageUp", "Left"):
            if self.current_page > 1:
                self._prev_page()
                return True
        elif key in ("Arrow Right", "ArrowRight", "Page Down", "PageDown", "Right"):
            if self.current_page < self.total_pages:
                self._next_page()
                return True
        return False

    def _prev_page(self, _e: ft.ControlEvent | None = None) -> None:
        if self.current_page > 1:
            self.current_page -= 1
            self._load_current_page()

    def _next_page(self, _e: ft.ControlEvent | None = None) -> None:
        if self.current_page < self.total_pages:
            self.current_page += 1
            self._load_current_page()

    def _zoom_in(self, _e: ft.ControlEvent | None = None) -> None:
        if self.zoom_level < 2.5:
            self.zoom_level = round(self.zoom_level + 0.25, 2)
            self._load_current_page()

    def _zoom_out(self, _e: ft.ControlEvent | None = None) -> None:
        if self.zoom_level > 0.5:
            self.zoom_level = round(self.zoom_level - 0.25, 2)
            self._load_current_page()

    def _zoom_reset(self, _e: ft.ControlEvent | None = None) -> None:
        """Redefine o zoom para 100% (Ajustar à página)."""
        self.zoom_level = 1.0
        self._load_current_page()

    def _toggle_sidebar(self, _e: ft.ControlEvent | None = None) -> None:
        self.show_sidebar = not self.show_sidebar
        self.sidebar_container.visible = self.show_sidebar
        try:
            self.update()
        except (RuntimeError, AttributeError):
            pass

    def _toggle_text_panel(self, _e: ft.ControlEvent | None = None) -> None:
        self.show_text_panel = not self.show_text_panel
        self.text_panel_container.visible = self.show_text_panel
        try:
            self.update()
        except (RuntimeError, AttributeError):
            pass

    def _handle_new_fragment_click(self, _e: ft.ControlEvent | None = None) -> None:
        """Abre modal interno para criação de fragmento na página atual sem sair do leitor."""
        snippet = (self.page_text_field.value or self.current_page_text or '').strip()
        if snippet.startswith('(Nenhum texto'):
            snippet = ''
        self._open_fragment_modal(initial_excerpt=snippet)

    def _use_selected_text_in_fragment(self, _e: ft.ControlEvent | None = None) -> None:
        """Abre modal interno com o texto extraído da página atual sem sair do leitor."""
        text = (self.page_text_field.value or self.current_page_text or '').strip()
        if text.startswith('(Nenhum texto'):
            text = ''
        self._open_fragment_modal(initial_excerpt=text)

    def _open_fragment_modal(self, initial_excerpt: str = '') -> None:
        """Abre modal unificado para criação de novo fragmento sem sair do leitor."""
        if not self.page:
            return

        self.fragment_modal.page = self.page
        self.fragment_modal.open_create_for_work(
            bib_res_id=self.resource.id,
            title=self.work_title,
            initial_location_type='Página',
            initial_location_value=str(self.current_page),
            initial_excerpt=initial_excerpt,
            on_saved=self._on_fragment_saved,
        )

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
                        tooltip='Clique para ir até a página do fragmento',
                        on_click=lambda _e, loc=item.location_value: self._jump_to_fragment_page(loc),
                    )
                )
            self.fragments_column.controls = cards

        try:
            self.sidebar_container.update()
        except (RuntimeError, AttributeError):
            pass

    def _jump_to_fragment_page(self, loc_val: str | None) -> None:
        """Navega para a página apontada pelo fragmento."""
        if not loc_val:
            return
        import re
        match = re.search(r'\d+', str(loc_val))
        if match:
            target = int(match.group(0))
            if 1 <= target <= self.total_pages:
                self.current_page = target
                self._load_current_page()

    def _handle_annotate_click(self, _e: ft.ControlEvent | None = None) -> None:
        """Registra nota rápida sobre a página atual."""
        if not self.page:
            return
        ui.toast(self.page, self.config, f'Anotação registrada na página {self.current_page}.')

    def _handle_open_browser_viewer(self, _e: ft.ControlEvent | None = None) -> None:
        """Abre o leitor interativo no navegador usando template PDF.js."""
        if not self.pdf_abs_path or not self.pdf_abs_path.exists():
            if self.page:
                ui.toast(self.page, self.config, 'Arquivo PDF não localizado no disco.')
            return

        try:
            html_content = generate_pdf_viewer_html(
                pdf_path=self.pdf_abs_path,
                title=self.work_title,
                initial_page=self.current_page,
            )
            temp_html_path = Path('/tmp') / f'hupomnemata_reader_{self.resource.id}.html'
            temp_html_path.write_text(html_content, encoding='utf-8')
            webbrowser.open(f'file://{temp_html_path.resolve()}')
            if self.page:
                ui.toast(self.page, self.config, 'Abrindo visualizador PDF.js no navegador...')
        except Exception as error:
            log_exception('Falha ao abrir visualizador no navegador', error)
            if self.page:
                ui.toast(self.page, self.config, f'Erro ao abrir no navegador: {error}')

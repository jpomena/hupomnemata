"""PdfRenderMixin extraído de ``reader_view.py``.

Movimentação literal: sem ``__init__``, colabora com ``PdfReaderView``
via ``self``.
"""

import base64

import flet as ft

from src.utils.clipboard import (
    _copy_plain_text_to_system_clipboard,
    get_system_clipboard_text,
)
from src.utils.error_log import log_exception
from src.views import ui_kit as ui
from .pdf_common import BASE_PAGE_HEIGHT
from src.utils.control_safety import safe_update

s = ui.s


class PdfRenderMixin:
    """Renderização das páginas, cache visual e anexo de PDF."""

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
            safe_update(self, exceptions=(RuntimeError, AttributeError))
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

            safe_update(self, exceptions=(RuntimeError, AttributeError))
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
            except Exception as error:
                log_exception(
                    'Falha ao copiar texto do PDF para a área de transferência',
                    error,
                )

        if self.page:
            label = 'Texto selecionado copiado!' if (self.selected_text and text == self.selected_text) else f'Texto da página {self.current_page} copiado!'
            ui.toast(self.page, self.config, label, icon_name='copy')

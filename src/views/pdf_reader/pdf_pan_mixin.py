"""PdfPanSelectionMixin extraído de ``reader_view.py``.

Movimentação literal: sem ``__init__``, colabora com ``PdfReaderView``
via ``self``.
"""

import flet as ft


class PdfPanSelectionMixin:
    """Gestos de pan, rolagem e seleção de texto sobre as páginas."""

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

"""PdfNavigationMixin extraído de ``reader_view.py``.

Movimentação literal: sem ``__init__``, colabora com ``PdfReaderView``
via ``self``.
"""

import flet as ft

from src.utils.clipboard import _copy_plain_text_to_system_clipboard
from src.utils.error_log import log_exception
from src.views import ui_kit as ui


class PdfNavigationMixin:
    """Navegação de páginas, zoom, offsets, edição direta e teclado."""

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
        if self.show_sidebar:
            self.sidebar_container.width = ui.s(320)
            self.sidebar_container.padding = ui.s(16)
            self.sidebar_container.opacity = 1.0
            self.sidebar_container.border = ft.Border.only(
                left=ft.BorderSide(1, self.config.colors['border'])
            )
        else:
            self.sidebar_container.opacity = 0.0
            self.sidebar_container.padding = 0
            self.sidebar_container.width = 0
            self.sidebar_container.border = None
        try:
            self.update()
        except (RuntimeError, AttributeError):
            pass

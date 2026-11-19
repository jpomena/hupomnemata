"""PdfToolsMixin extraído de ``reader_view.py``.

Movimentação literal: sem ``__init__``, colabora com ``PdfReaderView``
via ``self``.
"""

import flet as ft

from src.views import ui_kit as ui

s = ui.s
W600 = ui.W600


class PdfToolsMixin:
    """Barra superior do leitor: ferramentas, modos e responsividade."""

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

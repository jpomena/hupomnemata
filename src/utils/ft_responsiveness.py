"""Funções de escala para manter a interface proporcional à janela."""

import flet as ft

BASE_WIDTH = 1280
BASE_HEIGHT = 720


class Responsive:
    """Calcula dimensões proporcionais ao viewport de referência."""

    @staticmethod
    def font(size: float, scale: float) -> float:
        """Escala um tamanho tipográfico."""
        return size * scale

    @staticmethod
    def space(size: float, scale: float) -> float:
        """Escala um espaçamento ou dimensão."""
        return size * scale

    @staticmethod
    def get_page_dimensions(
        page: ft.Page | None, is_maximized: bool | None = None
    ) -> tuple[float, float]:
        """Recupera com precisão a largura e altura reais do viewport ou janela."""
        if page is None:
            return float(BASE_WIDTH), float(BASE_HEIGHT)

        pw = getattr(page, "width", None)
        ph = getattr(page, "height", None)
        if pw and pw > 200 and ph and ph > 200:
            return float(pw), float(ph)

        if is_maximized is None:
            window = getattr(page, "window", None)
            is_maximized = bool(getattr(window, "maximized", False))

        if is_maximized:
            try:
                import ctypes
                user32 = ctypes.windll.user32
                sw = float(user32.GetSystemMetrics(0))
                sh = float(user32.GetSystemMetrics(1))
                if sw > 200 and sh > 200:
                    return sw, sh
            except Exception:
                pass

        window = getattr(page, "window", None)
        if window is not None:
            ww = getattr(window, "width", None)
            wh = getattr(window, "height", None)
            if ww and ww > 200 and wh and wh > 200:
                return float(ww), float(wh)

        return 1400.0, 900.0

    @staticmethod
    def get_scale(page: ft.Page) -> float:
        """Calcula a escala mínima entre largura e altura disponíveis."""
        return (
            min(
                page.width / BASE_WIDTH,
                page.height / BASE_HEIGHT,
            )
            if page and hasattr(page, "width") and hasattr(page, "height") and page.width and page.height
            else 1
        )

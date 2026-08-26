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
    def get_scale(page: ft.Page) -> float:
        """Calcula a escala mínima entre largura e altura disponíveis."""
        return (
            min(
                page.width / BASE_WIDTH,
                page.height / BASE_HEIGHT,
            )
            if page.width and page.height
            else 1
        )

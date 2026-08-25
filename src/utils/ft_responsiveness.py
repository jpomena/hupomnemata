import flet as ft

BASE_WIDTH = 1280
BASE_HEIGHT = 720


class Responsive:

    @staticmethod
    def font(size: float, scale: float) -> float:
        return size * scale

    @staticmethod
    def space(size: float, scale: float) -> float:
        return size * scale

    @staticmethod
    def get_scale(page: ft.Page) -> float:
        return min(
            page.width / BASE_WIDTH,
            page.height / BASE_HEIGHT,
        ) if page.width and page.height else 1

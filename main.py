import flet as ft
from src.controllers import CoreController


def main(page: ft.Page):
    dark_theme = True
    CoreController(page, dark_theme=dark_theme).start()


if __name__ == '__main__':
    ft.run(main)

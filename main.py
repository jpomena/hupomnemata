import flet as ft
from src.controllers import CoreController


def main(page: ft.Page):
    CoreController(page).start()


if __name__ == '__main__':
    ft.run(main)

import flet as ft

from src.configs.settings import ASSETS_DIR
from src.controllers import CoreController


def main(page: ft.Page):
    CoreController(page).start()


if __name__ == '__main__':
    ft.run(main, assets_dir=str(ASSETS_DIR))

import flet as ft

from src.configs.settings import ASSETS_DIR
from src.controllers import CoreController
from src.db.bootstrap import bootstrap_user_environment
from src.utils.flet_patch import apply_flet_patches


def main(page: ft.Page):
    CoreController(page).start()


if __name__ == '__main__':
    bootstrap_user_environment()
    apply_flet_patches()
    ft.run(main, assets_dir=str(ASSETS_DIR))

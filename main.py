import flet as ft
import src.domains  # noqa:F401
import src.strategies  # noqa:F401
import src.utils  # noqa:F401
from src.db.db import init_db
from src.views.core import main


if __name__ == '__main__':
    init_db()

    ft.run(main)

"""Ponto de entrada da interface da aplicação."""

import flet as ft

from src.controllers import CoreController


def main(page: ft.Page) -> None:
    """Inicia a aplicação usando o controlador principal."""
    CoreController(page).start()

"""Utilitários compartilhados para o CompilationHubComposer."""

from typing import TypeVar
import flet as ft

EventControl = TypeVar('EventControl', bound=ft.Control)


def _control_list(*controls: ft.Control) -> list[ft.Control]:
    """Converte argumentos variáveis de controles em uma lista mutável."""
    return list(controls)

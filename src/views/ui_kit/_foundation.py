"""Escala, pesos tipográficos e transparência.

Extraído de ``src/views/ui_kit.py``; a fachada reexporta a API pública.
"""

import flet as ft

_SCALE = 1.0

W400 = ft.FontWeight.W_400

W500 = ft.FontWeight.W_500

W600 = ft.FontWeight.W_600

W700 = ft.FontWeight.W_700

UI_TRACKING = -0.08


def set_scale(scale: float) -> None:
    global _SCALE
    _SCALE = max(0.6, min(float(scale or 1.0), 1.6))


def s(value: float) -> float:
    """Aplica a escala da interface a um tamanho em pixels."""
    return round(value * _SCALE, 2)


def alpha(color: str, opacity: float) -> str:
    return ft.Colors.with_opacity(opacity, color)

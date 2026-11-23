"""Curvas e durações canônicas de movimento.

Extraído de ``src/views/ui_kit.py``; a fachada reexporta a API pública.
"""

import flet as ft

MOTION_INSTANT = 90

MOTION_FAST = 180

MOTION_BASE = 360

MOTION_SLOW = 720


def motion(duration: int = MOTION_FAST, curve: ft.AnimationCurve | None = None) -> ft.Animation:
    """Animação implícita padrão para cores, bordas, opacidade e escala."""
    return ft.Animation(duration, curve or ft.AnimationCurve.EASE_OUT)


def fade(duration: int = MOTION_FAST) -> ft.Animation:
    """Animação de opacidade com entrada suave."""
    return ft.Animation(duration, ft.AnimationCurve.EASE_OUT)

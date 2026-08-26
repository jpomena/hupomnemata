"""Mapeamento de nomes de configuração para ícones do Flet."""

import flet as ft

ICON_MAP = {
    "book_outlined": ft.Icons.BOOK_OUTLINED,
    "note_outlined": ft.Icons.NOTE_OUTLINED,
    "hub_outlined": ft.Icons.HUB_OUTLINED,
    "upload_file": ft.Icons.UPLOAD_FILE,
    "edit_note": ft.Icons.EDIT_NOTE,
    "menu_book": ft.Icons.MENU_BOOK,
    "hub": ft.Icons.HUB,
    "dashboard": ft.Icons.DASHBOARD_OUTLINED,
    "library": ft.Icons.LIBRARY_BOOKS_OUTLINED,
    "search": ft.Icons.SEARCH,
    "settings": ft.Icons.SETTINGS_OUTLINED,
    "bookmark": ft.Icons.BOOKMARK_BORDER,
    "label": ft.Icons.LABEL_OUTLINE,
    "share": ft.Icons.SHARE_OUTLINED,
    "download": ft.Icons.DOWNLOAD_OUTLINED,
    "analytics": ft.Icons.ANALYTICS_OUTLINED,
    "thrash": ft.Icons.RESTORE_FROM_TRASH_OUTLINED,
}


def get_icon(icon_name: str, fallback: ft.IconData = ft.Icons.CIRCLE):
    """Retorna o ícone configurado ou um fallback conhecido."""
    return ICON_MAP.get(icon_name, fallback)

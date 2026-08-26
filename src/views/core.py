import flet as ft
from src.utils import ControlsUtils as Utils
from src.utils import Responsive
from src.views.work_insert_modal import create_book_modal
from src.configs.settings import (
    FONTS,
    COLORS,
    TEXTS,
    CORE_MENUS,
    PAGE_FONTS,
    MAIN_VIEW_CARDS,
)

ICON_MAP = {
    # Existing core menu and card icons
    'book_outlined': ft.Icons.BOOK_OUTLINED,
    'note_outlined': ft.Icons.NOTE_OUTLINED,
    'hub_outlined': ft.Icons.HUB_OUTLINED,

    # Main View Practical Cards & General Actions
    'upload_file': ft.Icons.UPLOAD_FILE,
    'edit_note': ft.Icons.EDIT_NOTE,
    'menu_book': ft.Icons.MENU_BOOK,
    'hub': ft.Icons.HUB,

    # Navigation & Sidebar Icons
    'dashboard': ft.Icons.DASHBOARD_OUTLINED,
    'library': ft.Icons.LIBRARY_BOOKS_OUTLINED,
    'search': ft.Icons.SEARCH,

    # Utilities & Actions
    'settings': ft.Icons.SETTINGS_OUTLINED,
    'bookmark': ft.Icons.BOOKMARK_BORDER,
    'label': ft.Icons.LABEL_OUTLINE,
    'share': ft.Icons.SHARE_OUTLINED,
    'download': ft.Icons.DOWNLOAD_OUTLINED,
    'analytics': ft.Icons.ANALYTICS_OUTLINED,
    'thrash': ft.Icons.RESTORE_FROM_TRASH_OUTLINED
}


def main(page: ft.Page):
    book_modal = create_book_modal(page)

    def btn_click(e):
        page.show_dialog(book_modal)

    scale = Responsive.get_scale(page)
    page.fonts = PAGE_FONTS
    page.theme = ft.Theme(font_family=FONTS['cormorant'])
    page.title = f'{TEXTS['app']['name']} {TEXTS['app']['version']}'

    page.padding = 0

    page.window.width = 1600
    page.window.height = 900
    page.window.resizable = True

    # ============================================================
    # Cabeçalho da área principal
    # ============================================================

    main_view_title = ft.Text(
        TEXTS['app']['main_view_title'],
        weight=ft.FontWeight.W_700,
        color=COLORS['text'],
        font_family=FONTS['cormorant'],
        size=32,
    )

    main_view_subtitle = ft.Text(
        TEXTS['app']['main_view_subtitle'],
        weight=ft.FontWeight.W_500,
        color=COLORS['muted'],
        font_family=FONTS['montserrat'],
        size=12,
    )

    main_view_header = ft.Container(
        content=ft.Row(
            controls=[
                ft.Column(
                    controls=[
                        main_view_title,
                        main_view_subtitle
                    ],
                    spacing=2,
                    alignment=ft.MainAxisAlignment.CENTER
                ),
                ft.Column(
                    controls=[
                        ft.ElevatedButton(
                            ft.Text(
                                '+ Inserir Nova Obra',
                                weight=ft.FontWeight.BOLD,
                                font_family=FONTS['montserrat'],
                                color=COLORS['text']
                            ),
                            bgcolor=COLORS['gold'],
                            on_click=btn_click,
                        )
                    ],
                    alignment=ft.MainAxisAlignment.CENTER
                )
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER
        ),
        padding=ft.Padding.only(left=30, right=30, top=15, bottom=5)
    )

    # ============================================================
    # Sidebar - Branding
    # ============================================================

    sb_branding_area = ft.Container(
        padding=20,
        bgcolor=COLORS['surface'],
        content=ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Text(
                            TEXTS['app']['name_normalized'],
                            size=28,
                            weight=ft.FontWeight.BOLD,
                            color=COLORS['text'],
                            font_family=FONTS['greek'],
                            style=ft.TextStyle(letter_spacing=4),
                        )
                    ],
                    spacing=8,
                ),
                ft.Text(
                    TEXTS['app']['slogan'],
                    align=ft.Alignment.BOTTOM_CENTER,
                    font_family=FONTS['cormorant'],
                    color=COLORS['muted'],
                    style=ft.TextStyle(letter_spacing=3),
                    size=14,
                    weight=ft.FontWeight.BOLD,
                ),
            ],
            spacing=6,
        ),
    )

    # ============================================================
    # Sidebar - Navegação
    # ============================================================

    sb_navigation_area = ft.Container(
        content=ft.Column(
            controls=[
                ft.Text(
                    'Cadernos',
                    font_family=FONTS['montserrat'],
                    size=12,
                    color=COLORS['muted'],
                ),
                *[
                    Utils.create_sidebar_menu(
                        label_ref=label,
                        icon_data=ICON_MAP.get(
                            icon_data,
                            ft.Icons.CIRCLE
                        ),
                        scale=scale
                    )
                    for label, icon_data in CORE_MENUS.items()
                ],
            ],
            spacing=4,
            expand=True,
        ),
        padding=15,
        expand=True,
    )

    # ============================================================
    # Sidebar - Rodapé
    # ============================================================

    sb_footnote_area = ft.Container(
        content=ft.Row(
            controls=[
                ft.Text(
                    TEXTS['messages']['placeholder_citation'],
                    size=18 * scale,
                    color=COLORS['muted'],
                    font_family=FONTS['cormorant'],
                    align=ft.Alignment.CENTER_LEFT,
                    text_align=ft.TextAlign.JUSTIFY,
                    no_wrap=False,
                    expand=True,
                    weight=ft.FontWeight.W_600
                ),
            ],
            height=300 * scale,
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
        padding=15,
        border=ft.Border(
            top=ft.BorderSide(1, COLORS['border'])
        ),
    )

    # ============================================================
    # Sidebar
    # ============================================================

    sidebar = ft.Container(
        width=300,
        bgcolor=COLORS['surface'],
        border=ft.Border(
            right=ft.BorderSide(1, COLORS['border'])
        ),
        content=ft.Column(
            controls=[
                sb_branding_area,
                sb_navigation_area,
                sb_footnote_area,
            ],
            spacing=0,
            alignment=ft.MainAxisAlignment.START,
            expand=True,
        ),
    )

    # ============================================================
    # Cards da Main View
    # ============================================================

    grid_cards = ft.ResponsiveRow(
        controls=[
            ft.Container(
                content=Utils.create_main_view_card(
                    label_str=title,
                    icon_data=ICON_MAP.get(
                        data['icon'],
                        ft.Icons.HELP_OUTLINE,
                    ),
                    description_str=data['description'],
                    scale=scale
                ),
                col={
                    'xs': 12,
                    'sm': 6,
                    'md': 4,
                    'lg': 3,
                },
            )
            for title, data in MAIN_VIEW_CARDS.items()
        ],
        spacing=20,
        run_spacing=20,
    )

    # ============================================================
    # Área principal
    # ============================================================

    content_area = ft.Container(
        expand=True,
        padding=ft.Padding(top=10, right=0, bottom=0, left=0),
        bgcolor=COLORS['surface'],
        content=ft.Column(
            controls=[
                main_view_header,
                ft.Container(
                    content=grid_cards,
                    border=ft.Border(top=ft.BorderSide(1, COLORS['border'])),
                    padding=50,
                    expand=True,
                    bgcolor=COLORS['bg']
                )
            ],
            spacing=10,
            expand=True
        ),
    )

    # ============================================================
    # Layout principal
    # ============================================================

    page.add(
        ft.Row(
            controls=[
                sidebar,
                content_area,
            ],
            expand=True,
            spacing=0,
            vertical_alignment=ft.CrossAxisAlignment.STRETCH,
        )
    )

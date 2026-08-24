import flet as ft
import yaml
from pathlib import Path
from typing import TypedDict


class MessagesSchema(TypedDict):
    welcome: str


class AppSchema(TypedDict):
    app: dict
    messages: MessagesSchema


def main(page: ft.Page):
    texts_file_path = Path("src") / "assets" / "texts.yaml"

    with open(texts_file_path, 'r', encoding='utf-8') as file:
        TEXTS = yaml.safe_load(file)

    page.title = f'{TEXTS['app']['name']} {TEXTS['app']['version']}'
    page.padding = 20

    page.add(ft.Text(
        TEXTS['messages']['welcome'],
        text_align=ft.TextAlign.JUSTIFY,
        size=16
    ))


ft.app(target=main)

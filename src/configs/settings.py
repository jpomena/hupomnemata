import yaml
import json
import flet as ft
from pathlib import Path

CONFIG_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CONFIG_DIR.parents[1]
parameters_path = CONFIG_DIR / 'params.json'
with open(parameters_path, 'r', encoding='utf-8') as file:
    parameters = json.load(file)

texts_file_path = CONFIG_DIR / 'texts.yaml'
with open(texts_file_path, 'r', encoding='utf-8') as file:
    TEXTS = yaml.safe_load(file)

PART_IDENTIFIERS = parameters['PART_IDENTIFIERS']

PHYSICAL_ATTRIBUTES = parameters['PHYSICAL_ATTRIBUTES']

COLORS = parameters['COLORS']

CORE_MENUS = parameters['CORE_MENUS']

FONTS_CONFIGS = parameters['FONTS']
TYPOGRAPHY = parameters['TYPOGRAPHY']
UI = parameters['UI']
FONT_WEIGHT = {
    key: getattr(ft.FontWeight, value)
    for key, value in TYPOGRAPHY['weights'].items()
}
FONT_SIZE = TYPOGRAPHY['sizes']
FONTS = {}
PAGE_FONTS = {}
for key, config in FONTS_CONFIGS.items():
    FONTS[key] = config['name']
    PAGE_FONTS[config['name']] = str(
        PROJECT_ROOT / 'assets' / config['path']
    )

MAIN_VIEW_CARDS = parameters['MAIN_VIEW_CARDS']

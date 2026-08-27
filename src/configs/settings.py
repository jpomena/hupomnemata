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

FONT_CONFIG = parameters['FONTS']
ICON_SIZES = parameters['ICON_SIZES']
UI = parameters['UI']
FONT_FAMILIES = {}
PAGE_FONTS = {}
for key, config in FONT_CONFIG.items():
    FONT_FAMILIES[key] = config['name']
    PAGE_FONTS[config['name']] = str(
        PROJECT_ROOT / 'assets' / config['path']
    )

FONT_SIZES = {
    f'{family}_{size_name}': size
    for family, config in FONT_CONFIG.items()
    for size_name, size in config.get('sizes', {}).items()
}

FONT_WEIGHTS = {
    f'{family}_{weight_name}': getattr(ft.FontWeight, weight)
    for family, config in FONT_CONFIG.items()
    for weight_name, weight in config.get('weights', {}).items()
}

MAIN_VIEW_CARDS = parameters['MAIN_VIEW_CARDS']

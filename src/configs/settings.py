import yaml
import json
from pathlib import Path

parameters_path = Path('src') / 'configs' / 'params.json'
with open(parameters_path, 'r', encoding='utf-8') as file:
    parameters = json.load(file)

texts_file_path = Path('src') / 'configs' / 'texts.yaml'
with open(texts_file_path, 'r', encoding='utf-8') as file:
    TEXTS = yaml.safe_load(file)

PART_IDENTIFIERS = parameters['PART_IDENTIFIERS']

PHYSICAL_ATTRIBUTES = parameters['PHYSICAL_ATTRIBUTES']

COLORS = parameters['COLORS']

CORE_MENUS = parameters['CORE_MENUS']

FONTS_CONFIGS = parameters['FONTS']
FONTS = {}
PAGE_FONTS = {}
for key, config in FONTS_CONFIGS.items():
    FONTS[key] = config['name']
    PAGE_FONTS[config['name']] = config['path']

MAIN_VIEW_CARDS = parameters['MAIN_VIEW_CARDS']

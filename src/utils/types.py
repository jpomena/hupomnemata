from typing import List
from enum import Enum
from dataclasses import dataclass


PHYSICAL_ATTRIBUTES = {
    'page_quantity': ' p.',
    'volumes': ' v.',
    'illustrations': ' il.',
    'dimensions': ''
}


PART_IDENTIFIERS = {
    'part_volume',
    'part_chapter_number',
    'part_start_page',
    'part_end_page'
}


class TextStyle(str, Enum):
    NORMAL = 'normal'
    BOLD = 'bold'
    ITALIC = 'italic'


@dataclass
class ReferencePart:
    content: str
    style: TextStyle = TextStyle.NORMAL


@dataclass
class ViewReference:
    parts: List[ReferencePart]

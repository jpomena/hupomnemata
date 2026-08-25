from typing import List
from enum import Enum
from dataclasses import dataclass


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

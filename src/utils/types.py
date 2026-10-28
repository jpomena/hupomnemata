import flet as ft
from typing import List, Any
from enum import Enum
from dataclasses import dataclass


WORK_TYPE_LABELS = {
    "EditorialMonograph": "Livros em geral",
    "AcademicMonograph": "Trabalho acadêmico",
    "CorrespondenceMonograph": "Correspondência",
    "PeriodicalCollection": "Coleção periódica",
    "Magazine": "Revista",
    "JournalArticle": "Artigo de revista",
    "NewspaperArticle": "Artigo de jornal",
    "MonographicProceedings": "Anais de evento em volume único",
    "PeriodicalProceedings": "Anais de evento em periódico",
    "Patent": "Patente",
    "Statute": "Legislação",
    "CaseLaw": "Jurisprudência",
    "MiscellaneousDigitalDocument": "Documento digital",
    "AudiovisualDocument": "Audiovisual",
    "AudioDocument": "Áudio",
    "MusicalScore": "Partitura",
    "VisualDocument": "Documento visual",
    "CartographicDocument": "Cartográfico",
    "ThreeDimensionalDocument": "Tridimensional",
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


@dataclass(frozen=True)
class ViewConfig:
    """Agrupa os parametros visuais carregados pelo ponto de composicao."""

    colors: dict[str, Any]
    font_families: dict[str, str]
    page_fonts: dict[str, str]
    font_sizes: dict[str, int | float]
    icon_sizes: dict[str, int | float]
    font_weights: dict[str, ft.FontWeight]
    ui: dict[str, int | float]
    texts: dict[str, dict[str, str]]
    core_menus: dict[str, str]
    main_view_cards: dict[str, dict[str, str]]

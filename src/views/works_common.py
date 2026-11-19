"""Definições compartilhadas do Acervo.

Extraídas de ``works.py`` para eliminar o ciclo de importação com os mixins:
tanto a fachada ``WorksComposer`` quanto ``works_table``, ``works_toolbar`` e
``works_inspector`` importam daqui, sem depender uns dos outros.
"""

import re
from dataclasses import dataclass, field

from src.domains import BibliographicResource

TYPE_ICONS = {
    "Livros em geral": ("book-open", "solid"),
    "Trabalho acadêmico": ("graduation-cap", "solid"),
    "Correspondência": ("envelope", "regular"),
    "Artigo de revista": ("file-lines", "regular"),
    "Revista": ("book-open-reader", "solid"),
    "Coleção periódica": ("book", "solid"),
    "Artigo de jornal": ("newspaper", "regular"),
    "Anais de evento em volume único": ("calendar-days", "regular"),
    "Anais de evento em periódico": ("calendar-days", "regular"),
    "Legislação": ("gavel", "solid"),
    "Jurisprudência": ("building-columns", "solid"),
    "Patente": ("lightbulb", "regular"),
    "Documento digital": ("file-lines", "regular"),
    "Audiovisual": ("film", "solid"),
    "Áudio": ("music", "solid"),
    "Partitura": ("music", "solid"),
    "Documento visual": ("image", "regular"),
    "Cartográfico": ("map", "regular"),
    "Tridimensional": ("cube", "solid"),
}
MONTHS = [
    "jan", "fev", "mar", "abr", "mai", "jun",
    "jul", "ago", "set", "out", "nov", "dez",
]

# (chave, rótulo, largura fixa ou None = flexível, alinhado à direita)
COLUMNS = [
    ("title", "Título", None, False),
    ("author", "Autoria", None, False),
    ("type", "Tipo", 150, False),
    ("year", "Ano", 80, True),
    ("frag", "Frag.", 52, True),
    ("created", "Adicionada", 104, True),
]


@dataclass
class AcervoContext:
    """Dados de apoio vindos do controller (fragmentos e compilações por obra)."""

    fragments_by_work: dict[int, list[dict]] = field(default_factory=dict)
    compilations_by_work: dict[int, list[tuple[int, str]]] = field(
        default_factory=dict
    )
    compilations: list[tuple[int, str]] = field(default_factory=list)


def author_names(resource: BibliographicResource) -> str:
    """Nomes de autoria como o usuário cadastrou (pessoas e entidades)."""
    names: list[str] = []
    for author in getattr(resource, "authors", None) or []:
        if getattr(author, "corporation", False):
            legal = (author.given_names or author.last_name or "").strip()
            jurisdiction = getattr(author, "jurisdiction", None)
            if jurisdiction is not None:
                place = (
                    jurisdiction.given_names or jurisdiction.last_name or ""
                ).strip()
                if place and place != legal:
                    legal = f"{place}. {legal}" if legal else place
            if legal:
                names.append(legal)
            continue
        full = f"{author.given_names or ''} {author.last_name or ''}".strip()
        if full:
            names.append(full)
    return ", ".join(names)


def format_date(value) -> str:
    if value is None or not hasattr(value, "year"):
        return ""
    return f"{value.day} {MONTHS[value.month - 1]} {value.year}"


def year_sort_key(value: str) -> int:
    match = re.search(r"\d+", str(value or ""))
    number = int(match.group()) if match else 99999
    return -number if "a.C" in str(value or "") else number

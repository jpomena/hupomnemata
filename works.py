from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from enum import Enum


@dataclass
class Author:
    last_name: str
    first_name: str


class YearPrecision(Enum):
    YEAR = "year"
    DECADE = "decade"
    CENTURY = "century"
    MILLENNIUM = "millennium"


@dataclass
class Year:
    value: int
    approximate: bool = False
    precision: YearPrecision = YearPrecision.YEAR


class ReferenceType(Enum):
    BOOK = "book"
    BOOK_PART = "book_part"
    EBOOK = "ebook"
    JOURNAL = "journal"
    JOURNAL_ARTICLE = "journal_article"
    JOURNAL_SECTION = "journal_section"
    NEWSPAPER_ARTICLE = "newspaper_article"
    ACADEMIC = "academic"
    EVENT = "event"
    EVENT_PROCEEDING = "event_proceeding"
    EVENT_PAPER = "event_paper"
    NORMATIVE_DOCUMENT = "normative_document"
    JURISPRUDENCE = "jurisprudence"
    CORRESPONDENCE = "correspondence"
    PATENT = "patent"
    REPORT = "report"
    WEBSITE = "website"
    SOCIAL_MEDIA = "social_media"
    DATABASE = "database"
    AUDIOVISUAL = "audiovisual"
    SPECIAL_DOCUMENT = "special_document" # // Mapas, imagens e objetos 3D.


@dataclass
class Reference:
    title: str
    ref_type: ReferenceType = ReferenceType.BOOK
    authors: list[Author] = field(default_factory=list) # type: ignore
    extra: Dict[str, Any] = field(default_factory=dict) # type: ignore
    year: Optional[Year] = None
    id: Optional[int] = None

    def format_authors(self):
        if not self.authors:
            return ""

        elif len(self.authors) == 1:
            return (
                f"{self.authors[0].last_name.upper()}, "
                f"{self.authors[0].first_name.title()}."
            )

        elif 2 <= len(self.authors) <= 3:
            authors_str = "; ".join(
                f"{author.last_name.upper()}, {author.first_name.title()}"
                for author in self.authors
            )
            return authors_str + "."

        else:
            return (
                f"{self.authors[0].last_name.upper()}, "
                f"{self.authors[0].first_name.title()} et al."
            )

    def format_title(self):
        return f"{self.title}"

    def format_year(self) -> str:
        if self.year is None:
            return ""
        if self.year.precision == YearPrecision.DECADE:
            return f"[{str(self.year.value // 10)}-]"
        if self.year.precision == YearPrecision.CENTURY:
            return f"[{str(self.year.value // 100)}--]"
        if self.year.precision == YearPrecision.MILLENNIUM:
            return f"[{str(self.year.value // 1000)}---]"
        if self.year.approximate:
            return f"[{self.year.value}?]"
        else:
            return str(self.year.value)

    def format_extras(self) -> Dict[str, Any]:
        formatted_extras: Dict[str, Any] = {}
        ref_attributes = [
            'publisher', 'edition', 'url', 'publisher_location',
            'journal_volume', 'journal_number' 'collection', 'translator',
            'organizer', 'coordinator', 'journal', 'start_page', 'end_page',
            'journal_date', 'view_date', 'newspaper_section', 'director',
            'notes', 'container_title',
            'container_authors', 'institute', 'pages', 'delivery_year',
            'defence_year', 'academic_degree', 'collective_entity',
            'conference_name', 'conference_number', 'conference_year',
            'conference_location', 'proceedings_start_page',
            'proceedings_end_page', 'journal_first_volume_year',
            'journal_last_volume_year', 'journal_publication_month',
            'newspaper_day', 'newspaper_month', 'interviewee',
            'interviewer', 'interview_theme', 'media_type',
            'regulator', 'regulation_number', 'regulation_date',
            'regulation_summary', 'rapporteur'
            ]

        for i in ref_attributes:
            if i in self.extra:
                formatted_extras[i] = self.extra[i].lower()

        return formatted_extras


@dataclass
class Citation:
    reference: Reference
    content: str
    loc: str
    note: Optional[str] = None
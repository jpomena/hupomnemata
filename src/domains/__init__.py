from .core_domain import (
    DatePrecision, BibliographicResource, WorkMixin, Author, Authorship
)
from .digital import MiscDigitalDocument
from .monographs import (
    EditorialMonograph, AcademicMonograph, CorrespondenceMonograph
)
from .periodicals import PeriodicalCollection, JournalArticle, NewspaperArticle
from .proceedings import MonographicProceedings, PeriodicalProceedings
from .patent import Patent
from .legal_documents import Statute, CaseLaw
from .multimedia import AudiovisualDocument, AudioDocument, VisualDocument, ThreeDimensionalDocument, CartographicDocument, MusicalScore  # noqa: E501

__all__ = [
    'DatePrecision',
    'BibliographicResource',
    'WorkMixin',
    'Author',
    'Authorship',
    'EditorialMonograph',
    'AcademicMonograph',
    'CorrespondenceMonograph',
    'PeriodicalCollection',
    'JournalArticle',
    'NewspaperArticle',
    'MonographicProceedings',
    'PeriodicalProceedings',
    'Patent',
    'Statute',
    'CaseLaw',
    'AudiovisualDocument',
    'AudioDocument',
    'VisualDocument',
    'ThreeDimensionalDocument',
    'CartographicDocument',
    'MusicalScore',
    'MiscDigitalDocument',
]

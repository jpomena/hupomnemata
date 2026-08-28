from .core_domain import WorkMixin
from sqlalchemy import String, JSON
from sqlalchemy.orm import Mapped, mapped_column
from typing import Dict

'''Documentos, ou parte de documentos, constituídos de uma só parte ou de um
número previamente estabelecido de partes separadas. Por exemplo:
livros; folhetos; obras traduzidas; trabalhos acadêmicos; enciclopédias;
catálogos de exposição; correspondências, anuários, apostilas etc.'''


class EditorialMonograph(WorkMixin):
    '''Documentos monográficos que receberam tratamento
    editorial, e.g.: livros, enciclopédias, dicionários.'''

    __tablename__ = 'editorial_monographs'

    page_quantity: Mapped[int] = mapped_column(nullable=True)
    publication_place: Mapped[str] = mapped_column(
        String(150), nullable=False, default='[s.l.]'
    )
    additional_notes: Mapped[str] = mapped_column(String(500), nullable=True)
    responsabilities: Mapped[Dict[str, str]] = mapped_column(
        JSON, nullable=False
    )
    edition: Mapped[int] = mapped_column(nullable=True)
    publisher: Mapped[str] = mapped_column(
        String(100), nullable=False, default='[s.n.]'
    )
    volumes: Mapped[int] = mapped_column(nullable=True)
    translation_notes: Mapped[str] = mapped_column(String(200), nullable=True)
    original_full_title: Mapped[str] = mapped_column(
        String(500), nullable=True
    )
    dimensions: Mapped[str] = mapped_column(String(10), nullable=True)
    collection_name: Mapped[str] = mapped_column(String(100), nullable=True)
    collection_number: Mapped[int] = mapped_column(nullable=True)
    illustrations: Mapped[bool] = mapped_column(nullable=True)
    isbn: Mapped[str] = mapped_column(String(13), nullable=True)


class AcademicMonograph(WorkMixin):
    '''Documentos monográficos que não receberam tratamento
    editorial, e.g.: TCC's, dissertações, teses.'''

    __tablename__ = 'academic_monographs'

    page_quantity: Mapped[int] = mapped_column(nullable=False)
    publication_place: Mapped[str] = mapped_column(
        String(150), nullable=False, default='[s.l.]'
    )
    additional_notes: Mapped[str] = mapped_column(String(500), nullable=True)
    thesis_type: Mapped[str] = mapped_column(String(50), nullable=False)
    education_level: Mapped[str] = mapped_column(String(15), nullable=False)
    course: Mapped[str] = mapped_column(String(20), nullable=False)
    faculty: Mapped[str] = mapped_column(String(75), nullable=False)
    defense_year: Mapped[int] = mapped_column(nullable=False)


class CorrespondenceMonograph(WorkMixin):
    '''Documentos monográficos de correspondência entre
    duas ou mais pessoas, e.g.: cartas, telegramas, e-mails.'''

    __tablename__ = 'correspondence_monographs'

    publication_place: Mapped[str] = mapped_column(
        String(150), nullable=False, default='[s.l.]'
    )
    additional_notes: Mapped[str] = mapped_column(String(500), nullable=True)
    recipient: Mapped[str] = mapped_column(String(125), nullable=True)
    correspondence_type: Mapped[str] = mapped_column(
        String(25), nullable=False
    )

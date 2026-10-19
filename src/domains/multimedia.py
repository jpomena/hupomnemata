from .core_domain import PartialWorkMixin, WorkMixin
from sqlalchemy import String, JSON
from sqlalchemy.orm import Mapped, mapped_column
from typing import Dict


class AudiovisualDocument(WorkMixin):
    '''Documentos audiovisuais, como vídeos, áudios, gravações.'''

    __tablename__ = 'audiovisual_documents'

    responsibilities: Mapped[Dict[str, str]] = mapped_column(
        JSON, nullable=False
    )
    publication_place: Mapped[str] = mapped_column(
        String(150), nullable=False, default='[s.l.]'
    )
    publisher: Mapped[str] = mapped_column(
        String(100), nullable=False, default='[s.n.]'
    )
    carrier_type: Mapped[str] = mapped_column(String(50), nullable=False)
    additional_notes: Mapped[str] = mapped_column(
        String(500), nullable=True
    )
    seconds: Mapped[int] = mapped_column(nullable=False)
    sound: Mapped[bool] = mapped_column(nullable=False)
    colorized: Mapped[bool] = mapped_column(nullable=False)


class AudioDocument(PartialWorkMixin, WorkMixin):
    '''Inclui disco, CD, podcast, entre outros documentos.'''

    __tablename__ = 'audio_documents'

    responsibilities: Mapped[Dict[str, str]] = mapped_column(
        JSON, nullable=False
    )
    publication_place: Mapped[str] = mapped_column(
        String(150), nullable=False, default='[s.l.]'
    )
    publisher: Mapped[str] = mapped_column(
        String(100), nullable=False, default='[s.n.]'
    )
    carrier_type: Mapped[str] = mapped_column(
        String(15), nullable=False, default=''
    )
    is_partial: Mapped[bool] = mapped_column(nullable=False, default=False)
    part_responsibilities: Mapped[Dict[str, str]] = mapped_column(
        JSON, nullable=False
    )
    part_identifier: Mapped[str] = mapped_column(
        String(50), nullable=False, default=''
    )
    seconds: Mapped[int] = mapped_column(nullable=True)
    physical_details: Mapped[str] = mapped_column(
        String(200), nullable=True
    )
    additional_notes: Mapped[str] = mapped_column(
        String(500), nullable=True
    )


class MusicalScore(PartialWorkMixin, WorkMixin):
    __tablename__ = 'musical_scores'

    instrumentation: Mapped[str] = mapped_column(
        String(50), nullable=False, default=''
    )
    publication_place: Mapped[str] = mapped_column(
        String(150), nullable=False, default='[s.l.]'
    )
    publisher: Mapped[str] = mapped_column(
        String(100), nullable=False, default='[s.n.]'
    )
    author_role: Mapped[str] = mapped_column(String(50), nullable=True)
    physical_description: Mapped[str] = mapped_column(
        String(500), nullable=True
    )
    additional_notes: Mapped[str] = mapped_column(String(500), nullable=True)


class VisualDocument(WorkMixin):
    __tablename__ = 'visual_documents'

    physical_description: Mapped[str] = mapped_column(
        String(500), nullable=True
    )
    additional_notes: Mapped[str] = mapped_column(
        String(500), nullable=True
    )


class CartographicDocument(WorkMixin):
    __tablename__ = 'cartographic_documents'

    edition: Mapped[int] = mapped_column(nullable=True)
    publication_place: Mapped[str] = mapped_column(
        String(150), nullable=False, default='[s.l.]'
    )
    publisher: Mapped[str] = mapped_column(
        String(100), nullable=False, default='[s.n.]'
    )
    physical_description: Mapped[str] = mapped_column(
        String(500), nullable=True
    )
    additional_notes: Mapped[str] = mapped_column(String(500), nullable=True)


class ThreeDimensionalDocument(WorkMixin):
    __tablename__ = 'three_dimensional_documents'

    responsiblity_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default=''
    )
    manufacturing_place: Mapped[str] = mapped_column(
        String(150), nullable=False, default='[s.l.]'
    )
    manufacturer: Mapped[str] = mapped_column(
        String(100), nullable=False, default='[s.n.]'
    )
    physical_description: Mapped[str] = mapped_column(
        String(500), nullable=False, default=''
    )
    additional_notes: Mapped[str] = mapped_column(
        String(500), nullable=True
    )

from .core import WorkMixin
from sqlalchemy import String, JSON
from sqlalchemy.orm import Mapped, mapped_column
from typing import Dict


class AudiovisualDocument(WorkMixin):
    '''Documentos audiovisuais, como vídeos, áudios, gravações.'''

    __tablename__ = 'audiovisual_documents'

    responsabilities: Mapped[Dict[str, str]] = mapped_column(
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


class AudioDocument(WorkMixin):
    '''Inclui disco, CD, podcast, entre outros documentos.'''

    __tablename__ = 'audio_documents'

    responsabilities: Mapped[Dict[str, str]] = mapped_column(
        JSON, nullable=False
    )
    publication_place: Mapped[str] = mapped_column(
        String(150), nullable=False, default='[s.l.]'
    )
    publisher: Mapped[str] = mapped_column(
        String(100), nullable=False, default='[s.n.]'
    )
    carrier_type: Mapped[str] = mapped_column(String(15), nullable=False)
    is_part: Mapped[bool] = mapped_column(nullable=False, default=False)
    part_responsabilities: Mapped[Dict[str, str]] = mapped_column(
        JSON, nullable=False
    )
    part_identifier: Mapped[str] = mapped_column(String(15), nullable=False)


class MusicalScore(WorkMixin):
    __tablename__ = 'musical_scores'

    instrumentation: Mapped[str] = mapped_column(String(50), nullable=False)
    publication_place: Mapped[str] = mapped_column(
        String(150), nullable=False, default='[s.l.]'
    )
    publisher: Mapped[str] = mapped_column(
        String(100), nullable=False, default='[s.n.]'
    )
    additional_notes: Mapped[str] = mapped_column(String(500), nullable=True)


class VisualDocument(WorkMixin):
    __tablename__ = 'visual_documents'


class CartographicDocument(WorkMixin):
    __tablename__ = 'cartographic_documents'

    edition: Mapped[int] = mapped_column(nullable=True)
    publication_place: Mapped[str] = mapped_column(
        String(150), nullable=False, default='[s.l.]'
    )
    publisher: Mapped[str] = mapped_column(
        String(100), nullable=False, default='[s.n.]'
    )
    additional_notes: Mapped[str] = mapped_column(String(500), nullable=True)


class ThreeDimensionalDocument(WorkMixin):
    __tablename__ = 'three_dimensional_documents'

    responsability_type: Mapped[str] = mapped_column(
        String(15), nullable=False
    )
    manufacturing_place: Mapped[str] = mapped_column(
        String(150), nullable=False, default='[s.l.]'
    )
    manufacturer: Mapped[str] = mapped_column(
        String(100), nullable=False, default='[s.n.]'
    )

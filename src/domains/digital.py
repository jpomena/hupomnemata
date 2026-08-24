from .core import WorkMixin
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column


class MiscellaneousDigitalDocument(WorkMixin):
    __tablename__ = 'miscellaneous_digital_documents'

    version: Mapped[int] = mapped_column(nullable=True)
    publication_place: Mapped[str] = mapped_column(
        String(150), nullable=False, default='[s.l.]'
    )
    additional_notes: Mapped[str] = mapped_column(String(500), nullable=True)

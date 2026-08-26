from datetime import date

from .core import WorkMixin
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

'''Patente é o registro do direito do inventor, concedido através de
um documento oficial outorgado pelo Estado chamado carta-patente,
que garante o uso exclusivo, durante certo período, de algo inédito que
ele tenha inventado, criado ou aperfeiçoado.'''


class Patent(WorkMixin):
    __tablename__ = 'patents'

    title: Mapped[str] = mapped_column(
        String(150), nullable=False, default='Patente [...]'
    )
    applicant: Mapped[str] = mapped_column(String(100), nullable=False)
    representative: Mapped[str] = mapped_column(String(100), nullable=True)
    number: Mapped[str] = mapped_column(String(20), nullable=False)
    filing_date: Mapped[date] = mapped_column(nullable=False)
    grant_date: Mapped[date] = mapped_column(nullable=True)

from src.db.db import Base
from datetime import date
from .core_domain import WorkMixin
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column


class LegalMixin(Base):

    publication_media: Mapped[str] = mapped_column(String(100), nullable=False)
    publication_number: Mapped[int] = mapped_column(nullable=True)
    additional_notes: Mapped[str] = mapped_column(String(500), nullable=True)


class Statute(WorkMixin, LegalMixin):
    '''Compreende constituição, emenda constitucional, textos legais
    infraconstitucionais (lei complementar e ordinária, medida provisória,
    decreto em todas as suas formas, resolução do Senado Federal, entre
    outros) e normas emanadas das entidades coletivas públicas e privadas
    (ato normativo, portaria, resolução, ordem de serviço, instrução
    normativa, comunicado, aviso, circular, decisão administrativa, entre
    outras).
    Também Compreende circular, contrato, decreto, ordem de serviço, edital,
    estatuto, ofício, parecer, portaria, regulamento, regimento, entre outros
    documentos.'''

    __tablename__ = 'statutes'


class CaseLaw(WorkMixin, LegalMixin):
    '''Compreende súmula, enunciado, acórdão, sentença, despacho
    entre outros tipos de decisões judiciais.'''

    __tablename__ = 'caselaws'

    panel: Mapped[str] = mapped_column(String(100), nullable=True)
    region: Mapped[str] = mapped_column(String(100), nullable=True)
    decision_type: Mapped[str] = mapped_column(String(50), nullable=False)
    decision_date: Mapped[date] = mapped_column(nullable=False)
    case_number: Mapped[str] = mapped_column(String(50), nullable=True)
    rapporteur: Mapped[str] = mapped_column(String(75), nullable=True)

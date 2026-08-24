from datetime import date
from .core import WorkMixin
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column


class Statute(WorkMixin):
    """Compreende constituição, emenda constitucional, textos legais
    infraconstitucionais (lei complementar e ordinária, medida provisória,
    decreto em todas as suas formas, resolução do Senado Federal, entre
    outros) e normas emanadas das entidades coletivas públicas e privadas
    (ato normativo, portaria, resolução, ordem de serviço, instrução
    normativa, comunicado, aviso, circular, decisão administrativa, entre
    outras)."""

    __tablename__ = 'statutes'

    additional_notes: Mapped[str] = mapped_column(String(500), nullable=True)


class CaseLaw(WorkMixin):
    """Compreende súmula, enunciado, acórdão, sentença, despacho
    entre outros tipos de decisões judiciais."""

    __tablename__ = 'caselaws'

    decision_type: Mapped[str] = mapped_column(String(50), nullable=False)
    decision_date: Mapped[date] = mapped_column(nullable=False)
    case_number: Mapped[str] = mapped_column(String(50), nullable=True)
    rapporteur: Mapped[str] = mapped_column(String(75), nullable=True)

    additional_notes: Mapped[str] = mapped_column(String(500), nullable=True)


class AdministrativeAct(WorkMixin):
    """Compreende circular, contrato, decreto, ordem de serviço, edital,
    estatuto, ofício, parecer, portaria, regulamento, regimento, entre outros
    documentos."""

    __tablename__ = 'administrative_acts'

    additional_notes: Mapped[str] = mapped_column(String(500), nullable=True)

"""Prévia ABNT ao vivo para o diálogo "Nova obra".

Monta um ``BibliographicResource`` transitório (nunca adicionado a uma sessão)
a partir dos valores do formulário, usando o mesmo ``WorkFormService`` do
cadastro, e aplica os formatadores reais de ``src/strategies``. Nada é gravado
no banco.

Partes de outra obra (capítulo, artigo de revista, faixa etc.) dependem dos
dados da obra-pai, que só existem no banco; para elas a prévia aparece depois
de salvar.
"""

import re
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import inspect as sqlalchemy_inspect

from src.contracts import AuthorReference
from src.domains import (
    AcademicMonograph,
    AudioDocument,
    AudiovisualDocument,
    Author,
    Authorship,
    BibliographicResource,
    CartographicDocument,
    CaseLaw,
    CorrespondenceMonograph,
    EditorialMonograph,
    JournalArticle,
    Magazine,
    MiscDigitalDocument,
    MonographicProceedings,
    MusicalScore,
    NewspaperArticle,
    Patent,
    PeriodicalCollection,
    PeriodicalProceedings,
    Statute,
    ThreeDimensionalDocument,
    VisualDocument,
)
from src.services.work_form_service import WorkFormService
from src.utils.normalizers import CoreNormalizer
from src.utils.types import ViewReference

MSG_EMPTY = "Preencha título e ano para ver a referência."
MSG_EMPTY_DATE = "Preencha título e data para ver a referência."
MSG_INCOMPLETE = "Preencha os campos obrigatórios para ver a referência."
MSG_DATE_FORMAT = "Confira as datas para ver a referência."
MSG_AFTER_SAVE = "Prévia disponível após salvar."
MSG_UNAVAILABLE = "Não foi possível montar a prévia com estes dados."

ALWAYS_PARTIAL = {"journal_article", "periodical_collection"}
OPTIONAL_TITLE_TYPES = {"visual_document"}
MULTIMEDIA = WorkFormService.MULTIMEDIA_WORK_TYPES
FULL_DATE_TYPES = {"newspaper_article", "statute", "caselaw"}
DATE_FIELDS = {
    "viewed_at",
    "filing_date",
    "grant_date",
    "decision_date",
    "promulgation_date",
    "publication_date",
}
NUMERIC_FIELDS = {
    "consult_start_year",
    "consult_end_year",
    "edition",
    "page_quantity",
    "volumes",
    "collection_number",
    "first_volume_year",
    "last_volume_year",
    "volume",
    "year_season",
    "number",
    "event_number",
    "event_year",
    "publication_year",
    "publication_number",
    "vol_or_year",
    "version",
    "seconds",
    "defense_year",
}


_LEAKED_NONE = re.compile(r"\bNone\b")


@dataclass
class PreviewResult:
    """Resultado da prévia: a referência ou a mensagem que a substitui."""

    reference: ViewReference | None
    message: str = ""
    error: Exception | None = None

    @property
    def text(self) -> str:
        if self.reference is None:
            return ""
        return reference_text(self.reference)


def reference_text(reference: ViewReference) -> str:
    return "".join(part.content for part in reference.parts).strip()


def format_resource(resource: BibliographicResource) -> ViewReference | None:
    """Despacha o formatador do tipo, como ``WorkControllerMixin.format_reference``.

    Diferente do controller, não registra erro: quem chama decide o que fazer.
    """
    work = resource.specific_work
    if work is None:
        return None
    from src.strategies import (
        AudioFormatter,
        AudiovisualFormatter,
        CartographicFormatter,
        DigitalFormatter,
        LegalDocsFormatter,
        MonographFormatter,
        MusicalScoreFormatter,
        PatentFormatter,
        PeriodicalFormatter,
        ProceedingsFormatter,
        ThreeDimensionalFormatter,
        VisualFormatter,
    )

    if isinstance(
        work, (EditorialMonograph, AcademicMonograph, CorrespondenceMonograph)
    ):
        return MonographFormatter.formatter(resource)
    if isinstance(
        work,
        (PeriodicalCollection, JournalArticle, Magazine, NewspaperArticle),
    ):
        return PeriodicalFormatter.formatter(resource)
    if isinstance(work, (MonographicProceedings, PeriodicalProceedings)):
        return ProceedingsFormatter.formatter(resource)
    if isinstance(work, (Statute, CaseLaw)):
        return LegalDocsFormatter.formatter(work)
    if isinstance(work, MiscDigitalDocument):
        return DigitalFormatter.formatter(work)
    if isinstance(work, AudiovisualDocument):
        return AudiovisualFormatter.formatter(work)
    if isinstance(work, AudioDocument):
        return AudioFormatter.formatter(work)
    if isinstance(work, MusicalScore):
        return MusicalScoreFormatter.formatter(resource)
    if isinstance(work, VisualDocument):
        return VisualFormatter.formatter(work)
    if isinstance(work, CartographicDocument):
        return CartographicFormatter.formatter(work)
    if isinstance(work, ThreeDimensionalDocument):
        return ThreeDimensionalFormatter.formatter(work)
    if isinstance(work, Patent):
        return PatentFormatter.formatter(work)
    return None


def _text(value: object) -> str:
    return str(value or "").strip()


def _valid_date(value: str, fmt: str) -> bool:
    try:
        datetime.strptime(value, fmt)
    except ValueError:
        return False
    return True


def _date_anchor_ready(work_type: str, form_data: dict[str, object]) -> bool:
    """Confere o formato da data principal sem passar pelo log de erros."""
    value = _text(form_data.get("date_anchor"))
    unknown = form_data.get("date_precision") == "Data desconhecida"
    if work_type in MULTIMEDIA:
        return bool(value)
    if work_type == "magazine":
        return True
    if work_type == "periodical_proceedings" and not value:
        value = _text(form_data.get("publication_date"))
        return bool(value) and _valid_date(value, "%d/%m/%Y")
    if not value:
        return unknown
    if work_type == "journal_article":
        return _valid_date(value, "%m/%Y")
    if "/" in value or work_type in FULL_DATE_TYPES:
        return _valid_date(value, "%d/%m/%Y")
    return value.isdigit() and 0 < int(value) <= 9999


def _transient_author(
    reference: AuthorReference,
    normalizer: CoreNormalizer,
) -> Author:
    """Espelha ``WorkRepository._find_or_create_author`` sem tocar no banco."""
    if reference["corporation"]:
        name = normalizer.legal_entity_name_normalizer(reference["name"])
        elements = {
            "given_names": name,
            "last_name": name,
            "given_names_initials": "",
            "last_name_initial": "",
        }
    else:
        parsed = normalizer.natural_name_parser(reference["name"])
        elements = {
            "given_names": parsed.given_names,
            "last_name": parsed.last_name,
            "given_names_initials": parsed.given_names_initials,
            "last_name_initial": parsed.last_name_initial,
        }
    jurisdiction = None
    jurisdiction_name = _text(reference.get("jurisdiction_name"))
    if jurisdiction_name:
        jurisdiction = _transient_author(
            {
                "name": jurisdiction_name,
                "id": None,
                "corporation": True,
                "acronym": None,
                "jurisdiction_id": None,
                "jurisdiction_name": None,
            },
            normalizer,
        )
    author = Author(
        **elements,
        corporation=reference["corporation"],
        acronym=reference["acronym"],
        jurisdiction=jurisdiction,
    )
    _apply_column_defaults(author)
    return author


def _apply_column_defaults(instance: object) -> None:
    """Preenche os padrões escalares das colunas (ex.: ``[s.n.]``).

    No cadastro real eles entram no INSERT; aqui o objeto nunca é gravado.
    """
    mapper = sqlalchemy_inspect(type(instance))
    for prop in mapper.column_attrs:
        column = prop.columns[0]
        default = getattr(column, "default", None)
        if (
            default is not None
            and getattr(default, "is_scalar", False)
            and getattr(instance, prop.key, None) is None
        ):
            setattr(instance, prop.key, default.arg)


def build_transient_resource(
    form_data: dict[str, object],
    form_service: WorkFormService | None = None,
) -> BibliographicResource:
    """Converte os valores do formulário num recurso fora de sessão."""
    service = form_service or WorkFormService()
    payload = service.prepare_payload(form_data)
    work = payload["work_model"](**payload["work_data"])
    _apply_column_defaults(work)
    resource = BibliographicResource()
    setattr(resource, payload["relationship_name"], work)
    for reference in payload["author_names"]:
        resource.authorships.append(
            Authorship(author=_transient_author(reference, service.normalizer))
        )
    return resource


def build_reference_preview(
    form_data: dict[str, object],
    form_service: WorkFormService | None = None,
) -> PreviewResult:
    """Monta a prévia ABNT a partir dos valores atuais do formulário.

    Nunca levanta exceção. Erros inesperados voltam em ``error`` para quem
    chama registrar no log.
    """
    work_type = _text(form_data.get("work_type"))
    try:
        date_kind_full = work_type in FULL_DATE_TYPES or work_type in {
            "journal_article",
            "periodical_proceedings",
        }
        empty_message = MSG_EMPTY_DATE if date_kind_full else MSG_EMPTY
        if work_type in ALWAYS_PARTIAL or form_data.get("is_partial"):
            return PreviewResult(None, MSG_AFTER_SAVE)
        title_optional = work_type in OPTIONAL_TITLE_TYPES
        if not title_optional and not _text(form_data.get("title")):
            return PreviewResult(None, empty_message)
        if not _date_anchor_ready(work_type, form_data):
            has_value = bool(_text(form_data.get("date_anchor")))
            return PreviewResult(
                None, MSG_DATE_FORMAT if has_value else empty_message
            )
        for key in DATE_FIELDS:
            value = _text(form_data.get(key))
            if value and not _valid_date(value, "%d/%m/%Y"):
                return PreviewResult(None, MSG_DATE_FORMAT)
        for key in NUMERIC_FIELDS:
            value = _text(form_data.get(key))
            if value and not value.isdigit():
                return PreviewResult(None, MSG_INCOMPLETE)
    except Exception as error:  # noqa: BLE001 - prévia nunca derruba o diálogo
        return PreviewResult(None, MSG_UNAVAILABLE, error)

    try:
        resource = build_transient_resource(form_data, form_service)
    except (ValueError, TypeError):
        return PreviewResult(None, MSG_INCOMPLETE)
    except Exception as error:  # noqa: BLE001
        return PreviewResult(None, MSG_UNAVAILABLE, error)

    try:
        reference = format_resource(resource)
    except Exception as error:  # noqa: BLE001
        try:
            incomplete = _missing_required(form_data)
        except Exception:  # noqa: BLE001
            incomplete = False
        if incomplete:
            return PreviewResult(None, MSG_INCOMPLETE)
        return PreviewResult(None, MSG_UNAVAILABLE, error)
    if reference is None or not reference_text(reference):
        return PreviewResult(None, MSG_INCOMPLETE)
    if _LEAKED_NONE.search(reference_text(reference)):
        # Formatadores imprimem "None" quando falta um campo. Se faltar um
        # obrigatório, pede o campo; senão mostra o que o cadastro geraria.
        try:
            incomplete = _missing_required(form_data)
        except Exception:  # noqa: BLE001
            incomplete = True
        if incomplete:
            return PreviewResult(None, MSG_INCOMPLETE)
    return PreviewResult(reference)


def _missing_required(form_data: dict[str, object]) -> bool:
    """Usa a mesma regra de obrigatórios do cadastro (sem a obra-pai)."""
    from src.controllers.work_submission_controller import (
        WorkSubmissionController,
    )

    missing = WorkSubmissionController._missing_required_fields(form_data)
    return any(label != "Obra-pai" for label in missing)


__all__ = [
    "PreviewResult",
    "build_reference_preview",
    "build_transient_resource",
    "format_resource",
    "reference_text",
    "MSG_AFTER_SAVE",
    "MSG_EMPTY",
    "MSG_INCOMPLETE",
]

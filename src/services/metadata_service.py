"""Serviço de resolução e mapeamento de metadados bibliográficos remotos (DOI, ISBN, ISSN)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import httpx

from src.contracts import AuthorReference
from src.db.db import SessionLocal
from src.domains import (
    BibliographicResource,
    EditorialMonograph,
    JournalArticle,
    MonographicProceedings,
    NewspaperArticle,
    PeriodicalCollection,
    PeriodicalProceedings,
)


class IdentifierType(str, Enum):
    DOI = "doi"
    ISBN = "isbn"
    ISSN = "issn"
    UNKNOWN = "unknown"


@dataclass
class ImportedMetadata:
    identifier_type: IdentifierType
    raw_identifier: str
    normalized_identifier: str
    work_type: str
    values: dict[str, object]
    authors: list[AuthorReference]
    warnings: list[str] = field(default_factory=list)


# ── Detecção e Normalização ──────────────────────────────────────


DOI_PREFIX_REGEX = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", re.IGNORECASE)
DOI_PATTERN = re.compile(r"^10\.\d{4,9}/[-._;()/:A-Za-z0-9]+$")

ISSN_PREFIX_REGEX = re.compile(r"^(?:issn:\s*)", re.IGNORECASE)
ISSN_FORMATTED_PATTERN = re.compile(r"^\d{4}-\d{3}[\dX]$", re.IGNORECASE)

ISBN_PREFIX_REGEX = re.compile(r"^(?:isbn(?:-1[03])?:\s*)", re.IGNORECASE)


def clean_doi(raw: str) -> str:
    cleaned = DOI_PREFIX_REGEX.sub("", raw.strip()).strip()
    return cleaned


def clean_issn(raw: str) -> str:
    cleaned = ISSN_PREFIX_REGEX.sub("", raw.strip()).strip()
    digits = re.sub(r"[^0-9X]", "", cleaned.upper())
    if len(digits) == 8:
        return f"{digits[:4]}-{digits[4:]}"
    return cleaned.upper()


def clean_isbn(raw: str) -> str:
    cleaned = ISBN_PREFIX_REGEX.sub("", raw.strip()).strip()
    digits = re.sub(r"[^0-9X]", "", cleaned.upper())
    return digits


def detect_identifier(text: str) -> tuple[IdentifierType, str]:
    """Identifica o tipo e retorna a versão limpa do identificador."""
    if not text or not text.strip():
        return IdentifierType.UNKNOWN, ""

    raw = text.strip()

    # Checagem de DOI
    doi = clean_doi(raw)
    if DOI_PATTERN.match(doi):
        return IdentifierType.DOI, doi

    # Checagem de ISSN (8 dígitos, com ou sem hífen)
    issn_clean = clean_issn(raw)
    if ISSN_FORMATTED_PATTERN.match(issn_clean):
        return IdentifierType.ISSN, issn_clean

    # Checagem de ISBN (10 ou 13 dígitos)
    isbn_clean = clean_isbn(raw)
    if len(isbn_clean) in (10, 13):
        return IdentifierType.ISBN, isbn_clean

    return IdentifierType.UNKNOWN, raw


# ── Verificação de Duplicidade no Acervo Local ────────────────────


def check_local_duplicate(
    identifier_type: IdentifierType,
    normalized_id: str,
) -> tuple[int, str] | None:
    """Verifica se uma obra com este identificador já existe no banco de dados local.

    Retorna (resource_id, title) se encontrada, ou None.
    """
    if not normalized_id or identifier_type == IdentifierType.UNKNOWN:
        return None

    try:
        with SessionLocal() as session:
            if identifier_type == IdentifierType.DOI:
                # O DOI costuma constar no campo url ou additional_notes
                resources = (
                    session.query(BibliographicResource).all()
                )
                for res in resources:
                    sw = res.specific_work
                    if sw is None:
                        continue
                    doi_val = getattr(sw, "doi", "") or ""
                    url = getattr(sw, "url", "") or ""
                    notes = getattr(sw, "additional_notes", "") or ""
                    if (
                        (doi_val and clean_doi(doi_val).lower() == normalized_id.lower())
                        or normalized_id.lower() in url.lower()
                        or normalized_id.lower() in notes.lower()
                    ):
                        return res.id, getattr(sw, "title", "Obra sem título")

            elif identifier_type == IdentifierType.ISBN:
                clean_target = clean_isbn(normalized_id)
                for model in (EditorialMonograph, MonographicProceedings):
                    works = session.query(model).filter(model.isbn.isnot(None)).all()
                    for w in works:
                        if clean_isbn(w.isbn or "") == clean_target:
                            res_id = getattr(w, "bib_res_id", None)
                            if res_id is not None:
                                return res_id, getattr(w, "title", "Obra sem título")

            elif identifier_type == IdentifierType.ISSN:
                clean_target = clean_issn(normalized_id)
                for model in (PeriodicalCollection, JournalArticle, NewspaperArticle, PeriodicalProceedings):
                    works = session.query(model).filter(model.issn.isnot(None)).all()
                    for w in works:
                        if clean_issn(w.issn or "") == clean_target:
                            res_id = getattr(w, "bib_res_id", None)
                            if res_id is not None:
                                return res_id, getattr(w, "title", "Obra sem título")
    except Exception:
        # Se ocorrer falha no banco de dados (ex.: durante testes sem migração), não bloquear
        return None

    return None


# ── MetadataService ──────────────────────────────────────────────


class MetadataService:
    """Orquestra a busca de metadados em serviços remotos com fallback e mapeamento."""

    DEFAULT_TIMEOUT = 10.0
    HEADERS = {
        "User-Agent": "Hupomnemata/1.0 (https://github.com/jpomena/hupomnemata; mailto:dev@hupomnemata.local)",
    }

    def resolve(
        self,
        raw_text: str,
        client: httpx.Client | None = None,
    ) -> ImportedMetadata:
        """Ponto de entrada: detecta o formato e executa a busca correspondente."""
        id_type, clean_id = detect_identifier(raw_text)
        if id_type == IdentifierType.DOI:
            return self.fetch_doi(clean_id, client=client)
        if id_type == IdentifierType.ISBN:
            return self.fetch_isbn(clean_id, client=client)
        if id_type == IdentifierType.ISSN:
            return self.fetch_issn(clean_id, client=client)

        raise ValueError(
            "Identificador não reconhecido. Forneça um DOI válido (10.xxxx/...), ISBN (10 ou 13 dígitos) ou ISSN (xxxx-xxxx)."
        )

    # ── DOI ────────────────────────────────────────────────────────

    def fetch_doi(
        self,
        doi: str,
        client: httpx.Client | None = None,
    ) -> ImportedMetadata:
        """Recupera metadados via Content Negotiation em doi.org (CSL-JSON)."""
        clean = clean_doi(doi)
        headers = dict(self.HEADERS)
        headers["Accept"] = "application/vnd.citationstyles.csl+json"

        url = f"https://doi.org/{clean}"
        data: dict[str, Any] = {}

        if client is not None:
            resp = client.get(url, headers=headers, follow_redirects=True, timeout=self.DEFAULT_TIMEOUT)
            if resp.status_code == 404:
                raise ValueError(f"DOI '{clean}' não foi encontrado na base de dados global.")
            resp.raise_for_status()
            data = resp.json()
        else:
            with httpx.Client(timeout=self.DEFAULT_TIMEOUT) as local_client:
                resp = local_client.get(url, headers=headers, follow_redirects=True)
                if resp.status_code == 404:
                    raise ValueError(f"DOI '{clean}' não foi encontrado na base de dados global.")
                resp.raise_for_status()
                data = resp.json()

        return self._map_csl_json(data, raw_doi=doi, normalized_doi=clean)

    def _map_csl_json(
        self,
        data: dict[str, Any],
        raw_doi: str,
        normalized_doi: str,
    ) -> ImportedMetadata:
        csl_type = str(data.get("type", "")).lower()

        # Determinação do tipo de obra no Hupomnemata
        if csl_type in ("journal-article", "article-journal"):
            work_type = "journal_article"
        elif csl_type in ("proceedings-article", "paper-conference"):
            work_type = "periodical_proceedings"
        elif csl_type in ("book", "monograph"):
            work_type = "editorial_monograph"
        elif csl_type in ("chapter", "book-chapter"):
            work_type = "editorial_monograph"
        elif csl_type in ("periodical", "journal"):
            work_type = "periodical_collection"
        else:
            work_type = "journal_article"

        # Título e Subtítulo
        raw_title = data.get("title", "")
        if isinstance(raw_title, list):
            raw_title = raw_title[0] if raw_title else ""
        raw_title = str(raw_title or "").strip()

        raw_subtitle = data.get("subtitle", "")
        if isinstance(raw_subtitle, list):
            raw_subtitle = raw_subtitle[0] if raw_subtitle else ""
        raw_subtitle = str(raw_subtitle or "").strip()

        # Se o subtítulo não veio separado mas há dois-pontos no título
        if not raw_subtitle and ":" in raw_title:
            parts = raw_title.split(":", 1)
            raw_title = parts[0].strip()
            raw_subtitle = parts[1].strip()

        # Autores
        authors: list[AuthorReference] = []
        csl_authors = data.get("author", [])
        if isinstance(csl_authors, list):
            for i, a in enumerate(csl_authors):
                if not isinstance(a, dict):
                    continue
                family = str(a.get("family", "")).strip()
                given = str(a.get("given", "")).strip()
                literal = str(a.get("literal", "")).strip()
                if literal:
                    name = literal
                    is_corp = True
                elif family and given:
                    name = f"{given} {family}"
                    is_corp = False
                elif family:
                    name = family
                    is_corp = False
                elif given:
                    name = given
                    is_corp = False
                else:
                    continue

                authors.append(
                    {
                        "name": name,
                        "id": None,
                        "corporation": is_corp,
                        "acronym": None,
                        "jurisdiction_id": None,
                        "jurisdiction_name": None,
                    }
                )

        # Datas
        date_anchor = ""
        display_year = ""
        issued = data.get("issued", {})
        date_parts = issued.get("date-parts", []) if isinstance(issued, dict) else []
        if date_parts and isinstance(date_parts[0], list):
            parts = date_parts[0]
            year = parts[0] if len(parts) > 0 else None
            month = parts[1] if len(parts) > 1 else 1
            day = parts[2] if len(parts) > 2 else 1
            if year:
                display_year = str(year)
                date_anchor = f"{day:02d}/{month:02d}/{year:04d}"

        # Periódico / Revista / Publicação
        journal_title = str(data.get("container-title", "") or "").strip()
        if isinstance(journal_title, list):
            journal_title = journal_title[0] if journal_title else ""

        publisher = str(data.get("publisher", "") or "").strip()
        volume = str(data.get("volume", "") or "").strip()
        issue = str(data.get("issue", "") or "").strip()

        # Páginas
        page_range = str(data.get("page", "") or "").strip()
        part_start_page = ""
        part_end_page = ""
        if page_range:
            if "-" in page_range:
                p_parts = page_range.split("-", 1)
                part_start_page = p_parts[0].strip()
                part_end_page = p_parts[1].strip()
            else:
                part_start_page = page_range

        # Identificadores complementares
        issn_list = data.get("ISSN", [])
        issn = issn_list[0] if isinstance(issn_list, list) and issn_list else str(issn_list or "")
        issn = clean_issn(issn) if issn else ""

        isbn_list = data.get("ISBN", [])
        isbn = isbn_list[0] if isinstance(isbn_list, list) and isbn_list else str(isbn_list or "")
        isbn = clean_isbn(isbn) if isbn else ""

        values: dict[str, object] = {
            "title": raw_title,
            "subtitle": raw_subtitle or None,
            "doi": normalized_doi,
            "url": f"https://doi.org/{normalized_doi}",
            "date_precision": "Data exata",
        }
        if date_anchor:
            values["date_anchor"] = date_anchor
        if display_year:
            values["display_year"] = display_year
        if publisher:
            values["publisher"] = publisher
        if journal_title:
            values["journal_title"] = journal_title
        if volume:
            values["volume"] = volume
        if issue:
            values["number"] = issue
        if part_start_page:
            values["part_start_page"] = part_start_page
            values["start_page"] = part_start_page
        if part_end_page:
            values["part_end_page"] = part_end_page
            values["end_page"] = part_end_page
        if issn:
            values["issn"] = issn
        if isbn:
            values["isbn"] = isbn

        abstract = str(data.get("abstract", "") or "").strip()
        # Limpar tags HTML/JATS frequentes em abstracts de Crossref
        if abstract:
            clean_abstract = re.sub(r"<[^>]+>", "", abstract).strip()
            values["abstract"] = clean_abstract

        return ImportedMetadata(
            identifier_type=IdentifierType.DOI,
            raw_identifier=raw_doi,
            normalized_identifier=normalized_doi,
            work_type=work_type,
            values=values,
            authors=authors,
        )

    # ── ISBN ───────────────────────────────────────────────────────

    def fetch_isbn(
        self,
        isbn: str,
        client: httpx.Client | None = None,
    ) -> ImportedMetadata:
        """Busca metadados de livro via BrasilAPI com fallback para Open Library."""
        clean = clean_isbn(isbn)

        # 1. Tentar BrasilAPI primeiro (excelente para livros publicados no Brasil)
        brasil_data = self._fetch_brasil_api_isbn(clean, client)
        if brasil_data and brasil_data.get("title"):
            return self._map_brasil_api(brasil_data, raw_isbn=isbn, normalized_isbn=clean)

        # 2. Fallback: Open Library
        ol_data = self._fetch_open_library_isbn(clean, client)
        if ol_data and ol_data.get("title"):
            return self._map_open_library(ol_data, raw_isbn=isbn, normalized_isbn=clean)

        raise ValueError(f"ISBN '{clean}' não foi encontrado na BrasilAPI nem na Open Library.")

    def _fetch_brasil_api_isbn(
        self,
        isbn: str,
        client: httpx.Client | None,
    ) -> dict[str, Any] | None:
        url = f"https://brasilapi.com.br/api/isbn/v1/{isbn}"
        try:
            if client is not None:
                resp = client.get(url, headers=self.HEADERS, timeout=self.DEFAULT_TIMEOUT)
                if resp.status_code == 200:
                    return resp.json()
            else:
                with httpx.Client(timeout=self.DEFAULT_TIMEOUT) as local_client:
                    resp = local_client.get(url, headers=self.HEADERS)
                    if resp.status_code == 200:
                        return resp.json()
        except Exception:
            pass
        return None

    def _map_brasil_api(
        self,
        data: dict[str, Any],
        raw_isbn: str,
        normalized_isbn: str,
    ) -> ImportedMetadata:
        title = str(data.get("title", "") or "").strip()
        subtitle = str(data.get("subtitle", "") or "").strip()
        if not subtitle and ":" in title:
            parts = title.split(":", 1)
            title = parts[0].strip()
            subtitle = parts[1].strip()

        publisher = str(data.get("publisher", "") or "").strip()
        year = data.get("year")
        display_year = str(year) if year else ""
        date_anchor = f"01/01/{int(year):04d}" if year else ""

        authors: list[AuthorReference] = []
        raw_authors = data.get("authors", [])
        if isinstance(raw_authors, list):
            for a_name in raw_authors:
                name_str = str(a_name or "").strip()
                if name_str:
                    authors.append(
                        {
                            "name": name_str,
                            "id": None,
                            "corporation": False,
                            "acronym": None,
                            "jurisdiction_id": None,
                            "jurisdiction_name": None,
                        }
                    )

        values: dict[str, object] = {
            "title": title,
            "subtitle": subtitle or None,
            "isbn": normalized_isbn,
            "date_precision": "Data exata",
        }
        if publisher:
            values["publisher"] = publisher
        if display_year:
            values["display_year"] = display_year
        if date_anchor:
            values["date_anchor"] = date_anchor
        if data.get("page_count"):
            values["page_quantity"] = str(data["page_count"])
        if data.get("dimensions"):
            values["dimensions"] = str(data["dimensions"])
        if data.get("synopsis"):
            values["abstract"] = str(data["synopsis"]).strip()

        return ImportedMetadata(
            identifier_type=IdentifierType.ISBN,
            raw_identifier=raw_isbn,
            normalized_identifier=normalized_isbn,
            work_type="editorial_monograph",
            values=values,
            authors=authors,
        )

    def _fetch_open_library_isbn(
        self,
        isbn: str,
        client: httpx.Client | None,
    ) -> dict[str, Any] | None:
        # Tentar primeiro a API com jscmd=data (traz nomes de autores e editoras sem chaves extras)
        url_data = f"https://openlibrary.org/api/books?bibkeys=ISBN:{isbn}&format=json&jscmd=data"
        try:
            if client is not None:
                resp = client.get(url_data, headers=self.HEADERS, follow_redirects=True, timeout=self.DEFAULT_TIMEOUT)
                if resp.status_code == 200:
                    res_dict = resp.json().get(f"ISBN:{isbn}")
                    if res_dict:
                        return res_dict
            else:
                with httpx.Client(timeout=self.DEFAULT_TIMEOUT) as local_client:
                    resp = local_client.get(url_data, headers=self.HEADERS, follow_redirects=True)
                    if resp.status_code == 200:
                        res_dict = resp.json().get(f"ISBN:{isbn}")
                        if res_dict:
                            return res_dict
        except Exception:
            pass

        url = f"https://openlibrary.org/isbn/{isbn}.json"
        try:
            if client is not None:
                resp = client.get(url, headers=self.HEADERS, follow_redirects=True, timeout=self.DEFAULT_TIMEOUT)
                if resp.status_code == 200:
                    return resp.json()
            else:
                with httpx.Client(timeout=self.DEFAULT_TIMEOUT) as local_client:
                    resp = local_client.get(url, headers=self.HEADERS, follow_redirects=True)
                    if resp.status_code == 200:
                        return resp.json()
        except Exception:
            pass
        return None

    def _map_open_library(
        self,
        data: dict[str, Any],
        raw_isbn: str,
        normalized_isbn: str,
    ) -> ImportedMetadata:
        title = str(data.get("title", "") or "").strip()
        subtitle = str(data.get("subtitle", "") or "").strip()
        if not subtitle and ":" in title:
            parts = title.split(":", 1)
            title = parts[0].strip()
            subtitle = parts[1].strip()

        publishers = data.get("publishers", [])
        publisher = ""
        if isinstance(publishers, list) and publishers:
            p0 = publishers[0]
            publisher = str(p0.get("name", "") if isinstance(p0, dict) else p0).strip()

        publish_date = str(data.get("publish_date", "") or "").strip()
        year_match = re.search(r"\d{4}", publish_date)
        display_year = year_match.group(0) if year_match else ""
        date_anchor = f"01/01/{int(display_year):04d}" if display_year else ""

        authors: list[AuthorReference] = []
        raw_authors = data.get("authors", [])
        if isinstance(raw_authors, list):
            for a in raw_authors:
                name = ""
                if isinstance(a, dict) and "name" in a:
                    name = str(a["name"]).strip()
                elif isinstance(a, str):
                    name = a.strip()
                if name:
                    authors.append(
                        {
                            "name": name,
                            "id": None,
                            "corporation": False,
                            "acronym": None,
                            "jurisdiction_id": None,
                            "jurisdiction_name": None,
                        }
                    )

        values: dict[str, object] = {
            "title": title,
            "subtitle": subtitle or None,
            "isbn": normalized_isbn,
            "date_precision": "Data exata",
        }
        if publisher:
            values["publisher"] = publisher
        if display_year:
            values["display_year"] = display_year
        if date_anchor:
            values["date_anchor"] = date_anchor
        if data.get("number_of_pages"):
            values["page_quantity"] = str(data["number_of_pages"])

        return ImportedMetadata(
            identifier_type=IdentifierType.ISBN,
            raw_identifier=raw_isbn,
            normalized_identifier=normalized_isbn,
            work_type="editorial_monograph",
            values=values,
            authors=authors,
        )

    # ── ISSN ───────────────────────────────────────────────────────

    def fetch_issn(
        self,
        issn: str,
        client: httpx.Client | None = None,
    ) -> ImportedMetadata:
        """Recupera metadados de periódico na API Crossref Journals."""
        clean = clean_issn(issn)
        url = f"https://api.crossref.org/journals/{clean}"

        data: dict[str, Any] = {}
        if client is not None:
            resp = client.get(url, headers=self.HEADERS, follow_redirects=True, timeout=self.DEFAULT_TIMEOUT)
            if resp.status_code == 404:
                raise ValueError(f"ISSN '{clean}' não foi encontrado na base da Crossref Journals.")
            resp.raise_for_status()
            data = resp.json().get("message", {})
        else:
            with httpx.Client(timeout=self.DEFAULT_TIMEOUT) as local_client:
                resp = local_client.get(url, headers=self.HEADERS, follow_redirects=True)
                if resp.status_code == 404:
                    raise ValueError(f"ISSN '{clean}' não foi encontrado na base da Crossref Journals.")
                resp.raise_for_status()
                data = resp.json().get("message", {})

        title = str(data.get("title", "") or "").strip()
        publisher = str(data.get("publisher", "") or "").strip()

        values: dict[str, object] = {
            "title": title,
            "journal_title": title,
            "issn": clean,
            "date_precision": "Data exata",
        }
        if publisher:
            values["publisher"] = publisher

        return ImportedMetadata(
            identifier_type=IdentifierType.ISSN,
            raw_identifier=issn,
            normalized_identifier=clean,
            work_type="periodical_collection",
            values=values,
            authors=[],
        )

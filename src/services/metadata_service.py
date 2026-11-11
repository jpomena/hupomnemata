"""Serviço de resolução e mapeamento de metadados bibliográficos remotos (DOI, ISBN, ISSN)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import httpx
from sqlalchemy import func, select

from src.contracts import AuthorReference
from src.db.db import SessionLocal
from src.domains import (
    BibliographicResource,
    EditorialMonograph,
    JournalArticle,
    Magazine,
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
    parent_work_id: int | None = None
    parent_work_title: str = ""


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


# ── Dicionário Canônico de Locais de Publicação por Editora ─────────────

KNOWN_PUBLISHER_PLACES: dict[str, str] = {
    # Editoras Brasileiras
    "boitempo": "São Paulo",
    "companhia das letras": "São Paulo",
    "companhia de bolso": "São Paulo",
    "editora 34": "São Paulo",
    "zahar": "Rio de Janeiro",
    "jorge zahar": "Rio de Janeiro",
    "record": "Rio de Janeiro",
    "rocco": "Rio de Janeiro",
    "bertrand": "Rio de Janeiro",
    "paz e terra": "Rio de Janeiro",
    "josé olympio": "Rio de Janeiro",
    "nova fronteira": "Rio de Janeiro",
    "civilização brasileira": "Rio de Janeiro",
    "vozes": "Petrópolis",
    "cortez": "São Paulo",
    "brasiliense": "São Paulo",
    "martins fontes": "São Paulo",
    "fgv": "Rio de Janeiro",
    "edusp": "São Paulo",
    "unesp": "São Paulo",
    "fiocruz": "Rio de Janeiro",
    "unb": "Brasília",
    "scielo": "São Paulo",
    "cebrap": "São Paulo",
    "ufmg": "Belo Horizonte",
    "ufrj": "Rio de Janeiro",
    "ufsc": "Florianópolis",
    "ufrgs": "Porto Alegre",
    "loyola": "São Paulo",
    "paulus": "São Paulo",
    "paulinas": "São Paulo",
    "autêntica": "Belo Horizonte",
    "todavia": "São Paulo",
    "iluminuras": "São Paulo",
    "cosac naify": "São Paulo",
    "hedra": "São Paulo",
    "perspectiva": "São Paulo",
    "estação liberdade": "São Paulo",
    "l&pm": "Porto Alegre",
    "lpm": "Porto Alegre",
    "aleph": "São Paulo",
    "intrínseca": "Rio de Janeiro",
    "sextante": "Rio de Janeiro",
    "arqueiro": "Rio de Janeiro",
    "leya": "São Paulo",
    "suma": "São Paulo",
    "conrad": "São Paulo",
    "veneta": "São Paulo",
    "senac": "São Paulo",
    "saraiva": "São Paulo",
    "atlas": "São Paulo",
    "forense": "Rio de Janeiro",
    "revista dos tribunais": "São Paulo",
    "malheiros": "São Paulo",
    "manole": "São Paulo",
    "guanabara koogan": "Rio de Janeiro",
    "artmed": "Porto Alegre",
    "penso": "Porto Alegre",
    "bookman": "Porto Alegre",
    "pearson": "São Paulo",
    "cengage": "São Paulo",
    "mcgraw-hill": "São Paulo",

    # Editoras Internacionais / Acadêmicas
    "elsevier": "Amsterdam",
    "academic press": "San Diego",
    "churchill livingstone": "Edinburgh",
    "mosby": "St. Louis",
    "saunders": "Philadelphia",
    "cell press": "Cambridge, MA",
    "the lancet": "London",
    "springer": "Berlin",
    "nature": "London",
    "macmillan": "London",
    "palgrave": "London",
    "oxford": "Oxford",
    "oup": "Oxford",
    "cambridge": "Cambridge",
    "cup": "Cambridge",
    "harvard": "Cambridge, MA",
    "mit press": "Cambridge, MA",
    "yale": "New Haven",
    "princeton": "Princeton",
    "columbia": "New York",
    "chicago": "Chicago",
    "stanford": "Stanford",
    "california": "Berkeley",
    "johns hopkins": "Baltimore",
    "cornell": "Ithaca",
    "duke": "Durham",
    "indiana university": "Bloomington",
    "minnesota": "Minneapolis",
    "edinburgh university": "Edinburgh",
    "wiley": "Hoboken",
    "blackwell": "Oxford",
    "routledge": "London",
    "taylor & francis": "London",
    "taylor and francis": "London",
    "sage": "Thousand Oaks",
    "ieee": "Piscataway",
    "acm": "New York",
    "american chemical society": "Washington, DC",
    "american physical society": "College Park",
    "american psychological association": "Washington, DC",
    "bmj": "London",
    "plos": "San Francisco",
    "frontiers": "Lausanne",
    "mdpi": "Basel",
    "de gruyter": "Berlin",
    "brill": "Leiden",
    "peter lang": "Bern",
    "edward elgar": "Cheltenham",
    "bloomsbury": "London",
    "penguin": "London",
    "random house": "New York",
    "vintage": "New York",
    "anchor": "New York",
    "knopf": "New York",
    "doubleday": "New York",
    "farrar, straus": "New York",
    "harpercollins": "New York",
    "harper & row": "New York",
    "simon & schuster": "New York",
    "scribner": "New York",
    "houghton mifflin": "Boston",
    "norton": "New York",
    "verso": "London",
    "gallimard": "Paris",
    "seuil": "Paris",
    "minuit": "Paris",
    "puf": "Paris",
    "flammarion": "Paris",
    "albin michel": "Paris",
    "hachette": "Paris",
    "suhrkamp": "Berlin",
    "c.h. beck": "München",
    "hanser": "München",
    "fischer": "Frankfurt am Main",
    "rowohlt": "Hamburg",
    "bompiani": "Milano",
    "feltrinelli": "Milano",
    "einaudi": "Torino",
    "laterza": "Roma",
    "adelphi": "Milano",
    "mulino": "Bologna",
    "fondo de cultura": "Ciudad de México",
    "siglo xxi": "Ciudad de México",
    "alianza": "Madrid",
    "gredos": "Madrid",
    "crítica": "Barcelona",
    "planeta": "Barcelona",
    "anagrama": "Barcelona",
    "taurus": "Madrid",
    "trotta": "Madrid",
    "akal": "Madrid",
}


def clean_city_name(raw_location: str | None) -> str:
    """Extrai o nome canônico da cidade de uma string de localização."""
    if not raw_location:
        return ""
    loc = raw_location.strip()
    if not loc or loc.lower() in ("[s.l.]", "[s.l]", "s.l.", "unknown"):
        return ""
    parts = [p.strip() for p in re.split(r"[,;\-–/]", loc) if p.strip()]
    if parts:
        first = parts[0]
        if len(first) > 2 and first.upper() not in ("SP", "RJ", "MG", "RS", "PR", "SC", "BA", "DF", "UK", "US", "USA"):
            return first
    return loc


def deduce_publisher_place(publisher_name: str | None) -> str | None:
    """Deduz a cidade sede de uma editora conhecida."""
    if not publisher_name:
        return None
    name_clean = publisher_name.lower().strip()
    for pub_pattern, city in KNOWN_PUBLISHER_PLACES.items():
        if pub_pattern in name_clean:
            return city
    return None


def find_or_create_magazine(title: str, publication_place: str = "[s.l.]") -> tuple[int, str]:
    """Localiza uma Revista cadastrada pelo título ou cria uma nova se inexistente."""
    cleaned_title = (title or "").strip()
    if not cleaned_title:
        raise ValueError("Título da revista não pode ser vazio.")
    cleaned_place = clean_city_name(publication_place)
    place = cleaned_place or (publication_place or "").strip() or "[s.l.]"

    with SessionLocal() as session:
        stmt = (
            select(BibliographicResource.id, Magazine.title)
            .join(Magazine, Magazine.bib_res_id == BibliographicResource.id)
            .where(func.lower(Magazine.title) == func.lower(cleaned_title))
        )
        row = session.execute(stmt).first()
        if row is not None:
            mag_id, mag_title = row[0], row[1]
            if place != "[s.l.]":
                mag_obj = session.get(Magazine, mag_id)
                if mag_obj and (not mag_obj.publication_place or mag_obj.publication_place == "[s.l.]"):
                    mag_obj.publication_place = place
                    session.commit()
            return mag_id, mag_title

        resource = BibliographicResource()
        magazine = Magazine(
            title=cleaned_title,
            publication_place=place,
            display_year="[s.d.]",
        )
        resource.magazine = magazine
        session.add(resource)
        session.commit()
        session.refresh(resource)
        return resource.id, magazine.title


# ── MetadataService ──────────────────────────────────────────────


class MetadataService:
    """Orquestra a busca de metadados em serviços remotos com fallback e mapeamento."""

    DEFAULT_TIMEOUT = 10.0
    HEADERS = {
        "User-Agent": "Hupomnemata/1.0 (https://github.com/jpomena/hupomnemata; mailto:dev@hupomnemata.local)",
    }
    _MEMBER_CACHE: dict[str, str] = {}

    def _get_member_location(self, member_id: str, client: httpx.Client | None = None) -> str:
        """Consulta a localização (cidade/país) da editora membro no Crossref."""
        if not member_id:
            return ""
        if member_id in self._MEMBER_CACHE:
            return self._MEMBER_CACHE[member_id]
        url = f"https://api.crossref.org/members/{member_id}"
        try:
            if client is not None:
                resp = client.get(url, headers=self.HEADERS, follow_redirects=True, timeout=self.DEFAULT_TIMEOUT)
                if resp.status_code == 200:
                    loc = str(resp.json().get("message", {}).get("location", "") or "").strip()
                    self._MEMBER_CACHE[member_id] = loc
                    return loc
            else:
                with httpx.Client(timeout=self.DEFAULT_TIMEOUT) as local_client:
                    resp = local_client.get(url, headers=self.HEADERS, follow_redirects=True)
                    if resp.status_code == 200:
                        loc = str(resp.json().get("message", {}).get("location", "") or "").strip()
                        self._MEMBER_CACHE[member_id] = loc
                        return loc
        except Exception:
            pass
        return ""

    def resolve(
        self,
        raw_text: str,
        client: httpx.Client | None = None,
        auto_provision_magazine: bool = True,
    ) -> ImportedMetadata:
        """Ponto de entrada: detecta o formato e executa a busca correspondente."""
        id_type, clean_id = detect_identifier(raw_text)
        metadata: ImportedMetadata
        if id_type == IdentifierType.DOI:
            metadata = self.fetch_doi(clean_id, client=client)
        elif id_type == IdentifierType.ISBN:
            metadata = self.fetch_isbn(clean_id, client=client)
        elif id_type == IdentifierType.ISSN:
            metadata = self.fetch_issn(clean_id, client=client)
        else:
            raise ValueError(
                "Identificador não reconhecido. Forneça um DOI válido (10.xxxx/...), ISBN (10 ou 13 dígitos) ou ISSN (xxxx-xxxx)."
            )

        if (
            auto_provision_magazine
            and getattr(metadata, "work_type", None) == "journal_article"
            and not getattr(metadata, "parent_work_id", None)
        ):
            values = getattr(metadata, "values", {}) or {}
            journal_title = values.get("journal_title")
            if journal_title:
                try:
                    pub_place = str(
                        values.get("publication_city")
                        or values.get("publication_place")
                        or "[s.l.]"
                    )
                    mag_id, mag_title = find_or_create_magazine(str(journal_title), pub_place)
                    metadata.parent_work_id = mag_id
                    metadata.parent_work_title = mag_title
                except Exception as exc:
                    warnings = getattr(metadata, "warnings", None)
                    if isinstance(warnings, list):
                        warnings.append(f"Não foi possível auto-provisionar a revista: {exc}")

        return metadata

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
        year_season = ""

        # Inspecionar múltiplos contêineres de data da Crossref em ordem de especificidade
        date_parts = None
        for date_key in ("published-print", "issued", "published-online", "published", "created"):
            d_val = data.get(date_key)
            if isinstance(d_val, dict):
                dp = d_val.get("date-parts")
                if dp and isinstance(dp, list) and len(dp) > 0 and isinstance(dp[0], list) and len(dp[0]) > 0:
                    if dp[0][0]:  # tem ano válido
                        date_parts = dp
                        break

        if date_parts and isinstance(date_parts[0], list):
            parts = date_parts[0]
            year = parts[0] if len(parts) > 0 else None
            month = parts[1] if len(parts) > 1 else 1
            day = parts[2] if len(parts) > 2 else 1
            if year:
                display_year = str(year)
                year_season = str(year)
                if work_type == "journal_article":
                    date_anchor = f"{month:02d}/{year:04d}"
                elif work_type in ("editorial_monograph", "academic_monograph"):
                    date_anchor = str(year)
                elif work_type == "periodical_proceedings":
                    date_anchor = f"{day:02d}/{month:02d}/{year:04d}"
                else:
                    date_anchor = f"{day:02d}/{month:02d}/{year:04d}"

        # Periódico / Revista / Publicação
        journal_title = str(data.get("container-title", "") or "").strip()
        if isinstance(journal_title, list):
            journal_title = journal_title[0] if journal_title else ""

        journal_subtitle = ""
        if ":" in journal_title:
            j_parts = journal_title.split(":", 1)
            journal_title = j_parts[0].strip()
            journal_subtitle = j_parts[1].strip()

        publisher = str(data.get("publisher", "") or "").strip()
        raw_place = str(data.get("publisher-place", "") or "").strip()
        if not raw_place:
            raw_place = str(data.get("event-place", "") or "").strip()

        publisher_place = clean_city_name(raw_place)
        if not publisher_place and publisher:
            publisher_place = deduce_publisher_place(publisher) or ""

        # Fallback para localização do membro Crossref
        if not publisher_place and data.get("member"):
            mem_id = str(data.get("member"))
            mem_loc = self._get_member_location(mem_id, client=None)
            if mem_loc:
                publisher_place = clean_city_name(mem_loc)

        # Fallback para SciELO (prefixo 10.1590)
        if not publisher_place and normalized_doi.startswith("10.1590/"):
            publisher_place = "São Paulo"

        volume = str(data.get("volume", "") or "").strip()
        issue = str(data.get("issue", "") or "").strip()
        if not issue and isinstance(data.get("journal-issue"), dict):
            issue = str(data["journal-issue"].get("issue", "") or "").strip()

        # Páginas / Localizadores
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
        else:
            page_first = str(data.get("page-first", "") or "").strip()
            if page_first:
                part_start_page = page_first
            else:
                article_num = str(data.get("article-number", "") or "").strip()
                if article_num:
                    part_start_page = article_num

        # Identificadores complementares
        issn_list = data.get("ISSN", [])
        issn = issn_list[0] if isinstance(issn_list, list) and issn_list else str(issn_list or "")
        issn = clean_issn(issn) if issn else ""

        isbn_list = data.get("ISBN", [])
        isbn = isbn_list[0] if isinstance(isbn_list, list) and isbn_list else str(isbn_list or "")
        isbn = clean_isbn(isbn) if isbn else ""

        # URL canônica
        raw_url = str(data.get("URL", "") or "").strip()
        url = raw_url if raw_url.startswith("http") else f"https://doi.org/{normalized_doi}"

        values: dict[str, object] = {
            "title": raw_title,
            "subtitle": raw_subtitle or None,
            "doi": normalized_doi,
            "url": url,
            "date_precision": "Data exata",
        }
        if date_anchor:
            values["date_anchor"] = date_anchor
        if display_year:
            values["display_year"] = display_year
        if year_season and work_type == "journal_article":
            values["year_season"] = year_season
        if publisher:
            values["publisher"] = publisher
        if publisher_place:
            values["publication_place"] = publisher_place
            values["publication_city"] = publisher_place
        if journal_title:
            values["journal_title"] = journal_title
        if journal_subtitle:
            values["journal_subtitle"] = journal_subtitle
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

        # Edição
        edition = data.get("edition")
        if edition:
            edition_digits = re.sub(r"\D", "", str(edition))
            if edition_digits:
                values["edition"] = edition_digits

        # Coleção
        coll_name = str(data.get("collection-title", "") or "").strip()
        if coll_name:
            values["collection_name"] = coll_name
        coll_num = data.get("collection-number")
        if coll_num:
            coll_num_digits = re.sub(r"\D", "", str(coll_num))
            if coll_num_digits:
                values["collection_number"] = coll_num_digits

        # Páginas totais (para livros)
        num_pages = data.get("number-of-pages")
        if num_pages:
            num_pages_digits = re.sub(r"\D", "", str(num_pages))
            if num_pages_digits:
                values["page_quantity"] = num_pages_digits

        # Responsabilidades (Editores / Organizadores / Tradutores)
        csl_editors = data.get("editor", [])
        if isinstance(csl_editors, list) and csl_editors:
            ed_names = []
            for ed in csl_editors:
                if isinstance(ed, dict):
                    f = str(ed.get("family", "")).strip()
                    g = str(ed.get("given", "")).strip()
                    lit = str(ed.get("literal", "")).strip()
                    if lit:
                        ed_names.append(lit)
                    elif f and g:
                        ed_names.append(f"{g} {f}")
                    elif f:
                        ed_names.append(f)
            if ed_names:
                values["responsibilities"] = {"Organizador": "; ".join(ed_names)}

        csl_translators = data.get("translator", [])
        if isinstance(csl_translators, list) and csl_translators:
            tr_names = []
            for tr in csl_translators:
                if isinstance(tr, dict):
                    f = str(tr.get("family", "")).strip()
                    g = str(tr.get("given", "")).strip()
                    if f and g:
                        tr_names.append(f"{g} {f}")
                    elif f:
                        tr_names.append(f)
            if tr_names:
                values["translation_notes"] = f"Tradução de {'; '.join(tr_names)}"

        # Evento (para proceedings)
        if work_type == "periodical_proceedings":
            event_name = str(data.get("event-title", "") or "").strip()
            if not event_name and isinstance(data.get("event"), dict):
                event_name = str(data["event"].get("name", "")).strip()
            if event_name:
                values["event_name"] = event_name

            event_place = str(data.get("event-place", "") or "").strip()
            if not event_place and isinstance(data.get("event"), dict):
                event_place = str(data["event"].get("location", "")).strip()
            if event_place:
                values["event_place"] = event_place

            if display_year:
                values["event_year"] = display_year
            if date_anchor:
                values["publication_date"] = date_anchor

        # Abstract e Notas
        abstract = str(data.get("abstract", "") or "").strip()
        if abstract:
            clean_abstract = re.sub(r"<[^>]+>", "", abstract)
            clean_abstract = re.sub(r"\s+", " ", clean_abstract).strip()
            values["abstract"] = clean_abstract

        notes_parts = []
        subjects = data.get("subject", [])
        if isinstance(subjects, list) and subjects:
            clean_subjs = [str(s).strip() for s in subjects if str(s).strip()]
            if clean_subjs:
                notes_parts.append(f"Palavras-chave: {', '.join(clean_subjs[:6])}")

        article_num = str(data.get("article-number", "") or "").strip()
        if article_num and article_num != part_start_page:
            notes_parts.append(f"Artigo nº: {article_num}")

        if notes_parts:
            values["additional_notes"] = " · ".join(notes_parts)

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
        """Busca e coalesce metadados de livro via BrasilAPI e Open Library."""
        clean = clean_isbn(isbn)
        b_meta: ImportedMetadata | None = None
        ol_meta: ImportedMetadata | None = None

        # 1. Tentar BrasilAPI
        try:
            b_data = self._fetch_brasil_api_isbn(clean, client)
            if b_data and (b_data.get("title") or b_data.get("authors")):
                b_meta = self._map_brasil_api(b_data, raw_isbn=isbn, normalized_isbn=clean)
        except Exception:
            pass

        # 2. Tentar Open Library
        # Se for ISBN brasileiro mas faltou autor ou ano ou página no BrasilAPI,
        # ou se não for brasileiro, ou se b_meta não veio, busca OpenLibrary para enriquecimento
        needs_ol = (
            b_meta is None
            or not b_meta.authors
            or not b_meta.values.get("date_anchor")
            or not b_meta.values.get("publication_place")
            or not b_meta.values.get("page_quantity")
        )
        if needs_ol:
            try:
                ol_data = self._fetch_open_library_isbn(clean, client)
                if ol_data and ol_data.get("title"):
                    ol_meta = self._map_open_library(ol_data, raw_isbn=isbn, normalized_isbn=clean, client=client)
            except Exception:
                pass

        if b_meta and ol_meta:
            return self._merge_isbn_metadata(b_meta, ol_meta)
        if b_meta:
            if "publication_place" not in b_meta.values:
                pub = str(b_meta.values.get("publisher", ""))
                deduced = deduce_publisher_place(pub)
                if deduced:
                    b_meta.values["publication_place"] = deduced
                    b_meta.values["publication_city"] = deduced
            return b_meta
        if ol_meta:
            if "publication_place" not in ol_meta.values:
                pub = str(ol_meta.values.get("publisher", ""))
                deduced = deduce_publisher_place(pub)
                if deduced:
                    ol_meta.values["publication_place"] = deduced
                    ol_meta.values["publication_city"] = deduced
            return ol_meta

        raise ValueError(f"ISBN '{clean}' não foi encontrado na BrasilAPI nem na Open Library.")

    def _merge_isbn_metadata(
        self,
        b_meta: ImportedMetadata,
        ol_meta: ImportedMetadata,
    ) -> ImportedMetadata:
        """Funde e enriquece metadados do BrasilAPI e Open Library selecionando o melhor de cada base."""
        b_title = str(b_meta.values.get("title", "") or "").strip()
        ol_title = str(ol_meta.values.get("title", "") or "").strip()
        if b_title.isupper() and ol_title and not ol_title.isupper():
            title = ol_title
        elif ol_title.isupper() and b_title and not b_title.isupper():
            title = b_title
        else:
            title = b_title or ol_title

        subtitle = b_meta.values.get("subtitle") or ol_meta.values.get("subtitle")

        # Autores: BrasilAPI tem prioridade se preenchido; se vazio, OpenLibrary
        authors = list(b_meta.authors) if b_meta.authors else list(ol_meta.authors)
        if b_meta.authors and ol_meta.authors:
            existing_names = {a["name"].lower() for a in b_meta.authors}
            for a in ol_meta.authors:
                if a["name"].lower() not in existing_names:
                    authors.append(a)
                    existing_names.add(a["name"].lower())

        values = dict(b_meta.values)

        for k, v in ol_meta.values.items():
            if v and (k not in values or not values[k]):
                values[k] = v

        values["title"] = title
        if subtitle:
            values["subtitle"] = subtitle

        # Editora
        publisher = values.get("publisher") or ol_meta.values.get("publisher") or b_meta.values.get("publisher")
        if publisher:
            values["publisher"] = publisher

        # Local de publicação
        place = (
            values.get("publication_place")
            or ol_meta.values.get("publication_place")
            or b_meta.values.get("publication_place")
            or deduce_publisher_place(str(publisher or ""))
        )
        if place:
            values["publication_place"] = place
            values["publication_city"] = place

        # Ano / Datas
        date_anchor = values.get("date_anchor") or ol_meta.values.get("date_anchor") or b_meta.values.get("date_anchor")
        if date_anchor:
            values["date_anchor"] = date_anchor
            values["display_year"] = str(values.get("display_year") or date_anchor)

        # Páginas
        pages = values.get("page_quantity") or ol_meta.values.get("page_quantity") or b_meta.values.get("page_quantity")
        if pages and str(pages).isdigit() and int(pages) > 0:
            values["page_quantity"] = str(pages)

        # Abstract / Resumo: escolher o mais detalhado
        b_abs = str(b_meta.values.get("abstract", "") or "").strip()
        ol_abs = str(ol_meta.values.get("abstract", "") or "").strip()
        if len(ol_abs) > len(b_abs):
            values["abstract"] = ol_abs
        elif b_abs:
            values["abstract"] = b_abs

        return ImportedMetadata(
            identifier_type=IdentifierType.ISBN,
            raw_identifier=b_meta.raw_identifier or ol_meta.raw_identifier,
            normalized_identifier=b_meta.normalized_identifier or ol_meta.normalized_identifier,
            work_type="editorial_monograph",
            values=values,
            authors=authors,
        )

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
        date_anchor = str(year) if year else ""

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
        if data.get("page_count") and int(data.get("page_count") or 0) > 0:
            values["page_quantity"] = str(data["page_count"])

        # Localização da publicação
        raw_location = str(data.get("location", "") or "").strip()
        location = clean_city_name(raw_location)
        if not location and publisher:
            location = deduce_publisher_place(publisher) or ""

        if location:
            values["publication_place"] = location
            values["publication_city"] = location

        # Dimensões físicas
        dimensions_val = data.get("dimensions")
        if isinstance(dimensions_val, dict):
            w = dimensions_val.get("width")
            h = dimensions_val.get("height")
            unit = str(dimensions_val.get("unit", "cm")).lower()
            if unit == "centimeter":
                unit = "cm"
            if w and h:
                values["dimensions"] = f"{w} x {h} {unit}"
            elif h:
                values["dimensions"] = f"{h} {unit}"
        elif dimensions_val:
            values["dimensions"] = str(dimensions_val)

        if data.get("synopsis"):
            values["abstract"] = str(data["synopsis"]).strip()

        subjects = data.get("subjects", [])
        if isinstance(subjects, list) and subjects:
            clean_subjs = [str(s).strip() for s in subjects if str(s).strip()]
            if clean_subjs:
                values["additional_notes"] = f"Assuntos: {', '.join(clean_subjs)}"

        return ImportedMetadata(
            identifier_type=IdentifierType.ISBN,
            raw_identifier=raw_isbn,
            normalized_identifier=normalized_isbn,
            work_type="editorial_monograph",
            values=values,
            authors=authors,
        )

    def _fetch_open_library_work(
        self,
        work_key: str,
        client: httpx.Client | None,
    ) -> dict[str, Any] | None:
        if not work_key:
            return None
        clean_key = work_key if work_key.startswith("/") else f"/{work_key}"
        url = f"https://openlibrary.org{clean_key}.json"
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

    def _fetch_open_library_isbn(
        self,
        isbn: str,
        client: httpx.Client | None,
    ) -> dict[str, Any] | None:
        url_data = f"https://openlibrary.org/api/books?bibkeys=ISBN:{isbn}&format=json&jscmd=data"
        res_dict: dict[str, Any] = {}
        try:
            if client is not None:
                resp = client.get(url_data, headers=self.HEADERS, follow_redirects=True, timeout=self.DEFAULT_TIMEOUT)
                if resp.status_code == 200:
                    res_dict = resp.json().get(f"ISBN:{isbn}") or {}
            else:
                with httpx.Client(timeout=self.DEFAULT_TIMEOUT) as local_client:
                    resp = local_client.get(url_data, headers=self.HEADERS, follow_redirects=True)
                    if resp.status_code == 200:
                        res_dict = resp.json().get(f"ISBN:{isbn}") or {}
        except Exception:
            pass

        url_edition = f"https://openlibrary.org/isbn/{isbn}.json"
        try:
            ed_json = None
            if client is not None:
                resp2 = client.get(url_edition, headers=self.HEADERS, follow_redirects=True, timeout=self.DEFAULT_TIMEOUT)
                if resp2.status_code == 200:
                    ed_json = resp2.json()
            else:
                with httpx.Client(timeout=self.DEFAULT_TIMEOUT) as local_client:
                    resp2 = local_client.get(url_edition, headers=self.HEADERS, follow_redirects=True)
                    if resp2.status_code == 200:
                        ed_json = resp2.json()

            if isinstance(ed_json, dict):
                if not res_dict:
                    res_dict = dict(ed_json)
                else:
                    if "works" not in res_dict and "works" in ed_json:
                        res_dict["works"] = ed_json["works"]
                    if "publish_places" not in res_dict and "publish_places" in ed_json:
                        res_dict["publish_places"] = ed_json["publish_places"]
                    if "physical_dimensions" not in res_dict and "physical_dimensions" in ed_json:
                        res_dict["physical_dimensions"] = ed_json["physical_dimensions"]
                    if "series" not in res_dict and "series" in ed_json:
                        res_dict["series"] = ed_json["series"]
                    if "edition_name" not in res_dict and "edition_name" in ed_json:
                        res_dict["edition_name"] = ed_json["edition_name"]
        except Exception:
            pass

        return res_dict if res_dict else None

    def _map_open_library(
        self,
        data: dict[str, Any],
        raw_isbn: str,
        normalized_isbn: str,
        client: httpx.Client | None = None,
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
        date_anchor = display_year

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

        # Local de publicação
        place_name = ""
        publish_places = data.get("publish_places", [])
        if isinstance(publish_places, list) and publish_places:
            pp = publish_places[0]
            raw_pp = str(pp.get("name", "") if isinstance(pp, dict) else pp).strip()
            place_name = clean_city_name(raw_pp)
        if not place_name and publisher:
            place_name = deduce_publisher_place(publisher) or ""

        if place_name:
            values["publication_place"] = place_name
            values["publication_city"] = place_name

        # Dimensões físicas
        phys_dim = str(data.get("physical_dimensions", "") or "").strip()
        if phys_dim:
            values["dimensions"] = phys_dim
        elif data.get("weight"):
            values["dimensions"] = str(data["weight"]).strip()

        # Série / Coleção
        series = data.get("series", [])
        if isinstance(series, list) and series:
            s0 = series[0]
            series_name = str(s0.get("name", "") if isinstance(s0, dict) else s0).strip()
            if series_name:
                values["collection_name"] = series_name

        # Edição
        edition_name = str(data.get("edition_name", "") or "").strip()
        if edition_name:
            ed_digits = re.sub(r"\D", "", edition_name)
            if ed_digits:
                values["edition"] = ed_digits

        # Enriquecer com informações da obra (works endpoint)
        raw_works = data.get("works", [])
        work_key = None
        if isinstance(raw_works, list) and raw_works and isinstance(raw_works[0], dict):
            work_key = raw_works[0].get("key")
        if work_key:
            work_data = self._fetch_open_library_work(work_key, client)
            if isinstance(work_data, dict):
                orig_title = str(work_data.get("title", "") or "").strip()
                if orig_title and orig_title.lower() != title.lower() and "original_full_title" not in values:
                    values["original_full_title"] = orig_title
                desc = work_data.get("description", "")
                if isinstance(desc, dict):
                    desc = desc.get("value", "")
                desc_str = str(desc or "").strip()
                if desc_str and "abstract" not in values:
                    values["abstract"] = desc_str

        # Descrição / Abstract da edição se ainda não preenchido
        if "abstract" not in values:
            description = data.get("description", "")
            if isinstance(description, dict):
                description = description.get("value", "")
            description = str(description or "").strip()
            if description:
                values["abstract"] = description
            elif data.get("notes"):
                notes_str = str(data["notes"] if not isinstance(data["notes"], dict) else data["notes"].get("value", "")).strip()
                if notes_str:
                    values["additional_notes"] = notes_str

        # Assuntos em additional_notes
        subjects = data.get("subjects", [])
        if isinstance(subjects, list) and subjects and "additional_notes" not in values:
            clean_subjs = [str(s.get("name", "") if isinstance(s, dict) else s).strip() for s in subjects[:5]]
            clean_subjs = [s for s in clean_subjs if s]
            if clean_subjs:
                values["additional_notes"] = f"Assuntos: {', '.join(clean_subjs)}"

        if data.get("url"):
            values["url"] = str(data["url"]).strip()
        else:
            values["url"] = f"https://openlibrary.org/isbn/{normalized_isbn}"

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
        pub_place = deduce_publisher_place(publisher) or ""

        # Anos de publicação (primeiro e último volume)
        dois_by_year = data.get("breakdowns", {}).get("dois-by-issued-year", [])
        if not dois_by_year:
            dois_by_year = data.get("counts", {}).get("dois-by-issued-year", [])
        valid_years = [
            y[0]
            for y in dois_by_year
            if isinstance(y, list) and len(y) > 0 and isinstance(y[0], int) and y[0] > 1800
        ]
        first_vol_year = str(min(valid_years)) if valid_years else ""
        last_vol_year = str(max(valid_years)) if valid_years else ""

        # Áreas e contagens
        subjects = data.get("subjects", [])
        notes_parts = []
        if isinstance(subjects, list) and subjects:
            clean_subjs = [str(s.get("name", "") if isinstance(s, dict) else s).strip() for s in subjects]
            clean_subjs = [s for s in clean_subjs if s]
            if clean_subjs:
                notes_parts.append(f"Áreas: {', '.join(clean_subjs)}")

        counts = data.get("counts", {})
        if isinstance(counts, dict) and counts.get("total-dois"):
            notes_parts.append(f"Total de artigos indexados: {counts['total-dois']}")

        values: dict[str, object] = {
            "title": title,
            "journal_title": title,
            "issn": clean,
            "date_precision": "Data exata",
        }
        if publisher:
            values["publisher"] = publisher
        if pub_place:
            values["publication_place"] = pub_place
            values["publication_city"] = pub_place
        if first_vol_year:
            values["first_volume_year"] = first_vol_year
            values["date_anchor"] = first_vol_year
            values["display_year"] = first_vol_year
        if last_vol_year:
            values["last_volume_year"] = last_vol_year
        if notes_parts:
            values["additional_notes"] = " · ".join(notes_parts)

        return ImportedMetadata(
            identifier_type=IdentifierType.ISSN,
            raw_identifier=issn,
            normalized_identifier=clean,
            work_type="periodical_collection",
            values=values,
            authors=[],
        )

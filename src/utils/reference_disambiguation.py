"""Utilitários para diferenciação de ano (sufixos 'a', 'b', 'c'...) em referências e citações ABNT."""

import re
from typing import Any

from src.utils.types import ReferencePart, TextStyle, ViewReference


def _normalize_string(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(value.strip().split()).upper()


def _letter_suffix(index: int) -> str:
    """Retorna 'a', 'b', ..., 'z', 'aa', 'ab', etc."""
    chars: list[str] = []
    num = index
    while True:
        chars.append(chr(ord("a") + (num % 26)))
        num = (num // 26) - 1
        if num < 0:
            break
    return "".join(reversed(chars))


def extract_work_author_key(work: dict[str, Any]) -> str:
    """Extrai uma chave canônica de autoria ou jurisdição para fins de agrupamento.

    - Para órgãos jurisdicionados (legislação e jurisprudência), extrai o primeiro
      segmento da jurisdição antes de subordinações (ex: "BRASIL" para "BRASIL. Presidência...").
    - Para autores comuns, exige identidade total (todos os autores normalizados).
    - Para obras anônimas/sem autor, usa o título normalizado.
    """
    work_type = str(work.get("work_type") or "").strip().lower()
    raw_author = str(
        work.get("citation_author") or work.get("authors") or ""
    ).strip()

    if work_type in {"statute", "caselaw"}:
        if not raw_author:
            return f"JURISDICTION:{_normalize_string(work.get('title'))}"
        first_segment = re.split(r"[.,;]", raw_author)[0].strip()
        return f"JURISDICTION:{_normalize_string(first_segment)}"

    if raw_author:
        authors = [_normalize_string(a) for a in raw_author.split(";") if a.strip()]
        if authors:
            return f"AUTHORS:{'; '.join(sorted(authors))}"

    title = str(work.get("title") or "").strip()
    return f"TITLE:{_normalize_string(title)}"


def extract_work_year(work: dict[str, Any]) -> str | None:
    """Extrai o ano base da obra (preferencialmente 4 dígitos numéricos)."""
    raw_year = str(work.get("display_year") or "").strip()
    match = re.search(r"\b(\d{4})\b", raw_year)
    if match:
        return match.group(1)
    if raw_year and raw_year != "[s.d.]":
        return raw_year
    return None


def compute_year_suffixes(works: list[dict[str, Any]]) -> dict[int, str]:
    """Calcula os anos com sufixo ('2019a', '2019b') para obras com identidade total de autor/jurisdição e ano.

    Obras isoladas não recebem sufixo. Quando há colisão, o desempate é feito
    pela ordem alfabética do título da obra (ABNT NBR 10520 e NBR 6023).
    """
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}

    for work in works:
        work_id = work.get("id")
        if work_id is None:
            continue
        year = extract_work_year(work)
        if not year:
            continue
        author_key = extract_work_author_key(work)
        groups.setdefault((author_key, year), []).append(work)

    suffixes: dict[int, str] = {}
    for (_author_key, year), group in groups.items():
        if len(group) <= 1:
            continue
        # Ordenar pelo título da obra (casefold) para desempate
        group_sorted = sorted(
            group,
            key=lambda w: str(w.get("title") or "").strip().casefold(),
        )
        for index, item in enumerate(group_sorted):
            work_id = item["id"]
            suffix = _letter_suffix(index)
            suffixes[work_id] = f"{year}{suffix}"

    return suffixes


def apply_year_suffix_to_reference(
    reference_text: str,
    original_year: str,
    suffixed_year: str,
) -> str:
    """Substitui o ano de publicação na referência ABNT pelo ano com sufixo.

    Preserva anos que possam ocorrer no título (que aparecem antes da editora/publicação)
    e anos em URLs ou datas de acesso (que aparecem após 'Disponível em:').
    """
    if not reference_text or not original_year or not suffixed_year:
        return reference_text

    disp_token = "Disponível em:"
    if disp_token in reference_text:
        prefix, sep, suffix = reference_text.partition(disp_token)
    else:
        prefix, sep, suffix = reference_text, "", ""

    # Substitui a última ocorrência do ano original no prefixo
    pattern = re.compile(rf"\b{re.escape(original_year)}(?=[\.,;/\s]|$)")
    matches = list(pattern.finditer(prefix))
    if not matches:
        return reference_text

    last_match = matches[-1]
    start, end = last_match.span()
    new_prefix = prefix[:start] + suffixed_year + prefix[end:]
    return new_prefix + sep + suffix


def apply_year_suffix_to_view_reference(
    reference: ViewReference,
    original_year: str,
    suffixed_year: str,
) -> ViewReference:
    """Retorna uma cópia do ViewReference com o ano diferenciado no ReferencePart correspondente."""
    new_parts: list[ReferencePart] = []
    applied = False
    for part in reversed(reference.parts):
        content = part.content
        if (
            not applied
            and original_year
            and re.search(rf"\b{re.escape(original_year)}(?=[\.,;/\s]|$)", content)
        ):
            new_content = apply_year_suffix_to_reference(
                content, original_year, suffixed_year
            )
            new_parts.append(ReferencePart(content=new_content, style=part.style))
            applied = True
        else:
            new_parts.append(ReferencePart(content=content, style=part.style))
    new_parts.reverse()
    return ViewReference(parts=new_parts)


def reference_plain_text(reference: ViewReference | str | None) -> str:
    """Converte um ViewReference ou texto em string pura sem quebras residuais."""
    if reference is None:
        return ""
    if isinstance(reference, str):
        return reference.strip()
    return "".join(part.content for part in reference.parts).strip()


def build_disambiguated_view_references(
    works: list[dict[str, Any]],
    references_by_id: dict[int, ViewReference | str],
) -> list[ViewReference]:
    """Gera a lista de ViewReference com os sufixos de diferenciação aplicados, preservando estilos."""
    suffixes = compute_year_suffixes(works)
    result: list[ViewReference] = []

    for work in works:
        work_id = work.get("id")
        if work_id is None:
            continue
        raw_ref = references_by_id.get(work_id)
        if isinstance(raw_ref, ViewReference):
            ref = raw_ref
        elif isinstance(raw_ref, str):
            ref = ViewReference(parts=[ReferencePart(content=raw_ref, style=TextStyle.NORMAL)])
        else:
            title = str(work.get("title") or "")
            ref = ViewReference(parts=[ReferencePart(content=title, style=TextStyle.NORMAL)])

        if work_id in suffixes:
            orig_year = extract_work_year(work)
            suff_year = suffixes[work_id]
            if orig_year:
                ref = apply_year_suffix_to_view_reference(ref, orig_year, suff_year)
        result.append(ref)

    return result


def build_disambiguated_references(
    works: list[dict[str, Any]],
    references_by_id: dict[int, ViewReference | str],
) -> list[str]:
    """Gera a lista de textos de referência ABNT com os sufixos de diferenciação aplicados."""
    view_refs = build_disambiguated_view_references(works, references_by_id)
    return [reference_plain_text(ref) for ref in view_refs]

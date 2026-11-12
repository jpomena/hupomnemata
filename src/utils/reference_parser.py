"""Mecanismo heurístico para segmentação e classificação inicial de referências bibliográficas.

Este módulo decompõe blocos de texto acadêmico em referências individuais
e realiza predição inicial do tipo de obra para subsidiar a cognição do Nous.
"""

from __future__ import annotations

import re

# Padrões para cabeçalhos comuns que antecedem a lista de referências
HEADER_PATTERN = re.compile(
    r"^(?:REFERÊNCIAS\s*(?:BIBLIOGRÁFICAS)?|BIBLIOGRAFIA|REFERENCES|WORKS\s+CITED)\s*[:.]?\s*$",
    re.IGNORECASE | re.MULTILINE,
)

# Padrões de início de referência:
# 1. Sobrenome em caixa alta (ABNT): FOUCAULT, Michel. ou SILVA-SANTOS, J.
# 2. Citação numerada: [1], 1., (1)
# 3. Travessão/underline indicador de repetição de autoria (ABNT): ______. ou ------.
# 4. Autor-Ano internacional: Foucault, M. (1975) ou Smith, J., 2020
REF_START_PATTERNS = [
    re.compile(r"^[A-ZÀ-Ú]{2,}(?:-[A-ZÀ-Ú]+)?,\s+"),
    re.compile(r"^\[\d+\]\s*"),
    re.compile(r"^\d+[\.\)]\s+"),
    re.compile(r"^_{3,}\.?\s*"),
    re.compile(r"^-{3,}\.?\s*"),
    re.compile(r"^[A-ZÀ-Ú][a-zà-ú]+(?:-[A-ZÀ-Ú][a-zà-ú]+)?,\s+[A-ZÀ-Ú]\.\s*(?:\(\d{4}\)|\d{4})"),
]


def _is_reference_start(line: str) -> bool:
    """Verifica se a linha possui assinatura característica de início de referência."""
    trimmed = line.strip()
    return any(pat.match(trimmed) for pat in REF_START_PATTERNS)


def split_references_block(raw_text: str) -> list[str]:
    """Decompõe um bloco de texto bruto em uma lista de referências bibliográficas individuais.

    Trata quebras duplas de parágrafo, quebras espúrias em linhas de PDFs/Word
    e padrões ABNT/Vancouver.
    """
    if not raw_text or not raw_text.strip():
        return []

    # Normaliza quebras de linha
    text = raw_text.replace("\r\n", "\n").replace("\r", "\n").strip()

    # Remove cabeçalho se constar isolado no topo
    lines = text.split("\n")
    if lines and HEADER_PATTERN.match(lines[0].strip()):
        text = "\n".join(lines[1:]).strip()

    if not text:
        return []

    # Estratégia 1: Divisão por linhas em branco (duplas quebras)
    raw_paragraphs = [p.strip() for p in re.split(r"\n\s*\n+", text) if p.strip()]

    # Se obtivemos múltiplos blocos por linhas em branco, avaliamos se algum bloco
    # acumulou referências coladas sem linha em branco entre si
    extracted_refs: list[str] = []

    for paragraph in raw_paragraphs:
        p_lines = [line.strip() for line in paragraph.split("\n") if line.strip()]
        if not p_lines:
            continue

        # Verifica se há linhas internas neste parágrafo que marcam o início de uma nova referência
        current_chunk: list[str] = []
        for line in p_lines:
            if current_chunk and _is_reference_start(line):
                # Encerra o chunk anterior e inicia nova referência
                extracted_refs.append(" ".join(current_chunk))
                current_chunk = [line]
            else:
                current_chunk.append(line)

        if current_chunk:
            extracted_refs.append(" ".join(current_chunk))

    # Limpeza final e normalização de espaços
    results: list[str] = []
    for ref in extracted_refs:
        clean = re.sub(r"\s+", " ", ref).strip()
        # Filtra fragmentos minúsculos sem densidade bibliográfica (< 10 caracteres)
        if len(clean) >= 10:
            results.append(clean)

    return results


def detect_probable_work_type(raw_ref: str) -> str:
    """Infere o tipo inicial de obra bibliográfica a partir de termos característicos.

    Esta predição serve como sugestão padrão para o seletor da interface antes do envio ao Nous.
    """
    text_lower = raw_ref.lower()

    # 1. Teses e Dissertações
    if any(k in text_lower for k in ["tese (doutorado", "dissertação (mestrado", "tcc", "monografia (graduação"]):
        return "academic_monograph"

    # 2. Legislação / Normas
    if re.search(r"\b(?:lei|decreto|portaria|medida provisória)\s+n[ºo°]?\s*\d+", text_lower):
        return "statute"

    # 3. Artigos de Jornal
    if any(k in text_lower for k in ["folha de s.paulo", "o estado de s. paulo", "o globo", "jornal do brasil"]):
        return "newspaper_article"

    # 4. Anais e Eventos
    if " in:" in text_lower or text_lower.startswith("in:"):
        if any(k in text_lower for k in ["anais", "congresso", "simpósio", "encontro", "proceedings"]):
            return "monographic_proceedings"
        # Se for capítulo de livro com In:, sugerimos monografia editorial
        return "editorial_monograph"

    # 5. Artigos de Periódicos
    # Presença de volume, número e paginação clássicos (ex: v. 12, n. 3, p. 45-60)
    has_vol_num = bool(re.search(r"\bv(?:ol)?\.\s*\d+", text_lower) and re.search(r"\bn(?:º|o|um)?\.\s*\d+", text_lower))
    has_pages = bool(re.search(r"\bp(?:ág|p)?\.\s*\d+", text_lower))
    if has_vol_num and has_pages:
        return "journal_article"

    if any(k in text_lower for k in ["revista ", "journal of", "cadernos de", "boletim "]) and has_pages:
        return "journal_article"

    # Padrão para livros / monografias em geral
    return "editorial_monograph"

"""Mecanismo heurístico para segmentação e classificação inicial de referências bibliográficas.

Este módulo decompõe blocos de texto acadêmico em referências individuais
e realiza inferência ponderada de múltiplos sinais estruturais (multi-signal weighted scoring)
para determinar o tipo de obra mais provável (ABNT NBR 6023, APA, Chicago, Harvard, Vancouver).
"""

from __future__ import annotations

import re
from typing import Final

# Tipos de obras suportados pelo sistema
TYPE_EDITORIAL_MONOGRAPH: Final[str] = "editorial_monograph"
TYPE_JOURNAL_ARTICLE: Final[str] = "journal_article"
TYPE_ACADEMIC_MONOGRAPH: Final[str] = "academic_monograph"
TYPE_MONOGRAPHIC_PROCEEDINGS: Final[str] = "monographic_proceedings"
TYPE_NEWSPAPER_ARTICLE: Final[str] = "newspaper_article"
TYPE_STATUTE: Final[str] = "statute"
TYPE_CASELAW: Final[str] = "caselaw"
TYPE_MISC_DIGITAL: Final[str] = "miscellaneous_digital_document"

ALL_WORK_TYPES: Final[tuple[str, ...]] = (
    TYPE_EDITORIAL_MONOGRAPH,
    TYPE_JOURNAL_ARTICLE,
    TYPE_ACADEMIC_MONOGRAPH,
    TYPE_MONOGRAPHIC_PROCEEDINGS,
    TYPE_NEWSPAPER_ARTICLE,
    TYPE_STATUTE,
    TYPE_CASELAW,
    TYPE_MISC_DIGITAL,
)

# Padrões para cabeçalhos comuns que antecedem listas de referências
HEADER_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^(?:REFERÊNCIAS\s*(?:BIBLIOGRÁFICAS|NORMATIVAS)?|BIBLIOGRAFIA|REFERENCES|WORKS\s+CITED|"
    r"LITERATURE\s+CITED|FONTES\s+BIBLIOGRÁFICAS)\s*[:.]?\s*$",
    re.IGNORECASE | re.MULTILINE,
)

# Padrões de início de referência:
# 1. Sobrenome em caixa alta ABNT: FOUCAULT, Michel. ou SILVA-SANTOS, J.
# 2. Entidades estatais/institucionais em caixa alta: BRASIL. ou SÃO PAULO. ou UNESCO.
# 3. Citação numerada: [1], 1., 1), (1)
# 4. Travessão/underline indicador de repetição de autoria (ABNT): ______. ou ------. ou ——————.
# 5. Autor em formato internacional/APA/Chicago: Foucault, M. (1975) ou Smith, John, 2020.
# 6. Partículas de sobrenomes: van Dijk, T. A.
REF_START_PATTERNS: Final[list[re.Pattern[str]]] = [
    re.compile(r"^[A-ZÀ-Ú]{2,}(?:-[A-ZÀ-Ú]+)?,\s+"),
    re.compile(r"^(?:BRASIL|SÃO PAULO|RIO DE JANEIRO|MINAS GERAIS|[A-ZÀ-Ú\s]{3,})\.\s+"),
    re.compile(r"^\[\d+\]\s*"),
    re.compile(r"^\d+[\.\)]\s+"),
    re.compile(r"^\(\d+\)\s+"),
    re.compile(r"^_{3,}\.?\s*"),
    re.compile(r"^-{3,}\.?\s*"),
    re.compile(r"^[\u2014\u2013\u2015]{2,}\.?\s*"),
    re.compile(r"^[A-ZÀ-Ú][a-zà-ú]+(?:-[A-ZÀ-Ú][a-zà-ú]+)?,\s+[A-ZÀ-Ú]"),
    re.compile(r"^(?:van|von|de|da|do|dos|das|del|della|di)\s+[A-ZÀ-Ú][a-zà-ú]+,\s+"),
]


def _is_reference_start(line: str) -> bool:
    """Verifica se a linha possui assinatura característica de início de referência."""
    trimmed = line.strip()
    return any(pat.match(trimmed) for pat in REF_START_PATTERNS)


def split_references_block(raw_text: str) -> list[str]:
    """Decompõe um bloco de texto bruto em uma lista de referências bibliográficas individuais.

    Trata quebras duplas de parágrafo, quebras espúrias em linhas de PDFs/Word
    e padrões ABNT/Vancouver/APA.
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

    extracted_refs: list[str] = []

    for paragraph in raw_paragraphs:
        p_lines = [line.strip() for line in paragraph.split("\n") if line.strip()]
        if not p_lines:
            continue

        current_chunk: list[str] = []
        for line in p_lines:
            if current_chunk and _is_reference_start(line):
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


# ---------------------------------------------------------------------------
# Padrões Regex Pré-compilados para Inferência Ponderada de Tipos de Obra
# ---------------------------------------------------------------------------

# Jurisprudência (caselaw)
RE_CASELAW_COURTS = re.compile(
    r"\b(?:stf|stj|tst|tse|stm|tjsp|tjrj|tjmg|tjrs|tjpr|tjsc|tjba|tjpe|tjce|tjdf|trf\s*[1-6]|"
    r"trf[1-6]|trt\s*\d{1,2}|trt\d{1,2}|supremo\s+tribunal\s+federal|superior\s+tribunal\s+de\s+justi[çc]a|"
    r"tribunal\s+de\s+justi[çc]a|tribunal\s+regional\s+federal|tribunal\s+superior\s+do\s+trabalho)\b",
    re.IGNORECASE,
)
RE_CASELAW_ACTIONS = re.compile(
    r"(?:\brecurso\s+especial\b|\bresp\b|\brecurso\s+extraordin[áa]rio\b|\bre\s*n?[ºo°]?\s*\d+|"
    r"\bhabeas\s+corpus\b|\bhc\s*n?[ºo°]?\s*\d+|\badi\s*n?[ºo°]?\s*\d+|\badc\s*n?[ºo°]?\s*\d+|"
    r"\badpf\s*n?[ºo°]?\s*\d+|\bmandado\s+de\s+seguran[çc]a\b|\bagravo\s+de\s+instrumento\b|"
    r"\bapela[çc][ãa]o\s+c[íi]vel\b|\bembargos\s+de\s+declara[çc][ãa]o\b|\ba[çc][ãa]o\s+civil\s+p[úu]blica\b|"
    r"\bprocesso\s+n[ºo°]?\s*[\d.-]+)",
    re.IGNORECASE,
)
RE_CASELAW_TERMS = re.compile(
    r"(?:\brelator(?:a)?\b|\brel\.\s*(?:min|des)|\bac[óo]rd[ãa]o\b|\bs[úu]mula(?:\s+vinculante)?\s+n[ºo°]?\s*\d+|"
    r"\bjulgad[oa]\s+em\s+\d{1,2}|\bjulgamento\s+em\s+\d{1,2}|\bdi[áa]rio\s+da\s+justi[çc]a\b|\bdje\b)",
    re.IGNORECASE,
)

# Legislação (statute)
RE_STATUTE_START = re.compile(
    r"^(?:BRASIL|SÃO PAULO|RIO DE JANEIRO|MINAS GERAIS|DISTRITO FEDERAL|[A-ZÀ-Ú\s]{3,})"
    r"(?:\s*\([^)]+\))?\.\s*(?:[A-ZÀ-Ú\w\s.,-]+\.\s*)?"
    r"(?:Constitui[çc][ãa]o|Lei|Decreto|Portaria|Medida\s+Provis[óo]ria|C[óo]digo|Resolu[çc][ãa]o|"
    r"Instru[çc][ãa]o\s+Normativa|Regimento)",
)
RE_STATUTE_NORMS = re.compile(
    r"(?:\blei\s+(?:federal|estadual|municipal|complementar|ordin[áa]ria|delegada|org[âa]nica)?\s*n[ºo°]?\s*[\d.]+|"
    r"\blei\s+org[âa]nica\b|"
    r"\bdecreto(?:-lei)?\s+n[ºo°]?\s*[\d.]+|\bmedida\s+provis[óo]ria\s+n[ºo°]?\s*[\d.]+|"
    r"\bportaria(?:\s+interministerial|\s+conjunta|\s+[\w-]+)*\s+n[ºo°]?\s*[\d.]+|"
    r"\bemenda\s+constitucional\s+n[ºo°]?\s*[\d.]+|"
    r"\binstru[çc][ãa]o\s+normativa(?:\s+[\w-]+)*\s+n[ºo°]?\s*[\d.]+|"
    r"\bresolu[çc][ãa]o(?:\s+[\w-]+)*\s+n[ºo°]?\s*[\d.]+)",
    re.IGNORECASE,
)
RE_STATUTE_CODES = re.compile(
    r"\b(?:constitui[çc][ãa]o\s+(?:da\s+rep[úu]blica|federal|pol[íi]tica|de\s+\d{4})|"
    r"c[óo]digo\s+(?:civil|penal|tribut[áa]rio|florestal|comercial|eleitoral|de\s+tr[âa]nsito|"
    r"de\s+defesa\s+do\s+consumidor|de\s+processo\s+civil|de\s+processo\s+penal)|"
    r"consolida[çc][ãa]o\s+das\s+leis\s+do\s+trabalho|\bclt\b)\b",
    re.IGNORECASE,
)
RE_STATUTE_GAZETTE = re.compile(
    r"\b(?:di[áa]rio\s+oficial\s+(?:da\s+uni[ãa]o|do\s+estado|do\s+munic[íi]pio|eletr[ôo]nico)|\bdou\b)\b",
    re.IGNORECASE,
)

# Trabalhos Acadêmicos (academic_monograph)
RE_THESIS_DOCTORAL = re.compile(
    r"(?:\btese\s*\([^)]*(?:doutor|livre-doc[êe]ncia|titularidade)[^)]*\)|"
    r"\btese\s+de\s+(?:doutorado|livre-doc[êe]ncia)\b|"
    r"\btese\s+(?:apresentada|defendida)\b.*?(?:faculdade|instituto|universidade|programa|doutor)|"
    r"\bdoctoral\s+(?:dissertation|thesis)\b|\bph\.?d\.?\s+(?:dissertation|thesis)\b|"
    r"\bth[èée]ses?\s+de\s+doctorat\b)",
    re.IGNORECASE,
)
RE_THESIS_MASTER = re.compile(
    r"(?:\bdisserta[çc][ãa]o\s*\([^)]*mestrado[^)]*\)|"
    r"\bdisserta[çc][ãa]o\s+de\s+mestrado\b|"
    r"\bdisserta[çc][ãa]o\s+(?:apresentada|defendida)\b.*?(?:faculdade|instituto|universidade|programa|mestre)|"
    r"\bmaster(?:'s)?\s+thesis\b|\bm[ée]moire\s+de\s+master\b)",
    re.IGNORECASE,
)
RE_THESIS_TCC = re.compile(
    r"(?:\bmonografia\s*\([^)]*(?:especializa[çc][ãa]o|gradua[çc][ãa]o|aperfei[çc]oamento|p[óo]s-gradua[çc][ãa]o)[^)]*\)|"
    r"\btrabalho\s+de\s+conclus[ãa]o\s+de\s+curso\b|\bmonografia\s+de\s+conclus[ãa]o\b|\b\(?tcc\)?\b|"
    r"\brelat[óo]rio\s+de\s+est[áa]gio\s+curricular\b)",
    re.IGNORECASE,
)
RE_THESIS_CONTEXT = re.compile(
    r"(?:\bpara\s+(?:a\s+)?obten[çc][ãa]o\s+do\s+(?:t[íi]tulo|grau)\s+de\s+(?:mestre|doutor|bacharel|especialista)\b|"
    r"\bprograma\s+de\s+p[óo]s-gradua[çc][ãa]o\s+em\b|\bppg[a-z]*\b|"
    r"\b\d+\s*(?:f\.|folhas)\b)",
    re.IGNORECASE,
)

# Anais e Eventos (monographic_proceedings)
RE_PROCEEDINGS_IN = re.compile(
    r"\bin:\s*.*?\b(?:anais|atas|proceedings|actas|congresso|simp[óo]sio|encontro|semin[áa]rio|"
    r"jornada|col[óo]quio|workshop|conference|symposium|meeting|summit)\b",
    re.IGNORECASE,
)
RE_PROCEEDINGS_EXPLICIT = re.compile(
    r"(?:\banais\s+d[eoa]\b|\bproceedings\s+of\s+the\b|\bactas\s+d[eoa]\b|\banais\s*\[?\.\.\.\]?|"
    r"\b\d+[\.ªªºo]?\s*(?:congresso|simp[óo]sio|encontro|semin[áa]rio|jornada|col[óo]quio|conference|symposium)\b)",
    re.IGNORECASE,
)

# Artigos de Jornal (newspaper_article)
RE_NEWSPAPER_OUTLETS = re.compile(
    r"\b(?:folha\s+de\s+s\.?\s*paulo|o\s+estado\s+de\s+s\.?\s*paulo|estad[ãa]o|o\s+globo|"
    r"jornal\s+do\s+brasil|valor\s+econ[ôo]mico|gazeta\s+mercantil|nexo\s+jornal|correio\s+braziliense|"
    r"zero\s+hora|estado\s+de\s+minas|gazeta\s+do\s+povo|di[áa]rio\s+catarinense|a\s+tarde|"
    r"di[áa]rio\s+de\s+pernambuco|carta\s*capital|the\s+new\s+york\s+times|new\s+york\s+times|"
    r"the\s+guardian|the\s+wall\s+street\s+journal|wall\s+street\s+journal|the\s+washington\s+post|"
    r"washington\s+post|le\s+monde|el\s+pa[íi]s|the\s+times|financial\s+times|die\s+zeit|der\s+spiegel|"
    r"corriere\s+della\s+sera|clar[íi]n|p[áa]gina\s*12)\b",
    re.IGNORECASE,
)
RE_NEWSPAPER_GENERIC = re.compile(
    r"\b(?:jornal\s+[A-ZÀ-Ú][a-zà-ú]+|di[áa]rio\s+d[eoa]\s+(?!oficial)[A-ZÀ-Ú][a-zà-ú]+)\b",
)
RE_NEWSPAPER_DAILY_DATE = re.compile(
    r"\b(?:\d{1,2}\s+(?:de\s+)?(?:jan(?:eiro)?|fev(?:ereiro)?|mar(?:[çc]o)?|abr(?:il)?|mai(?:o)?|"
    r"jun(?:ho)?|jul(?:ho)?|ago(?:sto)?|set(?:embro)?|out(?:ubro)?|nov(?:embro)?|dez(?:embro)?)\.?,?\s+(?:de\s+)?\d{4}|"
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:tember)?|"
    r"oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\.?\s+\d{1,2},?\s+\d{4}|"
    r"\d{1,2}\s+(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:tember)?|"
    r"oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\.?\s+\d{4})\b",
    re.IGNORECASE,
)
RE_NEWSPAPER_SECTIONS = re.compile(
    r"\b(?:caderno|se[çc][ãa]o|suplemento|ilustrada|cotidiano|opini[ãa]o|primeiro\s+caderno|"
    r"p\.\s*[a-zA-Z]\d+|p\.\s*\d+-[a-zA-Z])\b",
    re.IGNORECASE,
)

# Artigos de Periódicos (journal_article)
RE_JOURNAL_VOL_NUM = re.compile(
    r"(?:\bv(?:ol)?\.\s*\d+.*?\bn(?:º|o|um)?\.\s*\d+|\bn(?:º|o|um)?\.\s*\d+.*?\bv(?:ol)?\.\s*\d+|"
    r"\bano\s+\d+.*?\bn(?:º|o|um)?\.\s*\d+)",
    re.IGNORECASE,
)
RE_JOURNAL_COMPACT_NOTATION = re.compile(
    r"\b\d+\s*\(\s*\d+\s*\)\s*(?::|,|\s)?\s*(?:p\.|pp\.)?\s*\d+\b",
)
RE_JOURNAL_PAGE_RANGE = re.compile(
    r"(?:\b(?:p\.|pp\.|p[áa]gs?\.)\s*\d+\s*[-–—]\s*\d+\b|:\s*\d+\s*[-–—]\s*\d+\b)",
    re.IGNORECASE,
)
RE_JOURNAL_ELOCATION = re.compile(
    r"\b(?:artigo|article|e-location|elocation-id)?\s*e\d{5,8}\b",
    re.IGNORECASE,
)
RE_JOURNAL_SEASONAL = re.compile(
    r"\b(?:(?:jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez)\.?\s*[\/-]\s*"
    r"(?:jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez)\.?|"
    r"semestral|trimestral|quadrimestral|bimestral|"
    r"(?:spring|summer|autumn|fall|winter)\s+\d{4})\b",
    re.IGNORECASE,
)
RE_JOURNAL_VEHICLE_TERMS = re.compile(
    r"\b(?:revista|journal(?:\s+of)?|review|cadernos\s+de|boletim\s+de|quarterly|"
    r"bulletin|acta\s+[a-z]+|annals\s+of)\b",
    re.IGNORECASE,
)
RE_JOURNAL_DOI = re.compile(
    r"\b(?:doi(?:\.org\/|:)\s*10\.\d{4,9}\/[-._;()/:A-Za-z0-9]+|10\.\d{4,9}\/[-._;()/:A-Za-z0-9]+)\b",
    re.IGNORECASE,
)
RE_JOURNAL_ISSN = re.compile(
    r"\bissn\s*(?:[0-9]{4}-[0-9]{3}[0-9xX])\b",
    re.IGNORECASE,
)

# Monografias Editoriais / Livros / Capítulos (editorial_monograph)
RE_BOOK_IMPRINT = re.compile(
    r"(?:[A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-ZÀ-Ú][a-zà-ú]+)*|[A-ZÀ-Ú]{2,}):\s+"
    r"[A-ZÀ-Ú][\w\s.&'-]+,\s*(?:19\d\d|20\d\d)\b",
)
RE_BOOK_KNOWN_CITIES = re.compile(
    r"\b(?:são\s+paulo|rio\s+de\s+janeiro|petr[óo]polis|belo\s+horizonte|porto\s+alegre|"
    r"curitiba|bras[íi]lia|campinas|salvador|recife|fortaleza|lisboa|coimbra|porto|"
    r"london|new\s+york|oxford|cambridge|paris|berlin|boston|chicago)\s*:",
    re.IGNORECASE,
)
RE_BOOK_KNOWN_PUBLISHERS = re.compile(
    r":\s*(?:companhia\s+das\s+letras|cia\.?\s+das\s+letras|vozes|brasiliense|cortez|zahar|"
    r"saraiva|forense|revista\s+dos\s+tribunais|atlas|martins\s+fontes|cosac\s+naify|boitempo|"
    r"editora\s+34|aut[êe]ntica|edusp|editora\s+unesp|almedina|routledge|springer|elsevier|"
    r"oxford\s+university\s+press|cambridge\s+university\s+press|harvard\s+university\s+press|"
    r"mit\s+press|gallimard|seuil|suhrkamp|de\s+gruyter|routledge)",
    re.IGNORECASE,
)
RE_BOOK_EDITION = re.compile(
    r"\b(?:\d+[\.ªªºo]?\s*ed(?:i[çc][ãa]o|\.)|(?:1st|2nd|3rd|[4-9]th)\s+ed(?:ition|\.)?|"
    r"ed\.\s*(?:rev|ampl|atual))\b",
    re.IGNORECASE,
)
RE_BOOK_TOTAL_PAGES = re.compile(
    r"\b\d+\s*(?:p\.|pp\.)(?!\s*[-–—\d])",
    re.IGNORECASE,
)
RE_BOOK_ISBN = re.compile(
    r"\bisbn(?:-1[03])?:?\s*[0-9xX-]{10,17}\b",
    re.IGNORECASE,
)
RE_BOOK_EDITORIAL_ROLES = re.compile(
    r"\b(?:\((?:orgs?|coords?|eds?|dirs?)\.?\)|organiza[çc][ãa]o\s+de|coordena[çc][ãa]o\s+de|"
    r"editado\s+por|tradu[çc][ãa]o\s+de|pref[áa]cio\s+de|translated\s+by)\b",
    re.IGNORECASE,
)

# Documentos Digitais Diversos / Web (miscellaneous_digital_document)
RE_WEB_ACCESS = re.compile(
    r"\b(?:dispon[íi]vel\s+em:\s*<?https?:|available\s+(?:at|from):\s*<?https?:|"
    r"acesso\s+em:\s*\d{1,2}|accessed(?:\s+on)?:\s*\w+)\b",
    re.IGNORECASE,
)
RE_WEB_URL_GENERAL = re.compile(
    r"https?:\/\/[^\s<>]+",
    re.IGNORECASE,
)
RE_WEB_PLATFORMS = re.compile(
    r"\b(?:blog|website|portal|online|wikipedia|github|medium\.com|youtube|podcast)\b",
    re.IGNORECASE,
)


def detect_probable_work_type(raw_ref: str) -> str:
    """Infere com alta precisão o tipo provável de obra bibliográfica via pontuação ponderada.

    Avalia múltiplos sinais ortogonais (sintaxe ABNT/APA, imprenta, veículos, paginação,
    identificadores digitais e papéis editoriais) eliminando ambiguidades entre artigos,
    livros, teses, anais, jornais, legislação e documentos web.
    """
    if not raw_ref or not raw_ref.strip():
        return TYPE_EDITORIAL_MONOGRAPH

    text = raw_ref.strip()
    text_lower = text.lower()
    has_in = bool(re.search(r"\bin:\s*", text, re.IGNORECASE))

    scores: dict[str, int] = {t: 0 for t in ALL_WORK_TYPES}

    # -----------------------------------------------------------------------
    # 1. Jurisprudência (caselaw)
    # -----------------------------------------------------------------------
    if RE_CASELAW_COURTS.search(text_lower):
        scores[TYPE_CASELAW] += 90
    if RE_CASELAW_ACTIONS.search(text_lower):
        scores[TYPE_CASELAW] += 90
    if RE_CASELAW_TERMS.search(text_lower):
        scores[TYPE_CASELAW] += 80

    # -----------------------------------------------------------------------
    # 2. Legislação (statute)
    # -----------------------------------------------------------------------
    if RE_STATUTE_START.search(text):
        scores[TYPE_STATUTE] += 120
    if RE_STATUTE_NORMS.search(text_lower):
        scores[TYPE_STATUTE] += 100
    if RE_STATUTE_CODES.search(text_lower):
        scores[TYPE_STATUTE] += 90
    if RE_STATUTE_GAZETTE.search(text_lower):
        scores[TYPE_STATUTE] += 60

    # -----------------------------------------------------------------------
    # 3. Trabalhos Acadêmicos (academic_monograph)
    # -----------------------------------------------------------------------
    if RE_THESIS_DOCTORAL.search(text_lower):
        scores[TYPE_ACADEMIC_MONOGRAPH] += 130
    if RE_THESIS_MASTER.search(text_lower):
        scores[TYPE_ACADEMIC_MONOGRAPH] += 130
    if RE_THESIS_TCC.search(text_lower):
        scores[TYPE_ACADEMIC_MONOGRAPH] += 110
    if RE_THESIS_CONTEXT.search(text_lower):
        scores[TYPE_ACADEMIC_MONOGRAPH] += 40

    # -----------------------------------------------------------------------
    # 4. Anais e Eventos (monographic_proceedings)
    # -----------------------------------------------------------------------
    if RE_PROCEEDINGS_IN.search(text):
        scores[TYPE_MONOGRAPHIC_PROCEEDINGS] += 140
    elif has_in and RE_PROCEEDINGS_EXPLICIT.search(text_lower):
        scores[TYPE_MONOGRAPHIC_PROCEEDINGS] += 120
    elif RE_PROCEEDINGS_EXPLICIT.search(text_lower):
        scores[TYPE_MONOGRAPHIC_PROCEEDINGS] += 70

    # -----------------------------------------------------------------------
    # 5. Artigos de Jornal (newspaper_article)
    # -----------------------------------------------------------------------
    is_official_gazette = bool(RE_STATUTE_GAZETTE.search(text_lower))
    has_news_outlet = bool(RE_NEWSPAPER_OUTLETS.search(text_lower))
    has_news_generic = bool(RE_NEWSPAPER_GENERIC.search(text)) and not is_official_gazette
    has_daily_date = bool(RE_NEWSPAPER_DAILY_DATE.search(text_lower))
    has_news_section = bool(RE_NEWSPAPER_SECTIONS.search(text_lower))

    if has_news_outlet:
        scores[TYPE_NEWSPAPER_ARTICLE] += 100
    elif has_news_generic:
        scores[TYPE_NEWSPAPER_ARTICLE] += 60

    if has_daily_date and not is_official_gazette:
        scores[TYPE_NEWSPAPER_ARTICLE] += 60
    if has_news_section and not is_official_gazette:
        scores[TYPE_NEWSPAPER_ARTICLE] += 50

    # -----------------------------------------------------------------------
    # 6. Artigos de Periódicos (journal_article)
    # -----------------------------------------------------------------------
    has_j_vol_num = bool(RE_JOURNAL_VOL_NUM.search(text_lower))
    has_j_compact = bool(RE_JOURNAL_COMPACT_NOTATION.search(text))
    has_j_page_range = bool(RE_JOURNAL_PAGE_RANGE.search(text))
    has_j_elocation = bool(RE_JOURNAL_ELOCATION.search(text_lower))
    has_j_seasonal = bool(RE_JOURNAL_SEASONAL.search(text_lower))
    has_j_vehicle = bool(RE_JOURNAL_VEHICLE_TERMS.search(text_lower))
    has_j_doi = bool(RE_JOURNAL_DOI.search(text_lower))
    has_j_issn = bool(RE_JOURNAL_ISSN.search(text_lower))

    # Volume ou fascículo isolados
    has_j_vol_alone = bool(re.search(r"\bv(?:ol)?\.\s*\d+\b", text_lower))
    has_j_num_alone = bool(re.search(r"\bn(?:º|o|um|\.)\s*\d+\b|\bfasc\.\s*\d+\b|\bissue\s+\d+\b", text_lower))

    if has_j_vol_num:
        scores[TYPE_JOURNAL_ARTICLE] += 90
    elif has_j_compact:
        scores[TYPE_JOURNAL_ARTICLE] += 90
    else:
        if has_j_vol_alone:
            scores[TYPE_JOURNAL_ARTICLE] += 35
        if has_j_num_alone:
            scores[TYPE_JOURNAL_ARTICLE] += 35

    if has_j_page_range and not has_in:
        scores[TYPE_JOURNAL_ARTICLE] += 45
    if has_j_elocation:
        scores[TYPE_JOURNAL_ARTICLE] += 50
    if has_j_seasonal:
        scores[TYPE_JOURNAL_ARTICLE] += 50
    if has_j_vehicle:
        scores[TYPE_JOURNAL_ARTICLE] += 40
    if has_j_doi:
        scores[TYPE_JOURNAL_ARTICLE] += 50
    if has_j_issn:
        scores[TYPE_JOURNAL_ARTICLE] += 60

    # Se contiver 'In:', geralmente é capítulo de livro ou anais, não periódico
    if has_in:
        scores[TYPE_JOURNAL_ARTICLE] -= 60

    # Se for notícia com data diária clara e jornal, periódico perde relevância
    if has_news_outlet and has_daily_date:
        scores[TYPE_JOURNAL_ARTICLE] -= 60

    # -----------------------------------------------------------------------
    # 7. Monografias Editoriais / Livros / Capítulos (editorial_monograph)
    # -----------------------------------------------------------------------
    has_book_imprint = bool(RE_BOOK_IMPRINT.search(text))
    has_book_city = bool(RE_BOOK_KNOWN_CITIES.search(text))
    has_book_pub = bool(RE_BOOK_KNOWN_PUBLISHERS.search(text))
    has_book_edition = bool(RE_BOOK_EDITION.search(text_lower))
    has_book_total_pages = bool(RE_BOOK_TOTAL_PAGES.search(text_lower))
    has_book_isbn = bool(RE_BOOK_ISBN.search(text_lower))
    has_book_roles = bool(RE_BOOK_EDITORIAL_ROLES.search(text_lower))

    if has_book_imprint:
        scores[TYPE_EDITORIAL_MONOGRAPH] += 80
    if has_book_city:
        scores[TYPE_EDITORIAL_MONOGRAPH] += 35
    if has_book_pub:
        scores[TYPE_EDITORIAL_MONOGRAPH] += 40
    if has_book_edition:
        scores[TYPE_EDITORIAL_MONOGRAPH] += 45
    if has_book_total_pages:
        scores[TYPE_EDITORIAL_MONOGRAPH] += 40
    if has_book_isbn:
        scores[TYPE_EDITORIAL_MONOGRAPH] += 70
    if has_book_roles:
        scores[TYPE_EDITORIAL_MONOGRAPH] += 45

    # Capítulo de Livro: tem 'In:', mas NÃO é Anais/Congresso
    if has_in and scores[TYPE_MONOGRAPHIC_PROCEEDINGS] == 0:
        scores[TYPE_EDITORIAL_MONOGRAPH] += 90

    # Penalidades para livro: faixa de páginas solta sem 'In:' aponta para artigo
    if has_j_page_range and not has_in:
        scores[TYPE_EDITORIAL_MONOGRAPH] -= 40
    if has_j_vol_num and not has_book_imprint:
        scores[TYPE_EDITORIAL_MONOGRAPH] -= 60

    # -----------------------------------------------------------------------
    # 8. Documentos Digitais / Web (miscellaneous_digital_document)
    # -----------------------------------------------------------------------
    has_web_access = bool(RE_WEB_ACCESS.search(text_lower))
    has_web_url = bool(RE_WEB_URL_GENERAL.search(text))
    has_web_platform = bool(RE_WEB_PLATFORMS.search(text_lower))

    if has_web_access:
        scores[TYPE_MISC_DIGITAL] += 50
    if has_web_url and not has_j_doi:
        scores[TYPE_MISC_DIGITAL] += 40
    if has_web_platform:
        scores[TYPE_MISC_DIGITAL] += 50

    # -----------------------------------------------------------------------
    # Árvore de Decisão e Resolução Ponderada de Conflitos
    # -----------------------------------------------------------------------

    # A) Precedência inequívoca de tipos institucionais e formais fechados
    if scores[TYPE_CASELAW] >= 80 and scores[TYPE_CASELAW] >= scores[TYPE_STATUTE]:
        return TYPE_CASELAW

    if scores[TYPE_STATUTE] >= 80:
        return TYPE_STATUTE

    if scores[TYPE_ACADEMIC_MONOGRAPH] >= 80:
        return TYPE_ACADEMIC_MONOGRAPH

    if scores[TYPE_MONOGRAPHIC_PROCEEDINGS] >= 80 and (has_in or scores[TYPE_MONOGRAPHIC_PROCEEDINGS] > scores[TYPE_JOURNAL_ARTICLE]):
        return TYPE_MONOGRAPHIC_PROCEEDINGS

    if scores[TYPE_NEWSPAPER_ARTICLE] >= 80:
        return TYPE_NEWSPAPER_ARTICLE

    # B) Disputa direta entre Artigo de Periódico e Livro/Monografia
    j_score = scores[TYPE_JOURNAL_ARTICLE]
    b_score = scores[TYPE_EDITORIAL_MONOGRAPH]

    # Se houver fortes sinais de periódico (volume/número, ou veículo + páginas/doi/issn)
    if j_score > b_score and j_score >= 50:
        return TYPE_JOURNAL_ARTICLE

    if b_score > j_score and b_score >= 50:
        return TYPE_EDITORIAL_MONOGRAPH

    # Se ainda restarem sinais positivos de periódico sobre livro
    if j_score > b_score and (has_j_vol_num or has_j_compact or (has_j_page_range and not has_in)):
        return TYPE_JOURNAL_ARTICLE

    # C) Documentos digitais / Web
    # Só prevalece sobre livro/artigo se o documento não apresentar sinais substanciais dos outros
    if scores[TYPE_MISC_DIGITAL] >= 50 and j_score < 40 and b_score < 40:
        return TYPE_MISC_DIGITAL

    # D) Fallback para a maior pontuação positiva
    best_type = max(scores, key=lambda k: scores[k])
    if scores[best_type] > 0:
        return best_type

    # E) Padrão monográfico acadêmico para referências sem sinais explícitos
    return TYPE_EDITORIAL_MONOGRAPH

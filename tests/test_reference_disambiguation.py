"""Testes para o algoritmo de diferenciação de ano ('2019a', '2019b') em referências e citações ABNT."""

from src.utils.clipboard import (
    copy_references,
    reference_html,
    reference_text,
)
from src.utils.reference_disambiguation import (
    apply_year_suffix_to_reference,
    apply_year_suffix_to_view_reference,
    build_disambiguated_references,
    build_disambiguated_view_references,
    compute_year_suffixes,
    extract_work_author_key,
    extract_work_year,
)
from src.utils.types import ReferencePart, TextStyle, ViewReference


def test_extract_work_author_key_and_year():
    # Autor comum
    w1 = {"authors": "Silva, João; Santos, Maria", "display_year": "2019"}
    assert extract_work_author_key(w1) == "AUTHORS:SANTOS, MARIA; SILVA, JOÃO"
    assert extract_work_year(w1) == "2019"

    # Órgão jurisdicionado (legislação/jurisprudência)
    w_statute = {
        "work_type": "statute",
        "authors": "BRASIL. Presidência da República",
        "display_year": "2020",
    }
    assert extract_work_author_key(w_statute) == "JURISDICTION:BRASIL"
    assert extract_work_year(w_statute) == "2020"

    w_caselaw = {
        "work_type": "caselaw",
        "authors": "BRASIL. Superior Tribunal de Justiça",
        "display_year": "2020",
    }
    assert extract_work_author_key(w_caselaw) == "JURISDICTION:BRASIL"

    # Sem autor (obra anônima)
    w_anon = {"title": "Memórias do cárcere", "display_year": "1953"}
    assert extract_work_author_key(w_anon) == "TITLE:MEMÓRIAS DO CÁRCERE"
    assert extract_work_year(w_anon) == "1953"


def test_compute_year_suffixes_identical_authors_same_year():
    works = [
        {"id": 1, "authors": "SILVA, João", "title": "Zebra e mente", "display_year": "2019"},
        {"id": 2, "authors": "SILVA, João", "title": "Antelope e razão", "display_year": "2019"},
        {"id": 3, "authors": "SILVA, João", "title": "Outro ano", "display_year": "2020"},
    ]
    suffixes = compute_year_suffixes(works)
    # Obra 2 (título começa com A) recebe '2019a', Obra 1 (Z) recebe '2019b'
    assert suffixes[2] == "2019a"
    assert suffixes[1] == "2019b"
    # Obra 3 em 2020 não tem colisão
    assert 3 not in suffixes


def test_compute_year_suffixes_partial_author_match_does_not_suffix():
    works = [
        {"id": 1, "authors": "SILVA, João", "title": "Obra individual", "display_year": "2019"},
        {"id": 2, "authors": "SILVA, João; SANTOS, Maria", "title": "Obra conjunta", "display_year": "2019"},
    ]
    suffixes = compute_year_suffixes(works)
    # Correspondência parcial NÃO aciona diferenciação
    assert suffixes == {}


def test_compute_year_suffixes_jurisdiction_matching():
    works = [
        {
            "id": 10,
            "work_type": "statute",
            "authors": "BRASIL",
            "title": "Lei nº 13.000",
            "display_year": "2021",
        },
        {
            "id": 11,
            "work_type": "statute",
            "authors": "BRASIL. Presidência da República",
            "title": "Decreto nº 10.000",
            "display_year": "2021",
        },
        {
            "id": 12,
            "work_type": "caselaw",
            "authors": "BRASIL. Supremo Tribunal Federal",
            "title": "Acórdão nº 500",
            "display_year": "2021",
        },
    ]
    suffixes = compute_year_suffixes(works)
    # Títulos ordenados:
    # 1. Acórdão nº 500 (id 12) -> 2021a
    # 2. Decreto nº 10.000 (id 11) -> 2021b
    # 3. Lei nº 13.000 (id 10) -> 2021c
    assert suffixes[12] == "2021a"
    assert suffixes[11] == "2021b"
    assert suffixes[10] == "2021c"


def test_apply_year_suffix_to_reference():
    # Referência padrão
    ref1 = "SILVA, João. A mente. São Paulo: Atlas, 2019."
    assert apply_year_suffix_to_reference(ref1, "2019", "2019a") == (
        "SILVA, João. A mente. São Paulo: Atlas, 2019a."
    )

    # Referência com ano no título e URL com ano
    ref2 = (
        "SILVA, João. O Brasil de 2019: ensaio. São Paulo: Atlas, 2019. "
        "Disponível em: https://exemplo.org/2019/artigo. Acesso em: 10 jan. 2024."
    )
    result = apply_year_suffix_to_reference(ref2, "2019", "2019b")
    expected = (
        "SILVA, João. O Brasil de 2019: ensaio. São Paulo: Atlas, 2019b. "
        "Disponível em: https://exemplo.org/2019/artigo. Acesso em: 10 jan. 2024."
    )
    assert result == expected


def test_apply_year_suffix_to_view_reference():
    view_ref = ViewReference(
        parts=[
            ReferencePart("SILVA, João. ", TextStyle.NORMAL),
            ReferencePart("A mente", TextStyle.BOLD),
            ReferencePart(". São Paulo: Atlas, 2019.", TextStyle.NORMAL),
        ]
    )
    suffixed_ref = apply_year_suffix_to_view_reference(view_ref, "2019", "2019a")
    assert suffixed_ref.parts[0].content == "SILVA, João. "
    assert suffixed_ref.parts[1].content == "A mente"
    assert suffixed_ref.parts[1].style == TextStyle.BOLD
    assert suffixed_ref.parts[2].content == ". São Paulo: Atlas, 2019a."


def test_build_disambiguated_references():
    works = [
        {"id": 1, "authors": "SILVA, João", "title": "B obra", "display_year": "2019"},
        {"id": 2, "authors": "SILVA, João", "title": "A obra", "display_year": "2019"},
    ]
    refs = {
        1: "SILVA, João. B obra. São Paulo: Atlas, 2019.",
        2: "SILVA, João. A obra. São Paulo: Atlas, 2019.",
    }
    result = build_disambiguated_references(works, refs)
    assert result == [
        "SILVA, João. B obra. São Paulo: Atlas, 2019b.",
        "SILVA, João. A obra. São Paulo: Atlas, 2019a.",
    ]


def test_build_disambiguated_view_references_preserves_styles():
    works = [
        {"id": 1, "authors": "SILVA, João", "title": "Zebra e mente", "display_year": "2019"},
        {"id": 2, "authors": "SILVA, João", "title": "Antelope e razão", "display_year": "2019"},
    ]
    refs = {
        1: ViewReference(parts=[
            ReferencePart("SILVA, João. ", TextStyle.NORMAL),
            ReferencePart("Zebra e mente", TextStyle.BOLD),
            ReferencePart(". São Paulo: Atlas, 2019.", TextStyle.NORMAL),
        ]),
        2: ViewReference(parts=[
            ReferencePart("SILVA, João. ", TextStyle.NORMAL),
            ReferencePart("Antelope e razão", TextStyle.BOLD),
            ReferencePart(". In: ", TextStyle.ITALIC),
            ReferencePart("COLETÂNEA", TextStyle.BOLD),
            ReferencePart(". São Paulo: Atlas, 2019.", TextStyle.NORMAL),
        ]),
    }
    view_refs = build_disambiguated_view_references(works, refs)
    assert len(view_refs) == 2

    # Obra 1 (Zebra -> 2019b)
    ref1 = view_refs[0]
    assert ref1.parts[1].content == "Zebra e mente"
    assert ref1.parts[1].style == TextStyle.BOLD
    assert ref1.parts[2].content == ". São Paulo: Atlas, 2019b."

    # Obra 2 (Antelope -> 2019a)
    ref2 = view_refs[1]
    assert ref2.parts[1].content == "Antelope e razão"
    assert ref2.parts[1].style == TextStyle.BOLD
    assert ref2.parts[2].content == ". In: "
    assert ref2.parts[2].style == TextStyle.ITALIC
    assert ref2.parts[3].content == "COLETÂNEA"
    assert ref2.parts[3].style == TextStyle.BOLD
    assert ref2.parts[4].content == ". São Paulo: Atlas, 2019a."


def test_reference_html_and_text():
    ref = ViewReference(parts=[
        ReferencePart("SILVA, João. ", TextStyle.NORMAL),
        ReferencePart("Título em Negrito", TextStyle.BOLD),
        ReferencePart(". In: ", TextStyle.ITALIC),
        ReferencePart("Revista Filosófica", TextStyle.BOLD),
        ReferencePart(", 2024.", TextStyle.NORMAL),
    ])
    html = reference_html(ref)
    assert '<b style="font-weight:bold">Título em Negrito</b>' in html
    assert '<i style="font-style:italic">. In: </i>' in html
    assert '<b style="font-weight:bold">Revista Filosófica</b>' in html
    assert reference_text(ref) == "SILVA, João. Título em Negrito. In: Revista Filosófica, 2024."


def test_copy_references_clipboard():
    ref1 = ViewReference(parts=[
        ReferencePart("AUTOR A. "),
        ReferencePart("Obra A", TextStyle.BOLD),
        ReferencePart(". 2024."),
    ])
    ref2 = ViewReference(parts=[
        ReferencePart("AUTOR B. "),
        ReferencePart("Obra B", TextStyle.ITALIC),
        ReferencePart(". 2024."),
    ])
    assert copy_references([]) is False
    assert copy_references([ref1, ref2]) is True

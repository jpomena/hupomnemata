"""Testes unitários para o segmentador heurístico de referências bibliográficas."""

from src.utils.reference_parser import (
    detect_probable_work_type,
    split_references_block,
)


def test_split_empty_text():
    assert split_references_block("") == []
    assert split_references_block("   \n\n  ") == []


def test_split_header_removal():
    raw = (
        "REFERÊNCIAS BIBLIOGRÁFICAS\n\n"
        "FOUCAULT, Michel. Vigiar e punir: nascimento da prisão. Petrópolis: Vozes, 2014.\n\n"
        "DELEUZE, Gilles. Diferença e repetição. Rio de Janeiro: Graal, 1988."
    )
    res = split_references_block(raw)
    assert len(res) == 2
    assert res[0].startswith("FOUCAULT, Michel.")
    assert res[1].startswith("DELEUZE, Gilles.")


def test_split_double_line_breaks_with_intra_line_wraps():
    raw = (
        "FOUCAULT, Michel. Vigiar e punir: nascimento\n"
        "da prisão. 42. ed. Petrópolis:\n"
        "Vozes, 2014.\n\n"
        "DELEUZE, Gilles; GUATTARI, Félix. O anti-Édipo:\n"
        "capitalismo e esquizofrenia. São Paulo:\n"
        "Editora 34, 2010."
    )
    res = split_references_block(raw)
    assert len(res) == 2
    assert "Vigiar e punir: nascimento da prisão." in res[0]
    assert "Petrópolis: Vozes, 2014." in res[0]
    assert "O anti-Édipo: capitalismo e esquizofrenia." in res[1]


def test_split_no_blank_lines_single_newlines():
    raw = (
        "FOUCAULT, Michel. Vigiar e punir. Petrópolis: Vozes, 2014.\n"
        "DELEUZE, Gilles. Diferença e repetição. Rio de Janeiro: Graal, 1988.\n"
        "KANT, Immanuel. Crítica da razão pura. Lisboa: Calouste Gulbenkian, 2001."
    )
    res = split_references_block(raw)
    assert len(res) == 3
    assert res[0].startswith("FOUCAULT")
    assert res[1].startswith("DELEUZE")
    assert res[2].startswith("KANT")


def test_split_numbered_citations():
    raw = (
        "[1] Turing, A. M. Computing machinery and intelligence. Mind, 1950.\n"
        "[2] Shannon, C. E. A mathematical theory of communication. Bell System Technical Journal, 1948."
    )
    res = split_references_block(raw)
    assert len(res) == 2
    assert res[0].startswith("[1] Turing")
    assert res[1].startswith("[2] Shannon")


def test_detect_probable_work_type():
    # Monografia editorial (livro)
    ref_book = "FOUCAULT, Michel. Vigiar e punir. Petrópolis: Vozes, 2014."
    assert detect_probable_work_type(ref_book) == "editorial_monograph"

    # Artigo de revista
    ref_journal = (
        "HABERMAS, Jürgen. Ação comunicativa e razão destranscendentalizada. "
        "Cadernos de Filosofia Alemã, v. 23, n. 2, p. 11-28, 2018."
    )
    assert detect_probable_work_type(ref_journal) == "journal_article"

    # Trabalho acadêmico (tese)
    ref_thesis = (
        "SILVA, João. A ontologia do presente na filosofia tardia de Heidegger. "
        "2021. 240 f. Tese (Doutorado em Filosofia) - FFLCH, USP, São Paulo, 2021."
    )
    assert detect_probable_work_type(ref_thesis) == "academic_monograph"

    # Anais de evento
    ref_event = (
        "SANTOS, Maria. Inteligência artificial e ontologia. In: ANAIS DO SIMPÓSIO NACIONAL "
        "DE FILOSOFIA, 12., 2022, Curitiba. Anais [...]. Curitiba: UFPR, 2022. p. 45-56."
    )
    assert detect_probable_work_type(ref_event) == "monographic_proceedings"

    # Artigo de jornal
    ref_news = "OLIVEIRA, Pedro. O futuro da leitura. Folha de S.Paulo, São Paulo, p. A4, 10 mar. 2023."
    assert detect_probable_work_type(ref_news) == "newspaper_article"

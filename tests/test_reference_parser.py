"""Testes unitários exaustivos para o segmentador e motor de inferência de referências bibliográficas."""

from __future__ import annotations

import pytest

from src.utils.reference_parser import (
    TYPE_ACADEMIC_MONOGRAPH,
    TYPE_CASELAW,
    TYPE_EDITORIAL_MONOGRAPH,
    TYPE_JOURNAL_ARTICLE,
    TYPE_MISC_DIGITAL,
    TYPE_MONOGRAPHIC_PROCEEDINGS,
    TYPE_NEWSPAPER_ARTICLE,
    TYPE_STATUTE,
    detect_probable_work_type,
    split_references_block,
)


# ===========================================================================
# 1. Testes de Segmentação de Texto Bruto (split_references_block)
# ===========================================================================

def test_split_empty_text():
    assert split_references_block("") == []
    assert split_references_block("   \n\n  ") == []


def test_split_header_removal():
    headers = [
        "REFERÊNCIAS BIBLIOGRÁFICAS",
        "REFERÊNCIAS",
        "BIBLIOGRAFIA",
        "REFERENCES",
        "WORKS CITED",
        "LITERATURE CITED",
        "FONTES BIBLIOGRÁFICAS",
    ]
    for h in headers:
        raw = (
            f"{h}\n\n"
            "FOUCAULT, Michel. Vigiar e punir: nascimento da prisão. Petrópolis: Vozes, 2014.\n\n"
            "DELEUZE, Gilles. Diferença e repetição. Rio de Janeiro: Graal, 1988."
        )
        res = split_references_block(raw)
        assert len(res) == 2, f"Falha ao remover cabeçalho: {h}"
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
        "[2] Shannon, C. E. A mathematical theory of communication. Bell System Technical Journal, 1948.\n"
        "(3) Wiener, N. Cybernetics. MIT Press, 1948."
    )
    res = split_references_block(raw)
    assert len(res) == 3
    assert res[0].startswith("[1] Turing")
    assert res[1].startswith("[2] Shannon")
    assert res[2].startswith("(3) Wiener")


def test_split_repeated_authors_dashes():
    raw = (
        "FOUCAULT, Michel. Vigiar e punir. Petrópolis: Vozes, 2014.\n"
        "______. As palavras e as coisas. São Paulo: Martins Fontes, 2000.\n"
        "------. História da sexualidade. Rio de Janeiro: Graal, 1988.\n"
        "——————. A arqueologia do saber. Rio de Janeiro: Forense Universitária, 2008."
    )
    res = split_references_block(raw)
    assert len(res) == 4
    assert res[0].startswith("FOUCAULT")
    assert res[1].startswith("______.")
    assert res[2].startswith("------.")
    assert res[3].startswith("——————.")


def test_split_statutory_and_apa_starts():
    raw = (
        "BRASIL. Lei nº 14.133, de 1º de abril de 2021. Diário Oficial da União, 2021.\n"
        "Foucault, Michel (1975). Discipline and punish. London: Tavistock.\n"
        "van Dijk, Teun A. (2008). Discourse and power. London: Palgrave."
    )
    res = split_references_block(raw)
    assert len(res) == 3
    assert res[0].startswith("BRASIL.")
    assert res[1].startswith("Foucault, Michel")
    assert res[2].startswith("van Dijk, Teun A.")


# ===========================================================================
# 2. Suíte de 25 Casos: Artigos de Periódicos (journal_article)
# ===========================================================================

JOURNAL_ARTICLE_CASES = [
    # 1. ABNT clássico com vol, num, páginas e meses
    "SILVA, M. A. A revolução copernicana. Revista Brasileira de Filosofia, v. 45, n. 182, p. 120-135, jan./mar. 1996.",
    # 2. Periódico sem número (apenas volume e páginas)
    "CARVALHO, J. O conceito de representação. Cadernos de Filosofia, v. 14, p. 88-104, 2015.",
    # 3. Periódico sem volume (apenas número e páginas)
    "SANTOS, L. R. Ética contemporânea e responsabilidade. Revista Polis, n. 42, p. 15-30, 2018.",
    # 4. Formato APA/internacional compacto vol(issue)
    "TURING, A. M. Computing machinery and intelligence. Mind, 59(236), 433-460, 1950.",
    # 5. Formato internacional com dois-pontos para páginas
    "NAGEL, T. What is it like to be a bat? The Philosophical Review, 83(4): 435-450, 1974.",
    # 6. Nature clássico (volume e páginas sem 'n.')
    "WATSON, J. D.; CRICK, F. H. Molecular structure of nucleic acids. Nature, v. 171, p. 737-738, 1953.",
    # 7. Artigo eletrônico com elocation-id em vez de páginas
    "SOUZA, R. P. et al. Redes neurais aplicadas à visão. Revista de Informática Teórica, v. 28, n. 2, e2021004, 2021.",
    # 8. Artigo com DOI
    "ALMEIDA, F. Razão e sensibilidade na modernidade. Estudos Filosóficos, n. 8, p. 55-70, 2012. https://doi.org/10.1590/0101-3173.2012.v35n1.04",
    # 9. Artigo com ISSN explícito
    "GOMES, P. O tempo em Bergson. Cadernos de Estudos Franceses, v. 12, p. 45-60, 2017. ISSN 1983-4567.",
    # 10. Periódico internacional com sazonalidade (Summer)
    "SMITH, J. Economic fluctuations in emerging markets. Journal of Economic Perspectives, v. 31, n. 3, p. 115-140, Summer 2017.",
    # 11. Periódico com indicação de periodicidade semestral
    "OLIVEIRA, T. Hermenêutica jurídica e aplicação do direito. Revista Jurídica do Sul, v. 5, n. 1, p. 200-225, semestral, 2020.",
    # 12. Artigo com URL e Acesso em (não deve virar documento web)
    "MORAES, C. Inteligência artificial na educação. Revista Ibero-Americana de Educação, v. 80, n. 1, p. 33-48, 2019. Disponível em: https://rieoei.org/3456. Acesso em: 10 out. 2023.",
    # 13. Transactions IEEE
    "CHOMSKY, N. Three models for the description of language. IRE Transactions on Information Theory, v. 2, n. 3, p. 113-124, 1956.",
    # 14. Periódico com 'ano X, n. Y'
    "LIMA, V. Crítica literária e engajamento. Boletim de Humanidades, ano 12, n. 4, p. 10-25, 2019.",
    # 15. Revista da Faculdade de Direito
    "BARROSO, L. R. Neoconstitucionalismo e constitucionalização. Revista da Faculdade de Direito da UERJ, n. 13, p. 1-35, 2005.",
    # 16. Annals of Mathematics
    "WILES, A. Modular elliptic curves and Fermat's Last Theorem. Annals of Mathematics, v. 141, n. 3, p. 443-551, 1995.",
    # 17. The Quarterly Journal of Economics
    "AKERLOF, G. A. The market for 'lemons'. The Quarterly Journal of Economics, 84(3), 488-500, 1970.",
    # 18. Acta Philosophica
    "ROSSI, P. F. Galileu e a ciência moderna. Acta Philosophica, v. 18, n. 2, p. 245-260, 2009.",
    # 19. Paginação precedida de dois pontos sem 'p.'
    "PUTNAM, H. The meaning of 'meaning'. Minnesota Studies in the Philosophy of Science, 7: 131-193, 1975.",
    # 20. Proceedings da NAS (periódico regular)
    "NASH, J. F. Equilibrium points in n-person games. Proceedings of the National Academy of Sciences, 36(1): 48-49, 1950.",
    # 21. Paginação indicada com 'págs.'
    "FERREIRA, B. Linguística e discurso. Revista Alfa, v. 30, págs. 75-89, 1986.",
    # 22. Cadernos de História da Ciência
    "MENDES, E. A epistemologia de Bachelard. Cadernos de História e Filosofia da Ciência, n. 22, p. 33-51, 1998.",
    # 23. Periódico com 'Issue'
    "TAYLOR, C. What is human agency? Human Agency and Language, Issue 2, p. 15-44, 1985.",
    # 24. Faixa de páginas com meia-risca (en-dash)
    "ROSA, G. O mito sertanejo. Revista de Literatura Brasileira, v. 10, n. 1, p. 50–75, 2014.",
    # 25. The Philosophical Review clássico
    "RAWLS, J. Two concepts of rules. The Philosophical Review, v. 64, n. 1, p. 3-32, 1955.",
]


@pytest.mark.parametrize("ref", JOURNAL_ARTICLE_CASES)
def test_detect_journal_articles(ref: str):
    assert detect_probable_work_type(ref) == TYPE_JOURNAL_ARTICLE


# ===========================================================================
# 3. Suíte de 25 Casos: Monografias Editoriais e Capítulos (editorial_monograph)
# ===========================================================================

EDITORIAL_MONOGRAPH_CASES = [
    # 1. Monografia clássica ABNT (Petrópolis: Vozes)
    "FOUCAULT, Michel. Vigiar e punir: nascimento da prisão. Petrópolis: Vozes, 2014.",
    # 2. Livro com menção a edição e coautoria
    "DELEUZE, Gilles; GUATTARI, Félix. O anti-Édipo. 2. ed. São Paulo: Editora 34, 2010.",
    # 3. Livro com total de páginas (não faixa)
    "KANT, Immanuel. Crítica da razão pura. Lisboa: Fundação Calouste Gulbenkian, 2001. 680 p.",
    # 4. Livro clássico em múltiplos volumes
    "MARX, Karl. O capital: crítica da economia política. Tradução de Rubens Enderle. São Paulo: Boitempo, 2013. Livro I, v. 1, 894 p.",
    # 5. Livro internacional Chicago University Press
    "Arendt, H. (1958). The human condition. Chicago: University of Chicago Press.",
    # 6. Livro com ISBN
    "HABERMAS, Jürgen. Teoria do agir comunicativo. São Paulo: WMF Martins Fontes, 2012. ISBN 978-85-7827-567-9.",
    # 7. Livro com organizador (Org.)
    "SILVA, Tomaz Tadeu da (Org.). O sujeito da educação: estudos foucaultianos. Petrópolis: Vozes, 1994.",
    # 8. Livro com tradução explícita e edição
    "HEIDEGGER, Martin. Ser e tempo. Tradução de Márcia Sá Cavalcante. 10. ed. Petrópolis: Vozes, 2015.",
    # 9. Capítulo de livro com 'In:' e organizador
    "ADORNO, Theodor W. A indústria cultural. In: COHN, Gabriel (Org.). Theodor W. Adorno. São Paulo: Ática, 1986. p. 92-99.",
    # 10. Capítulo de coletânea do próprio autor
    "FOUCAULT, Michel. O olho do poder. In: FOUCAULT, Michel. Microfísica do poder. Rio de Janeiro: Graal, 1979. p. 209-227.",
    # 11. Livro da Companhia das Letras com paginação total
    "CHAUÍ, Marilena. A nervura do real: pensamento e política em Spinoza. São Paulo: Companhia das Letras, 1999. 744 p.",
    # 12. Monografia internacional Cambridge University Press
    "SKINNER, Quentin. The foundations of modern political thought. Cambridge: Cambridge University Press, 1978. v. 1.",
    # 13. Tratado com indicação de Tomo
    "PONTES DE MIRANDA, F. C. Tratado de direito privado. Rio de Janeiro: Borsoi, 1971. Tomo 3, 420 p.",
    # 14. Livro internacional com organizadores (Eds.)
    "Nussbaum, M. C., & Sen, A. (Eds.). (1993). The quality of life. Oxford: Clarendon Press.",
    # 15. Capítulo de livro internacional com 'In:'
    "Williams, B. (1981). Moral luck. In: Williams, B. Moral luck: Philosophical papers. Cambridge: Cambridge University Press. pp. 20-39.",
    # 16. Edição revista e ampliada
    "BOBBIO, Norberto. O positivismo jurídico. 1. ed. rev. e ampl. São Paulo: Ícone, 2006.",
    # 17. Livro com páginas romanas preliminares
    "RAWLS, John. Uma teoria da justiça. Tradução de Jussara Simões. São Paulo: Martins Fontes, 2002. xlviii, 670 p.",
    # 18. Livro de editora jurídica de Coimbra
    "CANOTILHO, J. J. Gomes. Direito constitucional e teoria da constituição. 7. ed. Coimbra: Almedina, 2003.",
    # 19. Livro da Editora da USP (Edusp)
    "ARISTÓTELES. Poética. Tradução de Eudoro de Sousa. São Paulo: Edusp, 2008. 140 p.",
    # 20. Monografia editorial Vozes
    "BOFF, Leonardo. Ecologia: grito da terra, grito dos pobres. Petrópolis: Vozes, 1995.",
    # 21. Livro francês Gallimard
    "SARTRE, Jean-Paul. L'être et le néant: essai d'ontologie phénoménologique. Paris: Gallimard, 1943.",
    # 22. Obras reunidas Suhrkamp
    "BENJAMIN, Walter. Gesammelte Schriften. Frankfurt am Main: Suhrkamp, 1974. v. 2.",
    # 23. Capítulo de livro com coordenação
    "NERY JUNIOR, Nelson. Princípios constitucionais. In: WAMBIER, Teresa (Coord.). Processo civil moderno. São Paulo: RT, 2017. p. 55-80.",
    # 24. Routledge internacional em múltiplos volumes
    "POPPER, Karl. The open society and its enemies. London: Routledge, 1945. 2 v.",
    # 25. Livro Forense clássico
    "MEIRELLES, Hely Lopes. Direito administrativo brasileiro. 43. ed. São Paulo: Forense, 2018.",
]


@pytest.mark.parametrize("ref", EDITORIAL_MONOGRAPH_CASES)
def test_detect_editorial_monographs(ref: str):
    assert detect_probable_work_type(ref) == TYPE_EDITORIAL_MONOGRAPH


# ===========================================================================
# 4. Suíte de 25 Casos: Teses, Dissertações e TCCs (academic_monograph)
# ===========================================================================

ACADEMIC_MONOGRAPH_CASES = [
    # 1. Tese clássica com parênteses
    "SILVA, João. A ontologia do presente na filosofia de Heidegger. 2021. 240 f. Tese (Doutorado em Filosofia) - FFLCH, USP, São Paulo, 2021.",
    # 2. Tese sem parênteses
    "RODRIGUES, Carlos. Fenomenologia da percepção e cognição situada. Tese de Doutorado em Filosofia, Faculdade de Filosofia, USP, São Paulo, 2018. 310 f.",
    # 3. Dissertação de mestrado clássica
    "OLIVEIRA, Mariana. O conceito de justiça em Amartya Sen. 2019. 150 f. Dissertação (Mestrado em Ciência Política) - IFCH, Unicamp, Campinas, 2019.",
    # 4. Dissertação sem parênteses
    "SOUZA, Maria. Aprendizado profundo aplicado a imagens médicas. 2019. 110 p. Dissertação de Mestrado, Instituto de Informática, UFRGS, Porto Alegre, 2019.",
    # 5. Tese de Livre-Docência com parênteses
    "SANTOS, Paulo. Epistemologia social e virtudes epistêmicas. Tese (Livre-Docência em Filosofia) - FFLCH, USP, São Paulo, 2015.",
    # 6. PhD dissertation americana
    "JOHNSON, Robert. Essays on modern political economy. PhD dissertation, Department of Economics, Harvard University, Cambridge, MA, 2018.",
    # 7. Doctoral thesis britânica
    "EVANS, David. Logic and ontology in early analytic philosophy. Doctoral thesis, University of Oxford, Oxford, UK, 2016.",
    # 8. Master's thesis internacional
    "MILLER, David. Quantum entanglement in multi-qubit systems. Master's thesis, Department of Physics, Stanford University, Stanford, CA, 2020.",
    # 9. Thèse de doctorat francesa
    "DUPONT, Jean. Les théories de l'action communicative. Thèse de doctorat en philosophie, Université Paris 1 Panthéon-Sorbonne, Paris, 2014.",
    # 10. Monografia de Especialização
    "ALMEIDA, Lucas. Gestão de estoques em microempresas. 2020. 65 f. Monografia (Especialização em Logística) - FGV, Rio de Janeiro, 2020.",
    # 11. Trabalho de Conclusão de Curso (TCC)
    "COSTA, Juliana. Roteamento em redes veiculares. 2022. 80 f. Trabalho de Conclusão de Curso (Bacharelado em Ciência da Computação) - UFMG, Belo Horizonte, 2022.",
    # 12. Monografia de Conclusão de Curso com TCC explícito
    "PEREIRA, Tiago. Políticas de inclusão digital. Monografia de Conclusão de Curso (TCC) - Departamento de Sociologia, UnB, Brasília, 2021.",
    # 13. Dissertação com fórmula 'apresentada para obtenção do título'
    "BARBOSA, Fernanda. A teoria do reconhecimento. Dissertação apresentada ao PPG em Filosofia da UFRJ para obtenção do título de Mestre, Rio de Janeiro, 2017.",
    # 14. Tese com fórmula 'apresentada para obtenção do grau'
    "LIMA, Gustavo. Modelagem computacional de fluidos. Tese apresentada à Escola Politécnica da USP para a obtenção do grau de Doutor em Engenharia Mecânica, São Paulo, 2020.",
    # 15. Monografia de residência/especialização médica
    "CARVALHO, Beatriz. Manifestações clínicas de doenças autoimunes. Monografia (Especialização em Reumatologia) - Faculdade de Medicina, UFRJ, Rio de Janeiro, 2018.",
    # 16. TCC em Direito
    "MARTINS, Rodrigo. A crise do sistema prisional brasileiro. Monografia (Graduação em Direito) - Faculdade de Direito, UFPR, Curitiba, 2021.",
    # 17. Dissertação em PPG com indicação de folhas
    "VIEIRA, Camila. Memória e história na literatura de testemunho. 2018. 135 f. Dissertação (Mestrado) - PPG em Letras, PUCRS, Porto Alegre, 2018.",
    # 18. Ph.D. thesis com pontos
    "BROWN, Sarah. Neural correlates of episodic memory. Ph.D. thesis, Department of Psychology, Yale University, New Haven, 2019.",
    # 19. Tese de Doutorado Profissional
    "RAMOS, Eduardo. Governança corporativa em estatais. Tese (Doutorado Profissional em Administração) - EAESP, FGV, São Paulo, 2021.",
    # 20. Dissertação de Mestrado Profissional
    "FERREIRA, Daniel. Inovações metodológicas no ensino. Dissertação de Mestrado Profissional em Educação, UFSCar, São Carlos, 2020.",
    # 21. Mémoire de master francês
    "BERNARD, Claire. L'éthique environnementale contemporaine. Mémoire de master, Université de Strasbourg, Strasbourg, 2017.",
    # 22. Tese com folhas por extenso
    "NASCIMENTO, Renata. Bioética e biotecnologia. 2022. 215 folhas. Tese de Doutorado, Instituto de Bioética, UnB, Brasília, 2022.",
    # 23. Tese com fórmula 'defendida no instituto'
    "PINTO, Marcos. Teoria de campos e relatividade geral. Tese de Doutorado defendida no Instituto de Física Teórica da Unesp, São Paulo, 2016.",
    # 24. TCC em Engenharia
    "ARAÚJO, Gabriel. Desenvolvimento de sistema solar. Trabalho de Conclusão de Curso (Graduação em Engenharia Elétrica) - UFPE, Recife, 2023.",
    # 25. Tese de livre-docência sem parênteses
    "CARDOSO, Helena. Fundamentos epistemológicos da psicanálise. Tese de livre-docência, Faculdade de Filosofia, USP, Ribeirão Preto, 2019.",
]


@pytest.mark.parametrize("ref", ACADEMIC_MONOGRAPH_CASES)
def test_detect_academic_monographs(ref: str):
    assert detect_probable_work_type(ref) == TYPE_ACADEMIC_MONOGRAPH


# ===========================================================================
# 5. Suíte de 25 Casos: Trabalhos em Anais de Eventos (monographic_proceedings)
# ===========================================================================

MONOGRAPHIC_PROCEEDINGS_CASES = [
    # 1. Simpósio Nacional ABNT com 'In: ANAIS'
    "SANTOS, Maria. Inteligência artificial e ontologia. In: ANAIS DO SIMPÓSIO NACIONAL DE FILOSOFIA, 12., 2022, Curitiba. Anais [...]. Curitiba: UFPR, 2022. p. 45-56.",
    # 2. International Conference com 'In: PROCEEDINGS'
    "VASCONCELOS, A. Semantic web algorithms. In: PROCEEDINGS OF THE INTERNATIONAL CONFERENCE ON COMPUTER SCIENCE, 5., 2020, London. Proceedings [...]. London: IEEE, 2020. p. 110-120.",
    # 3. Encontro Nacional com 'In:'
    "SILVA, R.; COSTA, P. Avaliação de sistemas de transporte. In: ENCONTRO NACIONAL DE ENGENHARIA DE PRODUÇÃO, 38., 2018, Maceió. Anais [...]. Rio de Janeiro: ABEPRO, 2018.",
    # 4. Seminário de Pesquisa
    "OLIVEIRA, J. O conceito de alienação. In: SEMINÁRIO DE PESQUISA EM CIÊNCIAS SOCIAIS, 7., 2019, Belo Horizonte. Anais do VII Seminário... Belo Horizonte: UFMG, 2019. p. 88-102.",
    # 5. International Workshop com 'In:'
    "GARCIA, M. Deep learning for edge devices. In: INTERNATIONAL WORKSHOP ON EMBEDDED SYSTEMS, 3., 2021, San Diego. Proceedings... New York: ACM, 2021. p. 15-22.",
    # 6. SBRC Simpósio Brasileiro de Redes
    "ALMEIDA, T. Segurança em IoT. In: SIMPÓSIO BRASILEIRO DE REDES DE COMPUTADORES (SBRC), 37., 2019, Gramado. Anais [...]. Porto Alegre: SBC, 2019. p. 501-514.",
    # 7. Congresso Brasileiro de Direito Constitucional com Atas
    "BARROS, L. Direitos fundamentais e novas tecnologias. In: CONGRESSO BRASILEIRO DE DIREITO CONSTITUCIONAL, 20., 2020, São Paulo. Atas do Congresso... São Paulo: Malheiros, 2020. p. 40-58.",
    # 8. Colóquio Internacional
    "CASTRO, V. A dialética no jovem Hegel. In: COLÓQUIO INTERNACIONAL HEGEL, 4., 2017, Fortaleza. Anais do Colóquio... Fortaleza: UFC, 2017. p. 120-135.",
    # 9. Jornada de História
    "DIAS, F. Narrativas e história oral. In: JORNADA DE HISTÓRIA E PATRIMÔNIO CULTURAL, 2., 2019, Recife. Anais [...]. Recife: Fundaj, 2019. p. 30-42.",
    # 10. Conferência IEEE com 'In:'
    "KUMAR, A. Machine learning optimization. In: 2021 IEEE INTERNATIONAL CONFERENCE ON DATA MINING (ICDM), 2021, Auckland. Proceedings... Piscataway: IEEE, 2021. pp. 340-349.",
    # 11. ACM SIGMOD com 'In:'
    "SMITH, E. Privacy in distributed databases. In: PROCEEDINGS OF THE 2020 ACM SIGMOD INTERNATIONAL CONFERENCE ON MANAGEMENT OF DATA, 2020, Portland. New York: ACM, 2020. p. 450-462.",
    # 12. Encontro Nacional da ANPOF
    "NOGUEIRA, M. Tempo e subjetividade. In: ENCONTRO NACIONAL DA ANPOF, 18., 2018, Vitória. Anais do XVIII Encontro... São Paulo: ANPOF, 2018. p. 250-251.",
    # 13. Encontro Anual da ANPOCS
    "RIBEIRO, C. Desigualdades sociais no Brasil. In: ENCONTRO ANUAL DA ANPOCS, 42., 2018, Caxambu. Anais [...]. São Paulo: ANPOCS, 2018.",
    # 14. Simpósio Brasileiro de Sensoriamento Remoto
    "LIMA, K. Sensoriamento remoto no Cerrado. In: SIMPÓSIO BRASILEIRO DE SENSORIAMENTO REMOTO, 19., 2019, Santos. Anais [...]. São José dos Campos: INPE, 2019. p. 1500-1503.",
    # 15. Congreso Iberoamericano com Actas
    "PEREZ, J. Inteligencia artificial en educación. In: CONGRESO IBEROAMERICANO DE INFORMÁTICA EDUCATIVA, 10., 2018, Buenos Aires. Actas del Congreso... Buenos Aires: UNESCO, 2018. p. 77-89.",
    # 16. Simpósio Internacional de Sustentabilidade
    "MOREIRA, D. Cidades sustentáveis. In: SIMPÓSIO INTERNACIONAL DE SUSTENTABILIDADE URBANA, 2., 2021, Curitiba. Anais [...]. Curitiba: UFPR, 2021. p. 95-108.",
    # 17. World Energy Summit com Proceedings
    "ZHAO, X. Global trends in renewable energy. In: WORLD ENERGY SUMMIT, 8., 2022, Abu Dhabi. Proceedings... Abu Dhabi: IRENA, 2022. p. 12-25.",
    # 18. Congresso de Iniciação Científica
    "SOUZA, F. Modelagem matemática de epidemias. In: CONGRESSO DE INICIAÇÃO CIENTÍFICA DA UNICAMP, 29., 2021, Campinas. Anais [...]. Campinas: Unicamp, 2021.",
    # 19. Reunião Anual da SBPC
    "BARRETO, A. Ciência aberta no Brasil. In: REUNIÃO ANUAL DA SBPC, 71., 2019, Campo Grande. Anais/Resumos da 71ª Reunião... São Paulo: SBPC, 2019.",
    # 20. Encontro Nacional de Economia ANPEC
    "FERRAZ, P. Produtividade e câmbio na indústria. In: ENCONTRO NACIONAL DE ECONOMIA, 47., 2019, São Paulo. Anais do 47º Encontro... Niterói: ANPEC, 2019.",
    # 21. Congresso Brasileiro de Bioética
    "MEDEIROS, L. Terminalidade da vida e cuidados paliativos. In: CONGRESSO BRASILEIRO DE BIOÉTICA, 13., 2019, Goiânia. Anais [...]. Brasília: CFM, 2019. p. 102-115.",
    # 22. Workshop de Computação Quântica
    "TANAKA, H. Quantum algorithms for chemistry. In: WORKSHOP ON QUANTUM COMPUTING AND INFORMATION, 4., 2020, Tokyo. Proceedings... Tokyo: QCI, 2020. p. 45-58.",
    # 23. Simpósio Brasileiro de Jogos (SBGames)
    "MACHADO, G. Game design e acessibilidade motora. In: SIMPÓSIO BRASILEIRO DE JOGOS E ENTRETENIMENTO DIGITAL (SBGAMES), 19., 2020, Recife. Anais [...]. Porto Alegre: SBC, 2020. p. 230-239.",
    # 24. Encontro da ANPAD (EnANPAD)
    "CARNEIRO, M. Estratégia e transformação digital. In: ENCONTRO DA ANPAD, 43., 2019, São Paulo. Anais do XLIII EnANPAD. Maringá: ANPAD, 2019.",
    # 25. Proceedings de conferência internacional COLING
    "SCHMIDT, U. Natural language processing in legal texts. In: PROCEEDINGS OF THE INTERNATIONAL CONFERENCE ON COMPUTATIONAL LINGUISTICS, 28., 2020, Barcelona. Proceedings... Barcelona: COLING, 2020. p. 2100-2111.",
]


@pytest.mark.parametrize("ref", MONOGRAPHIC_PROCEEDINGS_CASES)
def test_detect_monographic_proceedings(ref: str):
    assert detect_probable_work_type(ref) == TYPE_MONOGRAPHIC_PROCEEDINGS


# ===========================================================================
# 6. Suíte de 25 Casos: Artigos de Jornal / Imprensa (newspaper_article)
# ===========================================================================

NEWSPAPER_ARTICLE_CASES = [
    # 1. Folha de S.Paulo com página e data
    "OLIVEIRA, Pedro. O futuro da leitura no mundo digital. Folha de S.Paulo, São Paulo, p. A4, 10 mar. 2023.",
    # 2. O Estado de S. Paulo com caderno e data diária
    "SANTOS, Lucas. Avanços da ciência brasileira. O Estado de S. Paulo, São Paulo, 15 maio 2022. Caderno Aliás, p. 2.",
    # 3. O Globo com seção de economia
    "GARCIA, Maria. A crise habitacional nas metrópoles. O Globo, Rio de Janeiro, 22 nov. 2021. Economia, p. 18.",
    # 4. Jornal do Brasil clássico com primeiro caderno
    "CARLOS, Josué. Novas perspectivas para o petróleo. Jornal do Brasil, Rio de Janeiro, 5 abr. 1998. Primeiro Caderno, p. 12.",
    # 5. Valor Econômico com caderno B
    "FERREIRA, Carla. Fusões e aquisições batem recorde no trimestre. Valor Econômico, São Paulo, 14 set. 2023. Empresas, p. B1.",
    # 6. Nexo Jornal
    "MENDONÇA, Heloísa. Os impactos da inteligência artificial no mercado editorial. Nexo Jornal, São Paulo, 18 out. 2023.",
    # 7. Correio Braziliense com caderno cidades
    "LIMA, Roberto. A reforma tributária e os municípios. Correio Braziliense, Brasília, 14 nov. 2023. Caderno Cidades, p. 4.",
    # 8. Zero Hora com caderno temático
    "ALMEIDA, Cristina. O clima e a produção de grãos no sul. Zero Hora, Porto Alegre, 28 jan. 2024. Campo e Lavoura, p. 8.",
    # 9. Estado de Minas com caderno de cultura
    "PEREIRA, Geraldo. Patrimônio histórico e turismo em Minas. Estado de Minas, Belo Horizonte, 12 out. 2022. Caderno Cultura, p. 6.",
    # 10. Gazeta do Povo regional
    "ROCHA, Marcelo. Infraestrutura portuária em Paranaguá. Gazeta do Povo, Curitiba, 30 mar. 2021. Economia, p. 11.",
    # 11. Diário Catarinense com página de caderno A
    "SANTOS, Pedro. Nova legislação ambiental no litoral. Diário Catarinense, Florianópolis, 10 mar. 2022, p. A12.",
    # 12. The New York Times com data em inglês e página A
    "FRIEDMAN, Thomas L. The big trends reshaping our world. The New York Times, New York, 14 Feb. 2023. Opinion, p. A23.",
    # 13. The Guardian com data diária
    "WATSON, Emma. Artificial intelligence and creative copyright. The Guardian, London, 22 Jan. 2024. Technology, p. 15.",
    # 14. The Wall Street Journal com caderno B
    "SMITH, Gregory. Tech valuations face rising bond yields. The Wall Street Journal, New York, 5 Oct. 2023. Markets, p. B1.",
    # 15. Le Monde com seção de economia
    "DURAND, Pierre. Les défis de la transition énergétique. Le Monde, Paris, 18 nov. 2022. Économie, p. 8.",
    # 16. El País com seção internacional
    "MARTINEZ, Carmen. Nuevas tensiones geopolíticas. El País, Madrid, 4 dic. 2023. Internacional, p. 10.",
    # 17. Financial Times internacional
    "JOHNSON, Alistair. Central banks face inflation dilemma. Financial Times, London, 19 Apr. 2023. Global Economy, p. 4.",
    # 18. Die Zeit alemão com data
    "MÜLLER, Hans. Die Zukunft der Demokratie. Die Zeit, Hamburg, 15. Juni 2023. Politik, S. 3.",
    # 19. A Tarde da Bahia com data diária
    "NASCIMENTO, Jorge. Desafios do transporte na Baía de Todos-os-Santos. A Tarde, Salvador, 17 jul. 2022. Geral, p. 5.",
    # 20. Diário de Pernambuco com página B
    "BEZERRA, Amanda. Carnaval e economia criativa em Olinda. Diário de Pernambuco, Recife, 8 fev. 2023. Viver, p. B4.",
    # 21. CartaCapital com páginas
    "SILVEIRA, Marco. Os rumos da política industrial brasileira. CartaCapital, São Paulo, 12 ago. 2022. Economia, p. 24-26.",
    # 22. Notícia em jornal com URL
    "COSTA, Flávio. A expansão das energias renováveis no semiárido. Folha de S.Paulo, São Paulo, 20 set. 2023. Disponível em: https://folha.uol.com.br/mercado. Acesso em: 25 set. 2023.",
    # 23. Jornal com 'de janeiro de 2024'
    "MOREIRA, Sandra. O cinema independente em Tiradentes. O Globo, Rio de Janeiro, 26 de janeiro de 2024. Segundo Caderno, p. 3.",
    # 24. The Washington Post com formato Month Day, Year
    "LEWIS, Clara. Biotech breakthroughs in gene editing. The Washington Post, Washington, D.C., November 12, 2023.",
    # 25. Jornal regional com termo 'Jornal'
    "RIBEIRO, Antônio. O polo calçadista do Vale do Sinos. Jornal NH, Novo Hamburgo, 3 de maio de 2021. Economia, p. 7.",
]


@pytest.mark.parametrize("ref", NEWSPAPER_ARTICLE_CASES)
def test_detect_newspaper_articles(ref: str):
    assert detect_probable_work_type(ref) == TYPE_NEWSPAPER_ARTICLE


# ===========================================================================
# 7. Suíte de 25 Casos: Legislação / Normas (statute)
# ===========================================================================

STATUTE_CASES = [
    # 1. Lei Geral de Proteção de Dados (LGPD)
    "BRASIL. Lei nº 13.709, de 14 de agosto de 2018. Lei Geral de Proteção de Dados Pessoais. Diário Oficial da União, Brasília, DF, 15 ago. 2018.",
    # 2. Lei de Licitações
    "BRASIL. Lei nº 14.133, de 1º de abril de 2021. Lei de Licitações e Contratos Administrativos. Diário Oficial da União, Brasília, DF, 1 abr. 2021.",
    # 3. Constituição Federal de 1988
    "BRASIL. [Constituição (1988)]. Constituição da República Federativa do Brasil de 1988. Brasília, DF: Presidência da República, 2016.",
    # 4. Constituição Federal promulgada
    "BRASIL. Constituição da República Federativa do Brasil. Promulgada em 5 de outubro de 1988. Brasília, DF: Senado Federal, 1988.",
    # 5. Código Civil
    "BRASIL. Lei nº 10.406, de 10 de janeiro de 2002. Institui o Código Civil. Diário Oficial da União, Brasília, DF, 11 jan. 2002.",
    # 6. Código Penal
    "BRASIL. Decreto-Lei nº 2.848, de 7 de dezembro de 1940. Código Penal. Diário Oficial da União, Rio de Janeiro, 31 dez. 1940.",
    # 7. Código de Processo Civil
    "BRASIL. Lei nº 13.105, de 16 de março de 2015. Código de Processo Civil. Diário Oficial da União, Brasília, DF, 17 mar. 2015.",
    # 8. CLT
    "BRASIL. Decreto-Lei nº 5.452, de 1º de maio de 1943. Aprova a Consolidação das Leis do Trabalho. Diário Oficial da União, Rio de Janeiro, 9 ago. 1943.",
    # 9. Medida Provisória
    "BRASIL. Medida Provisória nº 1.154, de 1º de janeiro de 2023. Organização básica da Presidência e Ministérios. Diário Oficial da União, Brasília, DF, 1 jan. 2023.",
    # 10. Emenda Constitucional
    "BRASIL. Emenda Constitucional nº 45, de 30 de dezembro de 2004. Altera a Constituição Federal. Diário Oficial da União, Brasília, DF, 31 dez. 2004.",
    # 11. Portaria Ministerial
    "BRASIL. Ministério da Educação. Portaria nº 343, de 17 de março de 2020. Substituição das aulas presenciais por meios digitais. Diário Oficial da União, Brasília, DF, 18 mar. 2020.",
    # 12. Resolução da ANVISA
    "BRASIL. Agência Nacional de Vigilância Sanitária. Resolução da Diretoria Colegiada - RDC nº 430, de 8 de outubro de 2020. Diário Oficial da União, Brasília, DF, 9 out. 2020.",
    # 13. Lei Estadual de São Paulo
    "SÃO PAULO (Estado). Lei nº 10.261, de 28 de outubro de 1968. Estatuto dos Funcionários Públicos Civis. Diário Oficial do Estado de São Paulo, São Paulo, 29 out. 1968.",
    # 14. Decreto Federal
    "BRASIL. Decreto nº 9.203, de 22 de novembro de 2017. Governança da administração pública federal. Diário Oficial da União, Brasília, DF, 23 nov. 2017.",
    # 15. Lei Orgânica Municipal
    "RIO DE JANEIRO (Município). Lei Orgânica do Município do Rio de Janeiro. Promulgada em 5 de abril de 1990. Diário Oficial do Município, Rio de Janeiro, 6 abr. 1990.",
    # 16. Lei Complementar (LRF)
    "BRASIL. Lei Complementar nº 101, de 4 de maio de 2000. Responsabilidade na gestão fiscal. Diário Oficial da União, Brasília, DF, 5 maio 2000.",
    # 17. Decreto-Lei histórico da Reforma Administrativa
    "BRASIL. Decreto-Lei nº 200, de 25 de fevereiro de 1967. Organização da Administração Federal. Diário Oficial da União, Brasília, DF, 27 fev. 1967.",
    # 18. Código de Defesa do Consumidor
    "BRASIL. Lei nº 8.078, de 11 de setembro de 1990. Dispõe sobre a proteção do consumidor. Diário Oficial da União, Brasília, DF, 12 set. 1990.",
    # 19. Instrução Normativa da Receita Federal
    "BRASIL. Secretaria da Receita Federal. Instrução Normativa RFB nº 2.110, de 17 de outubro de 2022. Diário Oficial da União, Brasília, DF, 19 out. 2022.",
    # 20. Marco Civil da Internet
    "BRASIL. Lei nº 12.965, de 23 de abril de 2014. Marco Civil da Internet no Brasil. Diário Oficial da União, Brasília, DF, 24 abr. 2014.",
    # 21. Estatuto da Criança e do Adolescente (ECA)
    "BRASIL. Lei nº 8.069, de 13 de julho de 1990. Estatuto da Criança e do Adolescente. Diário Oficial da União, Brasília, DF, 16 jul. 1990.",
    # 22. Código Tributário Nacional
    "BRASIL. Lei nº 5.172, de 25 de outubro de 1966. Código Tributário Nacional. Diário Oficial da União, Brasília, DF, 27 out. 1966.",
    # 23. Lei Estadual de Minas Gerais
    "MINAS GERAIS. Lei Estadual nº 14.184, de 31 de janeiro de 2002. Processo administrativo estadual. Diário do Executivo, Belo Horizonte, 1 fev. 2002.",
    # 24. Decreto Regulamentador com URL
    "BRASIL. Decreto nº 10.024, de 20 de setembro de 2019. Pregão na forma eletrônica. Disponível em: http://www.planalto.gov.br/ccivil_03/decreto/d10024.htm. Acesso em: 10 mar. 2023.",
    # 25. Código de Processo Penal
    "BRASIL. Decreto-Lei nº 3.689, de 3 de outubro de 1941. Código de Processo Penal. Diário Oficial da União, Rio de Janeiro, 13 out. 1941.",
]


@pytest.mark.parametrize("ref", STATUTE_CASES)
def test_detect_statutes(ref: str):
    assert detect_probable_work_type(ref) == TYPE_STATUTE


# ===========================================================================
# 8. Suíte de 25 Casos: Jurisprudência (caselaw)
# ===========================================================================

CASELAW_CASES = [
    # 1. Recurso Extraordinário no STF com Relator
    "BRASIL. Supremo Tribunal Federal. Recurso Extraordinário 593.840/RS. Relator: Min. Luiz Fux, Tribunal Pleno, julgado em 14/03/2019, Diário de Justiça Eletrônico, 12 abr. 2019.",
    # 2. Ação Direta de Inconstitucionalidade (ADI)
    "BRASIL. Supremo Tribunal Federal. Ação Direta de Inconstitucionalidade nº 4.275/DF. Relator: Min. Marco Aurélio, Tribunal Pleno, julgado em 01/03/2018, DJe 07/03/2019.",
    # 3. Recurso Especial no STJ
    "BRASIL. Superior Tribunal de Justiça. Recurso Especial nº 1.642.315/SP. Relatora: Min. Nancy Andrighi, Terceira Turma, julgado em 18/05/2021, DJe 24/05/2021.",
    # 4. Habeas Corpus no STF
    "BRASIL. Supremo Tribunal Federal. Habeas Corpus nº 126.292/SP. Relator: Min. Teori Zavascki, Tribunal Pleno, julgado em 17/02/2016, DJe 17/05/2016.",
    # 5. Habeas Corpus no STJ
    "SUPERIOR TRIBUNAL DE JUSTIÇA. Habeas Corpus nº 450.123/SP, Rel. Ministro Felix Fischer, Quinta Turma, julgado em 02/08/2018, DJe 10/08/2018.",
    # 6. Súmula Vinculante do STF
    "BRASIL. Supremo Tribunal Federal. Súmula Vinculante nº 11. Diário da Justiça, Brasília, DF, 22 ago. 2008.",
    # 7. Apelação Cível no TJSP
    "SÃO PAULO (Estado). Tribunal de Justiça do Estado de São Paulo. Apelação Cível nº 1002345-67.2020.8.26.0100. Relator: Des. Francisco Loureiro, 1ª Câmara de Direito Privado, julgado em 15/06/2021.",
    # 8. Recurso de Revista no TST
    "BRASIL. Tribunal Superior do Trabalho. Recurso de Revista nº 1000-45.2018.5.02.0001. Relator: Min. Mauricio Godinho Delgado, 3ª Turma, julgado em 14/10/2020, DEJT 16/10/2020.",
    # 9. Apelação no TRF-4
    "BRASIL. Tribunal Regional Federal (4. Região). Apelação Criminal nº 5021365-32.2017.4.04.7000. Relator: Des. Federal João Pedro Gebran Neto, Oitava Turma, julgado em 27/11/2019.",
    # 10. Arguição de Descumprimento de Preceito Fundamental (ADPF)
    "BRASIL. Supremo Tribunal Federal. ADPF 54/DF. Relator: Min. Marco Aurélio, Tribunal Pleno, julgado em 12/04/2012, DJe 30/04/2013.",
    # 11. Agravo em Recurso Especial no STJ
    "BRASIL. Superior Tribunal de Justiça. Agravo Interno no Agravo em Recurso Especial nº 1.450.210/RJ. Relator: Min. Raul Araújo, Quarta Turma, julgado em 04/05/2020, DJe 18/05/2020.",
    # 12. Súmula do STJ
    "BRASIL. Superior Tribunal de Justiça. Súmula nº 385. Segunda Seção, julgado em 27/05/2009, DJe 09/06/2009.",
    # 13. Embargos de Declaração no STF
    "BRASIL. Supremo Tribunal Federal. Embargos de Declaração no RE 870.947/SE. Relator: Min. Luiz Fux, Tribunal Pleno, julgado em 03/10/2019, DJe 03/02/2020.",
    # 14. Agravo de Instrumento no TJRJ
    "RIO DE JANEIRO (Estado). Tribunal de Justiça do Estado do Rio de Janeiro. Agravo de Instrumento nº 0012345-67.2021.8.19.0000. Relator: Des. Mauro Dickstein, 16ª Câmara Cível, julgado em 10/08/2021.",
    # 15. Mandado de Segurança no STJ
    "BRASIL. Superior Tribunal de Justiça. Mandado de Segurança nº 21.345/DF. Relator: Min. Herman Benjamin, Primeira Seção, julgado em 25/09/2019, DJe 14/10/2019.",
    # 16. Ação Declaratória de Constitucionalidade (ADC)
    "BRASIL. Supremo Tribunal Federal. Ação Declaratória de Constitucionalidade nº 43/DF. Relator: Min. Marco Aurélio, Tribunal Pleno, julgado em 07/11/2019, DJe 09/12/2020.",
    # 17. Apelação Cível no TJRS
    "RIO GRANDE DO SUL (Estado). Tribunal de Justiça do Estado do Rio Grande do Sul. Apelação Cível nº 70081234567. Relator: Des. Jorge Luís Dall'Agnol, Segunda Câmara Cível, julgado em 26/02/2020.",
    # 18. Apelação no TRF-1
    "BRASIL. Tribunal Regional Federal da 1ª Região. Apelação Cível nº 0001234-56.2015.4.01.3400. Relator: Desembargador Federal Souza Prudente, Quinta Turma, julgado em 05/08/2020.",
    # 19. Repercussão Geral no STF
    "BRASIL. Supremo Tribunal Federal. Tema 1010 de Repercussão Geral. Recurso Extraordinário nº 1.010.606/RJ. Relator: Min. Dias Toffoli, Tribunal Pleno, julgado em 11/02/2021, DJe 24/05/2021.",
    # 20. Medida Cautelar no STJ com decisão monocrática
    "BRASIL. Superior Tribunal de Justiça. Medida Cautelar no REsp nº 1.800.000/MG. Relator: Min. Luis Felipe Salomão, Quarta Turma, decisão monocrática publicada no DJe de 15/03/2021.",
    # 21. TJDFT acórdão
    "DISTRITO FEDERAL. Tribunal de Justiça do Distrito Federal e dos Territórios. Acórdão nº 1234567, Apelação Cível 0701234-56.2020.8.07.0001, Relator: Des. Arnoldo Camanho, julgado em 11/02/2021, DJE 01/03/2021.",
    # 22. Recurso Ordinário no TRT-2
    "BRASIL. Tribunal Regional do Trabalho da 2ª Região. Recurso Ordinário nº 1001234-56.2019.5.02.0002. Relator: Des. Sergio Pinto Martins, 3ª Turma, julgado em 15/09/2020.",
    # 23. Conflito de Competência no STJ
    "BRASIL. Superior Tribunal de Justiça. Conflito de Competência nº 160.000/DF. Relator: Min. Mauro Campbell Marques, Primeira Seção, julgado em 12/12/2018, DJe 18/12/2018.",
    # 24. IRDR no TJSP
    "SÃO PAULO (Estado). Tribunal de Justiça de São Paulo. IRDR nº 0023456-78.2016.8.26.0000. Relator: Des. Décio Notarangeli, Turma Especial de Direito Público, julgado em 29/09/2017.",
    # 25. Súmula do TST
    "BRASIL. Tribunal Superior do Trabalho. Súmula nº 331. Redação dada pela Resolução nº 174/2011, DEJT divulgado em 27, 30 e 31.05.2011.",
]


@pytest.mark.parametrize("ref", CASELAW_CASES)
def test_detect_caselaw(ref: str):
    assert detect_probable_work_type(ref) == TYPE_CASELAW


# ===========================================================================
# 9. Suíte de 25 Casos: Documentos Digitais Diversos / Web (miscellaneous_digital_document)
# ===========================================================================

MISC_DIGITAL_CASES = [
    # 1. Relatório OMS/WHO com Disponível em e Acesso em
    "WORLD HEALTH ORGANIZATION. Mental health and COVID-19: early evidence of pandemic impact. 2022. Disponível em: https://www.who.int/publications/i/item/WHO-2019-nCoV-Sci_Brief. Acesso em: 15 mar. 2023.",
    # 2. Documentação oficial de linguagem
    "PYTHON SOFTWARE FOUNDATION. Python 3.12 documentation. 2023. Disponível em: https://docs.python.org/3/. Acesso em: 10 jan. 2024.",
    # 3. Blog corporativo/técnico
    "GOOGLE CLOUD. Building responsible AI solutions with vertex AI. Google Cloud Blog, 2023. Disponível em: https://cloud.google.com/blog/responsible-ai. Acesso em: 4 set. 2023.",
    # 4. Repositório no GitHub
    "TORVALDS, Linus. Linux kernel source tree. 2024. Disponível em: https://github.com/torvalds/linux. Acesso em: 12 fev. 2024.",
    # 5. Artigo na Wikipedia com Available at e Accessed on
    "WIKIPEDIA. Artificial neural network. 2023. Available at: https://en.wikipedia.org/wiki/Artificial_neural_network. Accessed on: 15 Aug. 2023.",
    # 6. Relatório online da Anistia Internacional
    "AMNESTY INTERNATIONAL. Annual report 2022/23: human rights. 2023. Available from: https://www.amnesty.org/documents/pol10/2023/en/. Accessed: 20 June 2023.",
    # 7. Portal institucional do Ministério da Saúde (sem ser lei)
    "BRASIL. Ministério da Saúde. Orientações sobre vacinação contra a gripe. 2023. Disponível em: https://www.gov.br/saude/pt-br/assuntos/vacinacao. Acesso em: 18 abr. 2023.",
    # 8. Artigo técnico em blog Medium
    "HENDRICKS, Alice. Understanding modern attention mechanisms. Towards Data Science, Medium.com, 2021. Available at: https://towardsdatascience.com/attention-123. Accessed on: 22 Nov. 2022.",
    # 9. Documentação Mozilla MDN Web Docs
    "MOZILLA DEVELOPER NETWORK. Web APIs: Fetch API. 2023. Available at: https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API. Accessed: 12 Nov. 2023.",
    # 10. Recomendação ética da UNESCO online
    "UNESCO. Recommendation on the ethics of artificial intelligence. 2021. Available at: https://unesdoc.unesco.org/ark:/48223/pf0000381137. Accessed on: 5 Jan. 2023.",
    # 11. Banco Mundial base de dados online
    "WORLD BANK. World development indicators online database. 2023. Available from: https://databank.worldbank.org/source/wdi. Accessed: 14 Oct. 2023.",
    # 12. Padrão web da W3C
    "WORLD WIDE WEB CONSORTIUM. Web content accessibility guidelines (WCAG) 2.2. W3C Recommendation, 2023. Available at: https://www.w3.org/TR/WCAG22/. Accessed on: 10 Nov. 2023.",
    # 13. Stanford Encyclopedia of Philosophy online
    "ZALTA, Edward N. (ed.). The Stanford Encyclopedia of Philosophy. Metaphysics Research Lab, online, 2022. Available at: https://plato.stanford.edu/. Accessed: 18 Dec. 2022.",
    # 14. Blog de Filosofia
    "LEITER, Brian. Leiter Reports: A philosophy blog. 2023. Available at: https://leiterreports.typepad.com/. Accessed on: 14 Feb. 2024.",
    # 15. Painel interativo do Censo no IBGE
    "INSTITUTO BRASILEIRO DE GEOGRAFIA E ESTATÍSTICA (IBGE). Censo Demográfico 2022: panorama interativo. 2023. Disponível em: https://censo2022.ibge.gov.br/panorama/. Acesso em: 29 out. 2023.",
    # 16. Docker Docs online
    "DOCKER INC. Docker documentation: container networking. 2023. Available at: https://docs.docker.com/network/. Accessed: 5 Sep. 2023.",
    # 17. Hugging Face documentação de modelos
    "HUGGING FACE. Transformers documentation for Pytorch. 2023. Available at: https://huggingface.co/docs/transformers. Accessed on: 3 Mar. 2024.",
    # 18. Transmissão no YouTube
    "CONFERÊNCIA NACIONAL DE SAÚDE. Mesa de abertura da 17ª CNS. YouTube, 2023. Disponível em: https://www.youtube.com/watch?v=abcdefghijk. Acesso em: 15 jul. 2023.",
    # 19. Relatório online da OCDE
    "OECD. Artificial intelligence in society. OECD online report, 2019. Available from: https://www.oecd.org/publications/ai-society.htm. Accessed: 12 Jan. 2022.",
    # 20. Episódio de Podcast online
    "FILOSOFIA POP. Episódio 150: Linguagem e pensamento. Podcast, 2022. Disponível em: https://filosofiapop.com.br/podcast/150/. Acesso em: 18 ago. 2023.",
    # 21. FAQ da Receita Federal
    "BRASIL. Receita Federal. Perguntas e respostas do IRPF 2023. Disponível em: https://www.gov.br/receitafederal/pt-br/assuntos/meu-imposto-de-renda. Acesso em: 20 maio 2023.",
    # 22. Atlas da Violência do IPEA plataforma online
    "INSTITUTO DE PESQUISA ECONÔMICA APLICADA (IPEA). Atlas da violência 2023: plataforma interativa. Disponível em: https://www.ipea.gov.br/atlasviolencia/. Acesso em: 14 out. 2023.",
    # 23. RFC do IETF online
    "INTERNET ENGINEERING TASK FORCE (IETF). HTTP/3. RFC 9114, online, 2022. Available at: https://www.rfc-editor.org/rfc/rfc9114.html. Accessed on: 10 Jan. 2024.",
    # 24. Relatório da FAO na web
    "FOOD AND AGRICULTURE ORGANIZATION (FAO). The state of food security 2023. Available from: https://www.fao.org/publications/sofi. Accessed: 1 Sep. 2023.",
    # 25. Portal da Transparência da CGU
    "BRASIL. Controladoria-Geral da União. Portal da Transparência do Governo Federal. 2024. Disponível em: https://portaldatransparencia.gov.br/. Acesso em: 5 fev. 2024.",
]


@pytest.mark.parametrize("ref", MISC_DIGITAL_CASES)
def test_detect_misc_digital_documents(ref: str):
    assert detect_probable_work_type(ref) == TYPE_MISC_DIGITAL

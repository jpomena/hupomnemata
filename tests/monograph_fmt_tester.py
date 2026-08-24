import sys
from pathlib import Path
projeto_raiz = str(Path(__file__).parent.parent)
if projeto_raiz not in sys.path:
    sys.path.insert(0, projeto_raiz)
from src.domains import (
    Author,
    EditorialMonograph,
    BibliographicResource,
    AcademicMonograph
)
from src.strategies import MonographFormatter
from src.utils.types import TextStyle




def run_test():
    # Cenário 1: Livro inteiro (Monografia Editorial)
    # ATENÇÃO: Ajuste os parâmetros abaixo caso a sua classe real exija
    # nomes de atributos ligeiramente diferentes no construtor.
    author = Author(last_name="Tolkien", given_names_initials="J. R. R.")
    academic_author = Author(
        last_name="SANTOS", given_names_initials="J. P. O."
    )

    book = EditorialMonograph(
        title="O Senhor dos Anéis",
        subtitle="a Sociedade do anel",
        publication_place="São Paulo",
        publisher="Martins Fontes",
        display_year="2000",
        edition="1",
        page_quantity=400,
        isbn="978-85-336-1337-9"
    )
    thesis = AcademicMonograph(
        title="Em nome da justiça, a busca por punição",
        subtitle="punitivismo nos discursos do pacote anticrime",
        publication_place="Ribeirão Preto",
        display_year="2024",
        page_quantity=164,
        thesis_type="Dissertação",
        education_level="Mestrado",
        course="Direito",
        faculty="Faculdade de Direito de Ribeirão Preto, Universidade de São Paulo",  # noqa: E501
        defense_year="2024",
    )

    # 1. Cria a obra completa (O Senhor dos Anéis)
    parent_resource = BibliographicResource(
        id=2,
        authors=[author],
        editorial_monograph=book,
        is_partial=False
    )

    # 2. Cria o recurso da parte (O capítulo)
    resource = BibliographicResource(  # noqa: F841
        id=1,
        authors=[author],
        is_partial=True,
        part_title='A Estalagem do Pônei Saltitante',
        part_start_page='145',
        part_end_page='160',
        part_volume='1',
        part_chapter='9',
        parent_work=parent_resource  # <-- AQUI ESTAVA FALTANDO
    )

    academic_resource = BibliographicResource(  # noqa: F841
        id=3,
        authors=[academic_author],
        academic_monograph=thesis,
        is_partial=False
    )

    # Executa o formatador
    view_reference = MonographFormatter.formatter(resource)

    # Imprime o resultado simulando a renderização no terminal
    print("\n=== RESULTADO DA REFERÊNCIA ===")

    texto_final = ""
    for part in view_reference.parts:
        texto = part.content

        if part.style == TextStyle.BOLD:
            texto_final += f"\033[1m{texto}\033[0m"  # Negrito no terminal
        elif part.style == TextStyle.ITALIC:
            texto_final += f"\033[3m{texto}\033[0m"  # Itálico no terminal
        else:
            texto_final += texto

    print(texto_final)
    print("===============================\n")


if __name__ == "__main__":
    run_test()

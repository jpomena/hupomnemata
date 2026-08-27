import sys
from pathlib import Path


project_root = str(Path(__file__).resolve().parents[1])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.db.db import SessionLocal  # noqa: E402
from src.domains import (  # noqa: E402
    AcademicMonograph,
    BibliographicResource,
    CorrespondenceMonograph,
    EditorialMonograph,
)  # noqa: E402
from src.strategies import MonographFormatter  # noqa: E402
from src.utils import TextStyle  # noqa: E402


MONOGRAPH_TYPES = (
    ('1', 'Livro', EditorialMonograph, 'editorial_monograph'),
    ('2', 'Tese / dissertação', AcademicMonograph, 'academic_monograph'),
    (
        '3',
        'Correspondência',
        CorrespondenceMonograph,
        'correspondence_monograph',
    ),
)


def select_monograph_type():
    print('Escolha o tipo de monografia:')
    for option, label, _, _ in MONOGRAPH_TYPES:
        print(f'{option}. {label}')

    selected_option = input('Tipo: ').strip()
    for option, label, model, relation_name in MONOGRAPH_TYPES:
        if option == selected_option:
            return label, model, relation_name
    raise ValueError('Tipo de monografia inválido.')


def run_test():
    label, model, relation_name = select_monograph_type()
    resource_id = int(input('ID da monografia no banco: ').strip())

    with SessionLocal() as session:
        resource = session.get(BibliographicResource, resource_id)
        if resource is None:
            raise ValueError(
                f'Não existe recurso bibliográfico com ID {resource_id}.'
            )

        work = getattr(resource, relation_name)
        if not isinstance(work, model):
            raise ValueError(
                f'O recurso ID {resource_id} não é do tipo {label}.'
            )

        view_reference = MonographFormatter.formatter(resource)

    print('\n=== RESULTADO DA REFERÊNCIA ===')
    texto_final = ''
    for part in view_reference.parts:
        texto = part.content
        if part.style == TextStyle.BOLD:
            texto_final += f'\033[1m{texto}\033[0m'
        elif part.style == TextStyle.ITALIC:
            texto_final += f'\033[3m{texto}\033[0m'
        else:
            texto_final += texto

    print(texto_final)
    print('===============================\n')


if __name__ == '__main__':
    run_test()

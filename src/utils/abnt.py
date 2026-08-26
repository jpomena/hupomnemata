from datetime import date, datetime
from typing import Iterable, TYPE_CHECKING, List, Tuple
from .types import TextStyle

if TYPE_CHECKING:

    from src.domains import Author, BibliographicResource


class ABNTUtils:
    @staticmethod
    def format_authors(authors: Iterable['Author']) -> str:
        '''
        Padroniza a lista de autores para qualquer referência ABNT.
        Ex: SILVA, J.; SANTOS, M.
        Ex: BRASIL. Ministério da Saúde.
        '''
        authors_strs = []
        if not authors:
            return ''

        for a in authors:
            if not a.corporation:
                # 1. Sem espaço no começo (o join já cuida da separação)
                authors_strs.append(
                    f'{a.last_name.upper()}, {a.given_names_initials}'
                )
            else:
                full_name = f'{a.given_names} {a.last_name}'.strip()

                if a.jurisdiction:
                    authors_strs.append(
                        f'{a.jurisdiction.upper()}. {full_name}.'
                    )
                else:
                    authors_strs.append(full_name.upper())

        return '; '.join(authors_strs)

    @staticmethod
    def format_part_header(
        partial_bibliographic_resource: BibliographicResource
    ) -> List[Tuple[str, TextStyle]]:
        '''Monta a string inicial de autoria e título da parte (capítulo, etc).
        '''
        parts = []
        parts.append((
                ABNTUtils.format_authors(
                    partial_bibliographic_resource.authors
                ),
                TextStyle.NORMAL
        ))
        parts.append((
            f' {partial_bibliographic_resource.part_title}',
            TextStyle.NORMAL
        ))
        if partial_bibliographic_resource.part_subtitle:
            parts.append((
                f': {partial_bibliographic_resource.part_subtitle}',
                TextStyle.NORMAL
            ))
        return parts

    @staticmethod
    def format_title_and_subtitle(
        title: str,
        subtitle: str | None = None,
        title_style: TextStyle = TextStyle.NORMAL
    ) -> List[Tuple[str, TextStyle]]:
        '''
        Formata título e subtítulo. O estilo do título pode variar
        (negrito na obra principal, normal na parte).
        O subtítulo, segundo a ABNT, nunca recebe destaque (sempre normal).
        '''
        parts = []
        parts.append((f' {title}', title_style))

        if subtitle:
            parts.append((f': {subtitle}', TextStyle.NORMAL))
        parts.append(('.', TextStyle.NORMAL))

        return parts

    @staticmethod
    def format_abbrev_date(
        date: date | datetime
    ) -> str:
        MESES_ABREV = {
            1: 'jan.', 2: 'fev.', 3: 'mar.', 4: 'abr.',
            5: 'maio', 6: 'jun.', 7: 'jul.', 8: 'ago.',
            9: 'set.', 10: 'out.', 11: 'nov.', 12: 'dez.'
        }
        day = date.day
        month_raw = date.month
        month = MESES_ABREV[month_raw]
        year = date.strftime('%Y')

        return f'{day} {month} {year}'

from datetime import date, datetime
from typing import Iterable, TYPE_CHECKING, List, Tuple
from .types import TextStyle

if TYPE_CHECKING:

    from src.domains import Author, BibliographicResource


class ABNTUtils:
    @staticmethod
    def fmt_authors(authors: Iterable['Author']) -> str:
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
                full_name = f'{a.given_names}'.strip()

                if a.jurisdiction:
                    authors_strs.append(
                        f'{a.jurisdiction.given_names.upper()}. {full_name}.'
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
        work = partial_bibliographic_resource.specific_work
        if work is None:
            raise ValueError(
                f'O recurso bibliográfico ID '
                f'{partial_bibliographic_resource.id} '
                'não possui nenhuma obra específica associada.'
            )

        parts = []
        parts.append((
                ABNTUtils.fmt_authors(
                    partial_bibliographic_resource.authors
                ),
                TextStyle.NORMAL
        ))
        parts.append((
            f' {work.title}',
            TextStyle.NORMAL
        ))
        if work.subtitle:
            parts.append((
                f': {work.subtitle}',
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
        title_text = title.strip().lower()
        if title_text:
            title_text = title_text.capitalize()
        subtitle_text = subtitle.strip() if subtitle else ''

        parts = []
        parts.append((f' {title_text}', title_style))

        if subtitle_text:
            parts.append((f': {subtitle_text}', TextStyle.NORMAL))
        parts.append(('.', TextStyle.NORMAL))

        return parts

    @staticmethod
    def format_abbrev_date(
        date: date | datetime | None
    ) -> str:
        if date is None:
            return '[s.d.]'

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

    @staticmethod
    def fmt_full_date(
            date: date | datetime | None
    ) -> str:
        if date is None:
            return '[s.d.]'

        MESES = {
            1: 'janeiro', 2: 'fevereiro', 3: 'março', 4: 'abril',
            5: 'maio', 6: 'junho', 7: 'julho', 8: 'agosto',
            9: 'setembro', 10: 'outubro', 11: 'novembro', 12: 'dezembro'
        }
        day = date.day
        month_raw = date.month
        month = MESES[month_raw]
        year = date.strftime('%Y')

        return f'{day} de {month} de {year}'

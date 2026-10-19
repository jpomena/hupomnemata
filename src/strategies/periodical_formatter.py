from src.utils import ABNTUtils as Utils
from typing import List, TYPE_CHECKING
from src.domains import (
    Magazine,
    PeriodicalCollection,
    JournalArticle,
    NewspaperArticle
)
from src.utils import (
    ViewReference,
    TextStyle,
    ReferencePart
)

if TYPE_CHECKING:
    from src.domains import BibliographicResource


class PeriodicalFormatter:

    @staticmethod
    def formatter(
        bibliographic_resource: 'BibliographicResource'
    ) -> ViewReference:
        '''
        Método principal que orquestra a montagem da referência.
        Funciona como um 'sumário' do que está acontecendo.
        '''
        parts: List[ReferencePart] = []

        PeriodicalFormatter._validate_specific_work(bibliographic_resource)
        work = bibliographic_resource.specific_work
        if not work:
            return ViewReference(parts=parts)

        # Artigos sempre são parciais: precisam de autor e título do artigo
        if isinstance(work, (JournalArticle, NewspaperArticle)):
            PeriodicalFormatter._append_article_header(
                bibliographic_resource, parts
            )

        PeriodicalFormatter._append_journal_title(work, parts)
        if isinstance(work, (JournalArticle, NewspaperArticle)):
            del parts[-1]
            parts.append(ReferencePart(content=','))
        PeriodicalFormatter._append_specific_details(work, parts)
        PeriodicalFormatter._append_suffix_details(
            bibliographic_resource, parts
        )
        return ViewReference(parts=parts)

    @staticmethod
    def _validate_specific_work(bibliographic_resource):
        if not bibliographic_resource.specific_work:
            raise ValueError(
                f'O recurso ID {bibliographic_resource.id} '
                'não possui nenhuma obra específica associada.'
            )

    @staticmethod
    def _append_article_header(
        bibliographic_resource: 'BibliographicResource',
        parts: List[ReferencePart]
    ) -> None:
        work = bibliographic_resource.specific_work
        if not work:
            return

        parts.append(
            ReferencePart(
                content=Utils.fmt_authors(
                    bibliographic_resource.authors
                )
            )
        )

        for content, style in Utils.format_title_and_subtitle(
            title=work.title,
            subtitle=work.subtitle if work.subtitle else None,
            title_style=TextStyle.NORMAL,
            without_author=not bibliographic_resource.authors,
        ):
            parts.append(ReferencePart(content=content, style=style))

    @staticmethod
    def _append_journal_title(work, parts):
        if not work:
            return

        if isinstance(work, Magazine):
            title = work.title
            subtitle = work.subtitle
        elif isinstance(work, (JournalArticle, PeriodicalCollection)):
            magazine = PeriodicalFormatter._magazine_for(work)
            title = magazine.title
            subtitle = work.journal_subtitle
        else:
            title = work.journal_title
            subtitle = work.journal_subtitle

        for content, style in Utils.format_title_and_subtitle(
            title=title,
            subtitle=subtitle if subtitle else None,
            title_style=TextStyle.BOLD,
            without_author=(
                isinstance(work, (Magazine, PeriodicalCollection))
                and not work.authors
            ),
        ):
            parts.append(ReferencePart(content=content, style=style))

    @staticmethod
    def _magazine_for(work) -> Magazine:
        parent = getattr(work, 'parent_bibliographic_resource', None)
        magazine = (
            parent.specific_work if parent is not None else None
        )
        if not isinstance(magazine, Magazine):
            raise ValueError(
                'Artigo ou coleção periódica sem uma revista vinculada.'
            )
        return magazine

    @staticmethod
    def _append_specific_details(work, parts):
        if not work:
            return

        match work:
            case PeriodicalCollection():
                parts[-1].content = '.'
                parts.extend(
                    PeriodicalFormatter._format_collection_details(work)
                )
            case Magazine():
                parts.extend(
                    PeriodicalFormatter._format_magazine_details(work)
                )
            case JournalArticle():
                parts.extend(
                    PeriodicalFormatter._format_journal_article_details(
                        work
                    )
                )
            case NewspaperArticle():
                parts.extend(
                    PeriodicalFormatter._format_newspaper_article_details(
                        work
                    )
                )

    @staticmethod
    def _append_suffix_details(
        bibliographic_resource, parts
    ):
        work = bibliographic_resource.specific_work
        if not work or not work.url:
            return

        date = Utils.format_abbrev_date(work.viewed_at)
        parts.append(
            ReferencePart(
                content=(
                    ' Disponível em:'
                    f' {work.url}.'
                    ' Acesso em:'
                    f' {date}.'
                )
            )
        )

    # ==========================================
    #           MÉTODOS AUXILIARES
    # ==========================================

    @staticmethod
    def _format_collection_details(
        collection: PeriodicalCollection
    ) -> List[ReferencePart]:
        '''Trata particularidades de publicação de uma Coleção.'''
        parts = []
        magazine = PeriodicalFormatter._magazine_for(collection)

        parts.append(
            ReferencePart(
                content=(
                    f' {magazine.publication_place}:'
                    f' {collection.publisher},'
                    f' {collection.first_volume_year}'
                )
            )
        )
        if collection.last_volume_year:
            parts.append(
                ReferencePart(
                    content=f'–{collection.last_volume_year}'
                )
            )
        parts.append(ReferencePart(content='.'))

        if (
            collection.is_partial
            and collection.consult_start_year is not None
            and collection.consult_end_year is not None
        ):
            parts.append(ReferencePart(
                content=(
                    f' {collection.consult_start_year}'
                    f'–{collection.consult_end_year}.'
                )
            ))

        if collection.issn:
            parts.append(
                ReferencePart(content=f' ISSN: {collection.issn}.')
            )

        return parts

    @staticmethod
    def _format_magazine_details(
        magazine: Magazine,
    ) -> List[ReferencePart]:
        return [
            ReferencePart(
                content=f' {magazine.publication_place}.'
            )
        ]

    @staticmethod
    def _format_journal_article_details(
        article: JournalArticle
    ) -> List[ReferencePart]:
        parts = []
        magazine = PeriodicalFormatter._magazine_for(article)
        parts.append(
            ReferencePart(content=f' {magazine.publication_place},')
        )

        if article.year_season:
            parts.append(ReferencePart(
                content=f' ano {article.year_season},'
            ))

        if article.volume:
            parts.append(ReferencePart(
                content=f' vol. {article.volume},'
            ))

        if article.number:
            parts.append(ReferencePart(
                content=f' n. {article.number},'
            ))

        if article.part_start_page and article.part_end_page:
            parts.append(ReferencePart(
                content=(
                    f' p. {article.part_start_page}'
                    f'–{article.part_end_page},'
                )
            ))

        date = Utils.format_abbrev_month_year(article.date_anchor)
        parts.append(ReferencePart(
            content=f' {date}.'
        ))

        if article.issn:
            parts.append(ReferencePart(
                content=f' ISSN: {article.issn}.'
            ))

        return parts

    @staticmethod
    def _format_newspaper_article_details(
        article: NewspaperArticle
    ) -> List[ReferencePart]:
        parts = []

        parts.append(
            ReferencePart(content=f' {article.publication_place}')
        )
        if article.year_season:
            parts.append(ReferencePart(
                content=f' ano {article.year_season},'
            ))
        if article.volume:
            parts.append(ReferencePart(
                content=f' vol. {article.volume},'
            ))
        if article.number:
            parts.append(ReferencePart(
                content=f' n. {article.number},'
            ))

        def get_pagination(suffix: str) -> str:
            if not article.start_page or 's.p.' in article.start_page:
                return f' Não paginado{suffix}'
            if article.start_page == article.end_page:
                return f' p. {article.start_page}{suffix}'
            return f' p. {article.start_page}–{article.end_page}{suffix}'

        formatted_date = Utils.format_abbrev_date(article.date_anchor)

        if article.section:
            parts.append(ReferencePart(
                content=f' {formatted_date}. {article.section},'
            ))
            parts.append(ReferencePart(content=get_pagination(suffix='.')))
        else:
            parts.append(ReferencePart(content=get_pagination(suffix=',')))
            parts.append(ReferencePart(content=f' {formatted_date}.'))

        return parts

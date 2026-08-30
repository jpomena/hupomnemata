from src.utils import ABNTUtils as Utils
from typing import TYPE_CHECKING
from src.domains import (
    MonographicProceedings,
    PeriodicalProceedings
)
from src.utils import (
    ViewReference,
    ReferencePart,
    TextStyle
)

if TYPE_CHECKING:
    from src.domains import BibliographicResource


class ProceedingsFormatter:

    @staticmethod
    def formatter(bib_res: 'BibliographicResource') -> ViewReference:
        specific_work = bib_res.specific_work

        if not isinstance(
            specific_work, (PeriodicalProceedings, MonographicProceedings)
        ):
            raise TypeError("Tipo de documento inválido.")

        if (
            not specific_work.is_partial
            and isinstance(specific_work, MonographicProceedings)
            and not specific_work.published
        ):
            return ViewReference(
                ProceedingsFormatter._format_unpublished(specific_work)
            )

        parts = []

        if specific_work.is_partial:
            parent_resource = (
                specific_work.parent_bibliographic_resource
            )
            if parent_resource is None:
                raise TypeError(
                    "Obra pai (parent_bibliographic_resource) não encontrada."
                )

            main_doc = parent_resource.specific_work
            if not isinstance(
                main_doc, (PeriodicalProceedings, MonographicProceedings)
            ):
                raise TypeError("Tipo de documento principal/pai inválido.")

            parts.extend(
                ProceedingsFormatter
                ._format_child_work(specific_work, main_doc)
            )
        else:
            main_doc = specific_work

        parts.extend(
            ProceedingsFormatter._format_event_and_title(
                main_doc, specific_work.is_partial
            )
        )

        parts.extend(
            ProceedingsFormatter._format_publication_data(
                main_doc, specific_work.is_partial
            )
        )

        if specific_work.is_partial:
            parts.extend(
                ProceedingsFormatter._format_pagination(specific_work)
            )

        return ViewReference(parts)

    @staticmethod
    def _format_child_work(
        child_doc: MonographicProceedings | PeriodicalProceedings,
        parent_doc: MonographicProceedings | PeriodicalProceedings
    ) -> list[ReferencePart]:
        parts = [
            ReferencePart(f'{Utils.fmt_authors(child_doc.authors)}.'),
            ReferencePart(f' {child_doc.title}')
        ]
        if child_doc.subtitle:
            parts.append(ReferencePart(f': {child_doc.subtitle}'))

        if isinstance(parent_doc, MonographicProceedings):
            parts.append(ReferencePart('. In:', TextStyle.ITALIC))
        else:
            parts.append(ReferencePart('.'))

        return parts

    @staticmethod
    def _format_unpublished(
        document: MonographicProceedings
    ) -> list[ReferencePart]:
        parts = [
            ReferencePart(f'{Utils.fmt_authors(document.authors)}'),
            ReferencePart(f' {document.title}', TextStyle.BOLD)
        ]
        if document.subtitle:
            parts.append(ReferencePart(f': {document.subtitle}'))
        parts.append(ReferencePart(f'. {document.date_anchor}.'))

        return parts

    @staticmethod
    def _format_event_and_title(
        document: MonographicProceedings | PeriodicalProceedings,
        is_partial: bool
    ) -> list[ReferencePart]:
        # Adiciona espaço inicial se vier depois
        #  do "In:" ou do título do artigo
        prefix = ' ' if is_partial else ''
        parts = [ReferencePart(f'{prefix}{document.event_name.upper()}')]

        if document.event_number:
            parts.append(ReferencePart(f', {document.event_number}'))

        if document.event_place:
            parts.append(ReferencePart(
                f', {document.event_year}, {document.event_place}.'
            ))
        else:
            parts.append(ReferencePart(f', {document.event_year}.'))

        parts.append(ReferencePart(f' {document.title}', TextStyle.BOLD))

        if document.subtitle:
            parts.append(ReferencePart(f': {document.subtitle}'))

        return parts

    @staticmethod
    def _format_publication_data(
        document: MonographicProceedings | PeriodicalProceedings,
        is_partial: bool
    ) -> list[ReferencePart]:
        parts = []
        if isinstance(document, MonographicProceedings):
            parts.append(ReferencePart(
                f'. {document.publication_place}: {document.publisher},'
                f' {document.display_year}.'
            ))
            # Adiciona páginas totais apenas se for a obra completa
            if not is_partial and document.page_quantity:
                parts.append(ReferencePart(f' {document.page_quantity} p.'))

        elif isinstance(document, PeriodicalProceedings):
            parts.append(ReferencePart(
                f', {document.publication_place}, ano/vol.'
                f' {document.vol_or_year}, n. {document.number},'
                f' {document.start_page}–{document.end_page},'
                f' {Utils.format_abbrev_date(document.publication_date)}.'
            ))
        return parts

    @staticmethod
    def _format_pagination(
        specific_work: MonographicProceedings | PeriodicalProceedings
    ) -> list[ReferencePart]:
        return [
            ReferencePart(
                ' p. '
                f'{specific_work.part_start_page}'
                f'–{specific_work.part_end_page}.'
            )
        ]

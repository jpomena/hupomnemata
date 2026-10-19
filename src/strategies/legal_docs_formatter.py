from src.domains import Statute, CaseLaw
from src.utils import ReferencePart, TextStyle, ViewReference
from src.utils import ABNTUtils as Utils
from typing import List


class LegalDocsFormatter:

    @staticmethod
    def formatter(
        work: CaseLaw | Statute
    ) -> ViewReference:
        ref_parts = []

        ref_parts.extend(LegalDocsFormatter._format_author(work=work))
        match work:
            case CaseLaw():
                ref_parts.extend(
                    LegalDocsFormatter
                    ._format_caselaw_specifics(
                        work=work
                    )
                )
            case Statute():
                ref_parts.extend(
                    LegalDocsFormatter
                    ._format_statute_specifics(
                        work=work
                    )
                )
        ref_parts.extend(
            LegalDocsFormatter
            ._format_publication_data(
                work=work
            )
        )
        ref_parts.extend(
            LegalDocsFormatter
            ._format_suffix_details(
                work=work
            )
        )

        return ViewReference(ref_parts)

    @staticmethod
    def _format_author(
        work: Statute | CaseLaw
    ) -> List[ReferencePart]:
        authors = work.authors
        parts = []

        parts.append(ReferencePart(f' {Utils.fmt_authors(authors)}'))
        if isinstance(work, CaseLaw) and (
            work.region or work.panel
        ):
            panels = []
            if work.region:
                panels.append(work.region)
            if work.panel:
                panels.append(work.panel)
            panels_str = ', '.join(panels)
            parts.append(ReferencePart(f'({panels_str})'))
        parts.append(ReferencePart('.'))

        return parts

    @staticmethod
    def _format_statute_specifics(
        work: Statute
    ) -> List[ReferencePart]:
        parts = []
        title = work.title
        if not Utils.fmt_authors(work.authors):
            title = Utils.format_title_without_author(title)
        parts.append(ReferencePart(
            f' {title}, de {Utils.fmt_full_date(work.promulgation_date)}.'
            f' {work.abstract}.'
        ))

        return parts

    @staticmethod
    def _format_caselaw_specifics(work: CaseLaw) -> List[ReferencePart]:
        parts = []

        title = work.title
        if not Utils.fmt_authors(work.authors):
            title = Utils.format_title_without_author(title)
        parts.append(ReferencePart(f' {title}.'))
        if work.case_number:
            parts.append(ReferencePart(f' Processo n. {work.case_number}.'))
        if work.abstract:
            parts.append(ReferencePart(f' {work.abstract}.'))
        if work.rapporteur:
            parts.append(ReferencePart(f' Relator: {work.rapporteur}.'))
        if work.decision_date:
            parts.append(ReferencePart(f' Julgado em {work.decision_date}.'))

        return parts

    @staticmethod
    def _format_publication_data(
        work: CaseLaw | Statute
    ) -> List[ReferencePart]:
        parts = []
        publication_date = work.date_anchor

        parts.append(ReferencePart(
            f' {work.publication_media}', TextStyle.BOLD
        ))
        if work.publication_number:
            parts.append(ReferencePart(f', {work.publication_number}'))

        parts.append(ReferencePart(
            f', {Utils.format_abbrev_date(publication_date)}.'
        ))

        return parts

    @staticmethod
    def _format_suffix_details(
        work: CaseLaw | Statute
    ) -> List[ReferencePart]:
        parts = []
        if work.additional_notes:
            parts.append(ReferencePart(f' {work.additional_notes}.'))
        if work.url:
            parts.append(
                ReferencePart(
                    content=(
                        ' Disponível em:'
                        f' {work.url}.'
                        ' Acesso em:'
                        f' {Utils.format_abbrev_date(work.viewed_at)}.'
                    )
                )
            )

        return parts

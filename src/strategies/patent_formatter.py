from src.utils import ABNTUtils as Utils
from typing import List
from src.domains import Patent
from src.utils import (
    ViewReference,
    ReferencePart,
)


class PatentFormatter:

    @staticmethod
    def formatter(
        work: Patent
    ) -> ViewReference:
        ref_parts = []

        ref_parts.extend(PatentFormatter._format_authors_and_title(work=work))
        ref_parts.extend(PatentFormatter._format_patent_details(work=work))
        ref_parts.extend(PatentFormatter._format_dates(work=work))

        return ViewReference(ref_parts)

    @staticmethod
    def _format_authors_and_title(
        work: Patent
    ) -> List[ReferencePart]:
        title = work.title
        authors = work.authors
        parts = []

        author_text = Utils.fmt_authors(authors)
        parts.append(ReferencePart(f' {author_text}'))
        parts.append(ReferencePart('.'))
        formatted_title = ''.join(
            content
            for content, _ in Utils.format_title_and_subtitle(
                title,
                without_author=not author_text,
            )
        )
        parts.append(ReferencePart(formatted_title))

        return parts

    @staticmethod
    def _format_patent_details(
        work: Patent
    ) -> List[ReferencePart]:
        parts = []

        if work.applicant:
            parts.append(ReferencePart(
                f' Depositante/Titular: {work.applicant}.'
            ))
        if work.representative:
            parts.append(ReferencePart(
                f' Procurador: {work.representative}.'
            ))
        parts.append(f' {work.number}')

        return parts

    @staticmethod
    def _format_dates(work: Patent) -> List[ReferencePart]:
        parts = []

        parts.append(ReferencePart(
            f' Depósito: {Utils.format_abbrev_date(work.filing_date)}.'
        ))
        parts.append(ReferencePart(
            f' Depósito: {Utils.format_abbrev_date(work.grant_date)}.'
        ))

        return parts

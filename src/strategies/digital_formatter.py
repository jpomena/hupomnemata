from src.domains import MiscDigitalDocument
from src.utils import ReferencePart, ViewReference
from src.utils import ABNTUtils as Utils


class DigitalFormatter:

    @staticmethod
    def formatter(
        work: MiscDigitalDocument
    ) -> ViewReference:
        parts = []
        author_text = Utils.fmt_authors(work.authors)
        parts.append(ReferencePart(author_text))
        title = (
            work.title
            if author_text
            else Utils.format_title_without_author(work.title)
        )
        parts.append(ReferencePart(f' {title}'))
        if work.subtitle:
            parts.append(ReferencePart(f': {work.subtitle}'))
        parts.append(ReferencePart('.'))
        if work.version:
            parts.append(ReferencePart(f' {work.version}.'))
        parts.append(ReferencePart(
            f' {work.publication_place}, {work.display_year}.'
        ))
        if work.additional_notes:
            parts.append(
                ReferencePart(content=f' {work.additional_notes}.')
            )

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

        return ViewReference(parts)

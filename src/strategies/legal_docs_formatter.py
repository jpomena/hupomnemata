from src.domains import Statute, CaseLaw, AdministrativeAct
from src.utils import ABNTUtils as Utils, ReferencePart, TextStyle
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.domains import Author


class LegalDocsFormatter:

    @staticmethod
    def _format_author(author: Author) -> ReferencePart:
        jurisdiction = author.jurisdiction
        parts = []
        if jurisdiction:
            parts.append(ReferencePart(f'{jurisdiction.given_names} {jurisdiction.last_name}'))

        return ReferencePart(f' ')

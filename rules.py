from works import ReferenceType
from enum import Enum


class FieldRequirement(Enum):
    REQUIRED = 'required'
    CONDITIONAL = 'conditional'
    OPTIONAL = 'optional'

COMMON_GLOBAL_RULES = {
    'agent': FieldRequirement.REQUIRED,
    'object': FieldRequirement.REQUIRED,
    'date': FieldRequirement.REQUIRED,
}

CONDITIONAL_GLOBAL_RULES = {
    'online': {
        'url': FieldRequirement.REQUIRED,
        'access_date': FieldRequirement.REQUIRED,
    },
    'doi': {
        'doi': FieldRequirement.CONDITIONAL
    }
}

FALLBACK_RULES = {
    'publication_place': '[S. l.]',
    'publisher': '[s. n.]',
    'date': '[s. d.]',
}


BOOK_RULES = {
    'publication_place': FieldRequirement.REQUIRED,
    'publisher': FieldRequirement.REQUIRED,
    'edition': FieldRequirement.CONDITIONAL,
    'pages': FieldRequirement.OPTIONAL,
    'series': FieldRequirement.OPTIONAL,
    'translator': FieldRequirement.OPTIONAL,
}


BOOK_PART_RULES = {
    'container': FieldRequirement.REQUIRED,
    'start_page': FieldRequirement.REQUIRED,
    'end_page': FieldRequirement.REQUIRED,
    'publication_place': FieldRequirement.REQUIRED,
    'publisher': FieldRequirement.REQUIRED,
    'edition': FieldRequirement.CONDITIONAL,
    'translator': FieldRequirement.OPTIONAL,
}


JOURNAL_ARTICLE_RULES = {
    'container': FieldRequirement.REQUIRED,
    'start_page': FieldRequirement.REQUIRED,
    'end_page': FieldRequirement.REQUIRED,
    'volume': FieldRequirement.CONDITIONAL,
    'issue': FieldRequirement.CONDITIONAL,
    'publication_month': FieldRequirement.CONDITIONAL,
    'doi': FieldRequirement.OPTIONAL,
}


NEWSPAPER_ARTICLE_RULES = {
    'container': FieldRequirement.REQUIRED,
    'publication_date': FieldRequirement.REQUIRED,
    'section': FieldRequirement.CONDITIONAL,
    'page': FieldRequirement.CONDITIONAL,
}


ACADEMIC_RULES = {
    'institution': FieldRequirement.REQUIRED,
    'degree': FieldRequirement.REQUIRED,
    'pages': FieldRequirement.OPTIONAL,
    'advisor': FieldRequirement.OPTIONAL,
    'program': FieldRequirement.OPTIONAL,
}


EVENT_PAPER_RULES = {
    'event_name': FieldRequirement.REQUIRED,
    'event_location': FieldRequirement.REQUIRED,
    'event_year': FieldRequirement.REQUIRED,
    'pages': FieldRequirement.CONDITIONAL,
    'container': FieldRequirement.CONDITIONAL,
}


NORMATIVE_DOCUMENT_RULES = {
    'jurisdiction': FieldRequirement.REQUIRED,
    'number': FieldRequirement.CONDITIONAL,
    'container': FieldRequirement.CONDITIONAL,
    'publication_place': FieldRequirement.CONDITIONAL,
    'publication_date': FieldRequirement.CONDITIONAL,
    'page': FieldRequirement.CONDITIONAL,
}


JURISPRUDENCE_RULES = {
    'court': FieldRequirement.REQUIRED,
    'decision_date': FieldRequirement.REQUIRED,
    'rapporteur': FieldRequirement.CONDITIONAL,
    'case_number': FieldRequirement.CONDITIONAL,
    'container': FieldRequirement.CONDITIONAL,
    'publication_place': FieldRequirement.CONDITIONAL,
    'publication_date': FieldRequirement.CONDITIONAL,
    'page': FieldRequirement.CONDITIONAL,
}


WEBSITE_RULES = {
    'url': FieldRequirement.REQUIRED,
    'access_date': FieldRequirement.REQUIRED,
    'publisher': FieldRequirement.CONDITIONAL,
}


AUDIOVISUAL_RULES = {
    'responsibility': FieldRequirement.REQUIRED,
    'duration': FieldRequirement.CONDITIONAL,
    'media_type': FieldRequirement.OPTIONAL,
}


PATENT_RULES = {
    'patent_number': FieldRequirement.REQUIRED,
    'institution': FieldRequirement.CONDITIONAL,
}


CORRESPONDENCE_RULES = {
    'recipient': FieldRequirement.REQUIRED,
    'sender': FieldRequirement.CONDITIONAL,
    'description': FieldRequirement.OPTIONAL,
}


SPECIAL_DOCUMENT_RULES = {
    'scale': FieldRequirement.CONDITIONAL,
    'dimensions': FieldRequirement.CONDITIONAL,
    'technique': FieldRequirement.OPTIONAL,
}


REQUIRED_BY_TYPE = {
    ReferenceType.BOOK: BOOK_RULES,
    ReferenceType.BOOK_PART: BOOK_PART_RULES,
    ReferenceType.JOURNAL_ARTICLE: JOURNAL_ARTICLE_RULES,
    ReferenceType.NEWSPAPER_ARTICLE: NEWSPAPER_ARTICLE_RULES,
    ReferenceType.ACADEMIC: ACADEMIC_RULES,
    ReferenceType.EVENT_PAPER: EVENT_PAPER_RULES,
    ReferenceType.NORMATIVE_DOCUMENT: NORMATIVE_DOCUMENT_RULES,
    ReferenceType.JURISPRUDENCE: JURISPRUDENCE_RULES,
    ReferenceType.WEBSITE: WEBSITE_RULES,
    ReferenceType.AUDIOVISUAL: AUDIOVISUAL_RULES,
    ReferenceType.PATENT: PATENT_RULES,
    ReferenceType.CORRESPONDENCE: CORRESPONDENCE_RULES,
    ReferenceType.SPECIAL_DOCUMENT: SPECIAL_DOCUMENT_RULES
}
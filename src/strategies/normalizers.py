import re
from datetime import date
from src.domains import DatePrecision
from dataclasses import dataclass

NAME_PARTICLES = (
            'da',
            'do',
            'das',
            'dos',
            'de',
            'van',
            'von',
            'di',
            'del',
            'du',
            'of'
        )


@dataclass
class NameElements:
    given_name: str
    last_name: str
    given_name_initials: str
    last_name_initial: str


class CoreNormalizer:
    def __init__(self):
        pass

    def natural_name_parser(self, name_string: str) -> NameElements:
        name_parts = [
            part if part in NAME_PARTICLES else part.title()
            for part in name_string.lower().strip().split()
        ]
        last_name = name_parts[-1]
        given_name = " ".join(name_parts[:-1])

        name_initials = [
            part[0].upper()
            for part in name_parts
            if part.lower() not in NAME_PARTICLES
        ]
        last_name_initial = name_initials[-1]
        given_names_initials = (
            ". ".join(name_initials[:-1]) + '.'
        )

        return NameElements(
            given_name=given_name,
            last_name=last_name,
            given_name_initials=given_names_initials,
            last_name_initial=last_name_initial
        )

    def legal_entity_name_normalizer(self, name_string: str) -> str:
        name_parts = [
            part if part in NAME_PARTICLES else part.title()
            for part in name_string.lower().strip().split()
        ]
        name = " ".join(name_parts)

        return name

    def title_normalizer(self, title_string: str) -> str:
        name_parts = [
            part if part in NAME_PARTICLES else part.title()
            for part in title_string.lower().strip().split()
        ]
        name = " ".join(name_parts)

        return name

    def display_year_normalizer(
            self, date_precision: DatePrecision, date_anchor: date
    ) -> str:
        if date_precision == DatePrecision.EXACT:
            display_year = date_anchor.strftime('%Y')
        if date_precision == DatePrecision.DECADE:
            ano_base = date_anchor.strftime('%Y')[:-1]
            display_year = f'[{ano_base}-]'
        if date_precision == DatePrecision.CENTURY:
            ano_base = date_anchor.strftime('%Y')[:-2]
            display_year = f'[{ano_base}--]'
        if date_precision == DatePrecision.MILLENIA:
            ano_base = date_anchor.strftime('%Y')[:-3]
            display_year = f'[{ano_base}---]'
        if date_precision == DatePrecision.UNKNOWN:
            display_year = '[s.d.]'

        return display_year

    def instrumentation_normalizer(
            self, instruments: list[str]
    ) -> str:
        instrumentation = ', '.join(instruments)
        instrumentation = instrumentation.lower().strip().capitalize()
        instrumentation = re.sub(r',(?!.*,)', ' e', instrumentation)

        return instrumentation

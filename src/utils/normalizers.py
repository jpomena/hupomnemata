import re
from dataclasses import dataclass
from datetime import date

from src.domains import DatePrecision

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
    'of',
)


@dataclass
class NameElements:
    given_names: str
    last_name: str
    given_names_initials: str
    last_name_initial: str


class CoreNormalizer:
    def natural_name_parser(self, name_string: str) -> NameElements:
        clean = name_string.strip()
        if not clean:
            return NameElements(
                given_names="",
                last_name="",
                given_names_initials="",
                last_name_initial="",
            )

        if "," in clean:
            parts = clean.split(",", 1)
            s_tokens = [p.lower() for p in parts[0].strip().split() if p]
            g_tokens = [p.lower() for p in parts[1].strip().split() if p]

            s_parts = [
                part if (part in NAME_PARTICLES and index != 0) else part.title()
                for index, part in enumerate(s_tokens)
            ]
            g_parts = [
                part if (part in NAME_PARTICLES and index != 0) else part.title()
                for index, part in enumerate(g_tokens)
            ]

            last_name = " ".join(s_parts)
            given_names = " ".join(g_parts)

            g_initials = [
                part[0].upper()
                for part in g_parts
                if part.lower() not in NAME_PARTICLES
            ]
            s_initials = [
                part[0].upper()
                for part in s_parts
                if part.lower() not in NAME_PARTICLES
            ]

            last_name_initial = s_initials[0] if s_initials else ""
            given_names_initials = (
                ". ".join(g_initials) + "."
                if g_initials
                else ""
            )

            return NameElements(
                given_names=given_names,
                last_name=last_name,
                given_names_initials=given_names_initials,
                last_name_initial=last_name_initial,
            )

        name_parts = [
            part if (
                part in NAME_PARTICLES and (
                    name_string.lower().strip().split().index(part)
                ) != 0
            ) else part.title()
            for part in name_string.lower().strip().split()
        ]
        last_name = name_parts[-1] if name_parts else ""
        given_names = " ".join(name_parts[:-1])

        name_initials = [
            part[0].upper()
            for part in name_parts
            if part.lower() not in NAME_PARTICLES
        ]
        last_name_initial = name_initials[-1] if name_initials else ""
        given_names_initials = (
            ". ".join(name_initials[:-1]) + "."
            if len(name_initials) > 1
            else ""
        )

        return NameElements(
            given_names=given_names,
            last_name=last_name,
            given_names_initials=given_names_initials,
            last_name_initial=last_name_initial,
        )

    def legal_entity_name_normalizer(self, name_string: str) -> str:
        name_parts = [
            part if (
                part in NAME_PARTICLES and (
                    name_string.lower().strip().split().index(part) != 0
                )
            ) else part.title()
            for part in name_string.lower().strip().split()
        ]
        return ' '.join(name_parts)

    def title_normalizer(self, title_string: str) -> str:
        crude_name_parts = title_string.lower().strip().split()
        name_parts = []
        for index, part in enumerate(crude_name_parts):
            if index == 0:
                name_parts.append(part.title())
            else:
                name_parts.append(part)

        return ' '.join(name_parts)

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

    def instrumentation_normalizer(self, instruments: list[str]) -> str:
        instrumentation = ', '.join(instruments)
        instrumentation = instrumentation.lower().strip().capitalize()
        instrumentation = re.sub(r',(?!.*,)', ' e', instrumentation)
        return instrumentation

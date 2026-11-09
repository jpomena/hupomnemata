"""Datas de cadastro formatadas para a interface.

O SQLite grava ``CURRENT_TIMESTAMP`` em UTC e sem fuso. Estas funções tratam
datas sem fuso como UTC e mostram no fuso local da máquina.
"""

from datetime import datetime, timezone

MONTHS_SHORT = (
    'jan', 'fev', 'mar', 'abr', 'mai', 'jun',
    'jul', 'ago', 'set', 'out', 'nov', 'dez',
)
MONTHS_LONG = (
    'janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho',
    'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro',
)


def to_local(value: datetime | str | None) -> datetime | None:
    if value is None or value == '':
        return None
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.strip().replace('T', ' '))
        except ValueError:
            return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone()


def format_date(value: datetime | str | None) -> str:
    """``3 nov 2026``."""
    moment = to_local(value)
    if moment is None:
        return ''
    return f'{moment.day} {MONTHS_SHORT[moment.month - 1]} {moment.year}'


def format_day(value: datetime | str | None) -> str:
    """``3 de novembro``, com o ano quando não é o ano corrente."""
    moment = to_local(value)
    if moment is None:
        return ''
    label = f'{moment.day} de {MONTHS_LONG[moment.month - 1]}'
    if moment.year != datetime.now().astimezone().year:
        label = f'{label} de {moment.year}'
    return label


def format_time(value: datetime | str | None) -> str:
    """``17:05``."""
    moment = to_local(value)
    if moment is None:
        return ''
    return f'{moment.hour:02d}:{moment.minute:02d}'


def sort_key(value: datetime | str | None) -> float:
    moment = to_local(value)
    return moment.timestamp() if moment is not None else float('-inf')

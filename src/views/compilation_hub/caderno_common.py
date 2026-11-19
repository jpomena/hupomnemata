"""Constantes e formatação compartilhadas do Caderno de trabalho."""

from src.contracts import CompilationFragmentRecord

QUEUE_KEY = 'queue'
FRAGMENT_DRAG_GROUP = 'caderno-fragments'


def kind_label(fragment: CompilationFragmentRecord) -> str:
    return 'Citação' if fragment['fragment_type'] == 'quote' else 'Paráfrase'


def quoted(text: str) -> str:
    text = (text or '').strip()
    return text if text[:1] in '“"«' else f'“{text}”'

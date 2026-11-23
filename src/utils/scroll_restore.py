"""Reaplica a rolagem da tela ativa depois de abrir ou fechar diálogos.

No cliente Flet 0.86, quando uma rota de diálogo (``AlertDialog``, ``SnackBar``)
é removida, os ``ScrollController`` da view abaixo voltam ao topo — sem emitir
evento de rolagem. O estado da rolagem pertence à tela ativa, então cada
compositor registra aqui um restaurador para a sua ``Page``.

O patch de ``show_dialog`` (abertura) e da dispensa (``open = False`` e
``_remove_dialog``) agenda o restaurador. Assim a tela não depende de
re-renderizar para reencontrar a posição que o usuário já tinha.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger('hupomnemata.ui')

# id(page) -> (page, callback). A referência à página valida a identidade:
# ids podem ser reaproveitados depois que um mock de teste é coletado.
_restorers: dict[int, tuple[Any, Callable[[], None]]] = {}


def register_scroll_restorer(
    page: Any,
    callback: Callable[[], None],
) -> None:
    """Associa a ``page`` o restaurador da tela atualmente montada."""
    if page is None or not callable(callback):
        return
    _restorers[id(page)] = (page, callback)


def unregister_scroll_restorer(
    page: Any,
    callback: Callable[[], None] | None = None,
) -> None:
    """Remove o restaurador (ou apenas se for o mesmo compositor)."""
    if page is None:
        return
    entry = _restorers.get(id(page))
    if entry is None or entry[0] is not page:
        return
    if callback is None or entry[1] == callback:
        _restorers.pop(id(page), None)


def has_scroll_restorer(page: Any) -> bool:
    """Indica se a página tem uma tela interessada em restaurar rolagem."""
    if page is None:
        return False
    entry = _restorers.get(id(page))
    return entry is not None and entry[0] is page


def schedule_scroll_restore(page: Any) -> bool:
    """Agenda a reaplicação da rolagem; ``False`` se não há tela registrada."""
    if page is None:
        return False
    entry = _restorers.get(id(page))
    if entry is None or entry[0] is not page:
        return False
    try:
        entry[1]()
    except Exception as error:  # noqa: BLE001 - fronteira de UI
        logger.debug('Restauração de rolagem ignorada: %s', error)
        return False
    return True

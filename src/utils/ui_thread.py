"""Utilitário canônico para mutações de controles Flet a partir de threads externas.

O Flet não permite mutar a árvore de controles (nem chamar ``control.update()`` ou
``page.update()``) fora da thread dona do event loop da sessão. Em contrapartida,
``Page.run_task`` é seguro a partir de outra thread, pois delega a coroutine ao loop
da sessão via ``asyncio.run_coroutine_threadsafe``.

``run_on_ui`` encapsula essa ponte: se já estivermos no loop de UI (ou se não houver
loop real, como em testes com duplos), executa o callback de imediato; caso contrário,
agenda-o no loop de UI usando ``page.run_task``.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any


def run_on_ui(page: Any, callback: Callable[[], None]) -> None:
    """Executa ``callback`` na thread do loop de UI associado a ``page``.

    A ordem de decisão é deliberada:

    1. Sem página (duplos de teste, modal ainda não montado), executamos inline.
    2. Sem loop asyncio real, loop fechado ou sem ``run_task`` chamável, executamos
       inline: preserva o funcionamento de testes que usam ``MagicMock`` ou
       ``SimpleNamespace``.
    3. Já estamos no próprio loop de UI, executamos inline, evitando agendamento
       desnecessário e possíveis deadlocks.
    4. Caso contrário, agendamos via ``page.run_task``, que é thread-safe.

    Args:
        page: Instância de ``flet.Page`` (ou duplo compatível) que dá acesso ao loop.
        callback: Função síncrona que muta controles e chama ``update()``.
    """
    if page is None:
        callback()
        return

    run_task = getattr(page, "run_task", None)
    loop = getattr(
        getattr(getattr(page, "session", None), "connection", None),
        "loop",
        None,
    )

    if (
        not isinstance(loop, asyncio.AbstractEventLoop)
        or loop.is_closed()
        or not callable(run_task)
    ):
        callback()
        return

    try:
        running_loop = asyncio.get_running_loop()
    except RuntimeError:
        running_loop = None

    if running_loop is loop:
        callback()
        return

    async def _runner() -> None:
        callback()

    try:
        run_task(_runner)
    except Exception:  # noqa: BLE001 - ponte de UI deve ter fallback
        # Em duplos de teste ou após o fechamento da sessão o agendamento
        # pode falhar de formas que não são RuntimeError/TypeError. Nunca
        # deixe o callback de encerramento sem execução.
        callback()

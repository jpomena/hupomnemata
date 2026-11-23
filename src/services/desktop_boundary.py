"""Frontera segura com o processo Flutter/Flet Desktop.

O ``flet`` executa o cliente gráfico em um processo separado do backend Python.
Matar apenas o backend pode deixar a janela aberta tentando reconectar. Este
adaptador registra o ``pid_file`` criado pelo runner para fechar o cliente sem
procurar ou encerrar processos alheios.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any


logger = logging.getLogger("hupomnemata.lifecycle")
_pid_file: str | None = None
_installed = False


def install_desktop_boundary() -> None:
    """Registra automaticamente a view criada para ``ft.run``.

    O patch deve ser aplicado antes de ``ft.run`` (que importa e chama
    ``open_flet_view_async`` depois). O protocolo retornado para o runner
    permanece intacto: ``(process, pid_file)``.
    """
    global _installed
    if _installed:
        return
    try:
        import flet_desktop
    except ImportError:
        logger.debug("Flet Desktop não instalado; boundary opcional inativo.")
        return

    original = flet_desktop.open_flet_view_async

    async def open_view_with_boundary(*args: Any, **kwargs: Any):
        process, pid_file = await original(*args, **kwargs)
        register_desktop_view(pid_file)
        return process, pid_file

    flet_desktop.open_flet_view_async = open_view_with_boundary
    _installed = True


def register_desktop_view(pid_file: str | None) -> None:
    """Guarda o único identificador necessário para fechar a view real."""
    global _pid_file
    _pid_file = str(pid_file) if pid_file else None
    if _pid_file is not None:
        logger.info("Flet Desktop registrado no lifecycle: %s", _pid_file)


def close_desktop_view() -> bool:
    """Fecha o processo gráfico registrado pelo próprio runner.

    ``close_flet_view`` mata somente o PID da view, remove o PID file e ignora
    arquivos já removidos. Nunca varre processos do sistema.
    """
    global _pid_file
    pid_file = _pid_file
    _pid_file = None
    if not pid_file:
        return False

    try:
        from flet_desktop import close_flet_view

        path = Path(pid_file)
        if not path.exists():
            return False
        close_flet_view(pid_file)
        logger.info("Flet Desktop encerrado pelo lifecycle.")
        return True
    except Exception as error:  # noqa: BLE001 - último recurso de lifecycle
        logger.warning("Falha ao fechar Flet Desktop: %s", error)
        return False

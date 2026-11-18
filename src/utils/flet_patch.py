"""Módulo de correção teológica e operacional para o transporte de mensagens Flet (v0.86+).

Em ambientes Windows sob asyncio.ProactorEventLoop (IOCP), invocar mutações de interface
(`page.update()`, `control.update()`) a partir de threads secundárias insere bytes diretamente
na `asyncio.Queue` de saída do `FletSocketServer`, mas sem notificar o loop via
`loop.call_soon_threadsafe()`. Como consequência, o loop de eventos permanece em espera
bloqueante de I/O e a interface só descarrega os patches quando um evento externo (como
ganho/perda de foco de janela) força o tráfego de entrada.

Este rito de purificação intercepta o envio em nível de transporte e garante o despertar
imediato do loop em qualquer thread.
"""

import asyncio
import logging

import msgpack
from flet.controls.base_control import BaseControl
from flet.messaging.protocol import (
    ClientMessage,
    configure_encode_object_for_msgpack,
)
from flet.messaging.flet_socket_server import FletSocketServer

logger = logging.getLogger("hupomnemata.flet_patch")

_patched = False


def _safe_put_send_queue(server: FletSocketServer, framed: bytes) -> None:
    """Enfileira quadro de dados no socket de forma estritamente thread-safe."""
    send_queue = getattr(server, "_FletSocketServer__send_queue", None)
    if send_queue is None:
        return

    loop = getattr(server, "loop", None)
    if loop is None or loop.is_closed():
        try:
            send_queue.put_nowait(framed)
        except Exception:
            pass
        return

    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        current_loop = None

    if current_loop is loop:
        # Já estamos no loop principal de eventos do asyncio
        send_queue.put_nowait(framed)
    else:
        # Estamos em uma thread de background (worker thread):
        # Desperta o IOCP / Proactor imediatamente via call_soon_threadsafe
        loop.call_soon_threadsafe(send_queue.put_nowait, framed)


def _patched_send_message(self: FletSocketServer, message: ClientMessage) -> None:
    """Substitui o envio original de mensagens garantindo despertar thread-safe."""
    body = msgpack.packb(
        [message.action, message.body],
        default=configure_encode_object_for_msgpack(BaseControl),
    )
    packet = b"\x00" + body
    framed = len(packet).to_bytes(4, "little", signed=False) + packet
    _safe_put_send_queue(self, framed)


def _patched_send_data_channel_frame(
    self: FletSocketServer, channel_id: int, payload: bytes
) -> None:
    """Substitui o envio de quadros de canais de dados garantindo despertar thread-safe."""
    framed = b"".join(
        [
            (5 + len(payload)).to_bytes(4, "little", signed=False),
            b"\x01",
            channel_id.to_bytes(4, "little", signed=False),
            payload,
        ]
    )
    _safe_put_send_queue(self, framed)


def apply_flet_patches() -> None:
    """Aplica o rito sagrado de interceptação do transporte do Flet."""
    global _patched
    if _patched:
        return

    FletSocketServer.send_message = _patched_send_message
    FletSocketServer.send_data_channel_frame = _patched_send_data_channel_frame
    _patched = True
    logger.info("Liturgia de atualização thread-safe do Flet aplicada com sucesso.")

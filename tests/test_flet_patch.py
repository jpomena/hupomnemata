"""Testes unitários para o rito de purificação de transporte Flet (flet_patch.py)."""

import asyncio
from unittest.mock import MagicMock
from flet.messaging.flet_socket_server import FletSocketServer
from flet.messaging.protocol import ClientAction, ClientMessage, PatchControlBody
from src.utils.flet_patch import apply_flet_patches


def test_apply_flet_patches_idempotence():
    """Garante que a aplicação do patch seja idempotente e estável."""
    apply_flet_patches()
    patched_send = FletSocketServer.send_message
    apply_flet_patches()
    assert FletSocketServer.send_message == patched_send


def test_patched_send_message_threadsafe_dispatch():
    """Garante que o envio de mensagens a partir de thread externa invoque loop.call_soon_threadsafe."""
    apply_flet_patches()

    mock_server = MagicMock(spec=FletSocketServer)
    mock_loop = MagicMock(spec=asyncio.AbstractEventLoop)
    mock_loop.is_closed.return_value = False
    mock_queue = MagicMock()

    mock_server.loop = mock_loop
    # Atributo privado name-mangled da classe
    setattr(mock_server, "_FletSocketServer__send_queue", mock_queue)

    msg = ClientMessage(ClientAction.PATCH_CONTROL, PatchControlBody("ctrl_1", []))

    # Executa em contexto síncrono simulando thread externa (sem running loop)
    FletSocketServer.send_message(mock_server, msg)

    # loop.call_soon_threadsafe deve ser chamado para despertar o IOCP
    assert mock_loop.call_soon_threadsafe.called
    args, _ = mock_loop.call_soon_threadsafe.call_args
    assert args[0] == mock_queue.put_nowait

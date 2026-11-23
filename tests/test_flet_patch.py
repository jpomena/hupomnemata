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


def test_flet_patch_allows_imperative_updates_on_frozen_controls():
    """O app não usa components declarativos; hovers não podem morrer congelados."""
    import flet as ft
    import pytest

    apply_flet_patches()

    text = ft.Text("original")
    object.__setattr__(text, "_frozen", True)
    text.value = "atualizado"
    assert text.value == "atualizado"
    assert not hasattr(text, "_frozen")

    box = ft.Container()
    object.__setattr__(box, "_frozen", True)
    with pytest.raises(RuntimeError, match="added to the page"):
        box.update()
    assert not hasattr(box, "_frozen")


def test_show_and_remove_dialog_schedule_scroll_restore(monkeypatch):
    """Toda rota de diálogo recompõe a rolagem da tela abaixo."""
    import flet as ft
    from types import SimpleNamespace

    from src.utils import flet_patch

    page = SimpleNamespace()
    page.page = page
    dialog = ft.AlertDialog()
    events: list[tuple[str, object]] = []

    monkeypatch.setattr(
        flet_patch,
        '_original_show_dialog',
        lambda target, value: events.append(('show', value)),
    )
    monkeypatch.setattr(
        flet_patch,
        '_original_remove_dialog',
        lambda target, value: events.append(('remove', value)),
    )
    monkeypatch.setattr(
        flet_patch,
        'schedule_scroll_restore',
        lambda target: events.append(('restore', target)),
    )

    flet_patch._patched_show_dialog(page, dialog)
    flet_patch._patched_remove_dialog(page, dialog)

    assert events == [
        ('show', dialog),
        ('restore', page),
        ('remove', dialog),
        ('restore', page),
    ]


def test_closing_dialog_schedules_scroll_restore(monkeypatch):
    """``dialog.open = False`` é o gatilho comum de fechamento."""
    import flet as ft

    from src.utils import flet_patch

    dialog = ft.AlertDialog(open=True)
    scheduled: list[object] = []
    monkeypatch.setattr(
        flet_patch,
        '_schedule_dialog_scroll_restore',
        scheduled.append,
    )

    prop = vars(ft.AlertDialog)['open']
    flet_patch._imperative_prop_set(prop, dialog, False)
    assert dialog.open is False
    assert scheduled == [dialog]

    # Reabrir não restaura rolagem: só o fechamento remonta a view.
    scheduled.clear()
    flet_patch._imperative_prop_set(prop, dialog, True)
    assert dialog.open is True
    assert scheduled == []

    # Um campo homônimo em controle que não é diálogo não dispara nada.
    box = ft.Container()
    scheduled.clear()
    flet_patch._imperative_prop_set(prop, box, False)
    assert scheduled == []

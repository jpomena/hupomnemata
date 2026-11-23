"""Módulo de correção teológica e operacional para o transporte de mensagens Flet (v0.86+).

Em ambientes Windows sob asyncio.ProactorEventLoop (IOCP), invocar mutações de interface
(`page.update()`, `control.update()`) a partir de threads secundárias insere bytes diretamente
na `asyncio.Queue` de saída do `FletSocketServer`, mas sem notificar o loop via
`loop.call_soon_threadsafe()`. Como consequência, o loop de eventos permanece em espera
bloqueante de I/O e a interface só descarrega os patches quando um evento externo (como
ganho/perda de foco de janela) força o tráfego de entrada.

Este rito de purificação intercepta o envio em nível de transporte e garante o despertar
imediato do loop em qualquer thread.

O módulo também cobre um efeito colateral do cliente Flet 0.86: ao abrir ou dispensar
uma rota de diálogo, os ``ScrollController`` da view abaixo são remontados e voltam ao
topo sem emitir evento de rolagem. A abertura (``show_dialog``), o fechamento
(``open = False``) e a remoção (``_remove_dialog``) agendam a restauração registrada
pela tela ativa.
"""

import asyncio
import logging

import msgpack
from flet.controls import object_patch as flet_object_patch
from flet.controls.base_control import BaseControl
from flet.controls.base_page import BasePage
from flet.controls.dialog_control import DialogControl
from flet.controls.value_types import Prop
from flet.messaging.protocol import (
    ClientMessage,
    configure_encode_object_for_msgpack,
)
from flet.messaging.flet_socket_server import FletSocketServer

from src.utils.scroll_restore import schedule_scroll_restore

logger = logging.getLogger("hupomnemata.flet_patch")

_patched = False
_original_prop_set = Prop.__set__
_original_base_update = BaseControl.update
_original_control_setattr = flet_object_patch._control_setattr
_original_show_dialog = BasePage.show_dialog
_original_remove_dialog = BasePage._remove_dialog


def _safe_put_send_queue(server: FletSocketServer, framed: bytes) -> None:
    """Enfileira quadro de dados no socket de forma estritamente thread-safe."""
    send_queue = getattr(server, "_FletSocketServer__send_queue", None)
    if send_queue is None:
        return

    loop = getattr(server, "loop", None)
    if loop is None or loop.is_closed():
        try:
            send_queue.put_nowait(framed)
        except Exception as error:  # noqa: BLE001 - transporte Flet
            logger.warning('Quadro descartado: fila de envio indisponível (%s)', error)
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


def _unfreeze_imperative_target(target: object) -> None:
    """Remove o marcador de congelamento de um controle mutável."""
    if hasattr(target, "_frozen"):
        object.__delattr__(target, "_frozen")


def _schedule_dialog_scroll_restore(control: object) -> None:
    """Recompõe a rolagem da view depois de abrir/fechar um diálogo.

    O cliente Flutter remonta os ``ScrollController`` da tela ao dispensar
    uma rota de diálogo (inclusive ``SnackBar``); a posição precisa ser
    reaplicada pela própria tela.
    """
    try:
        page = control.page
    except Exception:  # noqa: BLE001 - controle ainda não montado
        return
    if page is not None:
        schedule_scroll_restore(page)


def _patched_show_dialog(self: BasePage, dialog: DialogControl) -> None:
    """Abre o diálogo e devolve a rolagem perdida pela troca de rotas."""
    _original_show_dialog(self, dialog)
    _schedule_dialog_scroll_restore(self)


def _patched_remove_dialog(self: BasePage, dialog: DialogControl) -> None:
    """Remove o diálogo dispensado e recompõe a rolagem da tela abaixo.

    O cliente reporta a dispensa só depois da animação de saída — o instante
    em que os ``ScrollController`` da view são remontados.
    """
    _original_remove_dialog(self, dialog)
    _schedule_dialog_scroll_restore(self)


def _imperative_prop_set(self: Prop, obj: object, value: object) -> None:
    """Propriedades de controles imperativos podem ser alteradas após mount.

    O Hupomnemata não usa os components declarativos do Flet. O guard
    ``_frozen`` existe para proteger snapshots de components; quando ele
    vaza para a árvore imperativa, hovers e updates morrem com
    ``Frozen controls cannot be updated``. Removemos o marcador no alvo
    que o app decide mutar, preservando o diff normal do Flet.

    O fechamento de qualquer ``DialogControl`` (``open = False``) também
    agenda a restauração da rolagem da tela abaixo.
    """
    if (
        self.name == 'open'
        and value is False
        and isinstance(obj, DialogControl)
    ):
        _schedule_dialog_scroll_restore(obj)
    if obj is not None:
        _unfreeze_imperative_target(obj)
    _original_prop_set(self, obj, value)


def _imperative_base_update(self: BaseControl) -> None:
    """Atualiza controles imperativos mesmo se marcados como congelados."""
    _unfreeze_imperative_target(self)
    _original_base_update(self)


def _imperative_control_setattr(obj: object, name: str, value: object) -> None:
    """Mesma política para campos rastreados pelo object patch do Flet."""
    if not name.startswith("_"):
        _unfreeze_imperative_target(obj)
    _original_control_setattr(obj, name, value)


def apply_flet_patches() -> None:
    """Aplica o rito sagrado de interceptação do transporte do Flet."""
    global _patched
    if _patched:
        return

    FletSocketServer.send_message = _patched_send_message
    FletSocketServer.send_data_channel_frame = _patched_send_data_channel_frame
    BasePage.show_dialog = _patched_show_dialog
    BasePage._remove_dialog = _patched_remove_dialog
    Prop.__set__ = _imperative_prop_set
    BaseControl.update = _imperative_base_update
    flet_object_patch._control_setattr = _imperative_control_setattr
    _patched = True
    logger.info("Liturgia de atualização thread-safe do Flet aplicada com sucesso.")

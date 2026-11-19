"""Testes do utilitário canônico de mutação de UI a partir de threads."""

import asyncio
from types import SimpleNamespace
import threading
from unittest.mock import MagicMock

from src.utils.ui_thread import run_on_ui


def _start_loop_in_thread() -> tuple[asyncio.AbstractEventLoop, threading.Thread, threading.Event]:
    """Cria e executa um event loop asyncio em thread dedicada."""
    loop = asyncio.new_event_loop()
    ready = threading.Event()

    def _run() -> None:
        asyncio.set_event_loop(loop)
        loop.call_soon(ready.set)
        loop.run_forever()

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    assert ready.wait(2), "event loop não iniciou a tempo"
    return loop, thread, ready


def _stop_loop(loop: asyncio.AbstractEventLoop, thread: threading.Thread) -> None:
    loop.call_soon_threadsafe(loop.stop)
    thread.join(2)
    loop.close()


def test_run_on_ui_with_none_page_executes_immediately() -> None:
    calls: list[str] = []

    run_on_ui(None, lambda: calls.append("ok"))

    assert calls == ["ok"]


def test_run_on_ui_with_mock_page_executes_immediately() -> None:
    page = MagicMock()
    calls: list[str] = []

    run_on_ui(page, lambda: calls.append("ok"))

    assert calls == ["ok"]
    page.run_task.assert_not_called()


def test_run_on_ui_without_session_executes_immediately() -> None:
    page = SimpleNamespace(update=MagicMock(), run_task=MagicMock())
    calls: list[str] = []

    run_on_ui(page, lambda: calls.append("ok"))

    assert calls == ["ok"]
    page.run_task.assert_not_called()


def test_run_on_ui_schedules_callback_on_foreign_loop() -> None:
    loop, thread, _ready = _start_loop_in_thread()
    page = SimpleNamespace(
        session=SimpleNamespace(connection=SimpleNamespace(loop=loop)),
        run_task=lambda handler: asyncio.run_coroutine_threadsafe(handler(), loop),
    )
    executed = threading.Event()
    callback_threads: list[int] = []

    def _callback() -> None:
        callback_threads.append(threading.get_ident())
        executed.set()

    try:
        run_on_ui(page, _callback)
        assert executed.wait(2), "callback não executou no loop em até 2 s"
    finally:
        _stop_loop(loop, thread)

    assert callback_threads == [thread.ident]


def test_run_on_ui_inside_own_loop_executes_inline() -> None:
    calls: list[str] = []

    async def _scenario() -> None:
        loop = asyncio.get_running_loop()
        page = SimpleNamespace(
            session=SimpleNamespace(connection=SimpleNamespace(loop=loop)),
            run_task=MagicMock(side_effect=AssertionError("não deveria agendar")),
        )

        run_on_ui(page, lambda: calls.append("ok"))

        page.run_task.assert_not_called()

    asyncio.run(_scenario())

    assert calls == ["ok"]


def test_run_on_ui_with_closed_loop_executes_immediately() -> None:
    loop = asyncio.new_event_loop()
    loop.close()
    page = SimpleNamespace(
        session=SimpleNamespace(connection=SimpleNamespace(loop=loop)),
        run_task=MagicMock(),
    )
    calls: list[str] = []

    run_on_ui(page, lambda: calls.append("ok"))

    assert calls == ["ok"]
    page.run_task.assert_not_called()


def test_run_on_ui_falls_back_when_scheduling_fails() -> None:
    loop = asyncio.new_event_loop()

    def _run_task(handler):
        handler().close()
        raise RuntimeError("loop indisponível")

    page = SimpleNamespace(
        session=SimpleNamespace(connection=SimpleNamespace(loop=loop)),
        run_task=_run_task,
    )
    calls: list[str] = []

    try:
        run_on_ui(page, lambda: calls.append("ok"))
    finally:
        loop.close()

    assert calls == ["ok"]

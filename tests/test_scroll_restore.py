"""Registro de restauradores de rolagem por página."""

from types import SimpleNamespace

from src.utils.scroll_restore import (
    has_scroll_restorer,
    register_scroll_restorer,
    schedule_scroll_restore,
    unregister_scroll_restorer,
)


def test_register_schedule_and_unregister():
    page = SimpleNamespace()
    calls: list[str] = []

    register_scroll_restorer(page, lambda: calls.append('restore'))
    try:
        assert has_scroll_restorer(page)
        assert schedule_scroll_restore(page) is True
        assert calls == ['restore']
    finally:
        unregister_scroll_restorer(page)

    assert not has_scroll_restorer(page)
    assert schedule_scroll_restore(page) is False


def test_unregister_only_removes_current_owner():
    page = SimpleNamespace()
    first_calls: list[str] = []
    second_calls: list[str] = []

    def first() -> None:
        first_calls.append('first')

    def second() -> None:
        second_calls.append('second')

    register_scroll_restorer(page, first)
    register_scroll_restorer(page, second)
    try:
        # O compositor antigo não pode desregistrar o restaurador do atual.
        unregister_scroll_restorer(page, first)
        assert has_scroll_restorer(page)
        assert schedule_scroll_restore(page) is True
        assert first_calls == []
        assert second_calls == ['second']
    finally:
        unregister_scroll_restorer(page, second)

    assert not has_scroll_restorer(page)


def test_schedule_swallows_restorer_failures():
    page = SimpleNamespace()

    def broken() -> None:
        raise RuntimeError('controle desacoplado')

    register_scroll_restorer(page, broken)
    try:
        assert schedule_scroll_restore(page) is False
    finally:
        unregister_scroll_restorer(page)


def test_schedule_ignores_pages_without_restorer():
    assert schedule_scroll_restore(None) is False
    assert has_scroll_restorer(None) is False
    assert schedule_scroll_restore(SimpleNamespace()) is False

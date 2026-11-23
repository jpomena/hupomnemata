"""Encerramento real do processo Flutter usado pelo Flet Desktop."""

import asyncio

from src.services import desktop_boundary as boundary


def test_desktop_boundary_registers_and_closes_view(monkeypatch, tmp_path):
    import flet_desktop

    original_open = flet_desktop.open_flet_view_async
    closed = []
    view_process = object()
    pid_file = tmp_path / "flet-test.pid"
    pid_file.write_text("12345", encoding="utf-8")

    async def fake_open(*_args, **_kwargs):
        return view_process, str(pid_file)

    monkeypatch.setattr(flet_desktop, "open_flet_view_async", fake_open)
    monkeypatch.setattr(boundary, "_installed", False)
    monkeypatch.setattr(boundary, "_pid_file", None)
    monkeypatch.setattr(
        flet_desktop,
        "close_flet_view",
        lambda _path: closed.append("close"),
    )

    try:
        boundary.install_desktop_boundary()
        process, returned_pid = asyncio.run(
            flet_desktop.open_flet_view_async("url", None, False)
        )
        assert process is view_process
        assert returned_pid == str(pid_file)
        assert boundary.close_desktop_view() is True
        assert closed == ["close"]
        # A referência é consumida; não mata processo de uma sessão posterior.
        assert boundary.close_desktop_view() is False
        assert closed == ["close"]
    finally:
        monkeypatch.setattr(flet_desktop, "open_flet_view_async", original_open)
        monkeypatch.setattr(boundary, "_installed", False)
        monkeypatch.setattr(boundary, "_pid_file", None)

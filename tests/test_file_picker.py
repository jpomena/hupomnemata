"""Testes unitários para o utilitário de seleção de arquivos (FilePicker Flet 0.86+ e fallbacks)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import flet as ft

from src.utils.file_picker import (
    _ensure_file_picker_service,
    _pick_file_zenity,
    _pick_file_kdialog,
    _pick_file_tkinter,
    _pick_file_native_sync,
    pick_file,
)


def test_ensure_file_picker_service_never_uses_overlay():
    """Garante que FilePicker é registrado como Service e NUNCA em page.overlay."""
    mock_page = MagicMock(spec=ft.Page)
    mock_page.overlay = []
    mock_page.services = []
    mock_page._services = MagicMock()
    mock_page._services._services = []

    picker = _ensure_file_picker_service(mock_page)

    assert isinstance(picker, ft.FilePicker)
    # page.overlay NUNCA deve conter o FilePicker
    assert picker not in mock_page.overlay
    assert len(mock_page.overlay) == 0

    # Deve ter sido registrado em page._services e/ou page.services
    mock_page._services.register_service.assert_called_once_with(picker)
    assert picker in mock_page.services

    # Chamada subsequente deve reutilizar a mesma instância
    picker_reused = _ensure_file_picker_service(mock_page)
    assert picker_reused is picker


def test_pick_file_success_flet():
    """Quando o Flet FilePicker funciona normalmente, retorna o caminho do arquivo."""
    mock_page = MagicMock(spec=ft.Page)
    mock_page.overlay = []
    mock_page.services = []
    mock_page._services = MagicMock()
    mock_page._services._services = []

    mock_picker = MagicMock(spec=ft.FilePicker)
    mock_file = MagicMock()
    mock_file.path = "/home/user/document.pdf"
    mock_picker.pick_files = AsyncMock(return_value=[mock_file])
    mock_page._hupomnemata_file_picker = mock_picker

    with patch("src.utils.file_picker._pick_file_native_sync") as mock_native:
        result = asyncio.run(
            pick_file(mock_page, dialog_title="Selecionar PDF", allowed_extensions=["pdf"])
        )
        assert result == "/home/user/document.pdf"
        mock_native.assert_not_called()


def test_pick_file_user_cancelled_in_flet():
    """Quando o usuário cancela no Flet FilePicker, retorna None sem acionar fallback."""
    mock_page = MagicMock(spec=ft.Page)
    mock_page.overlay = []
    mock_page.services = []
    mock_page._services = MagicMock()
    mock_page._services._services = []

    mock_picker = MagicMock(spec=ft.FilePicker)
    mock_picker.pick_files = AsyncMock(return_value=[])
    mock_page._hupomnemata_file_picker = mock_picker

    with patch("src.utils.file_picker._pick_file_native_sync") as mock_native:
        result = asyncio.run(
            pick_file(mock_page, dialog_title="Selecionar PDF", allowed_extensions=["pdf"])
        )
        assert result is None
        mock_native.assert_not_called()


def test_pick_file_fallback_on_flet_exception():
    """Se o FilePicker do Flet lançar exceção (ex: Zenity/D-Bus/canal Flutter), aciona fallback nativo."""
    mock_page = MagicMock(spec=ft.Page)
    mock_page.overlay = []
    mock_page.services = []
    mock_page._services = MagicMock()
    mock_page._services._services = []

    mock_picker = MagicMock(spec=ft.FilePicker)
    mock_picker.pick_files = AsyncMock(side_effect=RuntimeError("Channel timeout / D-Bus error"))
    mock_page._hupomnemata_file_picker = mock_picker

    with patch("src.utils.file_picker._pick_file_native_sync", return_value="/fallback/path/file.pdf") as mock_native:
        result = asyncio.run(
            pick_file(mock_page, dialog_title="Selecionar PDF", allowed_extensions=["pdf"])
        )
        assert result == "/fallback/path/file.pdf"
        mock_native.assert_called_once_with("Selecionar PDF", ["pdf"])


def test_pick_file_zenity_success():
    """Zenity retorna caminho quando exit code é 0."""
    with patch("shutil.which", return_value="/usr/bin/zenity"), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="/path/to/work.pdf\n")
        handled, path = _pick_file_zenity("Selecionar PDF", ["pdf"])
        assert handled is True
        assert path == "/path/to/work.pdf"


def test_pick_file_zenity_cancel():
    """Zenity retorna handled=True e path=None quando usuário cancela (exit code 1)."""
    with patch("shutil.which", return_value="/usr/bin/zenity"), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        handled, path = _pick_file_zenity("Selecionar PDF", ["pdf"])
        assert handled is True
        assert path is None


def test_pick_file_zenity_error_continues_fallback():
    """Zenity retorna handled=False quando ocorre erro ou código diferente de 0/1."""
    with patch("shutil.which", return_value="/usr/bin/zenity"), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=255, stdout="")
        handled, path = _pick_file_zenity("Selecionar PDF", ["pdf"])
        assert handled is False
        assert path is None


def test_pick_file_kdialog_success():
    """kdialog retorna caminho quando exit code é 0."""
    with patch("shutil.which", return_value="/usr/bin/kdialog"), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="/path/to/kdialog.pdf\n")
        handled, path = _pick_file_kdialog("Selecionar PDF", ["pdf"])
        assert handled is True
        assert path == "/path/to/kdialog.pdf"


def test_pick_file_tkinter():
    """Tkinter filedialog abre e retorna seleção."""
    with patch("tkinter.Tk") as mock_tk, \
         patch("tkinter.filedialog.askopenfilename", return_value="/tk/selected.pdf"):
        mock_root = MagicMock()
        mock_tk.return_value = mock_root
        res = _pick_file_tkinter("Selecionar PDF", ["pdf"])
        assert res == "/tk/selected.pdf"
        mock_root.destroy.assert_called_once()


def test_pick_file_native_sync_chain():
    """Testa a cadeia completa de fallback no Linux."""
    with patch("sys.platform", "linux"), \
         patch("src.utils.file_picker._pick_file_zenity", return_value=(False, None)), \
         patch("src.utils.file_picker._pick_file_kdialog", return_value=(False, None)), \
         patch("src.utils.file_picker._pick_file_tkinter", return_value="/final/fallback.pdf"):
        res = _pick_file_native_sync("Titulo", ["pdf"])
        assert res == "/final/fallback.pdf"

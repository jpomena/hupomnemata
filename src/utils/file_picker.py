"""Utilitário robusto para seleção de arquivos no ecossistema Flet 0.86+ e desktop nativo."""

import asyncio
import shutil
import subprocess
import sys
import weakref
from typing import Optional

import flet as ft

from src.utils.error_log import log_exception


def _ensure_file_picker_service(page: ft.Page) -> ft.FilePicker:
    """Obtém ou instancia e registra o FilePicker como Service na página Flet.

    Em Flet 0.86+, FilePicker é uma subclasse de Service (não Control visual).
    Ele NUNCA deve ser adicionado a page.overlay.
    """
    picker = getattr(page, "_hupomnemata_file_picker", None)
    if picker is None:
        picker = ft.FilePicker()

        # Vincula ao registro de serviços da página Flet (page._services)
        if hasattr(page, "_services") and hasattr(page._services, "register_service"):
            tracked = getattr(page._services, "_services", [])
            if picker not in tracked:
                try:
                    page._services.register_service(picker)
                except Exception as err:
                    log_exception("Falha ao registrar FilePicker em page._services", err)

        # Adiciona a page.services para compatibilidade de ciclo de vida do View
        if hasattr(page, "services") and picker not in page.services:
            try:
                page.services.append(picker)
            except Exception as err:
                log_exception("Falha ao adicionar FilePicker em page.services", err)

        # Garante vínculo de parentesco fraco para que picker.page resolva sem RuntimeError
        if getattr(picker, "_parent", None) is None:
            parent_target = getattr(page, "_services", page)
            picker._parent = weakref.ref(parent_target)

        setattr(page, "_hupomnemata_file_picker", picker)

    return picker


def _pick_file_zenity(
    title: str, allowed_extensions: list[str] | None = None
) -> tuple[bool, Optional[str]]:
    """Tenta abrir caixa de diálogo nativa via Zenity no Linux.

    Retorna tupla (handled: bool, path: Optional[str]).
    handled=True indica que o Zenity executou normalmente (seleção com path ou cancelamento com None).
    handled=False indica falha/ausência do Zenity, orientando a tentativa do próximo fallback.
    """
    zenity_bin = shutil.which("zenity")
    if not zenity_bin:
        return False, None

    cmd = [zenity_bin, "--file-selection", f"--title={title}"]
    if allowed_extensions:
        patterns = " ".join(f"*.{ext} *.{ext.upper()}" for ext in allowed_extensions)
        cmd.append(f"--file-filter=Arquivos suportados ({patterns}) | {patterns}")

    try:
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            timeout=180,
        )
        if res.returncode == 0:
            selected = res.stdout.strip()
            return True, selected if selected else None
        elif res.returncode == 1:
            # Usuário cancelou intencionalmente a seleção no diálogo
            return True, None
        else:
            # Código != 0 e != 1 denota erro (falha de D-Bus, crash, display, etc)
            return False, None
    except Exception as err:
        log_exception("Subprocesso zenity falhou", err)
        return False, None


def _pick_file_kdialog(
    title: str, allowed_extensions: list[str] | None = None
) -> tuple[bool, Optional[str]]:
    """Tenta abrir caixa de diálogo nativa via kdialog no Linux/KDE."""
    kdialog_bin = shutil.which("kdialog")
    if not kdialog_bin:
        return False, None

    cmd = [kdialog_bin, "--getopenfilename", ".", f"--title={title}"]
    if allowed_extensions:
        pattern = " ".join(f"*.{ext} *.{ext.upper()}" for ext in allowed_extensions)
        cmd.append(f"{pattern}|Arquivos suportados ({pattern})")

    try:
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            timeout=180,
        )
        if res.returncode == 0:
            selected = res.stdout.strip()
            return True, selected if selected else None
        elif res.returncode == 1:
            return True, None
        else:
            return False, None
    except Exception as err:
        log_exception("Subprocesso kdialog falhou", err)
        return False, None


def _pick_file_tkinter(
    title: str, allowed_extensions: list[str] | None = None
) -> Optional[str]:
    """Fallback universal via Tkinter filedialog."""
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        try:
            root.attributes("-topmost", True)
        except Exception:
            pass

        filetypes = []
        if allowed_extensions:
            ext_pat = " ".join(f"*.{ext} *.{ext.upper()}" for ext in allowed_extensions)
            filetypes.append(("Arquivos suportados", ext_pat))
        filetypes.append(("Todos os arquivos", "*.*"))

        selected = filedialog.askopenfilename(
            title=title,
            filetypes=filetypes,
        )
        root.destroy()
        return selected if selected else None
    except Exception as err:
        log_exception("Tkinter filedialog fallback falhou", err)
        return None


def _pick_file_native_sync(
    title: str = "Selecionar arquivo",
    allowed_extensions: list[str] | None = None,
) -> Optional[str]:
    """Cadeia síncrona de seleção nativa de arquivos por sistema operacional."""
    if sys.platform.startswith("linux"):
        # 1. Tenta Zenity
        handled, path = _pick_file_zenity(title, allowed_extensions)
        if handled:
            return path

        # 2. Tenta kdialog
        handled, path = _pick_file_kdialog(title, allowed_extensions)
        if handled:
            return path

    # 3. Fallback universal Tkinter
    return _pick_file_tkinter(title, allowed_extensions)


async def pick_file(
    page: ft.Page | None = None,
    dialog_title: str = "Selecionar arquivo",
    allowed_extensions: list[str] | None = None,
) -> Optional[str]:
    """Abre diálogo para seleção de arquivos de forma assíncrona e resiliente.

    Prioriza o FilePicker nativo do Flet 0.86+ como Service (sem adicionar a page.overlay).
    Caso ocorra falha ou indisponibilidade no ecossistema Flet/Flutter/D-Bus, aciona
    automaticamente os fallbacks nativos do sistema (Zenity, kdialog, Tkinter).
    """
    if page is not None:
        try:
            picker = _ensure_file_picker_service(page)
            file_type = (
                ft.FilePickerFileType.CUSTOM
                if allowed_extensions
                else ft.FilePickerFileType.ANY
            )
            files = await picker.pick_files(
                dialog_title=dialog_title,
                allowed_extensions=allowed_extensions,
                file_type=file_type,
            )
            if files and len(files) > 0 and files[0].path:
                return files[0].path
            elif files is not None and len(files) == 0:
                # O usuário cancelou explicitamente o diálogo no Flet
                return None
        except Exception as err:
            log_exception(
                "Flet FilePicker falhou; acionando fallback nativo do sistema operacional",
                err,
            )

    # Executa fallbacks nativos em thread de trabalho sem bloquear o loop assíncrono
    return await asyncio.to_thread(
        _pick_file_native_sync,
        dialog_title,
        allowed_extensions,
    )

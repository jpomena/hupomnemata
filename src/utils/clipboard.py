"""Operacoes de clipboard para referencias bibliograficas."""

import html
import os
import shutil
import subprocess

from src.utils.types import TextStyle, ViewReference
from src.utils.error_log import log_exception

if os.name == "nt":
    import ctypes
    from ctypes import wintypes


def reference_text(reference: ViewReference) -> str:
    """Retorna o conteudo da referencia sem a formatacao visual."""
    return "".join(part.content for part in reference.parts).strip()


def reference_html(reference: ViewReference) -> str:
    """Converte ReferenceParts em HTML compativel com editores comuns."""
    spans = []
    for part in reference.parts:
        styles = []
        if part.style == TextStyle.BOLD:
            styles.append("font-weight:700")
        if part.style == TextStyle.ITALIC:
            styles.append("font-style:italic")
        style = f' style="{";".join(styles)}"' if styles else ""
        spans.append(f"<span{style}>{html.escape(part.content)}</span>")
    return "".join(spans)


def _copy_plain_text_to_system_clipboard(text: str) -> bool:
    """Copia texto puro usando ferramentas nativas do sistema operacional."""
    if os.name == "nt":
        command = [
            "powershell",
            "-NoLogo",
            "-NoProfile",
            "-Command",
            "Set-Clipboard -Value ([Console]::In.ReadToEnd())",
        ]
    elif os.name == "posix":
        if shutil.which("wl-copy"):
            command = ["wl-copy"]
        elif shutil.which("xclip"):
            command = ["xclip", "-selection", "clipboard"]
        elif shutil.which("xsel"):
            command = ["xsel", "--clipboard", "--input"]
        elif shutil.which("pbcopy"):
            command = ["pbcopy"]
        else:
            return False
    else:
        return False

    try:
        result = subprocess.run(
            command,
            input=text,
            text=True,
            capture_output=True,
            check=False,
        )
        return result.returncode == 0
    except (FileNotFoundError, OSError) as error:
        log_exception("Falha ao acessar o clipboard do sistema", error)
        return False


def copy_reference(reference: ViewReference) -> bool:
    """Copia HTML em Windows e texto puro em plataformas Unix-like."""
    plain_text = reference_text(reference)

    if os.name != "nt":
        return _copy_plain_text_to_system_clipboard(plain_text)

    fragment = reference_html(reference)
    html_document = (
        "<html><body><!--StartFragment-->"
        f"{fragment}"
        "<!--EndFragment--></body></html>"
    )
    html_bytes = html_document.encode("utf-8")
    marker_start = b"<!--StartFragment-->"
    marker_end = b"<!--EndFragment-->"
    header_template = (
        "Version:0.9\r\n"
        "StartHTML:{:010d}\r\n"
        "EndHTML:{:010d}\r\n"
        "StartFragment:{:010d}\r\n"
        "EndFragment:{:010d}\r\n"
    )
    header = header_template.format(0, 0, 0, 0).encode("ascii")
    start_fragment = len(header) + html_bytes.index(marker_start)
    start_fragment += len(marker_start)
    end_fragment = len(header) + html_bytes.index(marker_end)
    end_html = len(header) + len(html_bytes)
    header = header_template.format(
        len(header), end_html, start_fragment, end_fragment
    ).encode("ascii")

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalFree.argtypes = [ctypes.c_void_p]
    user32.RegisterClipboardFormatW.argtypes = [wintypes.LPCWSTR]
    user32.RegisterClipboardFormatW.restype = wintypes.UINT
    user32.SetClipboardData.argtypes = [wintypes.UINT, ctypes.c_void_p]
    user32.SetClipboardData.restype = ctypes.c_void_p
    html_format = user32.RegisterClipboardFormatW("HTML Format")
    if not user32.OpenClipboard(None):
        return False

    try:
        user32.EmptyClipboard()
        if not _set_clipboard_data(
            kernel32, user32, html_format, header + html_bytes
        ):
            return False
        return _set_clipboard_data(
            kernel32,
            user32,
            13,
            (plain_text + "\0").encode("utf-16-le"),
        )
    finally:
        user32.CloseClipboard()


def _set_clipboard_data(kernel32, user32, format_id: int, data: bytes) -> bool:
    handle = kernel32.GlobalAlloc(0x0002, len(data))
    if not handle:
        return False
    pointer = kernel32.GlobalLock(handle)
    if not pointer:
        kernel32.GlobalFree(handle)
        return False
    ctypes.memmove(pointer, data, len(data))
    kernel32.GlobalUnlock(handle)
    if not user32.SetClipboardData(format_id, handle):
        kernel32.GlobalFree(handle)
        return False
    return True

"""Operacoes de clipboard para referencias bibliograficas e textos do sistema."""

import html
import os
import shutil
import subprocess

from src.utils.error_log import log_exception
from src.utils.types import TextStyle, ViewReference

if os.name == "nt":
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalUnlock.restype = wintypes.BOOL
    kernel32.GlobalFree.argtypes = [ctypes.c_void_p]
    kernel32.GlobalFree.restype = ctypes.c_void_p

    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.CloseClipboard.argtypes = []
    user32.CloseClipboard.restype = wintypes.BOOL
    user32.EmptyClipboard.argtypes = []
    user32.EmptyClipboard.restype = wintypes.BOOL
    user32.SetClipboardData.argtypes = [wintypes.UINT, ctypes.c_void_p]
    user32.SetClipboardData.restype = ctypes.c_void_p
    user32.GetClipboardData.argtypes = [wintypes.UINT]
    user32.GetClipboardData.restype = ctypes.c_void_p
    user32.RegisterClipboardFormatW.argtypes = [wintypes.LPCWSTR]
    user32.RegisterClipboardFormatW.restype = wintypes.UINT


def reference_text(reference: ViewReference) -> str:
    """Retorna o conteudo da referencia sem a formatacao visual."""
    return "".join(part.content for part in reference.parts).strip()


def reference_html(reference: ViewReference) -> str:
    """Converte ReferenceParts em HTML compativel com editores comuns."""
    chunks = []
    for part in reference.parts:
        text = html.escape(part.content).replace("\n", "<br>")
        if part.style == TextStyle.BOLD:
            chunks.append(f'<b style="font-weight:bold">{text}</b>')
        elif part.style == TextStyle.ITALIC:
            chunks.append(f'<i style="font-style:italic">{text}</i>')
        else:
            chunks.append(text)
    return "".join(chunks)


def _copy_plain_text_to_windows_clipboard(text: str) -> bool:
    """Copia texto puro com codificação UTF-16 Unicode nativa para o clipboard do Windows."""
    if os.name != "nt":
        return False

    try:
        if not user32.OpenClipboard(None):
            return False
        try:
            user32.EmptyClipboard()
            data = (text + "\0").encode("utf-16-le")
            return _set_clipboard_data(kernel32, user32, 13, data)  # CF_UNICODETEXT = 13
        finally:
            user32.CloseClipboard()
    except Exception as error:
        log_exception("Falha ao copiar texto puro para o clipboard do Windows via Win32", error)
        return False


def get_system_clipboard_text() -> str:
    """Recupera o texto puro atualmente armazenado na área de transferência do sistema."""
    if os.name == "nt":
        try:
            if not user32.OpenClipboard(None):
                return ""
            try:
                handle = user32.GetClipboardData(13)  # CF_UNICODETEXT
                if not handle:
                    return ""
                ptr = kernel32.GlobalLock(handle)
                if not ptr:
                    return ""
                try:
                    return ctypes.c_wchar_p(ptr).value or ""
                finally:
                    kernel32.GlobalUnlock(handle)
            finally:
                user32.CloseClipboard()
        except Exception as error:
            log_exception("Falha ao ler texto do clipboard do Windows", error)
            return ""
    elif os.name == "posix":
        cmd: list[str] = []
        if shutil.which("wl-paste"):
            cmd = ["wl-paste", "--no-newline"]
        elif shutil.which("xclip"):
            cmd = ["xclip", "-selection", "clipboard", "-out"]
        elif shutil.which("xsel"):
            cmd = ["xsel", "--clipboard", "--output"]
        elif shutil.which("pbpaste"):
            cmd = ["pbpaste"]
        else:
            return ""
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=2, check=False)
            return res.stdout if res.returncode == 0 else ""
        except Exception:
            return ""
    return ""


def _copy_plain_text_to_system_clipboard(text: str) -> bool:
    """Copia texto puro usando ferramentas nativas do sistema operacional."""
    if os.name == "nt":
        return _copy_plain_text_to_windows_clipboard(text)
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
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=2,
        )
        return result.returncode == 0
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired) as error:
        log_exception("Falha ao acessar o clipboard do sistema", error)
        return False


def _copy_html_to_windows_clipboard(fragment: str, plain_text: str) -> bool:
    """Copia fragmento HTML e texto puro para o clipboard do Windows."""
    if os.name != "nt":
        return False

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
    dummy_header = header_template.format(0, 0, 0, 0).encode("ascii")
    header_len = len(dummy_header)
    start_fragment = header_len + html_bytes.index(marker_start) + len(marker_start)
    end_fragment = header_len + html_bytes.index(marker_end)
    end_html = header_len + len(html_bytes)
    header = header_template.format(
        header_len, end_html, start_fragment, end_fragment
    ).encode("ascii")
    full_html = header + html_bytes + b"\0"

    try:
        html_format = user32.RegisterClipboardFormatW("HTML Format")
        if not user32.OpenClipboard(None):
            return False

        try:
            user32.EmptyClipboard()
            if not _set_clipboard_data(
                kernel32, user32, html_format, full_html
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
    except Exception as error:
        log_exception("Falha ao copiar HTML para o clipboard do Windows", error)
        return False


def copy_reference(reference: ViewReference) -> bool:
    """Copia HTML em Windows e texto puro em plataformas Unix-like."""
    plain_text = reference_text(reference)

    if os.name != "nt":
        return _copy_plain_text_to_system_clipboard(plain_text)

    fragment = reference_html(reference)
    return _copy_html_to_windows_clipboard(fragment, plain_text)


def copy_references(references: list[ViewReference]) -> bool:
    """Copia uma lista de referências com formatação ABNT para o clipboard."""
    if not references:
        return False

    plain_text = "\n".join(reference_text(ref) for ref in references)
    if os.name != "nt":
        return _copy_plain_text_to_system_clipboard(plain_text)

    paragraphs = [
        f'<p style="margin:0 0 1em 0;">{reference_html(ref)}</p>'
        for ref in references
    ]
    fragment = "\n".join(paragraphs)
    return _copy_html_to_windows_clipboard(fragment, plain_text)


def _set_clipboard_data(k32, u32, format_id: int, data: bytes) -> bool:
    handle = k32.GlobalAlloc(0x0002, len(data))
    if not handle:
        return False
    pointer = k32.GlobalLock(handle)
    if not pointer:
        k32.GlobalFree(handle)
        return False
    ctypes.memmove(pointer, data, len(data))
    k32.GlobalUnlock(handle)
    if not u32.SetClipboardData(format_id, handle):
        k32.GlobalFree(handle)
        return False
    return True

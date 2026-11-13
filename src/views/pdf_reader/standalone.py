"""Janela desktop dedicada para leitura imersiva e anotação de PDFs.

Inicia uma instância independente de aplicação Flet em novo processo do sistema
operacional, garantindo que a janela principal do Hupomnemata permaneça intacta
com seu estado de navegação, filtros e contexto preservados.
"""

import inspect
import os
import sys
from pathlib import Path

import flet as ft

from src.configs.settings import (
    COLORS_DARK,
    COLORS_LIGHT,
    CORE_MENUS,
    FONT_FAMILIES,
    FONT_SIZES,
    FONT_WEIGHTS,
    ICON_SIZES,
    MAIN_VIEW_CARDS,
    PAGE_FONTS,
    TEXTS,
    UI,
)
from src.db.db import SessionLocal, init_db
from src.domains import BibliographicResource
from src.services.pdf_service import PdfService
from src.services.settings_service import SettingsService, resolve_effective_theme
from src.utils.error_log import log_exception
from src.utils.types import ViewConfig
from src.views import ui_kit as ui
from src.views.pdf_reader.reader_view import PdfReaderView


def open_pdf_standalone_window(
    resource_id: int,
    page: ft.Page | None = None,
    config: ViewConfig | None = None,
    work_title: str | None = None,
) -> bool:
    """Dispara a janela dedicada do leitor de PDF em subprocesso independente."""
    import subprocess

    if page and config:
        label = work_title or f"Obra #{resource_id}"
        ui.toast(
            page,
            config,
            f"Abrindo leitor em janela dedicada: {label}...",
            icon_name="book-open",
        )

    env = os.environ.copy()
    root_dir = str(Path(__file__).resolve().parent.parent.parent.parent)
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        os.pathsep.join(filter(None, [root_dir, existing_pythonpath]))
        if existing_pythonpath
        else root_dir
    )

    try:
        subprocess.Popen(
            [sys.executable, "-m", "src.views.pdf_reader.standalone", str(resource_id)],
            env=env,
            start_new_session=True,
        )
        return True
    except Exception as error:
        log_exception(f"Falha ao iniciar processo da janela de leitura de PDF #{resource_id}", error)
        if page and config:
            ui.toast(page, config, f"Erro ao abrir janela do leitor: {error}")
        return False


def run_standalone_reader(resource_id: int) -> None:
    """Ponto de entrada que inicializa a aplicação Flet da janela dedicada."""
    init_db()
    settings_service = SettingsService()
    settings = settings_service.load_settings()

    with SessionLocal() as session:
        resource = session.get(BibliographicResource, resource_id)
        if resource is None:
            print(f"[ERRO] Recurso bibliográfico #{resource_id} não encontrado no banco.")
            return

        work = getattr(resource, "specific_work", None)
        title = (
            getattr(work, "title", None)
            if work
            else None
        ) or getattr(resource, "pdf_filename", None) or f"Obra #{resource_id}"

    def main(page: ft.Page) -> None:
        effective_theme = resolve_effective_theme(settings.theme_mode, page)
        view_config = ViewConfig(
            colors=COLORS_DARK if effective_theme == "dark" else COLORS_LIGHT,
            page_fonts=PAGE_FONTS,
            font_families=FONT_FAMILIES,
            font_sizes=FONT_SIZES,
            icon_sizes=ICON_SIZES,
            font_weights=FONT_WEIGHTS,
            ui=UI,
            texts=TEXTS,
            core_menus=CORE_MENUS,
            main_view_cards=MAIN_VIEW_CARDS,
        )

        page.title = f"Hupomnemata — Leitor: {title}"
        page.fonts = PAGE_FONTS
        page.padding = 0
        page.spacing = 0
        page.bgcolor = view_config.colors["bg"]

        # Janela nativa com controles de fechamento, redimensionamento e centralização
        page.window.width = 1150
        page.window.height = 860
        page.window.min_width = 750
        page.window.min_height = 550
        try:
            window = getattr(page, "window", None)
            if window is not None and hasattr(window, "center"):
                center_fn = window.center
                run_task = getattr(page, "run_task", None)
                if run_task is not None:
                    run_task(center_fn)
                elif not inspect.iscoroutinefunction(center_fn):
                    center_fn()
        except Exception:
            pass

        if hasattr(page, "theme_mode"):
            page.theme_mode = (
                ft.ThemeMode.DARK if effective_theme == "dark" else ft.ThemeMode.LIGHT
            )

        reader_ref: list[PdfReaderView] = []

        def close_window() -> None:
            if reader_ref:
                reader_ref[0].close()
            try:
                page.window.close()
            except Exception:
                pass

        def on_window_event(e: ft.WindowEvent) -> None:
            if getattr(e, "type", None) == ft.WindowEventType.CLOSE and reader_ref:
                reader_ref[0].close()
            elif reader_ref and hasattr(reader_ref[0], "handle_window_event"):
                reader_ref[0].handle_window_event(e)

        page.window.on_event = on_window_event

        def on_page_resize(e: ft.ControlEvent) -> None:
            if reader_ref and hasattr(reader_ref[0], "handle_page_resize"):
                reader_ref[0].handle_page_resize(e)

        page.on_resize = on_page_resize

        with SessionLocal() as inner_session:
            fresh_resource = inner_session.get(BibliographicResource, resource_id)
            if fresh_resource is None:
                page.add(
                    ui.empty_state(
                        view_config,
                        "triangle-exclamation",
                        "Obra indisponível",
                        "O recurso bibliográfico solicitado não está mais disponível no banco.",
                    )
                )
                page.update()
                return

            pdf_service = PdfService()
            reader_view = PdfReaderView(
                config=view_config,
                resource=fresh_resource,
                on_back=close_window,
                pdf_service=pdf_service,
                page=page,
                show_back_button=False,
            )
            reader_ref.append(reader_view)

        def on_keyboard(event: ft.KeyboardEvent) -> None:
            if reader_ref and getattr(reader_ref[0], "is_modal_open", False):
                return
            is_mod = bool(event.ctrl or event.meta or event.alt)
            reader_view.handle_key(event.key, is_mod)

        page.on_keyboard_event = on_keyboard
        page.add(reader_view)
        page.update()

    ft.run(main)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python -m src.views.pdf_reader.standalone <resource_id>")
        sys.exit(1)

    try:
        res_id = int(sys.argv[1])
    except ValueError:
        print(f"[ERRO] ID do recurso inválido: {sys.argv[1]}")
        sys.exit(1)

    run_standalone_reader(res_id)

"""Diálogo modal para Importação Reversa de Referências Bibliográficas (Texto/Nous).

Permite colar um bloco de texto acadêmico, segmentá-lo heurística e interativamente,
selecionar tipos de obra e extrair metadados estruturados exclusivamente via Nous (Gemini BYOK).
"""

from __future__ import annotations

import asyncio
import re
import threading
from collections.abc import Callable
from typing import Any

import flet as ft

from src.services.metadata_service import find_or_create_magazine
from src.services.nous_service import NousAIService
from src.services.work_form_service import WorkFormService
from src.services.work_service import WorkService
from src.utils.error_log import log_exception
from src.utils.fa import fa_icon
from src.utils.reference_parser import (
    detect_probable_work_type,
    split_references_block,
)
from src.utils.types import ViewConfig
from src.utils.ui_thread import run_on_ui
from src.views import ui_kit as ui
from src.views.ui_kit import s
from src.utils.control_safety import safe_update

WORK_TYPE_OPTIONS: list[tuple[str, str]] = [
    ("editorial_monograph", "Livro / Monografia editorial"),
    ("journal_article", "Artigo de periódico"),
    ("academic_monograph", "Tese / Dissertação / TCC"),
    ("monographic_proceedings", "Trabalho em anais (evento)"),
    ("newspaper_article", "Artigo de jornal"),
    ("statute", "Legislação / Norma"),
    ("caselaw", "Jurisprudência / Decisão judicial"),
    ("miscellaneous_digital_document", "Documento digital / Web"),
]

WORK_TYPE_MAP: dict[str, str] = dict(WORK_TYPE_OPTIONS)


def sanitize_work_metadata(meta: dict[str, Any], work_type: str) -> dict[str, Any]:
    """Normaliza e enriquece os metadados brutos conforme as exigências do modelo de destino."""
    sanitized = dict(meta)
    sanitized["work_type"] = work_type

    raw_date = str(sanitized.get("date_anchor") or "").strip()
    year_match = re.search(r"\b(19\d\d|20\d\d)\b", raw_date)
    year_str = year_match.group(1) if year_match else "2024"
    year_int = int(year_str)

    if not sanitized.get("title"):
        sanitized["title"] = "Obra sem título"
    if not sanitized.get("publication_place"):
        sanitized["publication_place"] = "[s.l.]"
    if not sanitized.get("publisher"):
        sanitized["publisher"] = "[s.n.]"

    if work_type == "journal_article":
        sanitized["is_partial"] = True
        j_title = str(
            sanitized.get("journal_title")
            or sanitized.get("publisher")
            or "Revista Acadêmica"
        ).strip()
        pub_place = str(sanitized.get("publication_place") or "[s.l.]")
        parent_id, _ = find_or_create_magazine(j_title, pub_place)
        sanitized["parent_bibliographic_resource_id"] = parent_id
        sanitized["journal_title"] = j_title

        # Assegura que publisher não seja poluído com o nome do periódico
        if sanitized.get("publisher") == j_title or not sanitized.get("publisher"):
            sanitized["publisher"] = "[s.n.]"

        # Trata paginação (part_start_page / part_end_page)
        start_p = str(sanitized.get("part_start_page") or sanitized.get("start_page") or "").strip()
        end_p = str(sanitized.get("part_end_page") or sanitized.get("end_page") or "").strip()
        if "-" in start_p or "–" in start_p or "—" in start_p:
            parts_p = re.split(r"[-–—]", start_p)
            start_p = parts_p[0].strip()
            if len(parts_p) > 1 and not end_p:
                end_p = parts_p[1].strip()
        start_digits = re.search(r"\d+", start_p)
        end_digits = re.search(r"\d+", end_p)
        sanitized["part_start_page"] = start_digits.group(0)[:6] if start_digits else (start_p[:6] or None)
        sanitized["part_end_page"] = end_digits.group(0)[:6] if end_digits else (end_p[:6] or None)

        num_val = sanitized.get("number")
        if num_val is not None:
            try:
                sanitized["number"] = int(re.search(r"\d+", str(num_val)).group(0))
            except Exception:
                sanitized["number"] = 1
        else:
            sanitized["number"] = 1

        vol_val = sanitized.get("volume")
        if vol_val is not None:
            try:
                sanitized["volume"] = int(re.search(r"\d+", str(vol_val)).group(0))
            except Exception:
                sanitized["volume"] = None

        parts = [p for p in raw_date.split("/") if p]
        if len(parts) == 1:
            sanitized["date_anchor"] = f"01/{year_str}"
        elif len(parts) == 3:
            sanitized["date_anchor"] = f"{parts[1].zfill(2)}/{parts[2]}"
        elif len(parts) == 2:
            sanitized["date_anchor"] = f"{parts[0].zfill(2)}/{parts[1]}"
        else:
            sanitized["date_anchor"] = f"01/{year_str}"

    elif work_type == "academic_monograph":
        sanitized["is_partial"] = False
        sanitized.setdefault("thesis_type", "Dissertação")
        sanitized.setdefault("education_level", "Pós-Graduação")
        sanitized.setdefault("course", "Geral")
        sanitized.setdefault(
            "faculty",
            sanitized.get("institution")
            or sanitized.get("publisher")
            or "Universidade",
        )
        sanitized["defense_year"] = int(sanitized.get("defense_year") or year_int)
        sanitized["page_quantity"] = int(sanitized.get("page_quantity") or 100)
        sanitized["date_anchor"] = year_str

    elif work_type == "monographic_proceedings":
        sanitized["is_partial"] = False
        title_str = sanitized.get("title", "Evento")
        sanitized.setdefault("event_name", f"Anais do {title_str}")
        sanitized["event_year"] = int(sanitized.get("event_year") or year_int)
        sanitized["publication_year"] = int(sanitized.get("publication_year") or year_int)
        sanitized["date_anchor"] = year_str

    elif work_type == "newspaper_article":
        sanitized.setdefault(
            "journal_title", sanitized.get("publisher") or "Jornal"
        )
        sanitized.setdefault(
            "start_page", sanitized.get("part_start_page") or "s.p."
        )
        parts = [p for p in raw_date.split("/") if p]
        if len(parts) == 1:
            sanitized["date_anchor"] = f"01/01/{year_str}"
        elif len(parts) == 2:
            sanitized["date_anchor"] = f"01/{parts[0].zfill(2)}/{parts[1]}"
        elif len(parts) == 3:
            sanitized["date_anchor"] = (
                f"{parts[0].zfill(2)}/{parts[1].zfill(2)}/{parts[2]}"
            )
        else:
            sanitized["date_anchor"] = f"01/01/{year_str}"

    elif work_type == "statute":
        sanitized["is_partial"] = False
        sanitized.setdefault("publication_media", "Diário Oficial")
        if sanitized.get("publication_place") in (None, "", "[s.l.]"):
            sanitized["publication_place"] = "Brasília"
        raw_prom = str(sanitized.get("promulgation_date") or raw_date).strip()
        parts = [p for p in raw_prom.split("/") if p]
        if len(parts) == 1:
            full_date = f"01/01/{year_str}"
        elif len(parts) == 2:
            full_date = f"01/{parts[0].zfill(2)}/{parts[1]}"
        elif len(parts) == 3:
            full_date = f"{parts[0].zfill(2)}/{parts[1].zfill(2)}/{parts[2]}"
        else:
            full_date = f"01/01/{year_str}"
        sanitized["date_anchor"] = full_date
        sanitized["promulgation_date"] = full_date

    elif work_type == "caselaw":
        sanitized["is_partial"] = False
        court_val = str(sanitized.get("court") or "").strip()
        sanitized.setdefault("publication_media", court_val or "Diário da Justiça")
        sanitized.setdefault("decision_type", "Acórdão")
        if sanitized.get("publication_place") in (None, "", "[s.l.]"):
            sanitized["publication_place"] = "Brasília"
        if court_val:
            sanitized.setdefault("panel", court_val)
            sanitized.setdefault("region", court_val)
        else:
            sanitized.setdefault("panel", "Tribunal Pleno")
            sanitized.setdefault("region", "[s.r.]")

        raw_dec = str(
            sanitized.get("decision_date")
            or sanitized.get("judgment_date")
            or raw_date
        ).strip()
        parts = [p for p in raw_dec.split("/") if p]
        if len(parts) == 1:
            full_date = f"01/01/{year_str}"
        elif len(parts) == 2:
            full_date = f"01/{parts[0].zfill(2)}/{parts[1]}"
        elif len(parts) == 3:
            full_date = f"{parts[0].zfill(2)}/{parts[1].zfill(2)}/{parts[2]}"
        else:
            full_date = f"01/01/{year_str}"
        sanitized["date_anchor"] = full_date
        sanitized["decision_date"] = full_date

    elif work_type == "editorial_monograph":
        is_chapter = bool(
            sanitized.get("is_partial")
            or sanitized.get("part_chapter")
            or (sanitized.get("part_start_page") and sanitized.get("collection_name"))
            or re.search(r"\bin:\s*", str(sanitized.get("raw") or ""), re.IGNORECASE)
        )
        sanitized["is_partial"] = is_chapter
        sanitized["date_anchor"] = year_str
        if is_chapter:
            start_p = str(sanitized.get("part_start_page") or "").strip()
            end_p = str(sanitized.get("part_end_page") or "").strip()
            if "-" in start_p or "–" in start_p or "—" in start_p:
                parts_p = re.split(r"[-–—]", start_p)
                start_p = parts_p[0].strip()
                if len(parts_p) > 1 and not end_p:
                    end_p = parts_p[1].strip()
            start_digits = re.search(r"\d+", start_p)
            end_digits = re.search(r"\d+", end_p)
            sanitized["part_start_page"] = start_digits.group(0)[:6] if start_digits else (start_p[:6] or None)
            sanitized["part_end_page"] = end_digits.group(0)[:6] if end_digits else (end_p[:6] or None)

    elif work_type == "miscellaneous_digital_document":
        sanitized["is_partial"] = False
        sanitized["date_anchor"] = year_str
        sanitized.setdefault("publication_place", "[s.l.]")
        raw_access = str(sanitized.get("viewed_at") or sanitized.get("access_date") or "").strip()
        if raw_access:
            parts = [p for p in raw_access.split("/") if p]
            if len(parts) == 3:
                sanitized["viewed_at"] = f"{parts[0].zfill(2)}/{parts[1].zfill(2)}/{parts[2]}"
            elif len(parts) == 2:
                sanitized["viewed_at"] = f"01/{parts[0].zfill(2)}/{parts[1]}"
            elif len(parts) == 1:
                match_acc_year = re.search(r"\b(19\d\d|20\d\d)\b", raw_access)
                acc_year = match_acc_year.group(1) if match_acc_year else year_str
                sanitized["viewed_at"] = f"01/01/{acc_year}"

    return sanitized

    return sanitized


class ReverseImportModalDialog:
    """Orquestra o rito de importação reversa de referências através do motor Nous."""

    def __init__(
        self,
        page: ft.Page,
        config: ViewConfig,
        nous_service: NousAIService,
        work_service: WorkService,
        form_service: WorkFormService,
        on_success: Callable[[int], None] | None = None,
        on_open_nous_settings: Callable[[], None] | None = None,
    ) -> None:
        self.page = page
        self.config = config
        self.nous_service = nous_service
        self.work_service = work_service
        self.form_service = form_service
        self.on_success = on_success
        self.on_open_nous_settings = on_open_nous_settings

        self.dialog: ft.AlertDialog | None = None
        self.is_open = False
        self.phase: int = 1
        self.is_processing = False
        self.selected_batch_type: str = WORK_TYPE_OPTIONS[0][0]

        # Lista de itens segmentados
        # Cada item: {"raw": str, "work_type": str, "metadata": dict | None, "success": bool, "error": str | None, "selected": bool}
        self.items: list[dict[str, Any]] = []

        # Controles da Fase 1 (Entrada de Bloco)
        c = self.config
        self.input_textarea = ft.TextField(
            multiline=True,
            min_lines=8,
            max_lines=12,
            text_size=s(13),
            hint_text=(
                "Cole aqui o bloco de referências bibliográficas do artigo ou livro...\n\n"
                "Exemplo:\n"
                "FOUCAULT, Michel. Vigiar e punir: nascimento da prisão. Petrópolis: Vozes, 2014.\n\n"
                "HABERMAS, Jürgen. Ação comunicativa e razão destranscendentalizada. "
                "Cadernos de Filosofia Alemã, v. 23, n. 2, p. 11-28, 2018."
            ),
            bgcolor=c.colors.get("surface_variant", c.colors["surface"]),
            color=c.colors["text"],
            border_color=c.colors["border"],
            focused_border_color=c.colors["gold"],
            cursor_color=c.colors["gold"],
            border_radius=s(6),
            autofocus=True,
        )

        self.error_text = ui.ui_text(c, "", size=12, color=c.colors["danger"])
        self.error_container = ft.Container(
            content=ft.Row(
                [
                    fa_icon("circle-exclamation", size=s(14), color=c.colors["danger"]),
                    ft.Container(content=self.error_text, expand=True),
                ],
                spacing=s(8),
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            visible=False,
            padding=ft.Padding.symmetric(vertical=s(4)),
        )

        # Contêiner de conteúdo dinâmico (troca conforme a fase)
        self.content_container = ft.AnimatedSwitcher(
            content=ft.Container(),
            duration=ui.MOTION_SLOW,
            reverse_duration=ui.MOTION_FAST,
            switch_in_curve=ft.AnimationCurve.EASE_OUT,
            switch_out_curve=ft.AnimationCurve.EASE_IN,
            transition=ft.AnimatedSwitcherTransition.FADE,
        )

    def show(self) -> None:
        """Apresenta o diálogo de importação reversa."""
        c = self.config
        self.phase = 1
        self.items.clear()
        self.selected_batch_type = WORK_TYPE_OPTIONS[0][0]
        self.error_container.visible = False
        self.input_textarea.value = ""

        header = ft.Container(
            content=ft.Row(
                [
                    fa_icon("file-lines", size=s(18), color=c.colors["gold"]),
                    ft.Column(
                        [
                            ui.serif_text(c, "Importação por Referências (Texto / Nous)", size=18, weight=ui.W700),
                            ui.ui_text(
                                c,
                                "Decomponha listas bibliográficas e extraia metadados estruturados via IA do Nous.",
                                size=12,
                                color=c.colors["muted"],
                            ),
                        ],
                        spacing=s(2),
                        tight=True,
                        expand=True,
                    ),
                    ui.icon_button(c, "xmark", on_click=lambda _e: self.close(), tooltip="Fechar (Esc)"),
                ],
                spacing=s(12),
                vertical_alignment=ft.CrossAxisAlignment.START,
            ),
            padding=s(18),
            border=ft.Border.only(bottom=ft.BorderSide(1, c.colors["border"])),
        )

        self._render_current_phase()

        body = ft.Container(
            width=s(740),
            content=ft.Column(
                [
                    header,
                    self.content_container,
                ],
                spacing=0,
                tight=True,
            ),
        )

        self.dialog = ft.AlertDialog(
            content=body,
            content_padding=0,
            bgcolor=c.colors["surface"],
            shape=ft.RoundedRectangleBorder(radius=s(10)),
            alignment=ft.Alignment.CENTER,
            barrier_color=ft.Colors.with_opacity(0.65, c.colors["black"]),
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            on_dismiss=lambda _e: setattr(self, "is_open", False),
        )

        self.is_open = True
        ui.open_dialog(self.page, self.dialog)

    def close(self) -> None:
        """Fecha o diálogo modal com segurança."""
        self.is_open = False
        if self.dialog is not None:
            self.dialog.open = False
            ui.close_dialog(self.page)

    def _render_current_phase(self) -> None:
        """Atualiza o conteúdo do diálogo conforme a fase ativa."""
        if self.phase == 1:
            self.content_container.content = self._compose_phase1()
        elif self.phase == 2:
            self.content_container.content = self._compose_phase2()
        elif self.phase == 3:
            self.content_container.content = self._compose_phase3()

    # ── FASE 1: ENTRADA DE BLOCO ──────────────────────────────────────

    def _compose_phase1(self) -> ft.Container:
        c = self.config
        has_key = self.nous_service.has_api_key()

        # Aviso quando a chave do Nous não está cadastrada
        key_warning = ft.Container(
            content=ft.Row(
                [
                    fa_icon("triangle-exclamation", size=s(16), color=c.colors["gold"]),
                    ft.Column(
                        [
                            ui.ui_text(
                                c,
                                "Chave de API do Nous (Gemini BYOK) não configurada.",
                                size=12,
                                weight=ui.W600,
                                color=c.colors["gold"],
                            ),
                            ui.ui_text(
                                c,
                                "A extração de metadados estruturados depende exclusivamente da cognição do Nous. "
                                "Configure sua chave no Menu Nous para prosseguir.",
                                size=11,
                                color=c.colors["muted"],
                            ),
                        ],
                        spacing=s(2),
                        tight=True,
                        expand=True,
                    ),
                    ui.button(
                        c,
                        "Configurar Chave",
                        icon_name="key",
                        variant="ghost",
                        on_click=lambda _e: self._on_go_to_nous_settings(),
                    ),
                ],
                spacing=s(10),
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=ft.Colors.with_opacity(0.08, c.colors["gold"]),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.3, c.colors["gold"])),
            border_radius=s(6),
            padding=s(12),
            visible=not has_key,
        )

        controls: list[ft.Control] = [
            key_warning,
            ui.ui_text(
                c,
                "Cole abaixo o bloco de referências bibliográficas:",
                size=12,
                weight=ui.W600,
            ),
            self.input_textarea,
            self.error_container,
        ]

        footer = ft.Container(
            content=ft.Row(
                [
                    ft.Container(expand=True),
                    ui.button(c, "Cancelar", on_click=lambda _e: self.close(), variant="ghost"),
                    ui.button(
                        c,
                        "Segmentar Referências",
                        icon_name="scissors",
                        variant="primary",
                        on_click=lambda _e: self._on_segment_clicked(),
                    ),
                ],
                spacing=s(8),
            ),
            padding=ft.Padding.only(top=s(14)),
        )

        return ft.Container(
            content=ft.Column(controls + [footer], spacing=s(12), tight=True),
            padding=s(18),
        )

    def _on_go_to_nous_settings(self) -> None:
        self.close()
        if self.on_open_nous_settings:
            self.on_open_nous_settings()

    def _on_segment_clicked(self) -> None:
        raw_text = self.input_textarea.value or ""
        segments = split_references_block(raw_text)
        if not segments:
            self.error_text.value = "Nenhuma referência válida detectada no bloco de texto informado."
            self.error_container.visible = True
            self.page.update()
            return

        self.error_container.visible = False
        self.items = [
            {
                "raw": seg,
                "work_type": detect_probable_work_type(seg),
                "metadata": None,
                "success": False,
                "error": None,
                "selected": True,
            }
            for seg in segments
        ]
        self.phase = 2
        self._render_current_phase()
        self.page.update()

    # ── FASE 2: REVISÃO DE SEGMENTOS E TIPOS ──────────────────────────

    def _compose_phase2(self) -> ft.Container:
        c = self.config
        has_key = self.nous_service.has_api_key()

        # Seletor em lote para definir tipo de todas
        batch_type_dropdown = ft.Dropdown(
            options=[ft.dropdown.Option(k, v) for k, v in WORK_TYPE_OPTIONS],
            value=self.selected_batch_type,
            height=s(34),
            text_size=s(12),
            bgcolor=c.colors.get("surface_variant", c.colors["surface"]),
            border_color=c.colors["border"],
            focused_border_color=c.colors["gold"],
            border_radius=s(6),
        )

        def on_batch_type_change(e):
            self.selected_batch_type = e.control.value
            batch_type_dropdown.value = e.control.value

        batch_type_dropdown.on_change = on_batch_type_change

        def on_apply_batch_type(_e):
            selected_type = self.selected_batch_type or batch_type_dropdown.value
            if selected_type:
                for item in self.items:
                    item["work_type"] = selected_type
                    if item.get("metadata"):
                        item["metadata"]["work_type"] = selected_type
                self._render_current_phase()
                self.page.update()

        batch_bar = ft.Container(
            content=ft.Row(
                [
                    ui.ui_text(c, f"{len(self.items)} referências identificadas", size=13, weight=ui.W700),
                    ft.Container(expand=True),
                    ui.ui_text(c, "Definir todas como:", size=12, color=c.colors["muted"]),
                    ft.Container(content=batch_type_dropdown, width=s(210)),
                    ui.button(c, "Aplicar a todas", on_click=on_apply_batch_type, variant="ghost"),
                ],
                spacing=s(8),
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=ft.Colors.with_opacity(0.04, c.colors["text"]),
            border=ft.Border.all(1, c.colors["border"]),
            border_radius=s(6),
            padding=s(8),
        )

        # Monta os cartões de cada referência segmentada
        cards: list[ft.Control] = []
        for idx, item in enumerate(self.items, 1):
            cards.append(self._compose_segment_card(idx, item))

        cards_list = ft.ListView(
            controls=cards,
            spacing=s(10),
            height=s(320),
        )

        btn_extract = ui.button(
            c,
            "Extrair com Nous (IA)",
            icon_name="wand-magic-sparkles",
            variant="primary",
            disabled=not has_key or len(self.items) == 0,
            on_click=lambda _e: self._on_extract_clicked(),
        )

        footer = ft.Container(
            content=ft.Row(
                [
                    ui.button(
                        c,
                        "Voltar para Texto",
                        icon_name="arrow-left",
                        variant="ghost",
                        on_click=lambda _e: self._go_phase(1),
                    ),
                    ft.Container(expand=True),
                    ui.button(c, "Cancelar", on_click=lambda _e: self.close(), variant="ghost"),
                    btn_extract,
                ],
                spacing=s(8),
            ),
            padding=ft.Padding.only(top=s(14)),
        )

        return ft.Container(
            content=ft.Column(
                [
                    batch_bar,
                    cards_list,
                    self.error_container,
                    footer,
                ],
                spacing=s(12),
                tight=True,
            ),
            padding=s(18),
        )

    def _compose_segment_card(self, index: int, item: dict[str, Any]) -> ft.Container:
        c = self.config

        current_type = item.get("work_type")
        if current_type not in WORK_TYPE_MAP:
            current_type = WORK_TYPE_OPTIONS[0][0]
            item["work_type"] = current_type

        type_dropdown = ft.Dropdown(
            options=[ft.dropdown.Option(k, v) for k, v in WORK_TYPE_OPTIONS],
            value=current_type,
            height=s(32),
            text_size=s(11),
            bgcolor=c.colors.get("surface_variant", c.colors["surface"]),
            border_color=c.colors["border"],
            focused_border_color=c.colors["gold"],
            border_radius=s(4),
        )

        def on_type_changed(e):
            item["work_type"] = e.control.value
            type_dropdown.value = e.control.value
            if item.get("metadata"):
                item["metadata"]["work_type"] = e.control.value

        type_dropdown.on_change = on_type_changed

        text_input = ft.TextField(
            value=item["raw"],
            multiline=True,
            min_lines=2,
            max_lines=3,
            text_size=s(12),
            bgcolor=c.colors.get("surface_variant", c.colors["surface"]),
            color=c.colors["text"],
            border_color=c.colors["border"],
            focused_border_color=c.colors["gold"],
            border_radius=s(4),
            expand=True,
        )

        def on_text_changed(e):
            item["raw"] = e.control.value

        text_input.on_change = on_text_changed

        def on_delete_item(_e):
            if item in self.items:
                self.items.remove(item)
                if not self.items:
                    self._go_phase(1)
                    return
                self._render_current_phase()
                self.page.update()

        badge = ft.Container(
            content=ui.ui_text(c, f"#{index}", size=11, weight=ui.W700, color=c.colors["gold"]),
            bgcolor=ft.Colors.with_opacity(0.12, c.colors["gold"]),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.3, c.colors["gold"])),
            border_radius=s(4),
            padding=ft.Padding.symmetric(horizontal=s(6), vertical=s(2)),
        )

        header_row = ft.Row(
            [
                badge,
                ft.Container(content=type_dropdown, width=s(220)),
                ft.Container(expand=True),
                ui.icon_button(c, "trash-can", on_click=on_delete_item, tooltip="Remover referência"),
            ],
            spacing=s(8),
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        return ft.Container(
            content=ft.Column(
                [
                    header_row,
                    text_input,
                ],
                spacing=s(6),
                tight=True,
            ),
            bgcolor=ft.Colors.with_opacity(0.03, c.colors["text"]),
            border=ft.Border.all(1, c.colors["border"]),
            border_radius=s(6),
            padding=s(10),
        )

    def _go_phase(self, phase: int) -> None:
        self.phase = phase
        self.error_container.visible = False
        self._render_current_phase()
        self.page.update()

    # ── FASE 3: EXTRAÇÃO E PERSISTÊNCIA NO ACERVO ─────────────────────

    def _on_extract_clicked(self) -> None:
        """Inicia o processamento no Nous em thread desacoplada."""
        if not self.nous_service.has_api_key():
            self.error_text.value = (
                "Chave de API do Nous não encontrada. Cadastre sua chave no Menu Nous (BYOK)."
            )
            self.error_container.visible = True
            self.page.update()
            return

        self.phase = 3
        self.is_processing = True
        self._render_current_phase()
        self.page.update()

        run_task = getattr(self.page, "run_task", None)
        if run_task is not None:
            run_task(self._async_run_extraction)
        else:
            thread = threading.Thread(target=self._run_extraction_background, daemon=True)
            thread.start()

    async def _async_run_extraction(self) -> None:
        """Executa os workloads do Nous e atualiza a interface a cada item em tempo real."""
        try:
            total = len(self.items)
            for idx, item in enumerate(self.items, 1):
                raw = item["raw"].strip()
                work_type = item["work_type"]

                ok, meta, msg = await asyncio.to_thread(
                    self.nous_service.extract_reference_metadata, raw, work_type
                )
                item["success"] = ok
                item["metadata"] = meta if ok else None
                item["error"] = msg if not ok else None
                item["selected"] = ok

                # Aproveitamento da validação e sugestão cognitiva do motor Nous
                if ok and meta:
                    suggested = meta.get("suggested_work_type")
                    if suggested and suggested in WORK_TYPE_MAP:
                        item["work_type"] = suggested
                        meta["work_type"] = suggested

                # Atualiza progresso em tempo real
                self.progress_label.value = f"Processando referência {idx} de {total} via Nous..."
                self.progress_bar.value = idx / total
                try:
                    self.progress_label.update()
                    self.progress_bar.update()
                except Exception:
                    safe_update(self.page)

        except Exception as exc:
            log_exception("ReverseImportModalDialog._async_run_extraction", exc)
        finally:
            self.is_processing = False
            self._render_current_phase()
            safe_update(self.page)

    def _run_extraction_background(self) -> None:
        """Executa os workloads do Nous e atualiza a interface a cada item (fallback para thread pura)."""
        try:
            total = len(self.items)
            for idx, item in enumerate(self.items, 1):
                raw = item["raw"].strip()
                work_type = item["work_type"]

                ok, meta, msg = self.nous_service.extract_reference_metadata(raw, work_type)
                item["success"] = ok
                item["metadata"] = meta if ok else None
                item["error"] = msg if not ok else None
                item["selected"] = ok

                # Aproveitamento da validação e sugestão cognitiva do motor Nous
                if ok and meta:
                    suggested = meta.get("suggested_work_type")
                    if suggested and suggested in WORK_TYPE_MAP:
                        item["work_type"] = suggested
                        meta["work_type"] = suggested

                # Atualiza progresso
                def _apply_progress() -> None:
                    self.progress_label.value = f"Processando referência {idx} de {total} via Nous..."
                    self.progress_bar.value = idx / total
                    safe_update(self.page)

                run_on_ui(self.page, _apply_progress)

        except Exception as exc:
            log_exception("ReverseImportModalDialog._run_extraction_background", exc)
        finally:
            def _apply_finished() -> None:
                self.is_processing = False
                self._render_current_phase()
                safe_update(self.page)

            run_on_ui(self.page, _apply_finished)

    def _compose_phase3(self) -> ft.Container:
        c = self.config

        if self.is_processing:
            self.progress_bar = ft.ProgressBar(value=0, color=c.colors["gold"], bgcolor=c.colors["border"])
            self.progress_label = ui.ui_text(c, "Consultando motor cognitivo Nous...", size=13, weight=ui.W600)

            return ft.Container(
                content=ft.Column(
                    [
                        ft.Container(height=s(40)),
                        ft.Row([fa_icon("brain", size=s(24), color=c.colors["gold"])], alignment=ft.MainAxisAlignment.CENTER),
                        ft.Container(height=s(10)),
                        ft.Row([self.progress_label], alignment=ft.MainAxisAlignment.CENTER),
                        ft.Container(content=self.progress_bar, width=s(480), margin=ft.Margin.symmetric(vertical=s(16))),
                        ui.ui_text(c, "Extraindo autores, títulos, periódicos e dados documentais.", size=11, color=c.colors["muted"]),
                        ft.Container(height=s(40)),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    tight=True,
                ),
                padding=s(24),
            )

        # Processamento finalizado: exibe os resultados
        success_count = sum(1 for it in self.items if it.get("success"))
        total_count = len(self.items)

        header_text = f"{success_count} de {total_count} referências estruturadas com sucesso"
        status_header = ft.Row(
            [
                fa_icon("circle-check" if success_count > 0 else "circle-exclamation", size=s(16), color=c.colors["gold"] if success_count > 0 else c.colors["danger"]),
                ui.ui_text(c, header_text, size=13, weight=ui.W700),
                ft.Container(expand=True),
                ui.ui_text(c, f"Modelo: {self.nous_service.preferred_model}", size=11, color=c.colors["faint"]),
            ],
            spacing=s(8),
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        # Seletor em lote na Fase 3
        batch_type_dropdown_p3 = ft.Dropdown(
            options=[ft.dropdown.Option(k, v) for k, v in WORK_TYPE_OPTIONS],
            value=self.selected_batch_type,
            height=s(32),
            text_size=s(11),
            bgcolor=c.colors.get("surface_variant", c.colors["surface"]),
            border_color=c.colors["border"],
            focused_border_color=c.colors["gold"],
            border_radius=s(6),
        )

        def on_p3_batch_change(e):
            self.selected_batch_type = e.control.value
            batch_type_dropdown_p3.value = e.control.value

        batch_type_dropdown_p3.on_change = on_p3_batch_change

        def on_apply_batch_type_p3(_e):
            selected_type = self.selected_batch_type or batch_type_dropdown_p3.value
            if selected_type:
                for item in self.items:
                    item["work_type"] = selected_type
                    if item.get("metadata"):
                        item["metadata"]["work_type"] = selected_type
                self._render_current_phase()
                self.page.update()

        batch_bar_p3 = ft.Container(
            content=ft.Row(
                [
                    ui.ui_text(c, "Definir todas como:", size=11, color=c.colors["muted"]),
                    ft.Container(content=batch_type_dropdown_p3, width=s(210)),
                    ui.button(c, "Aplicar a todas", on_click=on_apply_batch_type_p3, variant="ghost"),
                ],
                spacing=s(8),
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=ft.Colors.with_opacity(0.04, c.colors["text"]),
            border=ft.Border.all(1, c.colors["border"]),
            border_radius=s(6),
            padding=s(6),
        )

        cards: list[ft.Control] = []
        for idx, item in enumerate(self.items, 1):
            cards.append(self._compose_result_card(idx, item))

        results_list = ft.ListView(
            controls=cards,
            spacing=s(10),
            height=s(320),
        )

        btn_save = ui.button(
            c,
            f"Salvar {success_count} no Acervo",
            icon_name="floppy-disk",
            variant="primary",
            disabled=success_count == 0,
            on_click=lambda _e: self._on_save_all_clicked(),
        )

        footer = ft.Container(
            content=ft.Row(
                [
                    ui.button(
                        c,
                        "Voltar aos Segmentos",
                        icon_name="arrow-left",
                        variant="ghost",
                        on_click=lambda _e: self._go_phase(2),
                    ),
                    ft.Container(expand=True),
                    ui.button(c, "Cancelar", on_click=lambda _e: self.close(), variant="ghost"),
                    btn_save,
                ],
                spacing=s(8),
            ),
            padding=ft.Padding.only(top=s(14)),
        )

        return ft.Container(
            content=ft.Column(
                [
                    status_header,
                    batch_bar_p3,
                    results_list,
                    self.error_container,
                    footer,
                ],
                spacing=s(12),
                tight=True,
            ),
            padding=s(18),
        )

    def _compose_result_card(self, index: int, item: dict[str, Any]) -> ft.Container:
        c = self.config
        ok = item.get("success", False)
        meta = item.get("metadata") or {}

        # Checkbox de seleção
        chk = ft.Checkbox(
            value=bool(item.get("selected", False)),
            active_color=c.colors["gold"],
            check_color=c.colors["surface"],
        )

        def on_chk_change(e):
            item["selected"] = bool(e.control.value)

        chk.on_change = on_chk_change

        badge_num = ft.Container(
            content=ui.ui_text(c, f"#{index}", size=11, weight=ui.W700, color=c.colors["gold"]),
            bgcolor=ft.Colors.with_opacity(0.12, c.colors["gold"]),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.3, c.colors["gold"])),
            border_radius=s(4),
            padding=ft.Padding.symmetric(horizontal=s(6), vertical=s(2)),
        )

        current_card_type = item.get("work_type")
        if current_card_type not in WORK_TYPE_MAP:
            current_card_type = WORK_TYPE_OPTIONS[0][0]
            item["work_type"] = current_card_type

        type_dropdown_card = ft.Dropdown(
            options=[ft.dropdown.Option(k, v) for k, v in WORK_TYPE_OPTIONS],
            value=current_card_type,
            height=s(30),
            text_size=s(11),
            bgcolor=c.colors.get("surface_variant", c.colors["surface"]),
            border_color=c.colors["border"],
            focused_border_color=c.colors["gold"],
            border_radius=s(4),
        )

        def on_card_type_changed(e):
            item["work_type"] = e.control.value
            type_dropdown_card.value = e.control.value
            if item.get("metadata"):
                item["metadata"]["work_type"] = e.control.value

        type_dropdown_card.on_change = on_card_type_changed

        if ok:
            title = meta.get("title", "Obra sem título")
            subtitle = meta.get("subtitle")
            full_title = f"{title}: {subtitle}" if subtitle else title

            # Formatação de autores
            authors = meta.get("authors", [])
            author_names = []
            if isinstance(authors, list):
                for a in authors:
                    if isinstance(a, dict):
                        author_names.append(a.get("name", ""))
                    elif isinstance(a, str):
                        author_names.append(a)
            authors_str = "; ".join([n for n in author_names if n]) or "Autoria não identificada"

            year = meta.get("date_anchor", "s.d.")
            pub = meta.get("publisher") or ""
            j_title = meta.get("journal_title") or ""
            place = meta.get("publication_place") or ""
            w_type = item.get("work_type", "editorial_monograph")

            details_parts = [f"Ano: {year}"]
            if w_type == "journal_article":
                rev = j_title or pub or "Revista Acadêmica"
                vol = f"v. {meta.get('volume')}" if meta.get("volume") else ""
                num = f"n. {meta.get('number')}" if meta.get("number") else ""
                p_range = ""
                if meta.get("part_start_page"):
                    p_range = f"p. {meta['part_start_page']}"
                    if meta.get("part_end_page"):
                        p_range += f"-{meta['part_end_page']}"
                vol_num = " • ".join([x for x in [vol, num, p_range] if x])
                details_parts.append(f"Periódico: {rev}")
                if vol_num:
                    details_parts.append(vol_num)
            elif w_type == "caselaw":
                dec_type = meta.get("decision_type") or "Acórdão"
                tribunal = meta.get("panel") or meta.get("region") or meta.get("court") or ""
                num_proc = meta.get("case_number")
                details_parts.append(f"Decisão: {dec_type}")
                if tribunal:
                    details_parts.append(f"Tribunal/Órgão: {tribunal}")
                if num_proc:
                    details_parts.append(f"Processo: {num_proc}")
            elif w_type == "statute":
                media = meta.get("publication_media") or "Diário Oficial"
                promulg = meta.get("promulgation_date") or year
                details_parts.append(f"Promulgação: {promulg}")
                details_parts.append(f"Veículo: {media}")
            elif w_type == "miscellaneous_digital_document":
                url_val = meta.get("url")
                acc_val = meta.get("viewed_at") or meta.get("access_date")
                if url_val:
                    details_parts.append(f"URL: {url_val}")
                if acc_val:
                    details_parts.append(f"Acesso: {acc_val}")
            else:
                if pub and pub != "[s.n.]":
                    details_parts.append(f"Editora: {pub}")
                if place and place != "[s.l.]":
                    details_parts.append(f"Local: {place}")
                if meta.get("is_partial") and meta.get("part_start_page"):
                    p_info = f"p. {meta['part_start_page']}"
                    if meta.get("part_end_page"):
                        p_info += f"-{meta['part_end_page']}"
                    details_parts.append(f"Capítulo ({p_info})")

            details_str = " • ".join(details_parts)

            content_col = ft.Column(
                [
                    ft.Row(
                        [
                            chk,
                            badge_num,
                            ft.Container(content=type_dropdown_card, width=s(220)),
                            ft.Container(expand=True),
                        ],
                        spacing=s(6),
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ui.serif_text(c, full_title, size=14, weight=ui.W700, color=c.colors["text"]),
                    ui.ui_text(c, f"Autores: {authors_str}", size=11, weight=ui.W600, color=c.colors["gold"]),
                    ui.ui_text(c, details_str, size=11, color=c.colors["muted"]),
                ],
                spacing=s(4),
                tight=True,
                expand=True,
            )
        else:
            err_msg = item.get("error") or "Falha ao processar pelo Nous."
            content_col = ft.Column(
                [
                    ft.Row(
                        [
                            badge_num,
                            ft.Container(content=type_dropdown_card, width=s(220)),
                            ft.Container(expand=True),
                        ],
                        spacing=s(6),
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ui.ui_text(c, f"Texto original: {item['raw']}", size=11, color=c.colors["muted"]),
                    ui.ui_text(c, f"Erro: {err_msg}", size=11, color=c.colors["danger"]),
                ],
                spacing=s(4),
                tight=True,
                expand=True,
            )

        return ft.Container(
            content=content_col,
            bgcolor=ui.alpha(c.colors["gold"] if ok else c.colors["danger"], 0.04),
            border=ft.Border.all(1, ui.alpha(c.colors["gold"] if ok else c.colors["danger"], 0.2)),
            border_radius=s(6),
            padding=s(10),
        )

    def _on_save_all_clicked(self) -> None:
        """Persiste as obras selecionadas no acervo do banco de dados."""
        items_to_save = [
            it for it in self.items
            if it.get("selected") and it.get("success") and it.get("metadata")
        ]
        if not items_to_save:
            return

        saved_count = 0
        errors: list[str] = []

        for item in items_to_save:
            meta = item["metadata"]
            target_work_type = (
                item.get("work_type")
                or meta.get("work_type")
                or "editorial_monograph"
            )
            try:
                sanitized_meta = sanitize_work_metadata(meta, target_work_type)
                payload = self.form_service.prepare_payload(sanitized_meta)
                self.work_service.create(payload)
                saved_count += 1
            except Exception as exc:
                title = meta.get("title", "Obra")
                log_exception(f"Falha ao salvar obra importada: {title}", exc)
                errors.append(f"{title}: {exc}")

        # Fecha e notifica
        self.close()
        if self.on_success:
            self.on_success(saved_count)

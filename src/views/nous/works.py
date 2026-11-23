"""Implementações de works do compositor Nous."""

from __future__ import annotations

from typing import TYPE_CHECKING

from typing import Any
from typing import Dict
from typing import List
import flet as ft
from src.utils.control_safety import safe_update

if TYPE_CHECKING:
    from src.views.nous_composer import NousComposer


def build_work_actions(self: NousComposer, w: Dict[str, Any]) -> ft.Control:
    w_id = w["id"]
    is_generating = w_id in self.generating_work_ids
    if is_generating:
        return ft.Container(
            bgcolor=self.config.colors["surface"],
            border=ft.Border.all(1, self.config.colors["border"]),
            border_radius=6,
            padding=ft.Padding(12 * self.scale, 8 * self.scale, 12 * self.scale, 8 * self.scale),
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(
                                ft.Icons.AUTO_AWESOME,
                                size=14 * self.scale,
                                color=self.config.colors["gold"],
                            ),
                            ft.Text(
                                "Consultando Nous... gerando síntese conceitual",
                                size=12 * self.scale,
                                font_family=self.config.font_families["montserrat"],
                                weight=ft.FontWeight.W_600,
                                color=self.config.colors["text"],
                            ),
                        ],
                        spacing=6 * self.scale,
                        tight=True,
                    ),
                    ft.ProgressBar(
                        color=self.config.colors["gold"],
                        bgcolor=self.config.colors["border"],
                        height=4 * self.scale,
                    ),
                ],
                spacing=6 * self.scale,
                tight=True,
            ),
        )
    return ft.Row(
        controls=[
            ft.FilledButton(
                content="Gerar com Nous",
                icon=ft.Icons.BOLT,
                on_click=lambda _, wid=w_id: self._handle_single_generate(wid),
                style=ft.ButtonStyle(
                    bgcolor=self.config.colors["gold"],
                    color=self.config.colors["on_gold"],
                ),
            ),
            ft.OutlinedButton(
                content="Sobrepor / Editar",
                icon=ft.Icons.EDIT_NOTE,
                on_click=lambda _, work_item=w: self._open_override_dialog(work_item),
                style=ft.ButtonStyle(
                    color=self.config.colors["text"],
                    side=ft.BorderSide(1, self.config.colors["border"]),
                ),
            ),
        ],
        spacing=8 * self.scale,
    )


def render_works_list(self: NousComposer, items: List[Dict[str, Any]]) -> None:
    """Renderiza cartões de obras com opções de geração de IA e sobreposição."""
    self.works_column.controls.clear()
    self.work_actions_containers.clear()
    self.work_snippet_texts.clear()
    self.work_badge_containers.clear()

    if not items:
        self.works_column.controls.append(
            ft.Container(
                alignment=ft.Alignment(0, 0),
                padding=20 * self.scale,
                content=ft.Text(
                    "Nenhuma obra encontrada no acervo.",
                    size=14 * self.scale,
                    font_family=self.config.font_families["montserrat"],
                    color=self.config.colors["muted"],
                ),
            )
        )
        return

    for w in items:
        w_id = w["id"]
        title = w["title"]
        authors = w["authors"]
        year = w["year"]
        status_label = w["status_label"]
        status_color = w["status_color"]
        snippet = w["snippet"] or "Sem síntese cadastrada."
        has_snippet = bool(w["snippet"])

        status_badge = ft.Container(
            content=ft.Text(
                status_label.upper(),
                size=10 * self.scale,
                weight=ft.FontWeight.W_600,
                font_family=self.config.font_families["montserrat"],
                color=status_color,
            ),
            bgcolor=self.config.colors["surface"],
            border=ft.Border.all(1, status_color),
            border_radius=4,
            padding=ft.Padding(8 * self.scale, 3 * self.scale, 8 * self.scale, 3 * self.scale),
        )
        self.work_badge_containers[w_id] = status_badge

        actions_box = ft.Container(
            content=self._build_work_actions(w),
        )
        self.work_actions_containers[w_id] = actions_box

        snippet_text = ft.Text(
            snippet,
            size=16 * self.scale,
            font_family=self.config.font_families["cormorant"],
            weight=ft.FontWeight.W_600 if has_snippet else ft.FontWeight.W_500,
            color=self.config.colors["text"] if has_snippet else self.config.colors["muted"],
            italic=not has_snippet,
            style=ft.TextStyle(height=1.45),
            selectable=True,
            text_align=ft.TextAlign.JUSTIFY if has_snippet else None,
        )
        self.work_snippet_texts[w_id] = snippet_text

        snippet_box = ft.Container(
            bgcolor=self.config.colors["surface"],
            border=ft.Border(left=ft.BorderSide(3 * self.scale, status_color)),
            border_radius=4,
            padding=ft.Padding(12 * self.scale, 10 * self.scale, 12 * self.scale, 10 * self.scale),
            content=snippet_text,
        )

        card = ft.Container(
            bgcolor=self.config.colors["bg"],
            border=ft.Border.all(1, self.config.colors["border"]),
            border_radius=8,
            padding=12 * self.scale,
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Column(
                                controls=[
                                    ft.Text(
                                        title,
                                        size=18.5 * self.scale,
                                        font_family=self.config.font_families["cormorant"],
                                        weight=ft.FontWeight.W_700,
                                        color=self.config.colors["gold"],
                                    ),
                                    ft.Text(
                                        f"{authors} • {year or 's.d.'}",
                                        size=12 * self.scale,
                                        font_family=self.config.font_families["montserrat"],
                                        weight=ft.FontWeight.W_500,
                                        color=self.config.colors["muted"],
                                    ),
                                ],
                                spacing=2 * self.scale,
                                tight=True,
                                expand=True,
                            ),
                            status_badge,
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    snippet_box,
                    actions_box,
                ],
                spacing=8 * self.scale,
                tight=True,
            ),
        )
        self.works_column.controls.append(card)


def update_single_work_ui(self: NousComposer, work_id: int) -> None:
    """Atualiza cirurgicamente apenas os controles do card da obra e o painel de métricas."""
    updated_list = self.nous_service.list_works_ai_status()
    updated_item = next((w for w in updated_list if w["id"] == work_id), None)
    if updated_item is None:
        self._refresh_works_data()
        return

    for idx, w in enumerate(self.works_data):
        if w["id"] == work_id:
            self.works_data[idx] = updated_item
            break

    # Atualiza métricas no topo in-place
    total = len(self.works_data)
    with_ai = sum(1 for w in self.works_data if w["has_llm"] and not w["has_custom"])
    custom = sum(1 for w in self.works_data if w["has_custom"])
    pending = sum(1 for w in self.works_data if not w["has_llm"] and not w["has_custom"])
    self.stat_total.value = str(total)
    self.stat_with_ai.value = str(with_ai)
    self.stat_custom.value = str(custom)
    self.stat_pending.value = str(pending)
    if hasattr(self, "metrics_row") and self.metrics_row is not None:
        safe_update(self.metrics_row)

    # Atualiza badge do card
    badge_box = self.work_badge_containers.get(work_id)
    if badge_box is not None:
        badge_box.content = ft.Text(
            updated_item["status_label"].upper(),
            size=10 * self.scale,
            weight=ft.FontWeight.W_600,
            font_family=self.config.font_families["montserrat"],
            color=updated_item["status_color"],
        )
        badge_box.bgcolor = self.config.colors["surface"]
        badge_box.border = ft.Border.all(1, updated_item["status_color"])
        safe_update(badge_box)

    # Atualiza snippet de texto do card
    snip_box = self.work_snippet_texts.get(work_id)
    if snip_box is not None:
        has_snip = bool(updated_item["snippet"])
        snip_box.value = updated_item["snippet"] or "Sem síntese cadastrada."
        snip_box.italic = not has_snip
        snip_box.weight = ft.FontWeight.W_600 if has_snip else ft.FontWeight.W_500
        snip_box.color = self.config.colors["text"] if has_snip else self.config.colors["muted"]
        safe_update(snip_box)

    # Atualiza botões de ação do card
    act_box = self.work_actions_containers.get(work_id)
    if act_box is not None:
        act_box.content = self._build_work_actions(updated_item)
        safe_update(act_box)


def handle_search_filter(self: NousComposer, _e: ft.ControlEvent) -> None:
    """Filtra obras exibidas na lista em tempo real."""
    query = (self.search_filter.value or "").strip().lower()
    if not query:
        self._render_works_list(self.works_data)
    else:
        filtered = [
            w for w in self.works_data
            if query in w["title"].lower() or query in w["authors"].lower()
        ]
        self._render_works_list(filtered)
    self.page.update()

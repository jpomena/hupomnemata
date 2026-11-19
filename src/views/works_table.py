"""Mixin de tabela do Acervo: filtros, ordenação, seleção e linhas."""

import flet as ft

from src.domains import BibliographicResource
from src.utils.fa import fa_icon
from src.views import ui_kit as ui
from src.views.ui_kit import s
from src.views.works_common import (
    COLUMNS,
    author_names,
    format_date,
    year_sort_key,
)


class WorksTableMixin:
    """Tabela, filtros e seleção do Acervo.

    Colabora com ``WorksComposer`` via ``self``: não define ``__init__``.
    """

    def visible_rows(self) -> list[tuple[BibliographicResource, int]]:
        """Obras filtradas e ordenadas. Revistas formam banners estruturais (-1)."""
        magazines_by_id = {r.id: r for r in self.works if self._is_magazine(r)}

        # Filtra apenas obras substantivas que atendem aos filtros ativos
        matching_substantive = [
            r for r in self.works
            if not self._is_magazine(r) and self._matches(r)
        ]
        matching_substantive.sort(key=self._sort_value, reverse=self.sort_desc)

        # Agrupa artigos por revista e identifica capítulos de monografias
        magazine_articles: dict[int, list[BibliographicResource]] = {}
        standalone_roots: list[BibliographicResource] = []
        non_mag_children: dict[int, list[BibliographicResource]] = {}

        for r in matching_substantive:
            pid = self._parent_id(r)
            if pid is not None and pid in magazines_by_id:
                magazine_articles.setdefault(pid, []).append(r)
            elif pid is not None:
                non_mag_children.setdefault(pid, []).append(r)
            else:
                standalone_roots.append(r)

        # Prepara grupos de topo: obras standalone e grupos de revistas
        top_items = []
        for r in standalone_roots:
            top_items.append(("work", self._sort_value(r), r))

        for mag_id, articles in magazine_articles.items():
            mag_resource = magazines_by_id[mag_id]
            if self.sort_key == "title":
                top_sort_val = self._sort_value(mag_resource)
            else:
                top_sort_val = self._sort_value(articles[0])
            top_items.append(("magazine", top_sort_val, (mag_resource, articles)))

        top_items.sort(key=lambda it: it[1], reverse=self.sort_desc)

        ordered: list[tuple[BibliographicResource, int]] = []
        for kind, _key, data in top_items:
            if kind == "work":
                r = data
                ordered.append((r, 0))
                for child in non_mag_children.get(r.id, []):
                    ordered.append((child, 1))
            elif kind == "magazine":
                mag_res, articles = data
                ordered.append((mag_res, -1))
                if mag_res.id not in self.collapsed_magazines:
                    for art in articles:
                        ordered.append((art, 1))

        return ordered

    def _matches(self, resource) -> bool:
        work = self._get_specific_work(resource)
        if work is None:
            return False
        if self.type_filter and self._type_label(resource) != self.type_filter:
            return False
        if self.compilation_filter is not None:
            ids = [cid for cid, _ in self.context.compilations_by_work.get(resource.id, [])]
            if self.compilation_filter not in ids:
                return False
        query = self.query.strip().lower()
        if query:
            haystack = " ".join(
                str(part) for part in (
                    work.title, getattr(work, "subtitle", "") or "",
                    getattr(work, "display_year", "") or "", author_names(resource),
                    getattr(work, "journal_title", "") or "",
                )
            ).lower()
            return query in haystack
        return True

    def _sort_value(self, resource):
        work = self._get_specific_work(resource)
        key = self.sort_key
        if key == "title":
            return (work.title or "").lower()
        if key == "author":
            return author_names(resource).lower() or "~"
        if key == "type":
            return self._type_label(resource)
        if key == "year":
            return year_sort_key(getattr(work, "display_year", ""))
        if key == "frag":
            return self._fragment_count(resource)
        created = getattr(work, "created_at", None)
        return (created.isoformat() if created else "", resource.id)

    def _refresh(self) -> None:
        if self.root is None:
            return
        self.root.content = self._compose_body()
        try:
            self.root.update()
        except Exception:
            pass

    def _refresh_table_only(self, toolbar: bool = False) -> None:
        if getattr(self, "table_host", None) is None:
            return self._refresh()
        self.table_host.content = self._compose_table()
        targets: list[ft.Control] = [self.table_host]
        if toolbar and getattr(self, "toolbar_host", None) is not None:
            self.toolbar_host.content = self._compose_toolbar()
            targets.append(self.toolbar_host)
        if getattr(self, "count_text", None) is not None:
            self.count_text.value = self._count_label()
            targets.append(self.count_text)
        for control in targets:
            try:
                control.update()
            except Exception:
                pass

    def select(self, resource_id: int | None) -> None:
        self.selected_id = resource_id
        self._refresh_table_only()
        if not self._render_inspector():
            self._refresh()

    def toggle_checked(self, resource_id: int) -> None:
        if resource_id in self.checked:
            self.checked.discard(resource_id)
        else:
            self.checked.add(resource_id)
        self._refresh_table_only(toolbar=True)

    def set_sort(self, key: str) -> None:
        if self.sort_key == key:
            self.sort_desc = not self.sort_desc
        else:
            self.sort_key = key
            self.sort_desc = key in {"year", "frag", "created"}
        self._refresh_table_only(toolbar=True)

    def set_type_filter(self, value: str | None) -> None:
        self.type_filter = value
        self._refresh_table_only(toolbar=True)

    def set_compilation_filter(self, value: int | None) -> None:
        self.compilation_filter = value
        self._refresh_table_only(toolbar=True)

    def move_selection(self, step: int) -> None:
        ids = [
            r.id for r, lvl in self.visible_rows()
            if not self._is_magazine(r)
        ]
        if not ids:
            return
        if self.selected_id not in ids:
            self.select(ids[0])
            return
        index = max(0, min(len(ids) - 1, ids.index(self.selected_id) + step))
        self.select(ids[index])

    def handle_key(self, key: str, mod: bool) -> bool:
        """Atalhos da tabela: ↑/↓ navegam, espaço marca, Esc fecha/limpa."""
        if key in ("Arrow Down", "Arrow Up") and not mod:
            self.move_selection(1 if key == "Arrow Down" else -1)
            return True
        if key == "Escape":
            if self.checked:
                self.checked.clear()
            elif self.selected_id is not None:
                self.selected_id = None
            else:
                return False
            self._refresh()
            return True
        if mod and key.upper() == "C" and self.selected_id is not None:
            resource = self._work(self.selected_id)
            if resource is not None:
                self._copy_reference(resource)
            return True
        return False

    def _checkbox(self, checked: bool, on_click, partial: bool = False) -> ft.Container:
        c = self.config
        mark = None
        if checked:
            mark = fa_icon("check", size=s(9), color=c.colors["on_gold"])
        elif partial:
            mark = fa_icon("minus", size=s(9), color=c.colors["on_gold"])
        return ft.Container(
            content=mark,
            width=s(16), height=s(16),
            alignment=ft.Alignment.CENTER,
            border_radius=ft.BorderRadius.all(s(4)),
            border=ft.Border.all(1, c.colors["gold"] if (checked or partial) else c.colors["faint"]),
            bgcolor=c.colors["gold"] if (checked or partial) else c.colors["bg"],
            animate=ui.motion(ui.MOTION_FAST),
            animate_scale=ui.motion(ui.MOTION_FAST),
            on_click=on_click,
            on_hover=lambda e: self._checkbox_hover(e, checked or partial),
        )

    def _checkbox_hover(self, event, marked: bool) -> None:
        if marked:
            return
        hovering = event.data in (True, "true")
        event.control.border = ft.Border.all(1, self.config.colors["muted"] if hovering else self.config.colors["faint"])
        event.control.scale = 1.12 if hovering else 1.0
        try:
            event.control.update()
        except Exception:
            pass

    def _header_hover(self, event, text: ft.Text, active: bool) -> None:
        if active:
            return
        hovering = event.data in (True, "true")
        text.color = self.config.colors["text"] if hovering else self.config.colors["faint"]
        try:
            text.update()
        except Exception:
            pass

    def _visible_columns(self) -> list[tuple[str, str, int | None, bool]]:
        if self.selected_id is not None:
            return [col for col in COLUMNS if col[0] not in {"author", "created"}]
        return COLUMNS

    def _cell(self, key: str, width: int | None, control: ft.Control, right: bool = False) -> ft.Container:
        flex = {"title": 24, "author": 12}.get(key)
        return ft.Container(
            content=control,
            width=s(width) if width else None,
            expand=flex if width is None else None,
            alignment=ft.Alignment.CENTER_RIGHT if right else ft.Alignment.CENTER_LEFT,
            padding=ft.Padding.symmetric(horizontal=s(8)),
        )

    def _header_row(self, rows: list) -> ft.Container:
        c = self.config
        ids = [r.id for r, _ in rows if not self._is_magazine(r)]
        n_checked = len([i for i in ids if i in self.checked])
        all_checked = bool(ids) and n_checked == len(ids)

        def toggle_all(_e):
            if all_checked:
                self.checked.difference_update(ids)
            else:
                self.checked.update(ids)
            self._refresh_table_only(toolbar=True)

        cells: list[ft.Control] = [
            ft.Container(self._checkbox(all_checked, toggle_all, partial=0 < n_checked < len(ids)), width=s(64), padding=ft.Padding.only(left=s(32)), alignment=ft.Alignment.CENTER_LEFT),
        ]
        for key, label, width, right in self._visible_columns():
            active = self.sort_key == key
            label_ctrl = ui.ui_text(
                c,
                label,
                size=12,
                weight=ui.W600 if active else ui.W500,
                color=c.colors["gold"] if active else c.colors["faint"],
            )
            parts: list[ft.Control] = [label_ctrl]
            if active:
                parts.append(
                    fa_icon(
                        "arrow-down" if self.sort_desc else "arrow-up",
                        size=s(9),
                        color=c.colors["gold"],
                    )
                )
            header = ft.Container(
                ft.Row(parts, spacing=s(4), tight=True),
                on_click=lambda _e, k=key: self.set_sort(k),
                animate=ui.motion(ui.MOTION_FAST),
                on_hover=lambda e, text=label_ctrl, is_active=active: self._header_hover(e, text, is_active),
            )
            cells.append(self._cell(key, width, header, right))
        return ft.Container(
            content=ft.Row(cells, spacing=0, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            height=s(34),
            padding=ft.Padding.only(right=s(16)),
            bgcolor=c.colors["chrome"],
            border=ft.Border.only(bottom=ft.BorderSide(1, c.colors["gold"])),
        )

    def _row(self, resource, level: int) -> ft.Container:
        c = self.config
        work = self._get_specific_work(resource)
        selected = resource.id == self.selected_id
        checked = resource.id in self.checked
        count = self._fragment_count(resource)
        title_parts: list[ft.Control] = []
        if level:
            title_parts.append(ft.Container(fa_icon("turn-up", size=s(9), color=c.colors["border_strong"]), rotate=ft.Rotate(1.5708), width=s(16), margin=ft.Margin.only(left=s(4 + 12 * (level - 1)))))
        title_text = ui.serif_text(c, work.title or "", size=16.5, weight=ui.W500, color=c.colors["gold"] if selected else c.colors["text"], max_lines=1, expand=True,)
        title_text.expand_loose = True
        if work.title:
            title_text.tooltip = work.title
        title_parts.append(title_text)
        if self._work_has_pdf(resource):
            title_parts.append(
                ft.Container(
                    content=ui.badge(c, "PDF", icon_name="file-pdf", variant="gold"),
                    on_click=lambda _e, res=resource: self._open_pdf_reader(res),
                    tooltip="Abrir no Leitor de PDF",
                    ink=True,
                )
            )
        subtitle = getattr(work, "subtitle", None)
        if subtitle:
            sub_text = ui.serif_text(c, subtitle, size=14, weight=ui.W600, color=c.colors["faint"], italic=True, max_lines=1, expand=True)
            sub_text.expand_loose = True
            sub_text.tooltip = subtitle
            title_parts.append(sub_text)
        values = {
            "title": ft.Row(title_parts, spacing=s(8), vertical_alignment=ft.CrossAxisAlignment.CENTER),
            "author": ui.ui_text(c, author_names(resource) or "Sem autoria", size=13, color=c.colors["muted"]),
            "type": ui.ui_text(c, self._type_label(resource), size=13, color=c.colors["muted"]),
            "year": ui.ui_text(c, str(getattr(work, "display_year", "") or ""), size=13, color=c.colors["muted"], tabular=True),
            "frag": ui.ui_text(c, str(count), size=13, color=c.colors["muted"] if count else c.colors["faint"], tabular=True),
            "created": ui.ui_text(c, format_date(getattr(work, "created_at", None)), size=13, color=c.colors["faint"], tabular=True),
        }
        cells: list[ft.Control] = [
            ft.Container(self._checkbox(checked, lambda _e, rid=resource.id: self.toggle_checked(rid)), width=s(64), padding=ft.Padding.only(left=s(32)), alignment=ft.Alignment.CENTER_LEFT),
        ]
        for key, _label, width, right in self._visible_columns():
            cells.append(self._cell(key, width, values[key], right))
        base = ui.alpha(c.colors["gold"], 0.10) if checked else None

        def _on_hover_work(hovering: bool) -> None:
            if not selected:
                title_text.color = c.colors["gold"] if hovering else c.colors["text"]

        row = ui.hover_surface(
            c,
            ft.Row(cells, spacing=0, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            on_click=lambda _e, rid=resource.id: self.select(rid),
            selected=selected,
            height=s(40),
            radius=0,
            base=base,
            padding=ft.Padding.only(right=s(16)),
            border=ft.Border.only(bottom=ft.BorderSide(1, c.colors["border"])),
            accent_left=True,
            on_hover=_on_hover_work,
        )
        row.key = f"work-{resource.id}"
        return row

    def _compose_table(self) -> ft.Control:
        c = self.config
        rows = self.visible_rows()
        if not rows:
            message = f"Nada corresponde a “{self.query}”." if self.query.strip() else "Nenhuma obra com esses filtros."
            has_substantive = any(not self._is_magazine(r) for r in self.works)
            body: ft.Control = ft.Container(
                ui.empty_state(
                    c, "magnifying-glass", "Nenhuma obra encontrada",
                    message + " Busque pelo sobrenome do autor ou pelo ano.",
                    action=ui.button(c, "Limpar filtros", small=True, on_click=lambda _e: self._clear_filters()),
                ) if has_substantive else ui.empty_state(
                    c, "book-open", "Seu acervo está vazio",
                    "Cadastre a primeira obra para começar a registrar fragmentos.",
                    action=ui.button(c, "Nova obra", variant="primary", icon_name="plus", small=True, on_click=lambda _e: self.on_navigate("work_insert")),
                ),
                padding=s(32),
            )
        else:
            magazines_by_id = {r.id: r for r in self.works if self._is_magazine(r)}
            magazine_counts: dict[int, int] = {}
            for r in self.works:
                pid = self._parent_id(r)
                if pid is not None and pid in magazines_by_id:
                    magazine_counts[pid] = magazine_counts.get(pid, 0) + 1

            controls: list[ft.Control] = []
            for resource, level in rows:
                if level == -1 or self._is_magazine(resource):
                    child_count = magazine_counts.get(resource.id, 0)
                    controls.append(self._magazine_banner_row(resource, child_count))
                else:
                    controls.append(self._row(resource, level))

            body = ft.ListView(
                controls=controls,
                expand=True,
                spacing=0,
            )
        footer_text = (
            f"Aberta: {self._get_specific_work(self._work(self.selected_id)).title}"
            if self._work(self.selected_id) is not None and not self._is_magazine(self._work(self.selected_id))
            else "Clique numa obra para ver os detalhes"
        )
        footer = ft.Container(
            content=ft.Row(
                [
                    ui.ui_text(c, footer_text, size=12, color=c.colors["faint"], expand=True),
                    ft.Row([ui.kbd(c, "↑"), ui.kbd(c, "↓"), ui.ui_text(c, "navegar", size=12, color=c.colors["faint"])], spacing=s(4), tight=True),
                    ft.Row([ui.kbd(c, "⌘C"), ui.ui_text(c, "copiar referência", size=12, color=c.colors["faint"])], spacing=s(4), tight=True),
                ],
                spacing=s(16),
            ),
            height=s(36),
            padding=ft.Padding.symmetric(horizontal=s(32)),
            border=ft.Border.only(top=ft.BorderSide(1, c.colors["border"])),
        )
        return ft.Column([self._header_row(rows), body, footer], spacing=0, expand=True)

    def _toggle_magazine_collapse(self, magazine_id: int) -> None:
        if magazine_id in self.collapsed_magazines:
            self.collapsed_magazines.remove(magazine_id)
        else:
            self.collapsed_magazines.add(magazine_id)
        self._refresh_table_only()

    def _magazine_banner_row(
        self, resource: BibliographicResource, child_count: int
    ) -> ft.Container:
        c = self.config
        mag = self._get_specific_work(resource)
        mag_title = getattr(mag, "title", "Revista")
        mag_place = getattr(mag, "publication_place", "")

        is_collapsed = resource.id in self.collapsed_magazines
        chevron_icon = fa_icon(
            "chevron-right" if is_collapsed else "chevron-down",
            size=s(9),
            color=c.colors["gold"],
        )
        mag_icon = fa_icon("book-open-reader", size=s(12), color=c.colors["gold"])

        chevron_container = ft.Container(
            content=ft.Row(
                [
                    ft.Container(
                        content=chevron_icon,
                        width=s(32),
                        alignment=ft.Alignment.CENTER,
                    ),
                    ft.Container(
                        content=mag_icon,
                        width=s(16),
                        alignment=ft.Alignment.CENTER,
                    ),
                ],
                spacing=0,
                tight=True,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            width=s(64),
            alignment=ft.Alignment.CENTER_LEFT,
        )

        title_text = ui.serif_text(
            c, mag_title, size=16.5, weight=ui.W500, color=c.colors["text"], max_lines=1, expand=True
        )
        title_text.expand_loose = True
        title_parts: list[ft.Control] = [title_text]
        if mag_place and mag_place != "[s.l.]":
            title_parts.append(
                ui.ui_text(c, f"• {mag_place}", size=12, color=c.colors["faint"])
            )

        title_container = ft.Container(
            content=ft.Row(
                title_parts,
                spacing=s(8),
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding.symmetric(horizontal=s(8)),
            expand=True,
            alignment=ft.Alignment.CENTER_LEFT,
        )

        badge_count = ft.Container(
            content=ui.ui_text(
                c,
                f"{child_count} {'artigo' if child_count == 1 else 'artigos'}",
                size=10.5,
                weight=ui.W600,
                color=c.colors["gold"],
            ),
            bgcolor=ui.alpha(c.colors["gold"], 0.10),
            border=ft.Border.all(1, ui.alpha(c.colors["gold"], 0.25)),
            border_radius=s(4),
            padding=ft.Padding.symmetric(horizontal=s(5), vertical=s(1.5)),
        )

        actions_button = ft.PopupMenuButton(
            content=ui.icon_button(c, "ellipsis-vertical", tooltip="Opções do periódico", boxed=False, size=22),
            items=[
                ft.PopupMenuItem(
                    content=ft.Row(
                        [
                            fa_icon("pen-to-square", size=s(12), color=c.colors["faint"]),
                            ui.ui_text(c, "Editar periódico", size=13, color=c.colors["text"]),
                        ],
                        spacing=s(10),
                        tight=True,
                    ),
                    height=s(32),
                    on_click=lambda _e, r=resource: self._open_edit_magazine_dialog(r),
                ),
                ft.PopupMenuItem(
                    content=ft.Row(
                        [
                            fa_icon("trash-can", size=s(12), color=c.colors["danger"]),
                            ui.ui_text(c, "Excluir periódico e artigos", size=13, color=c.colors["danger"]),
                        ],
                        spacing=s(10),
                        tight=True,
                    ),
                    height=s(32),
                    on_click=lambda _e, r=resource, cnt=child_count: (
                        self._open_delete_magazine_dialog(r, cnt)
                    ),
                ),
            ],
            tooltip="Opções do periódico",
            bgcolor=c.colors["surface"],
            elevation=6,
            shape=ft.RoundedRectangleBorder(radius=s(8)),
            menu_position=ft.PopupMenuPosition.UNDER,
        )

        trailing_container = ft.Container(
            content=ft.Row(
                [badge_count, actions_button],
                spacing=s(4),
                tight=True,
                alignment=ft.MainAxisAlignment.END,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            width=s(104),
            padding=ft.Padding.symmetric(horizontal=s(8)),
            alignment=ft.Alignment.CENTER_RIGHT,
        )

        header_content = ft.Row(
            [
                chevron_container,
                title_container,
                trailing_container,
            ],
            spacing=0,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        return ui.hover_surface(
            c,
            header_content,
            on_click=lambda _e, mid=resource.id: self._toggle_magazine_collapse(mid),
            height=s(40),
            radius=0,
            padding=ft.Padding.only(right=s(16)),
            border=ft.Border.only(bottom=ft.BorderSide(1, c.colors["border"])),
        )

    def _open_edit_magazine_dialog(self, resource: BibliographicResource) -> None:
        c = self.config
        mag = self._get_specific_work(resource)
        if mag is None:
            return

        title_input = ft.TextField(
            label="Nome da Revista",
            value=getattr(mag, "title", ""),
            text_size=s(13),
            bgcolor=c.colors.get("surface_variant", c.colors["surface"]),
            border_color=c.colors["border"],
            focused_border_color=c.colors["gold"],
            border_radius=s(6),
            autofocus=True,
        )

        place_input = ft.TextField(
            label="Local de Publicação",
            value=getattr(mag, "publication_place", "[s.l.]"),
            text_size=s(13),
            bgcolor=c.colors.get("surface_variant", c.colors["surface"]),
            border_color=c.colors["border"],
            focused_border_color=c.colors["gold"],
            border_radius=s(6),
        )

        dialog = ft.AlertDialog(
            title=ui.serif_text(c, "Editar Periódico", size=18, weight=ui.W700),
            content=ft.Container(
                content=ft.Column(
                    [
                        ui.ui_text(
                            c,
                            "As alterações serão sincronizadas com todos os artigos vinculados.",
                            size=12,
                            color=c.colors["muted"],
                        ),
                        title_input,
                        place_input,
                    ],
                    spacing=s(12),
                    tight=True,
                ),
                width=s(440),
                padding=s(8),
            ),
            actions=[
                ui.button(
                    c,
                    "Cancelar",
                    variant="ghost",
                    on_click=lambda _e: ui.close_dialog(self.page),
                ),
                ui.button(
                    c,
                    "Salvar",
                    variant="primary",
                    icon_name="floppy-disk",
                    on_click=lambda _e: self._save_edited_magazine(
                        resource.id, title_input.value, place_input.value
                    ),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        ui.open_dialog(self.page, dialog)

    def _save_edited_magazine(
        self, resource_id: int, new_title: str, new_place: str
    ) -> None:
        ui.close_dialog(self.page)
        if self.on_update_magazine:
            self.on_update_magazine(resource_id, new_title, new_place)
        else:
            res = self._work(resource_id)
            if res and res.specific_work:
                res.specific_work.title = new_title.strip()
                res.specific_work.publication_place = new_place.strip() or "[s.l.]"
            self._refresh()
        if self.page:
            try:
                self.page.update()
            except Exception:
                pass

    def _open_delete_magazine_dialog(
        self, resource: BibliographicResource, child_count: int
    ) -> None:
        c = self.config
        mag = self._get_specific_work(resource)
        mag_title = getattr(mag, "title", "este periódico")

        def confirm(_e):
            ui.close_dialog(self.page)
            if self.on_delete_magazine:
                self.on_delete_magazine(resource)
            else:
                self.on_delete_work(resource)
            if self.page:
                try:
                    self.page.update()
                except Exception:
                    pass

        msg = (
            f"Tem certeza que deseja excluir o periódico “{mag_title}” e "
            f"TODOS os {child_count} artigos vinculados a ele em cascata?\n\n"
            "Esta ação é irreversível."
            if child_count > 0
            else f"Tem certeza que deseja excluir o periódico “{mag_title}”?"
        )

        dialog = ft.AlertDialog(
            title=ui.serif_text(
                c,
                "Excluir Periódico em Cascata",
                size=18,
                weight=ui.W700,
                color=c.colors["danger"],
            ),
            content=ui.ui_text(c, msg, size=13),
            actions=[
                ui.button(
                    c,
                    "Cancelar",
                    variant="ghost",
                    on_click=lambda _e: ui.close_dialog(self.page),
                ),
                ui.button(
                    c,
                    "Excluir Periódico",
                    variant="danger",
                    icon_name="trash-can",
                    on_click=confirm,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        ui.open_dialog(self.page, dialog)

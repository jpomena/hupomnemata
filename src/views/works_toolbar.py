"""Mixin da barra de ferramentas do Acervo: busca, filtros e ações em lote."""

import flet as ft

from src.domains import BibliographicResource
from src.utils.types import ReferencePart, ViewReference
from src.views import ui_kit as ui
from src.views.ui_kit import s
from src.views.works_common import TYPE_ICONS
from src.utils.control_safety import safe_update


class WorksToolbarMixin:
    """Busca, filtros, cópia de referências e exclusão do Acervo.

    Colabora com ``WorksComposer`` via ``self``: não define ``__init__``.
    """

    def _on_search(self, event) -> None:
        self.query = event.control.value or ""
        self._refresh_table_only()

    def _copy_reference(self, resource, button: ft.Container | None = None) -> None:
        reference = self._reference(resource)
        if reference is None or self.page is None:
            return

        async def run():
            await self.on_copy_reference(reference)

        self.page.run_task(run)
        if button is not None:
            ui.flash_button(button, "Copiada", "Copiar", self.page)

    def _copy_checked(self, button: ft.Container | None = None) -> None:
        parts: list[ReferencePart] = []
        for resource, _level in self.visible_rows():
            if resource.id not in self.checked:
                continue
            reference = self._reference(resource)
            if reference is None:
                continue
            if parts:
                parts.append(ReferencePart(content="\n\n"))
            parts.extend(reference.parts)
        if not parts or self.page is None:
            return

        async def run():
            await self.on_copy_reference(ViewReference(parts=parts))

        self.page.run_task(run)
        if button is not None:
            ui.flash_button(button, "Copiadas", "Copiar referências", self.page)

    def _confirm_delete(self, resources: list[BibliographicResource]) -> None:
        """Excluir apaga a obra e os fragmentos dela no banco: pede confirmação."""
        if not resources or self.page is None:
            return
        c = self.config
        total_fragments = sum(self._fragment_count(r) for r in resources)
        title = (
            f"Excluir “{self._get_specific_work(resources[0]).title}”?"
            if len(resources) == 1 else f"Excluir {len(resources)} obras?"
        )
        detail = "A obra sai do acervo e das compilações." if len(resources) == 1 else "As obras saem do acervo e das compilações."
        if total_fragments:
            detail += (
                f" {total_fragments} fragmento{'s' if total_fragments != 1 else ''} "
                f"também {'serão excluídos' if total_fragments != 1 else 'será excluído'}."
            )
        dialog: ft.AlertDialog | None = None

        def close(_e=None):
            ui.close_dialog(self.page)

        def confirm(_e=None):
            close()
            self.checked.difference_update(r.id for r in resources)
            if self.selected_id in {r.id for r in resources}:
                self.selected_id = None
            if self.on_delete_works is not None:
                self.on_delete_works(resources)
            else:
                for resource in resources:
                    self.on_delete_work(resource)
            if self.page:
                safe_update(self.page)

        dialog = ft.AlertDialog(
            bgcolor=c.colors["surface"],
            shape=ft.RoundedRectangleBorder(radius=s(10)),
            title=ui.ui_text(c, title, size=15, weight=ui.W600, max_lines=2),
            content=ft.Container(
                ui.ui_text(c, detail + " Essa ação não pode ser desfeita.", size=13, color=c.colors["muted"], max_lines=4),
                width=s(420),
            ),
            actions=[
                ui.button(c, "Cancelar", on_click=close, variant="ghost"),
                ui.button(
                    c,
                    "Excluir",
                    on_click=confirm,
                    variant="danger",
                    icon_name="trash-can",
                    icon_style="regular",
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        ui.open_dialog(self.page, dialog)

    def _type_menu(self) -> ft.Control:
        counts: dict[str, int] = {}
        for resource in self.works:
            if self._is_magazine(resource):
                continue
            label = self._type_label(resource)
            if label:
                counts[label] = counts.get(label, 0) + 1
        if self.type_filter:
            return ui.chip_filter(self.config, "Tipo", active_value=self.type_filter, on_clear=lambda _e: self.set_type_filter(None))
        return self._popup(
            ui.chip_filter(self.config, "Tipo"),
            "Filtrar por tipo",
            [
                (TYPE_ICONS.get(label, ("file-lines", "regular")), label, str(count), (lambda _e, v=label: self.set_type_filter(v)))
                for label, count in sorted(counts.items(), key=lambda item: -item[1])
            ],
        )

    def _compilation_menu(self) -> ft.Control:
        compilations = self.context.compilations
        if self.compilation_filter is not None:
            name = next((n for cid, n in compilations if cid == self.compilation_filter), "")
            return ui.chip_filter(self.config, "Compilação", active_value=name, on_clear=lambda _e: self.set_compilation_filter(None))
        counts = {cid: 0 for cid, _ in compilations}
        for links in self.context.compilations_by_work.values():
            for cid, _ in links:
                counts[cid] = counts.get(cid, 0) + 1
        return self._popup(
            ui.chip_filter(self.config, "Compilação"),
            "Filtrar por compilação",
            [(("folder", "regular"), name, str(counts.get(cid, 0)), (lambda _e, v=cid: self.set_compilation_filter(v))) for cid, name in compilations],
        )

    def _compose_toolbar(self) -> ft.Control:
        c = self.config
        if self.checked:
            noun = "obra selecionada" if len(self.checked) == 1 else "obras selecionadas"
            copy_button = ui.button(c, "Copiar referências", icon_name="copy", icon_style="regular", small=True)
            copy_button.on_click = lambda _e: self._copy_checked(copy_button)
            add_items = [
                (("folder", "regular"), name, None, (lambda _e, cid=cid: self._add_checked_to(cid)))
                for cid, name in self.context.compilations
            ]
            add_button = self._popup(ui.button(c, "Adicionar à compilação", icon_name="bookmark", icon_style="regular", small=True), "Escolha a compilação", add_items)
            selected = [r for r in self.works if r.id in self.checked]
            return ft.Container(
                content=ft.Row(
                    [
                        ui.ui_text(c, f"{len(self.checked)} {noun}", size=13, weight=ui.W600),
                        copy_button,
                        add_button,
                        ui.button(c, "Excluir", icon_name="trash-can", icon_style="regular", variant="danger", small=True, on_click=lambda _e: self._confirm_delete(selected)),
                        ft.Container(expand=True),
                        ft.Row([ui.button(c, "Limpar seleção", variant="ghost", small=True, on_click=lambda _e: self._clear_checked()), ui.kbd(c, "esc")], spacing=s(6), tight=True),
                    ],
                    spacing=s(8),
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                height=s(40),
                padding=ft.Padding.only(left=s(12), right=s(8)),
                margin=ft.Margin.only(left=s(32), right=s(32), bottom=s(10), top=s(2)),
                bgcolor=c.colors["surface"],
                border=ft.Border.all(1, c.colors["gold"]),
                border_radius=ft.BorderRadius.all(s(8)),
            )
        self.count_text = ui.ui_text(c, self._count_label(), size=12, color=c.colors["faint"], tabular=True)
        self.search.value = self.query
        return ui.toolbar(c, [self.search, self._type_menu(), self._compilation_menu()], trailing=[self.count_text])

    def _clear_checked(self) -> None:
        self.checked.clear()
        self._refresh_table_only(toolbar=True)

    def _add_checked_to(self, compilation_id: int) -> None:
        if self.on_add_to_compilation is None:
            return
        for resource_id in list(self.checked):
            self.on_add_to_compilation(compilation_id, resource_id)
        if self.page is not None:
            ui.toast(self.page, self.config, f"{len(self.checked)} obra(s) adicionada(s) à compilação")
        self.checked.clear()
        self._refresh_table_only(toolbar=True)

    def _add_one_to(self, compilation_id: int, resource) -> None:
        if self.on_add_to_compilation is None:
            return
        ok = self.on_add_to_compilation(compilation_id, resource.id)
        if ok:
            links = self.context.compilations_by_work.setdefault(resource.id, [])
            name = next((n for cid, n in self.context.compilations if cid == compilation_id), "")
            links.append((compilation_id, name))
            if self.page is not None:
                ui.toast(self.page, self.config, f"Obra adicionada a {name}")
            self._refresh_table_only(toolbar=True)
            self._render_inspector()

    def _clear_filters(self) -> None:
        self.query = ""
        self.type_filter = None
        self.compilation_filter = None
        self._refresh_table_only(toolbar=True)

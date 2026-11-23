"""Mixin do painel de detalhes do Acervo: referência, abas e PDF."""

import flet as ft

from src.domains import BibliographicResource
from src.utils.error_log import log_exception
from src.utils.types import TextStyle
from src.views import ui_kit as ui
from src.views.ui_kit import s
from src.views.works_common import TYPE_ICONS, author_names, format_date


class WorksInspectorMixin:
    """Painel lateral de detalhes, abas e ações de PDF.

    Colabora com ``WorksComposer`` via ``self``: não define ``__init__``.
    """

    def _details_helper(self, resource):
        from src.views.work_details_popup import WorkDetailsPopup

        return WorkDetailsPopup(
            resource=resource,
            config=self.config,
            on_close=lambda: None,
            page=self.page,
            nous_service=self.nous_service,
            on_open_pdf=lambda _rid, res=resource: self._open_pdf_reader(res),
            on_attach_pdf=lambda res: self._open_attach_pdf_picker(res),
        )

    def _reference_text(self, resource) -> ft.Control:
        c = self.config
        reference = self._reference(resource)
        if reference is None or not reference.parts:
            return ui.ui_text(c, "Este tipo ainda não tem formatador.", size=13, color=c.colors["faint"], max_lines=None)
        spans = [
            ft.TextSpan(
                part.content,
                style=ft.TextStyle(
                    weight=ft.FontWeight.W_700 if part.style == TextStyle.BOLD else None,
                    italic=part.style == TextStyle.ITALIC,
                ),
            )
            for part in reference.parts
        ]
        return ft.Text(
            spans=spans,
            size=s(13),
            color=c.colors["text"],
            font_family=c.font_families["montserrat"],
            selectable=True,
            style=ft.TextStyle(height=1.6),
        )

    def _compose_inspector(self, framed: bool = True) -> ft.Control | None:
        resource = self._work(self.selected_id)
        if resource is None or self._is_magazine(resource):
            return None
        c = self.config
        work = self._get_specific_work(resource)
        type_label = self._type_label(resource)
        icon_name, icon_style = TYPE_ICONS.get(type_label, ("file-lines", "regular"))
        fragments = self.context.fragments_by_work.get(resource.id, [])

        top = ft.Row(
            [
                ui.badge(c, type_label, icon_name=icon_name),
                ft.Container(expand=True),
                ui.icon_button(c, "chevron-up", on_click=lambda _e: self.move_selection(-1), tooltip="Obra anterior"),
                ui.icon_button(c, "chevron-down", on_click=lambda _e: self.move_selection(1), tooltip="Próxima obra"),
                ui.icon_button(c, "xmark", on_click=lambda _e: self.select(None), tooltip="Fechar (esc)"),
            ],
            spacing=s(2),
        )
        header: list[ft.Control] = [
            top,
            ft.Container(
                ui.serif_text(
                    c,
                    work.title,
                    size=24,
                    weight=ui.W600,
                    color=c.colors["text"],
                    height=1.15,
                    selectable=True,
                ),
                margin=ft.Margin.only(top=s(8)),
            ),
        ]
        if getattr(work, "subtitle", None):
            header.append(ui.ui_text(c, work.subtitle, size=13, color=c.colors["muted"], max_lines=3))
        year = getattr(work, "display_year", "") or ""
        header.append(ui.ui_text(c, " · ".join(filter(None, [author_names(resource) or "Sem autoria", str(year)])), size=13, color=c.colors["muted"], max_lines=2))
        has_pdf = self._work_has_pdf(resource)
        more_items = [
            (("copy", "regular"), "Copiar referência", "⌘C", lambda _e: self._copy_reference(resource)),
        ]
        if not has_pdf:
            more_items.append(
                (("paperclip", "solid"), "Anexar arquivo PDF", None, lambda _e, res=resource: self._open_attach_pdf_picker(res))
            )
        else:
            more_items.append(
                (("link-slash", "solid"), "Desanexar PDF / excluir arquivo", None, lambda _e, res=resource: self._confirm_detach_pdf(res))
            )
        more_items.extend([
            *[(("folder", "regular"), f"Adicionar a {name}", None, (lambda _e, cid=cid: self._add_one_to(cid, resource))) for cid, name in self.context.compilations if cid not in {x for x, _ in self.context.compilations_by_work.get(resource.id, [])}],
            (None, "", None, None),
            (("trash-can", "regular"), "Excluir obra", None, lambda _e: self._confirm_delete([resource])),
        ])
        more = self._popup(
            ui.icon_button(c, "ellipsis", boxed=True, tooltip="Mais ações"),
            None,
            more_items,
        )
        action_buttons = []
        if has_pdf:
            action_buttons.append(
                ui.button(c, "Ler PDF", icon_name="book-open", variant="primary", small=True, on_click=lambda _e, res=resource: self._open_pdf_reader(res))
            )
        else:
            action_buttons.append(
                ui.button(c, "Anexar PDF", icon_name="paperclip", variant="default", small=True, tooltip="Vincular arquivo PDF a esta obra", on_click=lambda _e, res=resource: self._open_attach_pdf_picker(res))
            )
        action_buttons.extend([
            ui.button(c, "Editar", icon_name="pen", small=True, on_click=lambda _e: self.on_edit_work(resource)),
            ui.button(c, "Ver ficha", icon_name="up-right-from-square", small=True, tooltip="Ver ficha completa", on_click=lambda _e: self.on_work_click(resource)),
            more,
        ])
        header.append(
            ft.Container(
                ft.Row(
                    action_buttons,
                    spacing=s(6),
                    wrap=True,
                    run_spacing=s(6),
                ),
                margin=ft.Margin.only(top=s(12)),
            )
        )
        tabs = ui.tabs(
            c,
            [("geral", "Visão geral", None), ("fragmentos", "Fragmentos", len(fragments))],
            self.inspector_tab,
            self._set_inspector_tab,
            padding_left=24,
        )
        body = self._inspector_fragments(fragments) if self.inspector_tab == "fragmentos" else self._inspector_overview(resource)
        inner = ft.Column(
            [
                ft.Container(ft.Column(header, spacing=s(4), tight=True), padding=ft.Padding.only(left=s(24), right=s(16), top=s(16), bottom=s(12))),
                tabs,
                ft.Container(ft.Column(body, spacing=0, scroll=ft.ScrollMode.AUTO, expand=True), expand=True),
            ],
            spacing=0,
            expand=True,
        )
        if not framed:
            return inner
        return ft.Container(
            width=s(self.config.ui.get("inspector_width", 380)),
            bgcolor=c.colors["surface"],
            border=ft.Border.only(left=ft.BorderSide(1, c.colors["border"])),
            content=inner,
        )

    def _set_inspector_tab(self, key: str) -> None:
        self.inspector_tab = key
        if not self._render_inspector():
            self._refresh()

    def _open_pdf_reader(self, resource: BibliographicResource) -> None:
        """Abre o leitor imersivo de PDF em janela dedicada independente."""
        from src.views.pdf_reader.standalone import open_pdf_standalone_window

        work = getattr(resource, "specific_work", None)
        title = (
            getattr(work, "title", None) if work else None
        ) or getattr(resource, "pdf_filename", None) or "documento"

        opened = open_pdf_standalone_window(
            resource_id=resource.id,
            page=self.page,
            config=self.config,
            work_title=title,
        )
        if not opened:
            self.on_navigate(f"pdf_reader:{resource.id}")

    def _open_attach_pdf_picker(self, resource: BibliographicResource) -> None:
        """Abre seletor de arquivos para vincular um PDF a esta obra."""
        if not self.page:
            return

        from src.services.pdf_service import PdfService
        from src.utils.file_picker import pick_file

        async def _pick():
            try:
                selected_path = await pick_file(
                    page=self.page,
                    dialog_title="Selecionar PDF para a obra",
                    allowed_extensions=["pdf"],
                )
                if selected_path:
                    svc = PdfService()
                    info = svc.attach_pdf(resource.id, selected_path)
                    resource.pdf_path = info["pdf_path"]
                    resource.pdf_filename = info["pdf_filename"]
                    resource.pdf_page_count = info["pdf_page_count"]
                    if self.page:
                        ui.toast(self.page, self.config, f"PDF anexado: {info['pdf_filename']}")
                    self._refresh()
            except Exception as err:
                log_exception("Falha ao anexar PDF via picker", err)
                if self.page:
                    ui.toast(self.page, self.config, f"Erro ao anexar PDF: {err}")

        self.page.run_task(_pick)

    def _confirm_detach_pdf(self, resource: BibliographicResource) -> None:
        """Pede confirmação para desanexar o PDF e excluir o arquivo físico do repositório local."""
        if not resource or self.page is None:
            return
        c = self.config
        work = self._get_specific_work(resource)
        work_title = getattr(work, "title", "esta obra") or "esta obra"
        title = f"Desanexar PDF de “{work_title}”?"
        detail = "O arquivo PDF será desvinculado desta obra e removido do repositório local. Fragmentos já criados serão mantidos no Acervo."

        def close(_e=None):
            ui.close_dialog(self.page)

        def confirm(_e=None):
            close()
            from src.services.pdf_service import PdfService
            try:
                svc = PdfService()
                svc.detach_pdf(resource.id, delete_file=True)
                resource.pdf_path = None
                resource.pdf_filename = None
                resource.pdf_page_count = None
                resource.pdf_page_offset = 0
                if self.page:
                    ui.toast(self.page, self.config, "PDF desanexado com sucesso.", icon_name="check")
                self._refresh()
            except Exception as err:
                log_exception("Falha ao desanexar PDF", err)
                if self.page:
                    ui.toast(self.page, self.config, f"Erro ao desanexar PDF: {err}")

        dialog = ft.AlertDialog(
            modal=True,
            title=ui.serif_text(c, title, size=18, weight=ui.W700, color=c.colors["text"]),
            content=ft.Container(
                content=ui.ui_text(c, detail, size=13, color=c.colors["muted"]),
                width=s(400),
            ),
            actions=[
                ui.button(c, "Cancelar", variant="default", small=True, on_click=close),
                ui.button(c, "Desanexar e excluir", variant="danger", small=True, on_click=confirm),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            bgcolor=c.colors["surface"],
            shape=ft.RoundedRectangleBorder(radius=s(8)),
        )
        ui.open_dialog(self.page, dialog)

    def _inspector_overview(self, resource) -> list[ft.Control]:
        c = self.config
        work = self._get_specific_work(resource)
        copy_button = ui.button(c, "Copiar", icon_name="copy", icon_style="regular", small=True)
        copy_button.on_click = lambda _e: self._copy_reference(resource, copy_button)
        reference_box = ft.Container(
            self._reference_text(resource),
            bgcolor=c.colors["bg"],
            border=ft.Border.all(1, c.colors["border"]),
            border_radius=ft.BorderRadius.all(s(6)),
            padding=ft.Padding.symmetric(horizontal=s(12), vertical=s(10)),
        )
        sections = [self._section("Referência ABNT", [reference_box], copy_button)]

        helper = self._details_helper(resource)
        rows: list[tuple[str, ft.Control | str | None]] = [("Tipo", self._type_label(resource)), ("Autoria", author_names(resource) or "Sem autoria")]
        hidden = {"title", "subtitle", "abstract", "is_partial"}
        try:
            for name, value in helper._visible_fields(work):
                if name in hidden:
                    continue
                rows.append((helper._label(name), helper._format_value(value)))
        except Exception as error:
            log_exception('Falha ao montar propriedades da obra', error)
        parent_id = self._parent_id(resource)
        parent = self._work(parent_id)
        if parent is not None:
            rows.append(("Parte de", self._link(self._get_specific_work(parent).title, lambda _e, pid=parent.id: self.select(pid))))
        children = [r for r in self.works if self._parent_id(r) == resource.id]
        if children:
            rows.append(("Partes", ft.Column([self._link(self._get_specific_work(ch).title, lambda _e, cid=ch.id: self.select(cid)) for ch in children], spacing=s(4), tight=True)))
        links = self.context.compilations_by_work.get(resource.id, [])
        rows.append((
            "Compilações",
            ft.Column([self._link(name, lambda _e, cid=cid: self.on_navigate(f"compilacao:{cid}")) for cid, name in links], spacing=s(4), tight=True)
            if links else ui.ui_text(c, "Nenhuma", size=13, color=c.colors["faint"]),
        ))
        rows.append(("Adicionada", format_date(getattr(work, "created_at", None))))
        sections.append(self._section("Propriedades", [ui.props(c, rows, label_width=132)]))

        abstract = getattr(work, "abstract", None)
        if abstract:
            sections.append(self._section("Resumo", [ui.serif_text(c, abstract, size=16, selectable=True, align=ft.TextAlign.JUSTIFY)]))
        try:
            synthesis = helper._compose_synthesis_section()
            sections.append(ft.Container(synthesis, padding=ft.Padding.symmetric(horizontal=s(24), vertical=s(16))))
        except Exception as error:
            log_exception('Falha ao compor a síntese da obra', error)
        return sections

    def _inspector_fragments(self, fragments: list[dict]) -> list[ft.Control]:
        c = self.config
        if not fragments:
            return [ft.Container(
                ui.empty_state(c, "quote-left", "Nenhum fragmento", "Registre uma citação ou um paráfrase desta obra em Fragmentos.", action=ui.button(c, "Ir para Fragmentos", small=True, on_click=lambda _e: self.on_navigate("Fragmentos"))),
                padding=s(24),
            )]
        out: list[ft.Control] = []
        for record in fragments:
            is_quote = record.get("fragment_type") == "quote"
            excerpt = str(record.get("excerpt") or "")
            text = excerpt if not is_quote or excerpt.strip()[:1] in "“\"«" else f"“{excerpt}”"
            meta = ["Citação" if is_quote else "Paráfrase"]
            if record.get("location_value"):
                meta.append(str(record["location_value"]))
            copy_button = ui.icon_button(c, "copy", style="regular", tooltip="Copiar com citação")
            copy_button.on_click = lambda _e, r=record, t=text: self._copy_fragment(r, t)
            out.append(ft.Container(
                ft.Row(
                    [
                        ft.Column(
                            [
                                ui.meta_text(c, " · ".join(meta)),
                                ui.serif_text(c, text, size=16, max_lines=4, align=ft.TextAlign.JUSTIFY) if is_quote else ui.ui_text(c, text, size=13, color=c.colors["muted"], max_lines=4, align=ft.TextAlign.JUSTIFY),
                            ],
                            spacing=s(4), expand=True, tight=True,
                        ),
                        copy_button,
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.START,
                ),
                padding=ft.Padding.only(left=s(24), right=s(12), top=s(12), bottom=s(12)),
                border=ft.Border.only(bottom=ft.BorderSide(1, c.colors["border"])),
            ))
        return out

    def _copy_fragment(self, record: dict, text: str) -> None:
        if self.page is None:
            return
        cite = f"({record.get('citation_author', '')}, {record.get('display_year', '')}"
        if record.get("location_value"):
            cite += f", {record['location_value']}"
        cite += ")"

        async def run():
            if self.on_copy_text is not None:
                await self.on_copy_text(f"{text} {cite}")
            else:
                await self.page.clipboard.set(f"{text} {cite}")

        self.page.run_task(run)
        ui.toast(self.page, self.config, "Fragmento copiado com a citação")

    def _section(self, title: str, controls: list[ft.Control], trailing: ft.Control | None = None) -> ft.Container:
        c = self.config
        head = ft.Row([ui.label_text(c, title)] + ([trailing] if trailing else []), alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER)
        return ft.Container(
            ft.Column([head, *controls], spacing=s(8), tight=True),
            padding=ft.Padding.symmetric(horizontal=s(24), vertical=s(16)),
            border=ft.Border.only(bottom=ft.BorderSide(1, c.colors["border"])),
        )

    def _link(self, label: str, on_click) -> ft.Control:
        c = self.config
        text = ft.Text(label, size=s(13), color=c.colors["text"], font_family=c.font_families["montserrat"], style=ft.TextStyle(decoration=ft.TextDecoration.UNDERLINE, decoration_color=c.colors["border_strong"]))
        return ft.Container(text, on_click=on_click)

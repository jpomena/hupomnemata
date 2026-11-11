"""Composer da tela principal da aplicacao."""

import flet as ft
from src.domains import BibliographicResource
from src.contracts import (
    AuthorReference,
    AuthorSearchResult,
    CompilationPayload,
    CompilationRecord,
    FragmentRecord,
)

from collections.abc import Awaitable, Callable
from src.views.dashboard import DashboardComposer
from src.views.works import WorksComposer
from src.views.fragments import FragmentsComposer
from src.views.compilations import CompilationsComposer
from src.views.sidebar import SidebarComposer
from src.views.settings import SettingsComposer
from src.views.knowledge import KnowledgeComposer
from src.views.nous_composer import NousComposer
from src.services.nous_service import NousAIService
from src.utils.types import ViewConfig
from src.utils.types import ViewReference
from src.views.work_insert_modal import WorkInsertModalComposer
from src.views.general_popups import MultipleAuthorsPopup
from src.views.work_details_popup import WorkDetailsPopup
from src.views.sidebar import SidebarData
from src.views import ui_kit as ui
from src.views.ui_kit import s
from src.utils.fa import fa_icon, glyph as fa_glyph


class CoreComposer:
    """Compoe a estrutura visual principal da aplicacao."""

    def __init__(
        self,
        page: ft.Page,
        scale: float,
        config: ViewConfig,
        on_navigate: Callable[[str], None],
        on_work_click: Callable,
        on_edit_work: Callable,
        on_format_reference: Callable[
            [BibliographicResource], ViewReference | None
        ],
        on_copy_reference: Callable[[ViewReference], Awaitable[None]],
        on_delete_work: Callable,
        on_create_parent_work: Callable[
            [Callable[[int, str], None]], None
        ],
        on_fragment_save: Callable[
            [int | None, dict[str, object]], bool
        ],
        on_fragment_delete: Callable[[int], None],
        search_fragment_works: Callable[[str], list[tuple[int, str]]],
        search_compilation_works: Callable[
            [str], list[tuple[int, str]]
        ],
        refresh_compilations: Callable[[], list[CompilationRecord]],
        on_compilation_create: Callable[[CompilationPayload], int | None],
        on_compilation_update: Callable[
            [int, CompilationPayload], bool
        ],
        on_compilation_delete: Callable[[int], bool],
        on_compilation_add_work: Callable[[int, int], bool],
        on_compilation_remove_work: Callable[[int, int], bool],
        on_compilation_reorder_works: Callable[[int, list[int]], bool],
        on_compilation_fragment_membership: Callable[
            [int, int, bool], bool
        ],
        on_compilation_fragment_note: Callable[
            [int, int, str | None], bool
        ],
        on_compilation_section_create: Callable[
            [int, str, str | None], int | None
        ],
        on_compilation_section_update: Callable[
            [int, int, str, str | None], bool
        ],
        on_compilation_section_delete: Callable[[int, int], bool],
        on_compilation_section_reorder: Callable[[int, list[int]], bool],
        on_compilation_fragment_assign_section: Callable[
            [int, int, int | None], bool
        ],
        on_compilation_section_reorder_fragments: Callable[
            [int, int, list[int]], bool
        ],
        on_compilation_copy_caderno: Callable[[str], Awaitable[None]],
        on_compilation_create_work: Callable[[int], None],
        on_compilation_edit_work: Callable[[int, int], None],
        on_compilation_create_fragment: Callable[[int, int], None],
        on_compilation_edit_fragment: Callable[
            [int, FragmentRecord], None
        ],
        get_knowledge_graph: Callable[..., dict] | None = None,
        sync_knowledge_mesh: Callable[[], dict] | None = None,
        get_knowledge_resonances: Callable[..., list] | None = None,
        get_knowledge_work_fragments: Callable[..., list] | None = None,
        on_create_knowledge_link: Callable[..., bool] | None = None,
        on_add_knowledge_to_compilation: Callable[[int, int], bool] | None = None,
        current_theme_mode: str = "light",
        auto_scale: bool = True,
        manual_scale: float = 1.0,
        on_change_theme: Callable[[str], None] | None = None,
        on_toggle_auto_scale: Callable[[bool], None] | None = None,
        on_change_scale: Callable[[float], None] | None = None,
        on_reset_settings: Callable[[], None] | None = None,
        on_toggle_maximize: Callable[[], None] | None = None,
        nous_service: NousAIService | None = None,
        get_sidebar_data: Callable[[], SidebarData] | None = None,
        on_history: Callable[[int], None] | None = None,
        on_toggle_theme: Callable[[], None] | None = None,
        on_new_compilation: Callable[[], None] | None = None,
        palette_search: Callable[[str], dict] | None = None,
        on_navigate_with: Callable[..., None] | None = None,
        get_acervo_context: Callable[[], object] | None = None,
        on_delete_works: Callable[[list], None] | None = None,
        get_dashboard_data: Callable[[], dict] | None = None,
        compilation_work_references: Callable[[list[int]], dict] | None = None,
        on_import_work: Callable[[], None] | None = None,
    ):
        self.page = page
        self.scale = scale
        self.config = config
        self.on_navigate = on_navigate
        self.on_work_click = on_work_click
        self.on_edit_work = on_edit_work
        self.on_format_reference = on_format_reference
        self.on_copy_reference = on_copy_reference
        self.on_delete_work = on_delete_work
        self.on_create_parent_work = on_create_parent_work
        self.on_fragment_save = on_fragment_save
        self.on_fragment_delete = on_fragment_delete
        self.search_fragment_works = search_fragment_works
        self.search_compilation_works = search_compilation_works
        self.refresh_compilations = refresh_compilations
        self.on_compilation_create = on_compilation_create
        self.on_compilation_update = on_compilation_update
        self.on_compilation_delete = on_compilation_delete
        self.on_compilation_add_work = on_compilation_add_work
        self.on_compilation_remove_work = on_compilation_remove_work
        self.on_compilation_reorder_works = on_compilation_reorder_works
        self.on_compilation_fragment_membership = (
            on_compilation_fragment_membership
        )
        self.on_compilation_fragment_note = on_compilation_fragment_note
        self.on_compilation_section_create = on_compilation_section_create
        self.on_compilation_section_update = on_compilation_section_update
        self.on_compilation_section_delete = on_compilation_section_delete
        self.on_compilation_section_reorder = on_compilation_section_reorder
        self.on_compilation_fragment_assign_section = (
            on_compilation_fragment_assign_section
        )
        self.on_compilation_section_reorder_fragments = (
            on_compilation_section_reorder_fragments
        )
        self.on_compilation_copy_caderno = on_compilation_copy_caderno
        self.on_compilation_create_work = on_compilation_create_work
        self.on_compilation_edit_work = on_compilation_edit_work
        self.on_compilation_create_fragment = (
            on_compilation_create_fragment
        )
        self.on_compilation_edit_fragment = on_compilation_edit_fragment
        self.get_knowledge_graph = get_knowledge_graph
        self.sync_knowledge_mesh = sync_knowledge_mesh
        self.get_knowledge_resonances = get_knowledge_resonances
        self.get_knowledge_work_fragments = get_knowledge_work_fragments
        self.on_create_knowledge_link = on_create_knowledge_link
        self.on_add_knowledge_to_compilation = on_add_knowledge_to_compilation
        self.knowledge_composer: KnowledgeComposer | None = None
        self.current_theme_mode = current_theme_mode
        self.auto_scale = auto_scale
        self.manual_scale = manual_scale
        self.on_change_theme = on_change_theme
        self.on_toggle_auto_scale = on_toggle_auto_scale
        self.on_change_scale = on_change_scale
        self.on_reset_settings = on_reset_settings
        self.on_toggle_maximize = on_toggle_maximize
        self.compilations_composer: CompilationsComposer | None = None
        self.nous_service = nous_service
        self.nous_composer: NousComposer | None = None
        self.get_sidebar_data = get_sidebar_data
        self.on_history = on_history
        self.on_toggle_theme = on_toggle_theme
        self.on_new_compilation = on_new_compilation
        self.palette_search = palette_search or (lambda _q: {"works": [], "fragments": []})
        self.on_navigate_with = on_navigate_with or (lambda destination, **_kw: on_navigate(destination))
        self.current_destination = "dashboard"
        self.can_go_back = False
        self.can_go_forward = False
        self.view_options: dict = {}
        self.palette = None
        self.get_acervo_context = get_acervo_context
        self.on_delete_works = on_delete_works
        self.works_composer = None
        self.get_dashboard_data = get_dashboard_data
        self.compilation_work_references = compilation_work_references
        self.on_import_work = on_import_work
        self.fragment_dialog_composer: FragmentsComposer | None = None

    # ── shell: barra de título, sidebar, breadcrumb ────────

    def _window_control_button(
        self,
        icon_name: str,
        on_click: Callable[..., object] | None,
        tooltip: str | None = None,
        danger: bool = False,
    ) -> ft.Container:
        c = self.config
        glyph = fa_icon(icon_name, size=s(12), color=c.colors["faint"], style="regular" if icon_name in {"square", "clone"} else "solid")
        box = ft.Container(
            content=glyph,
            width=s(46),
            height=s(c.ui.get("titlebar_height", 40)),
            alignment=ft.Alignment.CENTER,
            tooltip=tooltip,
            on_click=on_click,
        )

        def _hover(e):
            hovering = e.data in (True, "true")
            box.bgcolor = (c.colors["danger"] if danger else c.colors["card_hover"]) if hovering else None
            glyph.color = (c.colors["on_gold"] if danger else c.colors["text"]) if hovering else c.colors["faint"]
            box.update()

        box.on_hover = _hover
        box.data = glyph
        return box

    def _compose_custom_title_bar(self) -> ft.WindowDragArea:
        c = self.config

        def minimize_window(_):
            self.page.window.minimized = True
            self.page.update()

        def toggle_maximize_window(_):
            if self.on_toggle_maximize is not None:
                self.on_toggle_maximize()
            else:
                self.page.window.maximized = not self.page.window.maximized
                self.page.update()

        async def close_window(_):
            await self.page.window.close()

        is_maximized = bool(
            getattr(getattr(self.page, "window", None), "maximized", False)
        )
        self.maximize_button = self._window_control_button(
            "clone" if is_maximized else "square",
            toggle_maximize_window,
            "Restaurar" if is_maximized else "Maximizar",
        )
        brand_text = ft.Text(
            value=c.texts["app"]["name_normalized"],
            size=s(24),
            color=c.colors["text"],
            font_family=c.font_families["greek"],
            style=ft.TextStyle(letter_spacing=1.2),
            text_align=ft.TextAlign.CENTER,
            no_wrap=True,
        )
        brand = ft.Container(
            content=brand_text,
            width=s(c.ui["sidebar_width"]),
            alignment=ft.Alignment.CENTER,
            border=ft.Border.only(right=ft.BorderSide(1, c.colors["border"])),
            on_click=lambda _e: self.on_navigate("dashboard"),
            animate=ft.Animation(120, ft.AnimationCurve.EASE_OUT),
        )

        def _on_hover_brand(e):
            hovering = e.data in (True, "true")
            brand_text.color = c.colors["gold"] if hovering else c.colors["text"]
            try:
                brand.update()
            except Exception:
                pass

        brand.on_hover = _on_hover_brand
        self.back_button = ui.icon_button(
            c, "arrow-left", on_click=lambda _e: self.on_history(-1) if self.on_history else None,
            tooltip="Voltar (⌘[)", disabled=not self.can_go_back,
        )
        self.forward_button = ui.icon_button(
            c, "arrow-right", on_click=lambda _e: self.on_history(1) if self.on_history else None,
            tooltip="Avançar (⌘])", disabled=not self.can_go_forward,
        )
        self.history_host = ft.Container(
            ft.Row([self.back_button, self.forward_button], spacing=s(2), tight=True),
            padding=ft.Padding.only(left=s(12), right=s(8)),
        )
        self.crumbs_host = ft.Row(self._crumb_controls(), spacing=s(2), expand=True, tight=True)
        controls = ft.Row(
            [
                self._window_control_button("minus", minimize_window, "Minimizar"),
                self.maximize_button,
                self._window_control_button("xmark", close_window, "Fechar", danger=True),
            ],
            spacing=0,
            tight=True,
        )
        return ft.WindowDragArea(
            content=ft.Container(
                content=ft.Row(
                    [brand, self.history_host, self.crumbs_host, controls],
                    spacing=0,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                bgcolor=c.colors["chrome"],
                border=ft.Border.only(bottom=ft.BorderSide(1, c.colors["border"])),
                height=s(c.ui.get("titlebar_height", 40)),
            )
        )

    def _crumb_parts(self) -> list[tuple[str, str | None]]:
        dest = self.current_destination
        labels = {"dashboard": "Início"}
        if dest.startswith("compilacao:"):
            name = self.compilation_name(int(dest.split(":", 1)[1])) or "Compilação"
            return [("Compilações", "Compilações"), (name, None)]
        return [(labels.get(dest, dest), None)]

    def _crumb_controls(self) -> list[ft.Control]:
        c = self.config
        parts = self._crumb_parts()
        out: list[ft.Control] = []
        for index, (label, target) in enumerate(parts):
            last = index == len(parts) - 1
            text = ui.ui_text(c, label, size=13, weight=ui.W500, color=c.colors["text"] if last else c.colors["faint"])
            if target and not last:
                out.append(ui.hover_surface(c, text, on_click=lambda _e, t=target: self.on_navigate(t), padding=ft.Padding.symmetric(horizontal=s(6), vertical=s(3)), radius=4))
                out.append(fa_icon("chevron-right", size=s(9), color=c.colors["faint"]))
            else:
                out.append(ft.Container(text, padding=ft.Padding.symmetric(horizontal=s(6))))
        return out

    def compilation_name(self, compilation_id: int) -> str | None:
        data = self.get_sidebar_data() if self.get_sidebar_data else SidebarData()
        return next((name for cid, name in data.compilations if cid == compilation_id), None)

    def _compose_sidebar(self) -> ft.Container:
        return SidebarComposer(
            scale=self.scale,
            config=self.config,
            on_navigate=self.on_navigate,
            current=self.current_destination,
            data=self.get_sidebar_data() if self.get_sidebar_data else SidebarData(),
            on_search=self.open_palette,
            on_new_work=lambda: self.on_navigate("work_insert"),
            on_new_compilation=self.on_new_compilation,
            on_toggle_theme=self.on_toggle_theme,
        ).compose()

    def set_history_state(self, can_back: bool, can_forward: bool) -> None:
        self.can_go_back = can_back
        self.can_go_forward = can_forward
        host = getattr(self, "history_host", None)
        if host is None:
            return
        self.back_button = ui.icon_button(self.config, "arrow-left", on_click=lambda _e: self.on_history(-1) if self.on_history else None, tooltip="Voltar (⌘[)", disabled=not can_back)
        self.forward_button = ui.icon_button(self.config, "arrow-right", on_click=lambda _e: self.on_history(1) if self.on_history else None, tooltip="Avançar (⌘])", disabled=not can_forward)
        host.content = ft.Row([self.back_button, self.forward_button], spacing=s(2), tight=True)
        try:
            host.update()
        except Exception:
            pass

    def refresh_chrome(self) -> None:
        """Atualiza sidebar e breadcrumb depois de uma navegação."""
        if getattr(self, "sidebar_host", None) is not None:
            self.sidebar_host.content = self._compose_sidebar()
        if getattr(self, "crumbs_host", None) is not None:
            self.crumbs_host.controls = self._crumb_controls()
        for control in (getattr(self, "sidebar_host", None), getattr(self, "crumbs_host", None)):
            try:
                if control is not None:
                    control.update()
            except Exception:
                pass

    def update_window_state(self, is_maximized: bool) -> None:
        """Atualiza o ícone do botão de maximizar/restaurar sem recriar a UI."""
        button = getattr(self, "maximize_button", None)
        if button is None:
            return
        glyph = button.data
        if glyph is not None:
            char, family = fa_glyph("clone" if is_maximized else "square", "regular")
            glyph.value = char
            glyph.font_family = family
        button.tooltip = "Restaurar" if is_maximized else "Maximizar"
        try:
            button.update()
        except Exception:
            pass

    def compose_main(self) -> ft.Column:
        """Monta barra de título, barra lateral e área de conteúdo."""
        ui.set_scale(self.scale)
        self.content = ft.Container(
            content=self._compose_dashboard(),
            expand=True,
            bgcolor=self.config.colors["bg"],
        )
        self.sidebar_host = ft.Container(content=self._compose_sidebar())
        return ft.Column(
            controls=[
                self._compose_custom_title_bar(),
                ft.Row(
                    controls=[self.sidebar_host, self.content],
                    expand=True,
                    spacing=0,
                    vertical_alignment=ft.CrossAxisAlignment.STRETCH,
                ),
            ],
            expand=True,
            spacing=0,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )

    def show_view(
        self,
        destination: str,
        works: list[BibliographicResource] | None = None,
        fragments: list[FragmentRecord] | None = None,
        compilations: list[CompilationRecord] | None = None,
        **options,
    ) -> None:
        self.view_options = options
        views = {
            "dashboard": self._compose_dashboard,
            "Acervo": lambda: self._compose_works(works),
            "Fragmentos": lambda: self._compose_fragments(fragments),
            "Compilações": lambda: self._compose_compilations(compilations),
            "Estruturas de Saber": self._compose_knowledge,
            "Nous": self._compose_nous,
            "Configurações": self._compose_settings,
        }
        if destination.startswith("compilacao:"):
            compilation_id = int(destination.split(":", 1)[1])
            view_factory = lambda: self._compose_compilation_page(compilations, compilation_id)
        else:
            view_factory = views.get(destination)
        if not view_factory:
            if destination not in self.config.core_menus:
                return
            self.current_destination = destination
            self.content.content = self._compose_placeholder_dashboard(
                destination
            )
        else:
            self.current_destination = destination
            self.content.content = view_factory()
        try:
            self.content.update()
        except (RuntimeError, AttributeError):
            pass
        self.refresh_chrome()

    def _compose_compilation_page(
        self,
        compilations: list[CompilationRecord] | None,
        compilation_id: int,
    ) -> ft.Control:
        """Página de uma compilação; se ela não existe mais, cai na lista."""
        control = self._compose_compilations(compilations)
        if self.compilations_composer is not None:
            return self.compilations_composer.open_compilation_page(compilation_id) or control
        return control

    # ── paleta ⌘K ──────────────────────────────────────────

    def open_palette(self) -> None:
        if self.page is None:
            return
        from src.views.command_palette import CommandPalette

        self.palette = CommandPalette(
            page=self.page,
            config=self.config,
            search=self.palette_search,
            on_open_work=lambda work_id: self.on_navigate_with("Acervo", focus_work_id=work_id),
            on_open_fragments=lambda query: self.on_navigate_with("Fragmentos", query=query),
            actions=[
                ("plus", "Inserir nova obra", "⌘N", lambda: self.on_navigate("work_insert")),
                ("file-import", "Importar obra (DOI, ISBN, ISSN)", "⌘I", lambda: self.on_import_work() if self.on_import_work else None),
                ("circle-half-stroke", "Alternar tema", None, lambda: self.on_toggle_theme() if self.on_toggle_theme else None),
                ("book", "Ir para Acervo", None, lambda: self.on_navigate("Acervo")),
                ("quote-left", "Ir para Fragmentos", None, lambda: self.on_navigate("Fragmentos")),
                ("folder-open", "Ir para Compilações", None, lambda: self.on_navigate("Compilações")),
            ],
        )
        self.palette.open()

    def handle_palette_key(self, key: str) -> bool:
        palette = getattr(self, "palette", None)
        if palette is None or not palette.is_open:
            return False
        return palette.handle_key(key)

    def _compose_dashboard(self) -> ft.Control:
        return DashboardComposer(
            scale=self.scale,
            config=self.config,
            on_navigate=self.on_navigate,
            get_dashboard_data=getattr(self, "get_dashboard_data", None),
            on_navigate_with=getattr(self, "on_navigate_with", None),
            on_new_fragment=self.open_fragment_create,
            on_open_palette=self.open_palette,
            on_import_work=getattr(self, "on_import_work", None),
        ).compose()

    def open_fragment_create(self) -> None:
        """Abre o diálogo de novo fragmento sem sair da tela atual."""
        self.fragment_dialog_composer = FragmentsComposer(
            page=self.page,
            config=self.config,
            fragments=[],
            search_works=self.search_fragment_works,
            on_save=self.on_fragment_save,
            on_delete=self.on_fragment_delete,
            on_copy_reference=self.on_copy_reference,
        )
        self.fragment_dialog_composer.open_create()

    def _fragment_compilations(self) -> dict[int, list[str]]:
        """Nomes das compilações em que cada fragmento entrou (selo na linha)."""
        names: dict[int, list[str]] = {}
        refresh = getattr(self, "refresh_compilations", None)
        if refresh is None:
            return names
        try:
            compilations = refresh() or []
        except Exception:
            return names
        for compilation in compilations:
            for work in compilation.get("works", []):
                for fragment in work.get("fragments", []):
                    if fragment.get("is_member"):
                        names.setdefault(fragment["id"], []).append(compilation["name"])
        return names

    def _compose_placeholder_dashboard(self, section: str) -> ft.Control:
        return DashboardComposer(
            scale=self.scale,
            config=self.config,
            on_navigate=self.on_navigate,
        ).compose_placeholder(section)

    def _compose_settings(self) -> ft.Control:
        return SettingsComposer(
            scale=self.scale,
            config=self.config,
            current_theme_mode=self.current_theme_mode,
            auto_scale=self.auto_scale,
            manual_scale=self.manual_scale,
            effective_scale=self.scale,
            on_navigate=self.on_navigate,
            on_change_theme=self.on_change_theme or (lambda _: None),
            on_toggle_auto_scale=self.on_toggle_auto_scale or (lambda _: None),
            on_change_scale=self.on_change_scale or (lambda _: None),
            on_reset_settings=self.on_reset_settings or (lambda: None),
        ).compose()

    def _compose_nous(self) -> ft.Control:
        self.nous_composer = NousComposer(
            page=getattr(self, "page", None),
            config=self.config,
            scale=self.scale,
            on_navigate=self.on_navigate,
            nous_service=getattr(self, "nous_service", None),
            current_theme_mode=getattr(self, "current_theme_mode", "light"),
        )
        return self.nous_composer.compose()

    def _compose_knowledge(self) -> ft.Control:
        self.knowledge_composer = KnowledgeComposer(
            page=getattr(self, "page", None),
            config=self.config,
            scale=self.scale,
            on_navigate=self.on_navigate,
            get_graph_data=getattr(self, "get_knowledge_graph", None) or (lambda _: {"nodes": [], "links": [], "clusters": []}),
            sync_mesh=getattr(self, "sync_knowledge_mesh", None) or (lambda: {"vectorized": 0, "clusters": 0}),
            get_resonances=getattr(self, "get_knowledge_resonances", None) or (lambda *_: []),
            get_work_fragments=getattr(self, "get_knowledge_work_fragments", None) or (lambda _: []),
            on_add_to_compilation=getattr(self, "on_add_knowledge_to_compilation", None),
            list_compilations=getattr(self, "refresh_compilations", None),
            on_create_link=getattr(self, "on_create_knowledge_link", None),
            current_theme_mode=getattr(self, "current_theme_mode", "light"),
        )
        return self.knowledge_composer.compose()

    def _compose_works(
        self,
        works: list[BibliographicResource] | None,
    ) -> ft.Control:
        options = getattr(self, "view_options", {}) or {}
        context = self.get_acervo_context() if getattr(self, "get_acervo_context", None) else None
        self.works_composer = WorksComposer(
            scale=self.scale,
            config=self.config,
            works=works or [],
            on_navigate=self.on_navigate,
            on_work_click=self.on_work_click,
            on_edit_work=self.on_edit_work,
            format_reference=self.on_format_reference,
            on_copy_reference=self.on_copy_reference,
            on_delete_work=self.on_delete_work,
            page=self.page,
            context=context,
            focus_work_id=options.get("focus_work_id"),
            type_filter=options.get("type_filter"),
            sort_key=options.get("sort_key"),
            sort_desc=options.get("sort_desc"),
            on_add_to_compilation=self.on_compilation_add_work,
            on_delete_works=getattr(self, "on_delete_works", None),
            nous_service=getattr(self, "nous_service", None),
            on_import_work=getattr(self, "on_import_work", None),
        )
        return self.works_composer.compose()

    def handle_view_key(self, key: str, mod: bool) -> bool:
        """Repassa atalhos de teclado para a tela ativa (ex.: tabela do Acervo)."""
        if self.current_destination == "Acervo" and getattr(self, "works_composer", None) is not None:
            return self.works_composer.handle_key(key, mod)
        return False

    def _compose_fragments(
        self,
        fragments: list[FragmentRecord] | None,
    ) -> ft.Control:
        options = getattr(self, "view_options", {}) or {}
        on_navigate_with = getattr(self, "on_navigate_with", None)
        composer = FragmentsComposer(
            page=self.page,
            config=self.config,
            fragments=fragments or [],
            search_works=self.search_fragment_works,
            on_save=self.on_fragment_save,
            on_delete=self.on_fragment_delete,
            on_copy_reference=self.on_copy_reference,
            compilations_by_fragment=self._fragment_compilations(),
            on_open_work=(
                (lambda work_id: on_navigate_with("Acervo", focus_work_id=work_id))
                if on_navigate_with is not None
                else None
            ),
            initial_query=str(options.get("query") or ""),
        )
        control = composer.compose()
        if options.get("create"):
            composer.open_create()
        return control

    def _compose_compilations(
        self,
        compilations: list[CompilationRecord] | None,
    ) -> ft.Control:
        self.compilations_composer = CompilationsComposer(
            page=self.page,
            config=self.config,
            compilations=compilations or [],
            search_works=self.search_compilation_works,
            refresh_compilations=self.refresh_compilations,
            on_create=self.on_compilation_create,
            on_update=self.on_compilation_update,
            on_delete=self.on_compilation_delete,
            on_add_work=self.on_compilation_add_work,
            on_remove_work=self.on_compilation_remove_work,
            on_reorder_works=self.on_compilation_reorder_works,
            on_fragment_membership=(
                self.on_compilation_fragment_membership
            ),
            on_fragment_note=self.on_compilation_fragment_note,
            on_create_section=self.on_compilation_section_create,
            on_update_section=self.on_compilation_section_update,
            on_delete_section=self.on_compilation_section_delete,
            on_reorder_sections=self.on_compilation_section_reorder,
            on_assign_fragment_to_section=(
                self.on_compilation_fragment_assign_section
            ),
            on_reorder_section_fragments=(
                self.on_compilation_section_reorder_fragments
            ),
            on_copy_caderno=self.on_compilation_copy_caderno,
            on_create_work=self.on_compilation_create_work,
            on_edit_work=self.on_compilation_edit_work,
            on_create_fragment=self.on_compilation_create_fragment,
            on_edit_fragment=self.on_compilation_edit_fragment,
            on_navigate=self.on_navigate,
            on_open_work=lambda work_id: self.on_navigate_with("Acervo", focus_work_id=work_id),
            on_chrome_changed=self.refresh_chrome,
            work_references=getattr(self, "compilation_work_references", None),
        )
        return self.compilations_composer.compose(
            open_create=bool(self.view_options.get("create"))
        )

    def refresh_compilation_hub(self, compilation_id: int) -> None:
        if self.compilations_composer is not None:
            self.compilations_composer.refresh_compilation_hub(
                compilation_id
            )

    @staticmethod
    def compose_work_details_popup(
        resource,
        config: ViewConfig,
        on_close: Callable[[], None],
        page: ft.Page | None = None,
        nous_service: object | None = None,
    ) -> ft.AlertDialog:
        return WorkDetailsPopup(
            resource=resource,
            config=config,
            on_close=on_close,
            page=page,
            nous_service=nous_service,
        ).compose()

    @staticmethod
    def compose_work_insert_modal(
        page: ft.Page,
        config: ViewConfig,
        on_save: Callable[[dict[str, object]], bool],
        search_authors: (
            Callable[[str], list[AuthorSearchResult]] | None
        ) = None,
        search_works: (
            Callable[[str, str | None], list[tuple[int, str]]] | None
        ) = None,
        on_create_parent_work: Callable[
            [Callable[[int, str], None], str | None], None
        ] | None = None,
        initial_work_type: str | None = None,
        parent_mode: bool = False,
        edit_mode: bool = False,
        initial_values: dict[str, object] | None = None,
        initial_author_references: list[AuthorReference] | None = None,
        initial_parent_work_id: int | None = None,
        initial_parent_work_title: str = "",
        on_navigate_to_work: Callable[[int], None] | None = None,
    ) -> ft.AlertDialog:
        return WorkInsertModalComposer(
            page=page,
            config=config,
            on_save=on_save,
            search_authors=search_authors,
            search_works=search_works,
            on_create_parent_work=on_create_parent_work,
            initial_work_type=initial_work_type,
            parent_mode=parent_mode,
            edit_mode=edit_mode,
            initial_values=initial_values,
            initial_author_references=initial_author_references,
            initial_parent_work_id=initial_parent_work_id,
            initial_parent_work_title=initial_parent_work_title,
            on_navigate_to_work=on_navigate_to_work,
        ).compose()

    @staticmethod
    def compose_multiple_authors_modal(
        authors,
        on_select: Callable[[int], None],
        on_create_new: Callable[[], None],
        on_cancel: Callable[[], None],
        config: ViewConfig
    ) -> ft.AlertDialog:
        return MultipleAuthorsPopup().compose(
            authors=authors,
            on_select=on_select,
            on_create_new=on_create_new,
            on_cancel=on_cancel,
            config=config
        )

"""PdfFragmentsMixin extraído de ``reader_view.py``.

Movimentação literal: sem ``__init__``, colabora com ``PdfReaderView``
via ``self``.
"""

import flet as ft

from src.domains import Fragment
from src.utils.clipboard import get_system_clipboard_text
from src.utils.error_log import log_exception
from src.views import ui_kit as ui

s = ui.s


class PdfFragmentsMixin:
    """Fragmentos e anotações vinculados ao documento aberto."""

    def _handle_new_fragment_click(self, _e: ft.ControlEvent | None = None) -> None:
        """Abre modal interno para criação de fragmento a partir do texto selecionado."""
        if self.is_modal_open:
            return
        snippet = (self.selected_text or getattr(self.page_text_field, 'value', '') or '').strip()
        if not snippet:
            clip = get_system_clipboard_text().strip()
            if clip and (clip in self.current_page_text or (hasattr(self, 'doc') and clip in (self.current_page_text or ''))):
                snippet = clip

        target_page = self.selected_page if snippet else self.current_page
        self._open_fragment_modal(initial_excerpt=snippet, page_number=target_page)

    def _open_fragment_modal(self, initial_excerpt: str = '', page_number: int | None = None) -> None:
        """Abre modal unificado para criação de novo fragmento sem sair do leitor."""
        if not self.page or self.is_modal_open:
            return

        loc_page = page_number or self.current_page
        work_page = self.get_work_page(loc_page)
        self.fragment_modal.page = self.page
        self.fragment_modal.open_create_for_work(
            bib_res_id=self.resource.id,
            title=self.work_title,
            initial_location_type='Página',
            initial_location_value=str(work_page),
            initial_excerpt=initial_excerpt,
            on_saved=self._on_fragment_saved,
        )

    def _handle_fragment_card_click(self, item: Fragment) -> None:
        """Navega para a página do fragmento e abre o modal padrão de edição."""
        if self.is_modal_open:
            return
        if item.location_value:
            self._jump_to_fragment_page(item.location_value)
        self._open_edit_fragment_modal(item)

    def _open_edit_fragment_modal(self, item: Fragment) -> None:
        """Abre o modal unificado de fragmento em modo de edição para o fragmento selecionado."""
        if not self.page or self.is_modal_open:
            return

        self.fragment_modal.page = self.page
        record = {
            'id': item.id,
            'fragment_type': item.fragment_type or 'quote',
            'bib_res_id': self.resource.id,
            'work_title': self.work_title,
            'citation_author': '',
            'display_year': '',
            'excerpt': item.excerpt or '',
            'location_type': item.location_type or None,
            'location_value': item.location_value or '',
        }
        self.fragment_modal.open_edit(record, on_saved=self._on_fragment_saved)

    def _on_fragment_saved(self) -> None:
        """Callback executado após salvar o fragmento no modal."""
        self._refresh_fragments_list()
        if self.page:
            ui.toast(self.page, self.config, 'Fragmento salvo com sucesso!', icon_name='check')

    def _save_fragment_from_modal(self, editing_id: int | None, payload: dict[str, object]) -> bool:
        """Persiste o fragmento gerado no modal diretamente no banco de dados."""
        from src.services.fragment_service import FragmentService

        text_val = (str(payload.get('excerpt') or '')).strip()
        if not text_val:
            if self.page:
                ui.toast(self.page, self.config, 'O conteúdo do fragmento não pode ser vazio.')
            return False

        kind = payload.get('fragment_type') or 'quote'
        loc_val = (str(payload.get('location_value') or '')).strip()
        if kind == 'quote' and not loc_val:
            if self.page:
                ui.toast(self.page, self.config, 'Citações exigem o valor da localização.')
            return False

        try:
            svc = FragmentService()
            if editing_id is not None:
                svc.update(editing_id, payload)
            else:
                svc.create(payload)
            return True
        except Exception as err:
            log_exception('Falha ao salvar fragmento via leitor de PDF', err)
            if self.page:
                ui.toast(self.page, self.config, f'Erro ao salvar fragmento: {err}')
            return False

    def _refresh_fragments_list(self) -> None:
        """Atualiza a lista lateral com os fragmentos já cadastrados da obra."""
        c = self.config
        colors = c.colors

        from src.db.db import SessionLocal

        with SessionLocal() as session:
            fragments = (
                session.query(Fragment)
                .filter(Fragment.bib_res_id == self.resource.id)
                .all()
            )
            frag_list = [
                Fragment(
                    id=f.id,
                    fragment_type=f.fragment_type,
                    excerpt=f.excerpt,
                    location_type=f.location_type,
                    location_value=f.location_value,
                )
                for f in fragments
            ]

        if not frag_list:
            self.fragments_column.controls = [
                ui.empty_state(
                    c,
                    'quote-left',
                    'Nenhum fragmento',
                    'Crie citações e paráfrases a partir das páginas deste PDF.',
                )
            ]
        else:
            cards = []
            for item in frag_list:
                loc_txt = ''
                if item.location_type and item.location_value:
                    loc_txt = f'{item.location_type} {item.location_value}'
                elif item.location_value:
                    loc_txt = f'p. {item.location_value}'

                cards.append(
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Row(
                                    controls=[
                                        ui.badge(
                                            c,
                                            'Citação' if item.fragment_type == 'quote' else 'Paráfrase',
                                            accent=(item.fragment_type == 'quote'),
                                        ),
                                        ui.ui_text(c, loc_txt, size=11, color=colors['muted']),
                                    ],
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                ),
                                ui.ui_text(
                                    c,
                                    f'“{item.excerpt}”' if item.fragment_type == 'quote' else item.excerpt,
                                    size=12,
                                    max_lines=3,
                                    color=colors['text'],
                                    align=ft.TextAlign.JUSTIFY,
                                ),
                            ],
                            spacing=s(6),
                            tight=True,
                        ),
                        bgcolor=colors['bg'],
                        border=ft.Border.all(1, colors['border']),
                        border_radius=ft.BorderRadius.all(s(6)),
                        padding=s(10),
                        ink=True,
                        tooltip='Clique para editar este fragmento',
                        on_click=lambda _e, f=item: self._handle_fragment_card_click(f),
                    )
                )
            self.fragments_column.controls = cards

        try:
            self.sidebar_container.update()
        except (RuntimeError, AttributeError):
            pass

    def _jump_to_fragment_page(self, loc_val: str | None) -> None:
        """Navega para a página apontada pelo fragmento considerando a sincronia de offset."""
        if not loc_val:
            return
        import re
        match = re.search(r'\d+', str(loc_val))
        if match:
            target_work_page = int(match.group(0))
            pdf_page = target_work_page - self.page_offset
            if 1 <= pdf_page <= self.total_pages:
                self.current_page = pdf_page
                self._load_current_page()
            elif 1 <= target_work_page <= self.total_pages:
                self.current_page = target_work_page
                self._load_current_page()

    def _handle_annotate_click(self, _e: ft.ControlEvent | None = None) -> None:
        """Registra nota rápida sobre a página atual."""
        if not self.page:
            return
        ui.toast(self.page, self.config, f'Anotação registrada na página {self.current_page}.')

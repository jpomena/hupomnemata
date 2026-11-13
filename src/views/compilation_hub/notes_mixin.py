"""Notas de articulação: o texto que liga um fragmento à ideia do projeto."""

import flet as ft

from src.contracts import CompilationFragmentRecord
from src.utils.fragment_reference import fragment_abnt_notation
from src.views import ui_kit as ui
from src.views.ui_kit import s
from .common import dialog, form_field, text_input


class CompilationHubNotesMixin:
    """Rodapé do bloco de fragmento e diálogo de edição da nota."""

    def _save_fragment_note(self, fragment_id: int, note: str | None) -> None:
        if self.on_fragment_note(
            self.compilation['id'],
            fragment_id,
            note.strip() if isinstance(note, str) and note.strip() else None,
        ):
            self.refresh()

    def _prompt_fragment_note(self, fragment: CompilationFragmentRecord) -> ft.AlertDialog:
        c = self.config
        work_title = self._work_title_of(fragment)
        kind = 'Citação' if fragment['fragment_type'] == 'quote' else 'Paráfrase'
        subtitle = ' · '.join(part for part in (kind, work_title, fragment_abnt_notation(fragment)) if part)
        note_field = text_input(
            c,
            value=fragment.get('work_note') or '',
            hint='Por que este trecho importa para a ideia ou para o projeto?',
            multiline=True,
            min_lines=3,
            max_lines=8,
            max_length=2000,
            autofocus=True,
        )
        excerpt = ft.Container(
            content=ui.serif_text(c, fragment.get('excerpt', ''), size=16, max_lines=5, color=c.colors['muted'], align=ft.TextAlign.JUSTIFY),
            padding=ft.Padding.symmetric(horizontal=s(12), vertical=s(10)),
            bgcolor=c.colors['bg'],
            border=ft.Border.all(1, c.colors['border']),
            border_radius=ft.BorderRadius.all(s(6)),
        )

        def save(_event=None) -> None:
            value = note_field.value
            clean = value.strip() if isinstance(value, str) and value.strip() else None
            self.page.pop_dialog()
            self._save_fragment_note(fragment['id'], clean)

        def delete(_event=None) -> None:
            self.page.pop_dialog()
            self._save_fragment_note(fragment['id'], None)

        actions: list[ft.Control] = []
        if fragment.get('work_note'):
            actions.append(ui.button(c, 'Excluir nota', on_click=delete, variant='danger', icon_name='trash-can', icon_style='regular'))
        actions.extend([
            ui.button(c, 'Cancelar', on_click=lambda _e: self.page.pop_dialog(), variant='ghost'),
            ui.button(c, 'Salvar nota', on_click=save, variant='primary'),
        ])
        modal = dialog(
            c,
            'Nota de articulação',
            [excerpt, form_field(c, 'Nota', note_field, hint='A nota vale só nesta compilação. O fragmento continua igual no Acervo.')],
            actions,
            width=560,
            subtitle=subtitle,
        )
        modal.data = {'note': note_field, 'save': save, 'delete': delete if fragment.get('work_note') else None}
        self.page.show_dialog(modal)
        return modal

    def _compose_fragment_note(self, fragment: CompilationFragmentRecord) -> ft.Container:
        """Rodapé do bloco: texto da nota (ou “Sem nota de articulação”) e o botão."""
        c = self.config
        note = fragment.get('work_note')
        text = ui.ui_text(
            c,
            note or 'Sem nota de articulação',
            size=12,
            color=c.colors['muted'] if note else c.colors['faint'],
            max_lines=None,
            expand=True,
            selectable=bool(note),
            align=ft.TextAlign.JUSTIFY if note else None,
        )
        action = ui.button(
            c,
            'Editar nota' if note else 'Adicionar nota',
            on_click=lambda _e, current=fragment: self._prompt_fragment_note(current),
            icon_name='note-sticky',
            icon_style='regular',
            variant='ghost',
            small=True,
            tooltip='Nota de articulação: o texto que liga este fragmento à ideia',
        )
        return ft.Container(
            content=ft.Row([text, action], spacing=s(8), vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.Padding.only(left=s(16), right=s(6), top=s(4), bottom=s(4)),
            border=ft.Border.only(top=ft.BorderSide(1, c.colors['border'])),
            data='note',
        )

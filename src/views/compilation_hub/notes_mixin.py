"""Mixin para notas de articulação no hub de compilações."""

from collections.abc import Callable
import flet as ft

from src.contracts import CompilationFragmentRecord
from src.utils.view_styles import button_text_style, text_field_style
from .common import EventControl


class CompilationHubNotesMixin:
    """Responsável pela gestão e apresentação de notas de articulação dos fragmentos."""

    def _save_fragment_note(
        self,
        fragment_id: int,
        note: str | None,
    ) -> None:
        if self.on_fragment_note(
            self.compilation['id'],
            fragment_id,
            note.strip() if isinstance(note, str) else None,
        ):
            self.refresh()

    def _toggle_fragment_note_expansion(
        self,
        fragment_id: int,
    ) -> None:
        if fragment_id in self.expanded_note_fragment_ids:
            self.expanded_note_fragment_ids.remove(fragment_id)
        else:
            self.expanded_note_fragment_ids.add(fragment_id)
        self.dialog.content = self._compose_content()
        self.page.update()

    def _prompt_fragment_note(
        self,
        fragment: CompilationFragmentRecord,
    ) -> None:
        work_title = ''
        for work in self.compilation.get('works', []):
            if any(
                f['id'] == fragment['id']
                for f in work.get('fragments', [])
            ):
                work_title = work.get('title') or ''
                break

        fragment_type = (
            'Citação' if fragment['fragment_type'] == 'quote' else 'Comentário'
        )
        location = ', '.join(
            part
            for part in (
                fragment.get('location_type'),
                fragment.get('location_value'),
            )
            if part
        )
        subtitle_parts = [fragment_type]
        if work_title:
            subtitle_parts.append(work_title)
        context_subtitle = ' — '.join(subtitle_parts)
        if location:
            context_subtitle += f' ({location})'

        note_field = ft.TextField(
            label='Nota de articulação (opcional)',
            hint_text='Por que este trecho importa para a ideia ou projeto?',
            value=fragment.get('work_note') or '',
            multiline=True,
            min_lines=3,
            max_lines=8,
            max_length=2000,
            expand=True,
            **text_field_style(self.config),
        )

        def save(event: ft.Event[ft.Button]) -> None:
            del event
            val = note_field.value
            clean_val = (
                val.strip() if isinstance(val, str) and val.strip() else None
            )
            self.page.pop_dialog()
            self._save_fragment_note(fragment['id'], clean_val)
            if clean_val:
                self.expanded_note_fragment_ids.add(fragment['id'])
            else:
                self.expanded_note_fragment_ids.discard(fragment['id'])

        def delete(event: ft.Event[ft.Button]) -> None:
            del event
            self.page.pop_dialog()
            self._save_fragment_note(fragment['id'], None)
            self.expanded_note_fragment_ids.discard(fragment['id'])

        actions: list[ft.Control] = []
        if fragment.get('work_note'):
            actions.append(
                ft.TextButton(
                    content=ft.Text(
                        'Excluir nota',
                        color=self.config.colors.get('danger', '#E05D52'),
                        font_family=self.config.font_families['montserrat'],
                        size=self.config.font_sizes['montserrat_medium'],
                        weight=self.config.font_weights['montserrat_normal'],
                    ),
                    style=ft.ButtonStyle(
                        text_style=button_text_style(self.config),
                    ),
                    on_click=delete,
                )
            )

        actions.extend([
            ft.TextButton(
                content=ft.Text(
                    'Cancelar',
                    color=self.config.colors['text'],
                    font_family=self.config.font_families['montserrat'],
                    size=self.config.font_sizes['montserrat_medium'],
                    weight=self.config.font_weights['montserrat_normal'],
                ),
                style=ft.ButtonStyle(
                    text_style=button_text_style(self.config),
                ),
                on_click=lambda: self.page.pop_dialog(),
            ),
            ft.FilledButton(
                content=ft.Text(
                    'Salvar nota',
                    color=self.config.colors['bg'],
                    font_family=self.config.font_families['montserrat'],
                    size=self.config.font_sizes['montserrat_medium'],
                    weight=self.config.font_weights['montserrat_normal'],
                ),
                bgcolor=self.config.colors['gold'],
                style=ft.ButtonStyle(
                    text_style=button_text_style(self.config),
                ),
                on_click=save,
            ),
        ])

        dialog = ft.AlertDialog(
            modal=True,
            bgcolor=self.config.colors['surface'],
            title=ft.Text(
                value='Nota de articulação',
                color=self.config.colors['gold'],
                font_family=self.config.font_families['cormorant'],
                size=self.config.font_sizes['cormorant_medium'],
                weight=self.config.font_weights['cormorant_semibold'],
            ),
            content=ft.Column(
                controls=[
                    ft.Text(
                        value=context_subtitle,
                        color=self.config.colors['muted'],
                        font_family=self.config.font_families['montserrat'],
                        size=self.config.font_sizes['montserrat_small'],
                    ),
                    ft.Container(
                        bgcolor=self.config.colors['bg'],
                        padding=ft.Padding.all(10),
                        border_radius=self.config.ui['card_radius'],
                        border=ft.Border.all(
                            1,
                            self.config.colors['border'],
                        ),
                        content=ft.Text(
                            value=f'"{fragment.get("excerpt", "")}"',
                            color=self.config.colors['text'],
                            font_family=self.config.font_families[
                                'montserrat'
                            ],
                            size=self.config.font_sizes['montserrat_small'],
                            italic=True,
                            max_lines=5,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                    ),
                    note_field,
                ],
                tight=True,
                width=560,
                spacing=self.config.ui['control_gap'],
            ),
            actions=actions,
            actions_alignment=ft.MainAxisAlignment.END,
            shape=ft.RoundedRectangleBorder(
                radius=self.config.ui['card_radius']
            ),
            content_padding=self.config.ui['modal_content_padding'],
        )
        self.page.show_dialog(dialog)

    def _compose_fragment_note(
        self,
        fragment: CompilationFragmentRecord,
    ) -> ft.Control:
        note = fragment.get('work_note')
        fragment_id = fragment['id']
        is_expanded = fragment_id in self.expanded_note_fragment_ids

        if not note:
            return ft.Row(
                controls=[
                    ft.TextButton(
                        content=ft.Row(
                            controls=[
                                ft.Icon(
                                    ft.Icons.NOTE_ADD_OUTLINED,
                                    size=16,
                                    color=self.config.colors['gold'],
                                ),
                                ft.Text(
                                    'Nota de articulação',
                                    color=self.config.colors['gold'],
                                    font_family=self.config.font_families[
                                        'montserrat'
                                    ],
                                    size=self.config.font_sizes[
                                        'montserrat_small'
                                    ],
                                    weight=self.config.font_weights[
                                        'montserrat_semibold'
                                    ],
                                ),
                            ],
                            spacing=6,
                            tight=True,
                        ),
                        tooltip=(
                            'Adicionar nota de articulação para '
                            'esta compilação'
                        ),
                        on_click=lambda event, current=fragment: (
                            self._run_click_action(
                                event,
                                lambda: self._prompt_fragment_note(current),
                            )
                        ),
                    )
                ],
                tight=True,
            )

        header_controls: list[ft.Control] = [
            ft.Row(
                controls=[
                    ft.Icon(
                        ft.Icons.STICKY_NOTE_2_OUTLINED,
                        size=16,
                        color=self.config.colors['gold'],
                    ),
                    ft.Text(
                        'Nota de articulação',
                        color=self.config.colors['gold'],
                        font_family=self.config.font_families['montserrat'],
                        size=self.config.font_sizes['montserrat_small'],
                        weight=self.config.font_weights['montserrat_semibold'],
                    ),
                    ft.IconButton(
                        icon=(
                            ft.Icons.EXPAND_LESS
                            if is_expanded
                            else ft.Icons.EXPAND_MORE
                        ),
                        icon_size=18,
                        icon_color=self.config.colors['muted'],
                        tooltip=(
                            'Recolher nota'
                            if is_expanded
                            else 'Expandir nota'
                        ),
                        on_click=lambda event, fid=fragment_id: (
                            self._run_click_action(
                                event,
                                lambda: self._toggle_fragment_note_expansion(
                                    fid
                                ),
                            )
                        ),
                    ),
                ],
                spacing=4,
                tight=True,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            ft.IconButton(
                icon=ft.Icons.EDIT_OUTLINED,
                icon_size=16,
                icon_color=self.config.colors['muted'],
                tooltip='Editar nota de articulação',
                on_click=lambda event, current=fragment: (
                    self._run_click_action(
                        event,
                        lambda: self._prompt_fragment_note(current),
                    )
                ),
            ),
        ]

        card_content: list[ft.Control] = [
            ft.Row(
                controls=header_controls,
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
        ]

        if is_expanded:
            card_content.append(
                ft.Container(
                    padding=ft.Padding.only(top=4, left=4, right=4, bottom=4),
                    content=ft.Text(
                        value=note,
                        color=self.config.colors['text'],
                        font_family=self.config.font_families['montserrat'],
                        size=self.config.font_sizes['montserrat_medium'],
                        selectable=True,
                    ),
                )
            )

        return ft.Container(
            content=ft.Column(
                controls=card_content,
                tight=True,
                spacing=2,
            ),
            bgcolor=self.config.colors['bg'],
            border=ft.Border.all(1, self.config.colors['border']),
            border_radius=self.config.ui['card_radius'],
            padding=ft.Padding.symmetric(horizontal=10, vertical=6),
            margin=ft.Padding.only(top=4, bottom=4),
        )

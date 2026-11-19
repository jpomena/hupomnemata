"""Aba Caderno de trabalho: roteiro, escrita e lateral de referências.

A implementação foi fatiada em cinco mixins; esta fachada preserva o nome
histórico e mantém ``_copy_references`` no módulo para o monkeypatch dos
testes sobre ``copy_references``.
"""

import flet as ft

from src.utils.clipboard import copy_references
from src.utils.reference_disambiguation import (
    build_disambiguated_view_references,
    reference_plain_text,
)
from src.views import ui_kit as ui
from .caderno_actions import CadernoActionsMixin
from .caderno_common import QUEUE_KEY, kind_label, quoted  # noqa: F401
from .caderno_data import CadernoDataMixin
from .caderno_outline import CadernoOutlineMixin
from .caderno_prompts import CadernoPromptsMixin
from .caderno_writing import CadernoWritingMixin


class CompilationHubCadernoMixin(
    CadernoDataMixin,
    CadernoActionsMixin,
    CadernoPromptsMixin,
    CadernoOutlineMixin,
    CadernoWritingMixin,
):
    """Ideias (seções), ordem dos fragmentos e o texto do esqueleto."""

    async def _copy_references(self, event=None) -> None:
        del event
        is_caderno = getattr(self, 'selected_tab', 'caderno') == 'caderno'
        works = self._used_works() if is_caderno else self.compilation['works']
        if not works:
            return
        references = self._work_references([work['id'] for work in works])
        disambiguated = build_disambiguated_view_references(works, references)
        disambiguated.sort(key=lambda ref: reference_plain_text(ref).casefold())
        text = '\n'.join(reference_plain_text(ref) for ref in disambiguated)

        copied = copy_references(disambiguated)
        if not copied or not isinstance(self.page, ft.Page):
            try:
                if hasattr(self.page, 'clipboard') and self.page.clipboard:
                    await self.page.clipboard.set(text)
            except Exception:
                if not copied:
                    return
        ui.toast(self.page, self.config, 'Referências copiadas.', icon_name='book-bookmark')

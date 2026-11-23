"""Componentes visuais compartilhados do redesign (v2).

Fachada pública do pacote; preserva exatamente a API de ``src.views.ui_kit``.
"""

from collections.abc import Callable, Sequence

import flet as ft

from src.utils.control_safety import safe_execute, safe_update
from src.utils.fa import fa_icon
from src.utils.types import ViewConfig

from ._foundation import (
    UI_TRACKING,
    W400,
    W500,
    W600,
    W700,
    alpha,
    s,
    set_scale,
)
from ._motion import (
    MOTION_BASE,
    MOTION_FAST,
    MOTION_INSTANT,
    MOTION_SLOW,
    fade,
    motion,
)
from ._typography import icon, label_text, meta_text, serif_text, ui_text
from ._buttons import button, flash_button, icon_button, link_button
from ._layout import (
    badge,
    card,
    card_head,
    chip_filter,
    divider,
    empty_state,
    hover_surface,
    interactive_card,
    kbd,
    page_header,
    props,
    search_field,
    segmented,
    tabs,
    toolbar,
)
from ._forms import (
    checkbox,
    dropdown_field,
    field_label,
    form_field,
    input_field,
    set_field_error,
)
from ._dialogs import close_dialog, dialog, modal, open_dialog, toast

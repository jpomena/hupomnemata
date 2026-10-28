"""Handlers e Mixins de coordenação para o CoreController."""

from .window_handler import WindowControllerMixin
from .work_handler import WorkControllerMixin
from .fragment_handler import FragmentControllerMixin
from .compilation_handler import CompilationControllerMixin
from .knowledge_handler import KnowledgeControllerMixin
from .nous_handler import NousControllerMixin

__all__ = [
    "WindowControllerMixin",
    "WorkControllerMixin",
    "FragmentControllerMixin",
    "CompilationControllerMixin",
    "KnowledgeControllerMixin",
    "NousControllerMixin",
]

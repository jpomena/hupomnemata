"""Pacote do Hub de Compilações.

Reexporta a classe CompilationHubComposer mantendo compatibilidade total de importação.
"""

from .common import _control_list
from .hub_composer import CompilationHubComposer

__all__ = ["CompilationHubComposer", "_control_list"]

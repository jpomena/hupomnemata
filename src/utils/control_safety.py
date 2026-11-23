"""Operações de interface tolerantes a controles desacoplados.

A camada de views frequentemente atualiza controles que já saíram da árvore
(modal fechado, aba trocada, página em teardown). O Flet levanta exceção nesses
casos; engolir o erro em silêncio esconde falhas reais. Estes utilitários
preservam a tolerância, mas registram o evento em nível de depuração.
"""

import logging
from typing import Any, Callable

logger = logging.getLogger('hupomnemata.ui')


def set_control_prop(control: Any, name: str, value: Any) -> None:
    """Define uma propriedade e mantém o controle vivo no modelo imperativo.

    O Flet 0.86 congela subárvores reutilizadas em alguns fluxos de eventos.
    Restaurar ``_frozen`` após a mutação faz o próximo ``page.update()``
    congelar também os filhos recém-adicionados, quebrando hovers e outros
    handlers. Portanto o marcador é removido permanentemente apenas no
    controle que a aplicação decidiu continuar mutando.
    """
    if hasattr(control, '_frozen'):
        object.__delattr__(control, '_frozen')
    setattr(control, name, value)


def safe_update(
    control: Any,
    *,
    context: str = '',
    exceptions: tuple[type[BaseException], ...] = (Exception,),
) -> bool:
    """Atualiza um controle, ignorando falhas de ciclo de vida.

    Retorna ``True`` quando a atualização foi aceita pelo Flet. Controles
    desacoplados (``page is None``) e páginas já fechadas retornam ``False``
    sem propagar exceção. ``exceptions`` preserva o escopo original de captura
    quando o chamador não deseja mascarar erros alheios ao ciclo de vida.
    """
    if control is None:
        return False
    try:
        control.update()
        return True
    except exceptions as error:
        suffix = f' [{context}]' if context else ''
        logger.debug('Atualização de controle ignorada%s: %s', suffix, error)
        return False


def safe_execute(context: str, callback: Callable[..., Any], *args: Any, **kwargs: Any) -> bool:
    """Executa uma ação de UI, registrando falhas esperadas em depuração."""
    try:
        callback(*args, **kwargs)
        return True
    except Exception as error:  # noqa: BLE001 - fronteira de UI
        logger.debug('Ação de interface ignorada [%s]: %s', context, error)
        return False

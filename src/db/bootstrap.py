"""Bootstrap do ambiente de dados do usuário.

Executado uma única vez no início da aplicação (janela principal e leitor de
PDF). Garante o diretório de dados, os backups e a adoção do banco legado
antes de qualquer conexão SQLAlchemy.
"""

import logging
from typing import Any

from src.configs.paths import ensure_user_environment

logger = logging.getLogger('hupomnemata.bootstrap')


def bootstrap_user_environment() -> dict[str, Any]:
    """Prepara diretórios e migra o banco legado quando necessário."""
    result = ensure_user_environment()
    if result.get('migrated'):
        logger.info(
            'Banco legado adotado: %s -> %s (original preservado).',
            result.get('source'),
            result.get('target'),
        )
    return result

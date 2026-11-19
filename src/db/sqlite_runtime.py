"""Runtime de conexão SQLite: PRAGMAs canônicos por conexão.

Centraliza a criação de engines para que **toda** conexão (aplicação, Alembic,
testes e subprocesso do leitor de PDF) declare as mesmas garantias:

- ``foreign_keys=ON``   — torna efetivos os ``ON DELETE CASCADE/SET NULL``;
- ``busy_timeout``      — espera configurada em vez de falha imediata;
- ``journal_mode=WAL``  — leitores concorrentes com um escritor (arquivos);
- ``synchronous=NORMAL`` — durabilidade adequada ao WAL.

Bancos em memória não recebem ``WAL`` (o journal não existe nesse modo), mas
mantêm FK e timeout. Volumes que não suportam WAL (rede/antivírus) degradam
para ``journal_mode=DELETE`` com aviso, em vez de impedir a abertura do app.
"""

import logging
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine

BUSY_TIMEOUT_MS = 10_000

logger = logging.getLogger('hupomnemata.sqlite')


def _is_file_backed(engine: Engine) -> bool:
    database = engine.url.database
    return bool(database) and database != ':memory:'


def apply_connection_pragmas(
    dbapi_connection: Any,
    file_backed: bool,
) -> None:
    """Aplica os PRAGMAs canônicos a uma conexão DBAPI recém-aberta."""
    cursor = dbapi_connection.cursor()
    try:
        # O timeout vem antes de qualquer tentativa de lock (WAL incluso).
        cursor.execute(f'PRAGMA busy_timeout={BUSY_TIMEOUT_MS}')
        cursor.execute('PRAGMA foreign_keys=ON')
        if file_backed:
            row = cursor.execute('PRAGMA journal_mode=WAL').fetchone()
            mode = str(row[0]).lower() if row else ''
            if mode != 'wal':
                # Volume sem suporte a WAL: seguimos com o journal clássico.
                logger.warning(
                    'WAL indisponível (journal_mode=%s); usando DELETE. '
                    'Concorrência entre processos ficará limitada.', mode
                )
                cursor.execute('PRAGMA journal_mode=DELETE')
        cursor.execute('PRAGMA synchronous=NORMAL')
    finally:
        cursor.close()


def attach_sqlite_pragmas(engine: Engine) -> Engine:
    """Registra o listener de PRAGMAs na engine e devolve a própria engine."""
    file_backed = _is_file_backed(engine)

    @event.listens_for(engine, 'connect')
    def _on_connect(dbapi_connection, _connection_record):  # noqa: ANN001
        apply_connection_pragmas(dbapi_connection, file_backed)

    return engine


def create_sqlite_engine(url: str | Path, **kwargs: Any) -> Engine:
    """Cria uma engine SQLite já instrumentada com os PRAGMAs canônicos.

    Aceita uma URL SQLAlchemy (``sqlite:///...``, ``sqlite://``) ou um
    ``Path`` para arquivo. Argumentos extras (``poolclass``, ``connect_args``)
    seguem para ``sqlalchemy.create_engine``.
    """
    if isinstance(url, Path):
        url = f'sqlite:///{url.as_posix()}'
    engine = create_engine(url, **kwargs)
    return attach_sqlite_pragmas(engine)

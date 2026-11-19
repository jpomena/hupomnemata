"""Auditoria e reparo conservador de integridade referencial do SQLite.

Quando ``PRAGMA foreign_keys=ON`` passa a valer, bancos legados podem conter
órfãos criados durante o período em que as FK estavam inertes. Esta rotina:

1. executa ``PRAGMA foreign_key_check``;
2. se houver violações, produz um snapshot consistente (``VACUUM INTO``) e um
   arquivo de quarentena com os **registros completos** (JSONL);
3. repara segundo a ação declarada na FK (``ON DELETE SET NULL`` → NULL;
   demais → remoção auditada da linha filha);
4. revalida e aborta se restar qualquer violação.

O reparo nunca é silencioso: todas as decisões ficam registradas no manifesto
retornado e no log da aplicação.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.engine import Engine

from src.utils.error_log import log_exception


def _quote_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _foreign_key_actions(connection, table: str) -> dict[int, tuple[str, str]]:
    """Mapeia ``fkid`` → (coluna local, ação ON DELETE) para uma tabela."""
    rows = connection.exec_driver_sql(
        f'PRAGMA foreign_key_list({_quote_identifier(table)})'
    ).fetchall()
    # colunas: id, seq, table, from, to, on_update, on_delete, match
    return {row[0]: (row[3], (row[6] or 'NO ACTION').upper()) for row in rows}


def find_foreign_key_violations(engine: Engine) -> list[tuple]:
    """Executa o preflight e devolve as linhas de ``PRAGMA foreign_key_check``."""
    with engine.connect() as connection:
        return list(
            connection.exec_driver_sql('PRAGMA foreign_key_check').fetchall()
        )


def _snapshot_database(engine: Engine, backup_dir: Path) -> Path | None:
    """Produz snapshot autocontido via ``VACUUM INTO`` (seguro com WAL)."""
    if not engine.url.database or engine.url.database == ':memory:':
        return None
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    target = backup_dir / f'hupomnemata_pre_fk_repair_{stamp}.db'
    raw = engine.raw_connection()
    try:
        raw.execute('VACUUM INTO ?', (str(target),))
    finally:
        raw.close()
    return target


def _quarantine_violations(
    connection,
    violations: list[tuple],
    quarantine_path: Path,
) -> int:
    """Grava os registros completos das linhas violadoras em JSONL."""
    written = 0
    with quarantine_path.open('w', encoding='utf-8') as handle:
        for table, rowid, parent_table, fkid in violations:
            try:
                cursor = connection.exec_driver_sql(
                    f'SELECT * FROM {_quote_identifier(table)} '
                    'WHERE rowid = ?',
                    (rowid,),
                )
                row = cursor.fetchone()
                if row is None:
                    continue
                payload = {
                    'table': table,
                    'rowid': rowid,
                    'missing_parent_table': parent_table,
                    'fk_index': fkid,
                    'row': dict(zip(cursor.keys(), row)),
                    'quarantined_at': datetime.now(timezone.utc).isoformat(),
                }
                handle.write(json.dumps(payload, ensure_ascii=False) + '\n')
                written += 1
            except Exception as error:  # noqa: BLE001
                log_exception(
                    f'Falha ao quarentenar linha órfã de {table}',
                    error,
                )
    return written


def _repair_violations(connection, violations: list[tuple]) -> dict[str, int]:
    """Aplica a política de reparo por FK e devolve contagem por ação."""
    actions: dict[str, int] = {}
    cache: dict[str, dict[int, tuple[str, str]]] = {}

    for table, rowid, _parent_table, fkid in violations:
        if table not in cache:
            cache[table] = _foreign_key_actions(connection, table)
        column, on_delete = cache[table].get(fkid, ('', 'NO ACTION'))
        if not column:
            actions['unknown'] = actions.get('unknown', 0) + 1
            continue

        if on_delete == 'SET NULL':
            connection.exec_driver_sql(
                f'UPDATE {_quote_identifier(table)} '
                f'SET {_quote_identifier(column)} = NULL WHERE rowid = ?',
                (rowid,),
            )
            key = 'set_null'
        else:
            connection.exec_driver_sql(
                f'DELETE FROM {_quote_identifier(table)} WHERE rowid = ?',
                (rowid,),
            )
            key = 'deleted'
        actions[key] = actions.get(key, 0) + 1
    return actions


def _purge_orphan_knowledge_rows(connection) -> dict[str, int]:
    """Remove apenas dados derivados polimórficos órfãos (embeddings/itens)."""
    purged: dict[str, int] = {}
    for table in ('knowledge_embeddings', 'knowledge_cluster_items'):
        for entity_type, parent in (
            ('work', 'bibliographic_resources'),
            ('fragment', 'fragments'),
        ):
            result = connection.exec_driver_sql(
                f'DELETE FROM {table} WHERE entity_type = ? AND entity_id '
                f'NOT IN (SELECT id FROM {parent})',
                (entity_type,),
            )
            if result.rowcount:
                key = f'{table}:{entity_type}'
                purged[key] = result.rowcount
    return purged


def ensure_referential_integrity(
    engine: Engine,
    backup_dir: Path,
) -> dict[str, Any]:
    """Executa preflight, quarentena e reparo; aborta se algo permanecer."""
    violations = find_foreign_key_violations(engine)
    summary: dict[str, Any] = {
        'violations': len(violations),
        'backup': None,
        'quarantine': None,
        'repaired': {},
        'purged_derived': {},
    }
    if not violations:
        with engine.begin() as connection:
            summary['purged_derived'] = _purge_orphan_knowledge_rows(connection)
        return summary

    summary['backup'] = str(_snapshot_database(engine, backup_dir) or '')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    quarantine_path = backup_dir / f'fk_quarantine_{stamp}.jsonl'
    backup_dir.mkdir(parents=True, exist_ok=True)

    with engine.begin() as connection:
        summary['quarantine'] = str(quarantine_path)
        summary['quarantined_rows'] = _quarantine_violations(
            connection, violations, quarantine_path
        )
        summary['repaired'] = _repair_violations(connection, violations)
        summary['purged_derived'] = _purge_orphan_knowledge_rows(connection)

    remaining = find_foreign_key_violations(engine)
    if remaining:
        raise RuntimeError(
            'Integridade referencial não foi restabelecida: '
            f'{len(remaining)} violação(ões) remanescente(s). '
            f'Quarentena em {quarantine_path}.'
        )
    return summary

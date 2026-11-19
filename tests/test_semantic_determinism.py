"""Determinismo do motor semântico e invalidação versionada de embeddings.

O defeito original: ``hash()`` de ``str`` é randomizado por processo, então
vetores persistidos deixavam de ser comparáveis após reiniciar a aplicação.
Estes testes exigem determinismo **entre processos** (PYTHONHASHSEED distintos)
e que a versão do motor invalide vetores antigos automaticamente.
"""

import hashlib
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from src.db import db as db_module
from src.domains import BibliographicResource, EditorialMonograph, Fragment
from src.domains.knowledge import KnowledgeEmbedding
from src.repositories.knowledge_repository import (
    KnowledgeRepository,
    compute_text_hash,
)
from src.services.semantic_engine import StatisticalTFIDFEngine

REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_TEXT = 'fenomenologia da percepção e hermenêutica do sujeito'


def _vector_digest_for_seed(seed: str) -> str:
    code = (
        'import hashlib;'
        'from src.services.semantic_engine import StatisticalTFIDFEngine;'
        f'vec = StatisticalTFIDFEngine().encode({SAMPLE_TEXT!r});'
        'print(hashlib.sha256(vec.tobytes()).hexdigest())'
    )
    env = {**os.environ, 'PYTHONHASHSEED': seed}
    result = subprocess.run(
        [sys.executable, '-c', code],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def test_vectors_are_identical_across_python_hash_seeds():
    digests = {_vector_digest_for_seed(seed) for seed in ('1', '2', '12345')}
    assert len(digests) == 1, f'Vetores divergiram entre processos: {digests}'


def test_text_hash_is_bound_to_engine_version():
    from src.utils.embedding_contract import EMBEDDING_ENGINE_VERSION

    plain_sha = hashlib.sha256(SAMPLE_TEXT.encode('utf-8')).hexdigest()
    canonical = compute_text_hash(SAMPLE_TEXT)
    assert canonical != plain_sha
    assert canonical == hashlib.sha256(
        f'{EMBEDDING_ENGINE_VERSION}\x1f{SAMPLE_TEXT}'.encode('utf-8')
    ).hexdigest()


def test_embedding_with_legacy_hash_is_recomputed(clean_db):
    with db_module.SessionLocal() as session:
        resource = BibliographicResource(
            editorial_monograph=EditorialMonograph(title='Obra Legada')
        )
        resource.fragments.append(
            Fragment(
                excerpt='Excerto antigo',
                fragment_type='quote',
                created_at=datetime.now(),
            )
        )
        session.add(resource)
        session.commit()
        fragment_id = resource.fragments[0].id

        repository = KnowledgeRepository(session)
        repository.save_embedding(
            entity_type='fragment',
            entity_id=fragment_id,
            # Hash produzido pela geração anterior, sem a versão do motor.
            text_hash=hashlib.sha256(b'Excerto antigo').hexdigest(),
            vector_bytes=b'\x00' * 4 * StatisticalTFIDFEngine.DIMENSION,
        )
        pending = repository.get_unvectorized_fragments()

    assert [fragment.id for fragment in pending] == [fragment_id]


def test_embedding_with_current_hash_is_not_recomputed(clean_db):
    with db_module.SessionLocal() as session:
        resource = BibliographicResource(
            editorial_monograph=EditorialMonograph(title='Obra Atual')
        )
        resource.fragments.append(
            Fragment(
                excerpt='Excerto atual',
                fragment_type='quote',
                created_at=datetime.now(),
            )
        )
        session.add(resource)
        session.commit()
        fragment_id = resource.fragments[0].id

        repository = KnowledgeRepository(session)
        repository.save_embedding(
            entity_type='fragment',
            entity_id=fragment_id,
            text_hash=compute_text_hash('Excerto atual'),
            vector_bytes=b'\x00' * 4 * StatisticalTFIDFEngine.DIMENSION,
        )
        pending = repository.get_unvectorized_fragments()

    assert pending == []


def test_sync_pending_embeddings_rewrites_legacy_vector(clean_db):
    from src.services.knowledge_service import KnowledgeService

    with db_module.SessionLocal() as session:
        resource = BibliographicResource(
            editorial_monograph=EditorialMonograph(title='Obra Reindexável')
        )
        resource.fragments.append(
            Fragment(
                excerpt='Excerto que precisa ser reindexado',
                fragment_type='quote',
                created_at=datetime.now(),
            )
        )
        session.add(resource)
        session.commit()
        fragment_id = resource.fragments[0].id
        session.add(
            KnowledgeEmbedding(
                entity_type='fragment',
                entity_id=fragment_id,
                text_hash='hash-da-geracao-antiga',
                vector=b'\x00' * 4 * StatisticalTFIDFEngine.DIMENSION,
            )
        )
        session.commit()

    vectorized = KnowledgeService().sync_pending_embeddings()
    assert vectorized >= 1

    with db_module.SessionLocal() as session:
        embedding = session.query(KnowledgeEmbedding).filter_by(
            entity_type='fragment', entity_id=fragment_id
        ).one()
        assert embedding.text_hash == compute_text_hash(
            'Excerto que precisa ser reindexado'
        )
        assert embedding.vector != b'\x00' * 4 * StatisticalTFIDFEngine.DIMENSION

    # Segunda passada não reindexa nada.
    assert KnowledgeService().sync_pending_embeddings() == 0

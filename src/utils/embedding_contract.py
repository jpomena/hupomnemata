"""Contrato canônico de versionamento dos embeddings.

A versão identifica a função de vetorização (algoritmo e parâmetros) usada para
gerar os bytes persistidos em ``knowledge_embeddings``. Vetores gerados por
versões distintas **não são comparáveis entre si**; a versão é incorporada ao
hash de texto (``compute_text_hash``), de modo que qualquer mudança de motor
invalida automaticamente os vetores antigos, forçando a re-vetorização
incremental no próximo ``sync_pending_embeddings``.

Histórico:
- ``tfidf-hash-v1``  — legacy: usava ``hash()`` de ``str`` (não determinístico
  entre processos por causa da randomização de PYTHONHASHSEED).
- ``tfidf-blake2b-v2`` — determinístico: BLAKE2b de 8 bytes por token.
"""

import hashlib

EMBEDDING_ENGINE_VERSION = "tfidf-blake2b-v2"


def deterministic_token_hash(token: str) -> int:
    """Deriva um inteiro estável para o token, independente do processo.

    ``hash()`` de ``str`` é randomizado por processo (PYTHONHASHSEED); usar o
    digest BLAKE2b garante que o mesmo texto produza sempre o mesmo bucket.
    """
    digest = hashlib.blake2b(token.encode('utf-8'), digest_size=8).digest()
    return int.from_bytes(digest, 'little', signed=False)

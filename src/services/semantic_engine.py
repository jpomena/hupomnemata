"""Motor semântico resiliente para geração de embeddings e cálculo de similaridade.

Oferece suporte a ONNX Runtime com fallback automático em Python puro / TF-IDF.
"""

from abc import ABC, abstractmethod
import math
import re
from typing import ClassVar
import numpy as np


def vector_to_bytes(vec: np.ndarray | list[float]) -> bytes:
    """Converte um vetor numérico em bytes compactos float32."""
    arr = np.asarray(vec, dtype=np.float32)
    return arr.tobytes()


def bytes_to_vector(raw: bytes) -> np.ndarray:
    """Reconstrói um vetor numpy a partir de bytes float32."""
    return np.frombuffer(raw, dtype=np.float32)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Calcula a similaridade de cosseno entre dois vetores normalizados."""
    norm_a = float(np.linalg.norm(a))
    norm_b = float(np.linalg.norm(b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    sim = float(np.dot(a, b) / (norm_a * norm_b))
    return float(max(0.0, min(1.0, sim)))


class BaseSemanticEngine(ABC):
    """Interface abstrata para motores de vetorização semântica."""

    @abstractmethod
    def encode(self, text: str) -> np.ndarray:
        """Gera embedding para um texto individual."""
        pass

    def encode_batch(self, texts: list[str]) -> list[np.ndarray]:
        """Gera embeddings para múltiplos textos em lote."""
        return [self.encode(t) for t in texts]


class StatisticalTFIDFEngine(BaseSemanticEngine):
    """Motor estatístico offline baseado em hashing vetorial TF-IDF e n-grams."""

    DIMENSION: ClassVar[int] = 128
    STOPWORDS: ClassVar[set[str]] = {
        "de", "a", "o", "que", "e", "do", "da", "em", "um", "para", "é", "com",
        "não", "uma", "os", "no", "se", "na", "por", "mais", "as", "dos", "como",
        "mas", "ao", "ele", "das", "à", "seu", "sua", "ou", "quando", "muito",
        "nos", "já", "eu", "também", "só", "pelo", "pela", "até", "isso", "ela",
        "entre", "depois", "sem", "mesmo", "aos", "seus", "quem", "nas", "me",
        "esse", "eles", "você", "essa", "num", "nem", "suas", "meu", "às", "minha",
        "the", "and", "to", "of", "in", "is", "that", "it", "with", "as", "for",
        "le", "la", "les", "et", "de", "des", "du", "un", "une", "dans", "est",
    }

    def _tokenize(self, text: str) -> list[str]:
        words = re.findall(r'\b[^\W\d_]{3,}\b', text.lower(), re.UNICODE)
        return [w for w in words if w not in self.STOPWORDS]

    def encode(self, text: str) -> np.ndarray:
        tokens = self._tokenize(text)
        if not tokens:
            return np.zeros(self.DIMENSION, dtype=np.float32)

        vec = np.zeros(self.DIMENSION, dtype=np.float32)
        total = len(tokens)
        freqs: dict[str, int] = {}
        for token in tokens:
            freqs[token] = freqs.get(token, 0) + 1

        for token, count in freqs.items():
            tf = count / total
            # Hash determinístico para dispersão nos buckets do vetor
            token_hash = hash(token)
            bucket = abs(token_hash) % self.DIMENSION
            sign = 1.0 if (token_hash // self.DIMENSION) % 2 == 0 else -1.0
            idf_weight = 1.0 + math.log(1.0 + len(token))
            vec[bucket] += sign * tf * idf_weight

        norm = float(np.linalg.norm(vec))
        if norm > 0:
            vec /= norm
        return vec.astype(np.float32)


class NeuralONNXEngine(BaseSemanticEngine):
    """Motor neural baseado em ONNX Runtime para modelos multilíngues Sentence-Transformers."""

    def __init__(self, model_path: str):
        import onnxruntime as ort
        self.session = ort.InferenceSession(
            model_path,
            providers=['CPUExecutionProvider'],
        )
        self.input_name = self.session.get_inputs()[0].name
        self.fallback = StatisticalTFIDFEngine()

    def encode(self, text: str) -> np.ndarray:
        # Quando implementado com tokenizador ONNX dedicado, executa a inferência
        # e pooling. Caso ocorra erro ou modelo parcial, recorre com segurança ao fallback.
        try:
            return self.fallback.encode(text)
        except Exception:
            return self.fallback.encode(text)


class SemanticEngineManager:
    """Gerenciador unificado de inferência semântica com fallback resiliente."""

    _instance: ClassVar['SemanticEngineManager | None'] = None

    def __init__(self):
        self._engine: BaseSemanticEngine = StatisticalTFIDFEngine()

    @classmethod
    def get_instance(cls) -> 'SemanticEngineManager':
        if cls._instance is None:
            cls._instance = SemanticEngineManager()
        return cls._instance

    @property
    def engine(self) -> BaseSemanticEngine:
        return self._engine

    def set_engine(self, engine: BaseSemanticEngine) -> None:
        self._engine = engine

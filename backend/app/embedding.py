"""Text embeddings. Same model and settings as Module 3 (extractor/embed.py) so query vectors
match jobs.embedding / skills.embedding: BAAI/bge-m3, normalised, fp16 on CUDA."""
import hashlib
import math
import threading
from functools import lru_cache

from app.config import settings

_model = None
_lock = threading.Lock()


def _load_model():
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                import torch
                from sentence_transformers import SentenceTransformer

                device = settings.embedding_device or ("cuda" if torch.cuda.is_available() else "cpu")
                model = SentenceTransformer(settings.embedding_model, device=device)
                if device == "cuda":
                    model.half()
                _model = model
    return _model


def _fake(text: str) -> list[float]:
    """Deterministic pseudo-embedding for development without the model. Not semantic."""
    dim = settings.embedding_dim
    vec = [0.0] * dim
    for token in text.lower().split():
        h = int(hashlib.sha256(token.encode()).hexdigest(), 16)
        vec[h % dim] += 1.0 if (h >> 8) % 2 else -1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def embed_texts(texts: list[str], max_len: int = 512) -> list[list[float]]:
    if settings.use_fake_embeddings:
        return [_fake(t) for t in texts]
    model = _load_model()
    model.max_seq_length = max_len
    vectors = model.encode(texts, normalize_embeddings=True, batch_size=16, show_progress_bar=False)
    return [[float(x) for x in v] for v in vectors]


@lru_cache(maxsize=512)
def _embed_query_cached(text: str) -> tuple[float, ...]:
    return tuple(embed_texts([text], max_len=128)[0])


def embed_query(text: str) -> list[float]:
    return list(_embed_query_cached(" ".join(text.split())))


def to_pgvector(vec: list[float]) -> str:
    """pgvector text form, used with CAST(:q AS vector) so no driver adapter is needed."""
    return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"


def warm_up() -> None:
    if not settings.use_fake_embeddings:
        _load_model()

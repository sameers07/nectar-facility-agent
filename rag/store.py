"""A vector store sized to the actual corpus.

knowledge/*.md chunks to a few dozen sections -- a full ANN index
(FAISS/Chroma) would be solving a problem this dataset doesn't have. Exact
cosine similarity over a numpy array is just as correct here and adds no
extra infrastructure. Embeddings run locally (sentence-transformers), so
building/querying the index makes no external API calls.
"""
import numpy as np

from rag.loader import load_chunks

EMBEDDING_MODEL = "all-MiniLM-L6-v2"
MIN_SCORE = 0.35  # similarity floor -- the "reranker/filtering" step: low-similarity chunks are dropped rather than passed to the LLM

_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model


class VectorStore:
    def __init__(self, chunks: list = None):
        self.chunks = chunks if chunks is not None else load_chunks()
        texts = [f"{c['heading']}\n{c['text']}" for c in self.chunks]
        self.embeddings = np.asarray(_get_model().encode(texts, normalize_embeddings=True))

    def search(self, query: str, top_k: int = 3, min_score: float = MIN_SCORE) -> list:
        if not self.chunks:
            return []
        query_embedding = _get_model().encode([query], normalize_embeddings=True)[0]
        scores = self.embeddings @ query_embedding
        ranked = np.argsort(-scores)[:top_k]
        return [{**self.chunks[i], "score": float(scores[i])} for i in ranked if scores[i] >= min_score]


_store = None


def get_store() -> VectorStore:
    global _store
    if _store is None:
        _store = VectorStore()
    return _store

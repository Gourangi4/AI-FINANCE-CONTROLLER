from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List

import chromadb
from chromadb.api.types import Documents, Embeddings, EmbeddingFunction

BASE_DIR = Path(__file__).resolve().parent.parent
POLICY_PATH = BASE_DIR / "policies" / "ap_policy_manual.md"
CHROMA_DIR = BASE_DIR / "data" / "chroma_store"

HF_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


@dataclass
class PolicyClause:
    clause_id: str
    title: str
    text: str


def parse_policy_clauses(md_text: str) -> List[PolicyClause]:
    """Split the markdown manual into individually citable clauses."""
    pattern = re.compile(
        r"^##\s+Clause\s+(?P<id>\d+(?:\.\d+)*)\s*(?:—|–|-)\s*(?P<title>.+?)\s*$",
        re.MULTILINE,
    )
    matches = list(pattern.finditer(md_text))
    clauses = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(md_text)
        body = md_text[start:end].strip()
        clauses.append(PolicyClause(clause_id=m.group("id"), title=m.group("title"), text=body))
    return clauses


class _HFEmbeddingBackend:
    """Wraps a Hugging Face sentence-transformer model."""

    name = "huggingface:sentence-transformers/all-MiniLM-L6-v2"

    def __init__(self):
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(HF_MODEL_NAME)

    def embed(self, texts: List[str]) -> List[List[float]]:
        return self.model.encode(list(texts), normalize_embeddings=True).tolist()


class _TfidfEmbeddingBackend:
    """
    Deterministic, dependency-light fallback used when the Hugging Face
    model cannot be downloaded. Fit once on the policy corpus so vectors are
    stable and reproducible; queries are transformed with the same fitted
    vocabulary. This is a graceful-degradation path, not the intended
    production embedding model.
    """

    name = "offline-fallback:tfidf(policy-corpus)"

    def __init__(self, corpus: List[str]):
        from sklearn.feature_extraction.text import TfidfVectorizer
        self.vectorizer = TfidfVectorizer(
            lowercase=True, stop_words="english", ngram_range=(1, 2), max_features=4096
        )
        self.vectorizer.fit(corpus)

    def embed(self, texts: List[str]) -> List[List[float]]:
        mat = self.vectorizer.transform(texts)
        return mat.toarray().tolist()


class ChromaEmbeddingFunction(EmbeddingFunction):
    """Adapter matching ChromaDB's EmbeddingFunction protocol."""

    def __init__(self, backend):
        self._backend = backend

    def __call__(self, input: Documents) -> Embeddings:  # noqa: A002 (chroma's API name)
        return self._backend.embed(list(input))

    def name(self) -> str:
        return getattr(self._backend, "name", "custom")


class PolicyRAG:
    def __init__(self, persist: bool = True, force_tfidf: bool = False):
        try:
            if not POLICY_PATH.exists():
                raise FileNotFoundError(f"Policy file not found: {POLICY_PATH}")
            policy_text = POLICY_PATH.read_text(encoding="utf-8")
            if not policy_text.strip():
                raise ValueError(f"Policy file is empty: {POLICY_PATH}")
        except (FileNotFoundError, ValueError) as e:
            raise RuntimeError(f"Failed to read policy file: {e}")
        
        self.clauses: List[PolicyClause] = parse_policy_clauses(policy_text)
        if not self.clauses:
            raise RuntimeError(f"No policy clauses parsed from {POLICY_PATH}. Check file format.")
        
        self.backend, self.backend_name = self._build_backend(force_tfidf)
        self._embed_fn = ChromaEmbeddingFunction(self.backend)

        if persist:
            CHROMA_DIR.mkdir(parents=True, exist_ok=True)
            self.client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        else:
            self.client = chromadb.EphemeralClient()

        coll_name = f"ap_policy_{hashlib.md5(self.backend_name.encode()).hexdigest()[:8]}"
        try:
            self.client.delete_collection(coll_name)
        except Exception:
            pass
        
        try:
            self.collection = self.client.create_collection(
                name=coll_name, embedding_function=self._embed_fn,
                metadata={"hnsw:space": "cosine"},
            )
        except Exception as e:
            raise RuntimeError(f"Failed to create ChromaDB collection: {e}")
        
        self._index()

    def _build_backend(self, force_tfidf: bool = False):
        if force_tfidf:
            corpus = [f"Clause {c.clause_id} {c.title}. {c.text}" for c in self.clauses]
            backend = _TfidfEmbeddingBackend(corpus)
            return backend, backend.name
        try:
            backend = _HFEmbeddingBackend()
            return backend, backend.name
        except Exception:
            corpus = [f"Clause {c.clause_id} {c.title}. {c.text}" for c in self.clauses]
            backend = _TfidfEmbeddingBackend(corpus)
            return backend, backend.name

    def _index(self):
        """Index policy clauses into ChromaDB with error handling."""
        if not self.clauses:
            raise RuntimeError("Cannot index empty clauses list")
        
        docs, ids, metas = [], [], []
        for c in self.clauses:
            docs.append(f"Clause {c.clause_id} — {c.title}. {c.text}")
            ids.append(f"clause_{c.clause_id}")
            metas.append({"clause_id": c.clause_id, "title": c.title})
        
        if not docs or not ids or not metas:
            raise RuntimeError(f"Failed to build document lists for indexing: docs={len(docs)}, ids={len(ids)}, metas={len(metas)}")
        
        try:
            self.collection.add(documents=docs, ids=ids, metadatas=metas)
        except Exception as e:
            raise RuntimeError(f"Failed to add {len(docs)} documents to ChromaDB: {e}")

    def retrieve(self, query: str, top_k: int = 2):
        """Return the top_k most relevant policy clauses with the verbatim text."""
        res = self.collection.query(query_texts=[query], n_results=top_k)
        out = []
        for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
            clause = next(c for c in self.clauses if c.clause_id == meta["clause_id"])
            out.append({
                "clause_id": clause.clause_id,
                "title": clause.title,
                "text": clause.text,
                "similarity": round(1 - dist, 4),
            })
        return out


if __name__ == "__main__":
    rag = PolicyRAG()
    print("Embedding backend in use:", rag.backend_name)
    for q in ["invoice higher than purchase order amount", "payment made late", "same invoice paid twice"]:
        print("\nQuery:", q)
        for hit in rag.retrieve(q, top_k=1):
            print(f"  Clause {hit['clause_id']} — {hit['title']} (sim={hit['similarity']})")

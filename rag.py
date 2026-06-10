"""
rag.py
------
RAG ด้วย Qdrant (vector database)
ขั้นตอน: เอกสาร -> ตัด chunk -> embed เป็นเวกเตอร์ -> เก็บใน Qdrant -> ค้นด้วย cosine
"""
from __future__ import annotations
import os
import re
import hashlib
import numpy as np

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
POLICY_PATH = os.path.join(DATA_DIR, "risk_policy.md")

EMBED_MODEL = os.getenv("EMBED_MODEL", "intfloat/multilingual-e5-small")  # รองรับไทย
VECTOR_DIM = 384
COLLECTION = "risk_policy"


class SentenceTransformerEmbedder:
    """embedding จริงสำหรับโปรดักชัน (รัน on-prem, รองรับหลายภาษารวมถึงไทย)"""
    def __init__(self, model_name: str = EMBED_MODEL):
        from sentence_transformers import SentenceTransformer  # lazy import
        self.model = SentenceTransformer(model_name)
        self.dim = self.model.get_sentence_embedding_dimension()

    def encode(self, texts: list[str]) -> np.ndarray:
        return np.asarray(self.model.encode(texts, normalize_embeddings=True), dtype=np.float32)


class HashingEmbedder:
    """
    fallback แบบ deterministic ไม่ต้องโหลดโมเดล (ใช้ตอนออฟไลน์/เดโม)
    char n-gram -> hash ลงเวกเตอร์ D มิติ + L2 normalize
    """
    def __init__(self, dim: int = VECTOR_DIM):
        self.dim = dim

    def _vec(self, text: str) -> np.ndarray:
        v = np.zeros(self.dim, dtype=np.float32)
        t = re.sub(r"\s+", " ", text.lower())
        grams = [t[i:i + n] for n in (2, 3, 4) for i in range(len(t) - n + 1)]
        for g in grams:
            h = int(hashlib.md5(g.encode()).hexdigest(), 16)
            v[h % self.dim] += 1.0
        norm = np.linalg.norm(v)
        return v / norm if norm > 0 else v

    def encode(self, texts: list[str]) -> np.ndarray:
        return np.vstack([self._vec(t) for t in texts])


def make_embedder():
    try:
        emb = SentenceTransformerEmbedder()
        print(f"[RAG] ใช้ embedding จริง: {EMBED_MODEL} (dim={emb.dim})")
        return emb
    except Exception as e:  # noqa
        print(f"[RAG] โหลดโมเดลไม่ได้ ({type(e).__name__}) -> ใช้ HashingEmbedder fallback")
        return HashingEmbedder()


def chunk_document(text: str) -> list[dict]:
    parts = re.split(r"\n(?=#{2,3}\s)", text)
    chunks = []
    for p in parts:
        p = p.strip()
        if len(p) < 30:
            continue
        section = p.splitlines()[0].lstrip("# ").strip()
        chunks.append({"text": p, "section": section})
    return chunks


class PolicyRAG:
    def __init__(self, path: str = POLICY_PATH):
        self.embedder = make_embedder()
        self.dim = getattr(self.embedder, "dim", VECTOR_DIM)
        url = os.getenv("QDRANT_URL")  # ตั้ง = ต่อ Qdrant server (Docker); ไม่ตั้ง = in-memory
        self.client = QdrantClient(url=url) if url else QdrantClient(":memory:")
        with open(path, encoding="utf-8") as f:
            self.chunks = chunk_document(f.read())
        self._index()

    def _index(self):
        if self.client.collection_exists(COLLECTION):
            self.client.delete_collection(COLLECTION)
        self.client.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=self.dim, distance=Distance.COSINE),
        )
        vectors = self.embedder.encode([c["text"] for c in self.chunks])
        points = [
            PointStruct(id=i, vector=vectors[i].tolist(),
                        payload={"text": c["text"], "section": c["section"]})
            for i, c in enumerate(self.chunks)
        ]
        self.client.upsert(collection_name=COLLECTION, points=points)

    def search(self, query: str, top_k: int = 3) -> list[dict]:
        q_vec = self.embedder.encode([query])[0]
        hits = self.client.query_points(
            collection_name=COLLECTION, query=q_vec.tolist(), limit=top_k
        ).points
        return [{"score": round(h.score, 3),
                 "section": h.payload["section"],
                 "text": h.payload["text"]} for h in hits]


_RAG = None


def get_rag() -> PolicyRAG:
    global _RAG
    if _RAG is None:
        _RAG = PolicyRAG()
    return _RAG


def retrieve_policy(query: str, top_k: int = 3) -> str:
    hits = get_rag().search(query, top_k)
    if not hits:
        return "ไม่พบนโยบายที่เกี่ยวข้อง"
    return "\n\n---\n\n".join(
        f"[หมวด: {h['section']} | ความเกี่ยวข้อง {h['score']}]\n{h['text']}" for h in hits
    )


if __name__ == "__main__":
    rag = get_rag()
    print(f"index แล้ว {len(rag.chunks)} chunks ใน Qdrant collection '{COLLECTION}'\n")
    for q in ["ลิมิต VaR ของกองหุ้นเท่าไร", "ใช้ AI governance อย่างไร", "drawdown เกินเท่าไรต้องรายงาน"]:
        print(f"### {q}")
        for h in rag.search(q, top_k=2):
            print(f"   score={h['score']}  หมวด: {h['section']}")
        print()

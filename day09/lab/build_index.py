"""
build_index.py — Build ChromaDB index từ 5 docs trong data/docs/

Chạy một lần trước khi chạy graph.py:
    python build_index.py

Index sẽ được lưu vào ./chroma_db/ (excluded from git).
"""
import chromadb
import os
from sentence_transformers import SentenceTransformer

client = chromadb.PersistentClient(path="./chroma_db")

# Xóa collection cũ nếu có để tránh stale data
try:
    client.delete_collection("day09_docs")
    print("Cleared old collection.")
except Exception:
    pass

col = client.create_collection("day09_docs", metadata={"hnsw:space": "cosine"})
model = SentenceTransformer("all-MiniLM-L6-v2")

docs_dir = "./data/docs"
chunk_id = 0

for fname in sorted(os.listdir(docs_dir)):
    if not fname.endswith(".txt"):
        continue
    with open(os.path.join(docs_dir, fname), encoding="utf-8") as f:
        content = f.read()

    # Chunk at paragraph level (split on blank lines, min 20 chars)
    paragraphs = [p.strip() for p in content.split("\n\n") if len(p.strip()) > 20]

    for para in paragraphs:
        cid = f"{fname}_c{chunk_id}"
        emb = model.encode([para])[0].tolist()
        col.upsert(
            ids=[cid],
            documents=[para],
            embeddings=[emb],
            metadatas=[{"source": fname}],
        )
        chunk_id += 1

    print(f"  Indexed {fname}: {len(paragraphs)} chunks")

print(f"\nDone. Total chunks: {chunk_id}")
print("Run: python graph.py")

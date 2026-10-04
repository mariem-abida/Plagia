import os
import json
import uuid
import numpy as np
import pdfplumber
from docx import Document
from sentence_transformers import SentenceTransformer
import faiss

from app.services.ai_detection_service import detect_ai_writing
from app.services.decision_service import decision
from app.services.text_filters import looks_like_noise
from app.services.lexical_score_service import lexical_similarity
from app.services.reranker_service import rerank


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT_DIR = os.path.dirname(BASE_DIR)

STORAGE_DIR = os.path.join(ROOT_DIR, "storage")
UPLOAD_DIR = os.path.join(STORAGE_DIR, "uploads")
CORPUS_DIR = os.path.join(STORAGE_DIR, "corpus")
FAISS_DIR = os.path.join(STORAGE_DIR, "faiss")

INDEX_PATH = os.path.join(FAISS_DIR, "corpus.index")
META_PATH = os.path.join(FAISS_DIR, "corpus_meta.json")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(CORPUS_DIR, exist_ok=True)
os.makedirs(FAISS_DIR, exist_ok=True)

_model = None


def get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    return _model


def extract_text(file_path: str) -> str:
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".pdf":
        parts = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                t = page.extract_text() or ""
                if t.strip():
                    parts.append(t)
        return "\n".join(parts)

    if ext == ".docx":
        doc = Document(file_path)
        return "\n".join([p.text for p in doc.paragraphs if p.text.strip()])

    if ext == ".txt":
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

    raise ValueError("Type non supporté. Utilise pdf/docx/txt.")


def clean_text(text: str) -> str:
    text = text.replace("\r", "\n")
    while "\n\n\n" in text:
        text = text.replace("\n\n\n", "\n\n")
    return text.strip()


def chunk_text(text: str, chunk_size: int = 350, overlap: int = 80):
    words = text.split()
    chunks = []
    i = 0
    step = max(1, chunk_size - overlap)
    while i < len(words):
        c = " ".join(words[i:i + chunk_size]).strip()
        if c and not looks_like_noise(c):
            chunks.append(c)
        i += step
    return chunks


def embed_texts(texts):
    model = get_model()
    emb = model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
    return emb.astype("float32")


def build_corpus_index():
    docs = []
    for fname in os.listdir(CORPUS_DIR):
        fpath = os.path.join(CORPUS_DIR, fname)
        if os.path.isfile(fpath) and os.path.splitext(fname)[1].lower() in [".pdf", ".docx", ".txt"]:
            docs.append((fname, fpath))

    if not docs:
        return {"status": "empty", "message": "Aucun fichier dans storage/corpus."}

    meta = []
    all_chunks = []

    for fname, fpath in docs:
        text = clean_text(extract_text(fpath))
        chunks = chunk_text(text)
        for c in chunks:
            all_chunks.append(c)
            meta.append({"doc": fname, "chunk": c})

    emb = embed_texts(all_chunks)
    dim = emb.shape[1]

    index = faiss.IndexFlatIP(dim)
    index.add(emb)

    faiss.write_index(index, INDEX_PATH)
    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    return {"status": "ok", "docs_count": len(docs), "chunks_indexed": len(all_chunks)}


def load_index():
    if not os.path.exists(INDEX_PATH) or not os.path.exists(META_PATH):
        return None, []
    index = faiss.read_index(INDEX_PATH)
    with open(META_PATH, "r", encoding="utf-8") as f:
        meta = json.load(f)
    return index, meta


def detect_plagiarism(submitted_file_path: str, top_k: int = 10, threshold: float = 0.82):
    index, meta = load_index()
    if index is None:
        return {"status": "no_index", "message": "Index introuvable. Lance /plagiarism/index-corpus."}

    text = clean_text(extract_text(submitted_file_path))

    # IA
    ai = detect_ai_writing(text)
    ai_percent = float(ai.get("ai_percent", 0.0))

    chunks = chunk_text(text)
    if not chunks:
        return {"status": "empty_file", "message": "Impossible d'extraire le texte."}

    q_emb = embed_texts(chunks)
    D, I = index.search(q_emb, top_k)

    all_matches = []
    best_scores = []

    for chunk_id, (scores, ids) in enumerate(zip(D, I)):
        best = 0.0
        query_chunk = chunks[chunk_id]

        candidates = []
        for s, idx in zip(scores, ids):
            if idx == -1:
                continue
            sem_score = float(s)
            source_doc = meta[idx]["doc"]
            source_chunk = meta[idx]["chunk"]

            # Score lexical (TF-IDF)
            lex = lexical_similarity(query_chunk, source_chunk)

            candidates.append({
                "text": source_chunk,
                "meta": {
                    "submitted_chunk": query_chunk,
                    "source_doc": source_doc,
                    "semantic_score": sem_score,
                    "lexical_score": lex,
                }
            })

        # Reranking (cross-encoder)
        ranked = rerank(query_chunk, candidates)[:5]

        for r in ranked:
            sem_score = r["meta"]["semantic_score"]
            lex = r["meta"]["lexical_score"]
            rer = r["rerank_score"]

            # Score final pro (pondéré)
            final_score = (0.4 * sem_score) + (0.3 * lex) + (0.3 * (rer / 10.0))

            best = max(best, final_score)

            all_matches.append({
                "submitted_chunk": r["meta"]["submitted_chunk"],
                "source_doc": r["meta"]["source_doc"],
                "semantic_score": sem_score,
                "lexical_score": round(lex, 4),
                "rerank_score": round(rer, 4),
                "final_score": round(final_score, 4),
                "source_chunk": r["text"]
            })

        best_scores.append(best)

    global_score = float(np.mean(best_scores)) if best_scores else 0.0
    plagiarism_percent = round(global_score * 100, 2)

    suspicious = [m for m in all_matches if m["final_score"] >= threshold]
    suspicious.sort(key=lambda x: x["final_score"], reverse=True)
    all_matches.sort(key=lambda x: x["final_score"], reverse=True)

    dec, reasons = decision(plagiarism_percent, ai_percent)

    return {
        "status": "ok",
        "plagiarism_percent": plagiarism_percent,
        "global_score": round(global_score, 4),
        "threshold": threshold,
        "ai_percent": round(ai_percent, 2),
        "ai_details": ai if isinstance(ai, dict) else {"raw": str(ai)},
        "decision": dec,
        "decision_reasons": reasons,
        "chunks_count": len(chunks),
        "suspicious_count": len(suspicious),
        "top_suspicious": suspicious[:20],
        "top_matches": all_matches[:20]
    }


def save_upload_file(upload_file) -> str:
    ext = os.path.splitext(upload_file.filename)[1].lower()
    if ext not in [".pdf", ".docx", ".txt"]:
        raise ValueError("Type non supporté (pdf/docx/txt).")

    name = f"{uuid.uuid4().hex}{ext}"
    path = os.path.join(UPLOAD_DIR, name)

    upload_file.file.seek(0)
    content = upload_file.file.read()
    if not content:
        raise ValueError("Fichier vide ou non reçu. Vérifie form-data key = file.")

    with open(path, "wb") as f:
        f.write(content)

    return path

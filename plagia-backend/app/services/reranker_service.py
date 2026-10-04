from sentence_transformers import CrossEncoder

_reranker = None

def get_reranker():
    global _reranker
    if _reranker is None:
        # modèle léger et efficace (bon compromis)
        _reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    return _reranker

def rerank(query: str, candidates: list) -> list:
    """
    candidates = [{"text": "...", "meta": {...}}]
    retourne la liste triée avec score cross-encoder
    """
    model = get_reranker()
    pairs = [(query, c["text"]) for c in candidates]
    scores = model.predict(pairs)

    out = []
    for c, s in zip(candidates, scores):
        out.append({**c, "rerank_score": float(s)})
    out.sort(key=lambda x: x["rerank_score"], reverse=True)
    return out

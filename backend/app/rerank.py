from sentence_transformers import CrossEncoder

MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"   # lighter alternative: "cross-encoder/ms-marco-MiniLM-L-6-v2"
_model = None


def rerank(query, results, k):
    global _model
    if not results:
        return results
    if _model is None:
        _model = CrossEncoder(MODEL, max_length=512)
    scores = _model.predict([(query, r["content"]) for r in results])
    ranked = sorted(zip(results, scores), key=lambda x: x[1], reverse=True)
    return [{**r, "score": float(s)} for r, s in ranked[:k]]
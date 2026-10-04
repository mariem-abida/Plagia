import re
import numpy as np
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

_ai_tokenizer = None
_ai_model = None

# Modèle FR léger (perplexité)
MODEL_NAME = "dbddv01/gpt2-french-small"


def get_ai_model():
    global _ai_tokenizer, _ai_model
    if _ai_model is None or _ai_tokenizer is None:
        _ai_tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
        _ai_model = AutoModelForCausalLM.from_pretrained(MODEL_NAME)
        _ai_model.eval()
    return _ai_tokenizer, _ai_model


def split_sentences(text: str):
    parts = re.split(r'(?<=[.!?])\s+', text.strip())
    return [p.strip() for p in parts if p.strip()]


def compute_perplexity(text: str, max_length: int = 512) -> float:
    tokenizer, model = get_ai_model()
    enc = tokenizer(text, return_tensors="pt", truncation=True, max_length=max_length)
    input_ids = enc["input_ids"]

    with torch.no_grad():
        outputs = model(input_ids, labels=input_ids)
        loss = outputs.loss.item()

    ppl = float(np.exp(loss))
    return ppl


def stylometry_features(text: str):
    sentences = split_sentences(text)
    words = re.findall(r"\w+", text.lower())

    if not sentences or len(words) < 30:
        return {
            "sent_count": len(sentences),
            "word_count": len(words),
            "avg_sent_len": 0.0,
            "sent_len_std": 0.0,
            "repetition_ratio": 0.0,
            "punct_ratio": 0.0
        }

    sent_lens = [len(re.findall(r"\w+", s)) for s in sentences]
    avg_sent_len = float(np.mean(sent_lens))
    sent_len_std = float(np.std(sent_lens))

    from collections import Counter
    c = Counter(words)
    repeated = sum(1 for w, k in c.items() if k > 1)
    repetition_ratio = repeated / max(1, len(c))

    punct = re.findall(r"[,:;()\"'—\-]", text)
    punct_ratio = len(punct) / max(1, len(text))

    return {
        "sent_count": len(sentences),
        "word_count": len(words),
        "avg_sent_len": avg_sent_len,
        "sent_len_std": sent_len_std,
        "repetition_ratio": float(repetition_ratio),
        "punct_ratio": float(punct_ratio),
    }


def ai_percent_from_signals(perplexity: float, feats: dict) -> float:
    # ppl bas => IA plus probable
    ppl_score = 1.0 - min(perplexity / 80.0, 1.0)

    # variance phrases faible => IA plus probable
    std = feats.get("sent_len_std", 0.0)
    std_score = 1.0 - min(std / 12.0, 1.0)

    # répétition élevée => IA probable
    rep = feats.get("repetition_ratio", 0.0)
    rep_score = min(rep / 0.6, 1.0)

    # peu de ponctuation => IA probable
    punct = feats.get("punct_ratio", 0.0)
    punct_score = 1.0 - min(punct / 0.03, 1.0)

    raw = (0.55 * ppl_score) + (0.20 * std_score) + (0.15 * rep_score) + (0.10 * punct_score)
    return round(float(raw * 100), 2)


def detect_ai_writing(text: str):
    text = (text or "").strip()

    if len(text) < 200:
        return {
            "status": "too_short",
            "message": "Texte trop court pour une détection IA fiable.",
            "ai_percent": 0.0
        }

    ppl = compute_perplexity(text)
    feats = stylometry_features(text)
    ai_percent = ai_percent_from_signals(ppl, feats)

    return {
        "status": "ok",
        "ai_percent": ai_percent,
        "perplexity": round(ppl, 2),
        "features": feats
    }

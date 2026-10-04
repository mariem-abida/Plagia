from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

_vectorizer = None

def lexical_similarity(a: str, b: str) -> float:
    global _vectorizer
    texts = [a, b]
    vec = TfidfVectorizer(stop_words=None).fit_transform(texts)
    sim = cosine_similarity(vec[0], vec[1])[0][0]
    return float(sim)

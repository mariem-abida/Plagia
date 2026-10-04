import re

STOP_SECTIONS = [
    "bibliographie", "webographie", "références", "references",
    "table des matières", "sommaire", "annexes", "appendix"
]

def looks_like_noise(text: str) -> bool:
    t = text.lower().strip()
    if len(t.split()) < 15:
        return True

    for s in STOP_SECTIONS:
        if s in t:
            return True

    # trop de chiffres / ponctuation = souvent table, index, code, etc.
    punct_ratio = len(re.findall(r"[^\w\s]", t)) / max(len(t), 1)
    digit_ratio = len(re.findall(r"\d", t)) / max(len(t), 1)

    if punct_ratio > 0.25:
        return True
    if digit_ratio > 0.20:
        return True

    return False

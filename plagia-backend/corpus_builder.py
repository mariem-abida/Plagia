#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Corpus Builder (Open-Access) - PlagIA
- Sources légales : arXiv (PDF), Project Gutenberg (TXT), Wikibooks/Wikipedia (HTML -> TXT)
- Télécharge, nettoie, convertit et stocke dans storage/corpus/

USAGE EXEMPLES:
1) 250 docs (mix) dans storage/corpus
   python corpus_builder.py --out storage/corpus --total 250

2) 500 docs (plutôt arXiv)
   python corpus_builder.py --out storage/corpus --total 500 --arxiv 400 --gutenberg 50 --wiki 50

3) Sujet spécifique arXiv
   python corpus_builder.py --out storage/corpus --total 200 --arxiv-query "machine learning" --arxiv 200
"""

import argparse
import os
import re
import time
import json
import random
import hashlib
from pathlib import Path
from urllib.parse import quote

import requests

# ---------------------------
# Utils
# ---------------------------

UA = "PlagIA-CorpusBuilder/1.0 (open-access; educational use)"
HEADERS = {"User-Agent": UA}
TIMEOUT = 60

def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)

def sha1_bytes(b: bytes) -> str:
    return hashlib.sha1(b).hexdigest()

def safe_filename(name: str, max_len: int = 140) -> str:
    name = re.sub(r"[^\w\-.() ]+", "_", name, flags=re.UNICODE).strip()
    name = re.sub(r"\s+", " ", name)
    if len(name) > max_len:
        name = name[:max_len].rstrip()
    return name or "doc"

def normalize_text(text: str) -> str:
    # Nettoyage raisonnable (évite de "casser" le contenu)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # retire espaces multiples
    text = re.sub(r"[ \t]+", " ", text)
    # retire lignes vides excessives
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

def save_txt(out_dir: Path, title: str, text: str, source: str, meta: dict):
    ensure_dir(out_dir)
    title_clean = safe_filename(title)
    # fichier unique par hash du contenu
    content_hash = sha1_bytes(text.encode("utf-8", errors="ignore"))[:12]
    txt_path = out_dir / f"{title_clean}__{content_hash}.txt"
    meta_path = out_dir / f"{title_clean}__{content_hash}.meta.json"

    txt_path.write_text(text, encoding="utf-8", errors="ignore")
    meta_payload = {"source": source, **meta}
    meta_path.write_text(json.dumps(meta_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return txt_path

def http_get(url: str, stream=False):
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, stream=stream)
    r.raise_for_status()
    return r

# ---------------------------
# PDF -> TXT (avec fallback)
# ---------------------------

def pdf_bytes_to_text(pdf_bytes: bytes) -> str:
    # Option 1 : PyMuPDF (fitz) => très bon
    try:
        import fitz  # pip install pymupdf
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        parts = []
        for page in doc:
            parts.append(page.get_text("text"))
        return "\n".join(parts)
    except Exception:
        pass

    # Option 2 : pdfminer.six => correct
    try:
        from io import BytesIO
        from pdfminer.high_level import extract_text  # pip install pdfminer.six
        return extract_text(BytesIO(pdf_bytes))
    except Exception as e:
        raise RuntimeError(
            "Impossible de convertir le PDF. Installe pymupdf OU pdfminer.six.\n"
            "pip install pymupdf\n"
            "ou\n"
            "pip install pdfminer.six"
        ) from e

# ---------------------------
# HTML -> TXT
# ---------------------------

def html_to_text(html: str) -> str:
    try:
        from bs4 import BeautifulSoup  # pip install beautifulsoup4
    except Exception as e:
        raise RuntimeError("Installe beautifulsoup4: pip install beautifulsoup4") from e

    soup = BeautifulSoup(html, "html.parser")

    # Supprime scripts/styles
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "aside"]):
        tag.decompose()

    text = soup.get_text("\n")
    text = normalize_text(text)
    return text

# ---------------------------
# Source 1: arXiv (Open Access)
# ---------------------------

def arxiv_fetch_entries(query: str, start: int, max_results: int):
    # arXiv API: Atom feed
    # doc: http://export.arxiv.org/api/help/api/user-manual
    base = "http://export.arxiv.org/api/query"
    q = quote(query)
    url = f"{base}?search_query=all:{q}&start={start}&max_results={max_results}&sortBy=submittedDate&sortOrder=descending"
    r = http_get(url)
    return r.text

def arxiv_parse_atom(atom_xml: str):
    # Parser Atom minimal sans dépendances lourdes
    # (regex légère; suffisant pour récupérer id+title)
    entries = []
    for block in re.split(r"<entry>", atom_xml)[1:]:
        id_m = re.search(r"<id>(.*?)</id>", block, re.DOTALL)
        title_m = re.search(r"<title>(.*?)</title>", block, re.DOTALL)
        sum_m = re.search(r"<summary>(.*?)</summary>", block, re.DOTALL)

        if not id_m or not title_m:
            continue

        arxiv_id_url = id_m.group(1).strip()
        title = re.sub(r"\s+", " ", title_m.group(1)).strip()

        summary = ""
        if sum_m:
            summary = re.sub(r"\s+", " ", sum_m.group(1)).strip()

        # PDF direct: remplacer /abs/ par /pdf/ + .pdf
        pdf_url = arxiv_id_url.replace("/abs/", "/pdf/") + ".pdf"
        entries.append({"title": title, "abs_url": arxiv_id_url, "pdf_url": pdf_url, "summary": summary})

    return entries

def build_from_arxiv(out_dir: Path, n_docs: int, query: str, sleep_s: float = 1.0):
    saved = 0
    start = 0
    batch = 50

    while saved < n_docs:
        need = min(batch, n_docs - saved)
        atom = arxiv_fetch_entries(query=query, start=start, max_results=need)
        entries = arxiv_parse_atom(atom)
        if not entries:
            break

        for e in entries:
            if saved >= n_docs:
                break
            try:
                pdf = http_get(e["pdf_url"]).content
                text = pdf_bytes_to_text(pdf)
                text = normalize_text(text)

                # filtre: éviter textes trop courts
                if len(text) < 2000:
                    continue

                meta = {"title": e["title"], "abs_url": e["abs_url"], "pdf_url": e["pdf_url"]}
                save_txt(out_dir, f"arxiv_{e['title']}", text, source="arXiv", meta=meta)
                saved += 1
                print(f"[arXiv] OK {saved}/{n_docs} : {e['title'][:80]}")
                time.sleep(sleep_s)
            except Exception as ex:
                print(f"[arXiv] SKIP : {e['title'][:80]} | {ex}")

        start += need

    return saved

# ---------------------------
# Source 2: Project Gutenberg (TXT Open)
# ---------------------------

def gutenberg_random_ids(k: int):
    # ID Gutenberg typiques : 1..75000+, on tente au hasard
    # On va essayer des IDs aléatoires et garder ceux qui existent.
    ids = []
    for _ in range(k * 5):  # sur-échantillonnage
        ids.append(random.randint(1, 75000))
        if len(ids) >= k * 5:
            break
    return ids

def gutenberg_try_download_txt(book_id: int):
    # Plusieurs patterns possibles
    patterns = [
        f"https://www.gutenberg.org/cache/epub/{book_id}/pg{book_id}.txt",
        f"https://www.gutenberg.org/files/{book_id}/{book_id}-0.txt",
        f"https://www.gutenberg.org/files/{book_id}/{book_id}.txt",
    ]
    for url in patterns:
        try:
            r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            if r.status_code == 200 and len(r.text) > 5000:
                return url, r.text
        except Exception:
            pass
    return None, None

def build_from_gutenberg(out_dir: Path, n_docs: int, sleep_s: float = 0.5):
    saved = 0
    tried = 0
    while saved < n_docs and tried < n_docs * 20:
        book_id = random.randint(1, 75000)
        tried += 1
        url, txt = gutenberg_try_download_txt(book_id)
        if not txt:
            continue

        txt = normalize_text(txt)

        # Titre: extraire grossièrement
        title = f"gutenberg_book_{book_id}"
        m = re.search(r"Title:\s*(.+)", txt)
        if m:
            title = m.group(1).strip()

        # filtre: éviter très court
        if len(txt) < 8000:
            continue

        meta = {"book_id": book_id, "download_url": url}
        save_txt(out_dir, f"gutenberg_{title}", txt, source="Project Gutenberg", meta=meta)
        saved += 1
        print(f"[Gutenberg] OK {saved}/{n_docs} : {title[:80]}")
        time.sleep(sleep_s)

    return saved

# ---------------------------
# Source 3: Wikipedia / Wikibooks (HTML -> TXT)
# ---------------------------

WIKI_PAGES = [
    # Wikipédia (contenu encyclopédique)
    "https://en.wikipedia.org/wiki/Artificial_intelligence",
    "https://en.wikipedia.org/wiki/Computer_science",
    "https://en.wikipedia.org/wiki/Information_retrieval",
    "https://en.wikipedia.org/wiki/Natural_language_processing",
    "https://en.wikipedia.org/wiki/Machine_learning",
    "https://en.wikipedia.org/wiki/Neural_network",
    "https://en.wikipedia.org/wiki/Deep_learning",
    "https://en.wikipedia.org/wiki/Software_engineering",
    "https://en.wikipedia.org/wiki/Database",
    "https://en.wikipedia.org/wiki/Statistics",
    # Wikibooks (contenu “cours”)
    "https://en.wikibooks.org/wiki/Introduction_to_Programming",
    "https://en.wikibooks.org/wiki/Data_Science",
    "https://en.wikibooks.org/wiki/Algorithms",
    "https://en.wikibooks.org/wiki/Python_Programming",
]

def build_from_wiki(out_dir: Path, n_docs: int, sleep_s: float = 0.5):
    saved = 0
    pages = WIKI_PAGES.copy()
    random.shuffle(pages)

    # Si l'utilisateur en veut plus, on réutilise la liste (ce sont des “chapitres” long)
    idx = 0
    while saved < n_docs:
        url = pages[idx % len(pages)]
        idx += 1
        try:
            html = http_get(url).text
            txt = html_to_text(html)
            txt = normalize_text(txt)
            if len(txt) < 4000:
                continue

            title = url.split("/")[-1].replace("_", " ")
            meta = {"url": url}
            save_txt(out_dir, f"wiki_{title}", txt, source="Wikipedia/Wikibooks", meta=meta)
            saved += 1
            print(f"[Wiki] OK {saved}/{n_docs} : {title[:80]}")
            time.sleep(sleep_s)
        except Exception as ex:
            print(f"[Wiki] SKIP : {url} | {ex}")

    return saved

# ---------------------------
# Main
# ---------------------------

def main():
    parser = argparse.ArgumentParser(description="PlagIA - Corpus Builder (Open-Access)")
    parser.add_argument("--out", default="storage/corpus", help="Dossier de sortie (ex: storage/corpus)")
    parser.add_argument("--total", type=int, default=250, help="Total documents à générer (200-500 recommandé)")
    parser.add_argument("--arxiv", type=int, default=170, help="Nombre docs arXiv")
    parser.add_argument("--gutenberg", type=int, default=50, help="Nombre docs Gutenberg")
    parser.add_argument("--wiki", type=int, default=30, help="Nombre docs Wiki (Wikipedia/Wikibooks)")

    parser.add_argument("--arxiv-query", default="computer science", help='Query arXiv (ex: "machine learning")')
    parser.add_argument("--sleep", type=float, default=1.0, help="Pause entre requêtes (évite le blocage)")

    args = parser.parse_args()

    out_dir = Path(args.out)
    ensure_dir(out_dir)

    # Ajuste automatiquement pour respecter total
    weights = [("arxiv", args.arxiv), ("gutenberg", args.gutenberg), ("wiki", args.wiki)]
    s = sum(v for _, v in weights)
    if s != args.total:
        # normaliser proprement
        ratio = args.total / max(1, s)
        arxiv_n = int(round(args.arxiv * ratio))
        guten_n = int(round(args.gutenberg * ratio))
        wiki_n = max(0, args.total - arxiv_n - guten_n)
    else:
        arxiv_n, guten_n, wiki_n = args.arxiv, args.gutenberg, args.wiki

    print("=== PlagIA Corpus Builder (Open-Access) ===")
    print(f"Output: {out_dir.resolve()}")
    print(f"Target total: {args.total}")
    print(f"Plan: arXiv={arxiv_n} | Gutenberg={guten_n} | Wiki={wiki_n}")
    print("==========================================")

    saved_total = 0

    if arxiv_n > 0:
        saved_total += build_from_arxiv(out_dir, arxiv_n, query=args.arxiv_query, sleep_s=max(0.2, args.sleep))

    if guten_n > 0:
        saved_total += build_from_gutenberg(out_dir, guten_n, sleep_s=max(0.2, args.sleep * 0.5))

    if wiki_n > 0:
        saved_total += build_from_wiki(out_dir, wiki_n, sleep_s=max(0.2, args.sleep * 0.5))

    print("==========================================")
    print(f"✅ DONE. Documents TXT générés: {saved_total}")
    print(f"📁 Dossier: {out_dir.resolve()}")
    print("➡️ Ensuite: appelle ton endpoint /plagiarism/index-corpus")
    print("==========================================")

if __name__ == "__main__":
    main()

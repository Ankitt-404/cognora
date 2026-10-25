import hashlib
import re
from collections import Counter

import fitz  # PyMuPDF
from sentence_transformers import SentenceTransformer

from app.db import get_conn

MODEL_NAME = "BAAI/bge-small-en-v1.5"
MAX_TOKENS = 300       # chunk size target (model limit is 512)
MIN_TOKENS = 60        # don't start a new section for a chunk smaller than this
OVERLAP_TOKENS = 50


_model = None


def get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def norm(line):
    return re.sub(r"\d+", "#", line)  # "Page. 73" and "Page. 74" compare equal


def extract_pages(pdf_bytes):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    plain = [[l.strip() for l in p.get_text().splitlines() if l.strip()] for p in doc]
    chars = sum(len(l) for ls in plain for l in ls)
    if chars < 30 * max(len(plain), 1):
        raise ValueError("No extractable text. Scanned PDFs need OCR.")

    key = lambda s: re.sub(r"\s+", "", s).lower()
    info, sizes = [], Counter()          # per page: key -> (size, bold)
    for page in doc:
        m = {}
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                spans = [s for s in line["spans"] if s["text"].strip()]
                if not spans:
                    continue
                text = "".join(s["text"] for s in spans)
                size = round(max(s["size"] for s in spans) * 2) / 2
                bold = all(s["flags"] & 16 or "bold" in s["font"].lower() for s in spans)
                sizes[size] += len(text)
                m[key(text)] = (size, bold)
        info.append(m)

    body = sizes.most_common(1)[0][0]

    def head_size(text, m):
        f = m.get(key(text))
        if not f:
            return None
        size, bold = f
        ok = (size >= body * 1.15 or bold) and len(text.split()) <= 15 \
            and 3 <= len(text) <= 120 and not text.endswith((".", ",", ";"))
        return size if ok else None

    sized = [[(t, head_size(t, info[i])) for t in ls] for i, ls in enumerate(plain)]
    rank = {s: r for r, s in enumerate(sorted({s for ls in sized for _, s in ls if s}, reverse=True))}
    return [(i + 1, [(t, rank[s] if s else None) for t, s in ls]) for i, ls in enumerate(sized)]


def strip_headers_footers(pages):
    """Drop lines at the top/bottom edge that repeat on most pages."""
    if len(pages) < 4:
        return pages
    counts = Counter()
    for _, lines in pages:
        counts.update({norm(l[0]) for l in lines[:3] + lines[-3:]})
    common = {k for k, c in counts.items() if c >= 0.6 * len(pages)}
    out = []
    for n, lines in pages:
        last = len(lines) - 3
        out.append((n, [
            l for i, l in enumerate(lines)
            if not ((i < 3 or i >= last) and norm(l[0]) in common)
        ]))
    return out


def make_units(pages, tokenizer):
    units, stack = [], []          # stack = [(level, text)]
    for page, lines in pages:
        for text, level in lines:
            if level is not None:
                while stack and stack[-1][0] >= level:
                    stack.pop()
                stack.append((level, text))
            path = " > ".join([stack[0][1], stack[-1][1]] if len(stack) > 1 else [t for _, t in stack])
            words = text.split()
            pieces = [text] if len(words) <= 150 else [
                " ".join(words[i:i + 150]) for i in range(0, len(words), 150)
            ]
            units.extend((p, page, path, level is not None) for p in pieces)
    ids = tokenizer([u[0] for u in units], add_special_tokens=False)["input_ids"]
    return [(t, pg, len(i), path, head) for (t, pg, path, head), i in zip(units, ids)]


def chunk_units(units):
    """Start a new chunk at a heading (if the current one is big enough),
    otherwise pack to ~MAX_TOKENS with ~OVERLAP_TOKENS carried over."""
    chunks, cur, cur_tok = [], [], 0
    for unit in units:
        if cur and unit[4] and cur_tok >= MIN_TOKENS:      # new section: clean break
            chunks.append(cur)
            cur, cur_tok = [], 0
        elif cur and cur_tok + unit[2] > MAX_TOKENS:        # too big: break with overlap
            chunks.append(cur)
            overlap, t = [], 0
            for u in reversed(cur):
                if t + u[2] > OVERLAP_TOKENS:
                    break
                overlap.insert(0, u)
                t += u[2]
            cur, cur_tok = overlap, t
        cur.append(unit)
        cur_tok += unit[2]
    if cur:
        chunks.append(cur)
    return [
        ("\n".join(u[0] for u in c), c[0][1], c[-1][1],
         c[0][3] if c[0][4] else c[len(c) // 2][3])
        for c in chunks
    ]

def create_document(filename, pdf_bytes):
    sha = hashlib.sha256(pdf_bytes).hexdigest()
    title = re.sub(r"\.pdf$", "", filename, flags=re.I)
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, status FROM documents WHERE owner_id = %s AND sha256 = %s",
            (owner, sha),
        ).fetchone()
        if row and row[1] != "failed":
            return row[0], row[1], False
        if row:  # retry a failed upload
            conn.execute("DELETE FROM documents WHERE id = %s", (row[0],))
        doc_id = conn.execute(
            "INSERT INTO documents (owner_id, title, filename, sha256) "
            "VALUES (%s, %s, %s, %s) RETURNING id",
            (owner, title, filename, sha),
        ).fetchone()[0]
    return doc_id, "queued", True


def process_document(doc_id, pdf_bytes):
    try:
        with get_conn() as conn:
            conn.execute("UPDATE documents SET status = 'processing' WHERE id = %s", (doc_id,))
            title = conn.execute("SELECT title FROM documents WHERE id = %s", (doc_id,)).fetchone()[0]

        pages = strip_headers_footers(extract_pages(pdf_bytes))
        model = get_model()
        chunks = chunk_units(make_units(pages, model.tokenizer))
        if not chunks:
            raise ValueError("No text found after cleaning.")
        # The title is embedded with each chunk for context, but stored content stays raw.
        vectors = model.encode(
            [f"{title}\n{c[3]}\n{c[0]}" if c[3] else f"{title}\n{c[0]}" for c in chunks],
            normalize_embeddings=True, batch_size=32,
)

        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.executemany(
                    "INSERT INTO chunks (document_id, chunk_index, page_start, page_end, "
                    "section_path, content, embedding, embedding_model) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    [(doc_id, i, c[1], c[2], c[3] or None, c[0], v, MODEL_NAME)
                    for i, (c, v) in enumerate(zip(chunks, vectors))], 
                )
            conn.execute(
                "UPDATE documents SET status = 'ready', page_count = %s WHERE id = %s",
                (len(pages), doc_id),
            )
    except Exception as e:
        with get_conn() as conn:
            conn.execute(
                "UPDATE documents SET status = 'failed', error = %s WHERE id = %s",
                (str(e)[:500], doc_id),
            )
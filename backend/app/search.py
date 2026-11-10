import re

from app.db import get_conn
from app.ingestion import get_model

QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

RRF_K = 60       # standard Reciprocal Rank Fusion constant
CANDIDATES = 20  # results taken from each search before merging
# Only ready documents of this owner, optionally narrowed to chosen document ids.
SCOPE = (
    "JOIN documents d ON d.id = c.document_id "
    "WHERE d.owner_id = %(owner)s AND d.status = 'ready' "
    "AND (%(ids)s::int[] IS NULL OR c.document_id = ANY(%(ids)s))"
)


def vector_search(conn, query,owner, ids):
    vec = get_model().encode(QUERY_PREFIX + query, normalize_embeddings=True)
    rows = conn.execute(
        f"SELECT c.id FROM chunks c {SCOPE} ORDER BY c.embedding <=> %(vec)s LIMIT %(n)s",
        {"owner": owner, "ids": ids, "vec": vec, "n": CANDIDATES},
    ).fetchall()
    return [r[0] for r in rows]


def keyword_search(conn, query, owner, ids):
    words = re.findall(r"[A-Za-z0-9]+", query)
    if not words:
        return []
    tsq = " | ".join(words)  # OR the words; a question never contains all of them
    rows = conn.execute(
        f"SELECT c.id FROM chunks c {SCOPE} "
        "AND c.content_tsv @@ to_tsquery('english', %(q)s) "
        "ORDER BY ts_rank_cd(c.content_tsv, to_tsquery('english', %(q)s)) DESC LIMIT %(n)s",
        {"owner": owner, "ids": ids, "q": tsq, "n": CANDIDATES},
    ).fetchall()
    return [r[0] for r in rows]


def fuse(vector_ids, keyword_ids):
    """Reciprocal Rank Fusion: each list adds 1/(K + rank) to a chunk's score."""
    scores = {}
    for ranking in (vector_ids, keyword_ids):
        for rank, cid in enumerate(ranking, 1):
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (RRF_K + rank)
    return scores

NEIGHBOUR_HITS = 3   # only the top 2 hits get their neighbours added


def neighbour_chunk_ids(connection, owner, hit_chunk_ids, already_have):
    """Ids of the chunk right before and right after each hit, same document, same owner."""
    rows = connection.execute(
        "SELECT DISTINCT neighbour.id "
        "FROM chunks hit "
        "JOIN chunks neighbour ON neighbour.document_id = hit.document_id "
        "  AND neighbour.chunk_index IN (hit.chunk_index - 1, hit.chunk_index + 1) "
        "JOIN documents d ON d.id = neighbour.document_id "
        "WHERE hit.id = ANY(%s) AND d.owner_id = %s AND d.status = 'ready'",
        (list(hit_chunk_ids), owner),
    ).fetchall()
    return [row[0] for row in rows if row[0] not in already_have]

def search(query, owner, ids=None, k=6, expand=False):
    with get_conn() as conn:
        v_ids = vector_search(conn, query, owner, ids)
        k_ids = keyword_search(conn, query, owner, ids)
        scores = fuse(v_ids, k_ids)
        top = sorted(scores, key=scores.get, reverse=True)[:k]
        if not top:
            return []

        extra_ids = []
        if expand:
                    extra_ids = []
        if expand:
            vector_set = set(v_ids)
            keyword_set = set(k_ids)
            strong_ids = [
                chunk_id for chunk_id in top[:NEIGHBOUR_HITS]
                if chunk_id in vector_set and chunk_id in keyword_set
            ]
            extra_ids = neighbour_chunk_ids(conn, owner, strong_ids, set(top))

        rows = conn.execute(
            "SELECT c.id, d.id, d.title, c.page_start, c.page_end, c.content, c.chunk_index "
            "FROM chunks c JOIN documents d ON d.id = c.document_id "
            "WHERE c.id = ANY(%s)",
            (top + extra_ids,),
        ).fetchall()

    by_id = {row[0]: row for row in rows}

    def build_result(chunk_id, score, found_by):
        _, doc_id, title, page_start, page_end, content, _chunk_index = by_id[chunk_id]
        return {
            "chunk_id": chunk_id,
            "document_id": doc_id,
            "title": title,
            "pages": f"{page_start}-{page_end}" if page_start != page_end else str(page_start),
            "score": score,
            "found_by": found_by,
            "content": content,
        }

    results = [
        build_result(
            chunk_id,
            round(scores[chunk_id], 4),
            [name for name, id_list in (("vector", v_ids), ("keyword", k_ids)) if chunk_id in id_list],
        )
        for chunk_id in top
    ]
    # Neighbours go after the ranked hits, in document order
    extra_sorted = sorted(extra_ids, key=lambda chunk_id: (by_id[chunk_id][1], by_id[chunk_id][6]))
    results += [build_result(chunk_id, 0.0, ["neighbour"]) for chunk_id in extra_sorted]
    return results
    
import json
import sys
from pathlib import Path

from app.db import get_conn
from app.search import search
from app.tools import read_pages

TOP_K = 10
QUESTION_LIMIT = 15   # questions per user (each one is run twice)
QUESTIONS_FILE = Path(__file__).parent / "tests" / "questions.json"


def pick_two_users():
    """The two owners with the most ready documents, with their document ids."""
    with get_conn() as connection:
        rows = connection.execute(
            "SELECT owner_id, array_agg(id) FROM documents WHERE status = 'ready' "
            "GROUP BY owner_id ORDER BY COUNT(*) DESC LIMIT 2"
        ).fetchall()
    if len(rows) < 2:
        sys.exit("Need two users who each have at least one ready document.")
    return rows[0], rows[1]


def chunk_owners(chunk_ids):
    """Map chunk id -> the owner of the document it belongs to."""
    if not chunk_ids:
        return {}
    with get_conn() as connection:
        rows = connection.execute(
            "SELECT c.id, d.owner_id FROM chunks c "
            "JOIN documents d ON d.id = c.document_id WHERE c.id = ANY(%s)",
            (list(chunk_ids),),
        ).fetchall()
    return dict(rows)


def leaked_chunk_ids(caller, results):
    """Chunks returned to `caller` that belong to someone else."""
    chunk_ids = [result["chunk_id"] for result in results]
    owners = chunk_owners(chunk_ids)
    return [chunk_id for chunk_id in chunk_ids if owners.get(chunk_id) != caller]


def main():
    (owner_a, documents_a), (owner_b, documents_b) = pick_two_users()
    items = json.loads(QUESTIONS_FILE.read_text(encoding="utf-8"))
    questions = [item["question"] for item in items][:QUESTION_LIMIT]

    # (caller, the other user's document ids)
    pairs = [(owner_a, documents_b), (owner_b, documents_a)]

    chunks_checked = 0
    normal_leaks = 0
    targeted_leaks = 0
    page_leaks = 0

    for caller, other_documents in pairs:
        for question in questions:
            # 1) Normal search: the caller must only ever get their own chunks.
            normal_results = search(question, caller, None, TOP_K)
            chunks_checked += len(normal_results)
            normal_leaks += len(leaked_chunk_ids(caller, normal_results))

            # 2) Targeted search: the caller names the OTHER user's document ids.
            targeted_results = search(question, caller, other_documents, TOP_K)
            chunks_checked += len(targeted_results)
            targeted_leaks += len(leaked_chunk_ids(caller, targeted_results))

        # 3) The agent's read_pages tool aimed at the other user's documents.
        for document_id in other_documents:
            pages, _error = read_pages(caller, document_id, 1, 1, None)
            if pages:
                page_leaks += len(pages)

    total_leaks = normal_leaks + targeted_leaks + page_leaks
    print(f"user A {str(owner_a)[:8]}... docs {documents_a}")
    print(f"user B {str(owner_b)[:8]}... docs {documents_b}")
    print(f"questions per user: {len(questions)}")
    print(f"retrieved chunks checked: {chunks_checked}")
    print(f"leaked chunks, normal search:           {normal_leaks}")
    print(f"leaked chunks, targeted at other's docs: {targeted_leaks}")
    print(f"leaked pages, read_pages on other's docs: {page_leaks}")
    print("RESULT:", "PASS (0 leaks)" if total_leaks == 0 else f"FAIL ({total_leaks} leaks)")
    sys.exit(0 if total_leaks == 0 else 1)


if __name__ == "__main__":
    main()
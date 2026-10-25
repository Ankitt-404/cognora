from fastapi import HTTPException
from psycopg.types.json import Jsonb

from app.db import get_conn


def _check_owner(conn, conversation_id, owner):
    ok = conn.execute(
        "SELECT 1 FROM conversations WHERE id = %s AND owner_id = %s",
        (conversation_id, owner),
    ).fetchone()
    if not ok:
        raise HTTPException(404, "Conversation not found.")

def create_conversation(owner, first_question):
    with get_conn() as conn:
        return conn.execute(
            "INSERT INTO conversations (owner_id, title) VALUES (%s, %s) RETURNING id",
            (owner, first_question[:60]),
        ).fetchone()[0]


def load_history(conversation_id,owner, limit=6):
    with get_conn() as conn:
        _check_owner(conn, conversation_id, owner)
        rows = conn.execute(
            """
            SELECT role, content, sources FROM messages
            WHERE conversation_id = %s
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (conversation_id, limit),
        ).fetchall()

    history = []
    for role, content, sources in reversed(rows):
        content = content[:400]
        if role == "assistant" and sources:
            used = "; ".join(f"{s['title']} p.{s['pages']}" for s in sources)
            content += f"\n(Sources: {used})"
        history.append({"role": role, "content": content})
    return history


def save_turn(conversation_id, question,owner, answer, sources):
    with get_conn() as conn:
        _check_owner(conn, conversation_id, owner)
        conn.execute(
            "INSERT INTO messages (conversation_id, role, content) VALUES (%s, 'user', %s)",
            (conversation_id, question),
        )
        conn.execute(
            "INSERT INTO messages (conversation_id, role, content, sources) "
            "VALUES (%s, 'assistant', %s, %s)",
            (conversation_id, answer, Jsonb(sources)),
        )
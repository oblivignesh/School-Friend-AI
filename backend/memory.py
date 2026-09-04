"""Long-term memory: stores each chat message with a Gemini text embedding
and retrieves the most semantically relevant past messages for a given
query via cosine similarity - so the agent "remembers" things a student
said in earlier sessions (even after logging out and back in), not just
the last few messages of the current session.

Storage is a plain SQLite table (see backend/db.py); similarity search is
brute-force cosine similarity in numpy, which is fast enough for a single
student's/small school's message history and avoids needing a native
SQLite vector-search extension.
"""
import os
import sqlite3

import numpy as np
from google import genai
from google.genai import types

EMBED_MODEL = "gemini-embedding-001"
EMBED_DIM = 768
RECALL_TOP_K = 5
# Only consider a recalled message "relevant enough" above this cosine
# similarity threshold, to avoid injecting noise for a first-ever message.
RECALL_MIN_SIMILARITY = 0.5

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not set.")
        _client = genai.Client(api_key=api_key)
    return _client


def _embed(text: str, task_type: str) -> np.ndarray | None:
    """Embed a piece of text with Gemini. Returns None on failure so a
    down/mis-configured embeddings API never blocks the chat itself -
    memory becomes a best-effort feature, not a hard dependency.
    """
    try:
        result = _get_client().models.embed_content(
            model=EMBED_MODEL,
            contents=text,
            config=types.EmbedContentConfig(
                task_type=task_type,
                output_dimensionality=EMBED_DIM,
            ),
        )
        values = np.array(result.embeddings[0].values, dtype=np.float32)
        # gemini-embedding-001 only auto-normalizes at the full 3072 dims;
        # for a truncated output_dimensionality we must normalize ourselves.
        norm = np.linalg.norm(values)
        if norm > 0:
            values = values / norm
        return values
    except Exception:
        return None


def add_message(
    conn: sqlite3.Connection, user_id: int, role: str, content: str
) -> None:
    """Persist a chat message and its embedding for later semantic recall."""
    task_type = "RETRIEVAL_QUERY" if role == "user" else "RETRIEVAL_DOCUMENT"
    embedding = _embed(content, task_type)
    conn.execute(
        "INSERT INTO messages (user_id, role, content, embedding) "
        "VALUES (?, ?, ?, ?)",
        (
            user_id,
            role,
            content,
            embedding.tobytes() if embedding is not None else None,
        ),
    )
    conn.commit()


def get_recent_history(
    conn: sqlite3.Connection, user_id: int, limit: int = 20
) -> list[dict]:
    """Most recent messages for this user, oldest first, in Anthropic's
    {"role": ..., "content": ...} message format.
    """
    rows = conn.execute(
        "SELECT role, content FROM messages WHERE user_id = ? "
        "ORDER BY id DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


def recall_relevant_memories(
    conn: sqlite3.Connection,
    user_id: int,
    query: str,
    exclude_recent: int = 20,
    top_k: int = RECALL_TOP_K,
) -> list[str]:
    """Semantic search over this user's older messages (older than the
    recency window already included in the prompt) for ones most similar
    in meaning to the current question. Returns formatted "role: content"
    strings, most relevant first.
    """
    query_embedding = _embed(query, "RETRIEVAL_QUERY")
    if query_embedding is None:
        return []

    rows = conn.execute(
        "SELECT id, role, content, embedding FROM messages "
        "WHERE user_id = ? AND embedding IS NOT NULL "
        "ORDER BY id DESC",
        (user_id,),
    ).fetchall()
    if len(rows) <= exclude_recent:
        return []
    # Skip the messages already present in the recency window to avoid
    # duplicating them in the prompt.
    candidates = rows[exclude_recent:]
    if not candidates:
        return []

    matrix = np.stack(
        [np.frombuffer(r["embedding"], dtype=np.float32) for r in candidates]
    )
    scores = matrix @ query_embedding
    top_indices = np.argsort(-scores)[:top_k]

    results = []
    for i in top_indices:
        if scores[i] < RECALL_MIN_SIMILARITY:
            continue
        row = candidates[int(i)]
        results.append(f"{row['role']}: {row['content']}")
    return results

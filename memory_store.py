"""SQLite-backed vector memory store.

Vectors are stored as JSON-encoded float lists in a TEXT column. Similarity
search is plain-Python cosine similarity — fine at demo-corpus scale, no
vector extension or numpy required.
"""

import json
import math
import sqlite3


def connect(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            chunk TEXT NOT NULL,
            embedding TEXT NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def add_chunk(conn, source, chunk, embedding):
    conn.execute(
        "INSERT INTO memories (source, chunk, embedding) VALUES (?, ?, ?)",
        (source, chunk, json.dumps(embedding)),
    )
    conn.commit()


def _cosine_similarity(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def search(conn, query_vec, k):
    rows = conn.execute("SELECT source, chunk, embedding FROM memories").fetchall()
    scored = [
        (_cosine_similarity(query_vec, json.loads(embedding)), source, chunk)
        for source, chunk, embedding in rows
    ]
    scored.sort(key=lambda row: row[0], reverse=True)
    return [
        {"score": score, "source": source, "chunk": chunk}
        for score, source, chunk in scored[:k]
    ]

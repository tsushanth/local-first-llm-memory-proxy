"""CLI: walk a folder of .txt/.md files, chunk them, embed via Ollama, and
write the resulting rows into the memory store.

Usage:
    python ingest.py sample_notes/
"""

import json
import sys
import tomllib
import urllib.request
from pathlib import Path

import memory_store


def load_config(path="config.toml"):
    with open(path, "rb") as f:
        return tomllib.load(f)


def chunk_text(text, chunk_size):
    """Naive fixed-size chunking, splitting on paragraph boundaries."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks = []
    current = ""
    for para in paragraphs:
        if current and len(current) + len(para) + 2 > chunk_size:
            chunks.append(current)
            current = para
        else:
            current = f"{current}\n\n{para}" if current else para
    if current:
        chunks.append(current)
    return chunks


def embed(host, model, text):
    payload = json.dumps({"model": model, "prompt": text}).encode("utf-8")
    req = urllib.request.Request(
        f"{host}/api/embeddings",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        body = json.loads(resp.read())
    return body["embedding"]


def main():
    if len(sys.argv) != 2:
        print("usage: python ingest.py <folder>")
        sys.exit(1)

    folder = Path(sys.argv[1])
    config = load_config()
    ollama_host = config["ollama"]["host"]
    embed_model = config["ollama"]["embed_model"]
    chunk_size = config["memory"]["chunk_size"]
    db_path = config["memory"]["db_path"]

    conn = memory_store.connect(db_path)

    files = sorted(list(folder.glob("*.md")) + list(folder.glob("*.txt")))
    if not files:
        print(f"no .md or .txt files found in {folder}")
        return

    total_chunks = 0
    for file in files:
        text = file.read_text(encoding="utf-8")
        for chunk in chunk_text(text, chunk_size):
            vector = embed(ollama_host, embed_model, chunk)
            memory_store.add_chunk(conn, str(file), chunk, vector)
            total_chunks += 1
        print(f"ingested {file}")

    print(f"done: {total_chunks} chunks written to {db_path}")


if __name__ == "__main__":
    main()

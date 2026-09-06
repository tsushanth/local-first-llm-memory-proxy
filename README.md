# Local-First LLM Memory Proxy

A local daemon that sits between your LLM client and Ollama, silently
retrieving relevant chunks from a private on-disk vector store and injecting
them into the prompt — no cloud, no accounts, zero client-side changes.

This is an MVP scaffold proving one thing: *ask the proxy something only
your notes know, and get an answer that reflects it — then show the same
question fails against the model directly.* Everything else (GUI, packaging,
paid Mac app) is downstream of this working. See `plan.md` for the full
scope and what's deliberately left out.

## Requirements

- Python 3.11+ (stdlib only — no `pip install` needed).
- [Ollama](https://ollama.com) running locally.

## Setup

```bash
ollama pull llama3.2
ollama pull nomic-embed-text
ollama serve
```

## Run

1. Ingest your notes into the local memory store:

   ```bash
   python ingest.py sample_notes/
   ```

   Verify the rows landed:

   ```bash
   sqlite3 memory.db "select source, substr(chunk,1,60) from memories;"
   ```

2. Start the proxy (listens on a different port than Ollama, see
   `config.toml`):

   ```bash
   python proxy.py
   ```

3. See the difference memory makes. First, ask Ollama directly — it has no
   idea:

   ```bash
   curl http://localhost:11434/api/chat -d '{
     "model": "llama3.2",
     "messages": [{"role": "user", "content": "what is my cats name?"}]
   }'
   ```

   Now send the *identical* request to the proxy's port instead:

   ```bash
   curl http://localhost:11435/api/chat -d '{
     "model": "llama3.2",
     "messages": [{"role": "user", "content": "what is my cats name?"}]
   }'
   ```

   Same request shape, same headers, only the port differs — the proxy
   silently retrieved the relevant chunk from `sample_notes/pets.md` and
   spliced it into the conversation before forwarding to Ollama.

## Configuration

All settings live in `config.toml`: Ollama's host, which chat/embedding
models to use, the proxy's listen port, and memory tuning (`top_k`,
`chunk_size`).

## Tests

Unit tests for the memory store run without Ollama or network access:

```bash
python -m unittest discover tests
```

## How it works

- `ingest.py` walks a folder of `.txt`/`.md` files, splits them into
  paragraph-sized chunks, embeds each chunk via Ollama's `/api/embeddings`,
  and writes the chunk + embedding into `memory.db` (SQLite).
- `memory_store.py` is the storage layer: schema, `add_chunk()`, and a
  `search()` that ranks stored chunks by cosine similarity to a query vector.
- `proxy.py` is the daemon: on every `/api/chat` request it embeds the
  latest user message, searches `memory.db` for the top matches, injects
  them as a system message, and forwards the rewritten request to Ollama's
  real `/api/chat` endpoint — returning the response unchanged.

## What's not here (yet)

Auth, billing, streaming responses, a GUI memory inspector, multi-client
support (OpenAI-compatible / LM Studio / Claude API), and packaging as a
single binary are all out of scope for this scaffold — see `plan.md` §2 for
the reasoning behind each.

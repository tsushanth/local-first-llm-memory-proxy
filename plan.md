# Local-First LLM Memory Proxy — MVP Scaffold Plan

## Goal of this MVP

Prove the one novel hook: a transparent local proxy that sits in front of an
OpenAI/Ollama-compatible chat API, silently retrieves relevant chunks from a
private on-disk vector store, and injects them into the prompt — with zero
changes required on the client side. Everything else (GUI, packaging, paid
Mac app) is downstream of proving this works and feels good to use.

## 1. Stack

**Python 3.11+, standard library only, no pip installs.**

- `http.server` — the proxy's HTTP listener (single-threaded is fine for a demo).
- `tomllib` (stdlib since 3.11) — reads `config.toml`.
- `sqlite3` (stdlib) — on-disk store for text chunks + their embedding vectors
  (vectors stored as JSON-encoded float lists in a TEXT column; no vector
  extension needed at this scale).
- `urllib.request` — calls Ollama's existing local HTTP API for both
  embeddings (`/api/embeddings`) and chat completion (`/api/chat`), and
  forwards the (possibly rewritten) request there.
- Plain Python for cosine similarity (a dozen lines, no numpy) — corpus size
  for a demo is small enough that this is not a performance concern.

Why this stack: Ollama is already installed by the exact audience we're
targeting (r/LocalLLaMA), and it already exposes an embeddings endpoint, so
we don't need to bundle or download any embedding model ourselves. Avoiding
every third-party dependency means the demo runs with nothing but a stock
Python install and `ollama serve` — no venv, no requirements.txt, no version
conflicts. This is a throwaway-if-wrong prototype; the eventual real product
(per the pitch) is a compiled single binary, likely Go — that rewrite only
happens after this scaffold proves the retrieval-injection loop is worth
shipping.

## 2. Explicitly out of scope for this MVP

- **Auth / accounts** — it's a loopback-only local daemon; nobody but the
  local user can reach it.
- **Billing / monetization** — the paid Mac app wrapper is a distribution
  decision for later, irrelevant to proving core value.
- **Hosting / deploy / CI** — runs on localhost from a checkout, nothing to
  deploy.
- **Multi-client support** — only an Ollama-style `/api/chat` endpoint is
  proxied for the demo. OpenAI-compatible `/v1/chat/completions` and
  LM Studio/Claude API support are the same pattern repeated, not new
  validation of the idea — noted as a follow-up, not built now.
- **Streaming responses** — proxy will make a non-streaming call to Ollama
  and return the full JSON body. Streaming is a real feature gap for
  day-to-day use but adds no evidence about whether memory injection works.
- **GUI / memory inspector** — the paid-app hook, but the CLI + a raw
  `sqlite3` query is enough to verify memory contents for this stage.
- **Chunking sophistication, memory pruning/expiry, re-ranking, dedup** —
  fixed-size naive chunking (e.g. split by paragraph, cap ~500 chars) is
  enough to prove retrieval-and-injection works end to end.
- **Concurrency / production hardening / error handling for malformed
  input** — single local user, single request at a time, happy-path only.
- **Packaging as a single binary** — stays a plain Python script for now;
  PyInstaller/Go port is a separate, later effort once the concept is
  validated.

None of these are needed to demonstrate the core value: *ask the proxy
something only your notes know, and get an answer that reflects it — then
show the same question fails against the model directly.*

## 3. File / directory layout

```
local-first-llm-memory-proxy/
├── plan.md                # this document
├── README.md              # setup + run-through (mirrors section 4 below)
├── config.toml             # user-editable config: ports, model names, top_k
├── ingest.py               # CLI: walk a folder of .txt/.md files, chunk,
│                           #   embed via Ollama, write rows to memory.db
├── memory_store.py         # sqlite schema/init, add_chunk(), search(query_vec, k)
├── proxy.py                # the daemon: HTTP server, on each request:
│                           #   embed last user message -> search() -> splice
│                           #   retrieved chunks into the prompt -> forward to
│                           #   Ollama -> return response
├── sample_notes/           # a few throwaway .md/.txt fixtures used to
│                           #   demo + manually verify retrieval
│   ├── pets.md
│   └── preferences.md
├── memory.db               # generated at runtime by ingest.py (gitignored)
└── tests/
    └── test_memory_store.py  # unittest, stdlib only, no Ollama required
```

## 4. Verification plan

**Automated (fast, no Ollama needed):**
- `tests/test_memory_store.py` — unit tests against `memory_store.py` using
  hand-constructed embedding vectors (e.g. simple orthogonal/near-identical
  float lists) to assert `search()` ranks the closest vector first and
  respects `top_k`. Run with `python -m unittest discover tests`.

**Manual run-through (proves the actual product experience):**
1. `ollama pull llama3.2` and `ollama pull nomic-embed-text` (one-time setup).
2. `ollama serve` running locally on its default port.
3. `python ingest.py sample_notes/` — populates `memory.db`; confirm with
   `sqlite3 memory.db "select source, substr(chunk,1,60) from memories;"`
   that rows exist.
4. `python proxy.py` — starts the proxy on a different local port than
   Ollama's.
5. Baseline (no memory): `curl` Ollama directly with a question whose answer
   only exists in `sample_notes/` (e.g. "what's my cat's name?") and observe
   the model has no idea.
6. Through the proxy: send the identical `curl` request to the proxy's port
   instead, and confirm the answer now reflects the injected fact — this
   side-by-side is the entire pitch in one terminal.
7. Confirm zero client-side changes were needed: same request shape, same
   headers, only the port differs — showing the "works with any client
   immediately" claim holds.

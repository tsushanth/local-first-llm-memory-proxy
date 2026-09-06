"""The proxy daemon.

Listens on `proxy.port` and speaks Ollama's `/api/chat` shape. On each
request it embeds the last user message, searches the local memory store for
relevant chunks, splices them into the conversation as a system message, and
forwards the (rewritten) request to the real Ollama server — then returns
Ollama's response unchanged. Non-streaming only; single request at a time.
"""

import json
import tomllib
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

import memory_store
from ingest import embed


def load_config(path="config.toml"):
    with open(path, "rb") as f:
        return tomllib.load(f)


CONFIG = load_config()
OLLAMA_HOST = CONFIG["ollama"]["host"]
EMBED_MODEL = CONFIG["ollama"]["embed_model"]
TOP_K = CONFIG["memory"]["top_k"]
DB_PATH = CONFIG["memory"]["db_path"]


def last_user_message(messages):
    for message in reversed(messages):
        if message.get("role") == "user":
            return message.get("content", "")
    return ""


def build_memory_system_message(chunks):
    if not chunks:
        return None
    bullet_points = "\n".join(f"- {c['chunk']}" for c in chunks)
    content = (
        "The following facts are retrieved from the user's private notes. "
        "Use them if relevant when answering:\n" + bullet_points
    )
    return {"role": "system", "content": content}


def forward_to_ollama(body):
    payload = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        f"{OLLAMA_HOST}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        return resp.read(), resp.status


class ProxyHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/api/chat":
            self.send_response(404)
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length))
        body["stream"] = False

        messages = body.get("messages", [])
        query = last_user_message(messages)

        conn = memory_store.connect(DB_PATH)
        if query:
            query_vec = embed(OLLAMA_HOST, EMBED_MODEL, query)
            chunks = memory_store.search(conn, query_vec, TOP_K)
        else:
            chunks = []

        system_message = build_memory_system_message(chunks)
        if system_message:
            body["messages"] = [system_message] + messages

        response_body, status = forward_to_ollama(body)

        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(response_body)

    def log_message(self, format, *args):
        print(f"[proxy] {self.address_string()} - {format % args}")


def main():
    port = CONFIG["proxy"]["port"]
    server = HTTPServer(("127.0.0.1", port), ProxyHandler)
    print(f"memory proxy listening on http://127.0.0.1:{port}")
    print(f"forwarding to ollama at {OLLAMA_HOST}")
    server.serve_forever()


if __name__ == "__main__":
    main()

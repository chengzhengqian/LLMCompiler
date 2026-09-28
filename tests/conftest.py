"""Shared fixtures: a throwaway project and a fake Ollama server."""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from ic import config


def reply_text(intent="Counts things.", spec="## Representation\nAn Int.",
               choices="- chose Int", questions="none") -> str:
    return (f"=== INTENT ===\n{intent}\n\n=== SPEC ===\n{spec}\n\n"
            f"=== CHOICES ===\n{choices}\n\n=== QUESTIONS ===\n{questions}\n")


class FakeOllama:
    """Streams a queued reply per /api/chat request, in small chunks."""

    def __init__(self):
        self.replies = []          # list of str, or dict lines to send verbatim
        self.requests = []
        self.models = ["test-model"]
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                body = json.dumps({"models": [{"name": m} for m in fake.models]}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                n = int(self.headers["Content-Length"])
                fake.requests.append(json.loads(self.rfile.read(n)))
                reply = fake.replies.pop(0) if fake.replies else reply_text()
                self.send_response(200)
                self.send_header("Content-Type", "application/x-ndjson")
                self.end_headers()
                if isinstance(reply, list):
                    lines = reply
                else:
                    step = 7
                    lines = [{"message": {"content": reply[i:i + step]}, "done": False}
                             for i in range(0, len(reply), step)]
                    lines.append({"done": True, "eval_count": len(lines),
                                  "eval_duration": 2_000_000_000,
                                  "prompt_eval_count": 50, "prompt_eval_duration": 10**8})
                for line in lines:
                    self.wfile.write((json.dumps(line) + "\n").encode())
                    self.wfile.flush()

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, args=(0.01,), daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def ollama():
    fake = FakeOllama()
    yield fake
    fake.close()


@pytest.fixture
def project(tmp_path, ollama):
    """A project root with ic.toml pointing at the fake server, and one unit."""
    (tmp_path / "ic.toml").write_text(
        f'language = "julia"\n\n[endpoints.fake]\nurl = "{ollama.url}"\nmodel = "test-model"\n'
        f'\n[endpoints.other]\nurl = "{ollama.url}"\nmodel = "other-model"\n'
        f'\n[stages]\nplan = "fake"\n')
    (tmp_path / "units" / "counter").mkdir(parents=True)
    (tmp_path / "units" / "counter" / "input.md").write_text("A counter.\n")
    return tmp_path


@pytest.fixture
def cfg(project):
    return config.load(project)

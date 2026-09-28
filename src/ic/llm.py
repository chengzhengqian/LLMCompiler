"""Minimal Ollama client (standard library only)."""

import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from .config import Endpoint


@dataclass
class StreamStats:
    """What arrived on the wire, and when. Times are seconds since the request."""
    headers: float | None = None                  # response headers received
    reads: list = field(default_factory=list)     # (t, bytes, lines completed)
    lines: list = field(default_factory=list)     # (t, bytes) per JSON line

    def to_dict(self) -> dict:
        r3 = lambda x: round(x, 4)
        return {
            "headers": r3(self.headers) if self.headers is not None else None,
            "reads": [[r3(t), b, n] for t, b, n in self.reads],
            "lines": [[r3(t), b] for t, b in self.lines],
        }


@dataclass
class Reply:
    text: str
    thinking: str
    seconds: float
    eval_count: int | None             # generated tokens (exact, from Ollama)
    eval_seconds: float | None         # time spent generating
    prompt_count: int | None           # prompt tokens processed
    prompt_seconds: float | None       # time spent on the prompt
    load_seconds: float | None = None  # time spent loading the model into memory
    stream: StreamStats = field(default_factory=StreamStats)

    @property
    def rate(self) -> float | None:
        if self.eval_count and self.eval_seconds:
            return self.eval_count / self.eval_seconds
        return None


def _post(url: str, payload: dict, timeout: float):
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    return urllib.request.urlopen(req, timeout=timeout)


def chat(endpoint: Endpoint, system: str, user: str,
         on_chunk=None, timeout: float = 900) -> Reply:
    """Send one system+user exchange.

    on_chunk(kind, text) is called for every streamed piece, with kind
    "thinking" (separate reasoning channel) or "content".
    """
    payload = {
        "model": endpoint.model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": True,
    }
    if endpoint.think is not None:
        payload["think"] = endpoint.think
    if endpoint.options:
        payload["options"] = endpoint.options

    content, thinking, final = [], [], {}
    stats = StreamStats()

    def handle(line: bytes) -> bool:
        """Process one JSON line; True when the stream is finished."""
        nonlocal final
        line = line.strip()
        if not line:
            return False
        chunk = json.loads(line)
        if "error" in chunk:
            raise RuntimeError(f"ollama: {chunk['error']}")
        msg = chunk.get("message", {})
        if msg.get("thinking"):
            thinking.append(msg["thinking"])
            if on_chunk:
                on_chunk("thinking", msg["thinking"])
        if msg.get("content"):
            content.append(msg["content"])
            if on_chunk:
                on_chunk("content", msg["content"])
        if chunk.get("done"):
            final = chunk
            return True
        return False

    t0 = time.monotonic()
    try:
        with _post(f"{endpoint.url}/api/chat", payload, timeout) as resp:
            stats.headers = time.monotonic() - t0
            buf, done = b"", False
            while not done:
                # read1 returns whatever has arrived (up to the limit) without
                # waiting to fill the buffer, so each call is one delivery.
                data = resp.read1(65536)
                if not data:
                    break
                t = time.monotonic() - t0
                buf += data
                *complete, buf = buf.split(b"\n")
                stats.reads.append((t, len(data), len(complete)))
                for raw in complete:
                    stats.lines.append((t, len(raw) + 1))
                    if handle(raw):
                        done = True
                        break
            if not done and buf.strip():
                stats.lines.append((time.monotonic() - t0, len(buf)))
                handle(buf)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"ollama HTTP {e.code}: {e.read().decode(errors='replace')}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"cannot reach {endpoint.url} ({e.reason}) — is the port forward up?")

    text = "".join(content)
    # Some models inline their reasoning; keep it out of the artifact.
    inline = re.findall(r"<think>(.*?)</think>", text, flags=re.S)
    if inline:
        thinking.extend(inline)
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)

    return Reply(
        text=text.strip(),
        thinking="".join(thinking).strip(),
        seconds=time.monotonic() - t0,
        eval_count=final.get("eval_count"),
        eval_seconds=_ns(final.get("eval_duration")),
        prompt_count=final.get("prompt_eval_count"),
        prompt_seconds=_ns(final.get("prompt_eval_duration")),
        load_seconds=_ns(final.get("load_duration")),
        stream=stats,
    )


def _ns(value) -> float | None:
    return value / 1e9 if value else None


def list_models(endpoint: Endpoint, timeout: float = 5) -> list[str]:
    """Names of models available at the endpoint (GET /api/tags)."""
    try:
        with urllib.request.urlopen(f"{endpoint.url}/api/tags", timeout=timeout) as resp:
            data = json.load(resp)
    except (urllib.error.URLError, TimeoutError) as e:
        raise RuntimeError(f"cannot reach {endpoint.url} ({getattr(e, 'reason', e)})")
    return [m["name"] for m in data.get("models", [])]

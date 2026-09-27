"""Minimal Ollama client (standard library only)."""

import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

from .config import Endpoint


@dataclass
class Reply:
    text: str
    thinking: str
    seconds: float
    eval_count: int | None


def _post(url: str, payload: dict, timeout: float):
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    return urllib.request.urlopen(req, timeout=timeout)


def chat(endpoint: Endpoint, system: str, user: str,
         stream_to=None, timeout: float = 900) -> Reply:
    """Send one system+user exchange; stream content to stream_to if given."""
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
    t0 = time.monotonic()
    try:
        with _post(f"{endpoint.url}/api/chat", payload, timeout) as resp:
            for raw in resp:
                line = raw.strip()
                if not line:
                    continue
                chunk = json.loads(line)
                if "error" in chunk:
                    raise RuntimeError(f"ollama: {chunk['error']}")
                msg = chunk.get("message", {})
                if msg.get("thinking"):
                    thinking.append(msg["thinking"])
                if msg.get("content"):
                    content.append(msg["content"])
                    if stream_to:
                        stream_to.write(msg["content"])
                        stream_to.flush()
                if chunk.get("done"):
                    final = chunk
                    break
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
    )


def list_models(endpoint: Endpoint, timeout: float = 5) -> list[str]:
    """Names of models available at the endpoint (GET /api/tags)."""
    try:
        with urllib.request.urlopen(f"{endpoint.url}/api/tags", timeout=timeout) as resp:
            data = json.load(resp)
    except (urllib.error.URLError, TimeoutError) as e:
        raise RuntimeError(f"cannot reach {endpoint.url} ({getattr(e, 'reason', e)})")
    return [m["name"] for m in data.get("models", [])]

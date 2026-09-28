import pytest

from ic.config import Endpoint
from ic.llm import chat, list_models


def ep(url, **kw):
    return Endpoint(name="t", url=url, model="test-model", **kw)


def test_chat_streams_and_collects(ollama):
    ollama.replies.append("hello world, streamed in pieces")
    seen = []
    reply = chat(ep(ollama.url), "sys", "usr", on_chunk=lambda k, t: seen.append((k, t)))
    assert reply.text == "hello world, streamed in pieces"
    assert "".join(t for _, t in seen) == reply.text
    assert reply.eval_count and reply.rate and reply.prompt_count == 50
    assert reply.stream.lines and reply.stream.headers is not None
    req = ollama.requests[0]
    assert req["messages"] == [{"role": "system", "content": "sys"},
                               {"role": "user", "content": "usr"}]
    assert "think" not in req and "options" not in req


def test_chat_sends_think_and_options(ollama):
    chat(ep(ollama.url, think=False, options={"num_ctx": 8192}), "s", "u")
    assert ollama.requests[0]["think"] is False
    assert ollama.requests[0]["options"] == {"num_ctx": 8192}


def test_thinking_channel_and_inline_think(ollama):
    ollama.replies.append([
        {"message": {"thinking": "hmm "}},
        {"message": {"content": "<think>inline</think>answer"}},
        {"done": True},
    ])
    reply = chat(ep(ollama.url), "s", "u")
    assert reply.text == "answer"
    assert reply.thinking == "hmm inline"


def test_error_chunk_raises(ollama):
    ollama.replies.append([{"error": "model not loaded"}])
    with pytest.raises(RuntimeError, match="model not loaded"):
        chat(ep(ollama.url), "s", "u")


def test_unreachable():
    with pytest.raises(RuntimeError, match="cannot reach"):
        chat(ep("http://127.0.0.1:9"), "s", "u", timeout=2)
    with pytest.raises(RuntimeError, match="cannot reach"):
        list_models(ep("http://127.0.0.1:9"))


def test_list_models(ollama):
    assert list_models(ep(ollama.url)) == ["test-model"]

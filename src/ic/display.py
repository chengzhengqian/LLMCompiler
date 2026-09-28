"""A single self-overwriting status line for streaming LLM output.

    ⠹ writing  412 tok  18.3 tok/s  31s │ … Pinned examples ⏎ index(0b0011) == 1

Redraws on a timer, so the spinner and clock keep moving while the model is
still processing the prompt and no token has arrived yet. Token counts here
are approximate (one streamed chunk ≈ one token); exact figures come from
Ollama's final statistics.
"""

import shutil
import sys
import threading
import time
import unicodedata

SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
CLEAR = "\r\x1b[2K"


def _width(s: str) -> int:
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def _fit_end(s: str, width: int) -> str:
    """Keep the end of s, in at most `width` terminal columns."""
    out, used = [], 0
    for c in reversed(s):
        w = 2 if unicodedata.east_asian_width(c) in "WF" else 1
        if used + w > width:
            break
        out.append(c)
        used += w
    return "".join(reversed(out))


class LiveLine:
    def __init__(self, stream=sys.stderr, interval: float = 0.1):
        self.stream = stream
        self.interval = interval
        self.enabled = hasattr(stream, "isatty") and stream.isatty()
        self.t0 = time.monotonic()
        self.first = None
        self.count = 0
        self.phase = "waiting"
        self.tail = ""
        self._inline_think = False
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        self._tick = 0

    def __enter__(self):
        if self.enabled:
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        if self._thread:
            self._thread.join()
        if self.enabled:
            with self._lock:
                self.stream.write(CLEAR)
                self.stream.flush()
        return False

    def feed(self, kind: str, text: str) -> None:
        with self._lock:
            if self.first is None:
                self.first = time.monotonic()
            if kind == "content":
                # Models that inline their reasoning in <think> tags.
                if "<think>" in text:
                    self._inline_think = True
                kind = "thinking" if self._inline_think else "content"
                if "</think>" in text:
                    self._inline_think = False
            self.phase = "thinking" if kind == "thinking" else "writing"
            self.count += 1
            self.tail = (self.tail + text)[-400:]

    def _render(self) -> str:
        now = time.monotonic()
        spin = SPINNER[self._tick % len(SPINNER)]
        elapsed = now - self.t0
        if self.first is None:
            status = f"{spin} waiting for first token  {elapsed:.0f}s"
        else:
            gen = now - self.first
            rate = f"{self.count / gen:.1f} tok/s" if gen > 0.5 else "-- tok/s"
            status = f"{spin} {self.phase}  {self.count} tok  {rate}  {elapsed:.0f}s"
        cols = shutil.get_terminal_size((100, 20)).columns - 1
        room = cols - _width(status) - 3
        if room < 8 or not self.tail:
            return _fit_end(status, cols)
        tail = " ".join(self.tail.replace("\n", " ⏎ ").split())
        return f"{status} │ {_fit_end(tail, room)}"

    def _loop(self) -> None:
        while not self._stop.wait(self.interval):
            with self._lock:
                self._tick += 1
                self.stream.write(CLEAR + self._render())
                self.stream.flush()


def summary(reply) -> str:
    """One-line recap using Ollama's exact statistics when available."""
    parts = []
    if reply.eval_count:
        s = f"generated {reply.eval_count} tok"
        if reply.eval_seconds:
            s += f" in {reply.eval_seconds:.1f}s ({reply.rate:.1f} tok/s)"
        parts.append(s)
    if reply.prompt_count:
        s = f"prompt {reply.prompt_count} tok"
        if reply.prompt_seconds:
            s += f" in {reply.prompt_seconds:.1f}s"
        parts.append(s)
    if reply.load_seconds and reply.load_seconds >= 0.5:
        parts.append(f"model load {reply.load_seconds:.1f}s")
    parts.append(f"total {reply.seconds:.1f}s")
    return " · ".join(parts)


def _pct(sorted_vals: list, q: float):
    return sorted_vals[min(len(sorted_vals) - 1, int(q * len(sorted_vals)))]


def _kb(n: int) -> str:
    return f"{n / 1024:.1f} KB" if n >= 1024 else f"{n} B"


def stream_report(stats) -> str:
    """Concrete picture of how the reply arrived: sizes, counts, intervals.

    Smooth streaming shows one line per read and read intervals near the
    per-token time. Upstream buffering shows up as few reads carrying many
    lines each, with long gaps between them.
    """
    if not stats.reads:
        return "stream   nothing received"
    total = sum(b for _, b, _ in stats.reads)
    first_line = stats.lines[0][0] if stats.lines else None
    head = (f"stream   {len(stats.lines)} json lines · {_kb(total)} · {len(stats.reads)} reads"
            f" · headers {stats.headers:.2f}s")
    if first_line is not None:
        head += f" · first line {first_line:.2f}s · last {stats.lines[-1][0]:.2f}s"
    out = [head]

    sizes = sorted(b for _, b in stats.lines)
    if sizes:
        out.append(f"  line size       min {sizes[0]} · median {_pct(sizes, .5)}"
                   f" · max {sizes[-1]} B")

    times = [t for t, _, _ in stats.reads]
    gaps = sorted((b - a) * 1000 for a, b in zip(times, times[1:]))
    if gaps:
        out.append(f"  read interval   min {gaps[0]:.0f} · median {_pct(gaps, .5):.0f}"
                   f" · p90 {_pct(gaps, .9):.0f} · max {gaps[-1]:.0f} ms")

    per_read = [n for _, _, n in stats.reads]
    single = sum(1 for n in per_read if n <= 1)
    out.append(f"  lines per read  ≤1 in {100 * single / len(per_read):.0f}% of reads"
               f" · max {max(per_read)}")
    return "\n".join(out)

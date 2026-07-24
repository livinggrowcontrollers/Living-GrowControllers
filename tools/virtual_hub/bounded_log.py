from collections import deque
from threading import Lock
from typing import Deque, Iterable, Optional


class BoundedLogBuffer:
    """Thread-sicherer, größenbegrenzter Puffer für gebündelte UI-Updates."""

    def __init__(
        self,
        max_lines: int,
        initial_lines: Iterable[str] = (),
    ):
        if max_lines < 1:
            raise ValueError("max_lines muss mindestens 1 sein.")

        self._max_lines = max_lines
        self._lines: Deque[str] = deque(maxlen=max_lines)
        self._pending: Deque[str] = deque(maxlen=max_lines)
        self._lock = Lock()
        self._lines.extend(str(line) for line in initial_lines)

    def append(self, line: str) -> None:
        with self._lock:
            self._pending.append(str(line))

    def drain_text(self) -> Optional[str]:
        with self._lock:
            if not self._pending:
                return None
            self._lines.extend(self._pending)
            self._pending.clear()
            return "\n".join(self._lines) + "\n"

    def snapshot(self) -> tuple[str, ...]:
        with self._lock:
            combined = (*self._lines, *self._pending)
            return tuple(combined[-self._max_lines:])

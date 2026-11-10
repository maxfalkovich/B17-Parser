"""Serialize public-site requests and persist pacing and access cooldowns."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import json
import math
import os
from pathlib import Path
import random
import tempfile
import threading
import time
from typing import Callable, Iterator


_THREAD_LOCKS: dict[str, threading.Lock] = {}
_THREAD_LOCKS_GUARD = threading.Lock()


class CooldownError(RuntimeError):
    """An earlier access denial prevents another automatic request for now."""


def _number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite nonnegative number")
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise ValueError(f"{name} must be a finite nonnegative number")
    return result


class AccessGate:
    """Coordinate requests from processes using the same state path on Unix.

    The caller must hold ``slot()`` throughout each complete HTTP request or
    browser navigation. No request may begin before the persisted spacing has
    elapsed. A cooldown raises immediately instead of waiting or bypassing it.
    ``block()`` records a denial inside or outside a slot and never reduces a
    cooldown already recorded by another caller.

    Delay and jitter are in seconds; a slot uses delay plus a random value in
    [0, jitter]. The interval starts again when the request finishes, so slow
    responses cannot accidentally consume the pause. A start-time write also
    retains a minimum pause if the process stops before its request finishes.
    Different state paths do not coordinate and must not be used to circumvent
    the shared pacing. The file lock is held across the request, not just writes.
    """

    def __init__(
        self,
        state_path: str | Path,
        delay: float = 15,
        jitter: float = 5,
        clock: Callable[[], float] = time.time,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.state_path = Path(state_path).expanduser().resolve()
        self.lock_path = self.state_path.with_name(self.state_path.name + ".lock")
        self.delay = _number(delay, "delay")
        self.jitter = _number(jitter, "jitter")
        self.clock, self.sleep = clock, sleep
        self._owner: int | None = None
        self._active_state: dict | None = None
        with _THREAD_LOCKS_GUARD:
            self._thread_lock = _THREAD_LOCKS.setdefault(str(self.state_path), threading.Lock())

    @contextmanager
    def _locked(self) -> Iterator[None]:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        with self._thread_lock:
            with self.lock_path.open("a", encoding="utf-8") as lock_file:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def _read(self) -> dict:
        if not self.state_path.exists():
            return {"version": 1, "next_allowed_at": 0.0, "cooldown_until": 0.0}
        try:
            state = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError("Invalid shared access state; requests are stopped") from exc
        if not isinstance(state, dict) or state.get("version") != 1:
            raise ValueError("Unsupported shared access state; requests are stopped")
        for field in ("next_allowed_at", "cooldown_until"):
            if field not in state:
                raise ValueError(f"Missing {field} in shared access state; requests are stopped")
            _number(state[field], field)
        for field in ("last_request_started_at", "last_request_finished_at"):
            if field in state:
                _number(state[field], field)
        return state

    def _write(self, state: dict) -> None:
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self.state_path.parent,
                prefix=self.state_path.name + ".", suffix=".tmp", delete=False,
            ) as output:
                temporary = output.name
                json.dump(state, output, ensure_ascii=False, indent=2, allow_nan=False)
                output.write("\n")
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, self.state_path)
            temporary = None
        finally:
            if temporary is not None:
                Path(temporary).unlink(missing_ok=True)

    def _check_cooldown(self, state: dict, now: float) -> None:
        until = state["cooldown_until"]
        if until > now:
            timestamp = datetime.fromtimestamp(until, timezone.utc).isoformat()
            raise CooldownError(f"Shared access cooldown is active until {timestamp}; no request was made")

    @contextmanager
    def slot(self) -> Iterator[None]:
        """Reserve one complete network operation after spacing, or fail closed.

        Keep the context open until the response or navigation finishes. Body
        exceptions still persist the ending pause and are propagated unchanged.
        A nested slot on the same gate is rejected; use ``block()`` to record
        an access denial while the current slot remains open.
        """
        if self._owner == threading.get_ident():
            raise RuntimeError("Nested request slots are not supported")
        with self._locked():
            state = self._read()
            now = self.clock()
            self._check_cooldown(state, now)
            previous_events = [state[field] for field in ("last_request_started_at", "last_request_finished_at")
                               if field in state]
            if previous_events:
                # A caller with a larger configured interval also observes its
                # own minimum after a preceding caller used a shorter interval.
                state["next_allowed_at"] = max(
                    state["next_allowed_at"], max(previous_events) + self.delay,
                )
            while state["next_allowed_at"] > now:
                self.sleep(min(30.0, state["next_allowed_at"] - now))
                now = self.clock()
                self._check_cooldown(state, now)
            gap = self.delay + random.uniform(0, self.jitter)
            state["last_request_started_at"] = now
            state["next_allowed_at"] = max(state["next_allowed_at"], now + gap)
            self._write(state)
            self._owner = threading.get_ident()
            self._active_state = state
            try:
                yield
            finally:
                try:
                    finished = self.clock()
                    state["last_request_finished_at"] = finished
                    state["next_allowed_at"] = max(state["next_allowed_at"], finished + gap)
                    self._write(state)
                finally:
                    self._active_state = None
                    self._owner = None

    def block(self, seconds: float = 3600) -> float:
        """Persist an access cooldown and return its expiry as a Unix timestamp.

        This method does not retry, sleep for the cooldown, or clear an existing
        block. The caller should stop its collection after recording a denial.
        """
        seconds = _number(seconds, "cooldown seconds")
        if seconds == 0:
            raise ValueError("Cooldown seconds must be greater than zero")

        def apply(state: dict) -> float:
            until = max(state["cooldown_until"], self.clock() + seconds)
            state["cooldown_until"] = until
            state["next_allowed_at"] = max(state["next_allowed_at"], until)
            self._write(state)
            return until

        if self._owner == threading.get_ident() and self._active_state is not None:
            return apply(self._active_state)
        with self._locked():
            return apply(self._read())

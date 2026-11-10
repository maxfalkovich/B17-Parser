"""Shared pacing contracts without any network access."""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from b17_parser import pacing
from b17_parser.pacing import AccessGate, CooldownError


class FakeTime:
    def __init__(self, now=1000.0):
        self.now = now
        self.sleeps = []

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


def make_gate(path, fake, **kwargs):
    return AccessGate(path, clock=fake.clock, sleep=fake.sleep, **kwargs)


def read_state(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_default_delay_and_jitter_persist_before_and_after_request(tmp_path, monkeypatch):
    fake = FakeTime()
    path = tmp_path / "work" / "access-state.json"
    monkeypatch.setattr(pacing.random, "uniform", lambda minimum, maximum: maximum)
    gate = make_gate(path, fake)
    with gate.slot():
        started = read_state(path)
        assert started["last_request_started_at"] == 1000
        assert started["next_allowed_at"] == 1020
        fake.now += 8
    finished = read_state(path)
    assert finished["last_request_finished_at"] == 1008
    assert finished["next_allowed_at"] == 1028
    with make_gate(path, fake).slot():
        assert fake.now == 1028
    assert fake.sleeps == [20]


def test_pause_is_shared_between_instances_and_counts_from_response_end(tmp_path):
    fake = FakeTime()
    path = tmp_path / "access-state.json"
    with make_gate(path, fake, delay=15, jitter=0).slot():
        fake.now += 12
    with make_gate(path, fake, delay=15, jitter=0).slot():
        assert fake.now == 1027
    assert fake.sleeps == [15]


def test_larger_configured_minimum_is_respected_after_shorter_previous_pause(tmp_path):
    fake = FakeTime()
    path = tmp_path / "access-state.json"
    with make_gate(path, fake, delay=2, jitter=0).slot():
        pass
    with make_gate(path, fake, delay=15, jitter=0).slot():
        assert fake.now == 1015


def test_waiting_is_split_into_at_most_30_second_chunks(tmp_path):
    fake = FakeTime()
    path = tmp_path / "access-state.json"
    gate = make_gate(path, fake, delay=75, jitter=0)
    with gate.slot():
        pass
    with gate.slot():
        assert fake.now == 1075
    assert fake.sleeps == [30, 30, 15]


def test_block_inside_slot_persists_and_other_instance_fails_without_waiting(tmp_path):
    fake = FakeTime()
    path = tmp_path / "access-state.json"
    gate = make_gate(path, fake, delay=15, jitter=0)
    with gate.slot():
        assert gate.block() == 4600
        assert read_state(path)["cooldown_until"] == 4600
    fake.now += 30
    with pytest.raises(CooldownError, match="no request was made"):
        with make_gate(path, fake).slot():
            pytest.fail("A blocked gate yielded a network slot")
    assert fake.sleeps == []
    assert read_state(path)["last_request_started_at"] == 1000


def test_block_outside_slot_does_not_shorten_existing_cooldown(tmp_path):
    fake = FakeTime()
    path = tmp_path / "access-state.json"
    gate = make_gate(path, fake, delay=15, jitter=0)
    assert gate.block(3600) == 4600
    fake.now += 10
    assert make_gate(path, fake).block(60) == 4600
    with pytest.raises(CooldownError):
        with gate.slot():
            pass
    assert fake.sleeps == []


def test_slot_is_available_after_cooldown_expires(tmp_path):
    fake = FakeTime()
    path = tmp_path / "access-state.json"
    gate = make_gate(path, fake, delay=15, jitter=0)
    gate.block(3600)
    fake.now = 4600
    with gate.slot():
        assert fake.now == 4600
    assert fake.sleeps == []


def test_body_exception_keeps_spacing_and_releases_lock(tmp_path):
    fake = FakeTime()
    path = tmp_path / "access-state.json"
    gate = make_gate(path, fake, delay=15, jitter=0)
    with pytest.raises(RuntimeError, match="request failure"):
        with gate.slot():
            fake.now += 4
            raise RuntimeError("request failure")
    assert read_state(path)["next_allowed_at"] == 1019
    with gate.slot():
        assert fake.now == 1019


def test_nested_slot_is_rejected_without_deadlock(tmp_path):
    fake = FakeTime()
    gate = make_gate(tmp_path / "access-state.json", fake, delay=15, jitter=0)
    with gate.slot():
        with pytest.raises(RuntimeError, match="Nested"):
            with gate.slot():
                pass


@pytest.mark.parametrize("contents", ["{", "[]", "{}", '{"version":2}',
    '{"version":1,"next_allowed_at":NaN,"cooldown_until":0}',
    '{"version":1,"next_allowed_at":0,"cooldown_until":true}'])
def test_corrupt_state_fails_before_any_request_or_wait(tmp_path, contents):
    fake = FakeTime()
    path = tmp_path / "access-state.json"
    path.write_text(contents, encoding="utf-8")
    with pytest.raises(ValueError):
        with make_gate(path, fake).slot():
            pytest.fail("Invalid state yielded a network slot")
    assert fake.sleeps == []


@pytest.mark.parametrize("name,value", [("delay", -1), ("jitter", -1), ("delay", float("nan")),
    ("jitter", float("inf")), ("delay", True)])
def test_invalid_intervals_are_rejected(tmp_path, name, value):
    with pytest.raises(ValueError):
        AccessGate(tmp_path / "access-state.json", **{name: value})


def test_separate_processes_cannot_overlap_slots(tmp_path):
    path = tmp_path / "access-state.json"
    script = """
import json,sys,time
from b17_parser.pacing import AccessGate
with AccessGate(sys.argv[1],delay=0.06,jitter=0).slot():
    start=time.time()
    time.sleep(0.08)
    end=time.time()
print(json.dumps([start,end]))
"""
    env = dict(os.environ)
    project = str(Path(__file__).resolve().parents[1])
    env["PYTHONPATH"] = project + os.pathsep + env.get("PYTHONPATH", "")
    processes = [subprocess.Popen([sys.executable, "-c", script, str(path)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env) for _ in range(2)]
    intervals = []
    for process in processes:
        stdout, stderr = process.communicate(timeout=10)
        assert process.returncode == 0, stderr
        intervals.append(json.loads(stdout))
    first, second = sorted(intervals)
    assert second[0] >= first[1] + 0.05
    state = read_state(path)
    assert state["last_request_finished_at"] >= second[1]

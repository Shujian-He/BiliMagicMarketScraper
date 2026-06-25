import sys
from datetime import datetime, timedelta
from pathlib import Path
from threading import Event

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tools
from tools import (
    RequestError,
    ResponseError,
    check_and_sleep,
    load_checkpoint,
    random_sleep,
    send_request,
    wait_or_stop,
    write_checkpoint,
)


class FakeResponse:
    def __init__(self, status_code, payload=None, headers=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}
        self.text = text

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class FakeSession:
    def __init__(self, outcomes):
        self.outcomes = iter(outcomes)
        self.calls = []

    def post(self, url, *, headers, json, timeout):
        self.calls.append(
            {
                "url": url,
                "headers": headers,
                "json": json,
                "timeout": timeout,
            }
        )
        outcome = next(self.outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def test_send_request_retries_timeout_then_succeeds():
    sleeps = []
    logs = []
    session = FakeSession(
        [
            requests.Timeout("slow"),
            FakeResponse(200, {"code": 0, "data": {"data": [], "nextId": None}}),
        ]
    )

    result = send_request(
        session,
        "https://example.invalid",
        {"x-test": "1"},
        {"page": 1},
        sleep=sleeps.append,
        jitter=lambda _low, _high: 0,
        log=logs.append,
    )

    assert result == {"code": 0, "data": {"data": [], "nextId": None}}
    assert len(session.calls) == 2
    assert session.calls[0]["timeout"] == (5, 15)
    assert sleeps == [1]
    assert "attempt 1" in logs[0]
    assert "slow" in logs[0]


def test_send_request_uses_retry_after_for_429():
    sleeps = []
    logs = []
    session = FakeSession(
        [
            FakeResponse(429, headers={"Retry-After": "3"}, text="rate limited"),
            FakeResponse(200, {"code": 0, "data": {"data": [], "nextId": None}}),
        ]
    )

    result = send_request(
        session,
        "https://example.invalid",
        {},
        {},
        sleep=sleeps.append,
        jitter=lambda _low, _high: 0,
        log=logs.append,
    )

    assert result["code"] == 0
    assert sleeps == [3.0]
    assert "Retry-After" in logs[0]


def test_send_request_retries_5xx_with_exponential_backoff():
    sleeps = []
    session = FakeSession(
        [
            FakeResponse(503, text="unavailable"),
            FakeResponse(502, text="bad gateway"),
            FakeResponse(200, {"code": 0, "data": {"data": [], "nextId": None}}),
        ]
    )

    send_request(
        session,
        "https://example.invalid",
        {},
        {},
        sleep=sleeps.append,
        jitter=lambda _low, _high: 0,
        log=lambda _message: None,
    )

    assert sleeps == [1, 2]


def test_send_request_does_not_retry_regular_4xx():
    session = FakeSession([FakeResponse(403, text="forbidden")])

    with pytest.raises(RequestError, match="HTTP 403"):
        send_request(session, "https://example.invalid", {}, {}, log=lambda _message: None)

    assert len(session.calls) == 1


def test_send_request_rejects_invalid_json_without_retrying():
    session = FakeSession([FakeResponse(200, ValueError("bad json"))])

    with pytest.raises(ResponseError, match="valid JSON"):
        send_request(session, "https://example.invalid", {}, {}, log=lambda _message: None)

    assert len(session.calls) == 1


def test_send_request_rejects_non_mapping_json_without_retrying():
    session = FakeSession([FakeResponse(200, ["not", "a", "dict"])])

    with pytest.raises(ResponseError, match="JSON object"):
        send_request(session, "https://example.invalid", {}, {}, log=lambda _message: None)

    assert len(session.calls) == 1


def test_send_request_stops_after_max_attempts():
    sleeps = []
    session = FakeSession([requests.Timeout("slow")] * 3)

    with pytest.raises(RequestError, match="after 3 attempts"):
        send_request(
            session,
            "https://example.invalid",
            {},
            {},
            sleep=sleeps.append,
            jitter=lambda _low, _high: 0,
            log=lambda _message: None,
        )

    assert len(session.calls) == 3
    assert sleeps == [1, 2]


def test_load_and_write_checkpoint_round_trip_and_clear(tmp_path):
    checkpoint = tmp_path / "nextId.txt"

    assert load_checkpoint(checkpoint) is None

    write_checkpoint(" next-42 \n", checkpoint)
    assert load_checkpoint(checkpoint) == "next-42"

    write_checkpoint(None, checkpoint)
    assert checkpoint.read_text() == ""
    assert load_checkpoint(checkpoint) is None


def test_write_checkpoint_uses_os_replace(tmp_path, monkeypatch):
    checkpoint = tmp_path / "nextId.txt"
    calls = []
    original_replace = tools.os.replace

    def spy_replace(src, dst):
        calls.append((src, dst))
        original_replace(src, dst)

    monkeypatch.setattr(tools.os, "replace", spy_replace)

    write_checkpoint("abc123", checkpoint)

    assert checkpoint.read_text() == "abc123"
    assert len(calls) == 1
    src, dst = calls[0]
    assert dst == str(checkpoint)
    assert tools.os.path.dirname(src) == str(tmp_path)


def test_wait_or_stop_uses_sleep_without_event():
    sleeps = []

    stopped = wait_or_stop(2.5, sleep=sleeps.append)

    assert stopped is False
    assert sleeps == [2.5]


def test_wait_or_stop_returns_true_when_event_is_set():
    event = Event()
    event.set()

    stopped = wait_or_stop(5, stop_event=event, sleep=lambda _seconds: None)

    assert stopped is True


def test_random_sleep_is_interruptible():
    event = Event()
    event.set()

    stopped = random_sleep(
        stop_event=event,
        sleep=lambda _seconds: pytest.fail("sleep should not be called"),
        random_value=lambda: 0.1,
        uniform=lambda low, high: low,
    )

    assert stopped is True


def test_check_and_sleep_returns_same_start_time_when_threshold_not_reached():
    start_time = datetime(2026, 1, 1, 12, 0, 0)

    new_start_time, stopped = check_and_sleep(
        start_time,
        now=lambda: start_time + timedelta(seconds=599),
        sleep=lambda _seconds: pytest.fail("sleep should not be called"),
        log=lambda _message: None,
    )

    assert new_start_time == start_time
    assert stopped is False


def test_check_and_sleep_can_stop_during_throttle_window():
    start_time = datetime(2026, 1, 1, 12, 0, 0)
    current_time = start_time + timedelta(seconds=601)
    event = Event()
    event.set()
    logs = []

    new_start_time, stopped = check_and_sleep(
        start_time,
        stop_event=event,
        now=lambda: current_time,
        sleep=lambda _seconds: pytest.fail("sleep should not be called"),
        log=logs.append,
    )

    assert new_start_time == current_time
    assert stopped is True
    assert any("Start to sleep" in message for message in logs)

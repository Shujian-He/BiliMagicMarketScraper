"""
tools.py
Bili Market Scraper
-------------------
Author: Shujian
Description: A scraper getting your favorite items in Bilibili magic market.
License: MIT License
"""

import os
import random
import tempfile
import time
from datetime import datetime, timedelta

import requests


class RequestError(RuntimeError):
    """Raised when an HTTP request fails or exhausts its retry budget."""


class ResponseError(RequestError):
    """Raised when a successful HTTP response contains unusable JSON."""


def load_cookie(file_path="cookies.txt"):
    try:
        with open(file_path) as file:
            return file.read().strip()
    except FileNotFoundError:
        print(f"Cookie file '{file_path}' not found.")
        return ""


def _parse_retry_after(value):
    try:
        delay = float(value)
    except (TypeError, ValueError):
        return None
    return delay if delay >= 0 else None


def _backoff_delay(attempt, jitter):
    return (2 ** (attempt - 1)) + jitter(0, 1)


def send_request(
    session,
    url,
    headers,
    payload,
    *,
    max_attempts=100,
    timeout=(5, 15),
    sleep=time.sleep,
    jitter=random.uniform,
    log=print,
):
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")

    last_error = None
    last_reason = "unknown error"

    for attempt in range(1, max_attempts + 1):
        try:
            response = session.post(url, headers=headers, json=payload, timeout=timeout)
        except requests.RequestException as exc:
            last_error = exc
            last_reason = f"{exc.__class__.__name__}: {exc}"
            delay = _backoff_delay(attempt, jitter)
        else:
            status_code = response.status_code

            if status_code == 200:
                try:
                    payload_json = response.json()
                except Exception as exc:  # noqa: BLE001
                    raise ResponseError(
                        f"HTTP 200 response from {url} did not contain valid JSON: {exc}"
                    ) from exc

                if not isinstance(payload_json, dict):
                    raise ResponseError(
                        f"HTTP 200 response from {url} did not contain a JSON object."
                    )

                return payload_json

            if status_code == 429:
                last_error = RequestError(f"HTTP 429 for {url}: {response.text}")
                retry_after = _parse_retry_after(response.headers.get("Retry-After"))
                if retry_after is not None:
                    last_reason = "HTTP 429 with Retry-After"
                    delay = retry_after
                else:
                    last_reason = "HTTP 429"
                    delay = _backoff_delay(attempt, jitter)
            elif 500 <= status_code < 600:
                last_error = RequestError(f"HTTP {status_code} for {url}: {response.text}")
                last_reason = f"HTTP {status_code}"
                delay = _backoff_delay(attempt, jitter)
            else:
                raise RequestError(f"HTTP {status_code} for {url}: {response.text}")

        if attempt == max_attempts:
            error = RequestError(
                f"Request attempts exhausted after {max_attempts} attempts for {url}: "
                f"{last_reason}"
            )
            if last_error is not None:
                raise error from last_error
            raise error

        log(
            f"Retrying request after attempt {attempt} for {url} because {last_reason}. "
            f"Sleeping {delay:.2f}s."
        )
        sleep(delay)


def load_checkpoint(path="nextId.txt"):
    try:
        with open(path, encoding="utf-8") as file:
            value = file.read().strip()
    except FileNotFoundError:
        return None
    return value or None


def write_checkpoint(next_id, path="nextId.txt"):
    path_str = os.fspath(path)
    directory = os.path.dirname(path_str) or "."
    prefix = f".{os.path.basename(path_str)}."
    fd, temp_path = tempfile.mkstemp(dir=directory, prefix=prefix, text=True)

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            file.write("" if next_id is None else str(next_id))
        os.replace(temp_path, path_str)
    except BaseException:
        try:
            os.unlink(temp_path)
        except FileNotFoundError:
            pass
        raise


def wait_or_stop(seconds, stop_event=None, sleep=time.sleep):
    if stop_event is not None:
        return stop_event.wait(seconds)

    sleep(seconds)
    return False


def random_sleep(stop_event=None, *, sleep=time.sleep, random_value=None, uniform=None):
    random_value = random.random if random_value is None else random_value
    uniform = random.uniform if uniform is None else uniform

    if random_value() < 0.9:
        sleep_time = uniform(1, 1.5)
    else:
        sleep_time = uniform(2, 3)

    return wait_or_stop(sleep_time, stop_event=stop_event, sleep=sleep)


def check_and_sleep(start_time, stop_event=None, now=None, sleep=time.sleep, log=print):
    now = datetime.now if now is None else now
    current_time = now()

    if current_time - start_time < timedelta(seconds=600):
        return start_time, False

    log("Start to sleep for 60s")
    for second in range(60):
        if wait_or_stop(1, stop_event=stop_event, sleep=sleep):
            log("Sleep interrupted by stop event.")
            return now(), True
        log(f"{second + 1}s passed...")

    log("Slept for 60s")
    return now(), False

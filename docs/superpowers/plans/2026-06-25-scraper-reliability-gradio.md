# Scraper Reliability and Gradio UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the scraper stop and retry predictably, write each page consistently, expose one shared crawl loop to CLI and Gradio, and remove Streamlit without changing the SQLite schema or Cookie workflow.

**Architecture:** Keep the existing four-module shape. `tools.py` owns HTTP retries and atomic checkpoints, `db.py` owns schema-compatible batch upserts, `main.py` owns structured records and the shared crawl loop, and `ui_gradio.py` owns cancellable UI task orchestration. Tests use fake sessions and temporary SQLite/CSV files; no test calls Bilibili.

**Tech Stack:** Python 3.10+, requests 2.x, SQLite, Gradio 5.x, pytest 8.x, Ruff.

---

## File Map

- Modify `.gitignore`: replace the catch-all rule with explicit generated-file and local-scratch exclusions.
- Create `requirements.txt`: runtime dependencies.
- Create `requirements-dev.txt`: test and lint dependencies.
- Create `pyproject.toml`: pytest and Ruff configuration.
- Modify `tools.py`: request retries, interruptible waits, checkpoint reads/writes.
- Modify `db.py`: schema-compatible structured batch insert.
- Replace `main.py`: shared crawler, record parsing, CSV/database page transaction, CLI.
- Replace `ui_gradio.py`: cancellable Gradio worker using the shared crawler.
- Delete `ui.py`: remove Streamlit UI.
- Modify `main.sh`: forward arguments without reparsing.
- Modify `README.md` and `README.zh.md`: document Gradio and reliability behavior.
- Create `tests/test_tools.py`: retry and checkpoint tests.
- Create `tests/test_db.py`: batch insert and rollback tests.
- Create `tests/test_main.py`: parsing, CSV, cursor and crawl tests.
- Create `tests/test_ui_gradio.py`: controller and worker cleanup tests.

### Task 1: Make New Source and Tests Visible

**Files:**
- Modify: `.gitignore`
- Create: `requirements.txt`
- Create: `requirements-dev.txt`
- Create: `pyproject.toml`

- [ ] **Step 1: Replace the catch-all ignore file**

Use this exact `.gitignore`:

```gitignore
.DS_Store
__pycache__/
*.py[cod]
.pytest_cache/
.ruff_cache/
.venv/

/bilidata.db
/nextId.txt
/total_*.csv
/want_*.csv
/sort_*.csv

# Local scratch files that are not part of the application.
/a.py
/db_debug.py
/delete_csv.py
/miku.sql
/test_post.py
```

Do not add, remove, stage, or alter `cookies.txt`.

- [ ] **Step 2: Add reproducible dependency files**

Create `requirements.txt`:

```text
gradio>=5.0,<6
requests>=2.31,<3
```

Create `requirements-dev.txt`:

```text
-r requirements.txt
pytest>=8,<9
ruff>=0.12,<1
```

- [ ] **Step 3: Add test and lint configuration**

Create `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra"

[tool.ruff]
target-version = "py310"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]
```

- [ ] **Step 4: Verify Git now sees application additions**

Run:

```sh
git status --short
```

Expected: `ui_gradio.py` becomes visible as untracked, while the listed local scratch files and generated data remain ignored. `cookies.txt` must not appear as modified.

- [ ] **Step 5: Commit project metadata**

```sh
git add .gitignore requirements.txt requirements-dev.txt pyproject.toml
git commit -m "chore: define scraper dependencies and ignores"
```

### Task 2: Add Finite HTTP Retries and Atomic Checkpoints

**Files:**
- Modify: `tools.py`
- Create: `tests/test_tools.py`

- [ ] **Step 1: Write failing request retry tests**

Create `tests/test_tools.py` with response and session fakes:

```python
import os
from pathlib import Path

import pytest
import requests

from tools import RequestError, ResponseError, load_checkpoint, send_request, write_checkpoint


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
        self.calls = 0

    def post(self, *args, **kwargs):
        self.calls += 1
        outcome = next(self.outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def test_send_request_retries_timeout_then_succeeds():
    sleeps = []
    session = FakeSession(
        [
            requests.Timeout("slow"),
            FakeResponse(200, {"code": 0, "data": {"data": [], "nextId": None}}),
        ]
    )

    result = send_request(
        session,
        "https://example.invalid",
        {},
        {},
        sleep=sleeps.append,
        jitter=lambda _a, _b: 0,
    )

    assert result["code"] == 0
    assert session.calls == 2
    assert sleeps == [1]


def test_send_request_uses_retry_after_for_429():
    sleeps = []
    session = FakeSession(
        [
            FakeResponse(429, headers={"Retry-After": "3"}),
            FakeResponse(200, {"code": 0, "data": {"data": [], "nextId": None}}),
        ]
    )

    send_request(
        session,
        "https://example.invalid",
        {},
        {},
        sleep=sleeps.append,
        jitter=lambda _a, _b: 0,
    )

    assert sleeps == [3]


def test_send_request_retries_5xx_with_exponential_backoff():
    sleeps = []
    session = FakeSession(
        [
            FakeResponse(503, text="unavailable"),
            FakeResponse(200, {"code": 0, "data": {"data": [], "nextId": None}}),
        ]
    )

    send_request(
        session,
        "https://example.invalid",
        {},
        {},
        sleep=sleeps.append,
        jitter=lambda _a, _b: 0,
    )

    assert sleeps == [1]


def test_send_request_does_not_retry_regular_4xx():
    session = FakeSession([FakeResponse(403, text="forbidden")])

    with pytest.raises(RequestError, match="HTTP 403"):
        send_request(session, "https://example.invalid", {}, {})

    assert session.calls == 1


def test_send_request_rejects_invalid_json_without_retrying():
    session = FakeSession([FakeResponse(200, ValueError("bad json"))])

    with pytest.raises(ResponseError, match="valid JSON"):
        send_request(session, "https://example.invalid", {}, {})

    assert session.calls == 1


def test_send_request_stops_after_max_attempts():
    session = FakeSession([requests.Timeout("slow")] * 3)

    with pytest.raises(RequestError, match="after 3 attempts"):
        send_request(
            session,
            "https://example.invalid",
            {},
            {},
            sleep=lambda _seconds: None,
            jitter=lambda _a, _b: 0,
        )

    assert session.calls == 3
```

- [ ] **Step 2: Run the request tests and verify they fail**

Run:

```sh
pytest tests/test_tools.py -v
```

Expected: collection fails because `RequestError` and the new `send_request` signature do not exist.

- [ ] **Step 3: Implement finite retries in `tools.py`**

Replace the request portion with:

```python
import os
import random
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests


class RequestError(RuntimeError):
    pass


class ResponseError(RequestError):
    pass


def load_cookie(file_path="cookies.txt"):
    try:
        return Path(file_path).read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        print(f"Cookie file '{file_path}' not found.")
        return ""


def _retry_delay(response, attempt, jitter):
    if response is not None and response.status_code == 429:
        try:
            return max(0.0, float(response.headers.get("Retry-After", "")))
        except ValueError:
            pass
    return (2 ** (attempt - 1)) + jitter(0, 0.5)


def send_request(
    session,
    url,
    headers,
    payload,
    *,
    max_attempts=3,
    timeout=(5, 15),
    sleep=time.sleep,
    jitter=random.uniform,
    log=print,
):
    last_error = None
    for attempt in range(1, max_attempts + 1):
        response = None
        try:
            response = session.post(url, headers=headers, json=payload, timeout=timeout)
            if response.status_code == 200:
                try:
                    data = response.json()
                except ValueError as exc:
                    raise ResponseError("Response was not valid JSON") from exc
                if not isinstance(data, dict):
                    raise ResponseError("Response JSON must be an object")
                return data
            if response.status_code != 429 and response.status_code < 500:
                raise RequestError(f"HTTP {response.status_code}: {response.text[:200]}")
            last_error = RequestError(f"HTTP {response.status_code}: {response.text[:200]}")
        except ResponseError:
            raise
        except RequestError:
            raise
        except requests.RequestException as exc:
            last_error = exc

        if attempt == max_attempts:
            break
        delay = _retry_delay(response, attempt, jitter)
        log(f"Request failed ({last_error}); retrying in {delay:.1f}s")
        sleep(delay)

    raise RequestError(f"Request failed after {max_attempts} attempts: {last_error}")
```

- [ ] **Step 4: Run the retry tests**

Run:

```sh
pytest tests/test_tools.py -v
```

Expected: all six request tests pass.

- [ ] **Step 5: Write failing checkpoint tests**

Append:

```python
def test_checkpoint_round_trip_and_clear(tmp_path):
    checkpoint = tmp_path / "nextId.txt"

    write_checkpoint("cursor-1", checkpoint)
    assert load_checkpoint(checkpoint) == "cursor-1"

    write_checkpoint(None, checkpoint)
    assert load_checkpoint(checkpoint) is None


def test_checkpoint_uses_replace(tmp_path, monkeypatch):
    checkpoint = tmp_path / "nextId.txt"
    replacements = []
    real_replace = os.replace

    def record_replace(source, destination):
        replacements.append((Path(source), Path(destination)))
        real_replace(source, destination)

    monkeypatch.setattr("tools.os.replace", record_replace)
    write_checkpoint("cursor-2", checkpoint)

    assert replacements[0][1] == checkpoint
    assert checkpoint.read_text(encoding="utf-8") == "cursor-2"
```

- [ ] **Step 6: Implement checkpoint and interruptible wait helpers**

Append to `tools.py`:

```python
def load_checkpoint(file_path="nextId.txt"):
    try:
        value = Path(file_path).read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return None
    return value or None


def write_checkpoint(next_id, file_path="nextId.txt"):
    path = Path(file_path)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(next_id or "", encoding="utf-8")
    os.replace(temporary, path)


def wait_or_stop(seconds, stop_event=None, sleep=time.sleep):
    if stop_event is not None:
        return stop_event.wait(seconds)
    sleep(seconds)
    return False


def random_sleep(stop_event=None, rng=random.uniform):
    seconds = rng(1, 1.5) if random.random() < 0.9 else rng(2, 3)
    return wait_or_stop(seconds, stop_event)


def check_and_sleep(start_time, stop_event=None, now=datetime.now):
    current_time = now()
    if current_time - start_time < timedelta(minutes=10):
        return start_time, False
    stopped = wait_or_stop(60, stop_event)
    return now(), stopped
```

- [ ] **Step 7: Run tests and commit**

Run:

```sh
pytest tests/test_tools.py -v
ruff check tools.py tests/test_tools.py
```

Expected: all tests pass and Ruff reports no errors.

Commit:

```sh
git add tools.py tests/test_tools.py
git commit -m "feat: add bounded request retries and checkpoints"
```

### Task 3: Batch Database Writes Without Schema Changes

**Files:**
- Modify: `db.py`
- Create: `tests/test_db.py`

- [ ] **Step 1: Write failing batch insert tests**

Create `tests/test_db.py`:

```python
from db import initialize_database, insert_products


def test_insert_products_upserts_existing_schema(tmp_path):
    connection = initialize_database(tmp_path / "products.db")
    first = [("1", "old", 100, 200, 0.5, "2026-01-01 00:00:00")]
    second = [("1", "new", 120, 200, 0.6, "2026-01-02 00:00:00")]

    insert_products(first, connection)
    connection.commit()
    insert_products(second, connection)
    connection.commit()

    row = connection.execute(
        "SELECT id, name, price, market_price, rate, time FROM products"
    ).fetchone()
    assert row == second[0]


def test_insert_products_does_not_commit_implicitly(tmp_path):
    connection = initialize_database(tmp_path / "products.db")
    insert_products([("1", "name", 100, 200, 0.5, "time")], connection)
    connection.rollback()

    assert connection.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```sh
pytest tests/test_db.py -v
```

Expected: import fails because `insert_products` does not exist.

- [ ] **Step 3: Implement batch upsert while preserving the table**

Keep `initialize_database` and `insert_csv`, remove the string-splitting `insert_line`, and add:

```python
UPSERT_PRODUCTS = """
    INSERT INTO products (id, name, price, market_price, rate, time)
    VALUES (?, ?, ?, ?, ?, ?)
    ON CONFLICT(id) DO UPDATE SET
        name = excluded.name,
        price = excluded.price,
        market_price = excluded.market_price,
        rate = excluded.rate,
        time = excluded.time
"""


def insert_products(rows, conn):
    conn.executemany(UPSERT_PRODUCTS, rows)
```

Update `insert_csv` to build six-value tuples and call `insert_products`; retain its final commit and close behavior for command-line CSV importing:

```python
def insert_csv(total_file, conn):
    rows = []
    with open(total_file, newline="", encoding="utf-8") as file:
        for time_value, name, product_id, price, market_price, rate in csv.reader(file):
            rows.append(
                (
                    product_id,
                    name,
                    int(price),
                    int(market_price),
                    float(rate),
                    time_value,
                )
            )
    insert_products(rows, conn)
    conn.commit()
    conn.close()
```

- [ ] **Step 4: Prove schema compatibility**

Run:

```sh
pytest tests/test_db.py -v
sqlite3 -readonly bilidata.db ".schema products"
```

Expected: tests pass; existing schema output remains the six-column `products` table with `id TEXT PRIMARY KEY`.

- [ ] **Step 5: Commit**

```sh
git add db.py tests/test_db.py
git commit -m "refactor: batch product upserts per page"
```

### Task 4: Build the Shared Crawl Loop and Page Transaction

**Files:**
- Replace: `main.py`
- Create: `tests/test_main.py`

- [ ] **Step 1: Write parsing and CSV transaction tests**

Create `tests/test_main.py`:

```python
import csv
import sqlite3
from pathlib import Path
from threading import Event

import pytest

from main import (
    CrawlStatus,
    CursorStalledError,
    OutputPaths,
    ProductRecord,
    ScrapeConfig,
    ScraperError,
    crawl,
    parse_product,
    persist_page,
)


class CountingConnection:
    def __init__(self, connection):
        self.connection = connection
        self.commits = 0
        self.rollbacks = 0

    def execute(self, *args, **kwargs):
        return self.connection.execute(*args, **kwargs)

    def executemany(self, *args, **kwargs):
        return self.connection.executemany(*args, **kwargs)

    def commit(self):
        self.commits += 1
        return self.connection.commit()

    def rollback(self):
        self.rollbacks += 1
        return self.connection.rollback()


def make_connection():
    raw_connection = sqlite3.connect(":memory:")
    raw_connection.execute(
        """
        CREATE TABLE products (
            id TEXT PRIMARY KEY,
            name TEXT,
            price INTEGER,
            market_price INTEGER,
            rate REAL,
            time TEXT
        )
        """
    )
    return CountingConnection(raw_connection)


def test_parse_product_keeps_comma_and_normalizes_newline():
    item = {
        "totalItemsCount": 1,
        "c2cItemsName": "Miku, Racing\nVersion",
        "c2cItemsId": "42",
        "price": "5000",
        "detailDtoList": [{"marketPrice": "10000"}],
    }

    record = parse_product(item, "2026-01-01 00:00:00")

    assert record.name == "Miku, Racing Version"
    assert record.rate == 0.5


@pytest.mark.parametrize(
    "item",
    [
        {"totalItemsCount": 2},
        {
            "totalItemsCount": 1,
            "c2cItemsName": "bad",
            "c2cItemsId": "1",
            "price": "1",
            "detailDtoList": [],
        },
        {
            "totalItemsCount": 1,
            "c2cItemsName": "bad",
            "c2cItemsId": "1",
            "price": "1",
            "detailDtoList": [{"marketPrice": "0"}],
        },
    ],
)
def test_parse_product_rejects_unsupported_or_invalid_items(item):
    with pytest.raises(ValueError):
        parse_product(item, "time")


def test_persist_page_quotes_csv_and_commits_once(tmp_path):
    connection = make_connection()
    paths = OutputPaths(
        total=tmp_path / "total.csv",
        wanted=tmp_path / "want.csv",
        checkpoint=tmp_path / "nextId.txt",
    )
    record = ProductRecord("time", "Miku, Racing", "42", 5000, 10000, 0.5)

    persist_page(connection, [record], ["Miku"], paths)

    with paths.total.open(newline="", encoding="utf-8") as handle:
        assert list(csv.reader(handle))[0][1] == "Miku, Racing"
    assert connection.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 1
    assert connection.commits == 1
```

- [ ] **Step 2: Write crawl termination tests**

Append:

```python
class FakeResponse:
    status_code = 200
    headers = {}
    text = ""

    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, payloads):
        self.payloads = iter(payloads)
        self.closed = False

    def post(self, *args, **kwargs):
        return FakeResponse(next(self.payloads))

    def close(self):
        self.closed = True


def empty_page(next_id):
    return {"code": 0, "data": {"data": [], "nextId": next_id}}


def test_crawl_finishes_and_clears_checkpoint(tmp_path):
    paths = OutputPaths.for_run(tmp_path, "run")
    paths.checkpoint.write_text("old", encoding="utf-8")

    result = crawl(
        make_connection(),
        ScrapeConfig(("Miku",), ("20000-0",), ("70-100",), ""),
        paths=paths,
        session=FakeSession([empty_page(None)]),
        page_sleep=lambda _event: False,
        periodic_sleep=lambda start, _event: (start, False),
    )

    assert result is CrawlStatus.FINISHED
    assert paths.checkpoint.read_text(encoding="utf-8") == ""


def test_crawl_rejects_repeated_cursor_before_writing_page(tmp_path):
    paths = OutputPaths.for_run(tmp_path, "run")

    with pytest.raises(CursorStalledError, match="cursor-1"):
        crawl(
            make_connection(),
            ScrapeConfig(("Miku",), ("20000-0",), ("70-100",), ""),
            start_next_id="cursor-1",
            paths=paths,
            session=FakeSession([empty_page("cursor-1")]),
            page_sleep=lambda _event: False,
            periodic_sleep=lambda start, _event: (start, False),
        )

    assert not paths.total.exists()


def test_crawl_rejects_malformed_api_data(tmp_path):
    malformed = {"code": 0, "data": {"data": None, "nextId": None}}

    with pytest.raises(ScraperError, match="data field must be a list"):
        crawl(
            make_connection(),
            ScrapeConfig(("Miku",), ("20000-0",), ("70-100",), ""),
            paths=OutputPaths.for_run(tmp_path, "run"),
            session=FakeSession([malformed]),
            page_sleep=lambda _event: False,
            periodic_sleep=lambda start, _event: (start, False),
        )


def test_crawl_stops_at_page_boundary(tmp_path):
    stop_event = Event()
    stop_event.set()

    result = crawl(
        make_connection(),
        ScrapeConfig(("Miku",), ("20000-0",), ("70-100",), ""),
        paths=OutputPaths.for_run(tmp_path, "run"),
        session=FakeSession([]),
        stop_event=stop_event,
        page_sleep=lambda _event: False,
        periodic_sleep=lambda start, _event: (start, False),
    )

    assert result is CrawlStatus.STOPPED
```

- [ ] **Step 3: Run tests and verify the new API is missing**

Run:

```sh
pytest tests/test_main.py -v
```

Expected: collection fails on missing structured crawler names.

- [ ] **Step 4: Implement structured models and parsing**

Replace `main.py` imports and model definitions with:

```python
import argparse
import csv
import sys
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from threading import Event

import requests

from db import initialize_database, insert_products
from tools import (
    RequestError,
    check_and_sleep,
    load_checkpoint,
    load_cookie,
    random_sleep,
    send_request,
    write_checkpoint,
)

MARKET_URL = "https://mall.bilibili.com/mall-magic-c/internet/c2c/v2/list"
USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) "
    "AppleWebKit/619.2.8.10.7 (KHTML, like Gecko) Mobile/22B83 "
    "BiliApp/81900100 os/ios model/iPhone 14 Pro"
)


class ScraperError(RuntimeError):
    pass


class CursorStalledError(ScraperError):
    pass


class CrawlStatus(Enum):
    FINISHED = "finished"
    STOPPED = "stopped"


@dataclass(frozen=True)
class ScrapeConfig:
    want_list: tuple[str, ...]
    price_filters: tuple[str, ...]
    discount_filters: tuple[str, ...]
    category_filter: str


@dataclass(frozen=True)
class OutputPaths:
    total: Path
    wanted: Path
    checkpoint: Path

    @classmethod
    def for_run(cls, directory, run_id):
        directory = Path(directory)
        return cls(
            total=directory / f"total_{run_id}.csv",
            wanted=directory / f"want_{run_id}.csv",
            checkpoint=directory / "nextId.txt",
        )


@dataclass(frozen=True)
class ProductRecord:
    captured_at: str
    name: str
    product_id: str
    price: int
    market_price: int
    rate: float

    def csv_row(self):
        return (
            self.captured_at,
            self.name,
            self.product_id,
            self.price,
            self.market_price,
            self.rate,
        )

    def database_row(self):
        return (
            self.product_id,
            self.name,
            self.price,
            self.market_price,
            self.rate,
            self.captured_at,
        )


def parse_product(item, captured_at):
    if int(item.get("totalItemsCount", 0)) > 1:
        raise ValueError("multi-item packages are unsupported")
    try:
        details = item["detailDtoList"]
        market_price = int(details[0]["marketPrice"])
        price = int(item["price"])
        if market_price <= 0 or price < 0:
            raise ValueError("invalid price")
        name = " ".join(str(item["c2cItemsName"]).splitlines()).strip()
        product_id = str(item["c2cItemsId"])
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise ValueError(f"invalid product: {exc}") from exc
    return ProductRecord(
        captured_at,
        name,
        product_id,
        price,
        market_price,
        price / market_price,
    )
```

- [ ] **Step 5: Implement page persistence with rollback and CSV truncation**

Add:

```python
def persist_page(connection, records, want_list, paths):
    wanted = [
        record
        for record in records
        if any(keyword in record.name for keyword in want_list)
    ]
    paths.total.parent.mkdir(parents=True, exist_ok=True)
    with (
        paths.total.open("a+", newline="", encoding="utf-8") as total_handle,
        paths.wanted.open("a+", newline="", encoding="utf-8") as wanted_handle,
    ):
        total_handle.seek(0, 2)
        wanted_handle.seek(0, 2)
        total_position = total_handle.tell()
        wanted_position = wanted_handle.tell()
        try:
            insert_products([record.database_row() for record in records], connection)
            csv.writer(total_handle).writerows(record.csv_row() for record in records)
            csv.writer(wanted_handle).writerows(record.csv_row() for record in wanted)
            total_handle.flush()
            wanted_handle.flush()
            connection.commit()
        except Exception:
            connection.rollback()
            total_handle.seek(total_position)
            total_handle.truncate()
            wanted_handle.seek(wanted_position)
            wanted_handle.truncate()
            raise
```

- [ ] **Step 6: Implement response validation and the shared loop**

Add:

```python
def _headers():
    return {
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
        "Cookie": load_cookie(),
    }


def _payload(config, next_id):
    return {
        "categoryFilter": config.category_filter,
        "priceFilters": list(config.price_filters),
        "discountFilters": list(config.discount_filters),
        "sortType": "TIME_DESC",
        "nextId": next_id,
    }


def _page_data(response):
    if response.get("code") != 0:
        raise ScraperError(f"API returned code {response.get('code')}: {response}")
    try:
        container = response["data"]
        items = container["data"]
        next_id = container["nextId"]
    except (KeyError, TypeError) as exc:
        raise ScraperError("API response is missing data/data/nextId") from exc
    if not isinstance(items, list):
        raise ScraperError("API data field must be a list")
    return items, None if not next_id else str(next_id)


def crawl(
    connection,
    config,
    *,
    start_next_id=None,
    paths=None,
    session=None,
    stop_event=None,
    log=print,
    page_sleep=random_sleep,
    periodic_sleep=check_and_sleep,
):
    stop_event = stop_event or Event()
    run_id = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    paths = paths or OutputPaths.for_run(".", run_id)
    own_session = session is None
    session = session or requests.Session()
    current_id = start_next_id
    started_at = datetime.now()
    try:
        while True:
            if stop_event.is_set() or page_sleep(stop_event):
                return CrawlStatus.STOPPED
            response = send_request(
                session,
                MARKET_URL,
                _headers(),
                _payload(config, current_id),
                log=log,
            )
            items, next_id = _page_data(response)
            if next_id is not None and next_id == current_id:
                raise CursorStalledError(f"Cursor made no progress: {next_id}")

            records = []
            for item in items:
                try:
                    records.append(
                        parse_product(item, datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"))
                    )
                except ValueError as exc:
                    log(f"Skipping item: {exc}")
            persist_page(connection, records, config.want_list, paths)
            write_checkpoint(next_id, paths.checkpoint)
            log(f"Next ID: {next_id}")

            if next_id is None:
                return CrawlStatus.FINISHED
            current_id = next_id
            started_at, stopped = periodic_sleep(started_at, stop_event)
            if stopped:
                return CrawlStatus.STOPPED
    finally:
        if own_session:
            session.close()
```

- [ ] **Step 7: Run main tests**

Run:

```sh
pytest tests/test_main.py -v
```

Expected: all parsing, CSV, finish, cursor and stop tests pass.

- [ ] **Step 8: Add a rollback regression test**

Append:

```python
def test_persist_page_rolls_back_files_and_database(tmp_path, monkeypatch):
    connection = make_connection()
    paths = OutputPaths(
        total=tmp_path / "total.csv",
        wanted=tmp_path / "want.csv",
        checkpoint=tmp_path / "nextId.txt",
    )
    record = ProductRecord("time", "Miku", "42", 5000, 10000, 0.5)

    def fail_after_insert(rows, conn):
        conn.execute(
            """
            INSERT INTO products (id, name, price, market_price, rate, time)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            rows[0],
        )
        raise RuntimeError("database failure")

    monkeypatch.setattr("main.insert_products", fail_after_insert)

    with pytest.raises(RuntimeError, match="database failure"):
        persist_page(connection, [record], ["Miku"], paths)

    assert paths.total.read_text(encoding="utf-8") == ""
    assert paths.wanted.read_text(encoding="utf-8") == ""
    assert connection.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0
```

Run the specific test and confirm it passes:

```sh
pytest tests/test_main.py::test_persist_page_rolls_back_files_and_database -v
```

- [ ] **Step 9: Commit shared crawler**

```sh
git add main.py tests/test_main.py
git commit -m "refactor: share a reliable crawl loop"
```

### Task 5: Restore a Clean CLI on Top of the Shared Loop

**Files:**
- Modify: `main.py`
- Modify: `tests/test_main.py`

- [ ] **Step 1: Write argument validation tests**

Append:

```python
from main import build_parser, config_from_args


def test_invalid_filters_fall_back_to_defaults():
    args = build_parser().parse_args(["-p", "bad", "-d", "bad", "-c", "bad"])
    config = config_from_args(args, log=lambda _message: None)

    assert config.price_filters == ("10000-20000", "20000-0")
    assert config.discount_filters == ("0-30", "30-50", "50-70", "70-100")
    assert config.category_filter == ""
```

- [ ] **Step 2: Run and verify failure**

Run:

```sh
pytest tests/test_main.py::test_invalid_filters_fall_back_to_defaults -v
```

Expected: import fails because CLI helpers do not exist.

- [ ] **Step 3: Implement parser, validation and main**

Add constants and functions:

```python
VALID_PRICES = ("0-2000", "2000-3000", "3000-5000", "5000-10000", "10000-20000", "20000-0")
VALID_DISCOUNTS = ("0-30", "30-50", "50-70", "70-100")
VALID_CATEGORIES = ("2312", "2066", "2331", "2273", "fudai_cate_id", "")
DEFAULT_PRICES = ("10000-20000", "20000-0")
DEFAULT_DISCOUNTS = VALID_DISCOUNTS


def build_parser():
    parser = argparse.ArgumentParser(description="Scrape Bilibili Magic Market")
    parser.add_argument("-w", "--want", nargs="+", default=["初音未来"])
    parser.add_argument("-p", "--price", nargs="+", default=list(DEFAULT_PRICES))
    parser.add_argument("-d", "--discount", nargs="+", default=list(DEFAULT_DISCOUNTS))
    parser.add_argument("-c", "--category", default="")
    parser.add_argument("--id", action="store_true", help="Continue from nextId.txt")
    return parser


def config_from_args(args, log=print):
    prices = tuple(args.price)
    if any(value not in VALID_PRICES for value in prices):
        log("Invalid price filter; using defaults.")
        prices = DEFAULT_PRICES
    discounts = tuple(args.discount)
    if any(value not in VALID_DISCOUNTS for value in discounts):
        log("Invalid discount filter; using defaults.")
        discounts = DEFAULT_DISCOUNTS
    category = args.category
    if category not in VALID_CATEGORIES:
        log("Invalid category filter; using the blank category.")
        category = ""
    return ScrapeConfig(tuple(args.want), prices, discounts, category)


def main(argv=None):
    args = build_parser().parse_args(argv)
    config = config_from_args(args)
    next_id = load_checkpoint() if args.id else None
    connection = initialize_database()
    try:
        status = crawl(connection, config, start_next_id=next_id)
        print(f"Scraper {status.value}.")
        return 0
    except (RequestError, ScraperError) as exc:
        print(f"Scraper failed: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nStopped by user. Progress from the last complete page is saved.")
        return 130
    finally:
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run CLI tests and smoke check**

Run:

```sh
pytest tests/test_main.py -v
python3 main.py --help
```

Expected: tests pass and help exits zero without opening the database or network.

- [ ] **Step 5: Commit**

```sh
git add main.py tests/test_main.py
git commit -m "refactor: run cli through shared crawler"
```

### Task 6: Replace Streamlit with a Cancellable Gradio Worker

**Files:**
- Delete: `ui.py`
- Replace: `ui_gradio.py`
- Create: `tests/test_ui_gradio.py`

- [ ] **Step 1: Write controller and cleanup tests**

Create `tests/test_ui_gradio.py`:

```python
from ui_gradio import TaskController, run_scrape_job


class FakeConnection:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


def test_task_controller_prevents_duplicate_runs():
    controller = TaskController()

    assert controller.start() is True
    assert controller.start() is False
    assert controller.request_stop() is True
    controller.finish()
    assert controller.start() is True


def test_worker_always_closes_connection_and_resets_controller():
    controller = TaskController()
    controller.start()
    connection = FakeConnection()
    messages = []

    def failing_crawl(*args, **kwargs):
        raise RuntimeError("boom")

    run_scrape_job(
        connection_factory=lambda: connection,
        crawl_function=failing_crawl,
        controller=controller,
        config=None,
        next_id=None,
        emit=messages.append,
    )

    assert connection.closed is True
    assert controller.running is False
    assert any("boom" in message for message in messages)
```

- [ ] **Step 2: Run and verify failure**

Run:

```sh
pytest tests/test_ui_gradio.py -v
```

Expected: imports fail because `TaskController` and `run_scrape_job` do not exist.

- [ ] **Step 3: Implement the task controller**

Replace the global boolean with:

```python
import queue
import threading
import time
from dataclasses import dataclass, field

import gradio as gr

from db import initialize_database
from main import ScrapeConfig, crawl
from tools import load_checkpoint


@dataclass
class TaskController:
    lock: threading.Lock = field(default_factory=threading.Lock)
    stop_event: threading.Event = field(default_factory=threading.Event)
    running: bool = False

    def start(self):
        with self.lock:
            if self.running:
                return False
            self.running = True
            self.stop_event.clear()
            return True

    def request_stop(self):
        with self.lock:
            if not self.running:
                return False
            self.stop_event.set()
            return True

    def finish(self):
        with self.lock:
            self.running = False


controller = TaskController()
```

- [ ] **Step 4: Implement the worker and streaming generator**

Add:

```python
def run_scrape_job(
    *,
    connection_factory,
    crawl_function,
    controller,
    config,
    next_id,
    emit,
):
    connection = None
    try:
        connection = connection_factory()
        status = crawl_function(
            connection,
            config,
            start_next_id=next_id,
            stop_event=controller.stop_event,
            log=emit,
        )
        emit(f"Scraper {status.value}.")
    except Exception as exc:
        emit(f"Scraper failed: {exc}")
    finally:
        if connection is not None:
            connection.close()
        controller.finish()


def scrape(want_text, price_filters, discount_filters, category_filter, continue_from_id):
    if not controller.start():
        yield "A scraper task is already running."
        return

    config = ScrapeConfig(
        tuple(value.strip() for value in want_text.split(",") if value.strip()) or ("初音未来",),
        tuple(price_filters or ("10000-20000", "20000-0")),
        tuple(discount_filters or ("0-30", "30-50", "50-70", "70-100")),
        category_filter or "",
    )
    next_id = load_checkpoint() if continue_from_id else None
    messages = queue.Queue()
    worker = threading.Thread(
        target=run_scrape_job,
        kwargs={
            "connection_factory": initialize_database,
            "crawl_function": crawl,
            "controller": controller,
            "config": config,
            "next_id": next_id,
            "emit": messages.put,
        },
        daemon=True,
    )
    worker.start()

    log_lines = []
    while worker.is_alive() or not messages.empty():
        try:
            log_lines.append(messages.get(timeout=0.2))
            yield "\n".join(log_lines)
        except queue.Empty:
            time.sleep(0.05)
    worker.join()
    yield "\n".join(log_lines)


def stop_scraping():
    if controller.request_stop():
        return "Stopping after the current request/page completes."
    return "No scraper task is running."
```

Create the Gradio blocks with:

```python
with gr.Blocks(title="Bili Market Scraper") as demo:
    gr.Markdown("## Bili Market Scraper")
    want = gr.Textbox(label="Wanted item names (comma-separated)", value="初音未来")
    price = gr.CheckboxGroup(
        ["0-2000", "2000-3000", "3000-5000", "5000-10000", "10000-20000", "20000-0"],
        label="Price filters",
        value=["10000-20000", "20000-0"],
    )
    discount = gr.CheckboxGroup(
        ["0-30", "30-50", "50-70", "70-100"],
        label="Discount filters",
        value=["0-30", "30-50", "50-70", "70-100"],
    )
    category = gr.Dropdown(
        ["", "2312", "2066", "2331", "2273", "fudai_cate_id"],
        label="Category",
        value="",
    )
    continue_from_id = gr.Checkbox(label="Continue from nextId.txt", value=False)
    with gr.Row():
        run_button = gr.Button("Start scraping", variant="primary")
        stop_button = gr.Button("Stop scraping", variant="stop")
    log_output = gr.Textbox(label="Logs", lines=25, interactive=False)

    run_button.click(
        fn=scrape,
        inputs=[want, price, discount, category, continue_from_id],
        outputs=log_output,
    )
    stop_button.click(
        fn=stop_scraping,
        inputs=None,
        outputs=log_output,
        queue=False,
    )


if __name__ == "__main__":
    demo.queue().launch(inbrowser=True)
```

- [ ] **Step 5: Delete Streamlit UI and run UI tests**

Delete `ui.py`, then run:

```sh
pytest tests/test_ui_gradio.py -v
python3 -c "import ui_gradio; print(type(ui_gradio.demo).__name__)"
```

Expected: tests pass and import prints `Blocks`; it must not launch a server.

- [ ] **Step 6: Commit**

```sh
git add ui_gradio.py tests/test_ui_gradio.py
git rm ui.py
git commit -m "feat: make gradio the cancellable scraper ui"
```

### Task 7: Simplify Shell Entry and Update Documentation

**Files:**
- Modify: `main.sh`
- Modify: `README.md`
- Modify: `README.zh.md`

- [ ] **Step 1: Replace Shell argument parsing**

Replace `main.sh` with:

```sh
#!/bin/sh
exec python3 main.py "$@"
```

- [ ] **Step 2: Update both READMEs**

Make these concrete documentation changes in both languages:

- Project structure lists `ui_gradio.py`; remove `ui.py` and all Streamlit references.
- Installation uses `pip3 install -r requirements.txt`.
- Gradio launch command is `python3 ui_gradio.py`.
- Explain that Stop takes effect after the current HTTP request/page boundary.
- Explain that temporary network failures, HTTP 429 and HTTP 5xx are retried a limited number of times.
- Explain that persistent failures exit with an error instead of looping forever.
- Preserve the existing SQLite schema documentation.
- Preserve the existing Cookie setup documentation without changing its Git workflow.

- [ ] **Step 3: Check docs and shell**

Run:

```sh
sh -n main.sh
rg -n "Streamlit|streamlit|ui\\.py" README.md README.zh.md
```

Expected: shell syntax succeeds and `rg` returns no matches.

- [ ] **Step 4: Commit**

```sh
git add main.sh README.md README.zh.md
git commit -m "docs: document gradio scraper workflow"
```

### Task 8: Full Verification and Scope Audit

**Files:**
- Modify only files needed to fix verification failures.

- [ ] **Step 1: Run all automated tests**

```sh
pytest
```

Expected: all tests pass; test output contains no real Bilibili URL requests.

- [ ] **Step 2: Run static checks**

```sh
ruff check .
python3 -m compileall main.py tools.py db.py ui_gradio.py
```

Expected: both commands exit zero.

- [ ] **Step 3: Run non-network smoke checks**

```sh
python3 main.py --help
python3 -c "import ui_gradio; assert ui_gradio.controller.running is False"
sh -n main.sh
```

Expected: all commands exit zero and no UI server starts.

- [ ] **Step 4: Verify the database schema was not changed**

```sh
sqlite3 -readonly bilidata.db ".schema products"
```

Expected:

```sql
CREATE TABLE products (
            id TEXT PRIMARY KEY,
            name TEXT,
            price INTEGER,
            market_price INTEGER,
            rate REAL,
            time TEXT
        );
```

- [ ] **Step 5: Verify Cookie scope was untouched**

Run:

```sh
git status --short
git diff -- cookies.txt
git ls-files -v cookies.txt
```

Expected: no Cookie diff; the existing lowercase `h cookies.txt` assume-unchanged marker remains.

- [ ] **Step 6: Review the complete diff**

```sh
git diff 525d08e..HEAD --stat
git diff 525d08e..HEAD -- . ':(exclude)cookies.txt'
```

Confirm:

- no database file is staged;
- no CSV or checkpoint is staged;
- no Streamlit import/documentation remains;
- tests do not contain live credentials or live network calls;
- only the existing six-column SQLite table is used.

- [ ] **Step 7: Commit any verification-only fixes**

If verification required edits:

```sh
git add <only-the-files-fixed>
git commit -m "fix: address scraper verification findings"
```

If no edits were required, do not create an empty commit.

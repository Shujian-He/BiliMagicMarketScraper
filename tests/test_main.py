import csv
import sqlite3
import sys
from pathlib import Path
from threading import Event

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main
from main import (
    CrawlStatus,
    CursorStalledError,
    OutputPaths,
    ProductRecord,
    ScrapeConfig,
    ScraperError,
    build_parser,
    config_from_args,
    crawl,
    parse_product,
    persist_page,
)


class CountingConnection:
    def __init__(self):
        self.connection = sqlite3.connect(":memory:")
        self.connection.execute(
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
        self.calls = []
        self.closed = False

    def post(self, url, *, headers, json, timeout):
        self.calls.append((url, headers, json, timeout))
        return FakeResponse(next(self.payloads))

    def close(self):
        self.closed = True


def empty_page(next_id):
    return {"code": 0, "data": {"data": [], "nextId": next_id}}


def valid_item(name="Miku, Racing\nVersion", product_id="42"):
    return {
        "totalItemsCount": 1,
        "c2cItemsName": name,
        "c2cItemsId": product_id,
        "price": "5000",
        "detailDtoList": [{"marketPrice": "10000"}],
    }


def test_parse_product_keeps_comma_and_normalizes_newline():
    record = parse_product(valid_item(), "2026-01-01 00:00:00")

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
    connection = CountingConnection()
    paths = OutputPaths(
        total=tmp_path / "total.csv",
        wanted=tmp_path / "want.csv",
        checkpoint=tmp_path / "nextId.txt",
    )
    record = ProductRecord("time", "Miku, Racing", "42", 5000, 10000, 0.5)

    persist_page(connection, [record], ["Miku"], paths)

    with paths.total.open(newline="", encoding="utf-8") as handle:
        assert list(csv.reader(handle))[0][1] == "Miku, Racing"
    with paths.wanted.open(newline="", encoding="utf-8") as handle:
        assert list(csv.reader(handle))[0][2] == "42"
    assert connection.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 1
    assert connection.commits == 1


def test_persist_page_rolls_back_files_and_database(tmp_path, monkeypatch):
    connection = CountingConnection()
    paths = OutputPaths(
        total=tmp_path / "total.csv",
        wanted=tmp_path / "want.csv",
        checkpoint=tmp_path / "nextId.txt",
    )
    record = ProductRecord("time", "Miku", "42", 5000, 10000, 0.5)

    def fail_after_insert(rows, database):
        database.execute(
            """
            INSERT INTO products (id, name, price, market_price, rate, time)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            rows[0],
        )
        raise RuntimeError("database failure")

    monkeypatch.setattr(main, "insert_products", fail_after_insert)

    with pytest.raises(RuntimeError, match="database failure"):
        persist_page(connection, [record], ["Miku"], paths)

    assert paths.total.read_text(encoding="utf-8") == ""
    assert paths.wanted.read_text(encoding="utf-8") == ""
    assert connection.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0
    assert connection.rollbacks == 1


def test_persist_page_rolls_back_when_commit_is_interrupted(tmp_path, monkeypatch):
    connection = CountingConnection()
    paths = OutputPaths(
        total=tmp_path / "total.csv",
        wanted=tmp_path / "want.csv",
        checkpoint=tmp_path / "nextId.txt",
    )
    record = ProductRecord("time", "Miku", "42", 5000, 10000, 0.5)

    def interrupted_commit():
        raise KeyboardInterrupt

    monkeypatch.setattr(connection, "commit", interrupted_commit)

    with pytest.raises(KeyboardInterrupt):
        persist_page(connection, [record], ["Miku"], paths)

    assert paths.total.read_text(encoding="utf-8") == ""
    assert paths.wanted.read_text(encoding="utf-8") == ""
    assert connection.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0
    assert connection.rollbacks == 1


def test_crawl_finishes_and_clears_checkpoint(tmp_path):
    paths = OutputPaths.for_run(tmp_path, "run")
    paths.checkpoint.write_text("old", encoding="utf-8")
    session = FakeSession([empty_page(None)])

    result = crawl(
        CountingConnection(),
        ScrapeConfig(("Miku",), ("20000-0",), ("70-100",), ""),
        paths=paths,
        session=session,
        page_sleep=lambda _event: False,
        periodic_sleep=lambda start, _event: (start, False),
    )

    assert result is CrawlStatus.FINISHED
    assert paths.checkpoint.read_text(encoding="utf-8") == ""
    assert session.closed is False


def test_crawl_rejects_repeated_cursor_before_writing_page(tmp_path):
    paths = OutputPaths.for_run(tmp_path, "run")

    with pytest.raises(CursorStalledError, match="cursor-1"):
        crawl(
            CountingConnection(),
            ScrapeConfig(("Miku",), ("20000-0",), ("70-100",), ""),
            start_next_id="cursor-1",
            paths=paths,
            session=FakeSession([empty_page("cursor-1")]),
            page_sleep=lambda _event: False,
            periodic_sleep=lambda start, _event: (start, False),
        )

    assert not paths.total.exists()
    assert not paths.wanted.exists()


def test_crawl_rejects_malformed_api_data(tmp_path):
    malformed = {"code": 0, "data": {"data": None, "nextId": None}}

    with pytest.raises(ScraperError, match="data field must be a list"):
        crawl(
            CountingConnection(),
            ScrapeConfig(("Miku",), ("20000-0",), ("70-100",), ""),
            paths=OutputPaths.for_run(tmp_path, "run"),
            session=FakeSession([malformed]),
            page_sleep=lambda _event: False,
            periodic_sleep=lambda start, _event: (start, False),
        )


def test_crawl_skips_invalid_item_and_writes_valid_item(tmp_path):
    logs = []
    response = {
        "code": 0,
        "data": {
            "data": [
                {"totalItemsCount": 2},
                valid_item(name="Miku", product_id="valid"),
            ],
            "nextId": None,
        },
    }
    connection = CountingConnection()

    result = crawl(
        connection,
        ScrapeConfig(("Miku",), ("20000-0",), ("70-100",), ""),
        paths=OutputPaths.for_run(tmp_path, "run"),
        session=FakeSession([response]),
        log=logs.append,
        page_sleep=lambda _event: False,
        periodic_sleep=lambda start, _event: (start, False),
    )

    assert result is CrawlStatus.FINISHED
    assert connection.execute("SELECT id FROM products").fetchone()[0] == "valid"
    assert any("Skipping item" in message for message in logs)


def test_crawl_stops_at_page_boundary(tmp_path):
    stop_event = Event()
    stop_event.set()

    result = crawl(
        CountingConnection(),
        ScrapeConfig(("Miku",), ("20000-0",), ("70-100",), ""),
        paths=OutputPaths.for_run(tmp_path, "run"),
        session=FakeSession([]),
        stop_event=stop_event,
        page_sleep=lambda _event: False,
        periodic_sleep=lambda start, _event: (start, False),
    )

    assert result is CrawlStatus.STOPPED


def test_invalid_filters_fall_back_to_defaults():
    messages = []
    args = build_parser().parse_args(["-p", "bad", "-d", "bad", "-c", "bad"])

    config = config_from_args(args, log=messages.append)

    assert config.price_filters == ("10000-20000", "20000-0")
    assert config.discount_filters == ("0-30", "30-50", "50-70", "70-100")
    assert config.category_filter == ""
    assert len(messages) == 3


def test_cli_uses_checkpoint_and_closes_connection(monkeypatch):
    class FakeConnection:
        closed = False

        def close(self):
            self.closed = True

    connection = FakeConnection()
    captured = {}

    monkeypatch.setattr(main, "initialize_database", lambda: connection)
    monkeypatch.setattr(main, "load_checkpoint", lambda: "cursor-1")

    def fake_crawl(database, config, *, start_next_id):
        captured["database"] = database
        captured["config"] = config
        captured["next_id"] = start_next_id
        return CrawlStatus.FINISHED

    monkeypatch.setattr(main, "crawl", fake_crawl)

    exit_code = main.main(["--id"])

    assert exit_code == 0
    assert captured["database"] is connection
    assert captured["next_id"] == "cursor-1"
    assert connection.closed is True


def test_cli_returns_nonzero_for_scraper_error(monkeypatch, capsys):
    class FakeConnection:
        closed = False

        def close(self):
            self.closed = True

    connection = FakeConnection()
    monkeypatch.setattr(main, "initialize_database", lambda: connection)

    def failing_crawl(*_args, **_kwargs):
        raise ScraperError("broken response")

    monkeypatch.setattr(main, "crawl", failing_crawl)

    exit_code = main.main([])

    assert exit_code == 1
    assert "broken response" in capsys.readouterr().err
    assert connection.closed is True


def test_cli_returns_nonzero_for_checkpoint_io_error(monkeypatch, capsys):
    def failing_checkpoint():
        raise OSError("checkpoint unavailable")

    monkeypatch.setattr(main, "load_checkpoint", failing_checkpoint)

    exit_code = main.main(["--id"])

    assert exit_code == 1
    assert "checkpoint unavailable" in capsys.readouterr().err

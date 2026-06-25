"""Core crawler for Bilibili Magic Market."""

import csv
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from threading import Event

import requests

from db import insert_products
from tools import check_and_sleep, load_cookie, random_sleep, send_request, write_checkpoint

MARKET_URL = "https://mall.bilibili.com/mall-magic-c/internet/c2c/v2/list"
USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) "
    "AppleWebKit/619.2.8.10.7 (KHTML, like Gecko) Mobile/22B83 "
    "BiliApp/81900100 os/ios model/iPhone 14 Pro"
)


class ScraperError(RuntimeError):
    """Raised when the API response cannot be processed safely."""


class CursorStalledError(ScraperError):
    """Raised when the server returns the same non-empty cursor."""


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
    try:
        if int(item.get("totalItemsCount", 0)) > 1:
            raise ValueError("multi-item packages are unsupported")

        details = item["detailDtoList"]
        market_price = int(details[0]["marketPrice"])
        price = int(item["price"])
        name = " ".join(str(item["c2cItemsName"]).splitlines()).strip()
        product_id = str(item["c2cItemsId"]).strip()
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        if isinstance(exc, ValueError) and str(exc) == "multi-item packages are unsupported":
            raise
        raise ValueError(f"invalid product: {exc}") from exc

    if not name or not product_id:
        raise ValueError("invalid product: name and id are required")
    if market_price <= 0 or price < 0:
        raise ValueError("invalid product: price values are out of range")

    return ProductRecord(
        captured_at=captured_at,
        name=name,
        product_id=product_id,
        price=price,
        market_price=market_price,
        rate=price / market_price,
    )


def persist_page(connection, records, want_list, paths):
    """Persist one page, rolling back database and CSV appends together on failure."""
    wanted_records = [
        record for record in records if any(keyword in record.name for keyword in want_list)
    ]
    paths.total.parent.mkdir(parents=True, exist_ok=True)
    paths.wanted.parent.mkdir(parents=True, exist_ok=True)

    with (
        paths.total.open("a+", newline="", encoding="utf-8") as total_file,
        paths.wanted.open("a+", newline="", encoding="utf-8") as wanted_file,
    ):
        total_file.seek(0, 2)
        wanted_file.seek(0, 2)
        total_position = total_file.tell()
        wanted_position = wanted_file.tell()

        try:
            insert_products([record.database_row() for record in records], connection)
            csv.writer(total_file).writerows(record.csv_row() for record in records)
            csv.writer(wanted_file).writerows(
                record.csv_row() for record in wanted_records
            )
            total_file.flush()
            wanted_file.flush()
            connection.commit()
        except Exception:
            connection.rollback()
            total_file.seek(total_position)
            total_file.truncate()
            wanted_file.seek(wanted_position)
            wanted_file.truncate()
            raise


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

    normalized_next_id = None if next_id in (None, "") else str(next_id)
    return items, normalized_next_id


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
    """Crawl pages until completion, cancellation, or a non-recoverable error."""
    stop_event = stop_event or Event()
    run_id = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    paths = paths or OutputPaths.for_run(".", run_id)
    owns_session = session is None
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
                        parse_product(
                            item,
                            datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
                        )
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
        if owns_session:
            session.close()

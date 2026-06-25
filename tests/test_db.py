import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

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


def test_initialize_database_keeps_existing_products_schema(tmp_path):
    connection = initialize_database(tmp_path / "products.db")

    columns = connection.execute("PRAGMA table_info(products)").fetchall()

    assert [(column[1], column[2], column[5]) for column in columns] == [
        ("id", "TEXT", 1),
        ("name", "TEXT", 0),
        ("price", "INTEGER", 0),
        ("market_price", "INTEGER", 0),
        ("rate", "REAL", 0),
        ("time", "TEXT", 0),
    ]

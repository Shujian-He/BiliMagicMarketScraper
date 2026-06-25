"""
SQLite persistence for Bilibili Magic Market products.

The schema intentionally remains compatible with existing ``bilidata.db`` files.
"""

import csv
import glob
import sqlite3

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


def initialize_database(file_path="bilidata.db"):
    connection = sqlite3.connect(file_path)
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS products (
            id TEXT PRIMARY KEY,
            name TEXT,
            price INTEGER,
            market_price INTEGER,
            rate REAL,
            time TEXT
        )
        """
    )
    connection.commit()
    return connection


def insert_products(rows, connection):
    """Upsert structured product rows without committing the transaction."""
    connection.executemany(UPSERT_PRODUCTS, rows)


def insert_csv(total_file, connection):
    rows = []
    with open(total_file, newline="", encoding="utf-8") as file:
        for captured_at, name, product_id, price, market_price, rate in csv.reader(file):
            rows.append(
                (
                    product_id,
                    name,
                    int(price),
                    int(market_price),
                    float(rate),
                    captured_at,
                )
            )

    insert_products(rows, connection)
    connection.commit()
    connection.close()


if __name__ == "__main__":
    for csv_file in glob.glob("total_*.csv"):
        database = initialize_database()
        insert_csv(csv_file, database)

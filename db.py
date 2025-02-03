"""
db.py
Bili Market Scraper
-------------------
Author: Shujian
Description: A scraper getting your favorite items in Bilibili magic market.
License: MIT License
"""

"""
Special thanks to ChatGPT!
"""

import sqlite3
import csv
import glob

def initialize_database():
    # Initialize database connection
    conn = sqlite3.connect("bilidata.db")
    cursor = conn.cursor()
    
    # Create the table if it doesn't exist
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id TEXT PRIMARY KEY,
            name TEXT,
            price INTEGER,
            market_price INTEGER,
            rate REAL,
            time TEXT
        )
    """)
    conn.commit()
    return conn

def read_and_save(totalFile, conn):
    cursor = conn.cursor()
    # Read data from the CSV file
    with open(totalFile, "r") as file:
        reader = csv.reader(file)
        for row in reader:
            # print(row)
            time, name, id_, price, market_price, rate = row
            
            # Insert data into the database
            cursor.execute("""
                INSERT OR REPLACE INTO products (id, name, price, market_price, rate, time)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                id_,
                name,
                int(price),
                int(market_price),
                float(rate),
                time
            ))
            
    # Commit and close the database connection
    conn.commit()
    conn.close()

if __name__ == "__main__":
    files = glob.glob("total_*.csv")
    for file in files:
        conn = initialize_database()
        read_and_save(file, conn)

"""
tools.py
Bili Market Scraper
-------------------
Author: Shujian
Description: A scraper getting your favorite items in Bilibili magic market.
License: MIT License
"""

def load_cookie(file_path='cookies.txt'):
    try:
        with open(file_path, 'r') as file:
            return file.read().strip()
    except FileNotFoundError:
        print(f"Cookie file '{file_path}' not found.")
        return ''

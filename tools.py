"""
tools.py
Bili Market Scraper
-------------------
Author: Shujian
Description: A scraper getting your favorite items in Bilibili magic market.
License: MIT License
"""
import requests

def load_cookie(file_path='cookies.txt'):
    try:
        with open(file_path, 'r') as file:
            return file.read().strip()
    except FileNotFoundError:
        print(f"Cookie file '{file_path}' not found.")
        return ''

def send_request(url, headers, payload):
    response = requests.request("POST", url, headers=headers, data=payload, timeout=10)
    try:
        return response.json()
    except Exception as e:
        print(response.text)
        print("\nError Decoding json:", e)
        return None
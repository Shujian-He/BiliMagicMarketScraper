"""
tools.py
Bili Market Scraper
-------------------
Author: Shujian
Description: A scraper getting your favorite items in Bilibili magic market.
License: MIT License
"""

import requests
import time
from datetime import datetime, timedelta
import random

def load_cookie(file_path='cookies.txt'):
    try:
        with open(file_path, 'r') as file:
            return file.read().strip()
    except FileNotFoundError:
        print(f"Cookie file '{file_path}' not found.")
        return ''

def send_request(url, headers, payload):
    response = requests.post(url, headers=headers, json=payload)
    try:
        return response.json()
    except Exception as e:
        # print(response.text)
        print("\nError Decoding json:", e)
        return None
    
def check_and_sleep(startTime):
    currentTime = datetime.now()
    
    if currentTime - startTime >= timedelta(seconds=600):
        print("Start to sleep for 60s")
        try:
            for i in range(0, 60):
                time.sleep(1)
                print(f"{i+1}s passed...")
        except KeyboardInterrupt:
            print("Sleep interrupted by user. Exiting.")
            return startTime
        print("Slept for 60s")
        startTime = datetime.now()

    return startTime

def random_sleep():
    # High probability to sleep for a short time
    if random.random() < 0.9:
        sleep_time = random.uniform(1, 1.5)
    # Low probability to sleep for a longer time 
    else:
        sleep_time = random.uniform(2, 3)
    # print(f"Sleeping for {sleep_time:.2f} seconds.")
    time.sleep(sleep_time)

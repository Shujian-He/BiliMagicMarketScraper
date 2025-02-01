"""
main.py
Bili Market Scraper
-------------------
Author: Shujian
Description: A scraper getting your favorite items in Bilibili magic market.
License: MIT License
"""

import os
import time
from datetime import datetime
import requests
import json
import random
from db import initialize_database, read_and_save
import argparse

# function to load cookies
def load_cookie(file_path='cookies.txt'):
    try:
        with open(file_path, 'r') as file:
            return file.read().strip()
    except FileNotFoundError:
        print(f"Cookie file '{file_path}' not found.")
        return ''

# create the parser
parser = argparse.ArgumentParser(description="Process critical arguments.")

# define wanted item names in list
parser.add_argument(
    "-w", "--want",
    nargs="+",  # Allows multiple arguments for this option
    default=["初音未来"],
    help="List of wanted item names (default: ['mega39'])"
)
# define priceFilters: in cents, 0 is infinite
parser.add_argument(
    "-p", "--price",
    nargs=1, # Accept only one value but store it as a list
    default=["6000-10000"],
    help="price ranges in cents (default: ['6000-10000'])"
)
# define discountFilters: percentage
parser.add_argument(
    "-d", "--discount",
    nargs=1, # Accept only one value but store it as a list
    default=["0-100"],
    help="discount rate (default: ['0-100'])"
)

args = parser.parse_args()
wantList = args.want
priceFilters = args.price
discountFilters = args.discount

print("Want List:", wantList)
print("Price Filters:", priceFilters)

# define URL for market
url = "https://mall.bilibili.com/mall-magic-c/internet/c2c/v2/list"

# defime filenames
timeForFilename = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
wantFile = f"want_{timeForFilename}.csv"
totalFile = f"total_{timeForFilename}.csv"

# define nextId
nextId = None

# define start time for the loop
startTime = int(time.time())

while True:
    payload = json.dumps({
        "categoryFilter": "2312", # categoryFilter: 2312 for figure
        "priceFilters": priceFilters,
        "discountFilters": discountFilters,
        "nextId": nextId
    })

    headers = {
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/619.2.8.10.7 (KHTML, like Gecko) Mobile/22B83 BiliApp/81900100 os/ios model/iPhone 14 Pro mobi_app/iphone build/81900100 osVer/18.1 network/2 channel/AppStore',
        'Cookie': load_cookie()
    }
    try:
        # sleep for 60s after 1h running
        currTime = int(time.time())
        print("startTime:", startTime)
        print("currTime:", currTime)
        if currTime - startTime > 3600:
            print("Start to sleep for 60s")
            for i in range(0,60):
                time.sleep(1)
                print(f"{i+1}s passed...")
            print("Slept for 60s")
            startTime = int(time.time())
        
        # send request
        response = requests.request("POST", url, headers=headers, data=payload, timeout=10)
        print(response.text)
        response = response.json()

        # update nextId
        nextId = response.get("data", {}).get("nextId") # This will return None if "data" doesn’t exist.
        if nextId is None:
            print("\nEnd reached.")
            break
        
        # extract data & process
        data = response["data"]["data"]
        for item in data:
            timeNow = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
            item['time'] = timeNow

            # skip package with multiple items
            if item['totalItemsCount'] > 1:
                continue

            name = item["c2cItemsName"]
            id = item['c2cItemsId']
            price = item['price']
            marketPrice = item['detailDtoList'][0]['marketPrice']
            rate = int(price) / int(marketPrice)

            with open(totalFile, "a") as file:
                file.write(f"{timeNow}, {name}, {id}, {price}, {marketPrice}, {rate}\n")

            for wantName in wantList:
                if wantName in name:
                    with open(wantFile, "a") as file:
                        file.write(f"{timeNow}, {name}, {id}, {price}, {marketPrice}, {rate}\n")

        # 90% probability to sleep for 1s to 1.2s
        if random.random() < 0.9:
            time.sleep(random.uniform(1, 1.2))
        # 10% probability to sleep for 1.5s to 2s
        else:
            time.sleep(random.uniform(1.5, 2))
            
    except requests.exceptions.Timeout:
        print("\nThe request timed out")
        continue
        
    except KeyboardInterrupt:
        print("\nProcess interrupted by user.")
        break

    except Exception as e:
        print("\nUnknown error occurred.")
        print("Error:", e)
        break

conn = initialize_database()

if os.path.exists(totalFile):
    read_and_save(totalFile, conn)
else:
    print(f"File '{totalFile}' does not exist.")

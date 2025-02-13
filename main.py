"""
main.py
Bili Market Scraper
-------------------
Author: Shujian
Description: A scraper getting your favorite items in Bilibili magic market.
License: MIT License
"""

from datetime import datetime
import requests
import json
from db import initialize_database, insert_line
from tools import load_cookie, send_request, check_and_sleep, random_sleep
import argparse

# create the parser
parser = argparse.ArgumentParser(description="Process critical arguments.")

# define wanted item names in list
parser.add_argument(
    "-w", "--want",
    nargs="+",  # Allows multiple arguments for this option, stored as a list
    default=["初音未来"],
    help="List of wanted item names (default: 初音未来)"
)
# define priceFilters: in cents, 0 is infinite
parser.add_argument(
    "-p", "--price",
    nargs=1, # Accept only one value but store it as a list
    default=["6000-10000"],
    help="price ranges in cents (default: 6000-10000)"
)
# define discountFilters: percentage
parser.add_argument(
    "-d", "--discount",
    nargs=1, # Accept only one value but store it as a list
    default=["0-100"],
    help="discount rate (default: 0-100)"
)
# define category filter
parser.add_argument(
    "-c", "--category",
    nargs="?", # Accept only one value
    default="2312",
    help="category filter: 2312 for figure, 2066 for model, 2331 for merch, 2273 for 3c, fudai_cate_id for fudai (default: 2312)"
)

args = parser.parse_args()
wantList = args.want
priceFilter = args.price
discountFilter = args.discount
categories = ["2312", "2066", "2331", "2273", "fudai_cate_id"]
if args.category not in categories:
    print("Invalid category filter. Use default value.")
    print("Valid category: 2312 for figure, 2066 for model, 2331 for merch, 2273 for 3c, fudai_cate_id for fudai")
    categoryFilter = "2312"
else:
    categoryFilter = args.category

print("Want List:", wantList)
print("Price Filter:", priceFilter)
print("Discount Filter:", discountFilter)
print("Category Filter:", categoryFilter)

def run_once(wantList, priceFilter, discountFilter, categoryFilter, fileTimeString, nextId=None):
    # define file names
    wantFile = f"want_{fileTimeString}.csv"
    totalFile = f"total_{fileTimeString}.csv"

    # define URL for market
    url = "https://mall.bilibili.com/mall-magic-c/internet/c2c/v2/list"

    # define payload
    payload = json.dumps({
        "categoryFilter": categoryFilter,
        "priceFilters": priceFilter,
        "discountFilters": discountFilter,
        "sortType": "TIME_ASC",
        "nextId": nextId
    })

    # define headers
    headers = {
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/619.2.8.10.7 (KHTML, like Gecko) Mobile/22B83 BiliApp/81900100 os/ios model/iPhone 14 Pro mobi_app/iphone build/81900100 osVer/18.1 network/2 channel/AppStore',
        'Cookie': load_cookie()
    }

    # initialize database connection
    conn = initialize_database()
    
    try:
        # send request
        random_sleep()
        responseData = send_request(url, headers, payload)

        if responseData is None:
            print("\nNo response data. Retry.")
            return nextId
        elif responseData["code"] != 0:
            print(responseData)
            print("\nError occurred when getting data. Retry.")
            return nextId

        # extract data & process
        data = responseData["data"]["data"]
        for item in data:
            timeNow = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
            item['time'] = timeNow

            # skip package with multiple items
            if item['totalItemsCount'] > 1:
                continue

            name = item["c2cItemsName"].replace("\n", " ").replace(",", " ").strip() # to avoid linefeed & comma
            id = item['c2cItemsId']
            price = item['price']
            marketPrice = item['detailDtoList'][0]['marketPrice']
            rate = int(price) / int(marketPrice)

            lineToWrite = f"{timeNow},{name},{id},{price},{marketPrice},{rate}\n"
            insert_line(lineToWrite.strip(), conn)
            conn.commit()

            with open(totalFile, "a") as file:
                file.write(lineToWrite)

            with open(wantFile, "a") as file:
                for wantName in wantList:
                    if wantName in name:
                        file.write(lineToWrite)
                        break
        
        # update nextId
        nextId = responseData["data"]["nextId"]
        print(f"Next ID: {nextId}")
        if nextId is None:
            print("\nEnd reached. Exiting.")
        return nextId
                
    except requests.exceptions.Timeout:
        print("\nThe request timed out. Retry.")
        return nextId
        
    except KeyboardInterrupt:
        print("\nProcess interrupted by user. Exiting.")
        return None

    except Exception as e:
        print(f"\nUnknown error occurred: {e}. Retry.")
        return nextId

if __name__ == "__main__":
    # record start time
    startTime = datetime.now()
    fileTimeString = startTime.strftime("%Y-%m-%d-%H-%M-%S")
    print("Start Time:", startTime.strftime("%Y-%m-%d %H:%M:%S.%f"))
    # run for the first time
    nextId = run_once(wantList, priceFilter, discountFilter, categoryFilter, fileTimeString, None)
    while nextId:
        # record current time
        print("Current Time:", datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"))
        # sleep for 60s after a period of time
        startTime = check_and_sleep(startTime)
        # run again
        nextId = run_once(wantList, priceFilter, discountFilter, categoryFilter, fileTimeString, nextId)

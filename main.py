"""
main.py
Bili Market Scraper
-------------------
Author: Shujian
Description: A scraper getting your favorite items in Bilibili magic market.
License: MIT License
"""

import time
from datetime import datetime
import requests
import json
import random
from db import initialize_database, insert_csv, insert_line
from tools import load_cookie, send_request
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
    help="category filter: 2312 for figure, 2066 for model, 2331 for goods, 2273 for 3c, fudai_cate_id for fudai (default: 2312)"
)

args = parser.parse_args()
wantList = args.want
priceFilter = args.price
discountFilter = args.discount
categories = ["2312", "2066", "2331", "2273", "fudai_cate_id"]
if args.category not in categories:
    print("Invalid category filter. Use default value.")
    print("Valid category: 2312 for figure, 2066 for model, 2331 for goods, 2273 for 3c, fudai_cate_id for fudai")
    categoryFilter = "2312"
else:
    categoryFilter = args.category

print("Want List:", wantList)
print("Price Filter:", priceFilter)
print("Discount Filter:", discountFilter)
print("Category Filter:", categoryFilter)

def run(wantList, priceFilter, discountFilter):
    # define URL for market
    url = "https://mall.bilibili.com/mall-magic-c/internet/c2c/v2/list"

    # defime filenames
    fileTime = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    wantFile = f"want_{fileTime}.csv"
    totalFile = f"total_{fileTime}.csv"

    # define nextId
    nextId = None

    # define start time for the loop
    startTime = time.time()
    print("Start Time:", time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(startTime)))

    conn = initialize_database()

    while True:
        payload = json.dumps({
            "categoryFilter": categoryFilter,
            "priceFilters": priceFilter,
            "discountFilters": discountFilter,
            "sortType": "TIME_ASC",
            "nextId": nextId
        })

        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/619.2.8.10.7 (KHTML, like Gecko) Mobile/22B83 BiliApp/81900100 os/ios model/iPhone 14 Pro mobi_app/iphone build/81900100 osVer/18.1 network/2 channel/AppStore',
            'Cookie': load_cookie()
        }
        try:
            # sleep for 60s after a period of time
            currentTime = time.time()
            print("Current Time:", time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(currentTime)))

            if currentTime - startTime > 600:
                print("Start to sleep for 60s")
                for i in range(0,60):
                    time.sleep(1)
                    print(f"{i+1}s passed...")
                print("Slept for 60s")
                startTime = time.time()
            
            # send request
            while True:
                retry = False
                responseData = send_request(url, headers, payload)
                if responseData is None:
                    retry = True
                    break
                elif responseData["code"] != 0:
                    print(responseData)
                    print("\nError occurred when getting data. Retrying...")
                    continue
                else:
                    break
            if retry:
                continue
            

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

                with open(totalFile, "a") as file:
                    file.write(lineToWrite)

                for wantName in wantList:
                    if wantName in name:
                        with open(wantFile, "a") as file:
                            file.write(lineToWrite)
                        break

            conn.commit()
            
            # update nextId
            nextId = responseData["data"]["nextId"]
            print(f"Next ID: {nextId}")
            if nextId is None:
                print("\nEnd reached.")
                break

            # high probability to sleep for short time
            if random.random() < 0.9:
                time.sleep(random.uniform(1, 2))
            # low probability to sleep for lone time
            else:
                time.sleep(random.uniform(2, 3))
                
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

    conn.close()

    # if os.path.exists(totalFile):
    #     insert_csv(totalFile, conn)
    #     return totalFile
    # else:
    #     print(f"File '{totalFile}' does not exist.")
    #     return None

if __name__ == "__main__":
    run(wantList, priceFilter, discountFilter)
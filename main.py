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
from db import initialize_database, insert_line
from tools import load_cookie, send_request, check_and_sleep, random_sleep
import argparse

def run_once(conn, wantList, priceFilter, discountFilter, categoryFilter, fileTimeString, nextId=None):
    # define file names
    wantFile = f"want_{fileTimeString}.csv"
    totalFile = f"total_{fileTimeString}.csv"

    # define URL for market
    url = "https://mall.bilibili.com/mall-magic-c/internet/c2c/v2/list"

    # define payload, payload is a dict if using json parameter in requests.post
    # Note that nextId does not individually represent the next page, must include other parameters
    payload = {
        "categoryFilter": categoryFilter,
        "priceFilters": priceFilter,
        "discountFilters": discountFilter,
        "sortType": "TIME_DESC",
        "nextId": nextId
    }
    # print(f"Payload: {payload}\ntype: {type(payload)}")

    # define headers, header is a dict, not json string
    headers = {
        "Content-Type": "application/json",
        "User-Agent": 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/619.2.8.10.7 (KHTML, like Gecko) Mobile/22B83 BiliApp/81900100 os/ios model/iPhone 14 Pro mobi_app/iphone build/81900100 osVer/18.1 network/2 channel/AppStore',
        "Cookie": load_cookie()
    }
    # print(f"Headers: {headers}\ntype: {type(headers)}")
    
    try:
        # send request
        random_sleep()
        responseData = send_request(url, headers, payload)

        if responseData is None:
            print("\nNo response data. Possibly blocked. Retrying in 5 seconds.")
            time.sleep(5)
            return nextId
        elif responseData["code"] != 0:
            print(responseData)
            print("\nError occurred when getting data. Retrying.")
            return nextId

        # extract data & process
        data = responseData["data"]["data"]
        if data is None:
            print(responseData)
            print("\nNo data. Possibly illegal request. Retrying in 5 seconds.")
            time.sleep(5)
            return nextId
        
        for item in data:
            timeNow = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
            # item['time'] = timeNow

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

            # write total file
            with open(totalFile, "a") as file:
                file.write(lineToWrite)

            # write want file, avoid redundant open
            for wantName in wantList:
                if wantName in name:
                    with open(wantFile, "a") as file:
                        file.write(lineToWrite)
                    break
        
        # update nextId
        nextId = responseData["data"]["nextId"]
        print(f"Next ID: {nextId}")
        if nextId is None:
            print("\nEnd reached. Exiting.")
            open('nextId.txt', 'w').close()
        else:
            with open("nextId.txt", "w") as file:
                file.write(nextId)
        return nextId
                
    except requests.exceptions.Timeout:
        print("\nThe request timed out. Retrying.")
        return nextId
        
    except KeyboardInterrupt:
        print("\nProcess interrupted by user. Press 'r' to run again or any other key to exit.")
        choice = input().strip().lower()
        if choice != 'r':
            print("Progress saved. Exiting.")
            return None
        else:
            print("Running again.")
            return nextId

    except Exception as e:
        print(f"\nUnknown error occurred: {e}. Retrying.")
        return nextId

if __name__ == "__main__":
    # create the parser
    parser = argparse.ArgumentParser(description="Process arguments.")

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
        nargs="+", # Allows multiple arguments for this option, stored as a list
        default=["10000-20000", "20000-0"],
        help="Price ranges in cents (0 is infinite, default: 10000-20000 20000-0)"
    )
    # define discountFilters: percentage
    parser.add_argument(
        "-d", "--discount",
        nargs="+", # Allows multiple arguments for this option, stored as a list
        default=["0-30", "30-50", "50-70", "70-100"],
        help="Discount rate (default: 0-30 30-50 50-70 70-100)"
    )
    # define category filter
    parser.add_argument(
        "-c", "--category",
        nargs="?", # Accept only one value
        default="",
        help="Category filter (2312 for figure, 2066 for model, 2331 for merch, 2273 for 3c, fudai_cate_id for fudai, default: blank)"
    )
    # judge whether to get nextId from nextId.txt
    parser.add_argument('--id', action='store_true', help="Get nextId from nextId.txt")
    args = parser.parse_args()

    # define wantList, priceFilter, discountFilter, categoryFilter
    wantList = args.want
    priceFilter = args.price
    discountFilter = args.discount
    categoryFilter = args.category

    # check if the input is valid
    prices = ["0-2000", "2000-3000", "3000-5000", "5000-10000", "10000-20000", "20000-0"]
    for price in priceFilter:
        if price not in prices:
            print(f"{price}: Invalid price filter. Use default value. ", end="")
            print("Valid price: 0-2000, 2000-3000, 3000-5000, 5000-10000, 10000-20000, 20000-0")
            priceFilter = ["10000-20000", "20000-0"]
            break

    discounts = ["0-30", "30-50", "50-70", "70-100"]
    for discount in discountFilter:
        if discount not in discounts:
            print(f"{discount}: Invalid discount filter. Use default value. ", end="")
            print("Valid discount: 0-30, 30-50, 50-70, 70-100")
            discountFilter = ["0-30", "30-50", "50-70", "70-100"]
            break

    categories = ["2312", "2066", "2331", "2273", "fudai_cate_id", ""]
    if categoryFilter not in categories:
        print(f"{categoryFilter}: Invalid category filter. Use default value. ", end="")
        print("Valid category: 2312 for figure, 2066 for model, 2331 for merch, 2273 for 3c, fudai_cate_id for fudai")
        categoryFilter = ""

    # check if nextId exists if use --id
    nextId = None
    if args.id:
        try:
            with open("nextId.txt", 'r') as file:
                content = file.read().strip()
                if len(content) == 0:
                    print("\nnextId.txt is empty. Start from the beginning.")
                else:
                    nextId = content
                    print(f"\nContinue from ID: {nextId}")
        except FileNotFoundError:
            print("\nnextId.txt does not exist. Start from the beginning.")

    # print parameters
    print("\n", end="")
    print("Want List:", wantList)
    print("Price Filter:", priceFilter)
    print("Discount Filter:", discountFilter)
    print("Category Filter:", categoryFilter)
    print("Read Next ID:", nextId)
    print("\n", end="")

    # initialize database connection
    conn = initialize_database()

    # record start time
    startTime = datetime.now()
    fileTimeString = startTime.strftime("%Y-%m-%d-%H-%M-%S")
    print("Start Time:", startTime.strftime("%Y-%m-%d %H:%M:%S.%f"))
    # run for the first time
    nextId = run_once(conn, wantList, priceFilter, discountFilter, categoryFilter, fileTimeString, nextId) # last parameter must be nextId, not None, otherwise read nextId from nextId.txt will not work
    while nextId:
        # record current time
        print("Current Time:", datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"))
        # sleep for 60s after a period of time
        startTime = check_and_sleep(startTime)
        # run again
        nextId = run_once(conn, wantList, priceFilter, discountFilter, categoryFilter, fileTimeString, nextId)

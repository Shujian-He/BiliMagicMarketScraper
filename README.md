
# Bilibili Magic Market Scraper

## Overview

**Bilibili Magic Market Scraper** is a Python-based web scraping tool designed to extract product listings from the Bilibili magic market. It focuses on finding your favorite items based on specified criteria such as item name, price range, discount rate and category.

## Features

- **Customizable Item Search**: Filter by item names, price ranges, discount rates and categories.
- **Automated Data Storage**: Saves the scraped data into CSV files and an SQLite database.

## Project Structure

```
├── main.py          # The main scraper script
├── db.py            # Handles database operations (SQLite)
├── tools.py         # Additional helper functions
├── sort_total.sh    # Shell script for sorting CSV files
├── main.sh          # Shell script warpping main script (for shell lovers)
├── cookies.txt      # Text file to put cookies from Bilibili
├── bilidata.db      # SQLite database (created upon running the scraper)
├── total_*.csv      # CSV files with all scraped items (created upon running the scraper)
└── want_*.csv       # CSV files with filtered (wanted) items (created upon running the scraper)
```

## Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Shujian-He/BiliMagicMarketScraper.git
   cd BiliMarketScraper
   ```

2. **Install dependencies:**
   ```bash
   pip3 install requests
   ```

3. **Set Up Your Cookies:**
   - This scraper requires authentication cookies from your Bilibili account to access the market API.
   - Open `cookies.txt` and replace the placeholder cookies with your own.
   - You can obtain your cookies from your browser’s developer tools:
      - Login to Bilibili main site, then open Bilibili magic market at https://mall.bilibili.com/neul-next/index.html?page=magic-market_index.
      - Press F12 to open developer tools, then locate to **Network** tab.
      - Refresh the page (Press Ctrl+R on Windows or Command+R on macOS), and tap `list` file on the left side.
      - Navigate to *Headers* - *Request Headers*, copy everything after **Cookie:**.


## Usage

Run the scraper using:

```sh
python3 main.py -w <item_name> -p <price_range> -d <discount_range> -c <category>
```

or if you like shell:

```sh
sh main.sh -w <item_name> -p <price_range> -d <discount_range> -c <category>
```

### Arguments:

- `-w, --want`: One or more item names you want to track. *(Default: 初音未来)*
- `-p, --price`: Price range in cents. *(Default: 6000-10000)*
- `-d, --discount`: Discount percentage range. *(Default: 0-100)*
- `-c, --category`: Item category. 2312 for figure, 2066 for model, 2331 for goods, 2273 for 3c, fudai_cate_id for fudai. *(Default: 2312)*

### Example:

```sh
python3 main.py -w 初音未来 孤独摇滚 -p 5000-15000 -d 10-50
```

or

```sh
sh main.sh -w fufu -p 5000-50000 -d 0-100 -c 2331
```

This will generate 2 CSV files like `total_*.csv` and `want_*.csv`, while the data was automatically saved into the SQLite database (`bilidata.db`) after each successful page fetch.


## About Data

### CSV Files

The generated CSV files will have 6 columns, **without** a header row:

| Column Name      | Description                                            | Example |
|-----------------|--------------------------------------------------------|---------------------------|
| **Timestamp**   | Timestamp when the data was collected.     | `2025-02-01 16:04:41.964444` |
| **Product Name** | Name of the product.   | `S-FIRE 初音未来 秋日之约Ver. 正比手办` |
| **Product ID**   | Unique product identifier.         | `142389472138` |
| **Current Price** | Selling price of the product in cents.             | `34344` |
| **Original Price** | Original price of the product in cents.                   | `50500` |
| **Discount Rate** | Discount rate compared to the original price.        | `0.6800792079207921` |

- After scraping, you can sort the CSV files by item name and discount rate by running:

   ```bash
   sh sort_total.sh
   ```

   This will generate 2 sorted files like `sort_total_*.csv` and `sort_want_*.csv`.

### Database
The database will have a similar structure:

| Column Name  | Type   | Description |
|--------------|--------|-------------|
| `id`         | TEXT   | Unique product identifier (Primary Key). |
| `name`       | TEXT   | Name of the product. |
| `price`      | INTEGER | Selling price of the product in cents. |
| `market_price` | INTEGER | Original price of the product in cents. |
| `rate`       | REAL   | Discount rate of the product. |
| `time`       | TEXT   | Timestamp of data collection. |

It can be queried using tools like `DB Browser for SQLite` or via Python.
- In case of main script error, run

   ```sh
   python3 db.py
   ```

   to manually save data in CSV files into the database.


## How can I use the data

You may access a specfic item by its product id, just use the following link but ***replace `<REPLACE_THIS_WITH_PRODUCT_ID>` with the product id*** in your browser:
```
https://mall.bilibili.com/neul-next/index.html?page=magic-market_detail&noTitleBar=1&itemsId=<REPLACE_THIS_WITH_PRODUCT_ID>&from=market_index
```
For example the link should be like:

```
https://mall.bilibili.com/neul-next/index.html?page=magic-market_detail&noTitleBar=1&itemsId=142389472138&from=market_index
```


## License

This project is licensed under the MIT License. See the [LICENSE](./LICENSE) file for details.

## Acknowledgments

Special thanks to ChatGPT for assistance with coding and documentation.

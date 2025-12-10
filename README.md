
# Bilibili Magic Market Scraper

[English README](README.md) | [中文 README](README.zh.md)

## Overview

**Bilibili Magic Market Scraper** is a Python-based web scraping tool designed to extract product listings from Bilibili magic market. It focuses on finding your favorite items based on specified criteria such as item name, price range, discount rate and category.

## Features

- **Customizable Item Search**: Filter by item names, price ranges, discount rates and categories.
- **Automated Data Storage**: Saves the scraped data into CSV files and an SQLite database.

## Project Structure

```
├── main.py          # The main scraper script
├── db.py            # Functions handle SQLite database operations
├── tools.py         # Additional helper functions
├── ui.py            # User Interface using Streamlit
├── sort_total.sh    # Shell script for sorting CSV files
├── main.sh          # Shell script warpping main script (for shell lovers)
├── cookies.txt      # Text file to put cookies from Bilibili
├── nextId.txt       # Text file to store nextId in case of interruption. (created upon running the scraper, normally empty)
├── bilidata.db      # SQLite database (created upon running the scraper)
├── total_*.csv      # CSV files with all scraped items (created upon running the scraper)
└── want_*.csv       # CSV files with filtered (wanted) items (created upon running the scraper)
```

## Installation

### 1. Clone the repository
   ```sh
   git clone https://github.com/Shujian-He/BiliMagicMarketScraper.git
   cd BiliMagicMarketScraper
   ```

### 2. Install dependencies
   ```sh
   pip3 install requests
   ```

### 3. Set Up Your Cookies
   - This scraper requires authentication cookies from your Bilibili account to access the market API.
   - Open `cookies.txt` and replace the placeholder cookies with your own.
   - You can obtain your cookies from your browser’s developer tools:
      - Login to [Bilibili main site](https://www.bilibili.com/), then open [Bilibili magic market](https://mall.bilibili.com/neul-next/index.html?page=magic-market_index).
      - Press F12 to open developer tools, then locate to **Network** tab.
      - Refresh the page (Press Ctrl+R on Windows or command+R on macOS), and tap `list` file on the left side.
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

### Arguments

- `-w, --want`: ***One or more*** item names you want to track. *(Default: `初音未来`)*
- `-p, --price`: ***One or more*** price range in cents. *(Default: `10000-20000` `20000-0`)*
  - `0-2000`: 0 to 20 RMB Yuan
  - `2000-3000`: 20 to 30 RMB Yuan
  - `3000-5000`: 30 to 50 RMB Yuan
  - `5000-10000`: 50 to 100 RMB Yuan
  - `10000-20000`: 100 to 200 RMB Yuan
  - `20000-0`: 200 RMB Yuan and more
- `-d, --discount`: ***One or more*** discount percentage range. *(Default: `0-30` `30-50` `50-70` `70-100`)*
  - `0-30`: 100% to 70% discount
  - `30-50`: 70% to 50% discount
  - `50-70`: 50% to 30% discount
  - `70-100`: 30% to 0 discount
- `-c, --category`: ***ONE*** item category. *(Default: blank)*
  - `2312`：Figure
  - `2066`：Model
  - `2331`：Merch
  - `2273`：3C
  - `fudai_cate_id`：Fudai
- `--id`: Specify if want to continue searching. *(Read nextId from `nextId.txt`)*

> ⚠️ **Note:** As of **2025-02-20**, the server only accepts certain `--price` and `--discount` parameters above. Providing unsupported `--price` and `--discount` will result in empty data.

### Example

```sh
python3 main.py -w 初音未来 孤独摇滚 -p 5000-10000 10000-20000 20000-0 -d 50-70 70-100
```

or

```sh
sh main.sh -w fufu -p 10000-20000 -c 2331
```

This will generate 2 CSV files like `total_*.csv` and `want_*.csv`, while the data was automatically saved into the SQLite database (`bilidata.db`) after each successful page fetch. `nextId.txt` will also be generated and updated along.

It will stop after getting all items, or you can stop it manually by pressing `control+c`.

### In case of interruption

It happens sometimes when the script was stopped accidently or intentionally but you whatever want to continue searching. During this kind of situation you can simply run:

```sh
python3 main.py <previous_parameters> --id
```

or

```sh
sh main.sh <previous_parameters> --id
```

For example:

```sh
python3 main.py -w 初音未来 孤独摇滚 -p 5000-10000 10000-20000 20000-0 -d 50-70 70-100 --id
```

It will continue searching from where you stopped, perfectly avoid repeated search.


## About Data

### CSV Files

The generated CSV files will have 6 columns, **without** a header row:

| Column Name | Description | Example |
|-|-|-|
| **Timestamp** | Timestamp of data collection. | `2025-02-01 16:04:41.964444` |
| **Product Name** | Name of the product. | `S-FIRE 初音未来 秋日之约Ver. 正比手办` |
| **Product ID** | Unique product identifier. | `142389472138` |
| **Current Price** | Selling price of the product in cents. | `34344` |
| **Original Price** | Original price of the product in cents. | `50500` |
| **Discount Rate** | Discount rate of the product. | `0.6800792079207921` |

- After scraping, you can sort the CSV files by item name and discount rate by running:

   ```bash
   sh sort_total.sh
   ```

   This will generate 2 sorted files like `sort_total_*.csv` and `sort_want_*.csv`.

### Database
The database will have a similar structure:

| Column Name | Type | Description |
|-|-|-|
| `id` | TEXT | Unique product identifier (Primary Key). |
| `name` | TEXT | Name of the product. |
| `price` | INTEGER | Selling price of the product in cents. |
| `market_price` | INTEGER | Original price of the product in cents. |
| `rate` | REAL | Discount rate of the product. |
| `time` | TEXT | Timestamp of data collection. |

It can be queried using tools like [`DB Browser for SQLite`](https://sqlitebrowser.org/), [`sqlite-web`](https://github.com/coleifer/sqlite-web) or via Python.
- In case of main script error, run

   ```sh
   python3 db.py
   ```

   to manually save data from CSV files into the database.


## How can I use the data

You may access a specfic item by its product id, just use the following URL but ***replace `<REPLACE_THIS_WITH_PRODUCT_ID>` with specific product id*** in your browser:
```
https://mall.bilibili.com/neul-next/index.html?page=magic-market_detail&noTitleBar=1&itemsId=<REPLACE_THIS_WITH_PRODUCT_ID>&from=market_index
```
For example the URL should be like:

```
https://mall.bilibili.com/neul-next/index.html?page=magic-market_detail&noTitleBar=1&itemsId=142389472138&from=market_index
```


## User Interface (Beta)

The scraper comes with a simple user interface implemented using [`Streamlit`](https://streamlit.io/). Follow instructions below to use.

### 1. Install dependencies

```sh
pip3 install streamlit streamlit-tags
```

### 2. Run

```sh
streamlit run ui.py
```


## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Acknowledgments

Special thanks to ChatGPT for assistance with coding and documentation.

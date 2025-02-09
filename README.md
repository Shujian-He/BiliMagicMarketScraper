
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
      - Login to Bilibili main site, then open Bilibili market at https://mall.bilibili.com/neul-next/index.html?page=magic-market_index.
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

This will generate 2 files like `total_*.csv` and `want_*.csv`.

## Sorting Data

After scraping, you can sort the CSV files by item name and discount rate:

```bash
sh sort_total.sh
```

This will generate 2 sorted files like `sort_total_*.csv` and `sort_want_*.csv`.

## Database

The data is automatically saved into an SQLite database (`bilidata.db`) after each successful page fetch, which can be queried using tools like `DB Browser for SQLite` or via Python.

- In case of main script error, run

   ```
   python3 db.py
   ```

   to manually save data in CSV files into the database.

## License

This project is licensed under the MIT License. See the [LICENSE](./LICENSE) file for details.

## Acknowledgments

Special thanks to ChatGPT for assistance with coding and documentation.

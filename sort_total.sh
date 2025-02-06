#!/bin/sh

# sort_total.sh
# Bili Market Scraper
# -------------------
# Author: Shujian
# Description: A scraper getting your favorite items in Bilibili magic market.
# License: MIT License

for file in total*.csv want*.csv; do
    base_name=$(basename "$file" .csv)  # strip .csv
    echo "$base_name"
    sort -t',' -k2,2 -k6,6 "$file" > "sort_${base_name}.csv"
done

#!/bin/sh

# main.sh
# Bili Market Scraper
# -------------------
# Author: Shujian
# Description: A scraper getting your favorite items in Bilibili magic market.
# License: MIT License

# Special thanks to ChatGPT!

# Initialize variables
item_names=""
price_range=""
discount_range=""
category=""
id=""

# Parse command-line arguments
while [ $# -gt 0 ]; do
    case "$1" in
        -w | --want) 
            shift
            while [ $# -gt 0 ] && [ "${1#-}" = "$1" ]; do  # Stop at next flag
                item_names="${item_names} $1"
                shift
            done
            ;;
        -p | --price) 
            shift
            price_range="$1"
            shift
            ;;
        -d | --discount) 
            shift
            discount_range="$1"
            shift
            ;;
        -c | --category) 
            shift
            category="$1"
            shift
            ;;
        --id) 
            id="$1"
            shift
            ;;
        *)  # Handle unknown arguments
            shift
            ;;
    esac
done

# Trim leading whitespace from item_names (POSIX-compatible way)
item_names=$(echo "$item_names" | sed 's/^ *//')

# Set default values if not provided
if [ -z "$item_names" ]; then
    item_names="初音未来"
fi

if [ -z "$price_range" ]; then
    price_range="6000-10000"
fi

if [ -z "$discount_range" ]; then
    discount_range="0-100"
fi

if [ -z "$category" ]; then
    category="2312"
fi

# Execute the Python script
exec python3 main.py -w $item_names -p $price_range -d $discount_range -c $category $id
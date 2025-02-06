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

# Parse command-line arguments
while [ $# -gt 0 ]; do
    case "$1" in
        -w) 
            shift
            while [ $# -gt 0 ] && [ "${1#-}" = "$1" ]; do  # Stop at next flag
                item_names="${item_names} $1"
                shift
            done
            ;;
        -p) 
            shift
            price_range="$1"
            shift
            ;;
        -d) 
            shift
            discount_range="$1"
            shift
            ;;
        *)  # Handle unknown arguments
            shift
            ;;
    esac
done

# Trim leading whitespace from item_names (POSIX-compatible way)
item_names=$(echo "$item_names" | sed 's/^ *//')

# Execute the Python script
exec python3 main.py -w $item_names -p $price_range -d $discount_range
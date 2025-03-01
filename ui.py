"""
ui.py
Bili Market Scraper
-------------------
Author: Shujian
Description: A scraper getting your favorite items in Bilibili magic market.
License: MIT License
"""

import streamlit as st # pip3 install streamlit
from streamlit_tags import st_tags # pip3 install streamlit-tags
from datetime import datetime
from main import run_once
from db import initialize_database

# initialize database connection
conn = initialize_database()

st.set_page_config(layout="wide")

if 'next_id' not in st.session_state:
    st.session_state.next_id = None

st.title("Bilibili Magic Market Scraper")

# Input wanted items
want_list = st_tags(
    label='Enter item names:',
    text='Press enter to add more',
    value=['初音未来'],
    suggestions=[],
    maxtags = 10000,
    key='want'
)

# Select price range using a select_slider
price_filter = st.multiselect(
    "Select price range (cents)",
    ["0-2000", "2000-3000", "3000-5000", "5000-10000", "10000-20000", "20000-0"],
    ["10000-20000", "20000-0"],
    key="price",
)

# Select discount range using a select_slider
discount_filter = st.multiselect(
    "Select discount range",
    ["0-30", "30-50", "50-70", "70-100"],
    ["0-30", "30-50", "50-70", "70-100"],
    key="discount",
)

# Select category
category_mapping = {
    "Figure": "2312",
    "Model": "2066",
    "Merch": "2331",
    "3C": "2273",
    "Fudai": "fudai_cate_id"
}
selected_category = st.radio(
    "Select Category",
    key="category",
    options=["Figure", "Model", "Merch", "3C", "Fudai"],
    horizontal=True
)
category_filter = category_mapping[selected_category]

col1, col2 = st.columns(2)
with col1:
    if st.button("Run Scraper", key="run"):

        # st.write(f"Want List: {want_list}")
        # st.write(f"Price Filter: {price_filter}")
        # st.write(f"Discount Filter: {discount_filter}")
        # st.write(f"Category Filter: {category_filter}")

        startTime = datetime.now()
        st.write(f"Start time: {startTime}")

        fileTimeString = startTime.strftime("%Y-%m-%d-%H-%M-%S")
        print(st.session_state.next_id)
        if not st.session_state.next_id:
            st.write("Start a new search.")
            try:
                nextId = run_once(conn, want_list, price_filter, discount_filter, category_filter, fileTimeString, None)
            except Exception as e:
                st.error(f"Error: {e}")
        else:
            st.write(f"Continue search from ID: {st.session_state.next_id}")
            try:
                nextId = run_once(conn, want_list, price_filter, discount_filter, category_filter, fileTimeString, st.session_state.next_id)
            except Exception as e:
                st.error(f"Error: {e}")

        st.session_state.next_id = nextId
        time_placeholder = st.empty()
        nextid_placeholder = st.empty()
        time_placeholder.write(f"Current time: {datetime.now()}")
        nextid_placeholder.write(f"Next ID: {nextId}")

        while nextId:
            try:
                nextId = run_once(conn, want_list, price_filter, discount_filter, category_filter, fileTimeString, nextId)
                st.session_state.next_id = nextId
                time_placeholder.write(f"Current time: {datetime.now()}")
                nextid_placeholder.write(f"Next ID: {nextId}")
            except Exception as e:
                st.error(f"Error: {e}")
        st.success("Finished.")

with col2:
    if st.button("Stop Scraping", key="stop"):
        st.success("Stopped.")
    if st.button("Clear Cache", key="clear"):
        st.session_state.next_id = None
        st.success("Cache cleared.")

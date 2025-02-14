import streamlit as st # pip3 install streamlit
from streamlit_tags import st_tags # pip3 install streamlit-tags
from datetime import datetime
import main

st.set_page_config(layout="wide")

if 'stop_flag' not in st.session_state:
    st.session_state.stop_flag = False

if 'next_id' not in st.session_state:
    st.session_state.next_id = None

st.title("Bilibili Market Scraper")

want_list = st_tags(
    label='Enter item names:',
    text='Press enter to add more',
    value=['初音未来'],
    suggestions=[],
    maxtags = 10000,
    key='1')
# st.write(want_list)

# Select price range using a select_slider
price_filter = st.select_slider(
    "Select Price Range (RMB Yuan)", 
    options=[i for i in range(0, 501, 5)] + ["Infinity"],  # Creates a range
    value=(60, 100)
)
if price_filter[1] == "Infinity":
    price_filter = (price_filter[0], 0) # 0 represents infinity
else:
    price_filter = (price_filter[0] * 100, price_filter[1] * 100)
# st.write(price_filter)

# Select discount range using a select_slider
discount_filter = st.select_slider(
    "Select Discount Range (%)", 
    options=[i for i in range(0, 101, 1)],  # Creates a range from 0% to 100% with step 5
    value=(0, 100)
)
# st.write(discount_filter)

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
# st.write(category_filter)


col1, col2 = st.columns(2)

with col1:
    if st.button("Run Scraper"):
        st.session_state.stop_flag = False  # Reset stop flag before starting
        startTime = datetime.now()
        st.write(f"Start time: {startTime}")

        fileTimeString = startTime.strftime("%Y-%m-%d-%H-%M-%S")

        if not st.session_state.next_id:
            st.write("Start a new search.")
            nextId = main.run_once(fileTimeString, None)
        else:
            st.write(f"Continue the previous search from ID: {st.session_state.next_id}")
            nextId = main.run_once(fileTimeString, st.session_state.next_id)

        st.session_state.next_id = nextId
        st.write(f"Next ID: {nextId}")

        while nextId and not st.session_state.stop_flag:
            nextId = main.run_once(fileTimeString, nextId)
            st.session_state.next_id = nextId
            st.write(f"Next ID: {nextId}")

with col2:
    if st.button("Stop Scraping"):
        st.session_state.stop_flag = True
        st.success("Stopped.")

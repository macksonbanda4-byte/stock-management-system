import pandas as pd
import os

STOCK_FILE = "stock_export.csv"   # or stock_clean.csv depending on what you use
SALES_FILE = "sales.csv"

def load_stock():
    if not os.path.exists(STOCK_FILE):
        # empty frame with expected columns
        cols = [
            "Category", "Item", "Item Code", "Brand",
            "Available Stock", "Reorder Level",
            "Price", "Total Value", "Stock Status",
            "Location", "Supplier"
        ]
        return pd.DataFrame(columns=cols)

    df = pd.read_csv(STOCK_FILE)

    # --- normalize column names from both CSV versions ---
    rename_map = {
        "CATEGORY": "Category",
        "Item": "Item",
        "ITEM CODE": "Item Code",
        "Item Code": "Item Code",
        "BRAND": "Brand",
        "AVAILABLE STOCK": "Available Stock",
        "Available Stock": "Available Stock",
        "REORDER LEVEL": "Reorder Level",
        "Reorder Level": "Reorder Level",
        "Unit Price": "Price",
        "Price": "Price",
        "Total Value": "Total Value",
        "STOCK STATUS": "Stock Status",
        "Stock Status": "Stock Status",
    }
    df.rename(columns=rename_map, inplace=True)

    # --- ensure required columns exist ---
    required_cols = [
        "Category", "Item", "Item Code", "Brand",
        "Available Stock", "Reorder Level",
        "Price", "Total Value", "Stock Status",
        "Location", "Supplier"
    ]
    for col in required_cols:
        if col not in df.columns:
            if col in ["Available Stock", "Reorder Level", "Price", "Total Value"]:
                df[col] = 0
            else:
                df[col] = ""

    # default Location if empty
    df["Location"] = df["Location"].replace("", "Shop")

    # recompute total value if needed
    df["Total Value"] = df["Available Stock"].astype(float) * df["Price"].astype(float)

    return df


def save_stock(df: pd.DataFrame):
    df.to_csv(STOCK_FILE, index=False)
import streamlit as st

LOCATIONS = ["Blue container", "Red container", "Shop"]

def pick_item_with_search(df, title="Select Item", allow_location_filter=True):
    st.subheader(title)

    search = st.text_input("Search by Item Code, Name, or Brand")
    filtered = df.copy()

    if search:
        filtered = filtered[
            filtered["Item Code"].astype(str).str.contains(search, case=False, na=False)
            | filtered["Item"].astype(str).str.contains(search, case=False, na=False)
            | filtered["Brand"].astype(str).str.contains(search, case=False, na=False)
        ]

    if allow_location_filter:
        loc_choice = st.selectbox("Filter by Location", ["All"] + LOCATIONS)
        if loc_choice != "All":
            filtered = filtered[filtered["Location"] == loc_choice]

    if filtered.empty:
        st.warning("No matching items found.")
        return None, None

    display_series = filtered["Item"] + " | " + filtered["Item Code"].astype(str)
    choice = st.selectbox("Item list", display_series)

    idx = display_series[display_series == choice].index[0]
    row = filtered.loc[idx]

    st.info(
        f"""
**Item:** {row['Item']}
**Brand:** {row.get('Brand','N/A')}
**Location:** {row.get('Location','N/A')}
**Available Stock:** {row['Available Stock']}
**Reorder Level:** {row['Reorder Level']}
**Price:** {row['Price']}
"""
    )

    return idx, row
def issue_stock_page(df, sales_df):
    st.header("Issue Stock")

    idx, row = pick_item_with_search(df, title="Search & Select Item to Issue")
    if row is None:
        return

    qty = st.number_input("Quantity to issue", min_value=1, step=1)

    if st.button("Issue"):
        if qty > int(row["Available Stock"]):
            st.error("Not enough stock available.")
            return

        df.at[idx, "Available Stock"] = int(row["Available Stock"]) - qty
        df.at[idx, "Total Value"] = df.at[idx, "Available Stock"] * float(row["Price"])

        # TODO: append to sales_df and save if you already do that
        save_stock(df)
        st.success("Stock issued successfully.")
def receive_stock_page(df):
    st.header("Receive Stock")

    idx, row = pick_item_with_search(df, title="Search & Select Item to Receive")
    if row is None:
        return

    qty = st.number_input("Quantity to receive", min_value=1, step=1)

    if st.button("Receive"):
        df.at[idx, "Available Stock"] = int(row["Available Stock"]) + qty
        df.at[idx, "Total Value"] = df.at[idx, "Available Stock"] * float(row["Price"])
        save_stock(df)
        st.success("Stock received successfully.")
location = st.selectbox("Location", LOCATIONS, index=2)  # default "Shop"
supplier = st.text_input("Supplier")

# when building the new row dict:
new_row = {
    "Category": category,
    "Item": item,
    "Item Code": item_code,
    "Brand": brand,
    "Available Stock": qty,
    "Reorder Level": reorder_level,
    "Price": price,
    "Total Value": qty * price,
    "Stock Status": "Okay",  # or your logic
    "Location": location,
    "Supplier": supplier,
}location = st.selectbox(
    "Location",
    LOCATIONS,
    index=LOCATIONS.index(row.get("Location", "Shop")) if row.get("Location", "Shop") in LOCATIONS else 2
)
supplier = st.text_input("Supplier", value=row.get("Supplier", ""))
st.dataframe(df[["Location","Supplier","Item","Available Stock","Total Value","Stock Status"]])


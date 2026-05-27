import streamlit as st
import pandas as pd
import os
from datetime import datetime

# ============================================================
# CONFIG
# ============================================================
STOCK_FILE = "stock_export.csv"
SALES_FILE = "sales.csv"

LOCATIONS = ["Blue container", "Red container", "Shop"]


# ============================================================
# LOAD & SAVE FUNCTIONS
# ============================================================
def load_stock():
    """Load stock_export.csv and normalize columns."""
    if not os.path.exists(STOCK_FILE):
        cols = [
            "Category", "Item", "Item Code", "Brand",
            "Available Stock", "Reorder Level",
            "Price", "Total Value", "Stock Status",
            "Location", "Supplier"
        ]
        return pd.DataFrame(columns=cols)

    df = pd.read_csv(STOCK_FILE)

    # Normalize column names
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

    # Ensure required columns exist
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

    # Default location = Shop
    df["Location"] = df["Location"].replace("", "Shop")

    # Recompute total value
    df["Total Value"] = df["Available Stock"].astype(float) * df["Price"].astype(float)

    return df


def save_stock(df):
    df.to_csv(STOCK_FILE, index=False)


def load_sales():
    if not os.path.exists(SALES_FILE):
        cols = ["Date", "Item Code", "Item", "Quantity Sold", "Price", "Total", "Customer"]
        return pd.DataFrame(columns=cols)
    return pd.read_csv(SALES_FILE)


def save_sales(df):
    df.to_csv(SALES_FILE, index=False)


# ============================================================
# SEARCH + ITEM PICKER
# ============================================================
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

# ============================================================
# ADD ITEM PAGE
# ============================================================
def add_item_page(df):
    st.header("Add New Item")

    category = st.text_input("Category")
    item = st.text_input("Item Name")
    item_code = st.text_input("Item Code")
    brand = st.text_input("Brand")
    supplier = st.text_input("Supplier")
    location = st.selectbox("Location", LOCATIONS, index=2)

    qty = st.number_input("Initial Stock", min_value=0, step=1)
    reorder = st.number_input("Reorder Level", min_value=0, step=1)
    price = st.number_input("Unit Price", min_value=0.0, step=0.1)

    if st.button("Add Item"):
        new_row = {
            "Category": category,
            "Item": item,
            "Item Code": item_code,
            "Brand": brand,
            "Available Stock": qty,
            "Reorder Level": reorder,
            "Price": price,
            "Total Value": qty * price,
            "Stock Status": "OK",
            "Location": location,
            "Supplier": supplier,
        }
        df.loc[len(df)] = new_row
        save_stock(df)
        st.success("Item added successfully.")


# ============================================================
# EDIT ITEM PAGE
# ============================================================
def edit_item_page(df):
    st.header("Edit Item")

    idx, row = pick_item_with_search(df, "Search Item to Edit")
    if row is None:
        return

    category = st.text_input("Category", value=row["Category"])
    item = st.text_input("Item Name", value=row["Item"])
    item_code = st.text_input("Item Code", value=row["Item Code"])
    brand = st.text_input("Brand", value=row["Brand"])
    supplier = st.text_input("Supplier", value=row["Supplier"])

    location = st.selectbox(
        "Location",
        LOCATIONS,
        index=LOCATIONS.index(row["Location"]) if row["Location"] in LOCATIONS else 2
    )

    qty = st.number_input("Available Stock", min_value=0, step=1, value=int(row["Available Stock"]))
    reorder = st.number_input("Reorder Level", min_value=0, step=1, value=int(row["Reorder Level"]))
    price = st.number_input("Unit Price", min_value=0.0, step=0.1, value=float(row["Price"]))

    if st.button("Save Changes"):
        df.at[idx, "Category"] = category
        df.at[idx, "Item"] = item
        df.at[idx, "Item Code"] = item_code
        df.at[idx, "Brand"] = brand
        df.at[idx, "Supplier"] = supplier
        df.at[idx, "Location"] = location
        df.at[idx, "Available Stock"] = qty
        df.at[idx, "Reorder Level"] = reorder
        df.at[idx, "Price"] = price
        df.at[idx, "Total Value"] = qty * price

        save_stock(df)
        st.success("Item updated successfully.")


# ============================================================
# DELETE ITEM PAGE
# ============================================================
def delete_item_page(df):
    st.header("Delete Item")

    idx, row = pick_item_with_search(df, "Search Item to Delete")
    if row is None:
        return

    if st.button("Delete Item"):
        df.drop(idx, inplace=True)
        df.reset_index(drop=True, inplace=True)
        save_stock(df)
        st.success("Item deleted successfully.")


# ============================================================
# RECEIVE STOCK PAGE
# ============================================================
def receive_stock_page(df):
    st.header("Receive Stock")

    idx, row = pick_item_with_search(df, "Search Item to Receive")
    if row is None:
        return

    qty = st.number_input("Quantity Received", min_value=1, step=1)

    if st.button("Receive"):
        df.at[idx, "Available Stock"] = int(row["Available Stock"]) + qty
        df.at[idx, "Total Value"] = df.at[idx, "Available Stock"] * float(row["Price"])
        save_stock(df)
        st.success("Stock received successfully.")


# ============================================================
# ISSUE STOCK PAGE
# ============================================================
def issue_stock_page(df, sales_df):
    st.header("Issue Stock")

    idx, row = pick_item_with_search(df, "Search Item to Issue")
    if row is None:
        return

    qty = st.number_input("Quantity to Issue", min_value=1, step=1)
    customer = st.text_input("Customer Name (optional)")

    if st.button("Issue"):
        if qty > int(row["Available Stock"]):
            st.error("Not enough stock available.")
            return

        df.at[idx, "Available Stock"] = int(row["Available Stock"]) - qty
        df.at[idx, "Total Value"] = df.at[idx, "Available Stock"] * float(row["Price"])

        sale = {
            "Date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Item Code": row["Item Code"],
            "Item": row["Item"],
            "Quantity Sold": qty,
            "Price": row["Price"],
            "Total": qty * float(row["Price"]),
            "Customer": customer,
        }
        sales_df.loc[len(sales_df)] = sale

        save_stock(df)
        save_sales(sales_df)

        st.success("Stock issued successfully.")


# ============================================================
# REPORTS PAGE
# ============================================================
def reports_page(df, sales_df):
    st.header("Reports")

    st.subheader("Stock Summary")
    cols = ["Location", "Supplier", "Item", "Available Stock", "Total Value", "Stock Status"]
    cols = [c for c in cols if c in df.columns]
    st.dataframe(df[cols])

    st.subheader("Sales Summary")
    st.dataframe(sales_df)


# ============================================================
# DASHBOARD
# ============================================================
def dashboard_page(df):
    st.header("Dashboard")

    total_items = len(df)
    total_stock = df["Available Stock"].sum()
    total_value = df["Total Value"].sum()

    st.metric("Total Items", total_items)
    st.metric("Total Stock Units", total_stock)
    st.metric("Total Stock Value", f"K{total_value:,.2f}")

    low_stock = df[df["Available Stock"] <= df["Reorder Level"]]
    st.subheader("Low Stock Items")
    st.dataframe(low_stock)


# ============================================================
# MAIN APP
# ============================================================
def main():
    st.title("Stock Management System")

    df = load_stock()
    sales_df = load_sales()

    menu = [
        "Dashboard", "Add Item", "Edit Item", "Delete Item",
        "Receive Stock", "Issue Stock", "Reports"
    ]
    choice = st.sidebar.selectbox("Menu", menu)

    if choice == "Dashboard":
        dashboard_page(df)
    elif choice == "Add Item":
        add_item_page(df)
    elif choice == "Edit Item":
        edit_item_page(df)
    elif choice == "Delete Item":
        delete_item_page(df)
    elif choice == "Receive Stock":
        receive_stock_page(df)
    elif choice == "Issue Stock":
        issue_stock_page(df, sales_df)
    elif choice == "Reports":
        reports_page(df, sales_df)


if __name__ == "__main__":
    main()

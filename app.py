import streamlit as st
import pandas as pd
from datetime import datetime

# -----------------------------
# Load & Save CSV
# -----------------------------
def load_data():
    try:
        return pd.read_csv("stock_clean.csv")
    except:
        return pd.DataFrame(columns=[
            "Category", "Item", "Item Code", "Brand",
            "Available Stock", "Reorder Level", "Price",
            "Total Value", "Stock Status"
        ])

def save_data(df):
    df.to_csv("stock_clean.csv", index=False)

def load_sales():
    try:
        return pd.read_csv("sales.csv")
    except:
        return pd.DataFrame(columns=[
            "Item", "Item Code", "Quantity Sold",
            "Price", "Total Sale", "Date"
        ])

def save_sales(df):
    df.to_csv("sales.csv", index=False)

df = load_data()
sales_df = load_sales()

# -----------------------------
# Helpers
# -----------------------------
def compute_status(available, reorder):
    if available == 0:
        return "Out of Stock"
    elif available <= reorder:
        return "Low Stock"
    else:
        return "In Stock"

# -----------------------------
# Streamlit Page Setup
# -----------------------------
st.set_page_config(page_title="Automated Stock Management System", layout="wide")
st.title("📦 Automated Stock Management System")

menu = [
    "Dashboard",
    "Search Items",
    "Add New Item",
    "Receive Stock (by Code)",
    "Issue Stock (by Code)",
    "Sales Tracking",
    "Current Stock"
]

choice = st.sidebar.selectbox("Menu", menu)

# -----------------------------
# Dashboard
# -----------------------------
if choice == "Dashboard":
    st.header("📊 System Overview")

    if df.empty:
        st.warning("No stock data available.")
    else:
        total_items = len(df)
        total_value = df["Total Value"].sum()
        low_stock = len(df[df["Stock Status"] == "Low Stock"])
        out_stock = len(df[df["Stock Status"] == "Out of Stock"])

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Items", total_items)
        col2.metric("Total Stock Value (ZMW)", f"{total_value:,.2f}")
        col3.metric("Low Stock Items", low_stock)
        col4.metric("Out of Stock", out_stock)

        if out_stock > 0:
            st.error(f"⚠ {out_stock} items are OUT OF STOCK!")

        if low_stock > 0:
            st.warning(f"⚠ {low_stock} items are LOW on stock!")

# -----------------------------
# Search Items
# -----------------------------
elif choice == "Search Items":
    st.header("🔍 Search Inventory")
    term = st.text_input("Search by item name, code, or brand")

    if term:
        filtered = df[df.apply(
            lambda row: term.lower() in row.astype(str).str.lower().to_string(),
            axis=1
        )]
        st.dataframe(filtered)

# -----------------------------
# Add New Item
# -----------------------------
elif choice == "Add New Item":
    st.header("➕ Add New Stock Item")

    col1, col2 = st.columns(2)

    with col1:
        category = st.text_input("Category")
        item = st.text_input("Item Name")
        item_code = st.text_input("Item Code (scan or type)")
        brand = st.text_input("Brand")

    with col2:
        available = st.number_input("Available Stock", min_value=0)
        reorder = st.number_input("Reorder Level", min_value=0)
        price = st.number_input("Price (ZMW)", min_value=0.0, format="%.2f")

    if st.button("Add Item"):
        if not category or not item or not item_code or not brand:
            st.error("All text fields are required.")
        elif item_code in df["Item Code"].astype(str).values:
            st.error("An item with this Item Code already exists.")
        else:
            total_value = available * price
            status = compute_status(available, reorder)

            new_row = {
                "Category": category,
                "Item": item,
                "Item Code": item_code,
                "Brand": brand,
                "Available Stock": available,
                "Reorder Level": reorder,
                "Price": price,
                "Total Value": total_value,
                "Stock Status": status
            }

            df.loc[len(df)] = new_row
            save_data(df)
            st.success(f"{item} added successfully!")

# -----------------------------
# Receive Stock (by Code)
# -----------------------------
elif choice == "Receive Stock (by Code)":
    st.header("📥 Receive Stock (Scan/Enter Item Code)")

    if df.empty:
        st.warning("No items available.")
    else:
        code = st.text_input("Item Code (scan or type)")
        item_row = None

        if code:
            matches = df[df["Item Code"].astype(str) == str(code)]
            if matches.empty:
                st.error("No item found with that Item Code.")
            else:
                item_row = matches.iloc[0]
                st.success(f"Found: {item_row['Item']} ({item_row['Brand']})")
                st.write(f"**Category:** {item_row['Category']}")
                st.write(f"**Current Stock:** {item_row['Available Stock']}")
                st.write(f"**Price:** ZMW {item_row['Price']}")

        qty = st.number_input("Quantity Received", min_value=1)

        if st.button("Update Stock"):
            if item_row is None:
                st.error("Enter a valid Item Code first.")
            else:
                idx = df.index[df["Item Code"].astype(str) == str(code)][0]
                df.at[idx, "Available Stock"] += qty
                df.at[idx, "Total Value"] = df.at[idx, "Available Stock"] * df.at[idx, "Price"]
                df.at[idx, "Stock Status"] = compute_status(
                    df.at[idx, "Available Stock"],
                    df.at[idx, "Reorder Level"]
                )
                save_data(df)
                st.success("Stock updated!")

# -----------------------------
# Issue Stock (by Code) + SALES TRACKING
# -----------------------------
elif choice == "Issue Stock (by Code)":
    st.header("📤 Issue Stock (Scan/Enter Item Code)")

    if df.empty:
        st.warning("No items available.")
    else:
        code = st.text_input("Item Code (scan or type)")
        item_row = None

        if code:
            matches = df[df["Item Code"].astype(str) == str(code)]
            if matches.empty:
                st.error("No item found with that Item Code.")
            else:
                item_row = matches.iloc[0]
                st.success(f"Found: {item_row['Item']} ({item_row['Brand']})")
                st.write(f"**Available Stock:** {item_row['Available Stock']}")
                st.write(f"**Price:** ZMW {item_row['Price']}")

        qty = st.number_input("Quantity to Issue", min_value=1)

        if st.button("Issue"):
            if item_row is None:
                st.error("Enter a valid Item Code first.")
            elif qty > item_row["Available Stock"]:
                st.error("Not enough stock!")
            else:
                idx = df.index[df["Item Code"].astype(str) == str(code)][0]

                # Update stock
                df.at[idx, "Available Stock"] -= qty
                df.at[idx, "Total Value"] = df.at[idx, "Available Stock"] * df.at[idx, "Price"]
                df.at[idx, "Stock Status"] = compute_status(
                    df.at[idx, "Available Stock"],
                    df.at[idx, "Reorder Level"]
                )
                save_data(df)

                # Record sale
                sale = {
                    "Item": item_row["Item"],
                    "Item Code": item_row["Item Code"],
                    "Quantity Sold": qty,
                    "Price": item_row["Price"],
                    "Total Sale": qty * item_row["Price"],
                    "Date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }

                sales_df.loc[len(sales_df)] = sale
                save_sales(sales_df)

                st.success("Stock issued and sale recorded!")

# -----------------------------
# Sales Tracking + BEST SELLERS
# -----------------------------
elif choice == "Sales Tracking":
    st.header("💰 Sales Tracking")

    if sales_df.empty:
        st.info("No sales recorded yet.")
    else:
        st.subheader("📄 All Sales Records")
        st.dataframe(sales_df, use_container_width=True)

        st.subheader("🏆 Best‑Selling Items")

        best = sales_df.groupby(["Item", "Item Code"]).agg({
            "Quantity Sold": "sum",
            "Total Sale": "sum"
        }).sort_values("Quantity Sold", ascending=False)

        st.dataframe(best, use_container_width=True)

# -----------------------------
# Current Stock
# -----------------------------
elif choice == "Current Stock":
    st.header("📦 Current Stock List")

    if df.empty:
        st.warning("No stock data available.")
    else:
        styled = df.style.apply(
            lambda row: [
                "background-color: #ffcccc" if row["Stock Status"] == "Out of Stock"
                else "background-color: #fff3cd" if row["Stock Status"] == "Low Stock"
                else ""
                for _ in row
            ],
            axis=1
        )
        st.dataframe(styled, use_container_width=True)

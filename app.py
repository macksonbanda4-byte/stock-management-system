import streamlit as st
import pandas as pd

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

df = load_data()

# -----------------------------
# Streamlit Page Setup
# -----------------------------
st.set_page_config(page_title="Automated Stock Management System", layout="wide")
st.title("📦 Automated Stock Management System")

menu = [
    "Dashboard",
    "Search Items",
    "Add New Item",
    "Receive Stock",
    "Issue Stock",
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
        item_code = st.text_input("Item Code")
        brand = st.text_input("Brand")

    with col2:
        available = st.number_input("Available Stock", min_value=0)
        reorder = st.number_input("Reorder Level", min_value=0)
        price = st.number_input("Price (ZMW)", min_value=0.0, format="%.2f")

    if st.button("Add Item"):
        if not category or not item or not item_code or not brand:
            st.error("All text fields are required.")
        else:
            total_value = available * price

            if available == 0:
                status = "Out of Stock"
            elif available <= reorder:
                status = "Low Stock"
            else:
                status = "In Stock"

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
# Receive Stock
# -----------------------------
elif choice == "Receive Stock":
    st.header("📥 Receive Stock")

    if df.empty:
        st.warning("No items available.")
    else:
        item_name = st.selectbox("Select Item", df["Item"].unique())
        item_row = df[df["Item"] == item_name].iloc[0]

        st.write(f"**Category:** {item_row['Category']}")
        st.write(f"**Brand:** {item_row['Brand']}")
        st.write(f"**Price:** ZMW {item_row['Price']}")

        qty = st.number_input("Quantity Received", min_value=1)

        if st.button("Update Stock"):
            df.loc[df["Item"] == item_name, "Available Stock"] += qty
            df.loc[df["Item"] == item_name, "Total Value"] = (
                df.loc[df["Item"] == item_name, "Available Stock"] *
                df.loc[df["Item"] == item_name, "Price"]
            )

            new_stock = df.loc[df["Item"] == item_name, "Available Stock"].values[0]
            reorder = df.loc[df["Item"] == item_name, "Reorder Level"].values[0]

            if new_stock == 0:
                status = "Out of Stock"
            elif new_stock <= reorder:
                status = "Low Stock"
            else:
                status = "In Stock"

            df.loc[df["Item"] == item_name, "Stock Status"] = status
            save_data(df)
            st.success("Stock updated!")

# -----------------------------
# Issue Stock
# -----------------------------
elif choice == "Issue Stock":
    st.header("📤 Issue Stock")

    if df.empty:
        st.warning("No items available.")
    else:
        item_name = st.selectbox("Select Item", df["Item"].unique())
        item_row = df[df["Item"] == item_name].iloc[0]

        st.write(f"**Available Stock:** {item_row['Available Stock']}")

        qty = st.number_input("Quantity to Issue", min_value=1)

        if st.button("Issue"):
            if qty > item_row["Available Stock"]:
                st.error("Not enough stock!")
            else:
                df.loc[df["Item"] == item_name, "Available Stock"] -= qty
                df.loc[df["Item"] == item_name, "Total Value"] = (
                    df.loc[df["Item"] == item_name, "Available Stock"] *
                    df.loc[df["Item"] == item_name, "Price"]
                )

                new_stock = df.loc[df["Item"] == item_name, "Available Stock"].values[0]
                reorder = df.loc[df["Item"] == item_name, "Reorder Level"].values[0]

                if new_stock == 0:
                    status = "Out of Stock"
                elif new_stock <= reorder:
                    status = "Low Stock"
                else:
                    status = "In Stock"

                df.loc[df["Item"] == item_name, "Stock Status"] = status
                save_data(df)
                st.success("Stock issued!")

# -----------------------------
# Current Stock
# -----------------------------
elif choice == "Current Stock":
    st.header("📦 Current Stock List")
    st.dataframe(df)

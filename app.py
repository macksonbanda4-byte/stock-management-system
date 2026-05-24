import streamlit as st
import pandas as pd

# Load CSV
def load_data():
    return pd.read_csv("stock_clean.csv")

def save_data(df):
    df.to_csv("stock_clean.csv", index=False)

df = load_data()

# ---------------------- UI SETUP ----------------------
st.set_page_config(page_title="Automated Stock Management System", layout="wide")
st.title("Automated Stock Management System")

menu = ["Dashboard", "Search Items", "Receive Stock", "Issue Stock", "Current Stock"]
choice = st.sidebar.selectbox("Menu", menu)

# ---------------------- DASHBOARD ----------------------
if choice == "Dashboard":
    st.subheader("📊 System Overview")

    total_items = len(df)
    total_stock_units = df["Available Stock"].sum()
    total_inventory_value = df["Total Value"].sum()
    low_stock_count = (df["Stock Status"] == "Low Stock").sum()
    out_of_stock_count = (df["Stock Status"] == "Out of Stock").sum()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Items", total_items)
    col2.metric("Total Stock Units", total_stock_units)
    col3.metric("Low Stock Items", low_stock_count)
    col4.metric("Out of Stock", out_of_stock_count)

    st.write("### 📦 Full Inventory Overview")
    st.dataframe(df)

# ---------------------- SEARCH ITEMS ----------------------
elif choice == "Search Items":
    st.subheader("🔍 Search Inventory")

    query = st.text_input("Search by Item, Category, or Brand")

    if query:
        results = df[
            df["Item"].str.contains(query, case=False, na=False) |
            df["Category"].str.contains(query, case=False, na=False) |
            df["Brand"].str.contains(query, case=False, na=False)
        ]
        st.write(f"### Results for: **{query}**")
        st.dataframe(results)
    else:
        st.info("Type something to search…")

# ---------------------- RECEIVE STOCK ----------------------
elif choice == "Receive Stock":
    st.subheader("📥 Receive Stock")

    item = st.selectbox("Select Item", df["Item"].unique())
    selected = df[df["Item"] == item].iloc[0]

    st.write(f"**Category:** {selected['Category']}")
    st.write(f"**Brand:** {selected['Brand']}")
    st.write(f"**Price:** ZMW {selected['Price']}")

    qty = st.number_input("Enter Quantity Received", min_value=1)

    total_cost = qty * selected["Price"]
    st.write(f"**Total Cost:** ZMW {total_cost}")

    if st.button("Submit Stock"):
        df.loc[df["Item"] == item, "Available Stock"] += qty

        # Recalculate Total Value
        df.loc[df["Item"] == item, "Total Value"] = (
            df.loc[df["Item"] == item, "Available Stock"] * df.loc[df["Item"] == item, "Price"]
        )

        # Recalculate Stock Status
        stock = df.loc[df["Item"] == item, "Available Stock"].values[0]
        reorder = df.loc[df["Item"] == item, "Reorder Level"].values[0]

        if stock == 0:
            status = "Out of Stock"
        elif stock <= reorder:
            status = "Low Stock"
        else:
            status = "In Stock"

        df.loc[df["Item"] == item, "Stock Status"] = status

        save_data(df)
        st.success(f"Successfully received {qty} units of {item}.")

# ---------------------- ISSUE STOCK ----------------------
elif choice == "Issue Stock":
    st.subheader("📤 Issue Stock")

    item = st.selectbox("Select Item", df["Item"].unique())
    selected = df[df["Item"] == item].iloc[0]

    st.write(f"**Available Stock:** {selected['Available Stock']}")
    st.write(f"**Price:** ZMW {selected['Price']}")

    qty = st.number_input("Enter Quantity to Issue", min_value=1)

    if qty > selected["Available Stock"]:
        st.error("Not enough stock available.")
    else:
        total_value = qty * selected["Price"]
        st.write(f"**Total Value Issued:** ZMW {total_value}")

        if st.button("Issue Stock"):
            df.loc[df["Item"] == item, "Available Stock"] -= qty

            # Recalculate Total Value
            df.loc[df["Item"] == item, "Total Value"] = (
                df.loc[df["Item"] == item, "Available Stock"] * df.loc[df["Item"] == item, "Price"]
            )

            # Recalculate Stock Status
            stock = df.loc[df["Item"] == item, "Available Stock"].values[0]
            reorder = df.loc[df["Item"] == item, "Reorder Level"].values[0]

            if stock == 0:
                status = "Out of Stock"
            elif stock <= reorder:
                status = "Low Stock"
            else:
                status = "In Stock"

            df.loc[df["Item"] == item, "Stock Status"] = status

            save_data(df)
            st.success(f"Issued {qty} units of {item}.")

# ---------------------- CURRENT STOCK ----------------------
elif choice == "Current Stock":
    st.subheader("📦 Current Stock List")
    st.dataframe(df)

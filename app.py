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

menu = ["Dashboard", "Search Items", "Add New Item", "Receive Stock", "Issue Stock", "Current Stock"]
choice = st.sidebar.selectbox("Menu", menu)

# ---------------------- DASHBOARD ----------------------
if choice == "Dashboard":
    st.subheader("📊 System Overview")
    st.write("Dashboard coming soon...")

# ---------------------- SEARCH ITEMS ----------------------
elif choice == "Search Items":
    st.subheader("🔍 Search Inventory")
    search_term = st.text_input("Enter item name or code")

    if search_term:
        results = df[df.apply(lambda row: search_term.lower() in row.astype(str).str.lower().to_string(), axis=1)]
        st.dataframe(results)

# ---------------------- ADD NEW ITEM ----------------------
elif choice == "Add New Item":
    st.subheader("➕ Add New Stock Item")

    category = st.text_input("Category")
    item = st.text_input("Item Name")
    item_code = st.text_input("Item Code")
    brand = st.text_input("Brand")
    available_stock = st.number_input("Available Stock", min_value=0)
    reorder_level = st.number_input("Reorder Level", min_value=0)
    price = st.number_input("Price (ZMW)", min_value=0.0, format="%.2f")

    if st.button("Add Item"):
        if not category or not item or not item_code or not brand:
            st.error("Please fill in all text fields.")
        else:
            total_value = available_stock * price

            if available_stock == 0:
                status = "Out of Stock"
            elif available_stock <= reorder_level:
                status = "Low Stock"
            else:
                status = "In Stock"

            new_row = {
                "Category": category,
                "Item": item,
                "Item Code": item_code,
                "Brand": brand,
                "Available Stock": available_stock,
                "Reorder Level": reorder_level,
                "Price": price,
                "Total Value": total_value,
                "Stock Status": status
            }

            df.loc[len(df)] = new_row
            save_data(df)
            st.success(f"New item '{item}' added successfully!")

# ---------------------- RECEIVE STOCK ----------------------
elif choice == "Receive Stock":
    st.subheader("📥 Receive Stock")

    item_list = df["Item"].unique()
    selected_item = st.selectbox("Select Item", item_list)

    item_data = df[df["Item"] == selected_item].iloc[0]

    st.write(f"**Category:** {item_data['Category']}")
    st.write(f"**Brand:** {item_data['Brand']}")
    st.write(f"**Price:** ZMW {item_data['Price']}")

    qty = st.number_input("Enter quantity received", min_value=1)

    if st.button("Submit Stock"):
        df.loc[df["Item"] == selected_item, "Available Stock"] += qty
        df.loc[df["Item"] == selected_item, "Total Value"] = (
            df.loc[df["Item"] == selected_item, "Available Stock"] *
            df.loc[df["Item"] == selected_item, "Price"]
        )

        # Update status
        new_stock = df.loc[df["Item"] == selected_item, "Available Stock"].values[0]
        reorder = df.loc[df["Item"] == selected_item, "Reorder Level"].values[0]

        if new_stock == 0:
            status = "Out of Stock"
        elif new_stock <= reorder:
            status = "Low Stock"
        else:
            status = "In Stock"

        df.loc[df["Item"] == selected_item, "Stock Status"] = status

        save_data(df)
        st.success("Stock updated successfully!")

# ---------------------- ISSUE STOCK ----------------------
elif choice == "Issue Stock":
    st.subheader("📤 Issue Stock")

    item_list = df["Item"].unique()
    selected_item = st.selectbox("Select Item", item_list)

    item_data = df[df["Item"] == selected_item].iloc[0]

    st.write(f"**Available Stock:** {item_data['Available Stock']}")

    qty = st.number_input("Enter quantity to issue", min_value=1)

    if st.button("Issue Stock"):
        if qty > item_data["Available Stock"]:
            st.error("Not enough stock!")
        else:
            df.loc[df["Item"] == selected_item, "Available Stock"] -= qty
            df.loc[df["Item"] == selected_item, "Total Value"] = (
                df.loc[df["Item"] == selected_item, "Available Stock"] *
                df.loc[df["Item"] == selected_item, "Price"]
            )

            # Update status
            new_stock = df.loc[df["Item"] == selected_item, "Available Stock"].values[0]
            reorder = df.loc[df["Item"] == selected_item, "Reorder Level"].values[0]

            if new_stock == 0:
                status = "Out of Stock"
            elif new_stock <= reorder:
                status = "Low Stock"
            else:
                status = "In Stock"

            df.loc[df["Item"] == selected_item, "Stock Status"] = status

            save_data(df)
            st.success("Stock issued successfully!")

# ---------------------- CURRENT STOCK ----------------------
elif choice == "Current Stock":
    st.subheader("📦 Current Stock List")
    st.dataframe(df)

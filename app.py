import streamlit as st
import pandas as pd
from datetime import datetime

# -----------------------------
# Simple login config
# -----------------------------
USERS = {
    "admin": "admin123",
    "ackson": "password"
}

# -----------------------------
# Load & Save CSV
# -----------------------------
def load_data():
    try:
        return pd.read_csv("stock_clean.csv")
    except:
        return pd.DataFrame(columns=[
            "Category", "Item", "Item Code", "Brand",
            "Available Stock", "Reorder Level", "Cost Price",
            "Price", "Total Value", "Stock Status"
        ])

def save_data(df):
    df.to_csv("stock_clean.csv", index=False)

def load_sales():
    try:
        return pd.read_csv("sales.csv")
    except:
        return pd.DataFrame(columns=[
            "Item", "Item Code", "Quantity Sold",
            "Selling Price", "Cost Price",
            "Total Sale", "Total Cost", "Profit", "Date"
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

def card_container(title, value, color="#0078D4"):
    return f"""
    <div style="
        background-color: white;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.12);
        border-left: 6px solid {color};
        margin-bottom: 15px;
    ">
        <h4 style="margin: 0; color: #444;">{title}</h4>
        <h2 style="margin: 5px 0 0 0; color: #222;">{value}</h2>
    </div>
    """

def section_header(text):
    st.markdown(
        f"""
        <h2 style="
            color: #0078D4;
            padding-bottom: 5px;
            border-bottom: 2px solid #E5E5E5;
            margin-top: 20px;
        ">{text}</h2>
        """,
        unsafe_allow_html=True
    )

def login_form():
    st.markdown(
        """
        <h1 style="color:#0078D4; text-align:center;">🔐 Login</h1>
        """,
        unsafe_allow_html=True
    )

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    login_btn = st.button("Login")

    if login_btn:
        if username in USERS and USERS[username] == password:
            st.session_state["logged_in"] = True
            st.session_state["username"] = username
            st.success("Login successful!")
        else:
            st.error("Invalid username or password.")

# -----------------------------
# Streamlit Page Setup
# -----------------------------
st.set_page_config(page_title="Automated Stock Management System", layout="wide")

# Session state defaults
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
if "username" not in st.session_state:
    st.session_state["username"] = None

# If not logged in → show login screen only
if not st.session_state["logged_in"]:
    login_form()
    st.stop()

# -----------------------------
# Main app (only after login)
# -----------------------------
st.markdown(
    """
    <h1 style="color:#0078D4; font-weight:700;">📦 Automated Stock Management System</h1>
    """,
    unsafe_allow_html=True
)

# Sidebar with user info + logout
st.sidebar.markdown(
    f"""
    <div style="padding:10px; background:#F3F9FF; border-radius:8px; border-left:4px solid #0078D4;">
        <strong>👤 Logged in as:</strong><br>{st.session_state['username']}
    </div>
    """,
    unsafe_allow_html=True
)

if st.sidebar.button("Logout"):
    st.session_state["logged_in"] = False
    st.session_state["username"] = None
    st.experimental_rerun()

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
    section_header("📊 System Overview")

    if df.empty:
        st.warning("No stock data available.")
    else:
        total_items = len(df)
        total_value = df["Total Value"].sum()
        low_stock = len(df[df["Stock Status"] == "Low Stock"])
        out_stock = len(df[df["Stock Status"] == "Out of Stock"])

        col1, col2 = st.columns(2)
        col3, col4 = st.columns(2)

        col1.markdown(card_container("Total Items", total_items))
        col2.markdown(card_container("Total Stock Value (USD)", f"${total_value:,.2f}"))
        col3.markdown(card_container("Low Stock Items", low_stock, "#FFB900"))
        col4.markdown(card_container("Out of Stock", out_stock, "#D83B01"))

        if not sales_df.empty:
            total_profit = sales_df["Profit"].sum()
            st.markdown(card_container("Total Profit (USD)", f"${total_profit:,.2f}", "#107C10"))

# -----------------------------
# Search Items
# -----------------------------
elif choice == "Search Items":
    section_header("🔍 Search Inventory")
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
    section_header("➕ Add New Stock Item")

    col1, col2 = st.columns(2)

    with col1:
        category = st.text_input("Category")
        item = st.text_input("Item Name")
        item_code = st.text_input("Item Code (scan or type)")
        brand = st.text_input("Brand")

    with col2:
        available = st.number_input("Available Stock", min_value=0)
        reorder = st.number_input("Reorder Level", min_value=0)
        cost_price = st.number_input("Cost Price (USD)", min_value=0.0, format="%.2f")
        price = st.number_input("Selling Price (USD)", min_value=0.0, format="%.2f")

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
                "Cost Price": cost_price,
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
    section_header("📥 Receive Stock")

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
                st.info(f"Found: {item_row['Item']} ({item_row['Brand']})")
                st.write(f"**Current Stock:** {item_row['Available Stock']}")
                st.write(f"**Cost Price:** ${item_row['Cost Price']}")
                st.write(f"**Selling Price:** ${item_row['Price']}")

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
# Issue Stock (by Code)
# -----------------------------
elif choice == "Issue Stock (by Code)":
    section_header("📤 Issue Stock")

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
                st.info(f"Found: {item_row['Item']} ({item_row['Brand']})")
                st.write(f"**Available Stock:** {item_row['Available Stock']}")
                st.write(f"**Cost Price:** ${item_row['Cost Price']}")
                st.write(f"**Selling Price:** ${item_row['Price']}")

        qty = st.number_input("Quantity to Issue", min_value=1)

        if st.button("Issue"):
            if item_row is None:
                st.error("Enter a valid Item Code first.")
            elif qty > item_row["Available Stock"]:
                st.error("Not enough stock!")
            else:
                idx = df.index[df["Item Code"].astype(str) == str(code)][0]

                df.at[idx, "Available Stock"] -= qty
                df.at[idx, "Total Value"] = df.at[idx, "Available Stock"] * df.at[idx, "Price"]
                df.at[idx, "Stock Status"] = compute_status(
                    df.at[idx, "Available Stock"],
                    df.at[idx, "Reorder Level"]
                )
                save_data(df)

                selling_price = item_row["Price"]
                cost_price = item_row["Cost Price"]
                total_sale = qty * selling_price
                total_cost = qty * cost_price
                profit = total_sale - total_cost

                sale = {
                    "Item": item_row["Item"],
                    "Item Code": item_row["Item Code"],
                    "Quantity Sold": qty,
                    "Selling Price": selling_price,
                    "Cost Price": cost_price,
                    "Total Sale": total_sale,
                    "Total Cost": total_cost,
                    "Profit": profit,
                    "Date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }

                sales_df.loc[len(sales_df)] = sale
                save_sales(sales_df)

                st.success(f"Sale recorded! Profit: ${profit:,.2f}")

# -----------------------------
# Sales Tracking
# -----------------------------
elif choice == "Sales Tracking":
    section_header("💰 Sales Tracking")

    if sales_df.empty:
        st.info("No sales recorded yet.")
    else:
        st.subheader("📄 All Sales Records")
        st.dataframe(sales_df, use_container_width=True)

        st.subheader("🏆 Best‑Selling Items")

        best = sales_df.groupby(["Item", "Item Code"]).agg({
            "Quantity Sold": "sum",
            "Total Sale": "sum",
            "Total Cost": "sum",
            "Profit": "sum"
        }).sort_values("Quantity Sold", ascending=False)

        st.dataframe(best, use_container_width=True)

        st.subheader("📈 Profit Summary")
        total_revenue = sales_df["Total Sale"].sum()
        total_cost = sales_df["Total Cost"].sum()
        total_profit = sales_df["Profit"].sum()

        col1, col2, col3 = st.columns(3)
        col1.markdown(card_container("Total Revenue (USD)", f"${total_revenue:,.2f}", "#0078D4"))
        col2.markdown(card_container("Total Cost (USD)", f"${total_cost:,.2f}", "#FFB900"))
        col3.markdown(card_container("Total Profit (USD)", f"${total_profit:,.2f}", "#107C10"))

# -----------------------------
# Current Stock
# -----------------------------
elif choice == "Current Stock":
    section_header("📦 Current Stock List")

    if df.empty:
        st.warning("No stock data available.")
    else:
        st.dataframe(df, use_container_width=True)

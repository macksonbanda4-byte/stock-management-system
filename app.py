import streamlit as st
import pandas as pd
from datetime import datetime
import os

# ============================================================
#  USERS CSV HANDLING
# ============================================================

USERS_FILE = "users.csv"

def load_users():
    if not os.path.exists(USERS_FILE):
        df = pd.DataFrame(columns=["username", "password", "role"])
        df.to_csv(USERS_FILE, index=False)
    return pd.read_csv(USERS_FILE)

def save_users(df):
    df.to_csv(USERS_FILE, index=False)

# ============================================================
#  STOCK & SALES CSV HANDLING
# ============================================================

def load_stock():
    try:
        return pd.read_csv("stock_clean.csv")
    except:
        return pd.DataFrame(columns=[
            "Category", "Item", "Item Code", "Brand",
            "Available Stock", "Reorder Level", "Cost Price",
            "Price", "Total Value", "Stock Status"
        ])

def save_stock(df):
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

# ============================================================
#  HELPERS
# ============================================================

def compute_status(available, reorder):
    if available == 0:
        return "Out of Stock"
    elif available <= reorder:
        return "Low Stock"
    else:
        return "In Stock"

def card(title, value, color="#0078D4"):
    return f"""
    <div style="
        background:white;
        padding:20px;
        border-radius:12px;
        box-shadow:0 2px 8px rgba(0,0,0,0.15);
        border-left:6px solid {color};
        margin-bottom:15px;">
        <h4 style="margin:0;color:#444;">{title}</h4>
        <h2 style="margin:5px 0 0 0;color:#222;">{value}</h2>
    </div>
    """

def header(text):
    st.markdown(
        f"""
        <h2 style="color:#0078D4;border-bottom:2px solid #E5E5E5;padding-bottom:5px;">
            {text}
        </h2>
        """,
        unsafe_allow_html=True
    )

# ============================================================
#  LOGIN PAGE
# ============================================================

def login_page():
    st.markdown("<h1 style='color:#0078D4;text-align:center;'>🔐 Login</h1>", unsafe_allow_html=True)

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):

        # ====================================================
        #  EMERGENCY MASTER LOGIN (NO CSV NEEDED)
        # ====================================================
        if username.lower() == "master" and password.lower() == "letmein":
            st.session_state["logged_in"] = True
            st.session_state["username"] = "master"
            st.session_state["role"] = "admin"
            st.success("Master login successful!")
            st.stop()

        users = load_users()

        # CASE-INSENSITIVE LOGIN
        users["username_lower"] = users["username"].str.lower()
        users["password_lower"] = users["password"].astype(str).str.lower()

        match = users[
            (users["username_lower"] == username.lower()) &
            (users["password_lower"] == password.lower())
        ]

        if not match.empty:
            st.session_state["logged_in"] = True
            st.session_state["username"] = match.iloc[0]["username"]
            st.session_state["role"] = match.iloc[0]["role"]
            st.success("Login successful!")
        else:
            st.error("Invalid username or password.")

# ============================================================
#  MANAGE USERS (ADMIN ONLY)
# ============================================================

def manage_users_page():
    header("👥 Manage Users (Admin Only)")

    users = load_users()

    st.subheader("Add New User")
    new_user = st.text_input("New Username")
    new_pass = st.text_input("New Password", type="password")
    new_role = st.selectbox("Role", ["admin", "staff", "viewer"], key="new_role")

    if st.button("Add User"):
        if new_user.lower() in users["username"].str.lower().values:
            st.error("Username already exists.")
        else:
            users.loc[len(users)] = [new_user, new_pass, new_role]
            save_users(users)
            st.success("User added successfully!")

    st.subheader("Existing Users")
    st.dataframe(users)

    st.subheader("Edit / Delete User")
    selected = st.selectbox("Select User", users["username"].tolist(), key="select_user")

    if selected:
        row = users[users["username"] == selected].iloc[0]

        edit_pass = st.text_input("Password", value=row["password"], type="password", key=f"pass_{selected}")
        edit_role = st.selectbox(
            "Role",
            ["admin", "staff", "viewer"],
            index=["admin", "staff", "viewer"].index(row["role"]),
            key=f"edit_role_{selected}"
        )

        if st.button("Save Changes", key=f"save_{selected}"):
            users.loc[users["username"] == selected, "password"] = edit_pass
            users.loc[users["username"] == selected, "role"] = edit_role
            save_users(users)
            st.success("User updated successfully!")

        if st.button("Delete User", key=f"delete_{selected}"):
            if selected == st.session_state.get("username"):
                st.warning("You are deleting your own account. Confirm below.")
                if st.button("Confirm Delete", key=f"confirm_delete_{selected}"):
                    users = users[users["username"] != selected]
                    save_users(users)
                    st.session_state.clear()
                    st.success("Your account has been deleted.")
                    st.stop()
            else:
                users = users[users["username"] != selected]
                save_users(users)
                st.success("User deleted successfully!")

# ============================================================
#  MAIN APP
# ============================================================

st.set_page_config(page_title="Automated Stock Management System", layout="wide")

if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

if not st.session_state["logged_in"]:
    login_page()
    st.stop()

# Load data
df = load_stock()
sales_df = load_sales()

# Sidebar user info
if "username" in st.session_state and "role" in st.session_state:
    st.sidebar.markdown(
        f"""
        <div style="padding:10px;background:#F3F9FF;border-radius:8px;border-left:4px solid #0078D4;">
            <strong>👤 Logged in as:</strong><br>{st.session_state['username']} ({st.session_state['role']})
        </div>
        """,
        unsafe_allow_html=True
    )

if st.sidebar.button("Logout"):
    st.session_state.clear()
    st.experimental_rerun()

role = st.session_state.get("role", "viewer")

# ============================================================
#  ROLE-BASED MENU
# ============================================================

menu_admin = [
    "Dashboard", "Search Items", "Add New Item",
    "Receive Stock", "Issue Stock", "Sales Tracking",
    "Current Stock", "Manage Users"
]

menu_staff = [
    "Dashboard", "Search Items",
    "Receive Stock", "Issue Stock", "Current Stock"
]

menu_viewer = [
    "Dashboard", "Current Stock"
]

if role == "admin":
    choice = st.sidebar.selectbox("Menu", menu_admin)
elif role == "staff":
    choice = st.sidebar.selectbox("Menu", menu_staff)
else:
    choice = st.sidebar.selectbox("Menu", menu_viewer)

# ============================================================
#  DASHBOARD
# ============================================================

if choice == "Dashboard":
    header("📊 System Overview")

    if df.empty:
        st.warning("No stock data available.")
    else:
        total_items = len(df)
        total_value = df["Total Value"].sum()
        low_stock = len(df[df["Stock Status"] == "Low Stock"])
        out_stock = len(df[df["Stock Status"] == "Out of Stock"])

        col1, col2 = st.columns(2)
        col3, col4 = st.columns(2)

        col1.markdown(card("Total Items", total_items), unsafe_allow_html=True)
        col2.markdown(card("Total Stock Value (USD)", f"${total_value:,.2f}"), unsafe_allow_html=True)
        col3.markdown(card("Low Stock Items", low_stock, "#FFB900"), unsafe_allow_html=True)
        col4.markdown(card("Out of Stock", out_stock, "#D83B01"), unsafe_allow_html=True)

        if not sales_df.empty:
            total_profit = sales_df["Profit"].sum()
            st.markdown(card("Total Profit (USD)", f"${total_profit:,.2f}", "#107C10"), unsafe_allow_html=True)

# ============================================================
#  SEARCH ITEMS
# ============================================================

elif choice == "Search Items":
    header("🔍 Search Inventory")
    term = st.text_input("Search by item name, code, or brand")

    if term:
        filtered = df[df.apply(
            lambda row: term.lower() in row.astype(str).str.lower().to_string(),
            axis=1
        )]
        st.dataframe(filtered)

# ============================================================
#  ADD NEW ITEM (ADMIN ONLY)
# ============================================================

elif choice == "Add New Item" and role == "admin":
    header("➕ Add New Stock Item")

    col1, col2 = st.columns(2)

    with col1:
        category = st.text_input("Category")
        item = st.text_input("Item Name")
        item_code = st.text_input("Item Code")
        brand = st.text_input("Brand")

    with col2:
        available = st.number_input("Available Stock", min_value=0)
        reorder = st.number_input("Reorder Level", min_value=0)
        cost_price = st.number_input("Cost Price (USD)", min_value=0.0, format="%.2f")
        price = st.number_input("Selling Price (USD)", min_value=0.0, format="%.2f")

    if st.button("Add Item"):
        if not category or not item or not item_code or not brand:
            st.error("All fields are required.")
        elif item_code in df["Item Code"].astype(str).values:
            st.error("Item Code already exists.")
        else:
            total_value = available * price
            status = compute_status(available, reorder)

            df.loc[len(df)] = [
                category, item, item_code, brand,
                available, reorder, cost_price,
                price, total_value, status
            ]

            save_stock(df)
            st.success(f"{item} added successfully!")

# ============================================================
#  RECEIVE STOCK
# ============================================================

elif choice == "Receive Stock":
    header("📥 Receive Stock")

    code = st.text_input("Item Code")
    qty = st.number_input("Quantity Received", min_value=1)

    if st.button("Update Stock"):
        matches = df[df["Item Code"].astype(str) == str(code)]
        if matches.empty:
            st.error("Item not found.")
        else:
            idx = matches.index[0]
            df.at[idx, "Available Stock"] += qty
            df.at[idx, "Total Value"] = df.at[idx, "Available Stock"] * df.at[idx, "Price"]
            df.at[idx, "Stock Status"] = compute_status(
                df.at[idx, "Available Stock"],
                df.at[idx, "Reorder Level"]
            )
            save_stock(df)
            st.success("Stock updated!")

# ============================================================
#  ISSUE STOCK
# ============================================================

elif choice == "Issue Stock":
    header("📤 Issue Stock")

    code = st.text_input("Item Code")
    qty = st.number_input("Quantity to Issue", min_value=1)

    if st.button("Issue"):
        matches = df[df["Item Code"].astype(str) == str(code)]
        if matches.empty:
            st.error("Item not found.")
        else:
            row = matches.iloc[0]
            if qty > row["Available Stock"]:
                st.error("Not enough stock!")
            else:
                idx = matches.index[0]
                df.at[idx, "Available Stock"] -= qty
                df.at[idx, "Total Value"] = df.at[idx, "Available Stock"] * df.at[idx, "Price"]
                df.at[idx, "Stock Status"] = compute_status(
                    df.at[idx, "Available Stock"],
                    df.at[idx, "Reorder Level"]
                )
                save_stock(df)

                sale = {
                    "Item": row["Item"],
                    "Item Code": row["Item Code"],
                    "Quantity Sold": qty,
                    "Selling Price": row["Price"],
                    "Cost Price": row["Cost Price"],
                    "Total Sale": qty * row["Price"],
                    "Total Cost": qty * row["Cost Price"],
                    "Profit": qty * (row["Price"] - row["Cost Price"]),
                    "Date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }

                sales_df.loc[len(sales_df)] = sale
                save_sales(sales_df)

                st.success(f"Sale recorded! Profit: ${sale['Profit']:,.2f}")

# ============================================================
#  SALES TRACKING (ADMIN ONLY)
# ============================================================

elif choice == "Sales Tracking" and role == "admin":
    header("💰 Sales Tracking")

    if sales_df.empty:
        st.info("No sales recorded yet.")
    else:
        st.subheader("All Sales Records")
        st.dataframe(sales_df)

        st.subheader("Profit Summary")
        total_revenue = sales_df["Total Sale"].sum()
        total_cost = sales_df["Total Cost"].sum()
        total_profit = sales_df["Profit"].sum()

        col1, col2, col3 = st.columns(3)
        col1.markdown(card("Total Revenue (USD)", f"${total_revenue:,.2f}"), unsafe_allow_html=True)
        col2.markdown(card("Total Cost (USD)", f"${total_cost:,.2f}", "#FFB900"), unsafe_allow_html=True)
        col3.markdown(card("Total Profit (USD)", f"${total_profit:,.2f}", "#107C10"), unsafe_allow_html=True)

# ============================================================
#  CURRENT STOCK
# ============================================================

elif choice == "Current Stock":
    header("📦 Current Stock List")
    st.dataframe(df)

# ============================================================
#  MANAGE USERS (ADMIN ONLY)
# ============================================================

elif choice == "Manage Users" and role == "admin":
    manage_users_page()

import streamlit as st
import pandas as pd
from datetime import datetime
import os

# ============================================================
#  FILE PATHS
# ============================================================

USERS_FILE = "users.csv"
STOCK_FILE = "stock_clean.csv"
SALES_FILE = "sales.csv"
ACTIVITY_FILE = "activity_log.csv"

# ============================================================
#  DATA HELPERS
# ============================================================

def ensure_file(path: str, columns: list[str]) -> pd.DataFrame:
    if not os.path.exists(path):
        df = pd.DataFrame(columns=columns)
        df.to_csv(path, index=False)
    else:
        df = pd.read_csv(path)
    return df

def load_users() -> pd.DataFrame:
    return ensure_file(USERS_FILE, ["username", "password", "role"])

def save_users(df: pd.DataFrame) -> None:
    df.to_csv(USERS_FILE, index=False)

def compute_status(available: float, reorder: float) -> str:
    if available <= 0:
        return "Out of Stock"
    elif available <= reorder:
        return "Low Stock"
    else:
        return "In Stock"

def load_stock() -> pd.DataFrame:
    cols = [
        "Category", "Item", "Item Code", "Brand",
        "Available Stock", "Reorder Level", "Cost Price",
        "Price", "Total Value", "Stock Status"
    ]
    df = ensure_file(STOCK_FILE, cols)
    for c in ["Available Stock", "Reorder Level", "Cost Price", "Price", "Total Value"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    if "Stock Status" not in df.columns:
        df["Stock Status"] = df.apply(
            lambda r: compute_status(r.get("Available Stock", 0), r.get("Reorder Level", 0)),
            axis=1
        )
    return df

def save_stock(df: pd.DataFrame) -> None:
    df.to_csv(STOCK_FILE, index=False)

def load_sales() -> pd.DataFrame:
    cols = [
        "Item", "Item Code", "Quantity Sold",
        "Selling Price", "Cost Price",
        "Total Sale", "Total Cost", "Profit", "Date"
    ]
    df = ensure_file(SALES_FILE, cols)
    for c in ["Quantity Sold", "Selling Price", "Cost Price", "Total Sale", "Total Cost", "Profit"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    return df

def save_sales(df: pd.DataFrame) -> None:
    df.to_csv(SALES_FILE, index=False)

def load_activity() -> pd.DataFrame:
    cols = ["timestamp", "user", "action", "details"]
    return ensure_file(ACTIVITY_FILE, cols)

def save_activity(df: pd.DataFrame) -> None:
    df.to_csv(ACTIVITY_FILE, index=False)

# ============================================================
#  ACTIVITY LOGGING
# ============================================================

def log_activity(user: str, action: str, details: str = "") -> None:
    df = load_activity()
    df.loc[len(df)] = [
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        user,
        action,
        details
    ]
    save_activity(df)

# ============================================================
#  UI HELPERS
# ============================================================

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

def export_csv(df: pd.DataFrame, filename: str):
    st.download_button(
        label=f"Download {filename}",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name=filename,
        mime="text/csv",
    )

def import_csv(label: str) -> pd.DataFrame | None:
    uploaded = st.file_uploader(label, type=["csv"])
    if uploaded is not None:
        return pd.read_csv(uploaded)
    return None

# ============================================================
#  AUTH / LOGIN
# ============================================================

def login_page():
    st.markdown("<h1 style='color:#0078D4;text-align:center;'>🔐 Login</h1>", unsafe_allow_html=True)

    username = st.text_input("Username", key="login_username")
    password = st.text_input("Password", type="password", key="login_password")

    if st.button("Login", key="login_button"):

        # Master login bypass
        if username.lower() == "master" and password.lower() == "letmein":
            st.session_state["logged_in"] = True
            st.session_state["username"] = "master"
            st.session_state["role"] = "admin"
            log_activity("master", "login", "Master login")
            st.success("Master login successful!")
            st.stop()

        users = load_users()
        if users.empty:
            st.error("No users found. Please use master login first and create users.")
            return

        users["username_lower"] = users["username"].astype(str).str.lower()
        users["password_lower"] = users["password"].astype(str).str.lower()

        match = users[
            (users["username_lower"] == username.lower()) &
            (users["password_lower"] == password.lower())
        ]

        if not match.empty:
            st.session_state["logged_in"] = True
            st.session_state["username"] = match.iloc[0]["username"]
            st.session_state["role"] = match.iloc[0]["role"]
            log_activity(st.session_state["username"], "login", "Normal login")
            st.success("Login successful!")
        else:
            st.error("Invalid username or password.")

# ============================================================
#  MANAGE USERS
# ============================================================

def manage_users_page():
    header("👥 Manage Users (Admin Only)")

    users = load_users()

    st.subheader("Add New User")
    new_user = st.text_input("New Username", key="new_user_name")
    new_pass = st.text_input("New Password", type="password", key="new_user_pass")
    new_role = st.selectbox("Role", ["admin", "staff", "viewer"], key="new_user_role")

    if st.button("Add User", key="add_user_btn"):
        if not new_user or not new_pass:
            st.error("Username and password are required.")
        elif new_user.lower() in users["username"].astype(str).str.lower().values:
            st.error("Username already exists.")
        else:
            users.loc[len(users)] = [new_user, new_pass, new_role]
            save_users(users)
            log_activity(st.session_state["username"], "add_user", f"Added user {new_user} ({new_role})")
            st.success("User added successfully!")

    st.subheader("Existing Users")
    st.dataframe(users)

    st.subheader("Edit / Delete / Reset Password")
    if not users.empty:
        selected = st.selectbox(
            "Select User",
            users["username"].tolist(),
            key="select_user_for_edit"
        )

        if selected:
            row = users[users["username"] == selected].iloc[0]

            edit_pass = st.text_input(
                "Password",
                value=str(row["password"]),
                type="password",
                key=f"edit_pass_{selected}"
            )
            edit_role = st.selectbox(
                "Role",
                ["admin", "staff", "viewer"],
                index=["admin", "staff", "viewer"].index(str(row["role"])),
                key=f"edit_role_{selected}"
            )

            col1, col2, col3 = st.columns(3)

            with col1:
                if st.button("Save Changes", key=f"save_{selected}"):
                    users.loc[users["username"] == selected, "password"] = edit_pass
                    users.loc[users["username"] == selected, "role"] = edit_role
                    save_users(users)
                    log_activity(st.session_state["username"], "edit_user", f"Edited user {selected}")
                    st.success("User updated successfully!")

            with col2:
                if st.button("Reset Password to 'password123'", key=f"reset_{selected}"):
                    users.loc[users["username"] == selected, "password"] = "password123"
                    save_users(users)
                    log_activity(
                        st.session_state["username"],
                        "reset_password",
                        f"Reset password for {selected} to 'password123'"
                    )
                    st.success(f"Password for {selected} reset to 'password123'")

            with col3:
                if st.button("Delete User", key=f"delete_{selected}"):
                    if selected == st.session_state.get("username"):
                        st.warning("You are deleting your own account. Confirm below.")
                        if st.button("Confirm Delete", key=f"confirm_delete_{selected}"):
                            users = users[users["username"] != selected]
                            save_users(users)
                            log_activity(selected, "delete_self", "User deleted own account")
                            st.session_state.clear()
                            st.success("Your account has been deleted. Logging out...")
                            st.stop()
                    else:
                        users = users[users["username"] != selected]
                        save_users(users)
                        log_activity(
                            st.session_state["username"],
                            "delete_user",
                            f"Deleted user {selected}"
                        )
                        st.success("User deleted successfully!")

# ============================================================
#  STOCK OPERATIONS
# ============================================================

def add_item_page(df: pd.DataFrame):
    header("➕ Add New Stock Item")

    col1, col2 = st.columns(2)

    with col1:
        category = st.text_input("Category", key="add_cat")
        item = st.text_input("Item Name", key="add_item")
        item_code = st.text_input("Item Code / Barcode", key="add_code")
        brand = st.text_input("Brand", key="add_brand")

    with col2:
        available = st.number_input("Available Stock", min_value=0, key="add_available")
        reorder = st.number_input("Reorder Level", min_value=0, key="add_reorder")
        cost_price = st.number_input("Cost Price (USD)", min_value=0.0, format="%.2f", key="add_cost")
        price = st.number_input("Selling Price (USD)", min_value=0.0, format="%.2f", key="add_price")

    if st.button("Add Item", key="add_item_btn"):
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
            log_activity(
                st.session_state["username"],
                "add_item",
                f"Added item {item} ({item_code})"
            )
            st.success(f"{item} added successfully!")

def receive_stock_page(df: pd.DataFrame):
    header("📥 Receive Stock")

    code = st.text_input("Item Code / Barcode", key="receive_code")
    qty = st.number_input("Quantity Received", min_value=1, key="receive_qty")

    if st.button("Update Stock", key="receive_btn"):
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
            log_activity(
                st.session_state["username"],
                "receive_stock",
                f"Received {qty} of {df.at[idx, 'Item']} ({df.at[idx, 'Item Code']})"
            )
            st.success("Stock updated!")

def issue_stock_page(df: pd.DataFrame, sales_df: pd.DataFrame):
    header("📤 Issue Stock")

    code = st.text_input("Item Code / Barcode", key="issue_code")
    qty = st.number_input("Quantity to Issue", min_value=1, key="issue_qty")

    if st.button("Issue", key="issue_btn"):
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

                log_activity(
                    st.session_state["username"],
                    "issue_stock",
                    f"Issued {qty} of {row['Item']} ({row['Item Code']})"
                )

                st.success(f"Sale recorded! Profit: ${sale['Profit']:,.2f}")

# ============================================================
#  SALES TRACKING
# ============================================================

def sales_tracking_page(sales_df: pd.DataFrame):
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

        st.subheader("Profit by Item")
        profit_data = sales_df.groupby("Item")["Profit"].sum().sort_values(ascending=False)
        st.bar_chart(profit_data)

# ============================================================
#  IMPORT / EXPORT
# ============================================================

def import_export_page(df: pd.DataFrame, sales_df: pd.DataFrame):
    header("📤📥 Import / Export Data")

    st.subheader("Export")
    col1, col2 = st.columns(2)
    with col1:
        if not df.empty:
            export_csv(df, "stock_export.csv")
        else:
            st.info("No stock data to export.")
    with col2:
        if not sales_df.empty:
            export_csv(sales_df, "sales_export.csv")
        else:
            st.info("No sales data to export.")

    st.subheader("Import Stock")
    new_stock = import_csv("Upload stock CSV")
    if new_stock is not None:
        if st.button("Replace current stock with uploaded file", key="import_stock_btn"):
            save_stock(new_stock)
            log_activity(
                st.session_state["username"],
                "import_stock",
                "Replaced stock with uploaded CSV"
            )
            st.success("Stock data replaced. Click Rerun.")

    st.subheader("Import Sales")
    new_sales = import_csv("Upload sales CSV")
    if new_sales is not None:
        if st.button("Replace current sales with uploaded file", key="import_sales_btn"):
            save_sales(new_sales)
            log_activity(
                st.session_state["username"],
                "import_sales",
                "Replaced sales with uploaded CSV"
            )
            st.success("Sales data replaced. Click Rerun.")

# ============================================================
#  ACTIVITY LOG PAGE
# ============================================================

def activity_log_page():
    header("📜 User Activity Log")
    log_df = load_activity()
    if log_df.empty:
        st.info("No activity recorded yet.")
    else:
        st.dataframe(log_df.sort_values("timestamp", ascending=False))

# ============================================================
#  DASHBOARD
# ============================================================

def dashboard_page(df: pd.DataFrame, sales_df: pd.DataFrame):
    header("📊 System Overview")

    # ============================
    # QUICK BARCODE SCAN PANEL
    # ============================
    st.subheader("🔍 Quick Barcode Scan")

    scan_code = st.text_input("Scan Barcode / Enter Item Code", key="dash_scan_code")

    if scan_code:
        match = df[df["Item Code"].astype(str) == scan_code]

        if match.empty:
            st.error("No item found with that barcode.")
        else:
            item = match.iloc[0]

            st.success("Item Found")

            st.markdown(f"""
                **Item:** {item['Item']}  
                **Brand:** {item['Brand']}  
                **Available Stock:** {item['Available Stock']}  
                **Price:** ${item['Price']:.2f}  
                **Status:** {item['Stock Status']}
            """)

            colA, colB = st.columns(2)

            with colA:
                qty_receive = st.number_input(
                    "Quantity to Receive",
                    min_value=1,
                    key="dash_receive_qty"
                )
                if st.button("Receive Stock", key="dash_receive_btn"):
                    idx = match.index[0]
                    df.at[idx, "Available Stock"] += qty_receive
                    df.at[idx, "Total Value"] = df.at[idx, "Available Stock"] * df.at[idx, "Price"]
                    df.at[idx, "Stock Status"] = compute_status(
                        df.at[idx, "Available Stock"],
                        df.at[idx, "Reorder Level"]
                    )
                    save_stock(df)
                    log_activity(
                        st.session_state["username"],
                        "receive_stock_dashboard",
                        f"Received {qty_receive} of {item['Item']} ({item['Item Code']}) via dashboard"
                    )
                    st.success("Stock updated successfully.")

            with colB:
                qty_issue = st.number_input(
                    "Quantity to Issue",
                    min_value=1,
                    key="dash_issue_qty"
                )
                if st.button("Issue Stock", key="dash_issue_btn"):
                    if qty_issue > item["Available Stock"]:
                        st.error("Not enough stock to issue.")
                    else:
                        idx = match.index[0]
                        df.at[idx, "Available Stock"] -= qty_issue
                        df.at[idx, "Total Value"] = df.at[idx, "Available Stock"] * df.at[idx, "Price"]
                        df.at[idx, "Stock Status"] = compute_status(
                            df.at[idx, "Available Stock"],
                            df.at[idx, "Reorder Level"]
                        )
                        save_stock(df)

                        sale = {
                            "Item": item["Item"],
                            "Item Code": item["Item Code"],
                            "Quantity Sold": qty_issue,
                            "Selling Price": item["Price"],
                            "Cost Price": item["Cost Price"],
                            "Total Sale": qty_issue * item["Price"],
                            "Total Cost": qty_issue * item["Cost Price"],
                            "Profit": qty_issue * (item["Price"] - item["Cost Price"]),
                            "Date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }

                        sales_df.loc[len(sales_df)] = sale
                        save_sales(sales_df)

                        log_activity(
                            st.session_state["username"],
                            "issue_stock_dashboard",
                            f"Issued {qty_issue} of {item['Item']} ({item['Item Code']}) via dashboard"
                        )

                        st.success(f"Issued successfully. Profit: ${sale['Profit']:.2f}")

    if df.empty:
        st.warning("No stock data available.")
        return

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

    st.subheader("⚠️ Low Stock Alerts")
    alerts = df[df["Stock Status"].isin(["Low Stock", "Out of Stock"])]
    if alerts.empty:
        st.success("All items are sufficiently stocked.")
    else:
        for _, row in alerts.iterrows():
            msg = (
                f"{row['Item']} ({row['Item Code']}) - {row['Stock Status']} "
                f"(Available: {row['Available Stock']}, Reorder: {row['Reorder Level']})"
            )
            if row["Stock Status"] == "Out of Stock":
                st.error(msg)
            else:
                st.warning(msg)

    st.subheader("Stock by Item")
    chart_data = df[["Item", "Available Stock"]].set_index("Item")
    st.bar_chart(chart_data)

    if not sales_df.empty:
        st.subheader("Profit by Item")
        profit_data = sales_df.groupby("Item")["Profit"].sum().sort_values(ascending=False)
        st.bar_chart(profit_data)

# ============================================================
#  SEARCH
# ============================================================

def search_page(df: pd.DataFrame):
    header("🔍 Search Inventory")
    term = st.text_input("Search by item name, code, or brand", key="search_term")

    if term:
        filtered = df[df.apply(
            lambda row: term.lower() in row.astype(str).str.lower().to_string(),
            axis=1
        )]
        if filtered.empty:
            st.info("No matching items found.")
        else:
            st.dataframe(filtered)

# ============================================================
#  MAIN APP
# ============================================================

st.set_page_config(page_title="Automated Stock Management System", layout="wide")

if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

if not st.session_state["logged_in"]:
    login_page()
    st.stop()

df = load_stock()
sales_df = load_sales()

if "username" in st.session_state and "role" in st.session_state:
    st.sidebar.markdown(
        f"""
        <div style="padding:10px;background:#F3F9FF;border-radius:8px;border-left:4px solid #0078D4;">
            <strong>👤 Logged in as:</strong><br>{st.session_state['username']} ({st.session_state['role']})
        </div>
        """,
        unsafe_allow_html=True
    )

if st.sidebar.button("Logout", key="logout_btn"):
    log_activity(st.session_state.get("username", "unknown"), "logout", "User logged out")
    st.session_state.clear()
    st.experimental_rerun()

role = st.session_state.get("role", "viewer")

menu_admin = [
    "Dashboard", "Search Items", "Add New Item",
    "Receive Stock", "Issue Stock", "Sales Tracking",
    "Current Stock", "Import / Export", "Manage Users",
    "Activity Log"
]

menu_staff = [
    "Dashboard", "Search Items",
    "Receive Stock", "Issue Stock", "Current Stock"
]

menu_viewer = [
    "Dashboard", "Current Stock"
]

if role == "admin":
    choice = st.sidebar.selectbox("Menu", menu_admin, key="menu_admin")
elif role == "staff":
    choice = st.sidebar.selectbox("Menu", menu_staff, key="menu_staff")
else:
    choice = st.sidebar.selectbox("Menu", menu_viewer, key="menu_viewer")

if choice == "Dashboard":
    dashboard_page(df, sales_df)
elif choice == "Search Items":
    search_page(df)
elif choice == "Add New Item" and role == "admin":
    add_item_page(df)
elif choice == "Receive Stock":
    receive_stock_page(df)
elif choice == "Issue Stock":
    issue_stock_page(df, sales_df)
elif choice == "Sales Tracking" and role == "admin":
    sales_tracking_page(sales_df)
elif choice == "Current Stock":
    header("📦 Current Stock List")
    st.dataframe(df)
elif choice == "Import / Export" and role == "admin":
    import_export_page(df, sales_df)
elif choice == "Manage Users" and role == "admin":
    manage_users_page()
elif choice == "Activity Log" and role == "admin":
    activity_log_page()

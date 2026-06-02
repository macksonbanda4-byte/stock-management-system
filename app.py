import streamlit as st
import pandas as pd
import os
from datetime import datetime
import hashlib
import json
import shutil
from pathlib import Path
from io import BytesIO

# ============================================================
# FILE PATHS & CONSTANTS
# ============================================================
STOCK_FILE = "stock_export.csv"
SALES_FILE = "sales.csv"
USERS_FILE = "users.json"
ACTIVITY_LOG_FILE = "activity_log.csv"
BACKUP_DIR = "backups"
CLIENT_DIR = "backups/clients"
BARCODE_DIR = "barcodes"

LOCATIONS = ["Blue container", "Red container", "Shop"]

REQUIRED_STOCK_COLS = [
    "Category", "Item", "Item Code", "Brand",
    "Available Stock", "Reorder Level",
    "Cost Price", "Selling Price",
    "Total Value", "Stock Status",
    "Location", "Supplier"
]

# ============================================================
# LOAD & SAVE STOCK / SALES (FIXED)
# ============================================================
@st.cache_data
def load_stock():
    # If file missing or empty, try restore from latest backup
    if not os.path.exists(STOCK_FILE) or os.path.getsize(STOCK_FILE) == 0:
        backups = sorted([f for f in os.listdir(BACKUP_DIR) if f.startswith("stock_")])
        if backups:
            latest = backups[-1]
            shutil.copy(f"{BACKUP_DIR}/{latest}", STOCK_FILE)
            st.warning(f"Stock file was missing/empty. Restored from backup: {latest}")
        else:
            df = pd.DataFrame(columns=REQUIRED_STOCK_COLS)
            return normalize_stock_df(df)

    df = pd.read_csv(STOCK_FILE)
    return normalize_stock_df(df)


def save_stock(df):
    df.to_csv(STOCK_FILE, index=False)
    load_stock.clear()

    # Auto-backup with date stamp
    ensure_dir(BACKUP_DIR)
    timestamp = datetime.now().strftime("%Y%m%d")
    backup_file = f"{BACKUP_DIR}/stock_{timestamp}.csv"
    shutil.copy(STOCK_FILE, backup_file)

# ============================================================
# USER MANAGEMENT (LOCAL JSON)
# ============================================================
def load_users():
    if not os.path.exists(USERS_FILE):
        default = {
            "admin": {
                "password": hash_password("admin123"),
                "role": "admin",
            }
        }
        with open(USERS_FILE, "w") as f:
            json.dump(default, f, indent=4)
        return default
    with open(USERS_FILE, "r") as f:
        return json.load(f)

def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=4)

def authenticate(username, password):
    users = load_users()
    if username in users:
        return users[username]["password"] == hash_password(password)
    return False

def get_user_role(username):
    users = load_users()
    if username in users:
        return users[username].get("role", "user")
    return "user"

def login_block():
    st.title("Stock Management System - Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        if authenticate(username, password):
            st.session_state["logged_in"] = True
            st.session_state["username"] = username
            st.session_state["role"] = get_user_role(username)
            log_activity(username, "Login", "User logged in")
            st.rerun()
        else:
            st.error("Invalid username or password")

def require_login():
    if "logged_in" not in st.session_state or not st.session_state["logged_in"]:
        login_block()
        st.stop()

# ============================================================
# UNDO SUPPORT
# ============================================================
def push_undo_snapshot(df_stock, df_sales):
    st.session_state["undo_stock"] = df_stock.copy()
    st.session_state["undo_sales"] = df_sales.copy()

def can_undo():
    return "undo_stock" in st.session_state and "undo_sales" in st.session_state

def perform_undo():
    if not can_undo():
        return None, None
    df_stock = st.session_state["undo_stock"].copy()
    df_sales = st.session_state["undo_sales"].copy()
    save_stock(df_stock)
    save_sales(df_sales)
    del st.session_state["undo_stock"]
    del st.session_state["undo_sales"]
    return df_stock, df_sales

# ============================================================
# ITEM PAGES (Add / Edit / Delete / Receive / Transfer)
# ============================================================
def add_item_page(df_stock, current_user):
    st.header("➕ Add New Item")
    category = st.text_input("Category")
    item = st.text_input("Item Name")
    brand = st.text_input("Brand")
    supplier = st.text_input("Supplier")
    location = st.selectbox("Location", LOCATIONS)
    auto_code = generate_item_code(df_stock, category)
    item_code = st.text_input("Item Code", value=auto_code)
    available = st.number_input("Available Stock", min_value=0, step=1)
    reorder = st.number_input("Reorder Level", min_value=0, step=1)
    cost_price = st.number_input("Cost Price ($)", min_value=0.0, step=0.01, format="%.2f")
    selling_price = st.number_input("Selling Price ($)", min_value=0.0, step=0.01, format="%.2f")

    if st.button("Save Item"):
        if not category or not item or not item_code:
            st.error("Category, Item Name, and Item Code are required.")
            return
        push_undo_snapshot(df_stock, load_sales())
        total_value = available * cost_price
        status = "LOW" if available <= reorder else "OK"
        new_row = {
            "Category": category,
            "Item": item,
            "Item Code": item_code,
            "Brand": brand,
            "Available Stock": available,
            "Reorder Level": reorder,
            "Cost Price": cost_price,
            "Selling Price": selling_price,
            "Total Value": total_value,
            "Stock Status": status,
            "Location": location,
            "Supplier": supplier,
        }
        df_stock = pd.concat([df_stock, pd.DataFrame([new_row])], ignore_index=True)
        save_stock(df_stock)
        log_activity(current_user, "Add Item", f"{item} ({item_code})")
        st.success("Item added successfully.")

def edit_item_page(df_stock, current_user):
    st.header("✏️ Edit Item")
    idx, row = pick_item_with_search(df_stock, "Select Item to Edit")
    if row is None:
        return

    category = st.text_input("Category", value=row["Category"])
    item = st.text_input("Item Name", value=row["Item"])
    brand = st.text_input("Brand", value=row["Brand"])
    supplier = st.text_input("Supplier", value=row["Supplier"])
    location = st.selectbox("Location", LOCATIONS,
        index=LOCATIONS.index(row["Location"]) if row["Location"] in LOCATIONS else 0)

    item_code = st.text_input("Item Code", value=row["Item Code"])
    available = st.number_input("Available Stock", min_value=0, step=1, value=int(row["Available Stock"]))
    reorder = st.number_input("Reorder Level", min_value=0, step=1, value=int(row["Reorder Level"]))
    cost_price = st.number_input("Cost Price ($)", min_value=0.0, step=0.01,
                                 value=float(row["Cost Price"]), format="%.2f")
    selling_price = st.number_input("Selling Price ($)", min_value=0.0, step=0.01,
                                    value=float(row["Selling Price"]), format="%.2f")

    if st.button("Save Changes"):
        push_undo_snapshot(df_stock, load_sales())
        df_stock.at[idx, "Category"] = category
        df_stock.at[idx, "Item"] = item
        df_stock.at[idx, "Item Code"] = item_code
        df_stock.at[idx, "Brand"] = brand
        df_stock.at[idx, "Supplier"] = supplier
        df_stock.at[idx, "Location"] = location
        df_stock.at[idx, "Available Stock"] = available
        df_stock.at[idx, "Reorder Level"] = reorder
        df_stock.at[idx, "Cost Price"] = cost_price
        df_stock.at[idx, "Selling Price"] = selling_price
        df_stock.at[idx, "Total Value"] = available * cost_price
        df_stock.at[idx, "Stock Status"] = "LOW" if available <= reorder else "OK"
        save_stock(df_stock)
        log_activity(current_user, "Edit Item", f"{item} ({item_code})")
        st.success("Item updated successfully.")


def delete_item_page(df_stock, current_user):
    st.header("🗑️ Delete Item")
    idx, row = pick_item_with_search(df_stock, "Select Item to Delete", allow_location_filter=False)
    if row is None:
        return
    st.warning(f"Are you sure you want to delete: {row['Item']} ({row['Item Code']})?")
    if st.button("Confirm Delete"):
        push_undo_snapshot(df_stock, load_sales())
        df_stock = df_stock.drop(index=idx).reset_index(drop=True)
        save_stock(df_stock)
        log_activity(current_user, "Delete Item", f"{row['Item']} ({row['Item Code']})")
        st.success("Item deleted successfully.")


def receive_stock_page(df_stock, current_user):
    st.header("📥 Receive Stock")
    idx, row = pick_item_with_search(df_stock, "Select Item to Receive")
    if row is None:
        return
    qty = st.number_input("Quantity Received", min_value=1, step=1)
    cost_price = st.number_input("Cost Price per Unit ($)", min_value=0.0, step=0.01,
                                 value=float(row["Cost Price"]), format="%.2f")
    if st.button("Receive"):
        push_undo_snapshot(df_stock, load_sales())
        new_qty = int(row["Available Stock"]) + qty
        df_stock.at[idx, "Available Stock"] = new_qty
        df_stock.at[idx, "Cost Price"] = cost_price
        df_stock.at[idx, "Total Value"] = new_qty * cost_price
        df_stock.at[idx, "Stock Status"] = "LOW" if new_qty <= int(row["Reorder Level"]) else "OK"
        save_stock(df_stock)
        log_activity(current_user, "Receive Stock",
                     f"{qty} of {row['Item']} ({row['Item Code']}) at ${cost_price}")
        st.success("Stock received successfully.")


def transfer_stock_page(df_stock, current_user):
    st.header("🔁 Transfer Stock Between Locations")
    idx, row = pick_item_with_search(df_stock, "Select Item to Transfer", allow_location_filter=False)
    if row is None:
        return
    from_location = st.selectbox("From Location", LOCATIONS)
    to_location = st.selectbox("To Location", [loc for loc in LOCATIONS if loc != from_location])
    qty = st.number_input("Quantity to Transfer", min_value=1, step=1)
    if st.button("Transfer"):
        if from_location == to_location:
            st.error("From and To locations must be different.")
            return
        same_item = df_stock[(df_stock["Item Code"] == row["Item Code"]) & (df_stock["Location"] == from_location)]
        if same_item.empty:
            st.error("No stock found at the selected 'From' location.")
            return
        from_idx = same_item.index[0]
        from_row = df_stock.loc[from_idx]
        if qty > int(from_row["Available Stock"]):
            st.error("Not enough stock at the source location.")
            return
        push_undo_snapshot(df_stock, load_sales())
        new_from_qty = int(from_row["Available Stock"]) - qty
        df_stock.at[from_idx, "Available Stock"] = new_from_qty
        df_stock.at[from_idx, "Total Value"] = new_from_qty * float(from_row["Cost Price"])
        df_stock.at[from_idx, "Stock Status"] = "LOW" if new_from_qty <= int(from_row["Reorder Level"]) else "OK"
        target = df_stock[(df_stock["Item Code"] == row["Item Code"]) & (df_stock["Location"] == to_location)]
        if target.empty:
            new_row = from_row.copy()
            new_row["Location"] = to_location
            new_row["Available Stock"] = qty
            new_row["Total Value"] = qty * float(from_row["Cost Price"])
            new_row["Stock Status"] = "LOW" if qty <= int(from_row["Reorder Level"]) else "OK"
            df_stock = pd.concat([df_stock, pd.DataFrame([new_row])], ignore_index=True)
        else:
            to_idx = target.index[0]
            to_row = df_stock.loc[to_idx]
            new_to_qty = int(to_row["Available Stock"]) + qty
            df_stock.at[to_idx, "Available Stock"] = new_to_qty
            df_stock.at[to_idx, "Total Value"] = new_to_qty * float(to_row["Cost Price"])
            df_stock.at[to_idx, "Stock Status"] = "LOW" if new_to_qty <= int(to_row["Reorder Level"]) else "OK"
        save_stock(df_stock)
        log_activity(current_user, "Transfer Stock",
                     f"{qty} of {row['Item']} ({row['Item Code']}) from {from_location} to {to_location}")
        st.success("Stock transferred successfully.")


def issue_stock_page(df_stock, df_sales, current_user):
    st.header("📤 Issue Stock")
    idx, row = pick_item_with_search(df_stock, "Search Item to Issue")
    if row is None:
        return
    customer = st.text_input("Customer Name (Required)")
    qty = st.number_input("Quantity to Issue", min_value=1, step=1)
    if st.button("Issue Stock"):
        if not customer.strip():
            st.error("Customer name is required before issuing stock.")
            return
        if qty > int(row["Available Stock"]):
            st.error("Not enough stock available.")
            return
        push_undo_snapshot(df_stock, df_sales)
        new_qty = int(row["Available Stock"]) - qty
        df_stock.at[idx, "Available Stock"] = new_qty
        df_stock.at[idx, "Total Value"] = new_qty * float(row["Cost Price"])
        df_stock.at[idx, "Stock Status"] = "OK" if new_qty > int(row["Reorder Level"]) else "LOW"
        save_stock(df_stock)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        total = qty * float(row["Selling Price"])
        sale = {
            "Date": now,
            "Item Code": row["Item Code"],
            "Item": row["Item"],
            "Quantity Sold": qty,
            "Selling Price": row["Selling Price"],
            "Total": total,
            "Customer": customer,
            "Issued By": current_user,
        }
        df_sales = pd.concat([df_sales, pd.DataFrame([sale])], ignore_index=True)
        save_sales(df_sales)
        save_client_expense(sale)
        text_report = generate_issue_text_report(sale)
        log_activity(current_user, "Issue Stock",
                     f"{qty} of {row['Item']} ({row['Item Code']}) to {customer}")
        st.success("Stock issued successfully.")
        st.subheader("Delivery Note Preview")
        st.text(text_report)

# ============================================================
# REPORTS
# ============================================================
def low_stock_report(df_stock):
    st.header("⚠️ Low Stock Report")
    low_df = df_stock[df_stock["Stock Status"] == "LOW"]
    if low_df.empty:
        st.success("All items are above reorder level.")
        return
    st.warning("The following items are low on stock:")
    st.dataframe(low_df)


def stock_summary_report(df_stock):
    st.header("📦 Stock Summary")
    st.dataframe(df_stock)
    total_value = df_stock["Total Value"].sum()
    st.info(f"*Total Stock Value:* ${total_value:,.2f}")


def sales_report(df_sales):
    st.header("💰 Sales Report")
    if df_sales.empty:
        st.info("No sales recorded yet.")
        return
    st.dataframe(df_sales)
    total_sales = df_sales["Total"].astype(float).sum()
    st.success(f"*Total Sales:* ${total_sales:,.2f}")


# ============================================================
# BACKUP SYSTEM
# ============================================================
def backup_system():
    st.header("🗄️ Backup System")
    if st.button("Create Backup Now"):
        ensure_dir(BACKUP_DIR)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_folder = f"{BACKUP_DIR}/backup_{timestamp}"
        ensure_dir(backup_folder)
        for file in [STOCK_FILE, SALES_FILE, USERS_FILE, ACTIVITY_LOG_FILE]:
            if os.path.exists(file):
                shutil.copy(file, f"{backup_folder}/{os.path.basename(file)}")
        st.success(f"Backup created: {backup_folder}")


def restore_system():
    st.header("♻️ Restore System")
    backups = [d for d in os.listdir(BACKUP_DIR) if d.startswith("backup_")]
    if not backups:
        st.info("No backups found.")
        return
    choice = st.selectbox("Select Backup to Restore", backups)
    if st.button("Restore Selected Backup"):
        folder = f"{BACKUP_DIR}/{choice}"
        for file in ["stock_export.csv", "sales.csv", "users.json", "activity_log.csv"]:
            src = f"{folder}/{file}"
            if os.path.exists(src):
                shutil.copy(src, file)
        load_stock.clear()
        load_sales.clear()
        st.success("System restored successfully.")


# ============================================================
# IMPORT / EXPORT STOCK
# ============================================================
def import_stock(df_stock, current_user):
    st.header("📥 Import Stock CSV")
    uploaded = st.file_uploader("Upload CSV File", type=["csv"])
    if uploaded:
        new_df = pd.read_csv(uploaded)
        new_df = normalize_stock_df(new_df)
        push_undo_snapshot(df_stock, load_sales())
        save_stock(new_df)
        log_activity(current_user, "Import Stock", "CSV imported")
        st.success("Stock imported successfully.")


def export_stock(df_stock):
    st.header("📤 Export Stock CSV")
    csv = df_stock.to_csv(index=False)
    st.download_button("Download Stock CSV", csv, file_name="stock_export.csv")


# ============================================================
# ACTIVITY LOG VIEWER
# ============================================================
def activity_log_page():
    st.header("📘 Activity Log")
    if not os.path.exists(ACTIVITY_LOG_FILE):
        st.info("No activity recorded yet.")
        return
    df = pd.read_csv(ACTIVITY_LOG_FILE)
    st.dataframe(df)


# ============================================================
# MAIN APP (MENU + ROUTING)
# ============================================================
def main():
    require_login()
    st.sidebar.title("ID Solar Stock System")
    st.sidebar.write(f"Logged in as: *{st.session_state['username']}* ({st.session_state['role']})")

    menu = st.sidebar.radio(
        "Navigation",
        [
            "Dashboard",
            "Add Item",
            "Edit Item",
            "Delete Item",
            "Receive Stock",
            "Transfer Stock",
            "Issue Stock",
            "Low Stock Report",
            "Stock Summary",
            "Sales Report",
            "Import Stock",
            "Export Stock",
            "Backup System",
            "Restore System",
            "Activity Log",
            "User Management",
            "Undo Last Action",
            "Logout"
        ]
    )

    df_stock = load_stock()
    df_sales = load_sales()

    # Ensure required sales columns exist
    required_sales_cols = ["Date", "Item Code", "Item", "Quantity Sold",
                           "Selling Price", "Total", "Customer", "Issued By"]
    for col in required_sales_cols:
        if col not in df_sales.columns:
            df_sales[col] = 0

    user = st.session_state["username"]
    role = st.session_state["role"]

    # ROUTING
    if menu == "Dashboard":
        st.header("📊 Dashboard Overview")
        total_items = len(df_stock)
        total_sales = df_sales["Total"].astype(float).sum()
        st.metric("Total Items", total_items)
        st.metric("Total Sales ($)", f"{total_sales:,.2f}")

    elif menu == "Add Item":
        add_item_page(df_stock, user)
    elif menu == "Edit Item":
        edit_item_page(df_stock, user)
    elif menu == "Delete Item":
        delete_item_page(df_stock, user)
    elif menu == "Receive Stock":
        receive_stock_page(df_stock, user)
    elif menu == "Transfer Stock":
        transfer_stock_page(df_stock, user)
    elif menu == "Issue Stock":
        issue_stock_page(df_stock, df_sales, user)
    elif menu == "Low Stock Report":
        low_stock_report(df_stock)
    elif menu == "Stock Summary":
        stock_summary_report(df_stock)
    elif menu == "Sales Report":
        sales_report(df_sales)
    elif menu == "Import Stock":
        import_stock(df_stock, user)
    elif menu == "Export Stock":
        export_stock(df_stock)
    elif menu == "Backup System":
        backup_system()
    elif menu == "Restore System":
        restore_system()
    elif menu == "Activity Log":
        activity_log_page()
    elif menu == "User Management":
        user_management_page(user, role)
    elif menu == "Undo Last Action":
        if can_undo():
            df_stock, df_sales = perform_undo()
            st.success("Undo performed successfully.")
        else:
            st.info("No action to undo.")
    elif menu == "Logout":
        st.session_state.clear()
        st.success("Logged out successfully.")
        st.rerun()

# ============================================================
# REPORTS
# ============================================================
def low_stock_report(df_stock):
    st.header("⚠️ Low Stock Report")
    low_df = df_stock[df_stock["Stock Status"] == "LOW"]
    if low_df.empty:
        st.success("All items are above reorder level.")
        return
    st.warning("The following items are low on stock:")
    st.dataframe(low_df)


def stock_summary_report(df_stock):
    st.header("📦 Stock Summary")
    st.dataframe(df_stock)
    total_value = df_stock["Total Value"].sum()
    st.info(f"*Total Stock Value:* ${total_value:,.2f}")


def sales_report(df_sales):
    st.header("💰 Sales Report")
    if df_sales.empty:
        st.info("No sales recorded yet.")
        return
    st.dataframe(df_sales)
    total_sales = df_sales["Total"].astype(float).sum()
    st.success(f"*Total Sales:* ${total_sales:,.2f}")


# ============================================================
# BACKUP SYSTEM
# ============================================================
def backup_system():
    st.header("🗄️ Backup System")
    if st.button("Create Backup Now"):
        ensure_dir(BACKUP_DIR)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_folder = f"{BACKUP_DIR}/backup_{timestamp}"
        ensure_dir(backup_folder)
        for file in [STOCK_FILE, SALES_FILE, USERS_FILE, ACTIVITY_LOG_FILE]:
            if os.path.exists(file):
                shutil.copy(file, f"{backup_folder}/{os.path.basename(file)}")
        st.success(f"Backup created: {backup_folder}")


def restore_system():
    st.header("♻️ Restore System")
    backups = [d for d in os.listdir(BACKUP_DIR) if d.startswith("backup_")]
    if not backups:
        st.info("No backups found.")
        return
    choice = st.selectbox("Select Backup to Restore", backups)
    if st.button("Restore Selected Backup"):
        folder = f"{BACKUP_DIR}/{choice}"
        for file in ["stock_export.csv", "sales.csv", "users.json", "activity_log.csv"]:
            src = f"{folder}/{file}"
            if os.path.exists(src):
                shutil.copy(src, file)
        load_stock.clear()
        load_sales.clear()
        st.success("System restored successfully.")


# ============================================================
# IMPORT / EXPORT STOCK
# ============================================================
def import_stock(df_stock, current_user):
    st.header("📥 Import Stock CSV")
    uploaded = st.file_uploader("Upload CSV File", type=["csv"])
    if uploaded:
        new_df = pd.read_csv(uploaded)
        new_df = normalize_stock_df(new_df)
        push_undo_snapshot(df_stock, load_sales())
        save_stock(new_df)
        log_activity(current_user, "Import Stock", "CSV imported")
        st.success("Stock imported successfully.")


def export_stock(df_stock):
    st.header("📤 Export Stock CSV")
    csv = df_stock.to_csv(index=False)
    st.download_button("Download Stock CSV", csv, file_name="stock_export.csv")


# ============================================================
# ACTIVITY LOG VIEWER
# ============================================================
def activity_log_page():
    st.header("📘 Activity Log")
    if not os.path.exists(ACTIVITY_LOG_FILE):
        st.info("No activity recorded yet.")
        return
    df = pd.read_csv(ACTIVITY_LOG_FILE)
    st.dataframe(df)


# ============================================================
# MAIN APP (MENU + ROUTING)
# ============================================================
def main():
    require_login()
    st.sidebar.title("ID Solar Stock System")
    st.sidebar.write(f"Logged in as: *{st.session_state['username']}* ({st.session_state['role']})")

    menu = st.sidebar.radio(
        "Navigation",
        [
            "Dashboard",
            "Add Item",
            "Edit Item",
            "Delete Item",
            "Receive Stock",
            "Transfer Stock",
            "Issue Stock",
            "Low Stock Report",
            "Stock Summary",
            "Sales Report",
            "Import Stock",
            "Export Stock",
            "Backup System",
            "Restore System",
            "Activity Log",
            "User Management",
            "Undo Last Action",
            "Logout"
        ]
    )

    df_stock = load_stock()
    df_sales = load_sales()

    # Ensure required sales columns exist
    required_sales_cols = ["Date", "Item Code", "Item", "Quantity Sold",
                           "Selling Price", "Total", "Customer", "Issued By"]
    for col in required_sales_cols:
        if col not in df_sales.columns:
            df_sales[col] = 0

    user = st.session_state["username"]
    role = st.session_state["role"]

    # ROUTING
    if menu == "Dashboard":
        st.header("📊 Dashboard Overview")
        total_items = len(df_stock)
        total_sales = df_sales["Total"].astype(float).sum()
        st.metric("Total Items", total_items)
        st.metric("Total Sales ($)", f"{total_sales:,.2f}")

    elif menu == "Add Item":
        add_item_page(df_stock, user)
    elif menu == "Edit Item":
        edit_item_page(df_stock, user)
    elif menu == "Delete Item":
        delete_item_page(df_stock, user)
    elif menu == "Receive Stock":
        receive_stock_page(df_stock, user)
    elif menu == "Transfer Stock":
        transfer_stock_page(df_stock, user)
    elif menu == "Issue Stock":
        issue_stock_page(df_stock, df_sales, user)
    elif menu == "Low Stock Report":
        low_stock_report(df_stock)
    elif menu == "Stock Summary":
        stock_summary_report(df_stock)
    elif menu == "Sales Report":
        sales_report(df_sales)
    elif menu == "Import Stock":
        import_stock(df_stock, user)
    elif menu == "Export Stock":
        export_stock(df_stock)
    elif menu == "Backup System":
        backup_system()
    elif menu == "Restore System":
        restore_system()
    elif menu == "Activity Log":
        activity_log_page()
    elif menu == "User Management":
        user_management_page(user, role)
    elif menu == "Undo Last Action":
        if can_undo():
            df_stock, df_sales = perform_undo()
            st.success("Undo performed successfully.")
        else:
            st.info("No action to undo.")
    elif menu == "Logout":
        st.session_state.clear()
        st.success("Logged out successfully.")
        st.rerun()


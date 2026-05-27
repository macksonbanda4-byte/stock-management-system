import streamlit as st
import pandas as pd
import os
from datetime import datetime
import hashlib
import json
import shutil

# ============================================================
# CONFIG
# ============================================================
STOCK_FILE = "stock_export.csv"
SALES_FILE = "sales.csv"
USERS_FILE = "users.json"
ACTIVITY_LOG_FILE = "activity_log.csv"
BACKUP_DIR = "backups"

LOCATIONS = ["Blue container", "Red container", "Shop"]


# ============================================================
# UTILS
# ============================================================
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def ensure_backup_dir():
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)


def log_activity(user, action, details=""):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row = {
        "Timestamp": now,
        "User": user or "Unknown",
        "Action": action,
        "Details": details,
    }
    if os.path.exists(ACTIVITY_LOG_FILE):
        df = pd.read_csv(ACTIVITY_LOG_FILE)
        df.loc[len(df)] = row
    else:
        df = pd.DataFrame([row])
    df.to_csv(ACTIVITY_LOG_FILE, index=False)


# ============================================================
# USER MANAGEMENT (LOCAL JSON)
# ============================================================
def load_users():
    if not os.path.exists(USERS_FILE):
        # create default admin
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
            st.experimental_rerun()
        else:
            st.error("Invalid username or password")


def require_login():
    if "logged_in" not in st.session_state or not st.session_state["logged_in"]:
        login_block()
        st.stop()


# ============================================================
# LOAD & SAVE STOCK / SALES
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

    # Normalize column names from different variants
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

    # Default location = Shop if empty
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
# BACKUP / RESTORE
# ============================================================
def create_backup():
    ensure_backup_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"backup_{timestamp}")
    os.makedirs(backup_path, exist_ok=True)

    for f in [STOCK_FILE, SALES_FILE, USERS_FILE, ACTIVITY_LOG_FILE]:
        if os.path.exists(f):
            shutil.copy(f, os.path.join(backup_path, os.path.basename(f)))

    return backup_path


def list_backups():
    ensure_backup_dir()
    backups = sorted(os.listdir(BACKUP_DIR))
    return backups


def restore_backup(backup_name):
    backup_path = os.path.join(BACKUP_DIR, backup_name)
    if not os.path.exists(backup_path):
        return False

    for fname in os.listdir(backup_path):
        src = os.path.join(backup_path, fname)
        dst = fname
        shutil.copy(src, dst)

    return True


# ============================================================
# UNDO SUPPORT (LAST ACTION SNAPSHOT)
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
    log_activity(st.session_state.get("username"), "Undo", "Reverted to last snapshot")
    return df_stock, df_sales


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
def add_item_page(df_stock, current_user):
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
        if not item or not item_code:
            st.error("Item name and Item Code are required.")
            return

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
        push_undo_snapshot(df_stock, load_sales())
        df_stock.loc[len(df_stock)] = new_row
        save_stock(df_stock)
        log_activity(current_user, "Add Item", f"{item} ({item_code})")
        st.success("Item added successfully.")


# ============================================================
# EDIT ITEM PAGE
# ============================================================
def edit_item_page(df_stock, current_user):
    st.header("Edit Item")

    idx, row = pick_item_with_search(df_stock, "Search Item to Edit")
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
        push_undo_snapshot(df_stock, load_sales())
        df_stock.at[idx, "Category"] = category
        df_stock.at[idx, "Item"] = item
        df_stock.at[idx, "Item Code"] = item_code
        df_stock.at[idx, "Brand"] = brand
        df_stock.at[idx, "Supplier"] = supplier
        df_stock.at[idx, "Location"] = location
        df_stock.at[idx, "Available Stock"] = qty
        df_stock.at[idx, "Reorder Level"] = reorder
        df_stock.at[idx, "Price"] = price
        df_stock.at[idx, "Total Value"] = qty * price

        save_stock(df_stock)
        log_activity(current_user, "Edit Item", f"{item} ({item_code})")
        st.success("Item updated successfully.")


# ============================================================
# DELETE ITEM PAGE
# ============================================================
def delete_item_page(df_stock, current_user):
    st.header("Delete Item")

    idx, row = pick_item_with_search(df_stock, "Search Item to Delete")
    if row is None:
        return

    st.warning(f"Are you sure you want to delete: {row['Item']} ({row['Item Code']})?")
    if st.button("Confirm Delete"):
        push_undo_snapshot(df_stock, load_sales())
        df_stock.drop(idx, inplace=True)
        df_stock.reset_index(drop=True, inplace=True)
        save_stock(df_stock)
        log_activity(current_user, "Delete Item", f"{row['Item']} ({row['Item Code']})")
        st.success("Item deleted successfully.")


# ============================================================
# ADD ITEM PAGE
# ============================================================
def add_item_page(df_stock, current_user):
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
        if not item or not item_code:
            st.error("Item name and Item Code are required.")
            return

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
        push_undo_snapshot(df_stock, load_sales())
        df_stock.loc[len(df_stock)] = new_row
        save_stock(df_stock)
        log_activity(current_user, "Add Item", f"{item} ({item_code})")
        st.success("Item added successfully.")


# ============================================================
# EDIT ITEM PAGE
# ============================================================
def edit_item_page(df_stock, current_user):
    st.header("Edit Item")

    idx, row = pick_item_with_search(df_stock, "Search Item to Edit")
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
        push_undo_snapshot(df_stock, load_sales())
        df_stock.at[idx, "Category"] = category
        df_stock.at[idx, "Item"] = item
        df_stock.at[idx, "Item Code"] = item_code
        df_stock.at[idx, "Brand"] = brand
        df_stock.at[idx, "Supplier"] = supplier
        df_stock.at[idx, "Location"] = location
        df_stock.at[idx, "Available Stock"] = qty
        df_stock.at[idx, "Reorder Level"] = reorder
        df_stock.at[idx, "Price"] = price
        df_stock.at[idx, "Total Value"] = qty * price

        save_stock(df_stock)
        log_activity(current_user, "Edit Item", f"{item} ({item_code})")
        st.success("Item updated successfully.")


# ============================================================
# DELETE ITEM PAGE
# ============================================================
def delete_item_page(df_stock, current_user):
    st.header("Delete Item")

    idx, row = pick_item_with_search(df_stock, "Search Item to Delete")
    if row is None:
        return

    st.warning(f"Are you sure you want to delete: {row['Item']} ({row['Item Code']})?")
    if st.button("Confirm Delete"):
        push_undo_snapshot(df_stock, load_sales())
        df_stock.drop(idx, inplace=True)
        df_stock.reset_index(drop=True, inplace=True)
        save_stock(df_stock)
        log_activity(current_user, "Delete Item", f"{row['Item']} ({row['Item Code']})")
        st.success("Item deleted successfully.")
# ============================================================
# DASHBOARD PAGE
# ============================================================
def dashboard_page(df_stock, df_sales):
    st.header("Dashboard")

    total_items = len(df_stock)
    total_stock = df_stock["Available Stock"].sum()
    total_value = df_stock["Total Value"].sum()

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Items", total_items)
    col2.metric("Total Stock Units", int(total_stock))
    col3.metric("Total Stock Value", f"K{total_value:,.2f}")

    st.subheader("Low Stock Items")
    low_stock = df_stock[df_stock["Available Stock"] <= df_stock["Reorder Level"]]
    st.dataframe(low_stock)


# ============================================================
# MAIN APP
# ============================================================
def main():
    require_login()
    current_user = st.session_state.get("username", "Unknown")
    current_role = st.session_state.get("role", "user")

    st.sidebar.title(f"User: {current_user} ({current_role})")
    if st.sidebar.button("Logout"):
        log_activity(current_user, "Logout", "User logged out")
        st.session_state.clear()
        st.experimental_rerun()

    df_stock = load_stock()
    df_sales = load_sales()

    menu = [
        "Dashboard",
        "Add Item",
        "Edit Item",
        "Delete Item",
        "Receive Stock",
        "Issue Stock",
        "Reports",
        "Import / Export",
        "Backup & Restore",
        "Activity Log",
        "User Management",
    ]
    choice = st.sidebar.selectbox("Menu", menu)

    if can_undo():
        if st.sidebar.button("Undo Last Change"):
            df_stock, df_sales = perform_undo()
            st.experimental_rerun()

    if choice == "Dashboard":
        dashboard_page(df_stock, df_sales)
    elif choice == "Add Item":
        add_item_page(df_stock, current_user)
    elif choice == "Edit Item":
        edit_item_page(df_stock, current_user)
    elif choice == "Delete Item":
        delete_item_page(df_stock, current_user)
    elif choice == "Receive Stock":
        receive_stock_page(df_stock, current_user)
    elif choice == "Issue Stock":
        issue_stock_page(df_stock, df_sales, current_user)
    elif choice == "Reports":
        reports_page(df_stock, df_sales)
    elif choice == "Import / Export":
        import_export_page(df_stock, current_user)
    elif choice == "Backup & Restore":
        backup_restore_page(current_user)
    elif choice == "Activity Log":
        activity_log_page()
    elif choice == "User Management":
        user_management_page(current_user, current_role)


if __name__ == "__main__":
    main()


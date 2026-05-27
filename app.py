import streamlit as st
import pandas as pd
import os
from datetime import datetime
import hashlib
import json
import shutil
from pathlib import Path
from io import BytesIO

# Optional extra packages (install if you want these features):
# pip install python-barcode pillow reportlab

try:
    from barcode import Code128
    from barcode.writer import ImageWriter
    BARCODE_AVAILABLE = True
except ImportError:
    BARCODE_AVAILABLE = False

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

# ============================================================
# CONFIG
# ============================================================
STOCK_FILE = "stock_export.csv"
SALES_FILE = "sales.csv"
USERS_FILE = "users.json"
ACTIVITY_LOG_FILE = "activity_log.csv"
BACKUP_DIR = "backups"
BARCODE_DIR = "barcodes"

LOCATIONS = ["Blue container", "Red container", "Shop"]

# Column normalization map
COLUMN_RENAME_MAP = {
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

REQUIRED_STOCK_COLS = [
    "Category", "Item", "Item Code", "Brand",
    "Available Stock", "Reorder Level",
    "Price", "Total Value", "Stock Status",
    "Location", "Supplier"
]


# ============================================================
# UTILS
# ============================================================
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def ensure_dir(path: str):
    Path(path).mkdir(parents=True, exist_ok=True)


def ensure_backup_dir():
    ensure_dir(BACKUP_DIR)


def ensure_barcode_dir():
    ensure_dir(BARCODE_DIR)


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
        df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    else:
        df = pd.DataFrame([row])
    df.to_csv(ACTIVITY_LOG_FILE, index=False)


def normalize_stock_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.rename(columns=COLUMN_RENAME_MAP, inplace=True)

    for col in REQUIRED_STOCK_COLS:
        if col not in df.columns:
            if col in ["Available Stock", "Reorder Level", "Price", "Total Value"]:
                df[col] = 0
            else:
                df[col] = ""

    df["Location"] = df["Location"].replace("", "Shop")
    df["Available Stock"] = df["Available Stock"].astype(float)
    df["Price"] = df["Price"].astype(float)
    df["Total Value"] = df["Available Stock"] * df["Price"]

    # Simple stock status
    df["Stock Status"] = df.apply(
        lambda r: "LOW" if r["Available Stock"] <= r["Reorder Level"] else "OK",
        axis=1
    )

    return df


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
# LOAD & SAVE STOCK / SALES
# ============================================================
@st.cache_data
def load_stock():
    if not os.path.exists(STOCK_FILE):
        df = pd.DataFrame(columns=REQUIRED_STOCK_COLS)
        return normalize_stock_df(df)
    df = pd.read_csv(STOCK_FILE)
    df = normalize_stock_df(df)
    return df


def save_stock(df):
    df.to_csv(STOCK_FILE, index=False)
    load_stock.clear()  # clear cache


@st.cache_data
def load_sales():
    if not os.path.exists(SALES_FILE):
        cols = ["Date", "Item Code", "Item", "Quantity Sold", "Price", "Total", "Customer", "Issued By"]
        return pd.DataFrame(columns=cols)
    df = pd.read_csv(SALES_FILE)
    # Ensure columns
    for col in ["Date", "Item Code", "Item", "Quantity Sold", "Price", "Total", "Customer", "Issued By"]:
        if col not in df.columns:
            df[col] = "" if col in ["Date", "Item Code", "Item", "Customer", "Issued By"] else 0
    return df


def save_sales(df):
    df.to_csv(SALES_FILE, index=False)
    load_sales.clear()  # clear cache


# ============================================================
# BACKUP / RESTORE
# ============================================================
def create_backup():
    ensure_backup_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = Path(BACKUP_DIR) / f"backup_{timestamp}"
    backup_path.mkdir(parents=True, exist_ok=True)

    for f in [STOCK_FILE, SALES_FILE, USERS_FILE, ACTIVITY_LOG_FILE]:
        if os.path.exists(f):
            shutil.copy(f, backup_path / Path(f).name)

    return str(backup_path)


def list_backups():
    ensure_backup_dir()
    backups = sorted(os.listdir(BACKUP_DIR))
    return backups


def restore_backup(backup_name):
    backup_path = Path(BACKUP_DIR) / backup_name
    if not backup_path.exists():
        return False

    for fname in os.listdir(backup_path):
        src = backup_path / fname
        dst = Path(fname)
        shutil.copy(src, dst)

    load_stock.clear()
    load_sales.clear()
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
    del st.session_state["undo_stock"]
    del st.session_state["undo_sales"]
    return df_stock, df_sales


# ============================================================
# BARCODE GENERATION
# ============================================================
def generate_barcode_image(item_code: str) -> str | None:
    if not BARCODE_AVAILABLE:
        return None
    ensure_barcode_dir()
    filename = Path(BARCODE_DIR) / f"{item_code}.png"
    if not filename.exists():
        barcode = Code128(str(item_code), writer=ImageWriter())
        barcode.save(str(filename.with_suffix("")))
    return str(filename)


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
**Status:** {row['Stock Status']}
"""
    )

    if BARCODE_AVAILABLE:
        barcode_path = generate_barcode_image(row["Item Code"])
        if barcode_path and os.path.exists(barcode_path):
            st.image(barcode_path, caption=f"Barcode for {row['Item Code']}", width=200)

    return idx, row


# ============================================================
# ADD ITEM PAGE
# ============================================================
def add_item_page(df_stock, current_user):
    st.header("➕ Add New Item")

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
            "Stock Status": "OK" if qty > reorder else "LOW",
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
    st.header("✏️ Edit Item")

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
        df_stock.at[idx, "Stock Status"] = "OK" if qty > reorder else "LOW"

        save_stock(df_stock)
        log_activity(current_user, "Edit Item", f"{item} ({item_code})")
        st.success("Item updated successfully.")


# ============================================================
# DELETE ITEM PAGE
# ============================================================
def delete_item_page(df_stock, current_user):
    st.header("🗑️ Delete Item")

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
# RECEIVE STOCK PAGE
# ============================================================
def receive_stock_page(df_stock, current_user):
    st.header("📥 Receive Stock")

    idx, row = pick_item_with_search(df_stock, "Search Item to Receive")
    if row is None:
        return

    qty = st.number_input("Quantity Received", min_value=1, step=1)

    if st.button("Receive"):
        push_undo_snapshot(df_stock, load_sales())
        new_qty = int(row["Available Stock"]) + qty
        df_stock.at[idx, "Available Stock"] = new_qty
        df_stock.at[idx, "Total Value"] = new_qty * float(row["Price"])
        df_stock.at[idx, "Stock Status"] = "OK" if new_qty > int(row["Reorder Level"]) else "LOW"
        save_stock(df_stock)
        log_activity(current_user, "Receive Stock", f"{qty} of {row['Item']} ({row['Item Code']})")
        st.success("Stock received successfully.")


# ============================================================
# TRANSFER STOCK BETWEEN LOCATIONS
# ============================================================
def transfer_stock_page(df_stock, current_user):
    st.header("🔁 Transfer Stock Between Locations")

    idx, row = pick_item_with_search(df_stock, "Select Item to Transfer", allow_location_filter=False)
    if row is None:
        return

    from_location = st.selectbox("From Location", LOCATIONS, index=LOCATIONS.index(row["Location"]) if row["Location"] in LOCATIONS else 2)
    to_location = st.selectbox("To Location", [loc for loc in LOCATIONS if loc != from_location])
    qty = st.number_input("Quantity to Transfer", min_value=1, step=1)

    if st.button("Transfer"):
        same_item = df_stock[df_stock["Item Code"] == row["Item Code"]]

        from_mask = (same_item["Location"] == from_location)
        to_mask = (same_item["Location"] == to_location)

        if not from_mask.any():
            st.error("No stock found at the selected 'From' location.")
            return

        from_idx = same_item[from_mask].index[0]
        from_row = df_stock.loc[from_idx]

        if qty > int(from_row["Available Stock"]):
            st.error("Not enough stock at the 'From' location.")
            return

        push_undo_snapshot(df_stock, load_sales())

        new_from_qty = int(from_row["Available Stock"]) - qty
        df_stock.at[from_idx, "Available Stock"] = new_from_qty
        df_stock.at[from_idx, "Total Value"] = new_from_qty * float(from_row["Price"])
        df_stock.at[from_idx, "Stock Status"] = "OK" if new_from_qty > int(from_row["Reorder Level"]) else "LOW"

        if to_mask.any():
            to_idx = same_item[to_mask].index[0]
            to_row = df_stock.loc[to_idx]
            new_to_qty = int(to_row["Available Stock"]) + qty
            df_stock.at[to_idx, "Available Stock"] = new_to_qty
            df_stock.at[to_idx, "Total Value"] = new_to_qty * float(to_row["Price"])
            df_stock.at[to_idx, "Stock Status"] = "OK" if new_to_qty > int(to_row["Reorder Level"]) else "LOW"
        else:
            new_row = from_row.copy()
            new_row["Location"] = to_location
            new_row["Available Stock"] = qty
            new_row["Total Value"] = qty * float(from_row["Price"])
            new_row["Stock Status"] = "OK" if qty > int(from_row["Reorder Level"]) else "LOW"
            df_stock.loc[len(df_stock)] = new_row

        save_stock(df_stock)
        log_activity(current_user, "Transfer Stock", f"{qty} of {row['Item']} ({row['Item Code']}) from {from_location} to {to_location}")
        st.success("Stock transferred successfully.")


# ============================================================
# ISSUE REPORT GENERATION (TEXT + PDF)
# ============================================================
def generate_issue_text_report(sale_record, report_number):
    report = f"""
id Solar Solutions
Issued Stock Report - {report_number}

-----------------------------------------
Date & Time:     {sale_record['Date']}
Item:            {sale_record['Item']}
Item Code:       {sale_record['Item Code']}
Quantity Issued: {sale_record['Quantity Sold']}
Unit Price:      USD {float(sale_record['Price']):,.2f}
Total Amount:    USD {float(sale_record['Total']):,.2f}
Customer:        {sale_record['Customer']}
Issued By:       {sale_record['Issued By']}
-----------------------------------------

Authorized Signature: ______________________

"""
    return report


def generate_issue_pdf_report(sale_record, report_number) -> bytes | None:
    if not PDF_AVAILABLE:
        return None

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    y = height - 50
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y, "id Solar Solutions")
    y -= 25
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, f"Issued Stock Report - {report_number}")
    y -= 30

    c.setFont("Helvetica", 11)
    lines = [
        f"Date & Time:     {sale_record['Date']}",
        f"Item:            {sale_record['Item']}",
        f"Item Code:       {sale_record['Item Code']}",
        f"Quantity Issued: {sale_record['Quantity Sold']}",
        f"Unit Price:      USD {float(sale_record['Price']):,.2f}",
        f"Total Amount:    USD {float(sale_record['Total']):,.2f}",
        f"Customer:        {sale_record['Customer']}",
        f"Issued By:       {sale_record['Issued By']}",
        "",
        "Authorized Signature: ______________________",
    ]

    for line in lines:
        c.drawString(50, y, line)
        y -= 18

    c.showPage()
    c.save()
    pdf = buffer.getvalue()
    buffer.close()
    return pdf


# ============================================================
# ISSUE STOCK PAGE (SINGLE, IMPROVED VERSION)
# ============================================================
def issue_stock_page(df_stock, df_sales, current_user):
    st.header("📤 Issue Stock")

    idx, row = pick_item_with_search(df_stock, "Search Item to Issue")
    if row is None:
        return

    qty = st.number_input("Quantity to Issue", min_value=1, step=1)
    customer = st.text_input("Customer Name (optional)")

    if st.button("Issue"):
        if qty > int(row["Available Stock"]):
            st.error("Not enough stock available.")
            return

        push_undo_snapshot(df_stock, df_sales)

        new_qty = int(row["Available Stock"]) - qty
        df_stock.at[idx, "Available Stock"] = new_qty
        df_stock.at[idx, "Total Value"] = new_qty * float(row["Price"])
        df_stock.at[idx, "Stock Status"] = "OK" if new_qty > int(row["Reorder Level"]) else "LOW"

        sale = {
            "Date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Item Code": row["Item Code"],
            "Item": row["Item"],
            "Quantity Sold": qty,
            "Price": float(row["Price"]),
            "Total": qty * float(row["Price"]),
            "Customer": customer,
            "Issued By": current_user,
        }
        df_sales.loc[len(df_sales)] = sale

        save_stock(df_stock)
        save_sales(df_sales)
        log_activity(current_user, "Issue Stock", f"{qty} of {row['Item']} ({row['Item Code']})")

        st.success("Stock issued successfully.")

        report_number = f"ISSUE-{len(df_sales):04d}"
        report_text = generate_issue_text_report(sale, report_number)

        st.download_button(
            label="Download Issue Report (Text)",
            data=report_text,
            file_name=f"{report_number}.txt",
            mime="text/plain"
        )

        pdf_bytes = generate_issue_pdf_report(sale, report_number)
        if pdf_bytes:
            st.download_button(
                label="Download Issue Report (PDF)",
                data=pdf_bytes,
                file_name=f"{report_number}.pdf",
                mime="application/pdf"
            )

        st.text_area("Report Preview", report_text, height=300)


# ============================================================
# REPORTS PAGE
# ============================================================
def reports_page(df_stock, df_sales):
    st.header("📊 Reports")

    tab1, tab2, tab3, tab4 = st.tabs(["Stock Summary", "Low Stock", "Sales Summary", "Sales by Item"])

    with tab1:
        cols = ["Location", "Supplier", "Item", "Available Stock", "Total Value", "Stock Status"]
        cols = [c for c in cols if c in df_stock.columns]
        st.dataframe(df_stock[cols])

    with tab2:
        low_stock = df_stock[df_stock["Available Stock"] <= df_stock["Reorder Level"]]
        if low_stock.empty:
            st.success("No items are at or below reorder level.")
        else:
            st.error(f"{len(low_stock)} item(s) are at or below reorder level.")
            st.dataframe(low_stock)

    with tab3:
        st.dataframe(df_sales)

    with tab4:
        if not df_sales.empty:
            sales_group = df_sales.groupby("Item")[["Quantity Sold", "Total"]].sum().reset_index()
            st.dataframe(sales_group)
        else:
            st.info("No sales recorded yet.")


# ============================================================
# IMPORT / EXPORT PAGE
# ============================================================
def import_export_page(df_stock, current_user):
    st.header("📥📤 Import / Export Stock Data")

    st.subheader("Export Current Stock")
    csv_data = df_stock.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Download Stock CSV",
        data=csv_data,
        file_name="stock_export_backup.csv",
        mime="text/csv",
    )

    st.subheader("Import Stock CSV (replace current)")
    uploaded = st.file_uploader("Upload CSV file", type=["csv"])
    if uploaded is not None:
        new_df = pd.read_csv(uploaded)
        new_df = normalize_stock_df(new_df)

        if st.button("Confirm Import (Overwrite Stock)"):
            push_undo_snapshot(df_stock, load_sales())
            save_stock(new_df)
            log_activity(current_user, "Import Stock CSV", "Stock data replaced from CSV")
            st.success("Stock data imported and replaced successfully. Please refresh the app.")


# ============================================================
# BACKUP / RESTORE PAGE
# ============================================================
def backup_restore_page(current_user):
    st.header("💾 Backup & Restore")

    st.subheader("Create Backup")
    if st.button("Create Backup Now"):
        path = create_backup()
        log_activity(current_user, "Create Backup", path)
        st.success(f"Backup created at: {path}")

    st.subheader("Restore Backup")
    backups = list_backups()
    if backups:
        choice = st.selectbox("Select Backup Folder", backups)
        if st.button("Restore Selected Backup"):
            ok = restore_backup(choice)
            if ok:
                log_activity(current_user, "Restore Backup", choice)
                st.success("Backup restored. Please refresh the app.")
            else:
                st.error("Failed to restore backup.")
    else:
        st.info("No backups found.")


# ============================================================
# ACTIVITY LOG PAGE
# ============================================================
def activity_log_page():
    st.header("📜 Activity Log")

    if not os.path.exists(ACTIVITY_LOG_FILE):
        st.info("No activity logged yet.")
        return

    df_log = pd.read_csv(ACTIVITY_LOG_FILE)
    st.dataframe(df_log)


# ============================================================
# USER MANAGEMENT PAGE (ADMIN ONLY)
# ============================================================
def user_management_page(current_user, current_role):
    st.header("👤 User Management")

    if current_role != "admin":
        st.error("Only admin users can manage accounts.")
        return

    users = load_users()
    st.subheader("Existing Users")
    st.write(list(users.keys()))

    st.subheader("Add New User")
    new_username = st.text_input("New Username")
    new_password = st.text_input("New Password", type="password")
    new_role = st.selectbox("Role", ["admin", "user"])

    if st.button("Create User"):
        if not new_username or not new_password:
            st.error("Username and password are required.")
        elif new_username in users:
            st.error("User already exists.")
        else:
            users[new_username] = {
                "password": hash_password(new_password),
                "role": new_role,
            }
            save_users(users)
            log_activity(current_user, "Create User", new_username)
            st.success("User created successfully.")

    st.subheader("Reset User Password")
    reset_user = st.selectbox("Select User", list(users.keys()))
    reset_pass = st.text_input("New Password for Selected User", type="password")

    if st.button("Reset Password"):
        if not reset_pass:
            st.error("New password is required.")
        else:
            users[reset_user]["password"] = hash_password(reset_pass)
            save_users(users)
            log_activity(current_user, "Reset Password", reset_user)
            st.success("Password reset successfully.")


# ============================================================
# DASHBOARD PAGE
# ============================================================
def dashboard_page(df_stock, df_sales):
    st.header("📦 Dashboard")

    total_items = len(df_stock)
    total_stock = df_stock["Available Stock"].sum()
    total_value = df_stock["Total Value"].sum()

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Items", total_items)
    col2.metric("Total Stock Units", int(total_stock))
    col3.metric("Total Stock Value", f"USD {total_value:,.2f}")

    st.subheader("Low Stock Items")
    low_stock = df_stock[df_stock["Available Stock"] <= df_stock["Reorder Level"]]
    if not low_stock.empty:
        st.error(f"⚠ {len(low_stock)} item(s) are at or below reorder level.")
    else:
        st.success("All items are above reorder level.")
    st.dataframe(low_stock)


# ============================================================
# MAIN APP
# ============================================================
def main():
    st.set_page_config(page_title="Stock Management System", layout="wide")

    require_login()
    current_user = st.session_state.get("username", "Unknown")
    current_role = st.session_state.get("role", "user")

    st.sidebar.title(f"User: {current_user} ({current_role})")
    if st.sidebar.button("Logout"):
        log_activity(current_user, "Logout", "User logged out")
        st.session_state.clear()
        st.rerun()

    df_stock = load_stock()
    df_sales = load_sales()

    menu = [
        "Dashboard",
        "Add Item",
        "Edit Item",
        "Delete Item",
        "Receive Stock",
        "Issue Stock",
        "Transfer Stock",
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
            st.rerun()

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

    elif choice == "Transfer Stock":
        transfer_stock_page(df_stock, current_user)

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

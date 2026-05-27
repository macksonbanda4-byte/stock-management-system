import streamlit as st
import pandas as pd
import os
from datetime import datetime
import hashlib
import json
import shutil
from pathlib import Path
from io import BytesIO

# Optional extras
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
# FILE PATHS
# ============================================================
STOCK_FILE = "stock_export.csv"
SALES_FILE = "sales.csv"
USERS_FILE = "users.json"
ACTIVITY_LOG_FILE = "activity_log.csv"
BACKUP_DIR = "backups"
CLIENT_DIR = "backups/clients"   # <--- Your choice (Option B)
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
# FOLDER CREATION
# ============================================================
def ensure_dir(path: str):
    Path(path).mkdir(parents=True, exist_ok=True)

def ensure_all_folders():
    ensure_dir(BACKUP_DIR)
    ensure_dir(CLIENT_DIR)     # <--- Auto-create client folder
    ensure_dir(BARCODE_DIR)


ensure_all_folders()


# ============================================================
# PASSWORD HASHING
# ============================================================
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


# ============================================================
# ACTIVITY LOGGING
# ============================================================
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


# ============================================================
# NORMALIZE STOCK DATAFRAME
# ============================================================
def normalize_stock_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Ensure required columns exist
    for col in REQUIRED_STOCK_COLS:
        if col not in df.columns:
            if col in ["Available Stock", "Reorder Level", "Cost Price", "Selling Price", "Total Value"]:
                df[col] = 0
            else:
                df[col] = ""

    df["Available Stock"] = df["Available Stock"].astype(float)
    df["Cost Price"] = df["Cost Price"].astype(float)
    df["Selling Price"] = df["Selling Price"].astype(float)
    df["Total Value"] = df["Available Stock"] * df["Cost Price"]

    df["Stock Status"] = df.apply(
        lambda r: "LOW" if r["Available Stock"] <= r["Reorder Level"] else "OK",
        axis=1
    )

    df["Location"] = df["Location"].replace("", "Shop")

    return df


# ============================================================
# BARCODE GENERATION
# ============================================================
def generate_barcode_image(item_code: str) -> str | None:
    if not BARCODE_AVAILABLE:
        return None
    filename = Path(BARCODE_DIR) / f"{item_code}.png"
    if not filename.exists():
        barcode = Code128(str(item_code), writer=ImageWriter())
        barcode.save(str(filename.with_suffix("")))
    return str(filename)


# ============================================================
# AUTOMATIC ITEM CODE GENERATOR
# ============================================================
def generate_item_code(df_stock: pd.DataFrame, category: str) -> str:
    """
    Generates item code using:
    - First 3 letters of category (uppercase)
    - Independent sequence per category
    Example:
        Solar Panels → SOL-001
        Solar → SOL-001
        Solar Accessories → SOL-001
    """
    if not category:
        return ""

    prefix = category.strip().upper()[:3]

    # Filter items with same category
    same_cat = df_stock[df_stock["Category"].str.upper() == category.strip().upper()]

    if same_cat.empty:
        return f"{prefix}-001"

    # Extract existing numbers
    numbers = []
    for code in same_cat["Item Code"]:
        try:
            num = int(str(code).split("-")[-1])
            numbers.append(num)
        except:
            pass

    next_num = max(numbers) + 1 if numbers else 1
    return f"{prefix}-{next_num:03d}"

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
    load_stock.clear()  # refresh cache


@st.cache_data
def load_sales():
    if not os.path.exists(SALES_FILE):
        cols = ["Date", "Item Code", "Item", "Quantity Sold",
                "Selling Price", "Total", "Customer", "Issued By"]
        return pd.DataFrame(columns=cols)
    df = pd.read_csv(SALES_FILE)
    for col in ["Date", "Item Code", "Item", "Quantity Sold",
                "Selling Price", "Total", "Customer", "Issued By"]:
        if col not in df.columns:
            df[col] = ""
    return df


def save_sales(df):
    df.to_csv(SALES_FILE, index=False)
    load_sales.clear()


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
    log_activity(st.session_state.get("username"), "Undo", "Reverted last change")
    del st.session_state["undo_stock"]
    del st.session_state["undo_sales"]
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
**Brand:** {row['Brand']}
**Location:** {row['Location']}
**Available Stock:** {row['Available Stock']}
**Reorder Level:** {row['Reorder Level']}
**Cost Price:** {row['Cost Price']}
**Selling Price:** {row['Selling Price']}
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
    brand = st.text_input("Brand")
    supplier = st.text_input("Supplier")
    location = st.selectbox("Location", LOCATIONS, index=2)

    qty = st.number_input("Initial Stock", min_value=0, step=1)
    reorder = st.number_input("Reorder Level", min_value=0, step=1)
    cost_price = st.number_input("Cost Price", min_value=0.0, step=0.1)
    selling_price = st.number_input("Selling Price", min_value=0.0, step=0.1)

    # Auto-generate item code
    if category:
        auto_code = generate_item_code(df_stock, category)
        st.text_input("Generated Item Code", value=auto_code, disabled=True)
    else:
        auto_code = ""

    if st.button("Add Item"):
        if not item or not category:
            st.error("Category and Item Name are required.")
            return

        if not auto_code:
            st.error("Item code could not be generated. Check category.")
            return

        push_undo_snapshot(df_stock, load_sales())

        new_row = {
            "Category": category,
            "Item": item,
            "Item Code": auto_code,
            "Brand": brand,
            "Available Stock": qty,
            "Reorder Level": reorder,
            "Cost Price": cost_price,
            "Selling Price": selling_price,
            "Total Value": qty * cost_price,
            "Stock Status": "OK" if qty > reorder else "LOW",
            "Location": location,
            "Supplier": supplier,
        }

        df_stock.loc[len(df_stock)] = new_row
        save_stock(df_stock)
        log_activity(current_user, "Add Item", f"{item} ({auto_code})")
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
    brand = st.text_input("Brand", value=row["Brand"])
    supplier = st.text_input("Supplier", value=row["Supplier"])

    location = st.selectbox(
        "Location",
        LOCATIONS,
        index=LOCATIONS.index(row["Location"]) if row["Location"] in LOCATIONS else 2
    )

    qty = st.number_input("Available Stock", min_value=0, step=1, value=int(row["Available Stock"]))
    reorder = st.number_input("Reorder Level", min_value=0, step=1, value=int(row["Reorder Level"]))
    cost_price = st.number_input("Cost Price", min_value=0.0, step=0.1, value=float(row["Cost Price"]))
    selling_price = st.number_input("Selling Price", min_value=0.0, step=0.1, value=float(row["Selling Price"]))

    if st.button("Save Changes"):
        push_undo_snapshot(df_stock, load_sales())

        df_stock.at[idx, "Category"] = category
        df_stock.at[idx, "Item"] = item
        df_stock.at[idx, "Brand"] = brand
        df_stock.at[idx, "Supplier"] = supplier
        df_stock.at[idx, "Location"] = location
        df_stock.at[idx, "Available Stock"] = qty
        df_stock.at[idx, "Reorder Level"] = reorder
        df_stock.at[idx, "Cost Price"] = cost_price
        df_stock.at[idx, "Selling Price"] = selling_price
        df_stock.at[idx, "Total Value"] = qty * cost_price
        df_stock.at[idx, "Stock Status"] = "OK" if qty > reorder else "LOW"

        save_stock(df_stock)
        log_activity(current_user, "Edit Item", f"{item} ({row['Item Code']})")
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
        df_stock.at[idx, "Total Value"] = new_qty * float(row["Cost Price"])
        df_stock.at[idx, "Stock Status"] = "OK" if new_qty > int(row["Reorder Level"]) else "LOW"

        save_stock(df_stock)
        log_activity(current_user, "Receive Stock", f"{qty} of {row['Item']} ({row['Item Code']})")
        st.success("Stock received successfully.")


# ============================================================
# TRANSFER STOCK PAGE
# ============================================================
def transfer_stock_page(df_stock, current_user):
    st.header("🔁 Transfer Stock Between Locations")

    idx, row = pick_item_with_search(df_stock, "Select Item to Transfer", allow_location_filter=False)
    if row is None:
        return

    from_location = st.selectbox("From Location", LOCATIONS)
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

        # Deduct from source
        new_from_qty = int(from_row["Available Stock"]) - qty
        df_stock.at[from_idx, "Available Stock"] = new_from_qty
        df_stock.at[from_idx, "Total Value"] = new_from_qty * float(from_row["Cost Price"])
        df_stock.at[from_idx, "Stock Status"] = "OK" if new_from_qty > int(from_row["Reorder Level"]) else "LOW"

        # Add to destination
        if to_mask.any():
            to_idx = same_item[to_mask].index[0]
            to_row = df_stock.loc[to_idx]
            new_to_qty = int(to_row["Available Stock"]) + qty
            df_stock.at[to_idx, "Available Stock"] = new_to_qty
            df_stock.at[to_idx, "Total Value"] = new_to_qty * float(to_row["Cost Price"])
            df_stock.at[to_idx, "Stock Status"] = "OK" if new_to_qty > int(to_row["Reorder Level"]) else "LOW"
        else:
            new_row = from_row.copy()
            new_row["Location"] = to_location
            new_row["Available Stock"] = qty
            new_row["Total Value"] = qty * float(from_row["Cost Price"])
            new_row["Stock Status"] = "OK" if qty > int(from_row["Reorder Level"]) else "LOW"
            df_stock.loc[len(df_stock)] = new_row

        save_stock(df_stock)
        log_activity(current_user, "Transfer Stock",
                     f"{qty} of {row['Item']} ({row['Item Code']}) from {from_location} to {to_location}")
        st.success("Stock transferred successfully.")

# ============================================================
# DELIVERY NOTE (TEXT)
# ============================================================
def generate_issue_text_report(sale):
    lines = [
        "ID SOLAR SOLUTIONS",
        "----------------------------------------",
        f"DATE: {sale['Date']}",
        f"CUSTOMER: {sale['Customer']}",
        f"ISSUED BY: {sale['Issued By']}",
        "----------------------------------------",
        f"ITEM: {sale['Item']}",
        f"ITEM CODE: {sale['Item Code']}",
        f"QUANTITY: {sale['Quantity Sold']}",
        f"SELLING PRICE: {sale['Selling Price']}",
        f"TOTAL: {sale['Total']}",
        "----------------------------------------",
        "SIGNATURE (ISSUED BY): ________________",
        "SIGNATURE (CUSTOMER): ________________",
        "",
        "Thank you for doing business with ID Solar Solutions."
    ]
    return "\n".join(lines)


# ============================================================
# DELIVERY NOTE (PDF)
# ============================================================
def generate_issue_pdf_report(sale):
    if not PDF_AVAILABLE:
        return None

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    y = height - 50
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y, "ID SOLAR SOLUTIONS")
    y -= 30

    c.setFont("Helvetica", 12)
    fields = [
        ("DATE", sale["Date"]),
        ("CUSTOMER", sale["Customer"]),
        ("ISSUED BY", sale["Issued By"]),
        ("ITEM", sale["Item"]),
        ("ITEM CODE", sale["Item Code"]),
        ("QUANTITY", sale["Quantity Sold"]),
        ("SELLING PRICE", sale["Selling Price"]),
        ("TOTAL", sale["Total"]),
    ]

    for label, value in fields:
        c.drawString(50, y, f"{label}: {value}")
        y -= 20

    y -= 20
    c.drawString(50, y, "SIGNATURE (ISSUED BY): ______________________")
    y -= 30
    c.drawString(50, y, "SIGNATURE (CUSTOMER): _______________________")

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer


# ============================================================
# SAVE CLIENT EXPENSE FILE
# ============================================================
def save_client_expense(sale):
    """
    Saves sale to: backups/clients/<client_name>.csv
    Filename format: lowercase_with_underscores
    """
    client_name = sale["Customer"].strip().lower().replace(" ", "_")
    filepath = f"{CLIENT_DIR}/{client_name}.csv"

    ensure_dir(CLIENT_DIR)

    row = pd.DataFrame([{
        "Date": sale["Date"],
        "Item": sale["Item"],
        "Item Code": sale["Item Code"],
        "Quantity": sale["Quantity Sold"],
        "Selling Price": sale["Selling Price"],
        "Total": sale["Total"],
        "Issued By": sale["Issued By"],
    }])

    if os.path.exists(filepath):
        df = pd.read_csv(filepath)
        df = pd.concat([df, row], ignore_index=True)
    else:
        df = row

    df.to_csv(filepath, index=False)


# ============================================================
# ISSUE STOCK PAGE
# ============================================================
def issue_stock_page(df_stock, df_sales, current_user):
    st.header("📤 Issue Stock")

    idx, row = pick_item_with_search(df_stock, "Search Item to Issue")
    if row is None:
        return

    customer = st.text_input("Customer Name (Required)")
    qty = st.number_input("Quantity to Issue", min_value=1, step=1)

    if st.button("Issue Stock"):
        # Customer name required (your choice: A)
        if not customer.strip():
            st.error("Customer name is required before issuing stock.")
            return

        if qty > int(row["Available Stock"]):
            st.error("Not enough stock available.")
            return

        push_undo_snapshot(df_stock, df_sales)

        # Update stock
        new_qty = int(row["Available Stock"]) - qty
        df_stock.at[idx, "Available Stock"] = new_qty
        df_stock.at[idx, "Total Value"] = new_qty * float(row["Cost Price"])
        df_stock.at[idx, "Stock Status"] = "OK" if new_qty > int(row["Reorder Level"]) else "LOW"

        save_stock(df_stock)

        # Create sale record
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

        # Save client expense file
        save_client_expense(sale)

        # Generate delivery note
        text_report = generate_issue_text_report(sale)
        pdf_report = generate_issue_pdf_report(sale)

        log_activity(current_user, "Issue Stock",
                     f"{qty} of {row['Item']} ({row['Item Code']}) to {customer}")

        st.success("Stock issued successfully.")

        st.subheader("Delivery Note Preview")
        st.text(text_report)

        st.download_button(
            "Download Delivery Note (Text)",
            text_report,
            file_name=f"delivery_note_{row['Item Code']}.txt"
        )

        if pdf_report:
            st.download_button(
                "Download Delivery Note (PDF)",
                pdf_report,
                file_name=f"delivery_note_{row['Item Code']}.pdf"
            )
        else:
            st.warning("PDF generation not available (ReportLab not installed).")

# ============================================================
# LOW STOCK REPORT
# ============================================================
def low_stock_report(df_stock):
    st.header("⚠️ Low Stock Report")

    low_df = df_stock[df_stock["Stock Status"] == "LOW"]

    if low_df.empty:
        st.success("All items are above reorder level.")
        return

    st.warning("The following items are low on stock:")
    st.dataframe(low_df[[
        "Category", "Item", "Item Code", "Available Stock",
        "Reorder Level", "Location", "Supplier"
    ]])


# ============================================================
# STOCK SUMMARY REPORT
# ============================================================
def stock_summary_report(df_stock):
    st.header("📦 Stock Summary")

    st.dataframe(df_stock[[
        "Category", "Item", "Item Code", "Brand",
        "Available Stock", "Reorder Level",
        "Cost Price", "Selling Price",
        "Total Value", "Stock Status",
        "Location", "Supplier"
    ]])

    total_value = df_stock["Total Value"].sum()
    st.info(f"**Total Stock Value:** ZMW {total_value:,.2f}")


# ============================================================
# SALES REPORT
# ============================================================
def sales_report(df_sales):
    st.header("💰 Sales Report")

    if df_sales.empty:
        st.info("No sales recorded yet.")
        return

    st.dataframe(df_sales)

    total_sales = df_sales["Total"].astype(float).sum()
    st.success(f"**Total Sales:** ZMW {total_sales:,.2f}")


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

        # Copy main files
        for file in [STOCK_FILE, SALES_FILE, USERS_FILE, ACTIVITY_LOG_FILE]:
            if os.path.exists(file):
                shutil.copy(file, f"{backup_folder}/{os.path.basename(file)}")

        st.success(f"Backup created: {backup_folder}")


# ============================================================
# RESTORE SYSTEM
# ============================================================
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
# IMPORT STOCK
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


# ============================================================
# EXPORT STOCK
# ============================================================
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
    st.sidebar.write(f"Logged in as: **{st.session_state['username']}** ({st.session_state['role']})")

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
    user = st.session_state["username"]
    role = st.session_state["role"]

    # ---------------- Dashboard ----------------
    if menu == "Dashboard":
        st.header("📊 Dashboard Overview")

        total_items = len(df_stock)
        total_value = df_stock["Total Value"].sum()
        low_stock_count = len(df_stock[df_stock["Stock Status"] == "LOW"])
        total_sales = df_sales["Total"].astype(float).sum()

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Stock Items", total_items)
            st.metric("Low Stock Items", low_stock_count)
        with col2:
            st.metric("Total Stock Value (ZMW)", f"{total_value:,.2f}")
            st.metric("Total Sales (ZMW)", f"{total_sales:,.2f}")

        st.subheader("Recent Sales")
        if df_sales.empty:
            st.info("No sales recorded yet.")
        else:
            st.dataframe(df_sales.tail(10))

    # ---------------- Stock Management ----------------
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

    # ---------------- Issue Stock ----------------
    elif menu == "Issue Stock":
        issue_stock_page(df_stock, df_sales, user)

    # ---------------- Reports ----------------
    elif menu == "Low Stock Report":
        low_stock_report(df_stock)

    elif menu == "Stock Summary":
        stock_summary_report(df_stock)

    elif menu == "Sales Report":
        sales_report(df_sales)

    # ---------------- Import / Export ----------------
    elif menu == "Import Stock":
        import_stock(df_stock, user)

    elif menu == "Export Stock":
        export_stock(df_stock)

    # ---------------- Backup / Restore ----------------
    elif menu ==
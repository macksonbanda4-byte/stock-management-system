import streamlit as st
import sqlite3
from datetime import datetime
import hashlib
import pandas as pd
from io import BytesIO

# Optional: PDF delivery note
# pip install reportlab
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

DB_FILE = "stock_system.db"

LOCATIONS = ["Blue container", "Red container", "Shop"]


# ============================================================
# DB UTILITIES
# ============================================================
def get_conn():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    # Users
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            role TEXT NOT NULL
        )
        """
    )

    # Stock
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS stock (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT,
            item TEXT NOT NULL,
            item_code TEXT NOT NULL UNIQUE,
            brand TEXT,
            qty INTEGER NOT NULL DEFAULT 0,
            reorder_level INTEGER NOT NULL DEFAULT 0,
            cost_price REAL NOT NULL DEFAULT 0,
            selling_price REAL NOT NULL DEFAULT 0,
            location TEXT,
            supplier TEXT
        )
        """
    )

    # Sales
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            item_code TEXT,
            item TEXT,
            qty INTEGER,
            selling_price REAL,
            total REAL,
            customer TEXT,
            issued_by TEXT
        )
        """
    )

    # Activity log
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            user TEXT,
            action TEXT,
            details TEXT
        )
        """
    )

    # Default admin
    cur.execute("SELECT COUNT(*) AS c FROM users")
    if cur.fetchone()["c"] == 0:
        cur.execute(
            "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
            ("admin", hash_password("admin123"), "admin"),
        )

    conn.commit()
    conn.close()


# ============================================================
# GENERAL UTILS
# ============================================================
def hash_password(password: str) -> str:
    import hashlib
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def log_activity(user, action, details=""):
    conn = get_conn()
    cur = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur.execute(
        "INSERT INTO activity_log (timestamp, user, action, details) VALUES (?, ?, ?, ?)",
        (now, user or "Unknown", action, details),
    )
    conn.commit()
    conn.close()


# ============================================================
# USER MANAGEMENT
# ============================================================
def authenticate(username, password):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT password FROM users WHERE username = ?", (username,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return False
    return row["password"] == hash_password(password)


def get_user_role(username):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT role FROM users WHERE username = ?", (username,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return "user"
    return row["role"]


def load_users():
    conn = get_conn()
    df = pd.read_sql_query("SELECT username, role FROM users", conn)
    conn.close()
    return df


def create_user(username, password, role, current_user):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM users WHERE username = ?", (username,))
    if cur.fetchone():
        conn.close()
        return False, "User already exists."
    cur.execute(
        "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
        (username, hash_password(password), role),
    )
    conn.commit()
    conn.close()
    log_activity(current_user, "Create User", username)
    return True, "User created successfully."


def reset_user_password(username, new_password, current_user):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET password = ? WHERE username = ?",
        (hash_password(new_password), username),
    )
    conn.commit()
    conn.close()
    log_activity(current_user, "Reset Password", username)
    return True, "Password reset successfully."


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
# STOCK DB OPERATIONS
# ============================================================
def get_stock_df():
    conn = get_conn()
    df = pd.read_sql_query(
        """
        SELECT id, category, item, item_code, brand, qty, reorder_level,
               cost_price, selling_price, location, supplier
        FROM stock
        """,
        conn,
    )
    conn.close()
    return df


def add_stock_item(category, item, item_code, brand, supplier,
                   location, qty, reorder_level, cost_price, selling_price,
                   current_user):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO stock
            (category, item, item_code, brand, qty, reorder_level,
             cost_price, selling_price, location, supplier)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                category, item, item_code, brand, qty, reorder_level,
                cost_price, selling_price, location, supplier,
            ),
        )
        conn.commit()
        log_activity(current_user, "Add Item", f"{item} ({item_code})")
        return True, "Item added successfully."
    except sqlite3.IntegrityError:
        return False, "Item code already exists."
    finally:
        conn.close()


def update_stock_item(item_id, category, item, item_code, brand, supplier,
                      location, qty, reorder_level, cost_price, selling_price,
                      current_user):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE stock
        SET category = ?, item = ?, item_code = ?, brand = ?, supplier = ?,
            location = ?, qty = ?, reorder_level = ?, cost_price = ?, selling_price = ?
        WHERE id = ?
        """,
        (
            category, item, item_code, brand, supplier,
            location, qty, reorder_level, cost_price, selling_price, item_id,
        ),
    )
    conn.commit()
    conn.close()
    log_activity(current_user, "Edit Item", f"{item} ({item_code})")
    return True, "Item updated successfully."


def delete_stock_item(item_id, item, item_code, current_user):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM stock WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    log_activity(current_user, "Delete Item", f"{item} ({item_code})")
    return True, "Item deleted successfully."


def receive_stock(item_id, qty_received, current_user):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT item, item_code, qty FROM stock WHERE id = ?", (item_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return False, "Item not found."

    new_qty = row["qty"] + qty_received
    cur.execute("UPDATE stock SET qty = ? WHERE id = ?", (new_qty, item_id))
    conn.commit()
    conn.close()
    log_activity(current_user, "Receive Stock", f"{qty_received} of {row['item']} ({row['item_code']})")
    return True, "Stock received successfully."


def transfer_stock(item_id, from_location, to_location, qty, current_user):
    conn = get_conn()
    cur = conn.cursor()

    # Source row
    cur.execute(
        "SELECT * FROM stock WHERE id = ? AND location = ?",
        (item_id, from_location),
    )
    src = cur.fetchone()
    if not src:
        conn.close()
        return False, "No stock at the selected 'From' location."

    if qty > src["qty"]:
        conn.close()
        return False, "Not enough stock at the 'From' location."

    # Destination row (same item_code, different location)
    cur.execute(
        "SELECT * FROM stock WHERE item_code = ? AND location = ?",
        (src["item_code"], to_location),
    )
    dst = cur.fetchone()

    # Deduct from source
    new_src_qty = src["qty"] - qty
    cur.execute(
        "UPDATE stock SET qty = ? WHERE id = ?",
        (new_src_qty, src["id"]),
    )

    # Add to destination
    if dst:
        new_dst_qty = dst["qty"] + qty
        cur.execute(
            "UPDATE stock SET qty = ? WHERE id = ?",
            (new_dst_qty, dst["id"]),
        )
    else:
        cur.execute(
            """
            INSERT INTO stock
            (category, item, item_code, brand, qty, reorder_level,
             cost_price, selling_price, location, supplier)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                src["category"], src["item"], src["item_code"], src["brand"],
                qty, src["reorder_level"], src["cost_price"], src["selling_price"],
                to_location, src["supplier"],
            ),
        )

    conn.commit()
    conn.close()
    log_activity(
        current_user,
        "Transfer Stock",
        f"{qty} of {src['item']} ({src['item_code']}) from {from_location} to {to_location}",
    )
    return True, "Stock transferred successfully."


# ============================================================
# SALES / DELIVERY NOTE
# ============================================================
def record_sale(item_id, qty, customer, issued_by):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT * FROM stock WHERE id = ?", (item_id,))
    item = cur.fetchone()
    if not item:
        conn.close()
        return False, "Item not found.", None

    if qty > item["qty"]:
        conn.close()
        return False, "Not enough stock available.", None

    new_qty = item["qty"] - qty
    cur.execute("UPDATE stock SET qty = ? WHERE id = ?", (new_qty, item_id))

    total = qty * item["selling_price"]
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cur.execute(
        """
        INSERT INTO sales
        (date, item_code, item, qty, selling_price, total, customer, issued_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            now, item["item_code"], item["item"], qty,
            item["selling_price"], total, customer, issued_by,
        ),
    )
    sale_id = cur.lastrowid
    conn.commit()
    conn.close()

    log_activity(issued_by, "Issue Stock", f"{qty} of {item['item']} ({item['item_code']})")

    sale_record = {
        "id": sale_id,
        "date": now,
        "item_code": item["item_code"],
        "item": item["item"],
        "qty": qty,
        "selling_price": item["selling_price"],
        "total": total,
        "customer": customer,
        "issued_by": issued_by,
    }
    return True, "Stock issued successfully.", sale_record


def get_sales_df():
    conn = get_conn()
    df = pd.read_sql_query(
        """
        SELECT id, date, item_code, item, qty, selling_price, total, customer, issued_by
        FROM sales
        ORDER BY date DESC
        """,
        conn,
    )
    conn.close()
    return df


def generate_delivery_note_text(sale, note_number):
    return f"""
id Solar Solutions
Delivery Note - {note_number}

-----------------------------------------
Date & Time:     {sale['date']}
Item:            {sale['item']}
Item Code:       {sale['item_code']}
Quantity:        {sale['qty']}
Unit Price:      USD {sale['selling_price']:,.2f}
Total Amount:    USD {sale['total']:,.2f}
Customer:        {sale['customer']}
Issued By:       {sale['issued_by']}
-----------------------------------------

Customer Signature: ______________________
Authorized Signature: ______________________

"""


def generate_delivery_note_pdf(sale, note_number) -> bytes | None:
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
    c.drawString(50, y, f"Delivery Note - {note_number}")
    y -= 30

    c.setFont("Helvetica", 11)
    lines = [
        f"Date & Time:     {sale['date']}",
        f"Item:            {sale['item']}",
        f"Item Code:       {sale['item_code']}",
        f"Quantity:        {sale['qty']}",
        f"Unit Price:      USD {sale['selling_price']:,.2f}",
        f"Total Amount:    USD {sale['total']:,.2f}",
        f"Customer:        {sale['customer']}",
        f"Issued By:       {sale['issued_by']}",
        "",
        "Customer Signature: ______________________",
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
# UI HELPERS
# ============================================================
def pick_item_with_search(df, title="Select Item"):
    st.subheader(title)

    search = st.text_input("Search by Item Code, Name, or Brand")
    filtered = df.copy()

    if search:
        filtered = filtered[
            filtered["item_code"].astype(str).str.contains(search, case=False, na=False)
            | filtered["item"].astype(str).str.contains(search, case=False, na=False)
            | filtered["brand"].astype(str).str.contains(search, case=False, na=False)
        ]

    loc_choice = st.selectbox("Filter by Location", ["All"] + LOCATIONS)
    if loc_choice != "All":
        filtered = filtered[filtered["location"] == loc_choice]

    if filtered.empty:
        st.warning("No matching items found.")
        return None, None

    display_series = filtered["item"] + " | " + filtered["item_code"].astype(str)
    choice = st.selectbox("Item list", display_series)

    idx = display_series[display_series == choice].index[0]
    row = filtered.loc[idx]

    st.info(
        f"""
**Item:** {row['item']}
**Brand:** {row.get('brand','N/A')}
**Location:** {row.get('location','N/A')}
**Available Stock:** {row['qty']}
**Reorder Level:** {row['reorder_level']}
**Cost Price:** {row['cost_price']}
**Selling Price:** {row['selling_price']}
"""
    )

    return int(row["id"]), row


# ============================================================
# PAGES
# ============================================================
def add_item_page(current_user):
    st.header("➕ Add New Item")

    category = st.text_input("Category")
    item = st.text_input("Item Name")
    item_code = st.text_input("Item Code")
    brand = st.text_input("Brand")
    supplier = st.text_input("Supplier")
    location = st.selectbox("Location", LOCATIONS, index=2)

    qty = st.number_input("Initial Stock", min_value=0, step=1)
    reorder = st.number_input("Reorder Level", min_value=0, step=1)
    cost_price = st.number_input("Cost Price", min_value=0.0, step=0.1)
    selling_price = st.number_input("Selling Price", min_value=0.0, step=0.1)

    if st.button("Add Item"):
        if not item or not item_code:
            st.error("Item name and Item Code are required.")
            return
        ok, msg = add_stock_item(
            category, item, item_code, brand, supplier,
            location, qty, reorder, cost_price, selling_price,
            current_user,
        )
        if ok:
            st.success(msg)
        else:
            st.error(msg)


def edit_item_page(current_user):
    st.header("✏️ Edit Item")

    df_stock = get_stock_df()
    if df_stock.empty:
        st.info("No items in stock.")
        return

    item_id, row = pick_item_with_search(df_stock, "Search Item to Edit")
    if row is None:
        return

    category = st.text_input("Category", value=row["category"])
    item = st.text_input("Item Name", value=row["item"])
    item_code = st.text_input("Item Code", value=row["item_code"])
    brand = st.text_input("Brand", value=row["brand"])
    supplier = st.text_input("Supplier", value=row["supplier"])

    location = st.selectbox(
        "Location",
        LOCATIONS,
        index=LOCATIONS.index(row["location"]) if row["location"] in LOCATIONS else 2
    )

    qty = st.number_input("Available Stock", min_value=0, step=1, value=int(row["qty"]))
    reorder = st.number_input("Reorder Level", min_value=0, step=1, value=int(row["reorder_level"]))
    cost_price = st.number_input("Cost Price", min_value=0.0, step=0.1, value=float(row["cost_price"]))
    selling_price = st.number_input("Selling Price", min_value=0.0, step=0.1, value=float(row["selling_price"]))

    if st.button("Save Changes"):
        ok, msg = update_stock_item(
            item_id, category, item, item_code, brand, supplier,
            location, qty, reorder, cost_price, selling_price,
            current_user,
        )
        if ok:
            st.success(msg)
        else:
            st.error(msg)


def delete_item_page(current_user):
    st.header("🗑️ Delete Item")

    df_stock = get_stock_df()
    if df_stock.empty:
        st.info("No items in stock.")
        return

    item_id, row = pick_item_with_search(df_stock, "Search Item to Delete")
    if row is None:
        return

    st.warning(f"Are you sure you want to delete: {row['item']} ({row['item_code']})?")
    if st.button("Confirm Delete"):
        ok, msg = delete_stock_item(item_id, row["item"], row["item_code"], current_user)
        if ok:
            st.success(msg)
        else:
            st.error(msg)


def receive_stock_page(current_user):
    st.header("📥 Receive Stock")

    df_stock = get_stock_df()
    if df_stock.empty:
        st.info("No items in stock.")
        return

    item_id, row = pick_item_with_search(df_stock, "Search Item to Receive")
    if row is None:
        return

    qty = st.number_input("Quantity Received", min_value=1, step=1)

    if st.button("Receive"):
        ok, msg = receive_stock(item_id, qty, current_user)
        if ok:
            st.success(msg)
        else:
            st.error(msg)


def transfer_stock_page(current_user):
    st.header("🔁 Transfer Stock Between Locations")

    df_stock = get_stock_df()
    if df_stock.empty:
        st.info("No items in stock.")
        return

    item_id, row = pick_item_with_search(df_stock, "Select Item to Transfer")
    if row is None:
        return

    from_location = st.selectbox("From Location", LOCATIONS, index=LOCATIONS.index(row["location"]) if row["location"] in LOCATIONS else 2)
    to_location = st.selectbox("To Location", [loc for loc in LOCATIONS if loc != from_location])
    qty = st.number_input("Quantity to Transfer", min_value=1, step=1)

    if st.button("Transfer"):
        ok, msg = transfer_stock(item_id, from_location, to_location, qty, current_user)
        if ok:
            st.success(msg)
        else:
            st.error(msg)


def issue_stock_page(current_user):
    st.header("📤 Issue Stock (with Delivery Note)")

    df_stock = get_stock_df()
    if df_stock.empty:
        st.info("No items in stock.")
        return

    item_id, row = pick_item_with_search(df_stock, "Search Item to Issue")
    if row is None:
        return

    qty = st.number_input("Quantity to Issue", min_value=1, step=1)
    customer = st.text_input("Customer Name (optional)")

    if st.button("Issue"):
        ok, msg, sale = record_sale(item_id, qty, customer, current_user)
        if not ok:
            st.error(msg)
            return

        st.success(msg)

        note_number = f"DN-{sale['id']:04d}"
        note_text = generate_delivery_note_text(sale, note_number)

        st.download_button(
            label="Download Delivery Note (Text)",
            data=note_text,
            file_name=f"{note_number}.txt",
            mime="text/plain",
        )

        pdf_bytes = generate_delivery_note_pdf(sale, note_number)
        if pdf_bytes:
            st.download_button(
                label="Download Delivery Note (PDF)",
                data=pdf_bytes,
                file_name=f"{note_number}.pdf",
                mime="application/pdf",
            )

        st.text_area("Delivery Note Preview", note_text, height=300)


def reports_page():
    st.header("📊 Reports")

    df_stock = get_stock_df()
    df_sales = get_sales_df()

    tab1, tab2, tab3, tab4 = st.tabs(["Stock Summary", "Low Stock", "Sales Summary", "Sales by Item"])

    with tab1:
        if df_stock.empty:
            st.info("No stock data.")
        else:
            df_stock_display = df_stock.copy()
            df_stock_display["Total Value (Cost)"] = df_stock_display["qty"] * df_stock_display["cost_price"]
            df_stock_display["Total Value (Selling)"] = df_stock_display["qty"] * df_stock_display["selling_price"]
            st.dataframe(df_stock_display)

    with tab2:
        if df_stock.empty:
            st.info("No stock data.")
        else:
            low_stock = df_stock[df_stock["qty"] <= df_stock["reorder_level"]]
            if low_stock.empty:
                st.success("No items are below or at reorder level.")
            else:
                st.error(f"{len(low_stock)} item(s) are at or below reorder level.")
                st.dataframe(low_stock)

    with tab3:
        if df_sales.empty:
            st.info("No sales recorded yet.")
        else:
            st.dataframe(df_sales)

    with tab4:
        if df_sales.empty:
            st.info("No sales recorded yet.")
        else:
            sales_group = df_sales.groupby("item")[["qty", "total"]].sum().reset_index()
            st.dataframe(sales_group)


def activity_log_page():
    st.header("📜 Activity Log")
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM activity_log ORDER BY timestamp DESC", conn)
    conn.close()
    if df.empty:
        st.info("No activity logged yet.")
    else:
        st.dataframe(df)


def user_management_page(current_user, current_role):
    st.header("👤 User Management")

    if current_role != "admin":
        st.error("Only admin users can manage accounts.")
        return

    users_df = load_users()
    st.subheader("Existing Users")
    st.dataframe(users_df)

    st.subheader("Add New User")
    new_username = st.text_input("New Username")
    new_password = st.text_input("New Password", type="password")
    new_role = st.selectbox("Role", ["admin", "user"])

    if st.button("Create User"):
        if not new_username or not new_password:
            st.error("Username and password are required.")
        else:
            ok, msg = create_user(new_username, new_password, new_role, current_user)
            if ok:
                st.success(msg)
            else:
                st.error(msg)

    st.subheader("Reset User Password")
    if not users_df.empty:
        reset_user = st.selectbox("Select User", users_df["username"].tolist())
        reset_pass = st.text_input("New Password for Selected User", type="password")

        if st.button("Reset Password"):
            if not reset_pass:
                st.error("New password is required.")
            else:
                ok, msg = reset_user_password(reset_user, reset_pass, current_user)
                if ok:
                    st.success(msg)
                else:
                    st.error(msg)


def dashboard_page():
    st.header("📦 Dashboard")

    df_stock = get_stock_df()
    df_sales = get_sales_df()

    total_items = len(df_stock)
    total_stock = int(df_stock["qty"].sum()) if not df_stock.empty else 0
    total_value_selling = float((df_stock["qty"] * df_stock["selling_price"]).sum()) if not df_stock.empty else 0

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Items", total_items)
    col2.metric("Total Stock Units", total_stock)
    col3.metric("Total Stock Value (Selling)", f"USD {total_value_selling:,.2f}")

    if not df_stock.empty:
        low_stock = df_stock[df_stock["qty"] <= df_stock["reorder_level"]]
        if not low_stock.empty:
            st.error(f"⚠ {len(low_stock)} item(s) are at or below reorder level.")
        else:
            st.success("All items are above reorder level.")

        st.subheader("Low Stock Items")
        st.dataframe(low_stock)
    else:
        st.info("No stock data.")


# ============================================================
# MAIN
# ============================================================
def main():
    st.set_page_config(page_title="Stock Management System (SQLite v2)", layout="wide")
    init_db()

    require_login()
    current_user = st.session_state.get("username", "Unknown")
    current_role = st.session_state.get("role", "user")

    st.sidebar.title(f"User: {current_user} ({current_role})")
    if st.sidebar.button("Logout"):
        log_activity(current_user, "Logout", "User logged out")
        st.session_state.clear()
        st.rerun()

    menu = [
        "Dashboard",
        "Add Item",
        "Edit Item",
        "Delete Item",
        "Receive Stock",
        "Issue Stock",
        "Transfer Stock",
        "Reports",
        "Activity Log",
    ]
    if current_role == "admin":
        menu.append("User Management")

    choice = st.sidebar.selectbox("Menu", menu)

    if choice == "Dashboard":
        dashboard_page()
    elif choice == "Add Item":
        add_item_page(current_user)
    elif choice == "Edit Item":
        edit_item_page(current_user)
    elif choice == "Delete Item":
        delete_item_page(current_user)
    elif choice == "Receive Stock":
        receive_stock_page(current_user)
    elif choice == "Issue Stock":
        issue_stock_page(current_user)
    elif choice == "Transfer Stock":
        transfer_stock_page(current_user)
    elif choice == "Reports":
        reports_page()
    elif choice == "Activity Log":
        activity_log_page()
    elif choice == "User Management":
        user_management_page(current_user, current_role)


if __name__ == "__main__":
    main()

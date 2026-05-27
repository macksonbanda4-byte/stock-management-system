import streamlit as st
import pandas as pd
from datetime import datetime
import os
import smtplib

# ============================================================
#  FILE PATHS
# ============================================================
USERS_FILE = "users.csv"
STOCK_FILE = "stock_clean.csv"
SALES_FILE = "sales.csv"
ACTIVITY_FILE = "activity_log.csv"
PO_FILE = "purchase_orders.csv"
BACKUP_DIR = "backups"

# ============================================================
#  ALERTS (SMS / Email – SIMULATED)
# ============================================================
TEST_MODE = True  # keep True for Streamlit Cloud safety


def send_sms(phone, message):
    # Twilio removed to avoid ModuleNotFoundError on Streamlit Cloud
    print(f"[SMS SIMULATED] To: {phone} | Message: {message}")


def send_email(email, subject, message):
    if TEST_MODE:
        print(f"[EMAIL SIMULATED] To: {email} | Subject: {subject} | Message: {message}")
    else:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(os.getenv("EMAIL_USER"), os.getenv("EMAIL_PASS"))
        server.sendmail(os.getenv("EMAIL_USER"), email, f"Subject:{subject}\n\n{message}")
        server.quit()


def notify_users(action_message):
    users = load_users()
    for _, row in users.iterrows():
        if row.get("phone_number"):
            send_sms(row["phone_number"], action_message)
        if row.get("email"):
            send_email(row["email"], "Stock Alert", action_message)


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
    return ensure_file(
        USERS_FILE,
        ["username", "password", "role", "phone_number", "email", "location"],
    )


def save_users(df: pd.DataFrame) -> None:
    df.to_csv(USERS_FILE, index=False)


def load_stock() -> pd.DataFrame:
    cols = [
        "Category",
        "Item",
        "Item Code",
        "Brand",
        "Location",
        "Supplier",
        "Available Stock",
        "Reorder Level",
        "Cost Price",
        "Price",
        "Total Value",
        "Stock Status",
    ]
    return ensure_file(STOCK_FILE, cols)


def save_stock(df: pd.DataFrame) -> None:
    df.to_csv(STOCK_FILE, index=False)


def load_sales() -> pd.DataFrame:
    cols = [
        "Item",
        "Item Code",
        "Location",
        "Quantity Sold",
        "Selling Price",
        "Cost Price",
        "Total Sale",
        "Total Cost",
        "Profit",
        "Date",
    ]
    return ensure_file(SALES_FILE, cols)


def save_sales(df: pd.DataFrame) -> None:
    df.to_csv(SALES_FILE, index=False)


def load_activity() -> pd.DataFrame:
    cols = ["timestamp", "user", "action", "details"]
    return ensure_file(ACTIVITY_FILE, cols)


def save_activity(df: pd.DataFrame) -> None:
    df.to_csv(ACTIVITY_FILE, index=False)


# ============================================================
#  AUTO ITEM CODE GENERATOR
# ============================================================
def generate_category_barcode(category, df):
    prefix = str(category)[:3].upper()
    existing = df[df["Category"].astype(str).str.lower() == str(category).lower()]
    next_num = len(existing) + 1
    return f"{prefix}-{next_num:05d}"


# ============================================================
#  ROLE PROTECTION
# ============================================================
def require_admin():
    if st.session_state.get("role") != "admin":
        st.error("You do not have permission to perform this action.")
        st.stop()


# ============================================================
#  ACTIVITY LOGGING
# ============================================================
def log_activity(user: str, action: str, details: str = "") -> None:
    df = load_activity()
    df.loc[len(df)] = [
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        user,
        action,
        details,
    ]
    save_activity(df)


# ============================================================
#  UNDO STACK
# ============================================================
def init_undo_stack():
    if "undo_stack" not in st.session_state:
        st.session_state["undo_stack"] = []


def push_undo(action_type: str, payload: dict):
    init_undo_stack()
    st.session_state["undo_stack"].append({"type": action_type, "payload": payload})


# ============================================================
#  LOGIN PAGE
# ============================================================
def login_page():
    st.header("🔐 Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        # Master override
        if username.lower() == "master" and password.lower() == "letmein":
            st.session_state["logged_in"] = True
            st.session_state["username"] = "master"
            st.session_state["role"] = "admin"
            log_activity("master", "login", "Master login")
            st.success("Master login successful!")
            st.stop()

        users = load_users()
        match = users[
            (users["username"].str.lower() == username.lower())
            & (users["password"].str.lower() == password.lower())
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
    require_admin()
    st.header("👥 Manage Users")
    users = load_users()

    new_user = st.text_input("New Username")
    new_pass = st.text_input("New Password", type="password")
    new_role = st.selectbox("Role", ["admin", "staff", "viewer"])
    phone = st.text_input("Phone Number")
    email = st.text_input("Email Address")
    location = st.text_input("Location")

    if st.button("Add User"):
        if not new_user or not new_pass:
            st.error("Username and password are required.")
        else:
            users.loc[len(users)] = [new_user, new_pass, new_role, phone, email, location]
            save_users(users)
            log_activity(
                st.session_state["username"], "add_user", f"Added {new_user}"
            )
            st.success("User added successfully!")

    st.subheader("Existing Users")
    st.dataframe(users)


# ============================================================
#  DASHBOARD (QUICK ISSUE BY BARCODE)
# ============================================================
def dashboard_page(df: pd.DataFrame, sales_df: pd.DataFrame):
    st.header("📊 Dashboard")

    total_items = len(df)
    total_stock = df["Available Stock"].sum() if not df.empty else 0
    total_value = df["Total Value"].sum() if not df.empty else 0.0

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Items", f"{total_items}")
    c2.metric("Total Stock Units", f"{total_stock}")
    c3.metric("Stock Value", f"${total_value:,.2f}")

    low_stock = df[df["Available Stock"] <= df["Reorder Level"]]
    if not low_stock.empty:
        st.warning("⚠️ Low stock items detected:")
        st.dataframe(low_stock[["Item", "Location", "Supplier", "Available Stock", "Reorder Level"]])

    st.subheader("Quick Issue by Barcode / Item Code")
    scan_code = st.text_input("Scan Barcode / Enter Item Code")
    if scan_code:
        match = df[df["Item Code"].astype(str) == scan_code]
        if match.empty:
            st.error("No item found.")
        else:
            item = match.iloc[0]
            st.success(f"Item Found: {item['Item']} ({item['Location']})")

            qty_issue = st.number_input("Quantity to Issue", min_value=1, step=1)
            if st.button("Issue Stock (Dashboard)"):
                if qty_issue > item["Available Stock"]:
                    st.error("Not enough stock.")
                else:
                    idx = match.index[0]
                    before_row = df.loc[idx].to_dict()

                    df.at[idx, "Available Stock"] -= qty_issue
                    df.at[idx, "Total Value"] = (
                        df.at[idx, "Available Stock"] * df.at[idx, "Cost Price"]
                    )
                    df.at[idx, "Stock Status"] = (
                        "Low Stock"
                        if df.at[idx, "Available Stock"] <= df.at[idx, "Reorder Level"]
                        else "In Stock"
                    )
                    save_stock(df)

                    sale = {
                        "Item": item["Item"],
                        "Item Code": item["Item Code"],
                        "Location": item["Location"],
                        "Quantity Sold": qty_issue,
                        "Selling Price": item["Price"],
                        "Cost Price": item["Cost Price"],
                        "Total Sale": qty_issue * item["Price"],
                        "Total Cost": qty_issue * item["Cost Price"],
                        "Profit": qty_issue * (item["Price"] - item["Cost Price"]),
                        "Date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    }
                    sales_df = pd.concat(
                        [sales_df, pd.DataFrame([sale])], ignore_index=True
                    )
                    save_sales(sales_df)

                    push_undo(
                        "issue_stock",
                        {
                            "stock_index": int(idx),
                            "before_row": before_row,
                            "sale_row": sale,
                        },
                    )

                    log_activity(
                        st.session_state["username"],
                        "issue_stock_dashboard",
                        f"Issued {qty_issue} of {item['Item']} via dashboard",
                    )

                    if df.at[idx, "Available Stock"] <= df.at[idx, "Reorder Level"]:
                        notify_users(
                            f"Low stock alert: {item['Item']} at {item['Location']} (Available: {df.at[idx, 'Available Stock']})"
                        )

                    st.success("Issued successfully.")


# ============================================================
#  ADD ITEM
# ============================================================
def add_item_page(df: pd.DataFrame):
    st.header("➕ Add New Item")

    category = st.text_input("Category")
    item_name = st.text_input("Item Name")
    brand = st.text_input("Brand")
    location = st.text_input("Location")
    supplier = st.text_input("Supplier")
    reorder_level = st.number_input("Reorder Level", min_value=0, step=1, value=10)
    cost_price = st.number_input("Cost Price", min_value=0.0, step=0.01, value=0.0)
    price = st.number_input("Selling Price", min_value=0.0, step=0.01, value=0.0)
    initial_stock = st.number_input(
        "Initial Stock Quantity", min_value=0, step=1, value=0
    )

    if st.button("Add Item"):
        if not category or not item_name or not location:
            st.error("Category, Item Name and Location are required.")
            return

        item_code = generate_category_barcode(category, df)
        total_value = initial_stock * cost_price
        stock_status = (
            "Low Stock" if initial_stock <= reorder_level else "In Stock"
        )

        new_row = {
            "Category": category,
            "Item": item_name,
            "Item Code": item_code,
            "Brand": brand,
            "Location": location,
            "Supplier": supplier,
            "Available Stock": initial_stock,
            "Reorder Level": reorder_level,
            "Cost Price": cost_price,
            "Price": price,
            "Total Value": total_value,
            "Stock Status": stock_status,
        }

        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        save_stock(df)

        push_undo("add_item", {"item_code": item_code})

        log_activity(
            st.session_state["username"],
            "add_item",
            f"Added item {item_name} ({item_code})",
        )

        if initial_stock <= reorder_level:
            notify_users(
                f"New item added with low stock: {item_name} at {location} (Stock: {initial_stock})"
            )

        st.success(f"Item added successfully with code {item_code}.")


# ============================================================
#  RECEIVE STOCK
# ============================================================
def receive_stock_page(df: pd.DataFrame):
    st.header("📦 Receive Stock")

    if df.empty:
        st.info("No items in stock database yet.")
        return

    item_list = df["Item"] + " | " + df["Item Code"].astype(str)
    choice = st.selectbox("Select Item", item_list)
    idx = item_list[item_list == choice].index[0]
    row = df.loc[idx]

    st.write(f"**Selected:** {row['Item']} ({row['Item Code']}) at {row['Location']}")
    qty = st.number_input("Quantity Received", min_value=1, step=1)

    if st.button("Receive"):
        before_row = row.to_dict()

        df.at[idx, "Available Stock"] += qty
        df.at[idx, "Total Value"] = df.at[idx, "Available Stock"] * df.at[idx, "Cost Price"]
        df.at[idx, "Stock Status"] = (
            "Low Stock"
            if df.at[idx, "Available Stock"] <= df.at[idx, "Reorder Level"]
            else "In Stock"
        )
        save_stock(df)

        push_undo(
            "receive_stock",
            {"stock_index": int(idx), "before_row": before_row},
        )

        log_activity(
            st.session_state["username"],
            "receive_stock",
            f"Received {qty} of {row['Item']} ({row['Item Code']})",
        )

        st.success("Stock updated successfully.")


# ============================================================
#  ISSUE STOCK (DETAILED PAGE)
# ============================================================
def issue_stock_page(df: pd.DataFrame, sales_df: pd.DataFrame):
    st.header("📤 Issue Stock")

    if df.empty:
        st.info("No items in stock database yet.")
        return

    item_list = df["Item"] + " | " + df["Item Code"].astype(str)
    choice = st.selectbox("Select Item", item_list)
    idx = item_list[item_list == choice].index[0]
    row = df.loc[idx]

    st.write(f"**Selected:** {row['Item']} ({row['Item Code']}) at {row['Location']}")
    st.write(f"Available: {row['Available Stock']} | Reorder Level: {row['Reorder Level']}")
    qty = st.number_input("Quantity to Issue", min_value=1, step=1)

    if st.button("Issue"):
        if qty > row["Available Stock"]:
            st.error("Not enough stock.")
            return

        before_row = row.to_dict()

        df.at[idx, "Available Stock"] -= qty
        df.at[idx, "Total Value"] = df.at[idx, "Available Stock"] * df.at[idx, "Cost Price"]
        df.at[idx, "Stock Status"] = (
            "Low Stock"
            if df.at[idx, "Available Stock"] <= df.at[idx, "Reorder Level"]
            else "In Stock"
        )
        save_stock(df)

        sale = {
            "Item": row["Item"],
            "Item Code": row["Item Code"],
            "Location": row["Location"],
            "Quantity Sold": qty,
            "Selling Price": row["Price"],
            "Cost Price": row["Cost Price"],
            "Total Sale": qty * row["Price"],
            "Total Cost": qty * row["Cost Price"],
            "Profit": qty * (row["Price"] - row["Cost Price"]),
            "Date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        sales_df = pd.concat([sales_df, pd.DataFrame([sale])], ignore_index=True)
        save_sales(sales_df)

        push_undo(
            "issue_stock",
            {"stock_index": int(idx), "before_row": before_row, "sale_row": sale},
        )

        log_activity(
            st.session_state["username"],
            "issue_stock",
            f"Issued {qty} of {row['Item']} ({row['Item Code']})",
        )

        if df.at[idx, "Available Stock"] <= df.at[idx, "Reorder Level"]:
            notify_users(
                f"Low stock alert: {row['Item']} at {row['Location']} (Available: {df.at[idx, 'Available Stock']})"
            )

        st.success("Stock issued successfully.")


# ============================================================
#  EDIT ITEM
# ============================================================
def edit_item_page(df: pd.DataFrame):
    st.header("✏️ Edit Item")

    if df.empty:
        st.info("No items to edit.")
        return

    item_list = df["Item"] + " | " + df["Item Code"].astype(str)
    choice = st.selectbox("Select Item to Edit", item_list)
    idx = item_list[item_list == choice].index[0]
    row = df.loc[idx]

    category = st.text_input("Category", value=row["Category"])
    item_name = st.text_input("Item Name", value=row["Item"])
    brand = st.text_input("Brand", value=row["Brand"])
    location = st.text_input("Location", value=row["Location"])
    supplier = st.text_input("Supplier", value=row["Supplier"])
    reorder_level = st.number_input(
        "Reorder Level", min_value=0, step=1, value=int(row["Reorder Level"])
    )
    cost_price = st.number_input(
        "Cost Price", min_value=0.0, step=0.01, value=float(row["Cost Price"])
    )
    price = st.number_input(
        "Selling Price", min_value=0.0, step=0.01, value=float(row["Price"])
    )
    available_stock = st.number_input(
        "Available Stock", min_value=0, step=1, value=int(row["Available Stock"])
    )

    if st.button("Save Changes"):
        before_row = row.to_dict()

        df.at[idx, "Category"] = category
        df.at[idx, "Item"] = item_name
        df.at[idx, "Brand"] = brand
        df.at[idx, "Location"] = location
        df.at[idx, "Supplier"] = supplier
        df.at[idx, "Reorder Level"] = reorder_level
        df.at[idx, "Cost Price"] = cost_price
        df.at[idx, "Price"] = price
        df.at[idx, "Available Stock"] = available_stock
        df.at[idx, "Total Value"] = available_stock * cost_price
        df.at[idx, "Stock Status"] = (
            "Low Stock" if available_stock <= reorder_level else "In Stock"
        )

        save_stock(df)

        push_undo(
            "edit_item",
            {"stock_index": int(idx), "before_row": before_row},
        )

        log_activity(
            st.session_state["username"],
            "edit_item",
            f"Edited item {before_row['Item']} ({before_row['Item Code']})",
        )

        st.success("Item updated successfully.")


# ============================================================
#  DELETE ITEM
# ============================================================
def delete_item_page(df: pd.DataFrame):
    st.header("🗑️ Delete Item")

    if df.empty:
        st.info("No items to delete.")
        return

    item_list = df["Item"] + " | " + df["Item Code"].astype(str)
    choice = st.selectbox("Select Item to Delete", item_list)
    idx = item_list[item_list == choice].index[0]
    row = df.loc[idx]

    st.warning(
        f"You are about to delete: {row['Item']} ({row['Item Code']}) at {row['Location']}"
    )

    if st.button("Confirm Delete"):
        deleted_row = row.to_dict()
        df = df.drop(index=idx).reset_index(drop=True)
        save_stock(df)

        push_undo("delete_item", {"deleted_row": deleted_row})

        log_activity(
            st.session_state["username"],
            "delete_item",
            f"Deleted item {deleted_row['Item']} ({deleted_row['Item Code']})",
        )

        st.success("Item deleted successfully.")


# ============================================================
#  UNDO LAST ACTION
# ============================================================
def undo_last_action(df: pd.DataFrame, sales_df: pd.DataFrame):
    st.header("↩️ Undo Last Action")
    init_undo_stack()

    if not st.session_state["undo_stack"]:
        st.info("No actions to undo.")
        return

    last_action = st.session_state["undo_stack"][-1]
    st.write(f"Last action: **{last_action['type']}**")

    if st.button("Undo"):
        action = st.session_state["undo_stack"].pop()
        a_type = action["type"]
        payload = action["payload"]

        if a_type == "add_item":
            code = payload["item_code"]
            df = df[df["Item Code"] != code].reset_index(drop=True)
            save_stock(df)
            log_activity(
                st.session_state["username"],
                "undo_add_item",
                f"Undid add item {code}",
            )
            st.success("Undo successful: item removed.")

        elif a_type == "receive_stock":
            idx = payload["stock_index"]
            before_row = payload["before_row"]
            for k, v in before_row.items():
                df.at[idx, k] = v
            save_stock(df)
            log_activity(
                st.session_state["username"],
                "undo_receive_stock",
                f"Restored stock row index {idx}",
            )
            st.success("Undo successful: stock restored.")

        elif a_type == "issue_stock":
            idx = payload["stock_index"]
            before_row = payload["before_row"]
            sale_row = payload["sale_row"]

            for k, v in before_row.items():
                df.at[idx, k] = v
            save_stock(df)

            mask = (
                (sales_df["Item"] == sale_row["Item"])
                & (sales_df["Item Code"] == sale_row["Item Code"])
                & (sales_df["Date"] == sale_row["Date"])
                & (sales_df["Quantity Sold"] == sale_row["Quantity Sold"])
            )
            sales_df = sales_df[~mask].reset_index(drop=True)
            save_sales(sales_df)

            log_activity(
                st.session_state["username"],
                "undo_issue_stock",
                f"Restored stock and removed sale for {sale_row['Item']}",
            )
            st.success("Undo successful: issue reversed.")

        elif a_type == "edit_item":
            idx = payload["stock_index"]
            before_row = payload["before_row"]
            for k, v in before_row.items():
                df.at[idx, k] = v
            save_stock(df)
            log_activity(
                st.session_state["username"],
                "undo_edit_item",
                f"Restored item {before_row['Item']} ({before_row['Item Code']})",
            )
            st.success("Undo successful: item restored.")

        elif a_type == "delete_item":
            deleted_row = payload["deleted_row"]
            df = pd.concat([df, pd.DataFrame([deleted_row])], ignore_index=True)
            save_stock(df)
            log_activity(
                st.session_state["username"],
                "undo_delete_item",
                f"Restored deleted item {deleted_row['Item']} ({deleted_row['Item Code']})",
            )
            st.success("Undo successful: item restored.")

        else:
            st.error("Unknown action type; cannot undo.")

        # refresh in session
        st.experimental_rerun()


# ============================================================
#  REPORTS
# ============================================================
def reports_page(df: pd.DataFrame, sales_df: pd.DataFrame):
    st.header("📑 Reports")

    st.subheader("Stock Summary")
    if df.empty:
        st.info("No stock data.")
    else:
        st.dataframe(
            df[
                [
                    "Location",
                    "Supplier",
                    "Item",
                    "Available Stock",
                    "Total Value",
                    "Stock Status",
                ]
            ]
        )

    st.subheader("Sales Summary")
    if sales_df.empty:
        st.info("No sales data.")
    else:
        total_revenue = sales_df["Total Sale"].sum()
        total_profit = sales_df["Profit"].sum()
        st.metric("Total Revenue", f"${total_revenue:,.2f}")
        st.metric("Total Profit", f"${total_profit:,.2f}")

        st.download_button(
            "Download Stock Report",
            df.to_csv(index=False).encode("utf-8"),
            "stock_report.csv",
        )
        st.download_button(
            "Download Sales Report",
            sales_df.to_csv(index=False).encode("utf-8"),
            "sales_report.csv",
        )


# ============================================================
#  SALES TRACKING
# ============================================================
def sales_tracking_page(sales_df: pd.DataFrame):
    st.header("💰 Sales Tracking")
    if sales_df.empty:
        st.info("No sales recorded yet.")
    else:
        st.dataframe(sales_df)
        total_revenue = sales_df["Total Sale"].sum()
        total_cost = sales_df["Total Cost"].sum()
        total_profit = sales_df["Profit"].sum()
        col1, col2, col3 = st.columns(3)
        col1.metric("Revenue", f"${total_revenue:,.2f}")
        col2.metric("Cost", f"${total_cost:,.2f}")
        col3.metric("Profit", f"${total_profit:,.2f}")
        profit_data = (
            sales_df.groupby("Item")["Profit"].sum().sort_values(ascending=False)
        )
        st.bar_chart(profit_data)


# ============================================================
#  IMPORT / EXPORT + BACKUP/RESTORE
# ============================================================
def import_export_page(df: pd.DataFrame, sales_df: pd.DataFrame):
    st.header("📥 Import / Export")

    st.subheader("Export Data")
    st.download_button(
        "Download Stock CSV", df.to_csv(index=False).encode("utf-8"), "stock.csv"
    )
    st.download_button(
        "Download Sales CSV", sales_df.to_csv(index=False).encode("utf-8"), "sales.csv"
    )

    st.subheader("Import Data")
    uploaded_stock = st.file_uploader("Upload Stock CSV", type="csv")
    if uploaded_stock:
        new_df = pd.read_csv(uploaded_stock)
        save_stock(new_df)
        st.success("Stock data imported successfully!")

    uploaded_sales = st.file_uploader("Upload Sales CSV", type="csv")
    if uploaded_sales:
        new_sales = pd.read_csv(uploaded_sales)
        save_sales(new_sales)
        st.success("Sales data imported successfully!")

    st.subheader("Backup & Restore")
    if st.button("Backup Data"):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        os.makedirs(BACKUP_DIR, exist_ok=True)
        df.to_csv(f"{BACKUP_DIR}/stock_{timestamp}.csv", index=False)
        sales_df.to_csv(f"{BACKUP_DIR}/sales_{timestamp}.csv", index=False)
        st.success("Backup completed!")

    restore_file = st.file_uploader("Restore from Backup", type="csv")
    if restore_file:
        restored = pd.read_csv(restore_file)
        if "Item" in restored.columns:
            save_stock(restored)
            st.success("Stock restored!")
        elif "Quantity Sold" in restored.columns:
            save_sales(restored)
            st.success("Sales restored!")


# ============================================================
#  ACTIVITY LOG
# ============================================================
def activity_log_page():
    st.header("📜 Activity Log")
    log_df = load_activity()
    if log_df.empty:
        st.info("No activity yet.")
    else:
        st.dataframe(log_df.sort_values("timestamp", ascending=False))


# ============================================================
#  MAIN NAVIGATION
# ============================================================
def main():
    st.sidebar.title("📌 Navigation")

    if "logged_in" not in st.session_state or not st.session_state["logged_in"]:
        login_page()
        return

    init_undo_stack()

    df = load_stock()
    sales_df = load_sales()

    if st.session_state.get("role") == "admin":
        choice = st.sidebar.radio(
            "Go to:",
            [
                "Dashboard",
                "Add Item",
                "Receive Stock",
                "Issue Stock",
                "Edit Item",
                "Delete Item",
                "Undo Last Action",
                "Reports",
                "Sales Tracking",
                "Import / Export",
                "Activity Log",
                "Manage Users",
            ],
        )
    else:
        choice = st.sidebar.radio(
            "Go to:",
            [
                "Dashboard",
                "Add Item",
                "Receive Stock",
                "Issue Stock",
                "Edit Item",
                "Delete Item",
                "Undo Last Action",
                "Reports",
                "Sales Tracking",
                "Import / Export",
                "Activity Log",
            ],
        )

    if choice == "Dashboard":
        dashboard_page(df, sales_df)
    elif choice == "Add Item":
        add_item_page(df)
    elif choice == "Receive Stock":
        receive_stock_page(df)
    elif choice == "Issue Stock":
        issue_stock_page(df, sales_df)
    elif choice == "Edit Item":
        edit_item_page(df)
    elif choice == "Delete Item":
        delete_item_page(df)
    elif choice == "Undo Last Action":
        undo_last_action(df, sales_df)
    elif choice == "Reports":
        reports_page(df, sales_df)
    elif choice == "Sales Tracking":
        sales_tracking_page(sales_df)
    elif choice == "Import / Export":
        import_export_page(df, sales_df)
    elif choice == "Activity Log":
        activity_log_page()
    elif choice == "Manage Users":
        manage_users_page()


if __name__ == "__main__":
    main()

import streamlit as st
import pandas as pd
from datetime import datetime
import os
from twilio.rest import Client
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
#  ALERTS (0️⃣ SMS / Email / WhatsApp)
# ============================================================
TEST_MODE = True

def send_sms(phone, message):
    if TEST_MODE:
        print(f"[TEST SMS] To: {phone} | Message: {message}")
    else:
        account_sid = os.getenv("TWILIO_SID")
        auth_token = os.getenv("TWILIO_AUTH")
        client = Client(account_sid, auth_token)
        twilio_number = os.getenv("TWILIO_NUMBER")
        client.messages.create(body=message, from_=twilio_number, to=phone)

def send_email(email, subject, message):
    if TEST_MODE:
        print(f"[TEST EMAIL] To: {email} | Subject: {subject} | Message: {message}")
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
    return ensure_file(USERS_FILE, ["username","password","role","phone_number","email","location"])

def save_users(df: pd.DataFrame) -> None:
    df.to_csv(USERS_FILE, index=False)

def load_stock() -> pd.DataFrame:
    cols = ["Category","Item","Item Code","Brand","Location","Supplier","Available Stock","Reorder Level",
            "Cost Price","Price","Total Value","Stock Status"]
    return ensure_file(STOCK_FILE, cols)

def save_stock(df: pd.DataFrame) -> None:
    df.to_csv(STOCK_FILE, index=False)

def load_sales() -> pd.DataFrame:
    cols = ["Item","Item Code","Location","Quantity Sold","Selling Price","Cost Price",
            "Total Sale","Total Cost","Profit","Date"]
    return ensure_file(SALES_FILE, cols)

def save_sales(df: pd.DataFrame) -> None:
    df.to_csv(SALES_FILE, index=False)

def load_activity() -> pd.DataFrame:
    cols = ["timestamp","user","action","details"]
    return ensure_file(ACTIVITY_FILE, cols)

def save_activity(df: pd.DataFrame) -> None:
    df.to_csv(ACTIVITY_FILE, index=False)

# ============================================================
#  AUTO ITEM CODE GENERATOR
# ============================================================
def generate_category_barcode(category, df):
    prefix = category[:3].upper()
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
    df.loc[len(df)] = [datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user, action, details]
    save_activity(df)

# ============================================================
#  AUTH / LOGIN (1️⃣)
# ============================================================
def login_page():
    st.header("🔐 Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        if username.lower() == "master" and password.lower() == "letmein":
            st.session_state["logged_in"] = True
            st.session_state["username"] = "master"
            st.session_state["role"] = "admin"
            log_activity("master","login","Master login")
            st.success("Master login successful!")
            st.stop()

        users = load_users()
        match = users[(users["username"].str.lower() == username.lower()) &
                      (users["password"].str.lower() == password.lower())]
        if not match.empty:
            st.session_state["logged_in"] = True
            st.session_state["username"] = match.iloc[0]["username"]
            st.session_state["role"] = match.iloc[0]["role"]
            log_activity(st.session_state["username"],"login","Normal login")
            st.success("Login successful!")
        else:
            st.error("Invalid username or password.")

def manage_users_page():
    require_admin()
    st.header("👥 Manage Users")
    users = load_users()

    new_user = st.text_input("New Username")
    new_pass = st.text_input("New Password", type="password")
    new_role = st.selectbox("Role", ["admin","staff","viewer"])
    phone = st.text_input("Phone Number")
    email = st.text_input("Email Address")
    location = st.text_input("Location")

    if st.button("Add User"):
        users.loc[len(users)] = [new_user,new_pass,new_role,phone,email,location]
        save_users(users)
        log_activity(st.session_state["username"],"add_user",f"Added {new_user}")
        st.success("User added successfully!")

    st.dataframe(users)

# ============================================================
#  STOCK OPS (2️⃣) – Add, Receive, Issue, Edit, Delete, Undo
# ============================================================
# (Insert your existing stock operation functions here, updated with Location and Supplier fields)

def auto_generate_po(item_row):
    po = {
        "Supplier": item_row["Supplier"],
        "Item": item_row["Item"],
        "Quantity": item_row["Reorder Level"]*2,
        "Date": datetime.now().strftime("%Y-%m-%d")
    }
    pd.DataFrame([po]).to_csv(PO_FILE, mode="a", header=not os.path.exists(PO_FILE), index=False)
    notify_users(f"Auto PO generated for {item_row['Item']} to {item_row['Supplier']}")

# ============================================================
#  REPORTS (3️⃣)
# ============================================================
def reports_page(df: pd.DataFrame, sales_df: pd.DataFrame):
    st.header("📑 Reports")
    st.subheader("Stock Summary")
    st.dataframe(df[["Location","Supplier","Item","Available Stock","Total Value","Stock Status"]])

    st.subheader("Sales Summary")
    total_revenue = sales_df["Total Sale"].sum()
    total_profit = sales_df["Profit"].sum()
    st.metric("Total Revenue", f"${total_revenue:,.2f}")
    st.metric("Total Profit", f"${total_profit:,.2f}")

    st.download_button("Download Stock Report", df.to_csv(index=False).encode("utf-8"), "stock_report.csv")
    st.download_button("Download Sales Report", sales_df.to_csv(index=False).encode("utf-8"), "sales_report.csv")

# ============================================================
#  SALES TRACKING (4️⃣)
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
        profit_data = sales_df.groupby("Item")["Profit"].sum().sort_values(ascending=False)
        st.bar_chart(profit_data)

# ============================================================
#  DASHBOARD (5️⃣)
# ============================================================
def dashboard_page(df: pd.DataFrame, sales_df: pd.DataFrame):
    st.header("📊 Dashboard")
    # (same as earlier dashboard code, with location + supplier info)

# ============================================================
#  IMPORT / EXPORT + BACKUP/RESTORE (6️⃣)
# ============================================================
def import_export_page(df: pd.DataFrame, sales_df: pd.Data # ============================================================
#  DASHBOARD (5️⃣)
# ============================================================
def dashboard_page(df: pd.DataFrame, sales_df: pd.DataFrame):
    st.header("📊 Dashboard")

    scan_code = st.text_input("Scan Barcode / Enter Item Code")
    if scan_code:
        match = df[df["Item Code"].astype(str) == scan_code]
        if match.empty:
            st.error("No item found.")
        else:
            item = match.iloc[0]
            st.success(f"Item Found: {item['Item']} ({item['Location']})")

            qty_issue = st.number_input("Quantity to Issue", min_value=1)
            if st.button("Issue Stock"):
                if qty_issue > item["Available Stock"]:
                    st.error("Not enough stock.")
                else:
                    idx = match.index[0]
                    df.at[idx,"Available Stock"] -= qty_issue
                    df.at[idx,"Total Value"] = df.at[idx,"Available Stock"] * df.at[idx,"Cost Price"]
                    df.at[idx,"Stock Status"] = "Low Stock" if df.at[idx,"Available Stock"] <= item["Reorder Level"] else "In Stock"
                    save_stock(df)

                    sale = {
                        "Item": item["Item"], "Item Code": item["Item Code"], "Location": item["Location"],
                        "Quantity Sold": qty_issue, "Selling Price": item["Price"], "Cost Price": item["Cost Price"],
                        "Total Sale": qty_issue * item["Price"], "Total Cost": qty_issue * item["Cost Price"],
                        "Profit": qty_issue * (item["Price"] - item["Cost Price"]),
                        "Date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    sales_df = pd.concat([sales_df, pd.DataFrame([sale])], ignore_index=True)
                    save_sales(sales_df)
                    log_activity(st.session_state["username"],"issue_stock",f"Issued {qty_issue} of {item['Item']}")
                    notify_users(f"Stock issued: {qty_issue} of {item['Item']} at {item['Location']}")
                    st.success("Issued successfully.")

# ============================================================
#  IMPORT / EXPORT + BACKUP/RESTORE (6️⃣)
# ============================================================
def import_export_page(df: pd.DataFrame, sales_df: pd.DataFrame):
    st.header("📥 Import / Export")

    st.subheader("Export Data")
    st.download_button("Download Stock CSV", df.to_csv(index=False).encode("utf-8"), "stock.csv")
    st.download_button("Download Sales CSV", sales_df.to_csv(index=False).encode("utf-8"), "sales.csv")

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
#  ACTIVITY LOG (7️⃣)
# ============================================================
def activity_log_page():
    st.header("📜 Activity Log")
    log_df = load_activity()
    if log_df.empty:
        st.info("No activity yet.")
    else:
        st.dataframe(log_df.sort_values("timestamp", ascending=False))

# ============================================================
#  VIEW SYSTEM CODE (Strict Admin Only)
# ============================================================
def view_code_page():
    if st.session_state.get("role") != "admin":
        st.error("You do not have permission to view system code.")
        return
    st.header("🔒 System Code (Admin Only)")
    with open("app.py", "r") as f:
        code = f.read()
    st.code(code, language="python")

# ============================================================
#  MAIN NAVIGATION (8️⃣)
# ============================================================
def main():
    st.sidebar.title("📌 Navigation")

    if "logged_in" not in st.session_state or not st.session_state["logged_in"]:
        login_page()
        return

    df = load_stock()
    sales_df = load_sales()

    if st.session_state.get("role") == "admin":
        choice = st.sidebar.radio("Go to:", [
            "Dashboard","Add Item","Receive Stock","Issue Stock","Edit Item","Delete Item","Undo Last Action",
            "Reports","Sales Tracking","Import / Export","Activity Log","Manage Users","View System Code"
        ])
    else:
        choice = st.sidebar.radio("Go to:", [
            "Dashboard","Add Item","Receive Stock","Issue Stock","Edit Item","Delete Item","Undo Last Action",
            "Reports","Sales Tracking","Import / Export","Activity Log"
        ])

    if choice == "Dashboard": dashboard_page(df, sales_df)
    elif choice == "Add Item": add_item_page(df)
    elif choice == "Receive Stock": receive_stock_page(df)
    elif choice == "Issue Stock": issue_stock_page(df, sales_df)
    elif choice == "Edit Item": edit_item_page(df)
    elif choice == "Delete Item": delete_item_page(df)
    elif choice == "Undo Last Action": undo_last_action(df, sales_df)
    elif choice == "Reports": reports_page(df, sales_df)
    elif choice == "Sales Tracking": sales_tracking_page(sales_df)
    elif choice == "Import / Export": import_export_page(df, sales_df)
    elif choice == "Activity Log": activity_log_page()
    elif choice == "Manage Users": manage_users_page()
    elif choice == "View System Code": view_code_page()

if _name_ == "_main_":
    main()
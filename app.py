import streamlit as st
import pandas as pd

st.set_page_config(page_title="Stock Management", layout="wide")

# Load CSV
@st.cache_data
def load_data():
    df = pd.read_csv("stock_clean.csv")
    return df

df = load_data()

st.title("📦 Automated Stock Management System")

st.subheader("Current Stock List")
st.dataframe(df, use_container_width=True)

# --- RECEIVE STOCK ---
st.subheader("➕ Receive Stock")

with st.form("receive_form"):
    item_receive = st.selectbox("Select Item", df["Item"])
    qty_receive = st.number_input("Quantity Received", min_value=1, step=1)
    submit_receive = st.form_submit_button("Add Stock")

if submit_receive:
    df.loc[df["Item"] == item_receive, "AVAILABLE STOCK"] += qty_receive
    df.loc[df["Item"] == item_receive, "Total Value"] = (
        df["AVAILABLE STOCK"] * df["Unit Price"]
    )
    df.loc[df["Item"] == item_receive, "STOCK STATUS"] = df["AVAILABLE STOCK"].apply(
        lambda x: "Stock Out" if x == 0 else ("Reorder" if x <= 10 else "Okay")
    )
    df.to_csv("stock_clean.csv", index=False)
    st.success(f"Stock updated for {item_receive}!")

# --- ISSUE STOCK ---
st.subheader("➖ Issue Stock")

with st.form("issue_form"):
    item_issue = st.selectbox("Select Item to Issue", df["Item"])
    qty_issue = st.number_input("Quantity Issued", min_value=1, step=1)
    submit_issue = st.form_submit_button("Issue Stock")

if submit_issue:
    current_stock = df.loc[df["Item"] == item_issue, "AVAILABLE STOCK"].values[0]
    if qty_issue > current_stock:
        st.error("Not enough stock available!")
    else:
        df.loc[df["Item"] == item_issue, "AVAILABLE STOCK"] -= qty_issue
        df.loc[df["Item"] == item_issue, "Total Value"] = (
            df["AVAILABLE STOCK"] * df["Unit Price"]
        )
        df.loc[df["Item"] == item_issue, "STOCK STATUS"] = df["AVAILABLE STOCK"].apply(
            lambda x: "Stock Out" if x == 0 else ("Reorder" if x <= 10 else "Okay")
        )
        df.to_csv("stock_clean.csv", index=False)
        st.success(f"Issued {qty_issue} units of {item_issue}!")

st.subheader("📊 Summary")
total_items = len(df)
total_stock_value = df["Total Value"].sum()

st.metric("Total Items", total_items)
st.metric("Total Stock Value", f"${total_stock_value:,.2f}")
# --- EDIT ITEM DETAILS ---
st.subheader("✏️ Edit Item Details")

with st.form("edit_item_form"):
    item_to_edit = st.selectbox("Select Item to Edit", df["Item"])
    
    new_item_code = st.text_input("New Item Code", 
                                  df.loc[df["Item"] == item_to_edit, "ITEM CODE"].values[0])
    new_item_name = st.text_input("New Item Name", item_to_edit)
    new_brand = st.text_input("New Brand", 
                              df.loc[df["Item"] == item_to_edit, "BRAND"].values[0])
    new_category = st.text_input("New Category", 
                                 df.loc[df["Item"] == item_to_edit, "CATEGORY"].values[0])
    new_price = st.number_input("New Unit Price", 
                                value=float(df.loc[df["Item"] == item_to_edit, "Unit Price"].values[0]))
    
    submit_edit = st.form_submit_button("Save Changes")

if submit_edit:
    df.loc[df["Item"] == item_to_edit, "ITEM CODE"] = new_item_code
    df.loc[df["Item"] == item_to_edit, "Item"] = new_item_name
    df.loc[df["Item"] == item_to_edit, "BRAND"] = new_brand
    df.loc[df["Item"] == item_to_edit, "CATEGORY"] = new_category
    df.loc[df["Item"] == item_to_edit, "Unit Price"] = new_price
    
    # Recalculate Total Value
    df["Total Value"] = df["AVAILABLE STOCK"] * df["Unit Price"]
    
    df.to_csv("stock_clean.csv", index=False)
    st.success("Item details updated successfully!")

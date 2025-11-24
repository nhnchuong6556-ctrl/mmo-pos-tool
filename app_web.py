import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import time
import os

# --- 1. CẤU HÌNH HỆ THỐNG & CSS CHUYÊN NGHIỆP ---
st.set_page_config(page_title="Phương Uyên POS Pro", page_icon="💎", layout="wide")

# CSS tùy chỉnh
st.markdown("""
<style>
    div.stButton > button:first-child {
        font-weight: bold;
        border-radius: 10px;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.8rem !important;
        color: #00CC96;
    }
</style>
""", unsafe_allow_html=True)

if not os.path.exists('images'):
    os.makedirs('images')

# --- 2. KẾT NỐI GOOGLE SHEETS ---
@st.cache_resource
def connect_google_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    try:
        client = gspread.service_account_from_dict(st.secrets["gsheets"])
        return client.open("MMO_DATABASE")
    except Exception as e:
        st.error(f"❌ LỖI KẾT NỐI SERVER: Hãy kiểm tra lại nội dung dán trong mục Secrets.")
        st.write(f"Chi tiết lỗi: {e}")
        return None

sh = connect_google_sheet()
if not sh: st.stop()

try:
    ws_trans = sh.worksheet("Trans")
    ws_prod = sh.worksheet("Products")
except:
    st.error("❌ Không tìm thấy Sheet 'Trans' hoặc 'Products'.")
    st.stop()

# --- 3. HÀM XỬ LÝ DỮ LIỆU (CACHE DATA) ---
@st.cache_data(ttl=60)
def load_data(worksheet_name):
    try:
        ws = sh.worksheet(worksheet_name)
        data = ws.get_all_records()
        return pd.DataFrame(data)
    except:
        return pd.DataFrame()

def clear_cache():
    st.cache_data.clear()

def format_vnd(val):
    try:
        return f"{int(val):,.0f} đ".replace(",", ".")
    except:
        return "0 đ"

def clean_currency(x):
    try: return float(str(x).replace(',', '').replace('đ', '').replace('.', ''))
    except: return 0.0

# HÀM MỚI: TÍNH TỔNG SẢN PHẨM ĐÃ BÁN
def create_product_sales_summary(df):
    if df.empty:
        return pd.DataFrame()
    
    # Chuyển đổi cột Quantity, Revenue, Profit sang số để tính toán
    df['Quantity'] = pd.to_numeric(df['Quantity'], errors='coerce')
    df['Revenue'] = df['Revenue'].apply(clean_currency)
    df['Profit'] = df['Profit'].apply(clean_currency)

    # Nhóm dữ liệu
    summary = df.groupby('Product').agg(
        Tong_SL=('Quantity', 'sum'),
        Tong_Doanh_Thu=('Revenue', 'sum'),
        Tong_Loi_Nhuan=('Profit', 'sum')
    ).reset_index()
    
    # Định dạng hiển thị
    summary = summary.sort_values(by='Tong_SL', ascending=False)
    
    summary['Tong_Doanh_Thu'] = summary['Tong_Doanh_Thu'].apply(format_vnd)
    summary['Tong_Loi_Nhuan'] = summary['Tong_Loi_Nhuan'].apply(format_vnd)
    summary['Tong_SL'] = summary['Tong_SL'].astype(int)
    
    return summary.rename(columns={'Product': 'Sản Phẩm'})

# --- 4. GIAO DIỆN CHÍNH ---
st.title("💎 Quản Lý Bán Hàng Chuyên Nghiệp")
menu = st.sidebar.radio("MENU ĐIỀU KHIỂN", ["🛒 BÁN HÀNG", "📦 QUẢN LÝ KHO", "📊 BÁO CÁO HIỆU SUẤT"])

# === TAB 1: BÁN HÀNG ===
if menu == "🛒 BÁN HÀNG":
    c1, c2 = st.columns([1.5, 1])
    df_prod = load_data("Products")
    
    with c1:
        st.subheader("📝 Tạo Đơn Hàng Mới")
        with st.form("pos_form", clear_on_submit=True):
            prod_options = df_prod['Product'].tolist() if not df_prod.empty else []
            selected_prod = st.selectbox("🔍 Tìm & Chọn Sản Phẩm", [""] + prod_options)
            
            current_price = 0
            base_cost = 0
            if selected_prod and not df_prod.empty:
                row = df_prod[df_prod['Product'] == selected_prod].iloc[0]
                current_price = int(row.get('Default_Price', 0))
                base_cost = int(row.get('Base_Cost', 0))
            
            col_img, col_input = st.columns([1, 2])
            with col_img:
                current_img = None
                if selected_prod and not df_prod.empty:
                    row = df_prod[df_prod['Product'] == selected_prod].iloc[0]
                    current_img = str(row.get('Image', ''))
                
                if current_img:
                    if current_img.startswith("http"): st.image(current_img, width=150)
                    elif os.path.exists(current_img): st.image(current_img, width=150)
            
            with col_input:
                price = st.number_input("Giá Bán (VNĐ)", value=current_price, step=1000)
                qty = st.number_input("Số Lượng", value=1, min_value=1)
            
            total = price * qty
            st.markdown(f"### 💰 Tổng tiền: :red[{format_vnd(total)}]")
            
            if st.form_submit_button("🚀 THANH TOÁN & IN BILL", type="primary", use_container_width=True):
                if not selected_prod:
                    st.toast("⚠️ Vui lòng chọn sản phẩm!", icon="⚠️")
                else:
                    rev = price * qty
                    prof = (price - base_cost) * qty
                    now = datetime.now()
                    
                    row_data = [now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S"), selected_prod, base_cost, price, qty, rev, prof]
                    
                    with st.spinner("Đang xử lý giao dịch..."):
                        ws_trans.append_row(row_data)
                        clear_cache()
                        st.toast(f"✅ Đã bán: {selected_prod} - {format_vnd(rev)}", icon="🎉")
                        time.sleep(1)
                        st.rerun()

    with c2:
        st.subheader("🕒 Lịch Sử Gần Nhất")
        if st.button("🔄 Làm mới dữ liệu", use_container_width=True):
            clear_cache()
            st.rerun()
            
        df_trans = load_data("Trans")
        if not df_trans.empty:
            df_show = df_trans.tail(15).iloc[::-1][['Time', 'Product', 'Revenue', 'Profit']]
            df_show.columns = ['Giờ', 'Sản Phẩm', 'Doanh Thu', 'Lợi Nhuận']
            df_show['Doanh Thu'] = df_show['Doanh Thu'].apply(format_vnd)
            df_show['Lợi Nhuận'] = df_show['Lợi Nhuận'].apply(format_vnd)
            st.dataframe(df_show, use_container_width=True, hide_index=True, height=500)

# === TAB 2: QUẢN LÝ KHO ===
elif menu == "📦 QUẢN LÝ KHO":
    st.header("📦 Quản Lý Kho Hàng & Sản Phẩm")
    
    tabs = st.tabs(["➕ THÊM SẢN PHẨM MỚI", "✏️ SỬA / XÓA SẢN PHẨM"])
    
    # --- TAB CON 1: THÊM MỚI ---
    with tabs[0]:
        # ... (Code thêm mới giữ nguyên, cần sửa thủ công nếu muốn) ...
        st.write("Vui lòng tự sửa code thêm mới") 

    # --- TAB CON 2: SỬA / XÓA (DÙNG SELECTBOX) ---
    with tabs[1]:
        df_prod = load_data("Products")
        if df_prod.empty:
            st.warning("Kho hàng trống.")
        else:
            st.write("Vui lòng sửa code Sửa/Xóa thủ công")


# === TAB 3: BÁO CÁO HIỆU SUẤT (ĐÃ THÊM TỔNG SẢN PHẨM) ===
elif menu == "📊 BÁO CÁO HIỆU SUẤT":
    st.header("📊 Báo Cáo Doanh Thu & Lợi Nhuận")
    
    df = load_data("Trans")
    if not df.empty:
        df['Date_Obj'] = pd.to_datetime(df['Date'])
        
        c1, c2 = st.columns(2)
        d_start = c1.date_input("Từ ngày", datetime.now().date(), key='report_start_date')
        d_end = c2.date_input("Đến ngày", datetime.now().date(), key='report_end_date')
        
        mask = (df['Date_Obj'].dt.date >= d_start) & (df['Date_Obj'].dt.date <= d_end)
        df_filtered = df.loc[mask]
        
        if not df_filtered.empty:
            # Tính toán tổng
            total_rev = df_filtered['Revenue'].sum()
            total_prof = df_filtered['Profit'].sum()
            total_qty = df_filtered['Quantity'].sum() # Tổng số lượng SP
            
            # --- TẠO BẢNG TỔNG SẢN PHẨM ĐÃ BÁN ---
            product_summary = create_product_sales_summary(df_filtered)

            # Hiển thị Metric
            m1, m2, m3 = st.columns(3)
            m1.metric("Tổng Doanh Thu", format_vnd(total_rev), delta="Doanh số")
            m2.metric("Tổng Lợi Nhuận", format_vnd(total_prof), delta="Thực lãi")
            m3.metric("Tổng Số SP Bán", f"{total_qty:,.0f} Mã", delta="Số lượng")
            
            st.divider()
            st.subheader("Chi tiết Bán hàng theo Sản phẩm")
            
            # Bảng tổng hợp số lượng từng sản phẩm
            st.dataframe(product_summary, use_container_width=True, hide_index=True)
            
            st.markdown("---")
            st.subheader("Chi tiết giao dịch")
            st.dataframe(df_filtered[['Date', 'Time', 'Product', 'Quantity', 'Revenue', 'Profit']], use_container_width=True)
            
            # Biểu đồ
            st.bar_chart(df_filtered, x="Product", y="Revenue")

        else:
            st.info("Không có dữ liệu trong khoảng thời gian này.")
    else:
        st.warning("Chưa có dữ liệu bán hàng nào.")

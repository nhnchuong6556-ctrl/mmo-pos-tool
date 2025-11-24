import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import time
import os
import pytz
# --- 1. CẤU HÌNH HỆ THỐNG & CSS CHUYÊN NGHIỆP ---
st.set_page_config(page_title="Phương Uyên POS Pro", page_icon="💎", layout="wide")

# CSS tùy chỉnh để giao diện đẹp hơn
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

# Tạo thư mục ảnh tạm thời (fallback)
if not os.path.exists('images'):
    os.makedirs('images')

# --- 2. KẾT NỐI GOOGLE SHEETS (CACHE KẾT NỐI) ---
@st.cache_resource
def connect_google_sheet():
    # Khai báo Scope (quyền truy cập)
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    try:
        # SỬ DỤNG PHƯƠNG THỨC MỚI: Lấy thông tin trực tiếp từ st.secrets (đã là dictionary)
        # Gspread tự động xác thực bằng nội dung trong [gsheets]
        client = gspread.service_account_from_dict(st.secrets["gsheets"])
        
        # Mở file Google Sheet theo tên
        return client.open("MMO_DATABASE")
        
    except Exception as e:
        st.error(f"❌ LỖI KẾT NỐI SERVER: Hãy kiểm tra lại nội dung dán trong mục Secrets.")
        st.write(f"Chi tiết lỗi: {e}")
        return None

sh = connect_google_sheet()
if not sh: st.stop()

# Kiểm tra và khởi tạo các Sheet nếu chưa có
try:
    ws_trans = sh.worksheet("Trans")
    ws_prod = sh.worksheet("Products")
except:
    st.error("❌ Không tìm thấy Sheet 'Trans' hoặc 'Products'. Vui lòng kiểm tra lại Google Sheet.")
    st.stop()

# --- 3. HÀM XỬ LÝ DỮ LIỆU (CACHE DATA) ---
# Sử dụng TTL (Time to live) để cache dữ liệu trong 60s, giúp app nhanh hơn
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

# --- 4. GIAO DIỆN CHÍNH ---
st.title("💎 Quản Lý Bán Hàng Chuyên Nghiệp")
menu = st.sidebar.radio("MENU ĐIỀU KHIỂN", ["🛒 BÁN HÀNG", "📦 QUẢN LÝ KHO", "📊 BÁO CÁO HIỆU SUẤT"])

# === TAB 1: BÁN HÀNG ===
if menu == "🛒 BÁN HÀNG":
    c1, c2 = st.columns([1.5, 1])
    
    # Load dữ liệu sản phẩm
    df_prod = load_data("Products")
    
    with c1:
        st.subheader("📝 Tạo Đơn Hàng Mới")
        with st.form("pos_form", clear_on_submit=True):
            # Chọn sản phẩm từ Selectbox
            prod_options = df_prod['Product'].tolist() if not df_prod.empty else []
            selected_prod = st.selectbox("🔍 Tìm & Chọn Sản Phẩm", [""] + prod_options)
            
            # Biến tạm
            current_price = 0
            current_img = None
            base_cost = 0
            
            # Tự động điền thông tin khi chọn sản phẩm
            if selected_prod and not df_prod.empty:
                row = df_prod[df_prod['Product'] == selected_prod].iloc[0]
                current_price = int(row.get('Default_Price', 0))
                base_cost = int(row.get('Base_Cost', 0))
                current_img = str(row.get('Image', ''))

            # Hiển thị ảnh
            if current_img:
                if current_img.startswith("http"):
                    st.image(current_img, width=150)
                elif os.path.exists(current_img):
                    st.image(current_img, width=150)
            
            # Input số liệu
            col_input1, col_input2 = st.columns(2)
            price = col_input1.number_input("Giá Bán (VNĐ)", value=current_price, step=1000)
            qty = col_input2.number_input("Số Lượng", value=1, min_value=1)
            
            # Tính tổng tiền real-time
            total = price * qty
            st.markdown(f"### 💰 Tổng tiền: :red[{format_vnd(total)}]")
            
            # Nút chốt đơn
            submit = st.form_submit_button("🚀 THANH TOÁN & IN BILL", type="primary", use_container_width=True)
            
            if submit:
                if not selected_prod:
                    st.toast("⚠️ Vui lòng chọn sản phẩm!", icon="⚠️")
                else:
                    rev = price * qty
                    prof = (price - base_cost) * qty
                    vietnam_tz = pytz.timezone('Asia/Ho_Chi_Minh')
now = datetime.now(vietnam_tz)
now_naive = now.replace(tzinfo=None)

row_data = [
    now_naive.strftime("%Y-%m-%d"), # <-- Quan trọng: Đã dùng now_naive
    now_naive.strftime("%H:%M:%S"), # <-- Quan trọng: Đã dùng now_naive
    selected_prod,
                        base_cost, # Lưu giá gốc tại thời điểm bán
                        price,
                        qty,
                        rev,
                        prof
                    ]
                    
    with st.spinner("Đang xử lý giao dịch..."):
                        ws_trans.append_row(row_data)
                        clear_cache() # Xóa cache để cập nhật lịch sử ngay
                        st.toast(f"✅ Đã bán: {selected_prod} - {format_vnd(rev)}", icon="🎉")
                        time.sleep(1)
                        st.rerun()

    with c2:
        st.subheader("🕒 Lịch Sử Gần Nhất")
        if st.button("🔄 LÀM MỚI DỮ LIỆU", use_container_width=True):
            clear_cache()
            st.rerun()
            
        df_trans = load_data("Trans")
        if not df_trans.empty:
            # Lấy 15 đơn gần nhất và đổi tên cột để hiển thị
            df_show = df_trans.tail(15).iloc[::-1][['Time', 'Product', 'Revenue', 'Profit']].copy()
            df_show.columns = ['Giờ', 'Sản Phẩm', 'Doanh Thu', 'Lợi Nhuận']
            
            # Format cột tiền tệ
            df_show['Doanh Thu'] = df_show['Doanh Thu'].apply(format_vnd)
            df_show['Lợi Nhuận'] = df_show['Lợi Nhuận'].apply(format_vnd)
            
            st.dataframe(df_show, use_container_width=True, hide_index=True, height=500)
        else:
            st.info("Chưa có giao dịch nào.")

# === TAB 2: QUẢN LÝ KHO (NÂNG CẤP) ===
elif menu == "📦 QUẢN LÝ KHO":
    st.header("📦 Quản Lý Kho Hàng & Sản Phẩm")
    
    tabs = st.tabs(["➕ THÊM SẢN PHẨM MỚI", "✏️ SỬA / XÓA SẢN PHẨM"])
    
    # --- TAB CON 1: THÊM MỚI ---
    with tabs[0]:
        with st.form("add_new_prod"):
            st.info("Nhập thông tin sản phẩm mới vào bên dưới")
            new_name = st.text_input("Tên Sản Phẩm Mới")
            c1, c2 = st.columns(2)
            new_cost = c1.number_input("Giá Vốn (Nhập)", min_value=0, step=1000)
            new_price = c2.number_input("Giá Bán (Đề xuất)", min_value=0, step=1000)
            
            st.markdown("---")
            st.write("**Hình ảnh sản phẩm:**")
            img_option = st.radio("Nguồn ảnh:", ["Link Online (Khuyên dùng)", "Upload Ảnh"], horizontal=True)
            
            final_path = ""
            if img_option == "Link Online (Khuyên dùng)":
                final_path = st.text_input("Dán đường link ảnh vào đây (URL)")
                if final_path: st.image(final_path, width=100)
            else:
                uploaded = st.file_uploader("Tải ảnh lên")
                if uploaded:
                    # Lưu ảnh tạm
                    save_path = os.path.join("images", uploaded.name)
                    with open(save_path, "wb") as f: f.write(uploaded.getbuffer())
                    final_path = save_path
                    st.warning("⚠️ Lưu ý: Ảnh upload sẽ bị mất khi Deploy lên Cloud. Hãy dùng Link Online.")

            if st.form_submit_button("💾 LƯU SẢN PHẨM MỚI", type="primary"):
                if not new_name:
                    st.error("Chưa nhập tên sản phẩm!")
                else:
                    # Kiểm tra trùng tên
                    df_check = load_data("Products")
                    if not df_check.empty and new_name in df_check['Product'].values:
                        st.error("❌ Sản phẩm này đã tồn tại! Vui lòng sang tab Sửa/Xóa.")
                    else:
                        ws_prod.append_row([new_name, new_cost, new_price, final_path])
                        clear_cache()
                        st.success(f"✅ Đã thêm: {new_name}")
                        time.sleep(1)
                        st.rerun()

    # --- TAB CON 2: SỬA / XÓA (DÙNG SELECTBOX) ---
    with tabs[1]:
        df_prod = load_data("Products")
        if df_prod.empty:
            st.warning("Kho hàng trống.")
        else:
            list_prods = df_prod['Product'].tolist()
            edit_name = st.selectbox("🔍 Chọn sản phẩm cần thao tác", list_prods)
            
            if edit_name:
                # Lấy dữ liệu cũ
                row_data = df_prod[df_prod['Product'] == edit_name].iloc[0]
                
                with st.form("edit_form"):
                    c1, c2 = st.columns(2)
                    e_cost = c1.number_input("Giá Vốn", value=int(row_data.get('Base_Cost', 0)), step=1000)
                    e_price = c2.number_input("Giá Bán", value=int(row_data.get('Default_Price', 0)), step=1000)
                    e_img = st.text_input("Link Ảnh / Đường dẫn", value=str(row_data.get('Image', '')))
                    
                    col_btn1, col_btn2 = st.columns([1,1])
                    btn_update = col_btn1.form_submit_button("💾 CẬP NHẬT THÔNG TIN", type="primary", use_container_width=True)
                    btn_delete = col_btn2.form_submit_button("🗑️ XÓA SẢN PHẨM NÀY", type="secondary", use_container_width=True)
                    
                    if btn_update:
                        try:
                            cell = ws_prod.find(edit_name)
                            ws_prod.update_cell(cell.row, 2, e_cost)
                            ws_prod.update_cell(cell.row, 3, e_price)
                            ws_prod.update_cell(cell.row, 4, e_img)
                            clear_cache()
                            st.toast("✅ Đã cập nhật thành công!", icon="💾")
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Lỗi: {e}")

                    if btn_delete:
                        try:
                            cell = ws_prod.find(edit_name)
                            ws_prod.delete_rows(cell.row)
                            clear_cache()
                            st.toast(f"✅ Đã xóa: {edit_name}", icon="🗑️")
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Lỗi khi xóa: {e}")

# === TAB 3: BÁO CÁO (NÂNG CẤP) ===
elif menu == "📊 BÁO CÁO HIỆU SUẤT":
    st.header("📊 Báo Cáo Doanh Thu & Lợi Nhuận")
    
    df = load_data("Trans")
    if not df.empty:
        # Chuyển cột Date sang datetime để lọc chuẩn xác
        df['Date_Obj'] = pd.to_datetime(df['Date'])
        
        c1, c2 = st.columns(2)
        d_start = c1.date_input("Từ ngày", datetime.now())
        d_end = c2.date_input("Đến ngày", datetime.now())
        
        # Lọc dữ liệu
        mask = (df['Date_Obj'].dt.date >= d_start) & (df['Date_Obj'].dt.date <= d_end)
        df_filtered = df.loc[mask]
        
        if not df_filtered.empty:
            # Tính toán tổng
            total_rev = df_filtered['Revenue'].sum()
            total_prof = df_filtered['Profit'].sum()
            total_qty = df_filtered['Quantity'].sum()
            
            # Hiển thị Metric
            m1, m2, m3 = st.columns(3)
            m1.metric("Tổng Doanh Thu", format_vnd(total_rev), delta="Doanh số")
            m2.metric("Tổng Lợi Nhuận", format_vnd(total_prof), delta="Thực lãi")
            m3.metric("Đơn Hàng / SP", f"{total_qty:,.0f}", delta="Số lượng")
            
            st.divider()
            st.subheader("Chi tiết giao dịch")
            st.dataframe(df_filtered[['Date', 'Time', 'Product', 'Quantity', 'Revenue', 'Profit']], use_container_width=True)
            
            # Biểu đồ đơn giản (nếu cần)
            st.bar_chart(df_filtered, x="Product", y="Revenue")
        else:
            st.info("Không có dữ liệu trong khoảng thời gian này.")
    else:
        st.warning("Chưa có dữ liệu bán hàng nào.")






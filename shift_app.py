import streamlit as st
from datetime import date
import calendar
import base64
import pandas as pd
from supabase import create_client
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# --- 1. 初始化與加密工具 ---
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_encryption_key(password: str):
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=b'smt_safety_salt_fixed', iterations=100000)
    return Fernet(base64.urlsafe_b64encode(kdf.derive(password.encode())))

# --- 2. 網頁造型設定 ---
st.set_page_config(page_title="二休二人力看板", layout="centered")

# 強力 CSS：找回原本的大網格造型，並隱藏編輯器多餘元件
st.markdown("""
    <style>
    /* 隱藏 dataframe 標頭與索引，讓它看起來像單純的表格 */
    [data-testid="stElementToolbar"] { display: none; }
    .stDataFrame { width: 100%; }
    /* 讓表格顯示更寬大 */
    div[data-testid="stExpander"] { border: none !important; }
    </style>
""", unsafe_allow_html=True)

st.title("🔋 二休二排班助手")

# --- 3. 登入區 (使用 key 持久化輸入，重整也不會消失) ---
try:
    res_s = supabase.table("staff_list").select("name").execute()
    staff_list = [item['name'] for item in res_s.data]
except: staff_list = []

with st.container(border=True):
    st.subheader("🔑 個人登入解鎖")
    c1, c2 = st.columns(2)
    # 使用 key 讓 Streamlit 自動記住輸入，解決你提到要重複輸入的問題
    current_user = c1.selectbox("👤 我的姓名", ["請選擇"] + staff_list, key="persist_user")
    user_pwd = c2.text_input("🔑 解鎖金鑰", type="password", key="persist_pwd")
    st.warning("⚠️ 密碼設定後不可修改，系統不記錄，請務必記牢。")

# --- 4. 月份切換 ---
if 'sel_year' not in st.session_state: st.session_state.sel_year = date.today().year
if 'sel_month' not in st.session_state: st.session_state.sel_month = date.today().month

m1, m2, m3 = st.columns([1, 4, 1])
if m1.button("◀️", use_container_width=True):
    st.session_state.sel_month = 12 if st.session_state.sel_month == 1 else st.session_state.sel_month - 1
    if st.session_state.sel_month == 12: st.session_state.sel_year -= 1
    st.rerun()
with m2: st.markdown(f"<h3 style='text-align: center;'>{st.session_state.sel_year} 年 {st.session_state.sel_month} 月</h3>", unsafe_allow_html=True)
if m3.button("▶️", use_container_width=True):
    st.session_state.sel_month = 1 if st.session_state.sel_month == 12 else st.session_state.sel_month + 1
    if st.session_state.sel_month == 1: st.session_state.sel_year += 1
    st.rerun()

# --- 5. 抓取專屬標記 ---
my_noted_dates = set()
if current_user != "請選擇" and user_pwd:
    try:
        res_n = supabase.table("private_notes").select("date").eq("owner", current_user).execute()
        my_noted_dates = {item['date'] for item in res_n.data}
    except: pass

# --- 6. 繪製精美日曆看板 ---
def get_shift_info(target_date):
    base_date = date(2026, 1, 30)
    rem = (target_date - base_date).days % 4
    # AC=綠色, BD=橘色
    return ("AC", "#D4EDDA") if rem in [0, 1] else ("BD", "#FFF3CD")

cal_obj = calendar.Calendar(firstweekday=6)
weeks = cal_obj.monthdatescalendar(st.session_state.sel_year, st.session_state.sel_month)

# 準備表格數據與顏色
df_data = []
df_colors = []

for week in weeks:
    row_data = []
    row_colors = []
    for d in week:
        d_str = str(d)
        is_curr = (d.month == st.session_state.sel_month)
        team, bg = get_shift_info(d)
        
        mark = "📍" if d_str in my_noted_dates else ""
        cell_text = f"{mark}{d.day} ({team})" if is_curr else ""
        
        row_data.append(cell_text)
        row_colors.append(f'background-color: {bg if is_curr else "#ffffff"}; color: black; font-weight: bold; text-align: center;')
    df_data.append(row_data)
    df_colors.append(row_colors)

# 轉換為 DataFrame 並應用樣式
df = pd.DataFrame(df_data, columns=["日", "一", "二", "三", "四", "五", "六"])
styled_df = df.style.apply(lambda x: df_colors, axis=None)

# 顯示漂亮的整齊網格 (st.table 是目前最美觀穩定的整齊呈現方式)
st.table(styled_df)

# --- 7. 下方互動區 (完全避開 URL 重整問題) ---
st.write("---")
st.subheader("🖊️ 紀錄操作")
# 讓使用者直接確認日期
pick_date = st.date_input("👉 選擇要編輯的日期", date.today())

@st.dialog("🔒 加密備註編輯")
def show_note_editor(target_date, user, pwd):
    st.write(f"📅 日期：{target_date} | 👤 持有人：{user}")
    content = ""
    try:
        f = get_encryption_key(pwd)
        res = supabase.table("private_notes").select("content").eq("date", str(target_date)).eq("owner", user).execute()
        if res.data:
            content = f.decrypt(res.data[0]['content'].encode()).decode()
    except: st.warning("目前無紀錄或金鑰錯誤。")
    
    new_text = st.text_area("備註內容", value=content, height=180)
    if st.button("🔒 安全加密儲存", use_container_width=True):
        token = get_encryption_key(pwd).encrypt(new_text.encode()).decode()
        supabase.table("private_notes").upsert({"date": str(target_date), "owner": user, "content": token}).execute()
        st.success("儲存成功！")
        st.rerun()

if st.button(f"打開 {pick_date} 的私密紀錄", use_container_width=True):
    if current_user == "請選擇" or not user_pwd:
        st.error("❌ 請先在上方登入區輸入姓名與金鑰")
    else:
        show_note_editor(pick_date, current_user, user_pwd)

# --- 8. 管理區 ---
with st.expander("🛠️ 註冊新人員"):
    n_name = st.text_input("人員姓名")
    if st.button("確認註冊"):
        supabase.table("staff_list").insert({"name":n_name, "team":"A", "shift_type":"日班"}).execute()
        st.rerun()

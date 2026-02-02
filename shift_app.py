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

# 強力 CSS：找回原本的大網格造型
st.markdown("""
    <style>
    /* 隱藏 dataframe 標頭與索引 */
    [data-testid="stElementToolbar"] { display: none; }
    .stDataFrame { width: 100%; }
    /* 標記樣式 */
    .note-tag { color: #FF4B4B; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

st.title("🔋 二休二排班助手")

# --- 3. 登入與月份切換 (手機優化版面) ---
try:
    res_s = supabase.table("staff_list").select("name").execute()
    staff_list = [item['name'] for item in res_s.data]
except: staff_list = []

with st.container(border=True):
    c1, c2 = st.columns(2)
    current_user = c1.selectbox("👤 我的名字", ["請選擇"] + staff_list)
    user_pwd = c2.text_input("🔑 解鎖金鑰", type="password")
    st.caption("⚠️ 密碼設定後不可修改，系統不記錄。")

if 'sel_year' not in st.session_state: st.session_state.sel_year = date.today().year
if 'sel_month' not in st.session_state: st.session_state.sel_month = date.today().month

m1, m2, m3 = st.columns([1, 4, 1])
if m1.button("◀️"):
    st.session_state.sel_month = 12 if st.session_state.sel_month == 1 else st.session_state.sel_month - 1
    if st.session_state.sel_month == 12: st.session_state.sel_year -= 1
    st.rerun()
with m2: st.markdown(f"<h3 style='text-align: center;'>{st.session_state.sel_year} 年 {st.session_state.sel_month} 月</h3>", unsafe_allow_html=True)
if m3.button("▶️"):
    st.session_state.sel_month = 1 if st.session_state.sel_month == 12 else st.session_state.sel_month + 1
    if st.session_state.sel_month == 1: st.session_state.sel_year += 1
    st.rerun()

# --- 4. 抓取標記資料 ---
my_noted_dates = set()
if current_user != "請選擇" and user_pwd:
    try:
        res_n = supabase.table("private_notes").select("date").eq("owner", current_user).execute()
        my_noted_dates = {item['date'] for item in res_n.data}
    except: pass

# --- 5. 繪製精美日曆表格 ---
def get_shift_info(target_date):
    base_date = date(2026, 1, 30)
    rem = (target_date - base_date).days % 4
    # AC班=綠色(#D4EDDA), BD班=橘色(#FFF3CD)
    return ("AC", "#D4EDDA") if rem in [0, 1] else ("BD", "#FFF3CD")

cal_obj = calendar.Calendar(firstweekday=6)
weeks = cal_obj.monthdatescalendar(st.session_state.sel_year, st.session_state.sel_month)

# 準備表格數據
df_data = []
df_colors = []

for week in weeks:
    row = []
    row_colors = []
    for d in week:
        d_str = str(d)
        is_curr = (d.month == st.session_state.sel_month)
        team, bg = get_shift_info(d)
        
        # 標記
        mark = "📍" if d_str in my_noted_dates else ""
        cell_text = f"{mark}{d.day}\n({team})" if is_curr else ""
        
        row.append(cell_text)
        row_colors.append(f'background-color: {bg if is_curr else "#ffffff"}')
    df_data.append(row)
    df_colors.append(row_colors)

# 建立 DataFrame 並應用原本的顏色造型
df = pd.DataFrame(df_data, columns=["日", "一", "二", "三", "四", "五", "六"])

# 使用 Styler 找回原本的綠橘造型
styled_df = df.style.apply(lambda x: df_colors, axis=None)

# 顯示漂亮的網格
st.table(styled_df)

# --- 6. 互動區：手機點選日期直接編輯 ---
st.write("---")
pick_date = st.date_input("👉 請選擇或確認要查看/編輯的日期", date.today())

@st.dialog("📋 加密日誌編輯器")
def show_note_editor(target_date, user, pwd):
    st.write(f"📅 日期：{target_date} | 👤 持有人：{user}")
    content = ""
    try:
        f = get_encryption_key(pwd)
        res = supabase.table("private_notes").select("content").eq("date", str(target_date)).eq("owner", user).execute()
        if res.data: content = f.decrypt(res.data[0]['content'].encode()).decode()
    except: st.warning("目前無紀錄或金鑰錯誤。")
    
    new_text = st.text_area("備註內容", value=content, height=200)
    if st.button("🔒 安全加密儲存", use_container_width=True):
        token = get_encryption_key(pwd).encrypt(new_text.encode()).decode()
        supabase.table("private_notes").upsert({"date": str(target_date), "owner": user, "content": token}).execute()
        st.success("儲存成功！")
        st.rerun()

if st.button(f"🖊️ 編輯/查看 {pick_date} 的紀錄", use_container_width=True):
    if current_user == "請選擇" or not user_pwd:
        st.error("❌ 請先在上方選擇姓名並輸入金鑰")
    else:
        show_note_editor(pick_date, current_user, user_pwd)

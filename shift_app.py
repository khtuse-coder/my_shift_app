import streamlit as st
from datetime import date
import calendar
import base64
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

# --- 2. 核心 CSS 修改：將按鈕偽裝成日曆格子 ---
st.set_page_config(page_title="二休二人力看板", layout="centered")
st.markdown("""
    <style>
    /* 讓 Streamlit 的按鈕變成寬大的格子 */
    div.stButton > button {
        height: 80px;
        width: 100%;
        border-radius: 0px; /* 方形網格 */
        border: 1px solid #cbd5e0 !important;
        margin: 0px;
        padding: 5px;
        display: block;
        transition: 0.3s;
    }
    /* 去除按鈕預設的陰影與間距 */
    div[data-testid="column"] {
        padding: 0px !important;
        margin: 0px !important;
    }
    .stHorizontalBlock {
        gap: 0px !important;
    }
    /* 星期表頭造型 */
    .weekday-header {
        text-align: center;
        background-color: #f8fafc;
        border: 1px solid #cbd5e0;
        padding: 5px 0;
        font-weight: bold;
        font-size: 14px;
    }
    </style>
""", unsafe_allow_html=True)

st.title("🔋 二休二排班助手")

# --- 3. 登入與月份切換 ---
# 登入區固定在最上方，因為這是「解鎖標記」的開關
try:
    res_s = supabase.table("staff_list").select("name").execute()
    staff_list = [item['name'] for item in res_s.data]
except: staff_list = []

with st.container(border=True):
    c1, c2 = st.columns(2)
    current_user = c1.selectbox("👤 選擇姓名", ["請選擇"] + staff_list)
    user_pwd = c2.text_input("🔑 輸入金鑰", type="password")
    st.caption("⚠️ 密碼設定後不可修改，系統不記錄，請務必記牢。")

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

# --- 5. 繪製互動網格月曆 ---
def get_shift_info(target_date):
    base_date = date(2026, 1, 30)
    rem = (target_date - base_date).days % 4
    return ("AC", "#D4EDDA", "#155724") if rem in [0, 1] else ("BD", "#FFF3CD", "#856404")

@st.dialog("📝 加密備註編輯器")
def show_note_editor(target_date, user, pwd):
    st.write(f"📅 日期：{target_date} | 👤 持有人：{user}")
    content = ""
    try:
        f = get_encryption_key(pwd)
        res = supabase.table("private_notes").select("content").eq("date", str(target_date)).eq("owner", user).execute()
        if res.data: content = f.decrypt(res.data[0]['content'].encode()).decode()
    except: st.warning("目前無紀錄或金鑰錯誤。")
    
    new_text = st.text_area("內容", value=content, height=150)
    if st.button("🔒 儲存"):
        token = get_encryption_key(pwd).encrypt(new_text.encode()).decode()
        supabase.table("private_notes").upsert({"date": str(target_date), "owner": user, "content": token}).execute()
        st.success("已加密儲存")
        st.rerun()

# 星期表頭
h_cols = st.columns(7)
for i, day_name in enumerate(["日", "一", "二", "三", "四", "五", "六"]):
    h_cols[i].markdown(f"<div class='weekday-header'>{day_name}</div>", unsafe_allow_html=True)

# 月曆網格
cal_obj = calendar.Calendar(firstweekday=6)
weeks = cal_obj.monthdatescalendar(st.session_state.sel_year, st.session_state.sel_month)

for week in weeks:
    w_cols = st.columns(7)
    for i, d in enumerate(week):
        d_str = str(d)
        is_curr = (d.month == st.session_state.sel_month)
        team, bg, txt = get_shift_info(d)
        dot = "📍" if d_str in my_noted_dates else ""
        
        # 這是最關鍵的一步：透過 CSS 強行把按鈕變成你想要的顏色
        btn_label = f"{dot}{d.day}\n{team}" if is_curr else ""
        
        # 注入按鈕樣式
        st.markdown(f"""
            <style>
            button[key="{d_str}"] {{
                background-color: {bg if is_curr else "#ffffff"} !important;
                color: {txt if is_curr else "#cccccc"} !important;
                border: {'1px solid #cbd5e0' if is_curr else 'none'} !important;
            }}
            </style>
        """, unsafe_allow_html=True)
        
        if w_cols[i].button(btn_label, key=d_str):
            if is_curr:
                if current_user == "請選擇" or not user_pwd:
                    st.error("❌ 請先選名字並輸金鑰")
                else:
                    show_note_editor(d, current_user, user_pwd)

# --- 6. 管理區 ---
with st.expander("🛠️ 註冊新人員"):
    n_name = st.text_input("人員姓名")
    if st.button("確認註冊"):
        supabase.table("staff_list").insert({"name":n_name, "team":"A", "shift_type":"日班"}).execute()
        st.rerun()

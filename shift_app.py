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

# --- 2. 網頁造型設定 (找回原本的大網格 CSS) ---
st.set_page_config(page_title="二休二人力看板", layout="centered")
st.markdown("""
    <style>
    .cal-table { width: 100%; border-collapse: collapse; table-layout: fixed; margin-bottom: 20px; }
    .cal-table th { background-color: #f8fafc; color: #1e293b; text-align: center; padding: 10px 2px; border: 1px solid #cbd5e0; }
    .cal-table td { border: 1px solid #cbd5e0; text-align: center; padding: 0; height: 85px; position: relative; }
    
    /* 讓按鈕透明並覆蓋整個格子 */
    .stButton > button {
        background: transparent !important;
        border: none !important;
        width: 100% !important;
        height: 85px !important;
        padding: 0 !important;
        color: inherit !important;
        font-weight: bold !important;
    }
    .note-marker { color: #FF4B4B; font-size: 16px; position: absolute; top: 2px; right: 4px; z-index: 10; pointer-events: none; }
    .cell-label { position: absolute; width: 100%; top: 25%; pointer-events: none; }
    </style>
""", unsafe_allow_html=True)

st.title("🔋 二休二排班助手")

# --- 3. 登入區 (使用 key 記住輸入，切換月份也不會消失) ---
try:
    res_s = supabase.table("staff_list").select("name").execute()
    staff_list = [item['name'] for item in res_s.data]
except: staff_list = []

# 將登入區移到上方，並增加 key 確保資訊不會被重整刷掉
with st.container(border=True):
    c1, c2 = st.columns(2)
    current_user = c1.selectbox("👤 我的名字", ["請選擇"] + staff_list, key="keep_user")
    user_pwd = c2.text_input("🔑 解鎖金鑰", type="password", key="keep_pwd")
    st.caption("⚠️ 密碼設定後不可修改，系統不記錄。")

# --- 4. 月份切換 ---
if 'sel_year' not in st.session_state: st.session_state.sel_year = date.today().year
if 'sel_month' not in st.session_state: st.session_state.sel_month = date.today().month

m_col1, m_col2, m_col3 = st.columns([1, 4, 1])
if m_col1.button("◀️"):
    st.session_state.sel_month = 12 if st.session_state.sel_month == 1 else st.session_state.sel_month - 1
    if st.session_state.sel_month == 12: st.session_state.sel_year -= 1
    st.rerun()
with m_col2: st.markdown(f"<h3 style='text-align: center; margin: 0;'>{st.session_state.sel_year} 年 {st.session_state.sel_month} 月</h3>", unsafe_allow_html=True)
if m_col3.button("▶️"):
    st.session_state.sel_month = 1 if st.session_state.sel_month == 12 else st.session_state.sel_month + 1
    if st.session_state.sel_month == 1: st.session_state.sel_year += 1
    st.rerun()

# --- 5. 抓取標記資料 ---
my_noted_dates = set()
if current_user != "請選擇" and user_pwd:
    try:
        res_n = supabase.table("private_notes").select("date").eq("owner", current_user).execute()
        my_noted_dates = {item['date'] for item in res_n.data}
    except: pass

# --- 6. 彈出編輯器 (st.dialog) ---
@st.dialog("📋 專屬加密備註")
def show_note_editor(target_date, user, pwd):
    st.write(f"📅 日期：{target_date} | 👤 使用者：{user}")
    content = ""
    try:
        f = get_encryption_key(pwd)
        res = supabase.table("private_notes").select("content").eq("date", str(target_date)).eq("owner", user).execute()
        if res.data:
            content = f.decrypt(res.data[0]['content'].encode()).decode()
    except: st.warning("無法解密或無紀錄。")

    new_text = st.text_area("備註內容", value=content, height=180)
    if st.button("🔒 安全加密儲存", use_container_width=True):
        token = get_encryption_key(pwd).encrypt(new_text.encode()).decode()
        supabase.table("private_notes").upsert({"date": str(target_date), "owner": user, "content": token}).execute()
        st.success("儲存成功！")
        st.rerun()

# --- 7. 關鍵：手繪美觀網格 (恢復原本配色) ---
def get_shift_info(target_date):
    base_date = date(2026, 1, 30)
    rem = (target_date - base_date).days % 4
    return ("AC", "#D4EDDA", "#155724") if rem in [0, 1] else ("BD", "#FFF3CD", "#856404")

cal_obj = calendar.Calendar(firstweekday=6)
weeks = cal_obj.monthdatescalendar(st.session_state.sel_year, st.session_state.sel_month)

# 星期表頭
h_cols = st.columns(7)
for i, w_name in enumerate(["日","一","二","三","四","五","六"]):
    h_cols[i].markdown(f"<div style='text-align:center; background:#f8fafc; border:1px solid #cbd5e0; padding:5px 0; font-weight:bold;'>{w_name}</div>", unsafe_allow_html=True)

for week in weeks:
    cols = st.columns(7)
    for i, d in enumerate(week):
        d_str = str(d)
        is_curr = (d.month == st.session_state.sel_month)
        team, bg, txt = get_shift_info(d)
        dot = "📍" if d_str in my_noted_dates else ""
        
        # 視覺呈現：使用 Markdown 繪製漂亮背景格
        cols[i].markdown(f"""
            <div style="background-color:{bg}; opacity:{'1.0' if is_curr else '0.2'}; height:85px; border:1px solid #cbd5e0; position:relative; color:{txt}; text-align:center;">
                <span class="note-marker">{dot}</span>
                <div class="cell-label">
                    <div style="font-size:18px;">{d.day}</div>
                    <div style="font-size:10px;">{team}</div>
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        # 互動層：在格子上方疊加一個透明按鈕
        # 使用 empty() 佔位並將按鈕放上去
        with cols[i]:
            if st.button("", key=f"btn_{d_str}"):
                if is_curr:
                    if current_user == "請選擇" or not user_pwd:
                        st.error("❌ 請先選名字並輸金鑰")
                    else:
                        show_note_editor(d, current_user, user_pwd)

st.divider()
with st.expander("🛠️ 註冊新人員"):
    n_name = st.text_input("註冊姓名")
    if st.button("完成註冊"):
        supabase.table("staff_list").insert({"name":n_name, "team":"A", "shift_type":"日班"}).execute()
        st.rerun()

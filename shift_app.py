import streamlit as st
from datetime import date
import calendar
import base64
from supabase import create_client
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# --- 1. 初始化與工具 ---
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_encryption_key(password: str):
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=b'smt_safety_salt_fixed', iterations=100000)
    return Fernet(base64.urlsafe_b64encode(kdf.derive(password.encode())))

# --- 2. 核心 CSS：強制手機端維持 7 列網格 ---
st.set_page_config(page_title="二休二人力看板", layout="centered")
st.markdown("""
    <style>
    /* 強制月曆容器不換行 */
    .cal-container { width: 100%; overflow-x: auto; }
    .cal-table { width: 100%; border-collapse: collapse; table-layout: fixed; min-width: 320px; }
    .cal-table th, .cal-table td { 
        border: 1px solid #cbd5e0; 
        text-align: center; 
        padding: 0; 
        height: 70px; 
        position: relative; 
    }
    .cal-table th { background-color: #f8fafc; font-size: 12px; height: 30px; }
    
    /* 讓按鈕透明並完全覆蓋格子，且不觸發手機重整 */
    .stButton > button {
        background: transparent !important;
        border: none !important;
        width: 100% !important;
        height: 70px !important;
        position: absolute;
        top: 0; left: 0; z-index: 10;
        color: transparent !important;
    }
    
    /* 內容層 */
    .cell-content { position: relative; z-index: 5; pointer-events: none; padding-top: 10px; }
    .note-marker { color: #FF4B4B; font-size: 14px; position: absolute; top: 2px; right: 4px; }
    .day-num { font-size: 18px; font-weight: bold; line-height: 1; }
    .team-tag { font-size: 9px; margin-top: 2px; }
    </style>
""", unsafe_allow_html=True)

st.title("🔋 二休二排班助手")

# --- 3. 登入控制 (使用 Key 記住輸入) ---
with st.container(border=True):
    c1, c2 = st.columns(2)
    current_user = c1.selectbox("👤 姓名", ["請選擇"] + [item['name'] for item in supabase.table("staff_list").select("name").execute().data], key="u_login")
    user_pwd = c2.text_input("🔑 金鑰", type="password", key="p_login")

# --- 4. 月份切換 ---
if 'sel_year' not in st.session_state: st.session_state.sel_year = date.today().year
if 'sel_month' not in st.session_state: st.session_state.sel_month = date.today().month

m_col1, m_col2, m_col3 = st.columns([1, 2, 1])
if m_col1.button("◀️", key="btn_prev"):
    st.session_state.sel_month = 12 if st.session_state.sel_month == 1 else st.session_state.sel_month - 1
    if st.session_state.sel_month == 12: st.session_state.sel_year -= 1
    st.rerun()
with m_col2: st.markdown(f"<h4 style='text-align:center;'>{st.session_state.sel_year} / {st.session_state.sel_month}</h4>", unsafe_allow_html=True)
if m_col3.button("▶️", key="btn_next"):
    st.session_state.sel_month = 1 if st.session_state.sel_month == 12 else st.session_state.sel_month + 1
    if st.session_state.sel_month == 1: st.session_state.sel_year += 1
    st.rerun()

# --- 5. 抓取標記 ---
my_noted_dates = set()
if current_user != "請選擇" and user_pwd:
    res = supabase.table("private_notes").select("date").eq("owner", current_user).execute()
    my_noted_dates = {item['date'] for item in res.data}

# --- 6. 核心繪製 ---
@st.dialog("📝 私密日誌")
def show_note_editor(target_date, user, pwd):
    st.write(f"📅 日期：{target_date}")
    content = ""
    try:
        f = get_encryption_key(pwd)
        res = supabase.table("private_notes").select("content").eq("date", str(target_date)).eq("owner", user).execute()
        if res.data: content = f.decrypt(res.data[0]['content'].encode()).decode()
    except: pass
    
    new_text = st.text_area("內容", value=content, height=150)
    if st.button("🔒 儲存"):
        token = get_encryption_key(pwd).encrypt(new_text.encode()).decode()
        supabase.table("private_notes").upsert({"date": str(target_date), "owner": user, "content": token}).execute()
        st.rerun()

# 建立 HTML 表格 (確保 7 列不跑版)
cal_obj = calendar.Calendar(firstweekday=6)
weeks = cal_obj.monthdatescalendar(st.session_state.sel_year, st.session_state.sel_month)

html_code = '<div class="cal-container"><table class="cal-table"><thead><tr>'
for d_n in ["日","一","二","三","四","五","六"]: html_code += f'<th>{d_n}</th>'
html_code += '</tr></thead><tbody>'

for week in weeks:
    # 我們需要同步處理 Streamlit 按鈕與 HTML 表格
    # 先在 Streamlit 建立一個橫向 columns 來放透明按鈕
    cols = st.columns(7) 
    
    html_code += '<tr>'
    for i, d in enumerate(week):
        d_str = str(d)
        is_curr = (d.month == st.session_state.sel_month)
        # 排班邏輯 (AC綠 / BD橘)
        rem = (d - date(2026, 1, 30)).days % 4
        team, bg, txt = (("AC", "#D4EDDA", "#155724") if rem in [0, 1] else ("BD", "#FFF3CD", "#856404"))
        dot = '<span class="note-marker">📍</span>' if d_str in my_noted_dates else ""
        
        # 繪製 HTML 背景格
        html_code += f'<td style="background-color:{bg if is_curr else "#ffffff"}; opacity:{"1.0" if is_curr else "0.3"}; color:{txt if is_curr else "#ccc"};">'
        html_code += f'{dot}<div class="cell-content"><div class="day-num">{d.day}</div><div class="team-tag">{team if is_curr else ""}</div></div>'
        html_code += '</td>'
        
        # 放置對應的透明按鈕
        with cols[i]:
            if st.button("", key=f"btn_{d_str}"):
                if is_curr and current_user != "請選擇":
                    show_note_editor(d, current_user, user_pwd)
                elif current_user == "請選擇":
                    st.error("請登入")
    html_code += '</tr>'

html_code += '</tbody></table></div>'

# 將 HTML 表格與透明按鈕重疊 (透過 CSS 負位移，這是 Streamlit 實現此功能的唯一穩定方式)
st.markdown(f"<div style='margin-top: -515px;'>{html_code}</div>", unsafe_allow_html=True)

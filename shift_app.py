import streamlit as st
from datetime import date
import calendar
import base64
from supabase import create_client
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# --- 1. 初始化與工具 (維持不變) ---
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_encryption_key(password: str):
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=b'smt_safety_salt_fixed', iterations=100000)
    return Fernet(base64.urlsafe_b64encode(kdf.derive(password.encode())))

# --- 2. 深度 UI 美化 (關鍵區) ---
st.set_page_config(page_title="二休二排班看板", layout="centered")

st.markdown("""
    <style>
    /* 整體背景色微調 */
    .stApp { background-color: #fcfcfc; }
    
    /* 讓原生按鈕變成高質感的卡片 */
    div.stButton > button {
        height: 90px;
        width: 100%;
        border-radius: 12px;
        border: 1px solid rgba(0,0,0,0.05) !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
        margin: 4px 0px;
        transition: all 0.2s ease-in-out;
        font-family: 'PingFang TC', sans-serif;
    }
    
    /* 按鈕懸停感 */
    div.stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        border: 1px solid #ddd !important;
    }
    
    /* 星期表頭造型 */
    .weekday-header {
        text-align: center;
        background-color: transparent;
        color: #64748b;
        padding: 8px 0;
        font-weight: 600;
        font-size: 13px;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    /* 移除格子之間的預設間隙 */
    div[data-testid="column"] { padding: 2px !important; }
    
    /* 標題與登入區美化 */
    h1 { color: #1e293b; font-weight: 800 !important; }
    .stSelectbox label, .stTextInput label { color: #475569 !important; font-weight: 600 !important; }
    </style>
""", unsafe_allow_html=True)

st.title("🔋 二休二排班助手")

# --- 3. 登入控制台 (質感優化) ---
try:
    res_s = supabase.table("staff_list").select("name").execute()
    staff_list = [item['name'] for item in res_s.data]
except: staff_list = []

with st.container(border=True):
    c1, c2 = st.columns(2)
    # 增加 key 確保資訊不會被重整刷掉
    current_user = c1.selectbox("👤 我的姓名", ["請選擇"] + staff_list, key="u_name")
    user_pwd = c2.text_input("🔑 解鎖金鑰", type="password", key="u_pwd")
    st.markdown("<p style='font-size: 12px; color: #94a3b8;'>💡 密碼設定後不可修改，系統不記錄。</p>", unsafe_allow_html=True)

# --- 4. 月份切換 ---
if 'sel_year' not in st.session_state: st.session_state.sel_year = date.today().year
if 'sel_month' not in st.session_state: st.session_state.sel_month = date.today().month

col_prev, col_title, col_next = st.columns([1, 3, 1])
if col_prev.button("◀️", use_container_width=True):
    st.session_state.sel_month = 12 if st.session_state.sel_month == 1 else st.session_state.sel_month - 1
    if st.session_state.sel_month == 12: st.session_state.sel_year -= 1
    st.rerun()
with col_title:
    st.markdown(f"<h3 style='text-align: center; margin-top: 5px; color:#334155;'>{st.session_state.sel_year} / {st.session_state.sel_month:02d}</h3>", unsafe_allow_html=True)
if col_next.button("▶️", use_container_width=True):
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

# --- 6. 渲染質感看板 ---
def get_shift_info(target_date):
    base_date = date(2026, 1, 30)
    rem = (target_date - base_date).days % 4
    # 使用莫蘭迪色系 (Morandi Colors)
    # AC班: 粉淺綠, BD班: 粉淺橘
    return ("AC", "#E2F1E7", "#2D6A4F") if rem in [0, 1] else ("BD", "#FEF3E2", "#9A3412")

@st.dialog("📝 專屬加密備註")
def show_note_editor(target_date, user, pwd):
    st.write(f"📅 **日期：{target_date}**")
    content = ""
    try:
        f = get_encryption_key(pwd)
        res = supabase.table("private_notes").select("content").eq("date", str(target_date)).eq("owner", user).execute()
        if res.data:
            content = f.decrypt(res.data[0]['content'].encode()).decode()
    except: st.warning("目前無紀錄或解密失敗。")

    new_text = st.text_area("內容 (僅在本地加密)", value=content, height=180)
    if st.button("🔒 存檔並加密", use_container_width=True):
        token = get_encryption_key(pwd).encrypt(new_text.encode()).decode()
        supabase.table("private_notes").upsert({"date": str(target_date), "owner": user, "content": token}).execute()
        st.success("✅ 儲存成功！")
        st.rerun()

# 星期表頭
h_cols = st.columns(7)
for i, d_name in enumerate(["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]):
    h_cols[i].markdown(f"<div class='weekday-header'>{d_name}</div>", unsafe_allow_html=True)

# 月曆核心
cal_obj = calendar.Calendar(firstweekday=6)
weeks = cal_obj.monthdatescalendar(st.session_state.sel_year, st.session_state.sel_month)

for week in weeks:
    cols = st.columns(7)
    for i, d in enumerate(week):
        d_str = str(d)
        is_curr = (d.month == st.session_state.sel_month)
        team, bg, txt = get_shift_info(d)
        
        # 標記樣式
        dot = "📍 " if d_str in my_noted_dates else ""
        btn_label = f"{dot}{d.day}\n{team}" if is_curr else ""
        
        # 利用 CSS 注入顏色
        st.markdown(f"""
            <style>
            button[key="btn_{d_str}"] {{
                background-color: {bg if is_curr else "#ffffff"} !important;
                color: {txt if is_curr else "#cbd5e0"} !important;
                font-size: 16px !important;
                white-space: pre-wrap !important;
            }}
            </style>
        """, unsafe_allow_html=True)
        
        if cols[i].button(btn_label, key=f"btn_{d_str}"):
            if is_curr:
                if current_user == "請選擇" or not user_pwd:
                    st.error("請先登入及輸入金鑰")
                else:
                    show_note_editor(d, current_user, user_pwd)

# --- 7. 管理 ---
st.divider()
with st.expander("🛠️ 人員與權限管理"):
    n_name = st.text_input("人員註冊姓名")
    if st.button("確認註冊"):
        supabase.table("staff_list").insert({"name":n_name, "team":"A", "shift_type":"日班"}).execute()
        st.rerun()

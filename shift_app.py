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

# --- 2. 網頁基礎設定 & 恢復美觀 CSS ---
st.set_page_config(page_title="二休二人力看板", layout="centered")

# 這裡的 CSS 是為了讓原生按鈕看起來像你原本的日曆格子
st.markdown("""
    <style>
    /* 讓按鈕高度增加，像格子一樣 */
    div.stButton > button {
        height: 65px;
        width: 100%;
        border-radius: 5px;
        border: 1px solid #cbd5e0;
        padding: 5px;
        line-height: 1.2;
    }
    /* 強制隱藏按鈕邊框與陰影，模仿表格感 */
    div.stButton > button:hover {
        border: 2px solid #666;
    }
    .header-box {
        text-align: center;
        font-weight: bold;
        background-color: #f8fafc;
        padding: 5px 0;
        border: 1px solid #cbd5e0;
        margin-bottom: 5px;
    }
    </style>
""", unsafe_allow_html=True)

st.title("🔋 二休二排班助手")

# --- 3. 月份切換 ---
if 'sel_year' not in st.session_state: st.session_state.sel_year = date.today().year
if 'sel_month' not in st.session_state: st.session_state.sel_month = date.today().month

col_prev, col_title, col_next = st.columns([1, 4, 1])
if col_prev.button("◀️"):
    if st.session_state.sel_month == 1: st.session_state.sel_month = 12; st.session_state.sel_year -= 1
    else: st.session_state.sel_month -= 1
    st.rerun()
with col_title:
    st.markdown(f"<h3 style='text-align: center; margin: 0;'>{st.session_state.sel_year} 年 {st.session_state.sel_month} 月</h3>", unsafe_allow_html=True)
if col_next.button("▶️"):
    if st.session_state.sel_month == 12: st.session_state.sel_month = 1; st.session_state.sel_year += 1
    else: st.session_state.sel_month += 1
    st.rerun()

# --- 4. 登入區 (位於日曆上方) ---
try:
    res_s = supabase.table("staff_list").select("name").execute()
    staff_list = [item['name'] for item in res_s.data]
except: staff_list = []

with st.container(border=True):
    c1, c2 = st.columns(2)
    current_user = c1.selectbox("👤 我的名字", ["請選擇"] + staff_list)
    user_pwd = c2.text_input("🔑 解鎖金鑰", type="password")

# --- 5. 抓取標記資料 ---
my_noted_dates = set()
if current_user != "請選擇" and user_pwd:
    try:
        res_n = supabase.table("private_notes").select("date").eq("owner", current_user).execute()
        my_noted_dates = {item['date'] for item in res_n.data}
    except: pass

# --- 6. 核心邏輯與日曆繪製 ---
def get_shift_info(target_date):
    base_date = date(2026, 1, 30)
    rem = (target_date - base_date).days % 4
    # AC班為綠色系列，BD班為橘色系列
    return ("AC", "#D4EDDA", "#155724") if rem in [0, 1] else ("BD", "#FFF3CD", "#856404")

cal_obj = calendar.Calendar(firstweekday=6)
weeks = cal_obj.monthdatescalendar(st.session_state.sel_year, st.session_state.sel_month)

# 星期表頭
h_cols = st.columns(7)
for i, day_name in enumerate(["日", "一", "二", "三", "四", "五", "六"]):
    h_cols[i].markdown(f"<div class='header-box'>{day_name}</div>", unsafe_allow_html=True)

# 彈出編輯器
@st.dialog("📋 加密日誌備註")
def show_note_editor(target_date, user, pwd):
    st.write(f"📅 日期：{target_date} | 👤 持有人：{user}")
    st.error("⚠️ 密碼設定後就不能改了，系統不會記錄。")
    content = ""
    try:
        f = get_encryption_key(pwd)
        res = supabase.table("private_notes").select("content").eq("date", target_date).eq("owner", user).execute()
        if res.data: content = f.decrypt(res.data[0]['content'].encode()).decode()
    except: st.warning("目前無紀錄或金鑰錯誤。")
    
    new_text = st.text_area("備註內容", value=content, height=150)
    if st.button("🔒 安全加密儲存", use_container_width=True):
        token = get_encryption_key(pwd).encrypt(new_text.encode()).decode()
        supabase.table("private_notes").upsert({"date": str(target_date), "owner": user, "content": token}).execute()
        st.success("儲存成功！")
        st.rerun()

# 繪製日期格子 (使用色彩按鈕)
for week in weeks:
    cols = st.columns(7)
    for i, d in enumerate(week):
        d_str = str(d)
        is_curr = (d.month == st.session_state.sel_month)
        team, bg_color, txt_color = get_shift_info(d)
        
        # 標記
        dot = "📍" if d_str in my_noted_dates else ""
        label = f"{dot}{d.day}\n{team}"
        
        if not is_curr:
            cols[i].write("") # 非本月留白或顯示淡色
        else:
            # 這是美化關鍵：透過容器注入背景色
            # 雖然 Streamlit 原生按鈕難改顏色，但我們用 markdown 模擬背景
            st.markdown(f"""
                <style>
                button[key="{d_str}"] {{
                    background-color: {bg_color} !important;
                    color: {txt_color} !important;
                }}
                </style>
            """, unsafe_allow_html=True)
            
            if cols[i].button(label, key=d_str, use_container_width=True):
                if current_user == "請選擇" or not user_pwd:
                    st.error("❌ 請先輸入名字與金鑰")
                else:
                    show_note_editor(d, current_user, user_pwd)

# --- 7. 底部管理 ---
st.divider()
with st.expander("🛠️ 註冊新人員"):
    n_name = st.text_input("人員姓名")
    if st.button("註冊"):
        supabase.table("staff_list").insert({"name":n_name, "team":"A", "shift_type":"日班"}).execute()
        st.rerun()

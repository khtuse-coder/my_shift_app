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
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b'smt_safety_salt_fixed',
        iterations=100000
    )
    return Fernet(base64.urlsafe_b64encode(kdf.derive(password.encode())))

# --- 2. 網頁基礎設定 ---
st.set_page_config(page_title="二休二人力看板", layout="centered")
st.title("🔋 二休二排班助手")

# --- 3. 月份切換 ---
if 'sel_year' not in st.session_state: st.session_state.sel_year = date.today().year
if 'sel_month' not in st.session_state: st.session_state.sel_month = date.today().month

col_prev, col_title, col_next = st.columns([1, 3, 1])
if col_prev.button("◀️", use_container_width=True):
    if st.session_state.sel_month == 1: st.session_state.sel_month = 12; st.session_state.sel_year -= 1
    else: st.session_state.sel_month -= 1
    st.rerun()
with col_title:
    st.markdown(f"<h3 style='text-align: center;'>{st.session_state.sel_year} 年 {st.session_state.sel_month} 月</h3>", unsafe_allow_html=True)
if col_next.button("▶️", use_container_width=True):
    if st.session_state.sel_month == 12: st.session_state.sel_month = 1; st.session_state.sel_year += 1
    else: st.session_state.sel_month += 1
    st.rerun()

# --- 4. 加密備註視窗邏輯 ---
@st.dialog("📋 專屬加密備註")
def show_note_editor(target_date, user, pwd):
    st.write(f"📅 日期：{target_date} | 👤 持有人：{user}")
    st.error("⚠️ 密碼設定後就不能改了，系統不會記錄。請務必記牢。")
    
    content = ""
    try:
        f = get_encryption_key(pwd)
        res = supabase.table("private_notes").select("content").eq("date", target_date).eq("owner", user).execute()
        if res.data:
            content = f.decrypt(res.data[0]['content'].encode()).decode()
    except:
        st.warning("目前無紀錄或金鑰無法解密。")

    new_text = st.text_area("備註內容", value=content, height=150)
    if st.button("🔒 安全加密儲存", use_container_width=True):
        f = get_encryption_key(pwd)
        token = f.encrypt(new_text.encode()).decode()
        supabase.table("private_notes").upsert({"date": str(target_date), "owner": user, "content": token}).execute()
        st.success("儲存成功！")
        st.rerun()

# --- 5. 抓取標記資料 ---
# 獲取人員名單
try:
    res_s = supabase.table("staff_list").select("name").execute()
    staff_list = [item['name'] for item in res_s.data]
except: staff_list = []

# 這邊暫時放在下面，為了先抓取標記，我們先定義 user
# 為了穩定，我們把登入區移到日曆「上面」，這樣你一進來設定好，下面日曆就亮了
with st.container(border=True):
    c1, c2 = st.columns(2)
    current_user = c1.selectbox("👤 我的名字", ["請選擇"] + staff_list)
    user_pwd = c2.text_input("🔑 解鎖金鑰", type="password")

my_noted_dates = set()
if current_user != "請選擇" and user_pwd:
    try:
        res_n = supabase.table("private_notes").select("date").eq("owner", current_user).execute()
        my_noted_dates = {item['date'] for item in res_n.data}
    except: pass

# --- 6. 繪製原生按鈕月曆 ---
def get_shift_info(target_date):
    base_date = date(2026, 1, 30)
    rem = (target_date - base_date).days % 4
    return ("AC", "#D4EDDA", "#155724") if rem in [0, 1] else ("BD", "#FFF3CD", "#856404")

cal_obj = calendar.Calendar(firstweekday=6)
weeks = cal_obj.monthdatescalendar(st.session_state.sel_year, st.session_state.sel_month)

# 顯示星期表頭
cols = st.columns(7)
weekdays = ["日", "一", "二", "三", "四", "五", "六"]
for i, day_name in enumerate(weekdays):
    cols[i].markdown(f"<p style='text-align:center; font-weight:bold; background:#f0f2f6; margin:0;'>{day_name}</p>", unsafe_allow_html=True)

# 顯示日期按鈕
for week in weeks:
    cols = st.columns(7)
    for i, d in enumerate(week):
        d_str = str(d)
        is_curr = (d.month == st.session_state.sel_month)
        team, bg, txt = get_shift_info(d)
        
        # 標記符號
        label = f"{d.day}\n{team}"
        if d_str in my_noted_dates:
            label = f"📍{d.day}\n{team}"
        
        # 如果不是本月，顏色變淡
        if not is_curr:
            cols[i].button(label, key=d_str, disabled=True)
        else:
            # 使用原生按鈕觸發
            if cols[i].button(label, key=d_str, use_container_width=True):
                if current_user == "請選擇" or not user_pwd:
                    st.error("請先輸入名字與金鑰")
                else:
                    show_note_editor(d, current_user, user_pwd)

# --- 7. 底部管理區 ---
st.divider()
with st.expander("🛠️ 註冊新人員"):
    n_name = st.text_input("人員姓名")
    if st.button("確認註冊"):
        supabase.table("staff_list").insert({"name":n_name, "team":"A", "shift_type":"日班"}).execute()
        st.rerun()

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

# --- 2. 恢復原本最愛的漂亮表格 CSS ---
st.set_page_config(page_title="二休二人力看板", layout="centered")
st.markdown("""
    <style>
    /* 找回原本大網格造型 */
    .cal-table { width: 100%; border-collapse: collapse; table-layout: fixed; margin-bottom: 20px; }
    .cal-table th { background-color: #f8fafc; color: #1e293b; text-align: center; padding: 10px 2px; border: 1px solid #cbd5e0; font-size: 14px; }
    .cal-table td { border: 1px solid #cbd5e0; text-align: center; padding: 0; height: 85px; position: relative; }
    
    /* 調整內容與點擊連結 */
    .date-link { text-decoration: none; display: flex; flex-direction: column; align-items: center; justify-content: center; width: 100%; height: 100%; -webkit-tap-highlight-color: transparent; }
    .note-marker { color: #FF4B4B; font-size: 16px; position: absolute; top: 2px; right: 4px; }
    .day-num { font-size: 18px; font-weight: bold; }
    .shift-text { font-size: 10px; }
    
    /* 手機點擊視覺回饋 */
    .date-link:active { background-color: rgba(0,0,0,0.1); }
    </style>
""", unsafe_allow_html=True)

st.title("🔋 二休二排班助手")

# --- 3. 登入區 (使用 key 讓手機重整後不需重新輸入) ---
try:
    res_s = supabase.table("staff_list").select("name").execute()
    staff_list = [item['name'] for item in res_s.data]
except: staff_list = []

with st.container(border=True):
    st.subheader("🔑 登入並解鎖")
    c1, c2 = st.columns(2)
    # 使用 key 持久化輸入
    current_user = c1.selectbox("👤 姓名", ["請選擇"] + staff_list, key="u_name")
    user_pwd = c2.text_input("🔑 金鑰", type="password", key="u_pwd")
    st.info("⚠️ 密碼設定後不可修改，系統不記錄，請務必記牢。")

# --- 4. 抓取專屬標記 ---
my_noted_dates = set()
if current_user != "請選擇" and user_pwd:
    try:
        res_n = supabase.table("private_notes").select("date").eq("owner", current_user).execute()
        my_noted_dates = {item['date'] for item in res_n.data}
    except: pass

# --- 5. 月份切換 ---
if 'sel_year' not in st.session_state: st.session_state.sel_year = date.today().year
if 'sel_month' not in st.session_state: st.session_state.sel_month = date.today().month

m1, m2, m3 = st.columns([1, 4, 1])
if m1.button("◀️"):
    st.session_state.sel_month = 12 if st.session_state.sel_month == 1 else st.session_state.sel_month - 1
    if st.session_state.sel_month == 12: st.session_state.sel_year -= 1
    st.rerun()
with m2: st.markdown(f"<h3 style='text-align: center; margin: 0;'>{st.session_state.sel_year} 年 {st.session_state.sel_month} 月</h3>", unsafe_allow_html=True)
if m3.button("▶️"):
    st.session_state.sel_month = 1 if st.session_state.sel_month == 12 else st.session_state.sel_month + 1
    if st.session_state.sel_month == 1: st.session_state.sel_year += 1
    st.rerun()

# --- 6. 生成漂亮月曆 HTML ---
def get_shift_info(target_date):
    base_date = date(2026, 1, 30)
    rem = (target_date - base_date).days % 4
    return ("AC", "#D4EDDA", "#155724") if rem in [0, 1] else ("BD", "#FFF3CD", "#856404")

cal_obj = calendar.Calendar(firstweekday=6)
weeks = cal_obj.monthdatescalendar(st.session_state.sel_year, st.session_state.sel_month)

html_cal = '<table class="cal-table"><thead><tr>'
for w in ["日","一","二","三","四","五","六"]: html_cal += f'<th>{w}</th>'
html_cal += '</tr></thead><tbody>'

for week in weeks:
    html_cal += '<tr>'
    for d in week:
        d_str = str(d)
        is_curr = (d.month == st.session_state.sel_month)
        team, bg, txt = get_shift_info(d)
        dot = "📍" if d_str in my_noted_dates else ""
        
        html_cal += f'<td style="background-color:{bg}; opacity:{"1.0" if is_curr else "0.3"};">'
        if is_curr:
            # 點擊會觸發帶有日期參數的 URL，重整後會被 dialog 捕捉
            html_cal += f'<a href="?d={d_str}" target="_self" class="date-link" style="color:{txt};">'
            html_cal += f'<span class="note-marker">{dot}</span>'
            html_cal += f'<div class="day-num">{d.day}</div>'
            html_cal += f'<div class="shift-text">{team}</div></a>'
        html_cal += '</td>'
    html_cal += '</tr>'
html_cal += '</tbody></table>'
st.markdown(html_cal, unsafe_allow_html=True)

# --- 7. 彈出編輯器 (st.dialog) ---
@st.dialog("📋 專屬加密備註")
def show_note_editor(target_date, user, pwd):
    st.write(f"📅 日期：{target_date} | 👤 持有人：{user}")
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
        st.query_params.clear()
        st.rerun()

# 監控點擊跳轉
if "d" in st.query_params:
    clicked_date = st.query_params["d"]
    if current_user != "請選擇" and user_pwd:
        show_note_editor(clicked_date, current_user, user_pwd)
    else:
        st.error("❌ 請先輸入姓名與金鑰再點擊月曆。")
        if st.button("知道了"): st.query_params.clear(); st.rerun()

# --- 8. 管理 ---
with st.expander("🛠️ 註冊新人員"):
    n_name = st.text_input("註冊姓名")
    if st.button("完成註冊"):
        supabase.table("staff_list").insert({"name":n_name, "team":"A", "shift_type":"日班"}).execute()
        st.rerun()

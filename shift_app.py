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

# --- 2. 網頁造型設定 (找回原本的設計) ---
st.set_page_config(page_title="二休二人力看板", layout="centered")
st.markdown("""
    <style>
    .cal-table { width: 100%; border-collapse: collapse; table-layout: fixed; margin-bottom: 20px; }
    .cal-table th { background-color: #f8fafc; color: #1e293b; text-align: center; padding: 10px 2px; border: 1px solid #cbd5e0; }
    .cal-table td { border: 1px solid #cbd5e0; text-align: center; padding: 0; height: 80px; position: relative; }
    .date-link { text-decoration: none; display: flex; flex-direction: column; align-items: center; justify-content: center; width: 100%; height: 100%; }
    .note-marker { color: #FF4B4B; font-size: 14px; position: absolute; top: 2px; right: 4px; }
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

# --- 4. 核心邏輯 ---
def get_shift_info(target_date):
    base_date = date(2026, 1, 30)
    rem = (target_date - base_date).days % 4
    return ("AC", "#D4EDDA", "#155724") if rem in [0, 1] else ("BD", "#FFF3CD", "#856404")

# 先獲取人員名單供後續使用
try:
    res_s = supabase.table("staff_list").select("name").execute()
    staff_list = [item['name'] for item in res_s.data]
except: staff_list = []

# --- 5. 抓取標記資料 (需要先知道是誰) ---
# 這裡暫時無法在月曆前知道 user，我們改用 Session State 記住上次登入的人
current_user = st.session_state.get("login_user", "請選擇")
user_pwd = st.session_state.get("login_pwd", "")

my_noted_dates = set()
if current_user != "請選擇" and user_pwd:
    try:
        res_n = supabase.table("private_notes").select("date").eq("owner", current_user).execute()
        my_noted_dates = {item['date'] for item in res_n.data}
    except: pass

# --- 6. 生成月曆 HTML ---
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
        opacity = "1.0" if is_curr else "0.3"
        
        # 這裡改用 st.query_params 觸發，但修正 HTML 避免亂碼
        html_cal += f'<td style="background-color:{bg}; opacity:{opacity};">'
        if is_curr:
            html_cal += f'<a href="?d={d_str}" target="_self" class="date-link" style="color:{txt};">'
            html_cal += f'<span class="note-marker">{dot}</span>'
            html_cal += f'<div style="font-weight:bold; font-size:18px;">{d.day}</div>'
            html_cal += f'<div style="font-size:10px;">{team}</div></a>'
        html_cal += '</td>'
    html_cal += '</tr>'
html_cal += '</tbody></table>'
st.markdown(html_cal, unsafe_allow_html=True)

# --- 7. 個人登入區 (移到日曆下方) ---
st.divider()
with st.container(border=True):
    st.subheader("🔑 個人登入控制台")
    c1, c2 = st.columns(2)
    u = c1.selectbox("👤 我的名字", ["請選擇"] + staff_list, index=(staff_list.index(current_user)+1 if current_user in staff_list else 0))
    p = c2.text_input("🔑 解鎖金鑰", value=user_pwd, type="password")
    
    if st.button("確認登入並解鎖標記", use_container_width=True):
        st.session_state.login_user = u
        st.session_state.login_pwd = p
        st.rerun()
    
    st.warning("⚠️ 密碼設定後不可修改，系統不記錄。")

# --- 8. 彈出編輯器 ---
@st.dialog("📋 專屬加密備註")
def show_note_editor(target_date, user, pwd):
    st.write(f"📅 日期：{target_date} | 👤 持有人：{user}")
    content = ""
    try:
        f = get_encryption_key(pwd)
        res = supabase.table("private_notes").select("content").eq("date", str(target_date)).eq("owner", user).execute()
        if res.data:
            content = f.decrypt(res.data[0]['content'].encode()).decode()
    except: st.warning("目前無紀錄或金鑰錯誤。")

    new_text = st.text_area("備註內容", value=content, height=200)
    if st.button("🔒 安全加密儲存", use_container_width=True):
        token = get_encryption_key(pwd).encrypt(new_text.encode()).decode()
        supabase.table("private_notes").upsert({"date": str(target_date), "owner": user, "content": token}).execute()
        st.success("儲存成功！")
        st.query_params.clear()
        st.rerun()

# 監控點擊
if "d" in st.query_params:
    clicked_date = st.query_params["d"]
    if current_user == "請選擇" or not user_pwd:
        st.error("❌ 請先在下方登入區輸入名字與金鑰，才能查看。")
        if st.button("關閉"): st.query_params.clear(); st.rerun()
    else:
        show_note_editor(clicked_date, current_user, user_pwd)

# --- 9. 管理區 ---
with st.expander("🛠️ 註冊新人員"):
    n_name = st.text_input("新成員姓名")
    if st.button("註冊"):
        supabase.table("staff_list").insert({"name":n_name, "team":"A", "shift_type":"日班"}).execute()
        st.rerun()

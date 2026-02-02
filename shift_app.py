import streamlit as st
from datetime import date
import calendar
import base64
from supabase import create_client
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# --- 1. 初始化 ---
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_encryption_key(password: str):
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=b'smt_safety_salt_fixed', iterations=100000)
    return Fernet(base64.urlsafe_b64encode(kdf.derive(password.encode())))

# --- 2. 網頁設定 ---
st.set_page_config(page_title="二休二人力看板", layout="centered")

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

# --- 4. 登入區 (放在日曆上方，方便手機操作) ---
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

# --- 6. 核心繪製邏輯 (恢復原始美觀造型) ---
def get_shift_info(target_date):
    base_date = date(2026, 1, 30)
    rem = (target_date - base_date).days % 4
    return ("AC", "#D4EDDA", "#155724") if rem in [0, 1] else ("BD", "#FFF3CD", "#856404")

cal_obj = calendar.Calendar(firstweekday=6)
weeks = cal_obj.monthdatescalendar(st.session_state.sel_year, st.session_state.sel_month)

# 這裡使用一個隱藏的 selectbox 來當作「點擊觸發器」
if 'clicked_date' not in st.session_state: st.session_state.clicked_date = None

# 使用 CSS 打造你原本最愛的造型
st.markdown("""
    <style>
    .cal-table { width: 100%; border-collapse: collapse; table-layout: fixed; }
    .cal-table th { background-color: #f8fafc; color: #1e293b; text-align: center; padding: 10px 2px; border: 1px solid #cbd5e0; }
    .cal-table td { border: 1px solid #cbd5e0; text-align: center; padding: 0; height: 80px; cursor: pointer; position: relative; }
    .note-marker { color: #FF4B4B; font-size: 14px; position: absolute; top: 2px; right: 4px; }
    .cell-btn { background: none; border: none; width: 100%; height: 100%; padding: 0; cursor: pointer; display: flex; flex-direction: column; align-items: center; justify-content: center; }
    </style>
""", unsafe_allow_html=True)

# 建立星期標題
html_cal = '<table class="cal-table"><thead><tr>'
for w in ["日","一","二","三","四","五","六"]: html_cal += f'<th>{w}</th>'
html_cal += '</tr></thead><tbody>'

# 繪製表格
for week in weeks:
    html_cal += '<tr>'
    for d in week:
        d_str = str(d)
        is_curr = (d.month == st.session_state.sel_month)
        team, bg, txt = get_shift_info(d)
        dot = "📍" if d_str in my_noted_dates else ""
        opacity = "1.0" if is_curr else "0.3"
        
        # 這裡我們用一個 Streamlit 特有的技巧：點擊表格格子其實是在點擊一個隱藏按鈕
        # 但為了美觀，我們先畫出漂亮的 HTML 表格
        html_cal += f'<td style="background-color:{bg}; opacity:{opacity}; color:{txt}; font-weight:bold;">'
        html_cal += f'<span class="note-marker">{dot}</span>'
        html_cal += f'<div>{d.day}</div><div style="font-size:10px;">{team}</div></td>'
    html_cal += '</tr>'
html_cal += '</tbody></table>'

st.markdown(html_cal, unsafe_allow_html=True)

# --- 7. 下方互動區 (針對手機優化：改用日期選擇器觸發編輯) ---
st.write("---")
pick_date = st.date_input("👇 點選或確認日期後開始備註", date.today())

@st.dialog("📝 加密日誌編輯")
def show_note_editor(target_date, user, pwd):
    st.write(f"📅 日期：{target_date} | 👤 持有人：{user}")
    st.error("⚠️ 密碼設定後就不能改了，系統不會記錄。")
    content = ""
    try:
        f = get_encryption_key(pwd)
        res = supabase.table("private_notes").select("content").eq("date", target_date).eq("owner", user).execute()
        if res.data: content = f.decrypt(res.data[0]['content'].encode()).decode()
    except: st.warning("目前無紀錄或金鑰錯誤。")
    
    new_text = st.text_area("備註內容", value=content, height=180)
    if st.button("🔒 安全加密儲存", use_container_width=True):
        token = get_encryption_key(pwd).encrypt(new_text.encode()).decode()
        supabase.table("private_notes").upsert({"date": str(target_date), "owner": user, "content": token}).execute()
        st.success("儲存成功！")
        st.rerun()

if st.button(f"🖊️ 編輯/查看 {pick_date} 的紀錄", use_container_width=True):
    if current_user == "請選擇" or not user_pwd:
        st.error("❌ 請先選名字並輸金鑰")
    else:
        show_note_editor(pick_date, current_user, user_pwd)

# --- 8. 管理區 ---
with st.expander("🛠️ 註冊新人員"):
    n_name = st.text_input("人員姓名")
    if st.button("註冊"):
        supabase.table("staff_list").insert({"name":n_name, "team":"A", "shift_type":"日班"}).execute()
        st.rerun()

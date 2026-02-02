import streamlit as st
from datetime import date
import calendar
import base64
from supabase import create_client
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# --- 1. 雲端連線設定 ---
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- 2. 加密工具函式 ---
def get_encryption_key(password: str):
    password_bytes = password.encode()
    salt = b'smt_safety_salt_2026' 
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=100000)
    key = base64.urlsafe_b64encode(kdf.derive(password_bytes))
    return Fernet(key)

# --- 3. 核心邏輯：計算當班組別 ---
def get_shift_info(target_date):
    base_date = date(2026, 1, 30) 
    remainder = (target_date - base_date).days % 4
    if remainder in [0, 1]: return "AC", "#D4EDDA", "#155724"
    else: return "BD", "#FFF3CD", "#856404"

# --- 4. 網頁設定與 CSS (增加備註小點樣式) ---
st.set_page_config(page_title="二休二人力看板", layout="centered")
st.markdown("""
    <style>
    .cal-table { width: 100%; border-collapse: collapse; table-layout: fixed; }
    .cal-table th { background-color: #e2e8f0; color: #1a202c; text-align: center; padding: 10px 2px; font-weight: bold; border: 1px solid #cbd5e0; }
    .cal-table td { border: 1px solid #cbd5e0; text-align: center; padding: 10px 2px; vertical-align: middle; position: relative; }
    .holiday-box { outline: 3px solid #FF4B4B !important; outline-offset: -3px; }
    .other-month { opacity: 0.3; }
    .note-marker { color: #FF4B4B; font-size: 12px; position: absolute; top: 2px; right: 2px; }
    </style>
""", unsafe_allow_html=True)

st.title("🔋 二休二排班助手")

# --- 5. 月份切換 ---
if 'sel_year' not in st.session_state: st.session_state.sel_year = date.today().year
if 'sel_month' not in st.session_state: st.session_state.sel_month = date.today().month

col1, col2, col3 = st.columns([1, 4, 1])
if col1.button("◀️"):
    if st.session_state.sel_month == 1: st.session_state.sel_month = 12; st.session_state.sel_year -= 1
    else: st.session_state.sel_month -= 1
    st.rerun()
with col2: st.markdown(f"<h3 style='text-align: center; margin: 0;'>{st.session_state.sel_year} 年 {st.session_state.sel_month} 月</h3>", unsafe_allow_html=True)
if col3.button("▶️"):
    if st.session_state.sel_month == 12: st.session_state.sel_month = 1; st.session_state.sel_year += 1
    else: st.session_state.sel_month += 1
    st.rerun()

# --- 6. 抓取有備註的日期 (視覺化關鍵) ---
noted_dates = set()
try:
    # 這裡抓取目前月份的所有備註日期
    res_notes = supabase.table("private_notes").select("date").execute()
    for item in res_notes.data:
        noted_dates.add(item['date'])
except: pass

# --- 7. 生成月曆 ---
cal_obj = calendar.Calendar(firstweekday=6)
month_days = cal_obj.monthdatescalendar(st.session_state.sel_year, st.session_state.sel_month)

html_cal = '<table class="cal-table"><thead><tr>'
for w in ["日","一","二","三","四","五","六"]: html_cal += f'<th>{w}</th>'
html_cal += '</tr></thead><tbody>'

for week in month_days:
    html_cal += '<tr>'
    for d in week:
        is_this_month = (d.month == st.session_state.sel_month)
        # 檢查這天有沒有備註
        has_note = str(d) in noted_dates
        note_icon = "<span class='note-marker'>📌</span>" if has_note else ""
        
        team, bg, txt = get_shift_info(d)
        td_class = "class='other-month'" if not is_this_month else ""
        
        html_cal += f'<td {td_class} style="background-color:{bg}; color:{txt}; font-weight:bold;">{note_icon}{d.day}<br><span style="font-size:10px;">{team}</span></td>'
    html_cal += '</tr>'
html_cal += '</tbody></table>'
st.markdown(html_cal, unsafe_allow_html=True)

st.divider()

# --- 8. 下方管理區 ---
st.subheader("👥 當日名單與紀錄")
pick_date = st.date_input("選擇日期", date.today())

# 載入人員名單
staff_names = []
try:
    res = supabase.table("staff_list").select("name").execute()
    staff_names = [s['name'] for s in res.data]
except: pass

@st.dialog("🔒 加密備註")
def show_private_note_dialog(target_date):
    st.write(f"📅 日期：{target_date}")
    c1, c2 = st.columns(2)
    user = c1.selectbox("你是誰？", staff_names if staff_names else ["管理員"])
    pwd = c2.text_input("輸入解鎖金鑰", type="password")

    if pwd:
        decrypted_content = ""
        try:
            f = get_encryption_key(pwd)
            res = supabase.table("private_notes").select("content").eq("date", target_date).eq("owner", user).execute()
            if res.data:
                decrypted_content = f.decrypt(res.data[0]['content'].encode()).decode()
        except: st.warning("密碼錯誤或無紀錄")

        note_text = st.text_area("備註內容", value=decrypted_content, height=150)
        if st.button("儲存"):
            f = get_encryption_key(pwd)
            token = f.encrypt(note_text.encode()).decode()
            supabase.table("private_notes").upsert({"date": str(target_date), "owner": user, "content": token}).execute()
            st.success("已加密儲存")
            st.rerun()

if st.button(f"📝 編輯/查看 {pick_date} 的私密紀錄", use_container_width=True):
    show_private_note_dialog(pick_date)

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

# --- 2. 網頁造型設定 (手機版觸控優化) ---
st.set_page_config(page_title="二休二人力看板", layout="centered")
st.markdown("""
    <style>
    .cal-table { width: 100%; border-collapse: collapse; table-layout: fixed; margin-bottom: 20px; }
    .cal-table th { background-color: #f8fafc; color: #1e293b; text-align: center; padding: 10px 2px; border: 1px solid #cbd5e0; }
    .cal-table td { border: 1px solid #cbd5e0; text-align: center; padding: 0; height: 85px; position: relative; }
    .date-link { text-decoration: none; display: flex; flex-direction: column; align-items: center; justify-content: center; width: 100%; height: 100%; -webkit-tap-highlight-color: transparent; }
    .note-marker { color: #FF4B4B; font-size: 16px; position: absolute; top: 2px; right: 4px; }
    /* 點擊時的視覺回饋 */
    .date-link:active { background-color: rgba(0,0,0,0.1); }
    </style>
""", unsafe_allow_html=True)

st.title("🔋 二休二排班助手")

# --- 3. 月份切換 ---
if 'sel_year' not in st.session_state: st.session_state.sel_year = date.today().year
if 'sel_month' not in st.session_state: st.session_state.sel_month = date.today().month

m_col1, m_col2, m_col3 = st.columns([1, 4, 1])
if m_col1.button("◀️"):
    if st.session_state.sel_month == 1: st.session_state.sel_month = 12; st.session_state.sel_year -= 1
    else: st.session_state.sel_month -= 1
    st.rerun()
with m_col2: st.markdown(f"<h3 style='text-align: center; margin: 0;'>{st.session_state.sel_year} 年 {st.session_state.sel_month} 月</h3>", unsafe_allow_html=True)
if m_col3.button("▶️"):
    if st.session_state.sel_month == 12: st.session_state.sel_month = 1; st.session_state.sel_year += 1
    else: st.session_state.sel_month += 1
    st.rerun()

# --- 4. 登入狀態管理 ---
# 從 Session 抓取，確保點擊日期重整後，登入狀態還在
current_user = st.session_state.get("login_user", "請選擇")
user_pwd = st.session_state.get("login_pwd", "")

# 抓取標記資料
my_noted_dates = set()
if current_user != "請選擇" and user_pwd:
    try:
        res_n = supabase.table("private_notes").select("date").eq("owner", current_user).execute()
        my_noted_dates = {item['date'] for item in res_n.data}
    except: pass

# --- 5. 生成月曆 HTML ---
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
            # 加入 target="_self" 確保在同分頁跳轉，並加上一些 CSS 優化點擊感
            html_cal += f'<a href="?d={d_str}" target="_self" class="date-link" style="color:{txt};">'
            html_cal += f'<span class="note-marker">{dot}</span>'
            html_cal += f'<div style="font-weight:bold; font-size:18px;">{d.day}</div>'
            html_cal += f'<div style="font-size:10px;">{team}</div></a>'
        html_cal += '</td>'
    html_cal += '</tr>'
html_cal += '</tbody></table>'
st.markdown(html_cal, unsafe_allow_html=True)

# --- 6. 登入控制台 (位於日曆下方) ---
st.divider()
try:
    res_s = supabase.table("staff_list").select("name").execute()
    staff_list = [item['name'] for item in res_s.data]
except: staff_list = []

with st.container(border=True):
    st.subheader("🔑 登入解鎖標記")
    c1, c2 = st.columns(2)
    # 這裡使用 index 來自動選中 Session 裡的人
    u = c1.selectbox("👤 我的名字", ["請選擇"] + staff_list, index=(staff_list.index(current_user)+1 if current_user in staff_list else 0))
    p = c2.text_input("🔑 解鎖金鑰", value=user_pwd, type="password")
    
    if st.button("確認登入並同步標記", use_container_width=True):
        st.session_state.login_user = u
        st.session_state.login_pwd = p
        st.rerun()

# --- 7. 彈出編輯器 (st.dialog) ---
@st.dialog("📋 專屬加密備註")
def show_note_editor(target_date, user, pwd):
    st.write(f"📅 日期：{target_date} | 👤 使用者：{user}")
    
    content = ""
    try:
        f = get_encryption_key(pwd)
        res = supabase.table("private_notes").select("content").eq("date", str(target_date)).eq("owner", user).execute()
        if res.data:
            content = f.decrypt(res.data[0]['content'].encode()).decode()
    except: st.warning("目前無紀錄或金鑰錯誤。")

    new_text = st.text_area("備註內容 (加密後系統不存明文)", value=content, height=180)
    
    if st.button("🔒 安全加密儲存", use_container_width=True):
        token = get_encryption_key(pwd).encrypt(new_text.encode()).decode()
        supabase.table("private_notes").upsert({"date": str(target_date), "owner": user, "content": token}).execute()
        st.success("✅ 儲存成功！")
        # 儲存後清除網址參數，回到乾淨的狀態
        st.query_params.clear()
        st.rerun()

# 關鍵邏輯：偵測網址參數並彈出視窗
if "d" in st.query_params:
    clicked_date = st.query_params["d"]
    # 檢查是否有登入，沒登入就不能看
    if current_user == "請選擇" or not user_pwd:
        st.error("❌ 請先在下方登入區選擇姓名並輸入金鑰，否則無法加載加密內容。")
        if st.button("我知道了"):
            st.query_params.clear()
            st.rerun()
    else:
        # 直接執行 Dialog
        show_note_editor(clicked_date, current_user, user_pwd)

# --- 8. 人員註冊 ---
with st.expander("🛠️ 註冊新人員"):
    n_name = st.text_input("註冊姓名")
    if st.button("完成註冊"):
        supabase.table("staff_list").insert({"name":n_name, "team":"A", "shift_type":"日班"}).execute()
        st.rerun()

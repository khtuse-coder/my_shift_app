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

# --- 2. 網頁基礎設定 (手機版優化) ---
st.set_page_config(page_title="二休二人力看板", layout="centered")
st.markdown("""
    <style>
    .cal-table { width: 100%; border-collapse: collapse; table-layout: fixed; margin-bottom: 20px; }
    .cal-table th { background-color: #f8fafc; color: #1e293b; text-align: center; padding: 8px 2px; border: 1px solid #cbd5e0; font-size: 14px; }
    .cal-table td { border: 1px solid #cbd5e0; text-align: center; padding: 0; height: 70px; position: relative; }
    .note-dot { color: #FF4B4B; font-size: 16px; position: absolute; top: 2px; right: 4px; }
    .date-link { text-decoration: none; display: flex; flex-direction: column; align-items: center; justify-content: center; width: 100%; height: 100%; }
    /* 防止手機點擊出現灰色區塊 */
    a { -webkit-tap-highlight-color: transparent; }
    </style>
""", unsafe_allow_html=True)

st.title("🔋 二休二排班助手")

# --- 3. 月份切換 ---
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

# --- 4. 登入資訊 (現在位於日曆上方，方便手機一眼看到標記) ---
# 先獲取人員名單
try:
    res_s = supabase.table("staff_list").select("name").execute()
    staff_list = [item['name'] for item in res_s.data]
except: staff_list = []

# 手機版登入區：放在選單下方，日曆上方
with st.container(border=True):
    c1, c2 = st.columns(2)
    current_user = c1.selectbox("👤 我的名字", ["請選擇"] + staff_list)
    user_pwd = c2.text_input("🔑 解鎖金鑰", type="password")
    if current_user == "請選擇" or not user_pwd:
        st.caption("💡 請選名字並輸金鑰，月曆才會顯示你的專屬標記 📍")
    else:
        st.success(f"🔓 {current_user} 的標記已解鎖")

# --- 5. 抓取個人標記紀錄 ---
my_noted_dates = set()
if current_user != "請選擇" and user_pwd:
    try:
        res_n = supabase.table("private_notes").select("date").eq("owner", current_user).execute()
        my_noted_dates = {item['date'] for item in res_n.data}
    except: pass

# --- 6. 生成互動月曆 ---
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
        dot = f"<span class='note-dot'>📍</span>" if d_str in my_noted_dates else ""
        
        opacity = "1.0" if is_curr else "0.3"
        html_cal += f"""
            <td style="background-color:{bg}; opacity:{opacity};">
                <a href="?d={d_str}" target="_self" class="date-link" style="color:{txt};">
                    {dot}
                    <div style="font-weight:bold; font-size:16px;">{d.day}</div>
                    <div style="font-size:10px;">{team}</div>
                </a>
            </td>
        """
    html_cal += '</tr>'
html_cal += '</tbody></table>'
st.markdown(html_cal, unsafe_allow_html=True)

# --- 7. 彈出編輯器 (st.dialog) ---
@st.dialog("📋 專屬加密備註")
def show_note_editor(target_date, user, pwd):
    st.write(f"📅 日期：{target_date} | 👤 持有人：{user}")
    
    # 警告文字標註
    st.error("⚠️ 密碼設定後就不能改了，系統不會記錄。請務必記牢，否則資料無法救回。")
    
    content = ""
    try:
        f = get_encryption_key(pwd)
        res = supabase.table("private_notes").select("content").eq("date", target_date).eq("owner", user).execute()
        if res.data:
            content = f.decrypt(res.data[0]['content'].encode()).decode()
    except:
        st.warning("無法解開此日期的資料。可能是新紀錄或金鑰錯誤。")

    new_text = st.text_area("備註內容", value=content, height=180)
    
    if st.button("🔒 安全加密儲存", use_container_width=True):
        f = get_encryption_key(pwd)
        token = f.encrypt(new_text.encode()).decode()
        supabase.table("private_notes").upsert({"date": target_date, "owner": user, "content": token}).execute()
        st.success("儲存成功！")
        st.query_params.clear()
        st.rerun()

# 監控 URL 點擊
if "d" in st.query_params:
    clicked_date = st.query_params["d"]
    if current_user == "請選擇" or not user_pwd:
        st.error("❌ 請先在上方選擇姓名並輸入金鑰，才能查看/編輯。")
        if st.button("關閉"):
            st.query_params.clear()
            st.rerun()
    else:
        show_private_note = clicked_date # 暫存觸發
        show_note_editor(clicked_date, current_user, user_pwd)

# --- 8. 底部管理區 ---
st.divider()
with st.expander("🛠️ 人員與備註管理"):
    st.info("新成員請先在此註冊姓名")
    n_name = st.text_input("新增姓名")
    c_a, c_b = st.columns(2)
    n_team = c_a.selectbox("組別", ["A", "B", "C", "D"], key="new_team")
    n_type = c_b.selectbox("時段", ["日班", "夜班"], key="new_type")
    if st.button("➕ 加入名單", use_container_width=True):
        supabase.table("staff_list").insert({"name":n_name, "team":n_team, "shift_type":n_type}).execute()
        st.rerun()

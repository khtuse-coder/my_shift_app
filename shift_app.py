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
    """將密碼轉為軍規金鑰"""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b'smt_safety_salt_fixed', # 固定鹽值確保同密碼能解同內容
        iterations=100000
    )
    return Fernet(base64.urlsafe_b64encode(kdf.derive(password.encode())))

# --- 2. 網頁基礎設定 ---
st.set_page_config(page_title="二休二人力看板", layout="centered")
st.markdown("""
    <style>
    .cal-table { width: 100%; border-collapse: collapse; table-layout: fixed; }
    .cal-table th { background-color: #f8fafc; color: #1e293b; text-align: center; padding: 10px 2px; border: 1px solid #cbd5e0; }
    .cal-table td { border: 1px solid #cbd5e0; text-align: center; padding: 0; vertical-align: middle; height: 60px; }
    .note-dot { color: #FF4B4B; font-size: 14px; position: absolute; top: 2px; right: 4px; }
    .date-link { text-decoration: none; display: block; width: 100%; height: 100%; padding: 10px 2px; position: relative; }
    </style>
""", unsafe_allow_html=True)

# --- 3. 側邊欄：個人登入區 (註冊也在這裡) ---
with st.sidebar:
    st.title("🔐 個人登入控制台")
    
    # 抓取人員名單
    try:
        res_s = supabase.table("staff_list").select("name").execute()
        staff_list = [item['name'] for item in res_s.data]
    except: staff_list = []

    current_user = st.selectbox("👤 選擇你的姓名 (註冊請見下方)", ["未選取"] + staff_list)
    user_pwd = st.text_input("🔑 輸入解鎖金鑰 (密碼)", type="password")
    
    st.warning("⚠️ **密碼設定後就不能改了，系統不會記錄。** 請務必記牢，否則資料無法救回。")

    if current_user != "未選取" and user_pwd:
        st.success(f"已啟動 {current_user} 的加密模式")

    st.divider()
    with st.expander("➕ 註冊新人員"):
        new_name = st.text_input("人員姓名")
        new_team = st.selectbox("所屬組別", ["A", "B", "C", "D"])
        new_shift = st.selectbox("班別", ["日班", "夜班"])
        if st.button("確認註冊"):
            supabase.table("staff_list").insert({"name":new_name, "team":new_team, "shift_type":new_shift}).execute()
            st.rerun()

# --- 4. 抓取個人標記紀錄 ---
my_noted_dates = set()
if current_user != "未選取":
    try:
        res_n = supabase.table("private_notes").select("date").eq("owner", current_user).execute()
        my_noted_dates = {item['date'] for item in res_n.data}
    except: pass

# --- 5. 月份切換與排班計算 (維持原邏輯) ---
if 'sel_year' not in st.session_state: st.session_state.sel_year = date.today().year
if 'sel_month' not in st.session_state: st.session_state.sel_month = date.today().month

def get_shift_info(target_date):
    base_date = date(2026, 1, 30)
    rem = (target_date - base_date).days % 4
    return ("AC", "#D4EDDA", "#155724") if rem in [0, 1] else ("BD", "#FFF3CD", "#856404")

col1, col2, col3 = st.columns([1, 4, 1])
if col1.button("◀️"):
    if st.session_state.sel_month == 1: st.session_state.sel_month = 12; st.session_state.sel_year -= 1
    else: st.session_state.sel_month -= 1
    st.rerun()
with col2: st.markdown(f"<h3 style='text-align: center;'>{st.session_state.sel_year} 年 {st.session_state.sel_month} 月</h3>", unsafe_allow_html=True)
if col3.button("▶️"):
    if st.session_state.sel_month == 12: st.session_state.sel_month = 1; st.session_state.sel_year += 1
    else: st.session_state.sel_month += 1
    st.rerun()

# --- 6. 生成互動月曆 ---
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
        dot = "<span class='note-dot'>📍</span>" if d_str in my_noted_dates else ""
        
        opacity = "1.0" if is_curr else "0.3"
        html_cal += f"""
            <td style="background-color:{bg}; opacity:{opacity};">
                <a href="?d={d_str}" target="_self" class="date-link" style="color:{txt};">
                    {dot}
                    <div style="font-weight:bold;">{d.day}</div>
                    <div style="font-size:9px;">{team}</div>
                </a>
            </td>
        """
    html_cal += '</tr>'
html_cal += '</tbody></table>'
st.markdown(html_cal, unsafe_allow_html=True)

# --- 7. 點擊後跳出的加密編輯器 ---
@st.dialog("📋 專屬加密備註")
def show_note_editor(target_date, user, pwd):
    st.write(f"📅 日期：{target_date} | 👤 持有人：{user}")
    
    # 解密邏輯
    content = ""
    try:
        f = get_encryption_key(pwd)
        res = supabase.table("private_notes").select("content").eq("date", target_date).eq("owner", user).execute()
        if res.data:
            content = f.decrypt(res.data[0]['content'].encode()).decode()
    except:
        st.error("❌ 金鑰錯誤！無法解開此日期的加密資料。")

    new_text = st.text_area("備註內容", value=content, height=180)
    
    if st.button("🔒 安全加密儲存"):
        f = get_encryption_key(pwd)
        token = f.encrypt(new_text.encode()).decode()
        supabase.table("private_notes").upsert({"date": target_date, "owner": user, "content": token}).execute()
        st.success("加密儲存成功！")
        st.query_params.clear()
        st.rerun()

# 監控 URL 點擊
if "d" in st.query_params:
    clicked_date = st.query_params["d"]
    if current_user == "未選取" or not user_pwd:
        st.error("請先在左側選單選擇姓名並輸入金鑰，才能查看/編輯備註。")
        if st.button("關閉提示"):
            st.query_params.clear()
            st.rerun()
    else:
        show_note_editor(clicked_date, current_user, user_pwd)

st.divider()
st.caption("SMT 產業專用 - 個人加密日誌系統")

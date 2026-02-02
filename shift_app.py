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
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=b'smt_safety_salt', iterations=100000)
    return Fernet(base64.urlsafe_b64encode(kdf.derive(password.encode())))

# --- 2. 頁面設定 ---
st.set_page_config(page_title="二休二人力看板", layout="centered")
st.title("🔋 智能排班日誌系統")

# --- 3. 全局身份登入 (最重要的一步) ---
with st.sidebar:
    st.header("🔑 個人登入")
    staff_list = []
    try:
        res_s = supabase.table("staff_list").select("name").execute()
        staff_list = [item['name'] for item in res_s.data]
    except: pass
    
    current_user = st.selectbox("你是誰？", ["未登入"] + staff_list)
    user_pwd = st.text_input("輸入解鎖金鑰", type="password")
    
    if current_user != "未登入" and user_pwd:
        st.success(f"🔓 {current_user}：加密模式已啟動")

# --- 4. 抓取標記資料 ---
my_noted_dates = set()
if current_user != "未登入":
    try:
        res_n = supabase.table("private_notes").select("date").eq("owner", current_user).execute()
        my_noted_dates = {item['date'] for item in res_n.data}
    except: pass

# --- 5. 互動式月曆生成 ---
# (月份切換代碼維持不變，此處略過以節省空間)

cal_obj = calendar.Calendar(firstweekday=6)
month_days = cal_obj.monthdatescalendar(st.session_state.sel_year, st.session_state.sel_month)

html_cal = '<table class="cal-table"><thead><tr>'
for w in ["日","一","二","三","四","五","六"]: html_cal += f'<th>{w}</th>'
html_cal += '</tr></thead><tbody>'

for week in month_days:
    html_cal += '<tr>'
    for d in week:
        date_str = str(d)
        is_this_month = (d.month == st.session_state.sel_month)
        has_my_note = date_str in my_noted_dates
        team, bg, txt = get_shift_info(d)
        
        # 標記樣式
        note_icon = "📍" if has_my_note else ""
        td_style = f"background-color:{bg}; color:{txt}; font-weight:bold; cursor:pointer;"
        if not is_this_month: td_style += "opacity:0.3;"

        # 將日期包裝成超連結，點擊會帶入 URL 參數
        cell_content = f"""
            <a href='?target_date={date_str}' target='_self' style='text-decoration:none; color:{txt}; display:block; width:100%; height:100%;'>
                <div style='position:relative;'>
                    <span style='font-size:10px; color:#FF4B4B; position:absolute; top:-5px; right:0;'>{note_icon}</span>
                    {d.day}<br><span style='font-size:9px;'>{team}</span>
                </div>
            </a>
        """
        html_cal += f'<td style="{td_style}">{cell_content}</td>'
    html_cal += '</tr>'
html_cal += '</tbody></table>'
st.markdown(html_cal, unsafe_allow_html=True)

# --- 6. 點擊日期的彈出視窗邏輯 ---
@st.dialog("📝 備註編輯器")
def manage_note(target_date, user, pwd):
    st.write(f"📅 日期：{target_date} | 👤 使用者：{user}")
    
    # 自動解密
    existing_text = ""
    try:
        f = get_encryption_key(pwd)
        res = supabase.table("private_notes").select("content").eq("date", target_date).eq("owner", user).execute()
        if res.data:
            existing_text = f.decrypt(res.data[0]['content'].encode()).decode()
    except:
        st.error("❌ 金鑰錯誤，無法讀取加密內容")

    new_note = st.text_area("內容", value=existing_text, height=200)
    
    if st.button("🔒 安全加密並儲存"):
        f = get_encryption_key(pwd)
        token = f.encrypt(new_note.encode()).decode()
        supabase.table("private_notes").upsert({"date": target_date, "owner": user, "content": token}).execute()
        st.success("儲存成功！")
        st.query_params.clear() # 清除 URL 參數
        st.rerun()

# 監控 URL 參數：如果點了日期
if "target_date" in st.query_params:
    if current_user == "未登入" or not user_pwd:
        st.warning("⚠️ 請先在側邊欄登入並輸入金鑰，才能查看備註內容。")
        if st.button("關閉"): 
            st.query_params.clear()
            st.rerun()
    else:
        manage_note(st.query_params["target_date"], current_user, user_pwd)

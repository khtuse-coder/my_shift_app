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
    """將使用者密碼轉為加密金鑰"""
    password_bytes = password.encode()
    salt = b'smt_safety_salt_2026' # 固定鹽值
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password_bytes))
    return Fernet(key)

# --- 3. 國定假日設定 ---
HOLIDAYS = {
    date(2026, 1, 1): "元旦", date(2026, 2, 16): "除夕", date(2026, 2, 17): "春節",
    date(2026, 2, 18): "春節", date(2026, 2, 19): "春節", date(2026, 2, 20): "春節",
    date(2026, 2, 28): "228紀念", date(2026, 4, 4): "兒童/清明", date(2026, 4, 5): "清明節",
    date(2026, 5, 1): "勞動節", date(2026, 6, 19): "端午節", date(2026, 9, 25): "中秋節",
    date(2026, 10, 10): "國慶日"
}

# --- 4. 核心邏輯：計算當班組別 ---
def get_shift_info(target_date):
    base_date = date(2026, 1, 30) 
    remainder = (target_date - base_date).days % 4
    if remainder in [0, 1]:
        return "AC", "#D4EDDA", "#155724" # 綠色
    else:
        return "BD", "#FFF3CD", "#856404" # 橘色

# --- 5. 網頁設定與 CSS ---
st.set_page_config(page_title="二休二人力看板", layout="centered")
st.markdown("""
    <style>
    .cal-table { width: 100%; border-collapse: collapse; table-layout: fixed; }
    .cal-table th { background-color: #e2e8f0; color: #1a202c; text-align: center; padding: 10px 2px; font-weight: bold; border: 1px solid #cbd5e0; }
    .cal-table td { border: 1px solid #cbd5e0; text-align: center; padding: 10px 2px; vertical-align: middle; }
    .holiday-box { outline: 3px solid #FF4B4B !important; outline-offset: -3px; }
    .other-month { opacity: 0.3; }
    .holiday-name { font-size: 9px; color: #FF4B4B; display: block; margin-top: 2px; }
    </style>
""", unsafe_allow_html=True)

st.title("🔋 二休二排班助手")

# --- 6. 月份切換邏輯 ---
if 'sel_year' not in st.session_state: st.session_state.sel_year = date.today().year
if 'sel_month' not in st.session_state: st.session_state.sel_month = date.today().month

col1, col2, col3 = st.columns([1, 4, 1])
if col1.button("◀️"):
    if st.session_state.sel_month == 1:
        st.session_state.sel_month = 12; st.session_state.sel_year -= 1
    else: st.session_state.sel_month -= 1
    st.rerun()

with col2:
    st.markdown(f"<h3 style='text-align: center; margin: 0;'>{st.session_state.sel_year} 年 {st.session_state.sel_month} 月</h3>", unsafe_allow_html=True)

if col3.button("▶️"):
    if st.session_state.sel_month == 12:
        st.session_state.sel_month = 1; st.session_state.sel_year += 1
    else: st.session_state.sel_month += 1
    st.rerun()

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
        h_name = HOLIDAYS.get(d, "")
        td_class = "class='holiday-box'" if h_name else ""
        if not is_this_month: td_class = td_class.replace("class='", "class='other-month ")
        
        team, bg, txt = get_shift_info(d)
        h_label = f"<span class='holiday-name'>{h_name}</span>" if h_name else ""
        html_cal += f'<td {td_class} style="background-color:{bg}; color:{txt}; font-weight:bold;">{d.day}<br><span style="font-size:10px;">{team}</span>{h_label}</td>'
    html_cal += '</tr>'
html_cal += '</tbody></table>'
st.markdown(html_cal, unsafe_allow_html=True)

st.divider()

# --- 8. 當日名單查詢 ---
st.subheader("👥 當日值班名單")
pick_date = st.date_input("選擇日期查詢名單或紀錄", date.today())
team_type, _, _ = get_shift_info(pick_date)
on_duty_teams = ['A', 'C'] if team_type == "AC" else ['B', 'D']

# 嘗試讀取人員名單
staff_names = []
try:
    res = supabase.table("staff_list").select("*").execute()
    all_staff = res.data
    if all_staff:
        staff_names = [s['name'] for s in all_staff]
        on_duty_staff = [s for s in all_staff if s['team'] in on_duty_teams]
        c1, c2 = st.columns(2)
        with c1:
            st.write("☀️ 日班")
            for s in [p for p in on_duty_staff if p['shift_type'] == "日班"]: st.success(f"👤 {s['name']}")
        with c2:
            st.write("🌙 夜班")
            for s in [p for p in on_duty_staff if p['shift_type'] == "夜班"]: st.info(f"👤 {s['name']}")
except:
    st.warning("目前尚無人員資料")

# --- 9. 個人私密加密日誌 (彈出視窗) ---
@st.dialog("🔒 個人加密備註")
def show_private_note_dialog(target_date):
    st.write(f"📅 日期：{target_date}")
    
    # 讓同事選人並輸密碼
    c1, c2 = st.columns(2)
    user = c1.selectbox("你是誰？", staff_names if staff_names else ["請先新增人員"])
    pwd = c2.text_input("輸入解鎖金鑰", type="password", help="忘記金鑰資料將永遠無法找回！")

    if pwd:
        # 嘗試解密現有資料
        decrypted_content = ""
        try:
            f = get_encryption_key(pwd)
            res = supabase.table("private_notes").select("content").eq("date", target_date).eq("owner", user).execute()
            if res.data:
                encrypted_data = res.data[0]['content']
                decrypted_content = f.decrypt(encrypted_data.encode()).decode()
        except:
            st.warning("⚠️ 金鑰無法解密此日期資料。可能是密碼錯誤或當日無紀錄。")

        note_text = st.text_area("備註內容 (只有你知道密碼，雲端存的是亂碼)", value=decrypted_content, height=150)
        
        if st.button("加密儲存"):
            try:
                f = get_encryption_key(pwd)
                encrypted_token = f.encrypt(note_text.encode()).decode()
                supabase.table("private_notes").upsert({
                    "date": str(target_date),
                    "owner": user,
                    "content": encrypted_token
                }).execute()
                st.success("✅ 資料已成功加密並存入雲端！")
                st.rerun()
            except Exception as e:
                st.error(f"儲存失敗: {e}")
    else:
        st.write("請輸入金鑰以解鎖紀錄。")

st.write("---")
if st.button(f"📝 進入 {pick_date} 的加密私密日誌", use_container_width=True):
    show_private_note_dialog(pick_date)

# --- 10. 人員管理 (Expander) ---
with st.expander("🛠️ 人員名單管理"):
    n_name = st.text_input("新增姓名")
    c_a, c_b = st.columns(2)
    n_team = c_a.selectbox("組別", ["A", "B", "C", "D"])
    n_type = c_b.selectbox("時段", ["日班", "夜班"])
    if st.button("➕ 加入名單"):
        supabase.table("staff_list").insert({"name":n_name, "team":n_team, "shift_type":n_type}).execute()
        st.rerun()


























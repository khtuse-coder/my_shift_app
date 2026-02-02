import streamlit as st
import streamlit.components.v1 as components
from datetime import date
import calendar
import base64
from supabase import create_client
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# ===============================
# 1. Supabase / Encryption
# ===============================
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_encryption_key(password: str):
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"smt_safety_salt_fixed",
        iterations=100000,
    )
    return Fernet(base64.urlsafe_b64encode(kdf.derive(password.encode())))

# ===============================
# 2. Page / Session
# ===============================
st.set_page_config(page_title="二休二排班助手", layout="centered")
st.title("🔋 二休二排班助手")

if "clicked_date" not in st.session_state:
    st.session_state.clicked_date = None
if "year" not in st.session_state:
    st.session_state.year = date.today().year
if "month" not in st.session_state:
    st.session_state.month = date.today().month

# ===============================
# 3. Login
# ===============================
try:
    res = supabase.table("staff_list").select("name").execute()
    staff_list = [i["name"] for i in res.data]
except Exception:
    staff_list = []

with st.container(border=True):
    st.subheader("🔑 登入並解鎖")
    c1, c2 = st.columns(2)
    current_user = c1.selectbox("👤 姓名", ["請選擇"] + staff_list)
    user_pwd = c2.text_input("🔑 金鑰", type="password")
    st.caption("⚠️ 密碼僅用於本地加密，系統無法復原")

# ===============================
# 4. Noted Dates
# ===============================
my_noted_dates = set()
if current_user != "請選擇" and user_pwd:
    try:
        r = (
            supabase.table("private_notes")
            .select("date")
            .eq("owner", current_user)
            .execute()
        )
        my_noted_dates = {i["date"] for i in (r.data or [])}
    except Exception:
        pass

# ===============================
# 5. Month Switch
# ===============================
c1, c2, c3 = st.columns([1, 4, 1])

if c1.button("◀️"):
    st.session_state.month -= 1
    if st.session_state.month == 0:
        st.session_state.month = 12
        st.session_state.year -= 1
    st.rerun()

with c2:
    st.markdown(
        f"<h3 style='text-align:center;margin:0.4rem 0'>{st.session_state.year} 年 {st.session_state.month} 月</h3>",
        unsafe_allow_html=True,
    )

if c3.button("▶️"):
    st.session_state.month += 1
    if st.session_state.month == 13:
        st.session_state.month = 1
        st.session_state.year += 1
    st.rerun()

# ===============================
# 6. 二休二邏輯
# ===============================
def get_shift(d: date):
    base = date(2026, 1, 30)
    return "AC" if (d - base).days % 4 in (0, 1) else "BD"

cal = calendar.Calendar(firstweekday=6)
weeks = cal.monthdatescalendar(st.session_state.year, st.session_state.month)

# ===============================
# 7. Calendar HTML（固定 7 欄）
# ===============================
weekdays = ["日", "一", "二", "三", "四", "五", "六"]
today = date.today()
cur_month = st.session_state.month

cells_html = ""
for week in weeks:
    for d in week:
        d_str = str(d)
        is_curr = d.month == cur_month
        team = get_shift(d)
        has_note = d_str in my_noted_dates

        bg = "#d1fae5" if team == "AC" else "#fef3c7"
        cls = "cell"
        if not is_curr:
            cls += " out"
        if d == today:
            cls += " today"

        mark = "📍" if has_note else ""

        cells_html += f"""
        <div class="{cls}" style="background:{bg}"
             onclick="window.location.search='?d={d_str}'">
          <div class="day">{d.day}</div>
          <div class="shift">{team}</div>
          <div class="note">{mark}</div>
        </div>
        """

html = f"""
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
html, body {{
  margin:0;
  padding:0;
  background:#0b0f19;
}}
.wrapper {{
  max-width:760px;
  margin:0 auto;
  padding:12px;
}}
.grid {{
  display:grid;
  grid-template-columns:repeat(7,1fr);
  gap:6px;
}}
.dow {{
  text-align:center;
  font-weight:700;
  color:#ffffff;
}}
.cell {{
  height:60px;
  border-radius:10px;
  text-align:center;
  padding:6px 4px;
  color:#111111;
  cursor:pointer;
}}
.cell.out {{
  background:#1f2937 !important;
  color:#9ca3af;
}}
.cell.today {{
  outline:2px solid #ef4444;
  outline-offset:-2px;
}}
.day {{ font-size:14px; font-weight:800; }}
.shift {{ font-size:11px; }}
.note {{ font-size:11px; }}

@media(max-width:420px){{
  .cell{{height:56px;}}
  .day{{font-size:13px;}}
}}
</style>
</head>
<body>
<div class="wrapper">
  <div class="grid">
    {''.join([f"<div class='dow'>{w}</div>" for w in weekdays])}
    {cells_html}
  </div>
</div>
</body>
</html>
"""

# ⭐⭐⭐ 這一行是你之前少掉的關鍵 ⭐⭐⭐
components.html(
    html,
    height=520,
    scrolling=False
)

# ===============================
# 8. Read query param
# ===============================
clicked = None
try:
    clicked = st.query_params.get("d")
except Exception:
    try:
        clicked = st.experimental_get_query_params().get("d", [None])[0]
    except Exception:
        pass

if clicked:
    st.session_state.clicked_date = clicked

# ===============================
# 9. Note Dialog
# ===============================
@st.dialog("📋 專屬加密備註")
def show_note_editor(target_date, user, pwd):
    st.write(f"📅 日期：{target_date}")
    content = ""

    try:
        f = get_encryption_key(pwd)
        r = (
            supabase.table("private_notes")
            .select("content")
            .eq("date", target_date)
            .eq("owner", user)
            .execute()
        )
        if r.data:
            content = f.decrypt(r.data[0]["content"].encode()).decode()
    except Exception:
        st.warning("⚠️ 無法解密或尚無備註")

    txt = st.text_area("備註內容", value=content, height=160)

    if st.button("🔒 安全加密儲存", use_container_width=True):
        token = get_encryption_key(pwd).encrypt(txt.encode()).decode()
        (
            supabase.table("private_notes")
            .upsert({"date": target_date, "owner": user, "content": token})
            .execute()
        )

        st.session_state.clicked_date = None
        try:
            st.query_params.pop("d", None)
        except Exception:
            pass

        st.success("✅ 已儲存")
        st.rerun()

# ===============================
# 10. Trigger Dialog
# ===============================
if st.session_state.get("clicked_date"):
    if current_user != "請選擇" and user_pwd:
        show_note_editor(
            st.session_state.clicked_date,
            current_user,
            user_pwd,
        )
    else:
        st.warning("❌ 請先選擇人員並輸入金鑰")
        st.session_state.clicked_date = None

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

if "year" not in st.session_state:
    st.session_state.year = date.today().year
if "month" not in st.session_state:
    st.session_state.month = date.today().month

# ===============================
# 3. Login
# ===============================
try:
    res = supabase.table("staff_list").select("name").execute()
    staff_list = [i["name"] for i in (res.data or [])]
except Exception:
    staff_list = []

with st.container(border=True):
    st.subheader("🔑 登入並解鎖")
    c1, c2 = st.columns(2)
    current_user = c1.selectbox("👤 姓名", ["請選擇"] + staff_list)
    user_pwd = c2.text_input("🔑 金鑰", type="password")
    st.caption("⚠️ 密碼僅用於本地加密，系統無法復原")

# ===============================
# 4. Noted Dates（📍 用）
# ===============================
my_noted_dates = set()
if current_user != "請選擇" and user_pwd:
    r = (
        supabase.table("private_notes")
        .select("date")
        .eq("owner", current_user)
        .execute()
    )
    my_noted_dates = {i["date"] for i in (r.data or [])}

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
        f"<h3 style='text-align:center'>{st.session_state.year} 年 {st.session_state.month} 月</h3>",
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
# 7. Calendar（純顯示）
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
        <div class="{cls}" style="background:{bg if is_curr else '#1f2937'}">
          <div class="day">{d.day}</div>
          <div class="shift">{team}</div>
          <div class="note">{mark}</div>
        </div>
        """

html = f"""
<style>
.grid {{ display:grid; grid-template-columns:repeat(7,1fr); gap:6px; }}
.dow {{ text-align:center; font-weight:700; color:white; }}
.cell {{ height:60px; border-radius:10px; padding:6px; text-align:center; }}
.cell.out {{ color:#9ca3af; }}
.cell.today {{ outline:2px solid #ef4444; }}
.day {{ font-weight:800; }}
.shift {{ font-size:11px; }}
.note {{ font-size:11px; }}
</style>
<div class="grid">
{''.join([f"<div class='dow'>{w}</div>" for w in weekdays])}
{cells_html}
</div>
"""

components.html(html, height=120 + len(weeks) * 70)

# ===============================
# 8. 日期選擇 + 備註編輯
# ===============================
st.divider()
st.subheader("🗓 選擇日期")

selected_date = st.date_input(
    "請選擇要編輯的日期",
    value=date(st.session_state.year, st.session_state.month, 1),
)

note_text = ""
if current_user != "請選擇" and user_pwd:
    f = get_encryption_key(user_pwd)
    r = (
        supabase.table("private_notes")
        .select("content")
        .eq("owner", current_user)
        .eq("date", str(selected_date))
        .execute()
    )
    if r.data:
        try:
            note_text = f.decrypt(r.data[0]["content"].encode()).decode()
        except Exception:
            note_text = ""

txt = st.text_area("📝 備註內容", value=note_text, height=160)

if st.button("🔒 安全加密儲存"):
    token = get_encryption_key(user_pwd).encrypt(txt.encode()).decode()
    (
        supabase.table("private_notes")
        .upsert({
            "date": str(selected_date),
            "owner": current_user,
            "content": token,
        })
        .execute()
    )
    st.success("✅ 已儲存")
    st.rerun()

# ===============================
# 9. 本月備註（✅ 已修正）
# ===============================
st.divider()
st.subheader("📚 本月備註")

if current_user != "請選擇" and user_pwd:
    month_start = date(st.session_state.year, st.session_state.month, 1)
    if st.session_state.month == 12:
        next_month_start = date(st.session_state.year + 1, 1, 1)
    else:
        next_month_start = date(st.session_state.year, st.session_state.month + 1, 1)

    r = (
        supabase.table("private_notes")
        .select("date, content")
        .eq("owner", current_user)
        .gte("date", str(month_start))
        .lt("date", str(next_month_start))
        .order("date")
        .execute()
    )

    if not r.data:
        st.caption("（本月尚無備註）")
    else:
        f = get_encryption_key(user_pwd)
        for row in r.data:
            d = row["date"][5:]
            try:
                text = f.decrypt(row["content"].encode()).decode()
            except Exception:
                text = "⚠️ 無法解密"
            st.markdown(f"**{d}**　{text}")

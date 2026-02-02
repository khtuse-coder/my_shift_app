import streamlit as st
from datetime import date
import calendar
import base64
from supabase import create_client
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# ===============================
# 1. 初始化與加密工具
# ===============================
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

# ===============================
# 2. Page 設定
# ===============================
st.set_page_config(page_title="二休二人力看板", layout="centered")
st.title("🔋 二休二排班助手")

if "clicked_date" not in st.session_state:
    st.session_state.clicked_date = None

# ===============================
# 3. 登入
# ===============================
try:
    res = supabase.table("staff_list").select("name").execute()
    staff_list = [i["name"] for i in res.data]
except:
    staff_list = []

with st.container(border=True):
    st.subheader("🔑 登入並解鎖")
    c1, c2 = st.columns(2)
    current_user = c1.selectbox("👤 姓名", ["請選擇"] + staff_list)
    user_pwd = c2.text_input("🔑 金鑰", type="password")
    st.caption("⚠️ 密碼僅用於本地加密，系統無法復原")

# ===============================
# 4. 有備註日期
# ===============================
my_noted_dates = set()
if current_user != "請選擇" and user_pwd:
    try:
        r = supabase.table("private_notes").select("date").eq("owner", current_user).execute()
        my_noted_dates = {i["date"] for i in r.data}
    except:
        pass

# ===============================
# 5. 月份切換
# ===============================
if "year" not in st.session_state:
    st.session_state.year = date.today().year
if "month" not in st.session_state:
    st.session_state.month = date.today().month

c1, c2, c3 = st.columns([1,4,1])
if c1.button("◀️"):
    st.session_state.month -= 1
    if st.session_state.month == 0:
        st.session_state.month = 12
        st.session_state.year -= 1
    st.rerun()

with c2:
    st.markdown(
        f"<h3 style='text-align:center'>{st.session_state.year} / {st.session_state.month}</h3>",
        unsafe_allow_html=True
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
def get_shift(d):
    base = date(2026, 1, 30)
    return "AC" if (d - base).days % 4 in [0, 1] else "BD"

cal = calendar.Calendar(firstweekday=6)
weeks = cal.monthdatescalendar(st.session_state.year, st.session_state.month)

# ===============================
# 7. CSS（固定 Grid）
# ===============================
st.markdown("""
<style>
.calendar-grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 6px;
}
.day-cell {
  height: 72px;
  border-radius: 10px;
  padding: 6px 4px;
  text-align: center;
  cursor: pointer;
}
.day-num {
  font-size: 16px;
  font-weight: bold;
}
.shift {
  font-size: 11px;
  opacity: 0.8;
}
</style>
""", unsafe_allow_html=True)

# ===============================
# 8. 月曆 Grid
# ===============================
st.markdown("#### 📆 點選日期新增 / 查看備註")

html = "<div class='calendar-grid'>"

for week in weeks:
    for d in week:
        d_str = str(d)
        is_curr = d.month == st.session_state.month
        team = get_shift(d)
        mark = "📍" if d_str in my_noted_dates else ""

        bg = "#d1fae5" if team == "AC" else "#fef3c7"
        opacity = "1" if is_curr else "0.3"

        html += f"""
        <div class="day-cell"
             style="background:{bg};opacity:{opacity}"
             onclick="window.parent.postMessage('{d_str}', '*')">
            <div class="day-num">{d.day}</div>
            <div class="shift">{team}</div>
            <div>{mark}</div>
        </div>
        """

html += "</div>"
st.markdown(html, unsafe_allow_html=True)

# ===============================
# 9. JS → Streamlit
# ===============================
st.markdown("""
<script>
window.addEventListener("message", (e) => {
  const v = e.data;
  if (typeof v === "string" && v.includes("-")) {
    fetch("/_stcore/stream", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({clicked_date: v})
    });
  }
});
</script>
""", unsafe_allow_html=True)

if st.session_state.get("clicked_date"):
    if current_user != "請選擇" and user_pwd:
        pass
    else:
        st.error("❌ 請先選擇人員並輸入金鑰")

# ===============================
# 10. 備註 Dialog
# ===============================
@st.dialog("📋 專屬加密備註")
def show_note_editor(target_date, user, pwd):
    st.write(f"📅 日期：{target_date}")
    content = ""
    try:
        f = get_encryption_key(pwd)
        r = supabase.table("private_notes") \
            .select("content") \
            .eq("date", target_date) \
            .eq("owner", user).execute()
        if r.data:
            content = f.decrypt(r.data[0]["content"].encode()).decode()
    except:
        st.warning("⚠️ 無法解密或尚無備註")

    txt = st.text_area("備註內容", value=content, height=160)

    if st.button("🔒 安全加密儲存", use_container_width=True):
        token = get_encryption_key(pwd).encrypt(txt.encode()).decode()
        supabase.table("private_notes").upsert({
            "date": target_date,
            "owner": user,
            "content": token
        }).execute()
        st.session_state.clicked_date = None
        st.success("已儲存")
        st.rerun()

# ===============================
# 11. 觸發 Dialog
# ===============================
if st.session_state.get("clicked_date"):
    show_note_editor(
        st.session_state.clicked_date,
        current_user,
        user_pwd
    )

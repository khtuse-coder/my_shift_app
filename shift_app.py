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
# 2. 基本設定
# ===============================
st.set_page_config(page_title="二休二人力看板", layout="centered")
st.title("🔋 二休二排班助手")

if "clicked_date" not in st.session_state:
    st.session_state.clicked_date = None

# ===============================
# 3. 登入區
# ===============================
try:
    res_s = supabase.table("staff_list").select("name").execute()
    staff_list = [i["name"] for i in res_s.data]
except:
    staff_list = []

with st.container(border=True):
    st.subheader("🔑 登入並解鎖")
    c1, c2 = st.columns(2)
    current_user = c1.selectbox("👤 姓名", ["請選擇"] + staff_list)
    user_pwd = c2.text_input("🔑 金鑰", type="password")
    st.caption("⚠️ 密碼僅用於本地加密，系統無法復原")

# ===============================
# 4. 取得有備註的日期
# ===============================
my_noted_dates = set()
if current_user != "請選擇" and user_pwd:
    try:
        res_n = supabase.table("private_notes") \
            .select("date") \
            .eq("owner", current_user) \
            .execute()
        my_noted_dates = {i["date"] for i in res_n.data}
    except:
        pass

# ===============================
# 5. 月份切換
# ===============================
if "sel_year" not in st.session_state:
    st.session_state.sel_year = date.today().year
if "sel_month" not in st.session_state:
    st.session_state.sel_month = date.today().month

c1, c2, c3 = st.columns([1, 4, 1])
if c1.button("◀️"):
    st.session_state.sel_month -= 1
    if st.session_state.sel_month == 0:
        st.session_state.sel_month = 12
        st.session_state.sel_year -= 1
    st.rerun()

with c2:
    st.markdown(
        f"<h3 style='text-align:center'>{st.session_state.sel_year} 年 {st.session_state.sel_month} 月</h3>",
        unsafe_allow_html=True
    )

if c3.button("▶️"):
    st.session_state.sel_month += 1
    if st.session_state.sel_month == 13:
        st.session_state.sel_month = 1
        st.session_state.sel_year += 1
    st.rerun()

# ===============================
# 6. 二休二邏輯
# ===============================
def get_shift_info(d):
    base_date = date(2026, 1, 30)
    rem = (d - base_date).days % 4
    return "AC" if rem in [0, 1] else "BD"

cal = calendar.Calendar(firstweekday=6)
weeks = cal.monthdatescalendar(
    st.session_state.sel_year,
    st.session_state.sel_month
)

# ===============================
# 7. 月曆（可點擊）
# ===============================
st.markdown("#### 📆 點選日期新增 / 查看備註")

for week in weeks:
    cols = st.columns(7)
    for i, d in enumerate(week):
        d_str = str(d)
        is_curr = d.month == st.session_state.sel_month
        team = get_shift_info(d)
        mark = "📍" if d_str in my_noted_dates else ""

        with cols[i]:
            if not is_curr:
                st.markdown(
                    "<div style='height:90px; opacity:0.3; background:#eee'></div>",
                    unsafe_allow_html=True
                )
            else:
                if st.button(
                    f"{mark}\n{d.day}\n{team}",
                    key=f"day_{d_str}",
                    use_container_width=True
                ):
                    if current_user != "請選擇" and user_pwd:
                        st.session_state.clicked_date = d_str
                    else:
                        st.error("❌ 請先選人員並輸入金鑰")

# ===============================
# 8. 備註 Dialog
# ===============================
@st.dialog("📋 專屬加密備註")
def show_note_editor(target_date, user, pwd):
    st.write(f"📅 日期：{target_date}")
    st.write(f"👤 使用者：{user}")

    content = ""
    try:
        f = get_encryption_key(pwd)
        res = supabase.table("private_notes") \
            .select("content") \
            .eq("date", target_date) \
            .eq("owner", user) \
            .execute()
        if res.data:
            content = f.decrypt(res.data[0]["content"].encode()).decode()
    except:
        st.warning("⚠️ 無法解密或尚無備註")

    new_text = st.text_area("備註內容", value=content, height=160)

    if st.button("🔒 安全加密儲存", use_container_width=True):
        token = get_encryption_key(pwd).encrypt(new_text.encode()).decode()
        supabase.table("private_notes").upsert({
            "date": target_date,
            "owner": user,
            "content": token
        }).execute()

        st.success("✅ 已儲存")
        st.session_state.clicked_date = None
        st.rerun()

# ===============================
# 9. 觸發 Dialog
# ===============================
if st.session_state.clicked_date:
    show_note_editor(
        st.session_state.clicked_date,
        current_user,
        user_pwd
    )

# ===============================
# 10. 管理員註冊
# ===============================
with st.expander("🛠️ 註冊新人員"):
    n_name = st.text_input("姓名")
    if st.button("完成註冊"):
        supabase.table("staff_list").insert({
            "name": n_name,
            "team": "A",
            "shift_type": "日班"
        }).execute()
        st.success("已註冊")
        st.rerun()

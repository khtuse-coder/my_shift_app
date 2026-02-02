import streamlit as st
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
st.set_page_config(page_title="二休二人力看板", layout="centered")
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
        f"<h3 style='text-align:center;margin:0.3rem 0;'>{st.session_state.year} 年 {st.session_state.month} 月</h3>",
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

cal = calendar.Calendar(firstweekday=6)  # 週日開頭
weeks = cal.monthdatescalendar(st.session_state.year, st.session_state.month)

# ===============================
# 7. CSS（手機固定 7 欄 + 一頁看整月）
# ===============================
st.markdown(
    """
<style>
/* 讓上方 Streamlit 預設容器不要太寬，手機更好看 */
.block-container { padding-top: 1.2rem; padding-bottom: 1.2rem; }

/* 固定 7 欄：不使用 st.columns()，用 CSS Grid 自己掌控 */
.cal-wrap{
  max-width: 760px;
  margin: 0 auto;
}

/* 星期列 / 月曆格 都用同一個 grid */
.cal-grid{
  display:grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: 6px;
}

/* 星期標題 */
.cal-dow{
  text-align:center;
  font-weight:700;
  color:#ffffff;
  opacity:0.9;
  padding: 4px 0;
}

/* 日期格 */
.cal-cell{
  background: var(--bg);
  border-radius: 10px;
  border: 1px solid rgba(255,255,255,0.12);
  padding: 6px 4px;
  height: 62px;          /* ⭐ 手機一頁看整月：高度縮小 */
  text-align:center;
  cursor:pointer;
  user-select:none;
  color:#000000;         /* ⭐ 強制黑字 */
  box-shadow: 0 8px 18px rgba(0,0,0,0.18);
  position: relative;
  overflow:hidden;
}

/* 非本月日期淡化 */
.cal-out{ opacity: 0.35; }

/* 今天紅框 */
.cal-today{
  outline: 2px solid #ef4444;
  outline-offset: -2px;
}

/* 日期數字 */
.cal-day{
  font-weight: 800;
  font-size: 14px;
  line-height: 1.1;
}

/* 班別 */
.cal-shift{
  font-size: 11px;
  line-height: 1.1;
  margin-top: 2px;
}

/* 記號 */
.cal-note{
  font-size: 11px;
  line-height: 1;
  margin-top: 2px;
}

/* 手機再更緊湊一點 */
@media (max-width: 420px){
  .cal-grid{ gap: 5px; }
  .cal-cell{
    height: 56px;
    padding: 5px 3px;
    border-radius: 9px;
  }
  .cal-day{ font-size: 13px; }
  .cal-shift{ font-size: 10px; }
}
</style>
""",
    unsafe_allow_html=True,
)

# ===============================
# 8. Calendar UI（固定 7 欄）
# ===============================
st.markdown("#### 📆 點選日期新增 / 查看備註")

weekdays = ["日", "一", "二", "三", "四", "五", "六"]

# 星期列
st.markdown(
    "<div class='cal-wrap'><div class='cal-grid'>"
    + "".join([f"<div class='cal-dow'>{w}</div>" for w in weekdays])
    + "</div></div>",
    unsafe_allow_html=True,
)

# 日期格（點擊用 query param 傳值，避免 Streamlit columns 手機塌掉）
html = "<div class='cal-wrap'><div class='cal-grid'>"

today = date.today()
cur_month = st.session_state.month

for week in weeks:
    for d in week:
        d_str = str(d)
        is_curr = d.month == cur_month
        team = get_shift(d)
        has_note = d_str in my_noted_dates

        bg = "#d1fae5" if team == "AC" else "#fef3c7"
        cls = "cal-cell"
        if not is_curr:
            cls += " cal-out"
        if d == today:
            cls += " cal-today"

        mark = "📍" if has_note else ""

        # ⭐ 點擊：把 d 放進 query string，觸發 rerun，再由 st.query_params 讀取
        html += f"""
        <div class="{cls}" style="--bg:{bg}"
             onclick="
               const u = new URL(window.location.href);
               u.searchParams.set('d', '{d_str}');
               window.location.href = u.toString();
             ">
          <div class="cal-day">{d.day}</div>
          <div class="cal-shift">{team}</div>
          <div class="cal-note">{mark}</div>
        </div>
        """

html += "</div></div>"
st.markdown(html, unsafe_allow_html=True)

# ===============================
# 9. 讀取 query param → 觸發 dialog
# ===============================
# Streamlit 版本不同，query params API 可能略有差異，這裡做兼容
clicked = None
try:
    clicked = st.query_params.get("d")
except Exception:
    try:
        clicked = st.experimental_get_query_params().get("d", [None])[0]
    except Exception:
        clicked = None

if clicked:
    st.session_state.clicked_date = clicked

# ===============================
# 10. Note Dialog
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

        # 清掉點擊狀態 + 清掉 query param，避免一直反覆彈出
        st.session_state.clicked_date = None
        try:
            st.query_params.pop("d", None)
        except Exception:
            try:
                st.experimental_set_query_params()
            except Exception:
                pass

        st.success("✅ 已儲存")
        st.rerun()

# ===============================
# 11. Trigger Dialog
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
        # 同步清 query param，避免再次觸發
        try:
            st.query_params.pop("d", None)
        except Exception:
            try:
                st.experimental_set_query_params()
            except Exception:
                pass

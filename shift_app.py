import streamlit as st
from datetime import date
import calendar
from supabase import create_client

# --- 1. 雲端連線設定 ---
SUPABASE_URL = ["SUPABASE_URL"]
SUPABASE_KEY = "sb_publishable_mCFZYLTC-HHMuyIqGN9xvA_c-FIL5aV"
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- 2. 國定假日設定 (包含 2026 與 2027) ---
# 這樣你明年也不用改程式了
HOLIDAYS = {
    # 2026 年
    date(2026, 1, 1): "元旦", date(2026, 2, 16): "除夕", date(2026, 2, 17): "春節",
    date(2026, 2, 18): "春節", date(2026, 2, 19): "春節", date(2026, 2, 20): "春節",
    date(2026, 2, 28): "228紀念", date(2026, 4, 4): "兒童/清明", date(2026, 4, 5): "清明節",
    date(2026, 5, 1): "勞動節", date(2026, 6, 19): "端午節", date(2026, 9, 25): "中秋節",
    date(2026, 10, 10): "國慶日",
    # 2027 年 (預估)
    date(2027, 1, 1): "元旦", date(2027, 2, 6): "除夕", date(2027, 2, 7): "春節",
    date(2027, 2, 8): "春節", date(2027, 2, 9): "春節", date(2027, 2, 28): "228紀念",
    date(2027, 4, 4): "兒童節", date(2027, 4, 5): "清明節", date(2027, 5, 1): "勞動節",
    date(2027, 6, 9): "端午節", date(2027, 9, 15): "中秋節", date(2027, 10, 10): "國慶日"
}

# --- 3. 核心邏輯：計算當班組別 ---
def get_shift_info(target_date):
    base_date = date(2026, 1, 30) # 基準日
    remainder = (target_date - base_date).days % 4
    if remainder in [0, 1]:
        return "AC", "#D4EDDA", "#155724" # 綠色
    else:
        return "BD", "#FFF3CD", "#856404" # 橘色

# --- 4. 網頁設定與 CSS ---
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

# --- 5. 月份切換 ---
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

# --- 6. 月曆 HTML ---
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

# --- 7. 當日名單與管理 ---
st.subheader("👥 當日值班名單")
pick_date = st.date_input("查詢具體日期", date.today())
team_type, _, _ = get_shift_info(pick_date)
on_duty_teams = ['A', 'C'] if team_type == "AC" else ['B', 'D']

try:
    res = supabase.table("staff_list").select("*").execute()
    all_staff = res.data
    if all_staff:
        on_duty_staff = [s for s in all_staff if s['team'] in on_duty_teams]
        c1, c2 = st.columns(2)
        with c1:
            st.write("☀️ 日班")
            for s in [p for p in on_duty_staff if p['shift_type'] == "日班"]: st.success(f"👤 {s['name']}")
        with c2:
            st.write("🌙 夜班")
            for s in [p for p in on_duty_staff if p['shift_type'] == "夜班"]: st.info(f"👤 {s['name']}")
except: pass

with st.expander("🛠️ 人員與備註管理"):
    n_name = st.text_input("新增姓名")
    c_a, c_b = st.columns(2)
    n_team = c_a.selectbox("組別", ["A", "B", "C", "D"])
    n_type = c_b.selectbox("時段", ["日班", "夜班"])
    if st.button("➕ 加入"):
        supabase.table("staff_list").insert({"name":n_name, "team":n_team, "shift_type":n_type}).execute()
        st.rerun()



import streamlit as st
from datetime import date
import calendar
from supabase import create_client

# --- 1. 雲端連線設定 ---
SUPABASE_URL = "https://iomqohzyuwtbfxnoavjf.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImlvbXFvaHp5dXd0YmZ4bm9hdmpmIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njk2NTUxMzUsImV4cCI6MjA4NTIzMTEzNX0.raqhaFGXC50xWODruMD0M26HgDq0XC74KaOe48UpXP8"
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- 2. 核心邏輯：計算當班組別 ---
def get_shift_info(target_date):
    base_date = date(2026, 1, 30) # 基準日
    remainder = (target_date - base_date).days % 4
    if remainder in [0, 1]:
        return "AC", "#D4EDDA", "#155724" # 綠色 (AC 班)
    else:
        return "BD", "#FFF3CD", "#856404" # 橘色 (BD 班)

# --- 3. 網頁設定與 CSS ---
st.set_page_config(page_title="二休二排班看板", layout="centered")

st.markdown("""
    <style>
    .cal-table { width: 100%; border-collapse: collapse; table-layout: fixed; margin-bottom: 10px; }
    .cal-table th { 
        background-color: #e2e8f0 !important; 
        color: #1a202c !important; 
        text-align: center; 
        padding: 10px 2px; 
        font-size: 15px; 
        font-weight: bold;
        border: 1px solid #cbd5e0; 
    }
    .cal-table td { 
        border: 1px solid #cbd5e0; 
        text-align: center; 
        padding: 12px 2px; 
        vertical-align: middle;
    }
    /* 讓按鈕置中對齊文字 */
    .stButton button { width: 100%; }
    </style>
""", unsafe_allow_html=True)

st.title("🔋 二休二班表助手")

# --- 4. [置頂] 月份切換與月曆 ---
st.subheader("🗓️ 月份排班預覽")

# 初始化 Session State (如果還沒有記錄年份與月份)
if 'sel_year' not in st.session_state:
    st.session_state.sel_year = date.today().year
if 'sel_month' not in st.session_state:
    st.session_state.sel_month = date.today().month

# 建立左右按鈕導覽列
col1, col2, col3 = st.columns([1, 3, 1])

# 上一個月按鈕
if col1.button("◀️"):
    if st.session_state.sel_month == 1:
        st.session_state.sel_month = 12
        st.session_state.sel_year -= 1
    else:
        st.session_state.sel_month -= 1
    st.rerun()

# 顯示目前的年月
with col2:
    st.markdown(f"<h3 style='text-align: center; margin: 0;'>{st.session_state.sel_year} 年 {st.session_state.sel_month} 月</h3>", unsafe_allow_html=True)

# 下一個月按鈕
if col3.button("▶️"):
    if st.session_state.sel_month == 12:
        st.session_state.sel_month = 1
        st.session_state.sel_year += 1
    else:
        st.session_state.sel_month += 1
    st.rerun()

# 生成月曆 HTML
cal = calendar.monthcalendar(st.session_state.sel_year, st.session_state.sel_month)
html_cal = '<table class="cal-table"><thead><tr>'
for w in ["日","一","二","三","四","五","六"]:
    html_cal += f'<th>{w}</th>'
html_cal += '</tr></thead><tbody>'

for week in cal:
    html_cal += '<tr>'
    for day in week:
        if day == 0:
            html_cal += '<td></td>'
        else:
            cur_date = date(st.session_state.sel_year, st.session_state.sel_month, day)
            team, bg, txt = get_shift_info(cur_date)
            html_cal += f'<td style="background-color:{bg}; color:{txt}; font-weight:bold;">{day}<br><span style="font-size:10px;">{team}</span></td>'
    html_cal += '</tr>'
html_cal += '</tbody></table>'

st.markdown(html_cal, unsafe_allow_html=True)
st.caption("🟢 綠色: AC班 | 🟡 橘色: BD班")

st.divider()

# --- 5. 當日值班人員 ---
st.subheader("👥 當日值班名單")
# 查詢日期預設為今天
pick_date = st.date_input("選擇具體查詢日期", date.today())
team_type, _, _ = get_shift_info(pick_date)
on_duty_teams = ['A', 'C'] if team_type == "AC" else ['B', 'D']

try:
    res = supabase.table("staff_list").select("*").execute()
    all_staff = res.data
    if all_staff:
        on_duty_staff = [s for s in all_staff if s['team'] in on_duty_teams]
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### ☀️ 日班")
            day_p = [p for p in on_duty_staff if p['shift_type'] == "日班"]
            for s in day_p: st.success(f"👤 {s['name']}")
            if not day_p: st.write("無人上班")
        with c2:
            st.markdown("#### 🌙 夜班")
            night_p = [p for p in on_duty_staff if p['shift_type'] == "夜班"]
            for s in night_p: st.info(f"👤 {s['name']}")
            if not night_p: st.write("無人上班")
except:
    pass

# --- 6. 管理工具 ---
with st.expander("🛠️ 人員與備註管理"):
    st.write("### ✨ 新增員工")
    n_name = st.text_input("姓名")
    col_a, col_b = st.columns(2)
    n_team = col_a.selectbox("小組", ["A", "B", "C", "D"])
    n_type = col_b.selectbox("時段", ["日班", "夜班"])
    if st.button("➕ 加入名單"):
        if n_name:
            supabase.table("staff_list").insert({"name":n_name, "team":n_team, "shift_type":n_type}).execute()
            st.rerun()
    
    st.write("--- ### 📝 今日記事")
    note = st.text_area("備註內容")
    if st.button("🚀 儲存紀錄"):
        supabase.table("shift_records").insert({"user_id":"Old_Cha", "shift_date":str(pick_date), "shift_type":team_type, "note":note}).execute()
        st.success("已儲存！")

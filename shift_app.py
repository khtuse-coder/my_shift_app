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
    base_date = date(2026, 1, 30) # 1/30 為 AC 班第一天
    remainder = (target_date - base_date).days % 4
    if remainder in [0, 1]:
        return "AC", "#D4EDDA", "#155724" # 綠色
    else:
        return "BD", "#FFF3CD", "#856404" # 橘色

# --- 3. 網頁設定 ---
st.set_page_config(page_title="二休二排班看板", layout="centered")

# 用 CSS 讓表格在手機上更好看
st.markdown("""
    <style>
    .cal-table { width: 100%; border-collapse: collapse; table-layout: fixed; }
    .cal-table th, .cal-table td { border: 1px solid #ddd; text-align: center; padding: 8px 2px; font-size: 14px; }
    .cal-table th { background-color: #f0f2f6; }
    </style>
""", unsafe_allow_html=True)

st.title("🔋 二休二班表助手")

# --- 4. [置頂] 排班月曆 ---
st.subheader("🗓️ 月份排班預覽")

c1, c2 = st.columns(2)
this_date = date.today()
sel_year = c1.selectbox("年份", range(2025, 2030), index=(this_date.year - 2025))
sel_month = c2.selectbox("月份", range(1, 13), index=(this_date.month - 1))

# 生成月曆
cal = calendar.monthcalendar(sel_year, sel_month)
html_cal = '<table class="cal-table"><tr>'
for w in ["日","一","二","三","四","五","六"]:
    html_cal += f'<th>{w}</th>'
html_cal += '</tr>'

for week in cal:
    html_cal += '<tr>'
    for day in week:
        if day == 0:
            html_cal += '<td></td>'
        else:
            cur_date = date(sel_year, sel_month, day)
            team, bg, txt = get_shift_info(cur_date)
            html_cal += f'<td style="background-color:{bg}; color:{txt}; font-weight:bold;">{day}<br><span style="font-size:10px;">{team}</span></td>'
    html_cal += '</tr>'
html_cal += '</table>'

# 只有這一行會印出月曆，確保不會看到代碼
st.markdown(html_cal, unsafe_allow_html=True)
st.caption("🟢 綠色: AC班 | 🟡 橘色: BD班")

st.divider()

# --- 5. 當日值班人員 ---
st.subheader("👥 人員查詢")
pick_date = st.date_input("選擇日期", date.today())
team_type, _, _ = get_shift_info(pick_date)
on_duty_teams = ['A', 'C'] if team_type == "AC" else ['B', 'D']

try:
    res = supabase.table("staff_list").select("*").execute()
    all_staff = res.data
    if all_staff:
        on_duty_staff = [s for s in all_staff if s['team'] in on_duty_teams]
        col1, col2 = st.columns(2)
        with col1:
            st.write("☀️ **日班**")
            for s in [p for p in on_duty_staff if p['shift_type'] == "日班"]:
                st.success(f"👤 {s['name']}")
        with col2:
            st.write("🌙 **夜班**")
            for s in [p for p in on_duty_staff if p['shift_type'] == "夜班"]:
                st.info(f"👤 {s['name']}")
except:
    st.write("尚未建立名單")

# --- 6. 管理工具 (收納在下面) ---
with st.expander("🛠️ 人員與備註管理"):
    st.write("### ✨ 新增員工")
    n_name = st.text_input("姓名")
    c_a, c_b = st.columns(2)
    n_team = c_a.selectbox("小組", ["A", "B", "C", "D"])
    n_type = c_b.selectbox("時段", ["日班", "夜班"])
    if st.button("➕ 加入"):
        if n_name:
            supabase.table("staff_list").insert({"name":n_name, "team":n_team, "shift_type":n_type}).execute()
            st.rerun()
    
    st.write("---")
    st.write("### 📝 今日備註")
    note = st.text_area("內容")
    if st.button("🚀 儲存"):
        supabase.table("shift_records").insert({"user_id":"Old_Cha", "shift_date":str(pick_date), "shift_type":team_type, "note":note}).execute()
        st.success("已儲存")

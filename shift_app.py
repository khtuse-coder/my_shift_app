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

# --- 3. 網頁設定與優化樣式 ---
st.set_page_config(page_title="二休二排班看板", layout="centered")

# 強化星期標題的視覺效果
st.markdown("""
    <style>
    .cal-table { width: 100%; border-collapse: collapse; table-layout: fixed; margin-bottom: 10px; }
    .cal-table th { 
        background-color: #e2e8f0 !important; /* 強制淺灰色背景 */
        color: #1a202c !important;           /* 強制深黑色文字 */
        text-align: center; 
        padding: 12px 2px; 
        font-size: 16px; 
        font-weight: bold;
        border: 1px solid #cbd5e0; 
    }
    .cal-table td { 
        border: 1px solid #cbd5e0; 
        text-align: center; 
        padding: 12px 2px; 
        vertical-align: middle;
    }
    </style>
""", unsafe_allow_html=True)

st.title("🔋 二休二班表助手")

# --- 4. [置頂] 排班月曆 ---
st.subheader("🗓️ 月份排班預覽")

c1, c2 = st.columns(2)
this_date = date.today()
sel_year = c1.selectbox("年份", range(2025, 2030), index=(this_date.year - 2025))
sel_month = c2.selectbox("月份", range(1, 13), index=(this_date.month - 1))

# 生成月曆 HTML
cal = calendar.monthcalendar(sel_year, sel_month)
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
            cur_date = date(sel_year, sel_month, day)
            team, bg, txt = get_shift_info(cur_date)
            html_cal += f'<td style="background-color:{bg}; color:{txt}; font-weight:bold;">{day}<br><span style="font-size:11px;">{team}</span></td>'
    html_cal += '</tr>'
html_cal += '</tbody></table>'

st.markdown(html_cal, unsafe_allow_html=True)
st.caption("🟢 綠色: AC班當班 | 🟡 橘色: BD班當班")

st.divider()

# --- 5. 當日值班人員 (回歸姓名顯示) ---
st.subheader("👥 當日值班名單")
pick_date = st.date_input("選擇日期查詢人員", date.today())
team_type, _, _ = get_shift_info(pick_date)
on_duty_teams = ['A', 'C'] if team_type == "AC" else ['B', 'D']

try:
    res = supabase.table("staff_list").select("*").execute()
    all_staff = res.data
    if all_staff:
        on_duty_staff = [s for s in all_staff if s['team'] in on_duty_teams]
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### ☀️ 日班")
            day_people = [p for p in on_duty_staff if p['shift_type'] == "日班"]
            for s in day_people: st.success(f"👤 {s['name']}")
            if not day_people: st.write("無人上班")
        with col2:
            st.markdown("#### 🌙 夜班")
            night_people = [p for p in on_duty_staff if p['shift_type'] == "夜班"]
            for s in night_people: st.info(f"👤 {s['name']}")
            if not night_people: st.write("無人上班")
    else:
        st.info("💡 目前名單為空，請從下方展開『管理工具』來新增員工。")
except Exception as e:
    st.error(f"讀取名單失敗: {e}")

# --- 6. 管理工具 ---
with st.expander("🛠️ 人員與備註管理"):
    st.write("### ✨ 快速新增員工")
    n_name = st.text_input("輸入員工姓名")
    c_a, c_b = st.columns(2)
    n_team = c_a.selectbox("所屬小組", ["A", "B", "C", "D"])
    n_type = c_b.selectbox("班別時段", ["日班", "夜班"])
    if st.button("➕ 加入名單", use_container_width=True):
        if n_name:
            supabase.table("staff_list").insert({"name":n_name, "team":n_team, "shift_type":n_type}).execute()
            st.rerun()
    
    st.write("---")
    st.write("### 📝 今日記事備註")
    note = st.text_area("內容...")
    if st.button("🚀 儲存到雲端", use_container_width=True):
        supabase.table("shift_records").insert({"user_id":"Old_Cha", "shift_date":str(pick_date), "shift_type":team_type, "note":note}).execute()
        st.success("已成功存檔！")

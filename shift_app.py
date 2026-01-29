import streamlit as st
from datetime import date, timedelta
import calendar
from supabase import create_client

# --- 1. 雲端連線設定 (請檢查金鑰是否完整) ---
SUPABASE_URL = "https://iomqohzyuwtbfxnoavjf.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImlvbXFvaHp5dXd0YmZ4bm9hdmpmIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njk2NTUxMzUsImV4cCI6MjA4NTIzMTEzNX0.raqhaFGXC50xWODruMD0M26HgDq0XC74KaOe48UpXP8"
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- 2. 核心邏輯：計算哪組當班 ---
def get_shift_info(target_date):
    # 基準日：2026/01/30 是 AC 班上班的第一天
    base_date = date(2026, 1, 30)
    delta = (target_date - base_date).days
    remainder = delta % 4
    
    if remainder in [0, 1]:
        return "AC", "#D4EDDA", "#155724"  # 綠色 (AC 班)
    else:
        return "BD", "#FFF3CD", "#856404"  # 橘色 (BD 班)

# --- 3. 網頁設定 ---
st.set_page_config(page_title="二休二人力看板", layout="centered")
st.title("🔋 二休二班表助手")

# --- 4. [置頂] 月曆顯示區塊 ---
st.subheader("🗓️ 月份排班預覽")

# 月份選擇器 (預設今年今月)
col_y, col_m = st.columns(2)
this_year = date.today().year
this_month = date.today().month
sel_year = col_y.selectbox("選擇年份", range(2025, 2030), index=(this_year - 2025))
sel_month = col_m.selectbox("選擇月份", range(1, 13), index=(this_month - 1))

# 生成月曆 HTML 內容
cal = calendar.monthcalendar(sel_year, sel_month)
weekdays = ["日", "一", "二", "三", "四", "五", "六"]

# 構建 HTML 表格 (這段就是你剛才看到的骨架，我讓它變回漂漂亮亮的表格)
html_cal = '<table style="width:100%; text-align:center; border-collapse: collapse; font-family: sans-serif; font-size: 14px;">'
html_cal += '<tr style="background-color: #f8f9fa;">' + ''.join([f'<th style="padding:10px; border:1px solid #ddd;">{w}</th>' for w in weekdays]) + '</tr>'

for week in cal:
    html_cal += '<tr>'
    for day in week:
        if day == 0:
            html_cal += '<td style="padding:15px; border:1px solid #ddd;"></td>'
        else:
            current_date = date(sel_year, sel_month, day)
            team, bg, text_color = get_shift_info(current_date)
            html_cal += f'''
                <td style="padding:10px; border:1px solid #ddd; background-color: {bg}; color: {text_color}; font-weight: bold;">
                    {day}<br><span style="font-size: 0.8em;">{team}</span>
                </td>
            '''
    html_cal += '</tr>'
html_cal += '</table>'

# 這裡最重要！要用 st.markdown 並加上 unsafe_allow_html=True 才能正確顯示表格
st.markdown(html_cal, unsafe_allow_html=True)
st.caption("🟢 綠色：AC 班當班 | 🟡 橘色：BD 班當班")

st.divider()

# --- 5. 當日值班人員顯示 ---
st.subheader("👥 今日現場值班人員")
# 預設看今天，也可以點選看別天
pick_date = st.date_input("查看具體日期人員", date.today())
team_type, _, _ = get_shift_info(pick_date)
on_duty_teams = ['A', 'C'] if team_type == "AC" else ['B', 'D']

try:
    res = supabase.table("staff_list").select("*").execute()
    all_staff = res.data
    if all_staff:
        on_duty_staff = [s for s in all_staff if s['team'] in on_duty_teams]
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("### ☀️ 日班")
            day_people = [p for p in on_duty_staff if p['shift_type'] == "日班"]
            for s in day_people: st.success(f"👤 {s['name']} ({s['team']}班)")
            if not day_people: st.write("無人上班")
        with c2:
            st.markdown("### 🌙 夜班")
            night_people = [p for p in on_duty_staff if p['shift_type'] == "夜班"]
            for s in night_people: st.info(f"👤 {s['name']} ({s['team']}班)")
            if not night_people: st.write("無人上班")
    else:
        st.warning("⚠️ 尚未建立員工名單")
except Exception as e:
    st.error(f"讀取失敗: {e}")

st.divider()

# --- 6. 人員管理與備註 (收在展開盒裡) ---
with st.expander("🛠️ 人員與備註管理"):
    st.write("### ✨ 新增員工")
    new_name = st.text_input("員工姓名")
    col_a, col_b = st.columns(2)
    new_team = col_a.selectbox("所屬小組", ["A", "B", "C", "D"])
    new_type = col_b.selectbox("班別時段", ["日班", "夜班"])
    if st.button("➕ 加入名單", use_container_width=True):
        if new_name:
            supabase.table("staff_list").insert({"name": new_name, "team": new_team, "shift_type": new_type}).execute()
            st.rerun()

    st.write("---")
    st.write("### 📝 今日備註紀錄")
    user_note = st.text_area("筆記內容", placeholder="例如：今天交接事項...")
    if st.button("🚀 儲存備註", use_container_width=True):
        supabase.table("shift_records").insert({
            "user_id": "Old_Cha", 
            "shift_date": str(pick_date), 
            "shift_type": team_type, 
            "note": user_note
        }).execute()
        st.success("存好了！")

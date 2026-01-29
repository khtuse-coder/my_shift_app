import streamlit as st
from datetime import date
from supabase import create_client

# --- 1. 雲端連線設定 ---
SUPABASE_URL = "https://iomqohzyuwtbfxnoavjf.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImlvbXFvaHp5dXd0YmZ4bm9hdmpmIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njk2NTUxMzUsImV4cCI6MjA4NTIzMTEzNX0.raqhaFGXC50xWODruMD0M26HgDq0XC74KaOe48UpXP8"
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- 2. 邏輯運算 ---
def get_on_duty_teams(target_date):
    base_date = date(2026, 1, 30) # AC班上班第一天
    remainder = (target_date - base_date).days % 4
    if remainder in [0, 1]:
        return ['A', 'C'], "🛠️ AC 班當班"
    else:
        return ['B', 'D'], "🛠️ BD 班當班"

# --- 3. 網頁設定 ---
st.set_page_config(page_title="SMT 人力看板", layout="centered")
st.title("🔋 二休二班表助手")

# --- 4. 班表顯示 ---
pick_date = st.date_input("📅 選擇查看日期", date.today())
on_duty_teams, team_label = get_on_duty_teams(pick_date)

bg_color = "#FF4B4B" if "當班" in team_label else "#28A745"
st.markdown(f"""
    <div style="background-color:{bg_color}; padding:25px; border-radius:15px; text-align:center; color:white;">
        <h2 style="margin:0;">{pick_date}</h2>
        <h1 style="font-size:40px; margin:10px 0;">{team_label}</h1>
    </div>
""", unsafe_allow_html=True)

# --- 5. 今日值班人員名單 ---
st.subheader("👥 今日現場值班人員")
try:
    res = supabase.table("staff_list").select("*").execute()
    all_staff = res.data
    if all_staff:
        on_duty_staff = [s for s in all_staff if s['team'] in on_duty_teams]
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("### ☀️ 日班")
            for s in [p for p in on_duty_staff if p['shift_type'] == "日班"]:
                st.success(f"👤 {s['name']} ({s['team']}班)")
        with c2:
            st.markdown("### 🌙 夜班")
            for s in [p for p in on_duty_staff if p['shift_type'] == "夜班"]:
                st.info(f"👤 {s['name']} ({s['team']}班)")
except Exception as e:
    st.error(f"讀取名單失敗: {e}")

st.divider()

# --- 6. 人員管理 (新增/刪除) ---
with st.expander("🛠️ 人員管理系統"):
    # 新增人員
    st.write("--- ✨ 新增員工 ---")
    new_name = st.text_input("員工姓名")
    col_a, col_b = st.columns(2)
    new_team = col_a.selectbox("所屬小組", ["A", "B", "C", "D"])
    new_type = col_b.selectbox("班別時段", ["日班", "夜班"])
    
    if st.button("➕ 確認加入名單", use_container_width=True):
        if new_name:
            supabase.table("staff_list").insert({"name": new_name, "team": new_team, "shift_type": new_type}).execute()
            st.success(f"已加入: {new_name}")
            st.rerun() # 重新整理網頁
            
    # 刪除人員
    st.write("--- 🗑️ 刪除員工 ---")
    if all_staff:
        # 整理成可供選取的格式
        delete_list = [f"{s['id']} - {s['name']} ({s['team']}班/{s['shift_type']})" for s in all_staff]
        target = st.selectbox("選擇要刪除的人員", delete_list)
        if st.button("🔥 確認永久刪除", use_container_width=True):
            target_id = target.split(" - ")[0]
            supabase.table("staff_list").delete().eq("id", target_id).execute()
            st.warning("人員已移除")
            st.rerun()

st.divider()

# --- 7. 備註紀錄 (保留原功能) ---
st.subheader("📝 班別備註紀錄")
user_note = st.text_area("今日記事")
if st.button("🚀 儲存紀錄"):
    supabase.table("shift_records").insert({"user_id": "Old_Cha", "shift_date": str(pick_date), "shift_type": team_label, "note": user_note}).execute()
    st.success("已同步雲端")

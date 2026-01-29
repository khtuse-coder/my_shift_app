import streamlit as st
from datetime import date
from supabase import create_client
import pandas as pd

# --- 1. 雲端連線設定 ---
SUPABASE_URL = "https://iomqohzyuwtbfxnoavjf.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImlvbXFvaHp5dXd0YmZ4bm9hdmpmIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njk2NTUxMzUsImV4cCI6MjA4NTIzMTEzNX0.raqhaFGXC50xWODruMD0M26HgDq0XC74KaOe48UpXP8"

# 建立連線
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- 2. 邏輯運算函式 ---

def get_on_duty_teams(target_date):
    """根據日期計算哪組上班：AC班(0,1) 或 BD班(2,3)"""
    base_date = date(2026, 1, 30) # 基準日：AC班上班第一天
    delta = (target_date - base_date).days
    remainder = delta % 4
    
    # 回傳哪幾組今天當班
    if remainder in [0, 1]:
        return ['A', 'C'], "🛠️ AC 班當班"
    else:
        return ['B', 'D'], "🛠️ BD 班當班"

# --- 3. 網頁介面設計 ---
st.set_page_config(page_title="SMT 二休二人力看板", layout="centered")
st.title("🔋 二休二班表助手")

# 日期選擇器
today = date.today()
pick_date = st.date_input("📅 選擇查看日期", today)

# 算出當班組別
on_duty_teams, team_label = get_on_duty_teams(pick_date)

# 顯示狀態大卡片
bg_color = "#FF4B4B" if "當班" in team_label else "#28A745"
st.markdown(f"""
    <div style="background-color:{bg_color}; padding:30px; border-radius:15px; text-align:center; color:white;">
        <h2 style="margin:0;">{pick_date}</h2>
        <h1 style="font-size:40px; margin:10px 0;">{team_label}</h1>
    </div>
""", unsafe_allow_html=True)

st.divider()

# --- 4. 今日值班人員名單 (關鍵功能) ---
st.subheader("👥 今日現場值班人員")

try:
    # 從 Supabase 抓取所有員工名單
    res = supabase.table("staff_list").select("*").execute()
    all_staff = res.data
    
    if all_staff:
        # 過濾出今天「所屬小組」有上班的人
        on_duty_staff = [s for s in all_staff if s['team'] in on_duty_teams]
        
        # 區分日夜班顯示
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### ☀️ 日班")
            day_people = [s['name'] for s in on_duty_staff if s['shift_type'] == "日班"]
            if day_people:
                for name in day_people:
                    st.success(f"👤 {name}")
            else:
                st.write("無資料")
                
        with col2:
            st.markdown("### 🌙 夜班")
            night_people = [s['name'] for s in on_duty_staff if s['shift_type'] == "夜班"]
            if night_people:
                for name in night_people:
                    st.info(f"👤 {name}")
            else:
                st.write("無資料")
    else:
        st.warning("⚠️ 雲端名單是空的，請先去 Supabase 建立 staff_list 表並填入名字。")
except Exception as e:
    st.error(f"❌ 無法讀取名單：{e}")

st.divider()

# --- 5. 備註紀錄與歷史 ---
st.subheader("📝 班別備註紀錄")
user_note = st.text_area("今天有什麼想記下來的？", placeholder="例如：加 2 小時、換班、忘記打卡...")

if st.button("🚀 儲存紀錄到雲端", use_container_width=True):
    try:
        data = {
            "user_id": "Old_Cha",
            "shift_date": str(pick_date),
            "shift_type": team_label,
            "note": user_note
        }
        supabase.table("shift_records").insert(data).execute()
        st.success("✅ 已同步到雲端資料庫！")
    except Exception as e:
        st.error(f"❌ 儲存失敗：{e}")

# 顯示歷史紀錄
st.subheader("📊 最近紀錄")
try:
    history = supabase.table("shift_records").select("*").order("shift_date", desc=True).limit(5).execute()
    if history.data:
        for item in history.data:
            st.write(f"📅 {item['shift_date']} | {item['shift_type']} | 📝 {item['note']}")
except:
    pass

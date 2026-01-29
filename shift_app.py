import streamlit as st
from datetime import date
from supabase import create_client

# --- 1. 雲端連線設定 ---
# 檢查這兩行，確保網址正確，金鑰也要完整貼上
SUPABASE_URL = "https://iomqohzyuwtbfxnoavjf.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImlvbXFvaHp5dXd0YmZ4bm9hdmpmIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njk2NTUxMzUsImV4cCI6MjA4NTIzMTEzNX0.raqhaFGXC50xWODruMD0M26HgDq0XC74KaOe48UpXP8"

# 建立連線
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- 2. 二休二邏輯運算 ---
def get_shift_status(target_date):
    base_date = date(2026, 1, 30) # 以 1/30 為當班第一天
    delta = (target_date - base_date).days
    cycle_day = delta % 4
    
    if cycle_day in [0, 1]:
        return "🛠️ 上班 (當班)", "#FF4B4B" # 紅色
    else:
        return "☕ 休假 (休息)", "#28A745" # 綠色

# --- 3. 網頁介面設計 ---
st.set_page_config(page_title="二休二班表", layout="centered")
st.title("🔋 二休二班表助手")

# 日期選擇器
today = date.today()
pick_date = st.date_input("查看日期", today)
status, bg_color = get_shift_status(pick_date)

# 顯示大大的狀態卡片
st.markdown(f"""
    <div style="background-color:{bg_color}; padding:30px; border-radius:15px; text-align:center; color:white;">
        <h2 style="margin:0;">{pick_date}</h2>
        <h1 style="font-size:50px; margin:10px 0;">{status}</h1>
    </div>
""", unsafe_allow_html=True)

st.divider()

# 雲端紀錄功能
st.subheader("📝 班別備註紀錄")
user_note = st.text_area("今天有什麼想記下來的？", placeholder="例如：加 2 小時、換班、忘記打卡...")

if st.button("🚀 儲存紀錄到雲端", use_container_width=True):
    try:
        data = {
            "user_id": "Old_Cha",
            "shift_date": str(pick_date),
            "shift_type": status,
            "note": user_note
        }
        supabase.table("shift_records").insert(data).execute()
        st.success("✅ 已同步到雲端資料庫！")
    except Exception as e:
        st.error(f"❌ 儲存失敗：{e}")

# 顯示最近的 5 筆紀錄
st.subheader("📊 最近紀錄")
try:
    history = supabase.table("shift_records").select("*").order("shift_date", desc=True).limit(5).execute()
    if history.data:
        for item in history.data:
            st.write(f"📅 {item['shift_date']} | {item['shift_type']} | 📝 {item['note']}")
except:
    pass
import os
import requests
import pandas as pd
import streamlit as st

# 從環境變數讀取授權碼（本機可以用 setx / export，雲端用 Secrets）
CWA_KEY = os.environ.get("CWA_KEY", "")


st.set_page_config(page_title="台灣 36 小時天氣 Dashboard", layout="wide")

st.title("🌦️ 台灣 36 小時天氣 Dashboard")
st.caption("資料來源：中央氣象署開放資料平台 F-C0032-001")

# 檢查有沒有填授權碼
if not CWA_KEY:
    st.error("❌ 尚未設定 CWA_KEY，請在本機環境變數或 Streamlit Secrets 中加入。")
    st.stop()

API_URL = "https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-C0032-001"

@st.cache_data(ttl=900)
def fetch_forecast():
    """向中央氣象署取得 36 小時天氣預報資料"""
    params = {"Authorization": CWA_KEY}
    resp = requests.get(API_URL, params=params, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    return data

def to_dataframe(data: dict) -> pd.DataFrame:
    """把原始 JSON 轉成表格（DataFrame）"""
    locations = data["records"]["location"]
    rows = []

    for loc in locations:
        name = loc["locationName"]  # 縣市名稱

        # weatherElement 清單：Wx、PoP、MinT、CI、MaxT
        elements = {el["elementName"]: el["time"] for el in loc["weatherElement"]}

        # 以 PoP 的時間軸為主，其他欄位用相同 index 組合
        times = elements["PoP"]
        for i, t in enumerate(times):
            row = {
                "location": name,
                "startTime": t["startTime"],
                "endTime": t["endTime"],
                "PoP(%)": elements["PoP"][i]["parameter"]["parameterName"],
                "Wx": elements["Wx"][i]["parameter"]["parameterName"],
                "CI": elements["CI"][i]["parameter"]["parameterName"],
                "MinT(°C)": elements["MinT"][i]["parameter"]["parameterName"],
                "MaxT(°C)": elements["MaxT"][i]["parameter"]["parameterName"],
            }
            rows.append(row)

    df = pd.DataFrame(rows)

    # 轉型成時間 / 數字
    df["startTime"] = pd.to_datetime(df["startTime"])
    df["endTime"] = pd.to_datetime(df["endTime"])
    df["PoP(%)"] = pd.to_numeric(df["PoP(%)"], errors="coerce")
    df["MinT(°C)"] = pd.to_numeric(df["MinT(°C)"], errors="coerce")
    df["MaxT(°C)"] = pd.to_numeric(df["MaxT(°C)"], errors="coerce")

    df = df.sort_values(["location", "startTime"]).reset_index(drop=True)
    return df

# ================== 主程式開始 ==================
st.info("中央氣象署 36 小時各縣市預報（MinT / MaxT / PoP / Wx / CI）。")

try:
    raw_data = fetch_forecast()
    df = to_dataframe(raw_data)
except Exception as e:
    st.error(f"讀取資料失敗：{e}")
    st.stop()

# 縣市選單
all_locations = df["location"].unique().tolist()
col_left, col_right = st.columns([1, 2])

with col_left:
    city = st.selectbox("選擇縣市 / City", all_locations, index=0)
    sub = df[df["location"] == city].copy()

with col_right:
    if not sub.empty:
        st.subheader(f"{city} 的 36 小時預報")
        t0 = sub.iloc[0]["startTime"]
        t1 = sub.iloc[-1]["endTime"]
        st.write(f"時間區間：**{t0:%Y-%m-%d %H:%M} ~ {t1:%Y-%m-%d %H:%M}**")
        st.write("說明：Wx = 天氣現象敘述、CI = 舒適度指數。圖表顯示溫度與降雨機率。")

# 畫圖
col_temp, col_pop = st.columns(2)

with col_temp:
    st.subheader("氣溫變化 (°C)")
    temp_df = sub[["startTime", "MinT(°C)", "MaxT(°C)"]].set_index("startTime")
    st.line_chart(temp_df)   # 不指定顏色，交給 Streamlit 預設

with col_pop:
    st.subheader("降雨機率 PoP (%)")
    pop_df = sub[["startTime", "PoP(%)"]].set_index("startTime")
    st.bar_chart(pop_df)

st.subheader("詳細資料表")
st.dataframe(
    sub[["startTime", "endTime", "Wx", "CI", "MinT(°C)", "MaxT(°C)", "PoP(%)"]],
    use_container_width=True,
)

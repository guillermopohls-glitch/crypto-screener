import streamlit as st
import pandas as pd
import ta
import requests
import time
from streamlit_autorefresh import st_autorefresh

# 🔁 AUTO REFRESH
st_autorefresh(interval=60000, key="refresh")

st.set_page_config(page_title="Crypto Screener PRO", layout="wide")

st.title("📊 Crypto Entry Detector PRO")
st.caption("Producción real + Retry inteligente + Alertas")

# 🔔 TELEGRAM (usa secrets)
TOKEN = st.secrets.get("TOKEN", "")
CHAT_ID = st.secrets.get("CHAT_ID", "")

def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg}, timeout=10)
    except:
        pass

# 🧠 evitar duplicados
if "alerts_sent" not in st.session_state:
    st.session_state.alerts_sent = set()

# 🚀 RETRY INTELIGENTE
def fetch_with_retry(url, params, retries=3, delay=1.5):
    for attempt in range(retries):
        try:
            response = requests.get(url, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    return data

            time.sleep(delay * (attempt + 1))  # backoff progresivo

        except:
            time.sleep(delay * (attempt + 1))

    return None  # fallo total

# 📦 CACHE + RETRY
@st.cache_data(ttl=60)
def get_klines(symbol):
    url = "https://api.binance.com/api/v3/klines"

    params = {
        "symbol": symbol,
        "interval": "5m",
        "limit": 150
    }

    return fetch_with_retry(url, params)

symbols = [
    "BTCUSDT","ETHUSDT","SOLUSDT",
    "MANAUSDT","ADAUSDT","AVAXUSDT","ALGOUSDT"
]

results = []

for symbol in symbols:

    klines = get_klines(symbol)

    if klines is None:
        continue

    df = pd.DataFrame(klines, columns=[
        "time","open","high","low","close","volume",
        "close_time","qav","num_trades",
        "taker_base_vol","taker_quote_vol","ignore"
    ])

    df["close"] = df["close"].astype(float)
    df["high"] = df["high"].astype(float)
    df["low"] = df["low"].astype(float)
    df["volume"] = df["volume"].astype(float)

    # 📊 INDICADORES
    df["rsi"] = ta.momentum.RSIIndicator(df["close"], window=14).rsi()
    df["ma"] = df["close"].rolling(window=20).mean()

    macd = ta.trend.MACD(df["close"])
    df["macd"] = macd.macd()
    df["macd_signal"] = macd.macd_signal()

    df["vol_avg"] = df["volume"].rolling(window=20).mean()

    price = df["close"].iloc[-1]
    rsi = df["rsi"].iloc[-1]
    ma = df["ma"].iloc[-1]
    macd_val = df["macd"].iloc[-1]
    macd_sig = df["macd_signal"].iloc[-1]
    vol = df["volume"].iloc[-1]
    vol_avg = df["vol_avg"].iloc[-1]

    recent_high = df["high"].rolling(20).max().iloc[-1]
    recent_low = df["low"].rolling(20).min().iloc[-1]

    setup = "NO TRADE"
    entry = stop = target = rr = None
    probability = 0

    # 🧠 PROBABILIDAD SHORT
    prob_short = 0
    if rsi > 70: prob_short += 30
    elif rsi > 65: prob_short += 20
    if price < ma: prob_short += 25
    if macd_val < macd_sig: prob_short += 25
    if vol > vol_avg: prob_short += 20

    # 🧠 PROBABILIDAD LONG
    prob_long = 0
    if rsi < 30: prob_long += 30
    elif rsi < 35: prob_long += 20
    if price > ma: prob_long += 25
    if macd_val > macd_sig: prob_long += 25
    if vol > vol_avg: prob_long += 20

    # 🎯 DECISIÓN
    if prob_short >= 70:
        probability = prob_short
        entry = price
        stop = recent_high
        risk = stop - entry
        target = entry - (risk * 1.8)
        rr = 1.8
        setup = f"SHORT 📉 ({prob_short}%)"

    elif prob_long >= 70:
        probability = prob_long
        entry = price
        stop = recent_low
        risk = entry - stop
        target = entry + (risk * 1.8)
        rr = 1.8
        setup = f"LONG 📈 ({prob_long}%)"

    # 🔔 ALERTAS
    if probability >= 85:
        alert_key = f"{symbol}_{setup}"

        if alert_key not in st.session_state.alerts_sent:
            msg = f"""
🚨 SETUP DETECTADO 🚨
{symbol}

{setup}
Precio: {price:.4f}
Probabilidad: {probability}%

Entrada: {entry:.4f}
Stop: {stop:.4f}
TP: {target:.4f}
R:R: {rr}
"""
            send_telegram(msg)
            st.session_state.alerts_sent.add(alert_key)

    results.append({
        "Crypto": symbol.replace("USDT",""),
        "Precio": f"{price:,.4f}",
        "RSI": f"{rsi:.2f}",
        "Setup": setup,
        "Probabilidad %": probability,  # ← IMPORTANTE: número real
        "Entrada": f"{entry:,.4f}" if entry else "-",
        "Stop": f"{stop:,.4f}" if stop else "-",
        "TP": f"{target:,.4f}" if target else "-",
        "R:R": rr if rr else "-"
    })

# 🛡️ MANEJO SEGURO FINAL
if len(results) == 0:
    st.warning("⚠️ No se pudieron obtener datos (reintentos fallaron)")
    st.stop()

df_final = pd.DataFrame(results)

# Ordenar SOLO si existe columna
if "Probabilidad %" in df_final.columns:
    df_final = df_final.sort_values(by="Probabilidad %", ascending=False)

# Mostrar bonito
df_final["Probabilidad %"] = df_final["Probabilidad %"].astype(str) + "%"

st.dataframe(df_final, use_container_width=True)
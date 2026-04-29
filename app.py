import streamlit as st
import pandas as pd
from binance.client import Client
import ta
import requests
from streamlit_autorefresh import st_autorefresh

# 🔁 AUTO REFRESH
st_autorefresh(interval=60000, key="refresh")

st.set_page_config(page_title="Crypto Screener PRO", layout="wide")

st.title("📊 Crypto Entry Detector PRO")
st.caption("Formato profesional + Probabilidad inteligente")

# 🔔 TELEGRAM
TOKEN = "8728390279:AAH5EHU291mL-XOH3xOtuqsq-Wn3HFTGGxA"
CHAT_ID = "1662043599"

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg})

# Evitar alertas duplicadas
if "alerts_sent" not in st.session_state:
    st.session_state.alerts_sent = set()

# Binance
client = Client()

symbols = [
    "BTCUSDT","ETHUSDT","SOLUSDT",
    "MANAUSDT","ADAUSDT","AVAXUSDT","ALGOUSDT"
]

results = []

for symbol in symbols:

    klines = client.get_klines(
        symbol=symbol,
        interval=Client.KLINE_INTERVAL_5MINUTE,
        limit=150
    )

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

    # Últimos valores
    price = df["close"].iloc[-1]
    rsi = df["rsi"].iloc[-1]
    ma = df["ma"].iloc[-1]
    macd_val = df["macd"].iloc[-1]
    macd_sig = df["macd_signal"].iloc[-1]
    vol = df["volume"].iloc[-1]
    vol_avg = df["vol_avg"].iloc[-1]

    # Soporte / resistencia
    recent_high = df["high"].rolling(20).max().iloc[-1]
    recent_low = df["low"].rolling(20).min().iloc[-1]

    setup = "NO TRADE"
    entry = stop = target = rr = None
    probability = 0

    # 🧠 PROBABILIDAD PONDERADA SHORT
    prob_short = 0
    if rsi > 70:
        prob_short += 30
    elif rsi > 65:
        prob_short += 20

    if price < ma:
        prob_short += 25

    if macd_val < macd_sig:
        prob_short += 25

    if vol > vol_avg:
        prob_short += 20

    # 🧠 PROBABILIDAD PONDERADA LONG
    prob_long = 0
    if rsi < 30:
        prob_long += 30
    elif rsi < 35:
        prob_long += 20

    if price > ma:
        prob_long += 25

    if macd_val > macd_sig:
        prob_long += 25

    if vol > vol_avg:
        prob_long += 20

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
    if probability >= 80:
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

    # 🎨 FORMATO PRO
    price_fmt = f"{price:,.4f}"
    entry_fmt = f"{entry:,.4f}" if entry else "-"
    stop_fmt = f"{stop:,.4f}" if stop else "-"
    tp_fmt = f"{target:,.4f}" if target else "-"

    results.append({
        "Crypto": symbol.replace("USDT",""),
        "Precio": price_fmt,
        "RSI": f"{rsi:.2f}",
        "Setup": setup,
        "Probabilidad %": f"{probability}%",
        "Entrada": entry_fmt,
        "Stop": stop_fmt,
        "TP": tp_fmt,
        "R:R": rr if rr else "-"
    })

# 📊 TABLA
df_final = pd.DataFrame(results)

# Ordenar
df_final = df_final.sort_values(by="Probabilidad %", ascending=False)

st.dataframe(df_final, use_container_width=True)
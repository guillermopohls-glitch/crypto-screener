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
st.caption("Alta disponibilidad + Fallback multi API + Alertas")

# 🔔 TELEGRAM
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

# 🔁 RETRY
def fetch_with_retry(url, params=None, retries=3):
    for i in range(retries):
        try:
            r = requests.get(url, params=params, timeout=10)
            if r.status_code == 200:
                return r.json()
        except:
            time.sleep(1.5 * (i + 1))
    return None

# 📦 BINANCE (principal)
def get_binance(symbol):
    url = "https://data-api.binance.vision/api/v3/klines"
    params = {"symbol": symbol, "interval": "5m", "limit": 150}
    data = fetch_with_retry(url, params)
    return data if isinstance(data, list) else None

# 📦 COINGECKO (fallback)
def get_coingecko(symbol):
    mapping = {
        "BTCUSDT": "bitcoin",
        "ETHUSDT": "ethereum",
        "SOLUSDT": "solana",
        "ADAUSDT": "cardano",
        "AVAXUSDT": "avalanche-2",
        "ALGOUSDT": "algorand",
        "MANAUSDT": "decentraland"
    }

    coin = mapping.get(symbol)
    if not coin:
        return None

    url = f"https://api.coingecko.com/api/v3/coins/{coin}/market_chart"
    params = {"vs_currency": "usd", "days": "1"}

    data = fetch_with_retry(url, params)

    if not data or "prices" not in data:
        return None

    prices = data["prices"]

    # convertir a formato tipo Binance
    klines = []
    for p in prices[-150:]:
        price = p[1]
        klines.append([
            p[0], price, price, price, price, 100
        ] + [0]*6)

    return klines

# 🧠 HÍBRIDO
@st.cache_data(ttl=60)
def get_data(symbol):
    data = get_binance(symbol)
    if data:
        return data

    st.warning(f"⚠️ Binance falló → usando fallback ({symbol})")
    return get_coingecko(symbol)

symbols = [
    "BTCUSDT","ETHUSDT","SOLUSDT",
    "MANAUSDT","ADAUSDT","AVAXUSDT","ALGOUSDT"
]

results = []

for symbol in symbols:

    klines = get_data(symbol)

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

    prob_short = 0
    if rsi > 70: prob_short += 30
    elif rsi > 65: prob_short += 20
    if price < ma: prob_short += 25
    if macd_val < macd_sig: prob_short += 25
    if vol > vol_avg: prob_short += 20

    prob_long = 0
    if rsi < 30: prob_long += 30
    elif rsi < 35: prob_long += 20
    if price > ma: prob_long += 25
    if macd_val > macd_sig: prob_long += 25
    if vol > vol_avg: prob_long += 20

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

    if probability >= 70:
        key = f"{symbol}_{setup}"
        if key not in st.session_state.alerts_sent:
            msg = f"{symbol} | {setup} | {price:.4f} | {probability}%"
            send_telegram(msg)
            st.session_state.alerts_sent.add(key)

    results.append({
        "Crypto": symbol.replace("USDT",""),
        "Precio": f"{price:,.4f}",
        "RSI": f"{rsi:.2f}",
        "Setup": setup,
        "Probabilidad %": f"{probability}%",
        "Entrada": f"{entry:,.4f}" if entry else "-",
        "Stop": f"{stop:,.4f}" if stop else "-",
        "TP": f"{target:,.4f}" if target else "-",
        "R:R": rr if rr else "-"
    })

if len(results) == 0:
    st.error("⚠️ Ninguna API respondió")
    st.stop()

df = pd.DataFrame(results)
st.dataframe(df, use_container_width=True)
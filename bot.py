# cryptosignal46import os
import time
import requests
import ccxt
import pandas as pd
import ta
import numpy as np

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]

exchange = ccxt.okx({
    "enableRateLimit": True
})

def send_message(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={
        "chat_id": CHAT_ID,
        "text": message
    }, timeout=20)

def fetch_df(symbol, timeframe):
    candles = exchange.fetch_ohlcv(
        symbol, timeframe=timeframe, limit=250
    )
    df = pd.DataFrame(candles, columns=[
        "Time", "Open", "High", "Low", "Close", "Volume"
    ])
    return df

def analyze(df):
    df = df.copy()
    df["ema50"] = ta.trend.EMAIndicator(
        df["Close"], window=50
    ).ema_indicator()
    df["ema200"] = ta.trend.EMAIndicator(
        df["Close"], window=200
    ).ema_indicator()
    df["rsi"] = ta.momentum.RSIIndicator(
        df["Close"], window=14
    ).rsi()

    macd = ta.trend.MACD(df["Close"])
    df["macd"] = macd.macd()
    df["macd_signal"] = macd.macd_signal()

    df["atr"] = ta.volatility.AverageTrueRange(
        df["High"], df["Low"], df["Close"], window=14
    ).average_true_range()

    last = df.iloc[-2]

    if (
        last["Close"] > last["ema200"]
        and last["ema50"] > last["ema200"]
        and last["rsi"] > 50
        and last["macd"] > last["macd_signal"]
    ):
        return "LONG"

    if (
        last["Close"] < last["ema200"]
        and last["ema50"] < last["ema200"]
        and last["rsi"] < 50
        and last["macd"] < last["macd_signal"]
    ):
        return "SHORT"

    return "NO SIGNAL"

def get_levels(df, signal):
    last = df.iloc[-2]
    entry = float(last["Close"])
    atr = float(last["atr"])

    if not np.isfinite(atr) or atr <= 0:
        return None

    if signal == "LONG":
        return {
            "Entry": entry,
            "SL": entry - 1.5 * atr,
            "TP1": entry + atr,
            "TP2": entry + 2 * atr,
            "TP3": entry + 3 * atr
        }

    return {
        "Entry": entry,
        "SL": entry + 1.5 * atr,
        "TP1": entry - atr,
        "TP2": entry - 2 * atr,
        "TP3": entry - 3 * atr
    }

def scan_market():
    markets = exchange.load_markets()
    symbols = [
        s for s, m in markets.items()
        if m.get("swap")
        and m.get("quote") == "USDT"
        and m.get("active")
    ]

    results = []

    for symbol in symbols:
        try:
            df15 = fetch_df(symbol, "15m")
            df1h = fetch_df(symbol, "1h")

            signal15 = analyze(df15)
            signal1h = analyze(df1h)

            if signal15 != signal1h or signal15 == "NO SIGNAL":
                continue

            levels = get_levels(df15, signal15)
            if not levels:
                continue

            ticker = exchange.fetch_ticker(symbol)
            volume = float(
                ticker.get("quoteVolume") or 0
            )

            if volume <= 0:
                continue

            results.append({
                "symbol": symbol,
                "signal": signal15,
                "levels": levels,
                "volume": volume,
                "candle": int(df15.iloc[-2]["Time"])
            })

        except Exception as e:
            print("Skipped:", symbol, str(e)[:100])

    results.sort(key=lambda x: x["volume"], reverse=True)

    for item in results[:5]:
        message = (
            f"🚨 CRYPTOSIGNAL46 🚨\n\n"
            f"Coin: {item['symbol']}\n"
            f"Signal: {item['signal']}\n\n"
            f"Entry: {item['levels']['Entry']:.6g}\n"
            f"Stop Loss: {item['levels']['SL']:.6g}\n"
            f"TP1: {item['levels']['TP1']:.6g}\n"
            f"TP2: {item['levels']['TP2']:.6g}\n"
            f"TP3: {item['levels']['TP3']:.6g}\n\n"
            f"⚠️ Manual trading only"
        )
        send_message(message)

    print("Scan finished. Signals:", min(5, len(results)))

while True:
    try:
        print("Starting market scan...")
        scan_market()
    except Exception as e:
        print("Scan error:", e)

    print("Next scan in 15 minutes...")
    time.sleep(900)

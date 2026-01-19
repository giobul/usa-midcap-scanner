import os
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import requests
import google.generativeai as genai
from datetime import datetime

# --- CONFIGURAZIONE ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')

# Lista Mid-Cap
TICKERS = ['PLTR', 'MSTR', 'RBLX', 'AFRM', 'U', 'SNOW', 'SHOP', 'COIN', 'HOOD', 'DKNG']

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

def analyze_stock(ticker):
    try:
        df = yf.download(ticker, period="60d", interval="1d", progress=False)
        if df.empty or len(df) < 20: return None
        
        # Calcolo RSI
        df['RSI'] = ta.rsi(df['Close'], length=14)
        # Calcolo SMA 20
        df['SMA20'] = ta.sma(df['Close'], length=20)
        
        last = df.iloc[-1]
        vol_ma = df['Volume'].tail(20).mean()
        
        # Filtri: Prezzo sopra media, Volume > 1.5x, RSI < 70
        if last['Close'] > last['SMA20'] and last['Volume'] > (vol_ma * 1.5) and last['RSI'] < 70:
            return {"ticker": ticker, "price": round(float(last['Close']), 2), "rsi": round(float(last['RSI']), 2)}
    except:
        return None

def main():
    print("Inizio scansione...")
    for ticker in TICKERS:
        res = analyze_stock(ticker)
        if res:
            msg = f"🚀 *BREAKOUT:* {res['ticker']}\nPrezzo: ${res['price']}\nRSI: {res['rsi']}"
            send_telegram_message(msg)
            print(f"Segnale inviato per {ticker}")
    print("Scansione terminata.")

if __name__ == "__main__":
    main()

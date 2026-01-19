import os
import sys

# Prova a importare pandas_ta, se fallisce invia errore a Telegram
try:
    import pandas as pd
    import pandas_ta as ta
    import yfinance as yf
    import requests
    import google.generativeai as genai
except ImportError as e:
    # Se manca una libreria, proviamo a dirlo subito
    token = os.getenv("TELEGRAM_TOKEN")
    chat = os.getenv("CHAT_ID")
    if token and chat:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage", 
                      json={"chat_id": chat, "text": f"❌ Errore Import: {str(e)}"})
    sys.exit(1)

# --- RESTO DEL CODICE ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')

TICKERS = ['PLTR', 'MSTR', 'RBLX', 'AFRM', 'SNOW', 'SHOP', 'COIN', 'HOOD', 'DKNG']

def analyze_stock(ticker):
    try:
        df = yf.download(ticker, period="60d", interval="1d", progress=False)
        if df.empty or len(df) < 20: return None
        df.ta.rsi(append=True)
        df.ta.sma(length=20, append=True)
        last = df.iloc[-1]
        if last['Close'] > last['SMA_20'] and last['RSI_14'] < 70:
            return {"ticker": ticker, "price": round(float(last['Close']), 2)}
    except: return None
    return None

def main():
    print("Avvio scansione...")
    for t in TICKERS:
        res = analyze_stock(t)
        if res:
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                          json={"chat_id": CHAT_ID, "text": f"🚀 Segnale: {res['ticker']} a ${res['price']}"})
    print("Fine.")

if __name__ == "__main__":
    main()

import os
import sys

# Controllo di emergenza per le librerie
try:
    import pandas as pd
    import yfinance as yf
    import requests
    import google.generativeai as genai
    import pandas_ta as ta
except ImportError as e:
    print(f"ERRORE CRITICO: Manca la libreria -> {e}")
    sys.exit(1)

# --- CONFIGURAZIONE ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT = os.getenv("CHAT_ID")
API_KEY = os.getenv("GEMINI_API_KEY")

def main():
    print("Inizio scansione Mid-Cap...")
    
    # Configura Gemini
    model = None
    if API_KEY:
        genai.configure(api_key=API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')

    # Lista Mid-Cap Calde
    tickers = ['PLTR', 'MSTR', 'RBLX', 'AFRM', 'COIN', 'SHOP', 'DKNG', 'SOFI']
    
    for t in tickers:
        try:
            df = yf.download(t, period="60d", interval="1d", progress=False)
            if df.empty: continue
            
            # Calcolo RSI e SMA tramite pandas_ta
            df['RSI'] = ta.rsi(df['Close'], length=14)
            df['SMA20'] = ta.sma(df['Close'], length=20)
            
            last = df.iloc[-1]
            vol_ma = df['Volume'].tail(20).mean()
            vol_ratio = round(float(last['Volume'] / vol_ma), 1)
            
            # FILTRO: Prezzo > SMA20 e Volume > 1.5x (Segnale Istituzionale)
            if last['Close'] > last['SMA20'] and vol_ratio > 1.5:
                msg = f"🎯 *ACCUMULAZIONE: {t}*\nPrezzo: ${round(float(last['Close']), 2)}\nVol: {vol_ratio}x media\nRSI: {round(float(last['RSI']), 2)}"
                
                url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
                requests.post(url, json={"chat_id": CHAT, "text": msg, "parse_mode": "Markdown"})
                print(f"Segnale inviato per {t}")
        except Exception as e:
            print(f"Errore su {t}: {e}")
    
    print("Scansione terminata.")

if __name__ == "__main__":
    main()

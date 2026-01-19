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

# Lista Mid-Cap focalizzata su titoli ad alta crescita/volatilità
TICKERS = ['PLTR', 'MSTR', 'RBLX', 'AFRM', 'U', 'SNOW', 'SHOP', 'COIN', 'HOOD', 'DKNG', 'SOFI', 'MARA', 'RIOT', 'CLSK']

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

def analyze_stock(ticker):
    try:
        df = yf.download(ticker, period="60d", interval="1d", progress=False)
        if df.empty or len(df) < 30: return None
        
        # Indicatori Tecnici
        df['RSI'] = ta.rsi(df['Close'], length=14)
        df['SMA20'] = ta.sma(df['Close'], length=20)
        df['SMA50'] = ta.sma(df['Close'], length=50)
        
        last = df.iloc[-1]
        prev = df.iloc[-2]
        vol_ma = df['Volume'].tail(20).mean()
        
        # LOGICA DI BREAKOUT E ACCUMULAZIONE
        # 1. Prezzo sopra SMA20 e SMA50 (Trend Rialzista)
        # 2. Volume > 150% della media (Accumulazione Istituzionale)
        # 3. RSI tra 50 e 70 (Forza senza eccesso)
        
        is_breakout = last['Close'] > last['SMA20'] and last['Close'] > prev['Close']
        is_accumulation = last['Volume'] > (vol_ma * 1.5)
        
        if is_breakout and is_accumulation and 50 < last['RSI'] < 70:
            return {
                "ticker": ticker,
                "price": round(float(last['Close']), 2),
                "rsi": round(float(last['RSI']), 2),
                "vol_ratio": round(float(last['Volume'] / vol_ma), 2)
            }
    except Exception as e:
        print(f"Errore su {ticker}: {e}")
    return None

def main():
    print(f"--- Avvio Scansione Mid-Cap: {datetime.now().strftime('%Y-%m-%d %H:%M')} ---")
    signals_found = 0
    
    for ticker in TICKERS:
        res = analyze_stock(ticker)
        if res:
            signals_found += 1
            msg = (f"🚀 *BREAKOUT VALIDATO: {res['ticker']}*\n\n"
                   f"💰 Prezzo: ${res['price']}\n"
                   f"📊 RSI: {res['rsi']}\n"
                   f"📈 Volume: {res['vol_ratio']}x media (Accumulazione)\n"
                   f"⚠️ *Nota:* Volume elevato sopra resistenza SMA20.")
            send_telegram_message(msg)
            print(f"Segnale inviato per {ticker}")
            
    if signals_found == 0:
        print("Scansione completata: nessun titolo soddisfa i criteri.")
    else:
        print(f"Scansione completata: inviati {signals_found} segnali.")

if __name__ == "__main__":
    main()

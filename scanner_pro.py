import os
import sys
import pandas as pd
import yfinance as yf
import requests
import google.generativeai as genai
from datetime import datetime

# Gestione libreria tecnica (Calcolo manuale se fallisce import)
try:
    import pandas_ta as ta
    HAS_PANDAS_TA = True
except ImportError:
    HAS_PANDAS_TA = False

# Configurazione
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT = os.getenv("CHAT_ID")
API_KEY = os.getenv("GEMINI_API_KEY")

def get_ai_analysis(ticker, price, vol_ratio):
    if not API_KEY: return "Analisi AI non disponibile."
    try:
        genai.configure(api_key=API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"Analizza brevemente breakout {ticker} a ${price}. Vol {vol_ratio}x. Focus accumulazione."
        response = model.generate_content(prompt)
        return response.text
    except:
        return "Insight AI non disponibile."

def calculate_indicators(df):
    if HAS_PANDAS_TA:
        df['RSI'] = ta.rsi(df['Close'], length=14)
        df['SMA20'] = ta.sma(df['Close'], length=20)
    else:
        # Calcolo manuale RSI e SMA
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / (loss + 1e-9)
        df['RSI'] = 100 - (100 / (1 + rs))
        df['SMA20'] = df['Close'].rolling(window=20).mean()
    return df

def main():
    print(f"Scanner Online - Modalità TA: {'Standard' if HAS_PANDAS_TA else 'Manuale'}")
    tickers = ['PLTR', 'MSTR', 'RBLX', 'AFRM', 'COIN', 'SHOP', 'DKNG', 'SOFI']
    
    for t in tickers:
        try:
            df = yf.download(t, period="60d", interval="1d", progress=False)
            if df.empty: continue
            
            df = calculate_indicators(df)
            last = df.iloc[-1]
            vol_ma = df['Volume'].tail(20).mean()
            vol_ratio = round(float(last['Volume'] / vol_ma), 1)
            
            # Filtro Breakout Istituzionale (Prezzo > SMA20 e Vol > 1.5x)
            if last['Close'] > last['SMA20'] and vol_ratio > 1.5:
                ai_text = get_ai_analysis(t, round(float(last['Close']), 2), vol_ratio)
                msg = (f"🎯 *ACCUMULAZIONE: {t}*\n"
                       f"💰 Prezzo: ${round(float(last['Close']), 2)}\n"
                       f"📈 Vol: {vol_ratio}x media\n"
                       f"📊 RSI: {round(float(last['RSI']), 2)}\n\n"
                       f"🤖 *Analisi:* {ai_text}")
                
                requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                              json={"chat_id": CHAT, "text": msg, "parse_mode": "Markdown"})
                print(f"Inviato: {t}")
        except Exception as e:
            print(f"Errore {t}: {e}")

if __name__ == "__main__":
    main()

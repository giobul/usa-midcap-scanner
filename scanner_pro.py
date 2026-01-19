import os
import sys
import pandas as pd
import yfinance as yf
import requests
from google import genai
from datetime import datetime

# Prova a caricare pandas_ta, se manca usiamo calcoli manuali
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
    if not API_KEY: return "Analisi AI non configurata."
    try:
        client = genai.Client(api_key=API_KEY)
        prompt = f"Analizza brevemente il breakout di {ticker} a ${price}. Volume {vol_ratio}x media. Focus su istituzionali."
        response = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
        return response.text
    except:
        return "Insight AI momentaneamente non disponibile."

def calculate_indicators(df):
    if HAS_PANDAS_TA:
        df['RSI'] = ta.rsi(df['Close'], length=14)
        df['SMA20'] = ta.sma(df['Close'], length=20)
    else:
        # Calcolo manuale di emergenza se la libreria fallisce
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        df['SMA20'] = df['Close'].rolling(window=20).mean()
    return df

def main():
    print(f"Avvio Scansione (Libreria TA: {'OK' if HAS_PANDAS_TA else 'MANUALE'})")
    tickers = ['PLTR', 'MSTR', 'RBLX', 'AFRM', 'COIN', 'SHOP', 'DKNG', 'SOFI']
    
    for t in tickers:
        try:
            df = yf.download(t, period="60d", interval="1d", progress=False)
            if df.empty: continue
            
            df = calculate_indicators(df)
            last = df.iloc[-1]
            vol_ma = df['Volume'].tail(20).mean()
            vol_ratio = round(float(last['Volume'] / vol_ma), 1)
            
            # FILTRO: Prezzo > SMA20 e Volume > 1.5x (Segnale Istituzionale)
            if last['Close'] > last['SMA20'] and vol_ratio > 1.5:
                ai_text = get_ai_analysis(t, round(float(last['Close']), 2), vol_ratio)
                msg = (f"🎯 *ACCUMULAZIONE RILEVATA: {t}*\n"
                       f"💰 Prezzo: ${round(float(last['Close']), 2)}\n"
                       f"📈 Vol: {vol_ratio}x media\n"
                       f"📊 RSI: {round(float(last['RSI']), 2)}\n\n"
                       f"🤖 *AI Insight:* \n{ai_text}")
                
                requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                              json={"chat_id": CHAT, "text": msg, "parse_mode": "Markdown"})
                print(f"Segnale inviato per {t}")
        except Exception as e:
            print(f"Errore su {t}: {e}")
    print("Fine scansione.")

if __name__ == "__main__":
    main()main()

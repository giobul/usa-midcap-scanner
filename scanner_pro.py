import os
import sys
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import requests
import google.generativeai as genai

# Configurazione credenziali
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT = os.getenv("CHAT_ID")
API_KEY = os.getenv("GEMINI_API_KEY")

def main():
    print("--- Avvio Scansione Istituzionale Mid-Cap ---")
    
    # Inizializza Gemini se presente
    model = None
    if API_KEY:
        genai.configure(api_key=API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')

    # Focus su Mid-Cap ad alto volume
    tickers = ['PLTR', 'MSTR', 'RBLX', 'AFRM', 'COIN', 'SHOP', 'DKNG', 'SOFI']
    
    for t in tickers:
        try:
            df = yf.download(t, period="60d", interval="1d", progress=False)
            if df.empty: continue
            
            # Calcolo indicatori
            df['RSI'] = ta.rsi(df['Close'], length=14)
            df['SMA20'] = ta.sma(df['Close'], length=20)
            
            last = df.iloc[-1]
            vol_ma = df['Volume'].tail(20).mean()
            vol_ratio = round(float(last['Volume'] / vol_ma), 1)
            
            # FILTRO: Prezzo > SMA20 e Volume > 1.5x media (Segnale Istituzionale)
            if last['Close'] > last['SMA20'] and vol_ratio > 1.5:
                # Analisi AI opzionale
                ai_analysis = "Analisi non disponibile"
                if model:
                    try:
                        res = model.generate_content(f"Analizza breakout {t} a ${last['Close']} con volume {vol_ratio}x.")
                        ai_analysis = res.text
                    except: pass

                msg = (f"🎯 *ACCUMULAZIONE: {t}*\n"
                       f"💰 Prezzo: ${round(float(last['Close']), 2)}\n"
                       f"📈 Vol: {vol_ratio}x media\n"
                       f"📊 RSI: {round(float(last['RSI']), 2)}\n\n"
                       f"🤖 *AI Insight:* {ai_analysis}")
                
                requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                              json={"chat_id": CHAT, "text": msg, "parse_mode": "Markdown"})
                print(f"Segnale inviato per {t}")
        except Exception as e:
            print(f"Errore su {t}: {e}")
    
    print("--- Scansione terminata con successo ---")

if __name__ == "__main__":
    main()

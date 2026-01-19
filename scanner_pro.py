import os
import sys

# Importazioni standard
import pandas as pd
import yfinance as yf
import requests
import google.generativeai as genai
import pandas_ta as ta
from datetime import datetime

# Credenziali
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def send_telegram(msg):
    if TELEGRAM_TOKEN and CHAT_ID:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})

def main():
    print(f"Inizio scansione: {datetime.now()}")
    
    # Lista ridotta per test rapido
    tickers = ['PLTR', 'MSTR', 'RBLX', 'AFRM', 'COIN', 'SHOP']
    
    for ticker in tickers:
        try:
            print(f"Analizzando {ticker}...")
            df = yf.download(ticker, period="60d", interval="1d", progress=False)
            
            if df.empty: continue
            
            # Calcolo indicatori con pandas_ta
            rsi = ta.rsi(df['Close'], length=14)
            if rsi is None or len(rsi) == 0: continue
            
            current_rsi = rsi.iloc[-1]
            price = df['Close'].iloc[-1]
            
            # Condizione semplificata per il test
            if current_rsi < 70:
                msg = f"✅ *Scanner Attivo*\n\nStock: {ticker}\nPrezzo: ${round(float(price), 2)}\nRSI: {round(float(current_rsi), 2)}"
                send_telegram(msg)
                print(f"Segnale inviato per {ticker}")
                
        except Exception as e:
            print(f"Errore su {ticker}: {e}")

if __name__ == "__main__":
    main()main()

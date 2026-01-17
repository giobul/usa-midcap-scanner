import os
import yfinance as yf
import requests
import pandas as pd
import google.generativeai as genai
from datetime import datetime

# --- CARICAMENTO SEGRETI ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

TICKERS = ["NVDA", "AMD", "SMCI", "PLTR", "MSTR", "MARA", "COIN", "TSM", "AVGO", "ARM"]

def send_msg(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"})

def run_scanner():
    print(f"Inizio scansione: {datetime.now()}")
    for ticker in TICKERS:
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period="60d")
            if len(df) < 20: continue
            
            # Calcolo OBV manuale (senza librerie esterne)
            df['OBV'] = (df['Volume'] * (~df['Close'].diff().le(0) * 2 - 1)).cumsum()
            obv_trend = "Crescente" if df['OBV'].iloc[-1] > df['OBV'].iloc[-5] else "Neutro"
            
            last_price = df['Close'].iloc[-1]
            last_vol = df['Volume'].iloc[-1]
            avg_vol = df['Volume'].tail(20).mean()
            vol_ratio = round(last_vol/avg_vol, 1)

            # Trigger per il test (essendo sabato mettiamo un filtro basso o True per vedere se scrive)
            if vol_ratio > 0.1: # Filtro bassissimo solo per il test di stasera
                prompt = f"Analizza {ticker} a ${last_price}. Volumi {vol_ratio}x rispetto alla media, OBV {obv_trend}. Sii sintetico e professionale."
                analisi = model.generate_content(prompt).text
                send_msg(f"🚀 *TEST GITHUB: {ticker}*\n💰 Prezzo: ${last_price:.2f}\n📊 Volumi: {vol_ratio}x\n📈 OBV: {obv_trend}\n🤖 *IA:* {analisi}")
        except Exception as e:
            print(f"Errore su {ticker}: {e}")

if __name__ == "__main__":
    run_scanner()

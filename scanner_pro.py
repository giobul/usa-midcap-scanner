import os
import yfinance as yf
import requests
import pandas as pd
import google.generativeai as genai

# --- CONFIGURAZIONE ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-1.5-flash')

# Lista Mid-Cap e titoli ad alto potenziale
TICKERS = ["NVDA", "PLTR", "MSTR", "AMD", "MARA", "COIN", "SOFI", "AFRM", "UPST", "CLSK", "TSM", "ARM"]

def send_msg(text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"})

def run_scanner():
    print("Inizio scansione professionale...")
    for ticker in TICKERS:
        try:
            stock = yf.Ticker(ticker)
            # Scarichiamo 1 anno di dati per calcolare correttamente la media a 200 giorni
            df = stock.history(period="1y")
            if df.empty or len(df) < 200: continue
            
            # 1. Calcolo Prezzo e Volumi
            last_close = df['Close'].iloc[-1]
            last_vol = df['Volume'].iloc[-1]
            avg_vol = df['Volume'].tail(20).mean()
            vol_ratio = last_vol / avg_vol
            
            # 2. Calcolo Media Mobile a 200 giorni (SMA 200)
            sma_200 = df['Close'].rolling(window=200).mean().iloc[-1]
            is_bullish = last_close > sma_200
            
            # --- FILTRO DOPPIO: Volume Spike + Trend Rialzista ---
            if vol_ratio > 1.5 and is_bullish:
                prompt = (f"Analizza {ticker}. Prezzo (${last_close:.2f}) sopra la media 200 giorni (${sma_200:.2f}). "
                          f"Volume anomalo: {vol_ratio:.1f}x. Identifica segnali di accumulazione istituzionale, "
                          f"resistenze chiave e attività insolita sulle Call. Sii sintetico.")
                
                analisi = model.generate_content(prompt).text
                
                msg = (f"🔥 *GOLDEN SIGNAL: {ticker}*\n"
                       f"📈 Trend: *Sopra SMA 200* (Rialzista)\n"
                       f"📊 Volume Spike: *{vol_ratio:.1f}x*\n"
                       f"💰 Prezzo attuale: ${last_close:.2f}\n\n"
                       f"🤖 *ANALISI IA:*\n{analisi}")
                
                send_msg(msg)
                print(f"Segnale inviato per {ticker}")
            else:
                motivo = "Volume basso" if vol_ratio <= 1.5 else "Sotto SMA 200 (Trend debole)"
                print(f"{ticker}: Saltato ({motivo})")
                
        except Exception as e:
            print(f"Errore su {ticker}: {e}")

if __name__ == "__main__":
    run_scanner()

if __name__ == "__main__":
    run_scanner()

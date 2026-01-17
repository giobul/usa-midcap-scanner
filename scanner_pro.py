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

# Lista Mid-Cap e titoli caldi per accumulazione
TICKERS = ["NVDA", "PLTR", "MSTR", "AMD", "MARA", "COIN", "SOFI", "AFRM", "UPST", "CLSK"]

def send_msg(text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    # Invio del messaggio con formattazione Markdown per una lettura professionale
    requests.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"})

def run_scanner():
    print("Inizio scansione mercati...")
    for ticker in TICKERS:
        try:
            stock = yf.Ticker(ticker)
            # Prendiamo gli ultimi 30 giorni per calcolare la media dei volumi
            df = stock.history(period="30d")
            if df.empty or len(df) < 20: continue
            
            last_close = df['Close'].iloc[-1]
            last_vol = df['Volume'].iloc[-1]
            avg_vol = df['Volume'].tail(20).mean() # Media mobile a 20 giorni
            vol_ratio = last_vol / avg_vol
            
            # --- FILTRO ISTITUZIONALE 1.5x ---
            if vol_ratio > 1.5: 
                prompt = (f"Analizza {ticker} a ${last_close:.2f}. Volumi insoliti: {vol_ratio:.1f} volte la media. "
                          f"Identifica livelli di resistenza chiave e segnali di Option Sweeps o Unusual Call Activity. "
                          f"Spiega se questo movimento indica accumulazione istituzionale. Sii tecnico e conciso.")
                
                analisi = model.generate_content(prompt).text
                
                msg = (f"🚨 *ALERT ISTITUZIONALE: {ticker}*\n"
                       f"💰 Prezzo: ${last_close:.2f}\n"
                       f"📊 Volume Spike: *{vol_ratio:.1f}x*\n\n"
                       f"🤖 *ANALISI IA:*\n{analisi}")
                
                send_msg(msg)
                print(f"Segnale inviato per {ticker}")
            else:
                print(f"{ticker}: Volume normale ({vol_ratio:.1f}x)")
                
        except Exception as e:
            print(f"Errore su {ticker}: {e}")

if __name__ == "__main__":
    run_scanner()

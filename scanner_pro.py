import os
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import requests
import google.generativeai as genai

# Carico le chiavi dai Secrets di GitHub
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT = os.getenv("CHAT_ID")
API_KEY = os.getenv("GEMINI_API_KEY")

# Configurazione Gemini
if API_KEY:
    genai.configure(api_key=API_KEY)
    ai_model = genai.GenerativeModel('gemini-1.5-flash')

def get_ai_analysis(ticker, price, vol_ratio):
    if not API_KEY: return "Analisi AI non disponibile."
    prompt = f"Analizza brevemente il breakout di {ticker} a ${price}. Il volume è {vol_ratio}x la media. Focus su accumulazione istituzionale."
    try:
        response = ai_model.generate_content(prompt)
        return response.text
    except:
        return "Errore durante l'analisi AI."

def main():
    print("Avvio scansione Mid-Cap...")
    tickers = ['PLTR', 'MSTR', 'RBLX', 'AFRM', 'COIN', 'SHOP', 'DKNG', 'SOFI', 'MARA', 'RIOT']
    
    for t in tickers:
        try:
            df = yf.download(t, period="60d", interval="1d", progress=False)
            if df.empty: continue
            
            # Indicatori
            df['RSI'] = ta.rsi(df['Close'], length=14)
            df['SMA20'] = ta.sma(df['Close'], length=20)
            
            last = df.iloc[-1]
            vol_ma = df['Volume'].tail(20).mean()
            vol_ratio = round(float(last['Volume']/vol_ma), 1)
            
            # Filtro Istituzionali: Prezzo > SMA20 e Volume > 1.5x media
            if last['Close'] > last['SMA20'] and vol_ratio > 1.5:
                ai_text = get_ai_analysis(t, round(float(last['Close']), 2), vol_ratio)
                
                msg = (f"🎯 *ACCUMULAZIONE RILEVATA: {t}*\n"
                       f"💰 Prezzo: ${round(float(last['Close']), 2)}\n"
                       f"📈 Volume: {vol_ratio}x media\n"
                       f"📊 RSI: {round(float(last['RSI']), 2)}\n\n"
                       f"🤖 *Analisi Gemini:* \n{ai_text}")
                
                requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                              json={"chat_id": CHAT, "text": msg, "parse_mode": "Markdown"})
                print(f"Segnale inviato per {t}")
        except Exception as e:
            print(f"Errore su {t}: {e}")
    print("Scansione terminata.")

if __name__ == "__main__":
    main()

import os
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import requests
import google.generativeai as genai

# Caricamento credenziali
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def main():
    print("Verifica librerie completata con successo!")
    print(f"Versione Pandas: {pd.__version__}")
    
    # Test veloce su un solo titolo per vedere se funziona
    ticker = "PLTR"
    print(f"Analizzando {ticker}...")
    df = yf.download(ticker, period="60d", interval="1d", progress=False)
    
    if not df.empty:
        df['RSI'] = ta.rsi(df['Close'], length=14)
        ultimo_rsi = df['RSI'].iloc[-1]
        print(f"RSI di {ticker}: {ultimo_rsi}")
        
        # Invia un messaggio di test a Telegram
        msg = f"✅ Scanner Online!\nTest {ticker}: RSI {round(float(ultimo_rsi), 2)}"
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": CHAT_ID, "text": msg})
        print("Messaggio di test inviato a Telegram.")

if __name__ == "__main__":
    main()main()

import yfinance as yf
import pandas as pd
import datetime
import os
import requests
import time

# --- CONFIGURAZIONE ---
MY_PORTFOLIO = ["STNE"]
ORARI_CACCIA = [15, 18, 20] 

def send_telegram(message):
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id: return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

def calculate_rsi(prices, period=14):
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def main():
    # --- MESSAGGIO DI TEST ---
    send_telegram("🔔 TEST: Il sistema è collegato correttamente! Se senti questo suono, la configurazione è OK.")
    
    now = datetime.datetime.now()
    # (Il resto del codice di analisi segue qui sotto...)
    print("Test completato con successo.")

if __name__ == "__main__":
    main()

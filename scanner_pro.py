import pandas as pd
import requests
import os
import time
from datetime import datetime

# 🔑 CONFIG
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN", "TUO_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "TUA_CHAT_ID")

# Tickers core per test immediato
TICKERS = ["NVDA", "TSLA", "AAPL", "AMD", "PLTR", "MSTR", "MSFT", "META", "GOOGL", "AMZN"]

def get_price_google(ticker):
    """Recupera il prezzo tramite il mirror di Google Finance"""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=5d"
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()
        price = data['chart']['result'][0]['meta']['regularMarketPrice']
        prev_close = data['chart']['result'][0]['meta']['previousClose']
        return price, prev_close
    except:
        return None, None

def main():
    print(f"🧬 NEXUS v18.0 — GOOGLE SHIELD | {datetime.now().strftime('%H:%M')}")
    print(f"📡 Scansione di emergenza su {len(TICKERS)} titoli...")
    
    found = 0
    for ticker in TICKERS:
        print(f"🔍 Controllo {ticker}...", end="\r")
        price, prev_close = get_price_google(ticker)
        
        if price and prev_close:
            # Calcoliamo se il titolo è in rialzo (Aggressivo)
            change = ((price - prev_close) / prev_close) * 100
            
            # Se il titolo sta salendo, mandiamo l'alert
            if change > 0:
                found += 1
                msg = (f"🚀 *SHIELD ALERT: {ticker}*\n"
                       f"💰 Prezzo: `${price}`\n"
                       f"📈 Var: `+{round(change, 2)}%`\n"
                       f"🛠️ Stato: *Accumulazione*")
                
                requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                              data={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"})
                print(f"✅ Inviato: {ticker} ({round(change, 2)}%)")
        
        time.sleep(1.5) # Ritardo per sicurezza

    print(f"\n🏁 Fine. Inviati {found} alert.")

if __name__ == "__main__":
    main()
    

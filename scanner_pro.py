import subprocess
import sys

def install(package):
    try: subprocess.check_call([sys.executable, "-m", "pip", "install", package])
    except: pass

for p in ['pandas', 'pandas-datareader', 'numpy', 'requests']:
    try: __import__(p.replace('-', '_'))
    except ImportError: install(p)

import pandas as pd
import pandas_datareader.data as web
import numpy as np
import requests
import warnings
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

warnings.filterwarnings("ignore")

TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN", "YOUR_TOKEN_HERE")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "YOUR_CHAT_ID_HERE")

def analyze_ticker(ticker):
    try:
        symbol = f"{ticker}.US"
        df = web.DataReader(symbol, 'stooq')
        if df is None or df.empty or len(df) < 30: return None
        df = df.sort_index()
        
        price = float(df["Close"].iloc[-1])
        low_10 = float(df["Low"].rolling(10).min().iloc[-1])
        ma_20 = float(df["Close"].rolling(20).mean().iloc[-1])
        
        # 🎯 LOGICA RECOVERY: Prezzo sopra il minimo di 10gg e vicino/sopra la media 20
        # Questo intercetta chi sta ripartendo dopo un calo
        if price > low_10:
            score = 2
            if price > ma_20: score += 4  # Forza extra se sopra media
            if df["Close"].iloc[-1] > df["Close"].iloc[-2]: score += 4 # Momentum positivo
            
            atr = float((df["High"] - df["Low"]).rolling(14).mean().iloc[-1])
            sl = round(price - (atr * 1.5), 2)
            tg = round(price + (atr * 3.0), 2)

            return {
                "ticker": ticker, "price": round(price, 2), "ifs": score,
                "tg": tg, "sl": sl, "type": "RECOVERY" if price < ma_20 else "STRENGTH"
            }
    except: return None

def main():
    print(f"🧬 NEXUS v17.3 — BOTTOM HUNTER | {datetime.now().strftime('%H:%M')}")
    results = []
    tickers = ["AAPL", "MSFT", "NVDA", "AMD", "TSLA", "PLTR", "AMZN", "META", "GOOGL", "NFLX", "COIN", "MSTR", "SMCI"] # Test su core
    # Se vuoi testare tutti i 242, riaggiungi la SECTOR_MAP qui
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(analyze_ticker, t): t for t in tickers}
        for future in as_completed(futures):
            res = future.result()
            if res: results.append(res)

    results.sort(key=lambda x: x["ifs"], reverse=True)
    for r in results[:10]:
        msg = f"🟢 *SIGNAL: {r['ticker']}* ({r['type']})\n💰 PRICE: `${r['price']}` | IFS: `{r['ifs']}`\n🎯 TG: `${r['tg']}` | 🛑 SL: `${r['sl']}`"
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", data={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"})
        print(f"Inviato alert per {r['ticker']}")

if __name__ == "__main__":
    main()

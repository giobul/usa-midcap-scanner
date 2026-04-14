import pandas as pd
import requests
import os
import io
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# 🔑 CONFIG
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN", "TUO_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "TUA_CHAT_ID")

# Test limitato a titoli ad alta volatilità per confermare il funzionamento
TICKERS = ["NVDA", "TSLA", "AAPL", "AMD", "PLTR", "MSTR", "MARA", "COIN", "SMCI", "META"]

def get_stooq_data_direct(ticker):
    """Scarica il CSV direttamente da Stooq senza intermediari"""
    url = f"https://stooq.com/q/d/l/?s={ticker}.us&i=d"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            df = pd.read_csv(io.StringIO(response.text))
            if len(df) > 30:
                return df
        return None
    except:
        return None

def analyze(ticker, df):
    try:
        # Calcoli veloci
        last_price = float(df['Close'].iloc[-1])
        prev_price = float(df['Close'].iloc[-2])
        low_5 = float(df['Low'].rolling(5).min().iloc[-1])
        
        # LOGICA: Rimbalzo tecnico (prezzo odierno > prezzo ieri e sopra minimo 5gg)
        if last_price > prev_price and last_price > low_5:
            return {
                "ticker": ticker,
                "price": round(last_price, 2),
                "change": round(((last_price - prev_price) / prev_price) * 100, 2)
            }
    except: return None

def main():
    print(f"🧬 NEXUS v17.4 — DIRECT STREAM | {datetime.now().strftime('%H:%M')}")
    print(f"📡 Test su {len(TICKERS)} core leaders...")
    
    results = []
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(get_stooq_data_direct, t): t for t in TICKERS}
        for future in as_completed(futures):
            ticker = futures[future]
            df = future.result()
            if df is not None:
                res = analyze(ticker, df)
                if res:
                    results.append(res)
                    print(f"✅ Segnale trovato: {ticker}")
            time.sleep(1) # Cortesia per il server

    for r in results:
        msg = f"🚀 *RECOVERY ALERT: {r['ticker']}*\n💰 Prezzo: `${r['price']}`\n📈 Var: `+{r['change']}%`"
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                      data={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"})

    print(f"🏁 Scansione terminata. Trovati {len(results)} segnali.")

if __name__ == "__main__":
    main()

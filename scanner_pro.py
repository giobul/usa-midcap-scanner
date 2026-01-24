import yfinance as yf
import pandas as pd
import datetime
import os
import requests
import time

# --- 1. CONFIGURAZIONE ---
MY_PORTFOLIO = ["STNE"]
ORARI_CACCIA = [15, 18, 20] # 16:00, 19:00, 21:00 ITA

def send_telegram(message):
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id: return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    try: requests.post(url, json=payload, timeout=10)
    except: pass

def calculate_rsi(prices, period=14):
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def analyze_stock(ticker, is_full_scan):
    try:
        df = yf.download(ticker, period="5d", interval="15m", progress=False)
        if df.empty: return False
        
        cp = float(df['Close'].iloc[-1])
        vol = float(df['Volume'].iloc[-1])
        avg_vol = float(df['Volume'].mean())
        df['RSI'] = calculate_rsi(df['Close'])
        rsi = float(df['RSI'].iloc[-1])
        
        support_level = float(df['Low'].tail(50).min())
        distanza_supporto = ((cp - support_level) / support_level) * 100

        # --- AZIONE A: DIFESA (STNE) ---
        if ticker in MY_PORTFOLIO and rsi > 75:
            for h in ["🚨 VENDITA 1/3", "🔊 VENDITA 2/3", "⚠️ FINALE 3/3"]:
                send_telegram(f"*{h}*\n**{ticker}** RSI: {rsi:.2f}\nPrezzo: ${cp:.2f}")
                time.sleep(5)
            return True

        # --- AZIONE B: CACCIA CON ICEBERG SCORE ---
        mult = 1.5 if is_full_scan else 2.5
        if vol > (avg_vol * mult) and distanza_supporto <= 1.5:
            # Calcolo Score (1-10) basato sul moltiplicatore di volume
            score = min(10, int((vol / avg_vol) * 1.5))
            stars = "⭐" * (score // 2) if score > 1 else "🔹"
            
            if vol > (avg_vol * 4.0):
                tipo = "🔥 **SWEEP AGGRESSIVO**"
                status = "✅ **INGRESSO OTTIMALE**" if distanza_supporto <= 1.2 else "⚠️ **PREZZO IN FUGA**"
            else:
                tipo = "🧊 **ICEBERG DETECTED**"
                status = "⚖️ **ACCUMULO IN CORSO**"

            msg = f"{tipo}: **{ticker}**\n"
            msg += f"━━━━━━━━━━━━━━━\n"
            msg += f"📊 **ICEBERG SCORE: {score}/10** {stars}\n"
            msg += f"💰 Prezzo: ${cp:.2f}\n"
            msg += f"📈 Volumi: {vol/avg_vol:.1f}x media\n"
            msg += f"📍 Posizione: {status}\n"
            msg += f"🎯 Supporto: ${support_level:.2f}"
            send_telegram(msg)
            return True
        return False
    except: return False

def main():
    now = datetime.datetime.now()
    if now.weekday() > 4: return 
    if now.hour < 14 or (now.hour >= 21 and now.minute > 15): return

    watchlist = [
        "STNE", "NU", "PAGS", "MELI", "SOFI", "UPST", "AFRM", "HOOD", "SQ", "PYPL", "COIN", "FLYV", "MARQ", "BILL", "TOST",
        "PLTR", "SNOW", "NET", "CRWD", "DDOG", "ZS", "OKTA", "MDB", "TEAM", "SHOP", "DOCU", "ZM", "PATH", "C3AI", "U", "AI", "IONQ", "ASAN", "SMARTS", "IOT", "SAMS", "DUOL", "FRSH", "BRZE", "ADBE", "CRM", "WDAY", "NOW",
        "SE", "CPNG", "TME", "BILI", "PDUO", "JD", "BABA", "DASH", "ABNB", "UBER", "LYFT", "ETSG", "CHWY", "RVLV", "W", "ROKU", "PINS", "SNAP", "EBAY", "ETSY",
        "AMD", "NVDA", "INTC", "MU", "TXN", "TSM", "ASML", "AMAT", "LRCX", "KLAC", "SNPS", "CDNS", "ARM", "MRVL", "AVGO", "SMCI",
        "TSLA", "RIVN", "LCID", "F", "GM", "RACE", "STLA", "ENPH", "SEDG", "FSLR", "PLUG", "CHPT", "RUN", "QS", "NIO", "XPEV", "LI", "BE", "NEE",
        "MARA", "RIOT", "CLSK", "HUT", "BITF", "MSTR", "COIN", "WULF", "CIFR", "ANY",
        "DKNG", "PENN", "RCL", "CCL", "NCLH", "AAL", "DAL", "UAL", "LUV", "BKNG", "EXPE", "MAR", "HLT", "GENI", "RSI",
        "META", "GOOGL", "AMZN", "MSFT", "AAPL", "NFLX", "DIS", "PARA", "WBD", "AMC", "GME", "BB", "NOK", "TLRY", "CGC", "ACB", "SNDL", "OPEN", "HOV", "BLND", "HRTX", "MNMD", "FSR", "NKLA", "WKHS", "RBLX", "DNA", "S", "FUBO", "SPCE", "PLBY", "SKLZ", "VERV", "BEAM", "EDIT", "CRSP", "NTLA", "MTCH", "BMBL", "YELP"
    ]
    
    if now.hour in ORARI_CACCIA and now.minute < 35:
        tickers = list(set(watchlist + MY_PORTFOLIO))
        mode = "CACCIA"
    else:
        tickers = MY_PORTFOLIO
        mode = "DIFESA"

    found_any = False
    for t in tickers:
        if analyze_stock(t, mode == "CACCIA"): found_any = True
        time.sleep(0.4)

    if mode == "CACCIA" and not found_any:
        send_telegram(f"✅ Scansione delle {now.hour+1}:00 completata. Nessun accumulo rilevante.")

if __name__ == "__main__":
    main()

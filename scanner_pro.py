import yfinance as yf
import pandas as pd
import os
import requests
import time
import datetime

# --- LISTA PULITA (Rimosse le fallite: FSR, SGEN, GRTS, ecc.) ---
MY_PORTFOLIO = ["STNE", "PATH", "RGTI", "QUBT", "DKNG", "AI", "BBAI", "ADCT", "AGEN"]

WATCHLIST = ["STNE", "PATH", "RGTI", "QUBT", "IONQ", "AI", "BBAI", "PLTR", "SOUN", "SNOW", "NET", "CRWD", "DDOG", "ZS", "OKTA", "MDB", "TEAM", "S", "U", "ADBE", "CRM", "WDAY", "NOW", "NU", "PAGS", "MELI", "SOFI", "UPST", "AFRM", "HOOD", "PYPL", "COIN", "BILL", "TOST", "DAVE", "MQ", "LC", "BABA", "JD", "PDD", "MARA", "RIOT", "CLSK", "HUT", "BITF", "MSTR", "WULF", "CIFR", "ANY", "BTBT", "CAN", "VRTX", "VKTX", "SAVA", "IOVA", "BBIO", "MDGL", "REGN", "ILMN", "EXAS", "BNTX", "MRNA", "IQV", "TDOC", "BMEA", "SRPT", "CRSP", "EDIT", "BEAM", "NTLA", "RLAY", "IRON", "TLRY", "CGC", "AMD", "NVDA", "INTC", "MU", "TXN", "TSM", "ASML", "AMAT", "LRCX", "KLAC", "SNPS", "CDNS", "ARM", "MRVL", "AVGO", "SMCI", "ANET", "TER", "ENTG", "ON", "TSLA", "RIVN", "LCID", "F", "GM", "RACE", "STLA", "ENPH", "SEDG", "FSLR", "PLUG", "CHPT", "RUN", "QS", "NIO", "XPEV", "LI", "BE", "NEE", "BLDP", "FCEL", "DKNG", "PENN", "RCL", "CCL", "NCLH", "AAL", "DAL", "UAL", "LUV", "BKNG", "EXPE", "MAR", "HLT", "GENI", "RSI", "SHOP", "DOCU", "ZM", "DASH", "ABNB", "UBER", "LYFT", "CHWY", "ROKU", "PINS", "SNAP", "EBAY", "ETSY", "RVLV", "META", "GOOGL", "AMZN", "MSFT", "AAPL", "NFLX", "DIS", "WBD", "AMC", "GME", "BB", "NOK", "FUBO", "SPCE", "RBLX", "MTCH", "BMBL", "YELP", "TTD", "OPEN", "HOV", "BLND", "HRTX", "MNMD", "WKHS", "DNA", "PLBY", "SKLZ", "SENS", "HYLN", "ASTS", "INVZ", "AEVA", "VRT", "ETN", "POWI", "RMBS", "OKLO", "SMR", "HIMS", "CLVT", "LRN", "GCT"]

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

def analyze_stock(ticker):
    try:
        # progress=False e proxy=None aiutano a tenere i log puliti
        df = yf.download(ticker, period="20d", interval="15m", progress=False, show_errors=False)
        if df.empty or len(df) < 30: return
        
        cp = float(df['Close'].iloc[-1])
        lp = float(df['Close'].iloc[-2])
        vol_attuale = float(df['Volume'].iloc[-1])
        avg_vol = df['Volume'].mean()
        std_vol = df['Volume'].std()
        z_score = (vol_attuale - avg_vol) / std_vol
        rsi_val = calculate_rsi(df['Close']).iloc[-1]
        
        # LOGICA SNIPER
        if z_score > 3.0 and cp > lp:
            send_telegram(f"🐋 **BALENA (Sniper)**\nTicker: **{ticker}** | **${cp:.2f}**\nZ-Score: {z_score:.1f}x | RSI: {rsi_val:.1f}")
            print(f"ALERT SNIPER: {ticker}")
            
        # LOGICA ICEBERG
        elif z_score > 1.5 and abs((cp-lp)/lp)*100 < 0.25:
            send_telegram(f"🧊 **ICEBERG (Accumulo)**\nTicker: **{ticker}** | **${cp:.2f}**\nVolumi: +{((vol_attuale/avg_vol)-1)*100:.1f}%\nRSI: {rsi_val:.1f}")
            print(f"ALERT ICEBERG: {ticker}")

        # PROFIT CHECK
        if ticker in MY_PORTFOLIO and rsi_val > 75:
            send_telegram(f"💰 **PROFIT CHECK: {ticker}**\nRSI: {rsi_val:.1f}\nValuta se incassare!")
            print(f"ALERT PROFIT: {ticker}")

    except: pass

def main():
    print(f"--- Inizio Scansione {datetime.datetime.now()} ---")
    tickers = sorted(list(set(WATCHLIST + MY_PORTFOLIO)))
    for i, t in enumerate(tickers):
        analyze_stock(t)
        if (i + 1) % 25 == 0:
            print(f"Check: {i + 1}/{len(tickers)} titoli completati...")
        time.sleep(0.4) 
    print(f"--- Fine Scansione {datetime.datetime.now()} ---")

if __name__ == "__main__":
    main()

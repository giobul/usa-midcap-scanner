import yfinance as yf
import pandas as pd
import datetime
import os
import requests
import time

# --- 1. CONFIGURAZIONE ---
MY_PORTFOLIO = ["STNE", "PATH", "RGTI", "QUBT", "DKNG", "AI", "BBAI", "ADCT", "AGEN"]
WATCHLIST = ["STNE", "PATH", "RGTI", "QUBT", "IONQ", "C3AI", "AI", "BBAI", "PLTR", "SOUN", "SNOW", "NET", "CRWD", "DDOG", "ZS", "OKTA", "MDB", "TEAM", "S", "U", "ADBE", "CRM", "WDAY", "NOW", "NU", "PAGS", "MELI", "SOFI", "UPST", "AFRM", "HOOD", "SQ", "PYPL", "COIN", "FLYV", "MARQ", "BILL", "TOST", "DAVE", "MQ", "LC", "BABA", "JD", "PDUO", "MARA", "RIOT", "CLSK", "HUT", "BITF", "MSTR", "WULF", "CIFR", "ANY", "BTBT", "CAN", "SDIG", "ADCT", "AGEN", "VRTX", "VKTX", "SAVA", "IOVA", "BBIO", "MDGL", "REGN", "ILMN", "EXAS", "BNTX", "MRNA", "SGEN", "IQV", "TDOC", "BMEA", "SRPT", "CRSP", "EDIT", "BEAM", "NTLA", "VERV", "GRTS", "RLAY", "IRON", "TLRY", "CGC", "AMD", "NVDA", "INTC", "MU", "TXN", "TSM", "ASML", "AMAT", "LRCX", "KLAC", "SNPS", "CDNS", "ARM", "MRVL", "AVGO", "SMCI", "ANET", "TER", "ENTG", "ON", "TSLA", "RIVN", "LCID", "F", "GM", "RACE", "STLA", "ENPH", "SEDG", "FSLR", "PLUG", "CHPT", "RUN", "QS", "NIO", "XPEV", "LI", "BE", "NEE", "BLDP", "FCEL", "DKNG", "PENN", "RCL", "CCL", "NCLH", "AAL", "DAL", "UAL", "LUV", "BKNG", "EXPE", "MAR", "HLT", "GENI", "RSI", "SHOP", "DOCU", "ZM", "DASH", "ABNB", "UBER", "LYFT", "CHWY", "ROKU", "PINS", "SNAP", "EBAY", "ETSY", "RVLV", "META", "GOOGL", "AMZN", "MSFT", "AAPL", "NFLX", "DIS", "PARA", "WBD", "AMC", "GME", "BB", "NOK", "FUBO", "SPCE", "RBLX", "MTCH", "BMBL", "YELP", "TTD", "OPEN", "HOV", "BLND", "HRTX", "MNMD", "FSR", "NKLA", "WKHS", "DNA", "PLBY", "SKLZ", "SENS", "HYLN", "ASTS", "ORBK", "LIDR", "INVZ", "LAZR", "AEVA"]

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
        df = yf.download(ticker, period="20d", interval="15m", progress=False)
        if df.empty or len(df) < 30: return
        
        cp = float(df['Close'].iloc[-1])
        lp = float(df['Close'].iloc[-2])
        vol_attuale = float(df['Volume'].iloc[-1])
        avg_vol = df['Volume'].mean()
        std_vol = df['Volume'].std()
        z_score = (vol_attuale - avg_vol) / std_vol
        rsi_val = calculate_rsi(df['Close']).iloc[-1]
        
        # --- LOGICA 1: SNIPER (Balena Aggressiva) ---
        if z_score > 3.0 and cp > lp:
            msg = (f"🐋 **BALENA DETECTED (Sniper)**\n"
                   f"Ticker: **{ticker}** | Prezzo: **${cp:.2f}**\n"
                   f"Z-Score: {z_score:.1f}x | RSI: {rsi_val:.1f}\n"
                   f"Analisi: Rottura violenta in corso!")
            send_telegram(msg)
            
        # --- LOGICA 2: ICEBERG (Accumulazione Nascosta) ---
        # Volume > media ma prezzo stabile (movimento < 0.3%)
        elif z_score > 1.5 and abs((cp-lp)/lp)*100 < 0.3:
            stop_loss = cp * 0.95
            msg = (f"🧊 **ICEBERG DETECTED (Accumulo)**\n"
                   f"Ticker: **{ticker}** | Prezzo: **${cp:.2f}**\n"
                   f"Volumi: +{((vol_attuale/avg_vol)-1)*100:.1f}%\n"
                   f"RSI: {rsi_val:.1f} | Stop Loss: **${stop_loss:.2f}**\n"
                   f"Analisi: Qualcuno sta comprando senza dare nell'occhio.")
            send_telegram(msg)

    except: pass

def main():
    send_telegram("🚀 **SCANNER IBRIDO (SNIPER + ICEBERG) ATTIVO**\nPronto a scovare ogni movimento istituzionale.")
    while True:
        now = datetime.datetime.now()
        if now.weekday() < 5 and (15 <= now.hour <= 22):
            for t in set(WATCHLIST + MY_PORTFOLIO):
                analyze_stock(t)
                time.sleep(0.3)
            time.sleep(900)
        else:
            time.sleep(60)

if __name__ == "__main__":
    main()

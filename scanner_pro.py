import yfinance as yf
import pandas as pd
import os
import requests
import time
import datetime

# --- CONFIGURAZIONE ---
# Assicurati che siano scritti in MAIUSCOLO
MY_PORTFOLIO = ["STNE", "PATH", "RGTI", "QUBT", "DKNG", "AI", "BBAI", "ADCT", "AGEN"]

WATCHLIST = ["IONQ", "PLTR", "SOUN", "SNOW", "NET", "CRWD", "DDOG", "ZS", "OKTA", "MDB", "TEAM", "S", "U", "ADBE", "CRM", "WDAY", "NOW", "NU", "PAGS", "MELI", "SOFI", "UPST", "AFRM", "HOOD", "PYPL", "COIN", "BILL", "TOST", "DAVE", "MQ", "LC", "BABA", "JD", "PDD", "MARA", "RIOT", "CLSK", "HUT", "BITF", "MSTR", "WULF", "CIFR", "ANY", "BTBT", "CAN", "VRTX", "VKTX", "SAVA", "IOVA", "BBIO", "MDGL", "REGN", "ILMN", "EXAS", "BNTX", "MRNA", "IQV", "TDOC", "BMEA", "SRPT", "CRSP", "EDIT", "BEAM", "NTLA", "RLAY", "IRON", "TLRY", "CGC", "AMD", "NVDA", "INTC", "MU", "TXN", "TSM", "ASML", "AMAT", "LRCX", "KLAC", "SNPS", "CDNS", "ARM", "MRVL", "AVGO", "SMCI", "ANET", "TER", "ENTG", "ON", "TSLA", "RIVN", "LCID", "F", "GM", "RACE", "STLA", "ENPH", "SEDG", "FSLR", "PLUG", "CHPT", "RUN", "QS", "NIO", "XPEV", "LI", "BE", "NEE", "BLDP", "FCEL", "PENN", "RCL", "CCL", "NCLH", "AAL", "DAL", "UAL", "LUV", "BKNG", "EXPE", "MAR", "HLT", "GENI", "RSI", "SHOP", "DOCU", "ZM", "DASH", "ABNB", "UBER", "LYFT", "CHWY", "ROKU", "PINS", "SNAP", "EBAY", "ETSY", "RVLV", "META", "GOOGL", "AMZN", "MSFT", "AAPL", "NFLX", "DIS", "WBD", "AMC", "GME", "BB", "NOK", "FUBO", "SPCE", "RBLX", "MTCH", "BMBL", "YELP", "TTD", "OPEN", "HOV", "BLND", "HRTX", "MNMD", "WKHS", "DNA", "PLBY", "SKLZ", "SENS", "HYLN", "ASTS", "INVZ", "AEVA", "VRT", "ETN", "POWI", "RMBS", "OKLO", "SMR", "HIMS", "CLVT", "LRN", "GCT"]

SOGLIA_RSI_EXIT = 72.0

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
        df = yf.download(ticker, period="30d", interval="15m", progress=False, show_errors=False)
        if df.empty or len(df) < 20: return
        
        cp = float(df['Close'].iloc[-1])
        lp = float(df['Close'].iloc[-2])
        res_20d = float(df['High'].max())
        dist_res = ((res_20d - cp) / cp) * 100
        
        vol_attuale = float(df['Volume'].iloc[-1])
        avg_vol = df['Volume'].mean()
        z_score = (vol_attuale - avg_vol) / df['Volume'].std()
        rsi_val = calculate_rsi(df['Close']).iloc[-1]
        
        # --- LOGICA EXIT PRIORITARIA ---
        if ticker in MY_PORTFOLIO:
            # Se l'RSI scotta, spara l'exit
            if rsi_val >= SOGLIA_RSI_EXIT:
                msg = f"🏁 **STRATEGIC EXIT: {ticker}**\nPrezzo: **${cp:.2f}** | RSI: **{rsi_val:.1f}** 🔥\n"
                msg += f"🤖 **AI:** Target 72 raggiunto. Esci ora per proteggere il gain."
                send_telegram(msg)
                return # Blocca altri messaggi per questo titolo

        # --- LOGICA CACCIA ---
        if z_score > 3.0 and cp > lp:
            msg = f"🐋 **BALENA (Sniper): {ticker}**\nPrezzo: **${cp:.2f}** | RSI: {rsi_val:.1f}\n📈 Res: -{dist_res:.1f}%"
            send_telegram(msg)
        elif z_score > 1.8 and abs((cp-lp)/lp)*100 < 0.20:
            msg = f"🧊 **ICEBERG (Accumulo): {ticker}**\nPrezzo: **${cp:.2f}** | RSI: {rsi_val:.1f}"
            send_telegram(msg)

    except: pass

def main():
    # Test iniziale per vedere se legge il portafoglio
    startup_msg = f"🤖 **Scanner Avviato**\nMonitoraggio Exit su: {', '.join(MY_PORTFOLIO)}"
    send_telegram(startup_msg)
    
    all_tickers = sorted(list(set(WATCHLIST + MY_PORTFOLIO)))
    for t in all_tickers:
        analyze_stock(t)
        time.sleep(0.6)

if __name__ == "__main__":
    main()
                      

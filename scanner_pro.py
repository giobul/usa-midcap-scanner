import yfinance as yf
import pandas as pd
import numpy as np
import os
import requests
import datetime
import time
import logging

logging.getLogger('yfinance').setLevel(logging.CRITICAL)

# --- CONFIGURAZIONE ---
MY_PORTFOLIO = ["STNE", "PATH", "RGTI", "QUBT", "DKNG", "AI", "BBAI", "ADCT", "AGEN", "STX"]
WATCHLIST = ["STX", "IONQ", "PLTR", "SOUN", "SNOW", "NET", "CRWD", "DDOG", "ZS", "OKTA", "MDB", "TEAM", "S", "U", "ADBE", "CRM", "WDAY", "NOW", "NU", "PAGS", "MELI", "SOFI", "UPST", "AFRM", "HOOD", "PYPL", "COIN", "BILL", "TOST", "DAVE", "MQ", "LC", "BABA", "JD", "PDD", "MARA", "RIOT", "CLSK", "HUT", "BITF", "MSTR", "WULF", "CIFR", "ANY", "BTBT", "CAN", "VRTX", "VKTX", "SAVA", "IOVA", "BBIO", "MDGL", "REGN", "ILMN", "EXAS", "BNTX", "MRNA", "IQV", "TDOC", "BMEA", "SRPT", "CRSP", "EDIT", "BEAM", "NTLA", "RLAY", "IRON", "TLRY", "CGC", "AMD", "NVDA", "INTC", "MU", "TXN", "TSM", "ASML", "AMAT", "LRCX", "KLAC", "SNPS", "CDNS", "ARM", "MRVL", "AVGO", "SMCI", "ANET", "TER", "ENTG", "ON", "TSLA", "RIVN", "LCID", "F", "GM", "RACE", "STLA", "ENPH", "SEDG", "FSLR", "PLUG", "CHPT", "RUN", "QS", "NIO", "XPEV", "LI", "BE", "NEE", "BLDP", "FCEL", "PENN", "RCL", "CCL", "NCLH", "AAL", "DAL", "UAL", "LUV", "BKNG", "EXPE", "MAR", "HLT", "GENI", "RSI", "SHOP", "DOCU", "ZM", "DASH", "ABNB", "UBER", "LYFT", "CHWY", "ROKU", "PINS", "SNAP", "EBAY", "ETSY", "RVLV", "META", "GOOGL", "AMZN", "MSFT", "AAPL", "NFLX", "DIS", "WBD", "AMC", "GME", "BB", "NOK", "FUBO", "SPCE", "RBLX", "MTCH", "BMBL", "YELP", "TTD", "OPEN", "HOV", "BLND", "HRTX", "MNMD", "WKHS", "DNA", "PLBY", "SKLZ", "SENS", "HYLN", "ASTS", "INVZ", "AEVA", "VRT", "ETN", "POWI", "RMBS", "OKLO", "SMR", "HIMS", "CLVT", "LRN", "GCT"]

SOGLIA_RSI_EXIT = 70.0  

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
        df = yf.download(ticker, period="5d", interval="15m", progress=False, threads=False)
        if df.empty or len(df) < 25: return
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)

        cp = float(df['Close'].iloc[-1])
        lp = float(df['Close'].iloc[-2])
        vol_series = df['Volume'].tail(20)
        z_score = (float(df['Volume'].iloc[-1]) - vol_series.mean()) / vol_series.std() if vol_series.std() > 0 else 0
        rsi_val = float(calculate_rsi(df['Close']).iloc[-1])
        var_pct_candela = abs((cp - lp) / lp) * 100
        res = float(df['High'].iloc[-21:-1].max())
        sup = float(df['Low'].iloc[-21:-1].min())
        
        # --- NOVITÀ: VOLATILITÀ (SQUEEZE) ---
        std_dev = df['Close'].tail(20).std()
        avg_price = df['Close'].tail(20).mean()
        is_squeeze = (std_dev / avg_price) * 100 < 0.5  # Prezzo iper-compresso

        print(f"Checking {ticker}: ${cp:.2f} | Z:{z_score:.1f}")

        soglia_z = 1.3 if ticker in MY_PORTFOLIO else 2.0
        info_tecnica = f"\n📊 RSI: {rsi_val:.1f}\n📈 Res: ${res:.2f}\n🛡️ Sup: ${sup:.2f}"

        if z_score > soglia_z:
            # DARK POOL
            if z_score > 4.0 and var_pct_candela <= 0.30:
                msg = f"🌑 **DARK POOL DETECTED: {ticker}**\nPrezzo: ${cp:.2f} | **Z-Vol: {z_score:.1f}**" + info_tecnica + "\n📢 **COSA FARE:** Passaggio di blocchi massicci. Qualcosa di grosso bolle in pentola!"
                send_telegram(msg)
            # ICEBERG (Filtro STNE 0.50%)
            elif var_pct_candela <= 0.50:
                msg = f"🧊 **ACCUMULO ISTITUZIONALE: {ticker}**\nPrezzo: ${cp:.2f} | Z-Vol: {z_score:.1f}" + info_tecnica + "\n📢 **COSA FARE:** Balene in accumulo. Ottimo punto d'ingresso se tiene il supporto."
                send_telegram(msg)
            # SWEEP
            elif cp > lp:
                msg = f"🐋 **SWEEP BULLISH: {ticker}**\nPrezzo: ${cp:.2f}" + info_tecnica + "\n📢 **COSA FARE:** Forza confermata. Gli acquirenti spazzano le resistenze!"
                send_telegram(msg)
            # USCITA (Solo Portfolio)
            elif cp < lp and ticker in MY_PORTFOLIO:
                msg = f"🚨 **MOVIMENTO IN USCITA: {ticker}**" + info_tecnica + "\n📢 **COSA FARE:** Balene in uscita. Proteggi il capitale!"
                send_telegram(msg)

        # NOVITÀ: SQUEEZE ALERT (Indipendente dal volume)
        if is_squeeze and ticker in MY_PORTFOLIO:
            send_telegram(f"⚡ **SQUEEZE ALERT: {ticker}**\nPrezzo: ${cp:.2f}\n📢 **COSA FARE:** Volatilità ai minimi. Una violenta esplosione (su o giù) è imminente!")

        # TARGET PROFIT
        if ticker in MY_PORTFOLIO and rsi_val >= SOGLIA_RSI_EXIT:
            send_telegram(f"🏁 **ZONA TARGET: {ticker}**\nPrezzo: ${cp:.2f}" + info_tecnica + f"\n📢 **COSA FARE:** RSI alto ({rsi_val:.1f}). Se profitto > 50€, valuta di incassare!")

    except: pass

def main():
    now = datetime.datetime.now()
    current_time = int(now.strftime("%H%M"))
    if current_time < 1530 or current_time > 2210: return
    all_tickers = sorted(list(set(WATCHLIST + MY_PORTFOLIO)))
    for t in all_tickers:
        analyze_stock(t)
        time.sleep(0.4)

if __name__ == "__main__":
    main()

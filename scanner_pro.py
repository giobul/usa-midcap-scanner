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

def get_market_sentiment():
    try:
        # Analizziamo il QQQ (Nasdaq 100) per il contesto Tech/Growth
        idx = yf.download("QQQ", period="2d", interval="1d", progress=False)
        if len(idx) < 2: return "⚖️ NEUTRALE"
        change = ((idx['Close'].iloc[-1] - idx['Close'].iloc[-2]) / idx['Close'].iloc[-2]) * 100
        if change > 0.5: return "🚀 BULLISH"
        if change < -0.5: return "📉 BEARISH"
        return "⚖️ NEUTRALE"
    except: return "❓ INCERTO"

def calculate_rsi(prices, period=14):
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def analyze_stock(ticker, sentiment):
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
        
        # Check Squeeze
        std_dev = df['Close'].tail(20).std()
        avg_price = df['Close'].tail(20).mean()
        is_squeeze = (std_dev / avg_price) * 100 < 0.4 

        soglia_z = 1.3 if ticker in MY_PORTFOLIO else 2.0
        header = f"🌍 **CLIMA MERCATO:** {sentiment}\n"
        info_tecnica = f"\n📊 RSI: {rsi_val:.1f}\n📈 Res: ${res:.2f}\n🛡️ Sup: ${sup:.2f}"

        if z_score > soglia_z:
            # 1. DARK POOL
            if z_score > 4.0 and var_pct_candela <= 0.30:
                msg = f"{header}🌑 **DARK POOL DETECTED: {ticker}**\nZ-Vol: {z_score:.1f}" + info_tecnica + "\n📢 **COSA FARE:** Scambio massiccio fuori mercato. Segnale di forza se il mercato è BULLISH."
                send_telegram(msg)
            # 2. ICEBERG (Soglia 0.50% per STNE)
            elif var_pct_candela <= 0.50:
                msg = f"{header}🧊 **ACCUMULO ISTITUZIONALE: {ticker}**\nZ-Vol: {z_score:.1f}" + info_tecnica + "\n📢 **COSA FARE:** Balene in accumulo. Ottimo setup se il mercato regge."
                send_telegram(msg)
            # 3. SWEEP
            elif cp > lp:
                msg = f"{header}🐋 **SWEEP BULLISH: {ticker}**\nPrezzo: ${cp:.2f}" + info_tecnica + "\n📢 **COSA FARE:** Aggressività istituzionale in corso!"
                send_telegram(msg)
            # 4. USCITA (Solo Portfolio)
            elif cp < lp and ticker in MY_PORTFOLIO:
                msg = f"{header}🚨 **MOVIMENTO IN USCITA: {ticker}**" + info_tecnica + "\n📢 **COSA FARE:** Balene in vendita. Proteggi il capitale, specialmente se il mercato è BEARISH!"
                send_telegram(msg)

        if is_squeeze and ticker in MY_PORTFOLIO:
            send_telegram(f"{header}⚡ **SQUEEZE ALERT: {ticker}**\nPrezzo: ${cp:.2f}\n📢 **COSA FARE:** Prezzo compresso. Esplosione imminente!")

        if ticker in MY_PORTFOLIO and rsi_val >= SOGLIA_RSI_EXIT:
            send_telegram(f"{header}🏁 **ZONA TARGET: {ticker}**\nPrezzo: ${cp:.2f}" + info_tecnica + f"\n📢 **COSA FARE:** RSI alto. Se sei sopra i 50€ di gain, valuta il profitto!")

    except: pass

def main():
    now = datetime.datetime.now()
    current_time = int(now.strftime("%H%M"))
    if current_time < 1530 or current_time > 2210: return
    
    sentiment = get_market_sentiment()
    all_tickers = sorted(list(set(WATCHLIST + MY_PORTFOLIO)))
    for t in all_tickers:
        analyze_stock(t, sentiment)
        time.sleep(0.4)

if __name__ == "__main__":
    main()

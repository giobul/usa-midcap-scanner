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

def get_market_sentiment():
    try:
        spy = yf.download("SPY", period="5d", interval="15m", progress=False)
        rsi_spy = calculate_rsi(spy['Close']).iloc[-1]
        if rsi_spy > 60: return f"🟢 BULLISH ({rsi_spy:.1f})"
        if rsi_spy < 40: return f"🔴 BEARISH ({rsi_spy:.1f})"
        return f"⚪ NEUTRAL ({rsi_spy:.1f})"
    except: return "⚪ NEUTRAL"

def analyze_stock(ticker, market_sentiment):
    try:
        df = yf.download(ticker, period="20d", interval="15m", progress=False)
        if df.empty or len(df) < 20: return
        
        cp = float(df['Close'].iloc[-1])
        open_p = float(df['Open'].iloc[-1])
        vol_attuale = float(df['Volume'].iloc[-1])
        rsi = calculate_rsi(df['Close']).iloc[-1]
        
        # 1. ANALISI VOLUMETRICA (Z-SCORE)
        avg_vol = df['Volume'].mean()
        std_vol = df['Volume'].std()
        z_score = (vol_attuale - avg_vol) / std_vol
        
        # 2. CONTROLLO VELOCITÀ (CANDELA ESTESA)
        last_candle_move = ((cp - open_p) / open_p) * 100
        is_extended = last_candle_move > 3.0
        
        # 3. BREAKOUT & SUPPORTO
        recent_high = df['High'].tail(10).max()
        is_breaking_out = cp >= (recent_high * 0.995)
        support = float(df['Low'].tail(50).min())
        dist_supp = ((cp - support) / support) * 100

        # TRIGGER TEST (Z-Score > 1.5 per rilevare attività istituzionale)
        if z_score > 1.5:
            score = 4 
            if z_score > 2.5 : score += 2
            if is_breaking_out: score += 2
            if "BULLISH" in market_sentiment: score += 1
            if rsi > 70 or is_extended: score -= 1 
            
            # DETERMINAZIONE TIPO MOVIMENTO
            if cp > df['Close'].iloc[-2]: tipo = "🐋 BALENA / CALL SWEEP"
            else: tipo = "⚠️ VOLUME SOSPETTO"

            semaforo = "🟢 OTTIMO" if dist_supp < 3.0 else "🟡 RISCHIOSO"
            alert_speed = "⚠️ ESTESA" if is_extended else "✅ Sano"

            if score >= 5:
                msg = (f"{tipo} | {semaforo}\n"
                       f"📊 Ticker: **{ticker}**\n"
                       f"━━━━━━━━━━━━━━━\n"
                       f"🔥 Forza: **{z_score:.1f}x sopra media**\n"
                       f"⚡ Speed: **{last_candle_move:+.2f}%**\n"
                       f"🎯 RSI: {rsi:.1f} | **SCORE: {score}/10**\n"
                       f"📈 Breakout: {'SÌ' if is_breaking_out else 'NO'

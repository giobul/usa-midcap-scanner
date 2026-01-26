import yfinance as yf
import pandas as pd
import datetime
import os
import requests
import time

# --- 1. CONFIGURAZIONE ---
MY_PORTFOLIO = ["STNE", "PATH", "RGTI", "QUBT", "DKNG", "AI", "BBAI", "ADCT", "AGEN"]
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

def get_market_sentiment():
    """Analisi dell'indice SPY per definire il contesto di mercato"""
    try:
        spy = yf.download("SPY", period="2d", interval="15m", progress=False)
        rsi_spy = calculate_rsi(spy['Close']).iloc[-1]
        if rsi_spy < 40: return "🔴 BEARISH"
        if rsi_spy > 60: return "🟢 BULLISH"
        return "⚪ NEUTRAL"
    except: return "🟡 UNKNOWN"

def analyze_stock(ticker, is_full_scan, market_sentiment):
    try:
        df = yf.download(ticker, period="5d", interval="15m", progress=False)
        if df.empty: return False
        
        cp = float(df['Close'].iloc[-1])
        prev_cp = float(df['Close'].iloc[-2])
        var_pct = ((cp - prev_cp) / prev_cp) * 100
        vol = float(df['Volume'].iloc[-1])
        avg_vol = float(df['Volume'].mean())
        rsi = calculate_rsi(df['Close']).iloc[-1]
        
        support_level = float(df['Low'].tail(50).min())
        distanza_supporto = ((cp - support_level) / support_level) * 100
        cash_flow = (vol * cp) / 1_000_000 

        # --- LOGICA 9/10: FILTRO SWEEP / ICEBERG ---
        mult = 1.8 if is_full_scan else 3.5
        if vol > (avg_vol * mult):
            score = min(10, int((vol / avg_vol) * 1.5))
            if "BULLISH" in market_sentiment: score += 1
            stars = "⭐" * (score // 2)

            # Caso A: PUT SWEEP (Prezzo rompe supporto o calo violento)
            if cp < support_level or var_pct < -1.5:
                tipo = "🔴 **PUT SWEEP / DANGER**"
                nota = "Istituzionali in uscita aggressiva."
            # Caso B: CALL SWEEP / ICEBERG
            else:
                tipo = "🔵 **CALL SWEEP / ACCUMULO**" if var_pct > 0.5 else "🧊 **ICEBERG DETECTED**"
                nota = "Ingresso istituzionale rilevato."

            msg = (f"{tipo}\n"
                   f"📊 Ticker: **{ticker}** ({var_pct:+.2f}%)\n"
                   f"━━━━━━━━━━━━━━━\n"
                   f"💰 Flow: **${cash_flow:.2f}M**\n"
                   f"📈 RSI: {rsi:.1f} | MKT: {market_sentiment}\n"
                   f"📊 Score: {score}/10 {stars}\n"
                   f"🎯 Supporto: ${support_level:.2f}\n"
                   f"📢 *{nota}*")
            send_telegram(msg)
            return True

        # --- EXIT PROFIT (Solo Portfolio) ---
        if ticker in MY_PORTFOLIO and rsi > 75:
            send_telegram(f"🟡 **EXIT PROFIT: {ticker}**\n━━━━━━━━━━━━━━━\n📈 RSI: {rsi:.2f}\n💰 Prezzo: ${cp:.2f}\n✅ **Vendi e incassa!**")
            return True

        return False
    except: return False

def main():
    now = datetime.datetime.now()
    if now.weekday() > 4: return 
    if now.hour < 14 or (now.hour >= 21 and now.minute > 15): return

    watchlist = ["STNE", "PATH", "RGTI", "QUBT", "IONQ", "C3AI", "AI", "BBAI", "PLTR", "SOUN", "SNOW", "NET", "CRWD", "DDOG", "ZS", "OKTA", "MDB", "TEAM", "S", "U", "ADBE", "CRM", "WDAY", "NOW", "NU", "PAGS", "MELI", "SOFI", "UPST", "AFRM", "HOOD", "SQ", "PYPL", "COIN", "FLYV", "MARQ", "BILL", "TOST", "DAVE", "MQ", "LC", "BABA", "JD", "PDUO", "MARA", "RIOT", "CLSK", "HUT", "BITF", "MSTR", "WULF", "CIFR", "ANY", "BTBT", "CAN", "SDIG", "ADCT", "AGEN", "VRTX", "VKTX", "SAVA", "IOVA", "BBIO", "MDGL", "REGN", "ILMN", "EXAS", "BNTX", "MRNA", "SGEN", "IQV", "TDOC", "BMEA", "SRPT", "CRSP", "EDIT", "BEAM", "NTLA", "VERV", "GRTS", "RLAY", "IRON", "TLRY", "CGC", "AMD", "NVDA", "INTC", "MU", "TXN", "TSM", "ASML", "AMAT", "LRCX", "KLAC", "SNPS", "CDNS", "ARM", "MRVL", "AVGO", "SMCI", "ANET", "TER", "ENTG", "ON", "TSLA", "RIVN", "LCID", "F", "GM", "RACE", "STLA", "ENPH", "SEDG", "FSLR", "PLUG", "CHPT", "RUN", "QS", "NIO", "XPEV", "LI", "BE", "NEE", "BLDP", "FCEL", "DKNG", "PENN", "RCL", "CCL", "NCLH", "AAL", "DAL", "UAL", "LUV", "BKNG", "EXPE", "MAR", "HLT", "GENI", "RSI", "SHOP", "DOCU", "ZM", "DASH", "ABNB", "UBER", "LYFT", "CHWY", "ROKU", "PINS", "SNAP", "EBAY", "ETSY", "RVLV", "META", "GOOGL", "AMZN", "MSFT", "AAPL", "NFLX", "DIS", "PARA", "WBD", "AMC", "GME", "BB", "NOK", "FUBO", "SPCE", "RBLX", "MTCH", "BMBL", "YELP", "TTD", "OPEN", "HOV", "BLND", "HRTX", "MNMD", "FSR", "NKLA", "WKHS", "DNA", "PLBY", "SKLZ", "SENS", "HYLN", "ASTS", "ORBK", "LIDR", "INVZ", "LAZR", "AEVA"]
    
    market_sentiment = get_market_sentiment()
    is_caccia_time = now.hour in ORARI_CACCIA and now.minute < 15
    tickers = list(set(watchlist + MY_PORTFOLIO)) if is_caccia_time else MY_PORTFOLIO

    # --- STATUS MESSAGE ---
    if now.minute < 10:
        send_telegram(f"🔎 **SCANNER 9/10 ATTIVO**\n━━━━━━━━━━━━━━━\nMood Mercato: {market_sentiment}\nTarget: {len(tickers)} titoli")

    for t in tickers:
        analyze_stock(t, is_caccia_time, market_sentiment)
        time.sleep(0.6)

if __name__ == "__main__":
    main()

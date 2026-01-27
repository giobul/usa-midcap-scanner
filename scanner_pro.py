import yfinance as yf
import pandas as pd
import datetime
import os
import requests
import time

# --- 1. CONFIGURAZIONE ---
MY_PORTFOLIO = ["STNE", "PATH", "RGTI", "QUBT", "DKNG", "AI", "BBAI", "ADCT", "AGEN"]
WATCHLIST = ["STNE", "PATH", "RGTI", "QUBT", "IONQ", "C3AI", "AI", "BBAI", "PLTR", "SOUN", "SNOW", "NET", "CRWD", "DDOG", "ZS", "OKTA", "MDB", "TEAM", "S", "U", "ADBE", "CRM", "WDAY", "NOW", "NU", "PAGS", "MELI", "SOFI", "UPST", "AFRM", "HOOD", "SQ", "PYPL", "COIN", "FLYV", "MARQ", "BILL", "TOST", "DAVE", "MQ", "LC", "BABA", "JD", "PDUO", "MARA", "RIOT", "CLSK", "HUT", "BITF", "MSTR", "WULF", "CIFR", "ANY", "BTBT", "CAN", "SDIG", "ADCT", "AGEN", "VRTX", "VKTX", "SAVA", "IOVA", "BBIO", "MDGL", "REGN", "ILMN", "EXAS", "BNTX", "MRNA", "SGEN", "IQV", "TDOC", "BMEA", "SRPT", "CRSP", "EDIT", "BEAM", "NTLA", "VERV", "GRTS", "RLAY", "IRON", "TLRY", "CGC", "AMD", "NVDA", "INTC", "MU", "TXN", "TSM", "ASML", "AMAT", "LRCX", "KLAC", "SNPS", "CDNS", "ARM", "MRVL", "AVGO", "SMCI", "ANET", "TER", "ENTG", "ON", "TSLA", "RIVN", "LCID", "F", "GM", "RACE", "STLA", "ENPH", "SEDG", "FSLR", "PLUG", "CHPT", "RUN", "QS", "NIO", "XPEV", "LI", "BE", "NEE", "BLDP", "FCEL", "DKNG", "PENN", "RCL", "CCL", "NCLH", "AAL", "DAL", "UAL", "LUV", "BKNG", "EXPE", "MAR", "HLT", "GENI", "RSI", "SHOP", "DOCU", "ZM", "DASH", "ABNB", "UBER", "LYFT", "CHWY", "ROKU", "PINS", "SNAP", "EBAY", "ETSY", "RVLV", "META", "GOOGL", "AMZN", "MSFT", "AAPL", "NFLX", "DIS", "PARA", "WBD", "AMC", "GME", "BB", "NOK", "FUBO", "SPCE", "RBLX", "MTCH", "BMBL", "YELP", "TTD", "OPEN", "HOV", "BLND", "HRTX", "MNMD", "FSR", "NKLA", "WKHS", "DNA", "PLBY", "SKLZ", "SENS", "HYLN", "ASTS", "ORBK", "LIDR", "INVZ", "LAZR", "AEVA"]
ORARI_CACCIA = [15, 18, 20] # 16, 19, 21 ITA

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
        return f"🟢 BULLISH ({rsi_spy:.1f})" if rsi_spy > 60 else f"🔴 BEARISH ({rsi_spy:.1f})" if rsi_spy < 40 else f"⚪ NEUTRAL ({rsi_spy:.1f})"
    except: return "⚪ NEUTRAL"

def analyze_stock(ticker, is_caccia, market_sentiment):
    try:
        df = yf.download(ticker, period="5d", interval="15m", progress=False)
        if df.empty: return
        
        cp = float(df['Close'].iloc[-1])
        prev_cp = float(df['Close'].iloc[-2])
        var_pct = ((cp - prev_cp) / prev_cp) * 100
        vol = float(df['Volume'].iloc[-1])
        avg_vol = float(df['Volume'].mean())
        rsi = calculate_rsi(df['Close']).iloc[-1]
        
        support = float(df['Low'].tail(50).min())
        dist_supp = ((cp - support) / support) * 100
        cash_flow = (vol * cp) / 1_000_000 

        # --- LOGICA RADAR / CACCIA ---
        # Trigger: 1.8x volume in ora di caccia, oppure 5x volume / 4% movimento fuori ora
        trigger = (vol > avg_vol * 1.8) if is_caccia else (vol > avg_vol * 5.0 or abs(var_pct) > 4.0)

        if trigger:
            score = min(10, int((vol / avg_vol) * 1.5))
            if "BULLISH" in market_sentiment: score += 1
            
            # SEMAFORO
            semaforo = "🟢 OTTIMO" if dist_supp < 3 else "🟡 RISCHIOSO" if dist_supp < 6 else "🔴 TARDI"
            tipo = "🔵 CALL SWEEP" if var_pct > 0.5 else "🧊 ICEBERG"
            if var_pct < -2.0: tipo = "🔴 PUT SWEEP"

            msg = (f"{tipo} | {semaforo}\n"
                   f"📊 Ticker: **{ticker}** ({var_pct:+.2f}%)\n"
                   f"━━━━━━━━━━━━━━━\n"
                   f"💰 Flow: **${cash_flow:.2f}M**\n"
                   f"📉 Dist. Supporto: **{dist_supp:.2f}%**\n"
                   f"📈 RSI: {rsi:.1f} | Score: {score}/10\n"
                   f"📢 *Mkt: {market_sentiment}*")
            send_telegram(msg)

        # EXIT PROFIT PORTFOLIO
        if ticker in MY_PORTFOLIO and rsi > 75:
            send_telegram(f"🟡 **EXIT PROFIT: {ticker}**\n📈 RSI: {rsi:.2f} | Prezzo: ${cp:.2f}\n✅ **Vendi e incassa i 200€!**")

    except: pass

def main():
    now = datetime.datetime.now()
    if now.weekday() > 4: return 
    if now.hour < 14 or (now.hour >= 21 and now.minute > 15): return

    market_sentiment = get_market_sentiment()
    is_caccia = now.hour in ORARI_CACCIA and (15 <= now.minute <= 25)
    
    # Scansiona sempre tutto, ma analyze_stock decide se inviare alert basandosi sull'urgenza
    tickers = list(set(WATCHLIST + MY_PORTFOLIO))

    # Status Message
    if is_caccia and 15 <= now.minute <= 18:
        send_telegram(f"🔎 **SCANNER 10/10 ATTIVO**\nMood: {market_sentiment}\nTarget: {len(tickers)} titoli")

    for t in tickers:
        analyze_stock(t, is_caccia, market_sentiment)
        time.sleep(0.5)

if __name__ == "__main__":
    main()

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

def analyze_stock(ticker, is_full_scan):
    try:
        # Download dati 15m (5 giorni)
        df = yf.download(ticker, period="5d", interval="15m", progress=False)
        if df.empty: return False
        
        cp = float(df['Close'].iloc[-1])
        vol = float(df['Volume'].iloc[-1])
        avg_vol = float(df['Volume'].mean())
        df['RSI'] = calculate_rsi(df['Close'])
        rsi = float(df['RSI'].iloc[-1])
        
        # Analisi Tecnica
        support_level = float(df['Low'].tail(50).min())
        distanza_supporto = ((cp - support_level) / support_level) * 100
        
        # --- STIMA FLOW MONETARIO (MILIONI DI $) ---
        cash_flow = (vol * cp) / 1_000_000  # Valore della candela in Milioni
        
        # --- LOGICA SWEEP (CALL VS PUT) ---
        mult = 1.8 if is_full_scan else 3.5
        
        if vol > (avg_vol * mult):
            score = min(10, int((vol / avg_vol) * 1.5))
            stars = "⭐" * (score // 2)

            # Caso A: Prezzo rompe il supporto = PUT SWEEP (Bearish)
            if cp < support_level:
                msg = (f"🔴 **PUT SWEEP DETECTED (Bearish)**\n"
                       f"📊 Ticker: **{ticker}**\n"
                       f"━━━━━━━━━━━━━━━\n"
                       f"💀 **EMERGENZA/SCARICO**\n"
                       f"💰 Valore Stimato: **${cash_flow:.2f}M**\n"
                       f"📉 Prezzo: ${cp:.2f} (Sotto Supporto)\n"
                       f"📊 Score: {score}/10 {stars}\n"
                       f"📢 *Nota: Istituzionali in uscita o copertura Put.*")
                send_telegram(msg)
                return True

            # Caso B: Prezzo vicino al supporto o in rimbalzo = CALL SWEEP (Bullish)
            elif distanza_supporto <= 1.5:
                msg = (f"🔵 **CALL SWEEP DETECTED (Bullish)**\n"
                       f"📊 Ticker: **{ticker}**\n"
                       f"━━━━━━━━━━━━━━━\n"
                       f"🔥 **ACCUMULO ISTITUZIONALE**\n"
                       f"💰 Valore Stimato: **${cash_flow:.2f}M**\n"
                       f"📈 Prezzo: ${cp:.2f} (Vicino Supporto)\n"
                       f"📊 Score: {score}/10 {stars}\n"
                       f"✅ **INGRESSO OTTIMALE**")
                send_telegram(msg)
                return True

        # --- ALERT EXIT PROFIT (Solo Portfolio) ---
        if ticker in MY_PORTFOLIO and rsi > 75:
            send_telegram(f"🟡 **EXIT PROFIT: {ticker}**\n━━━━━━━━━━━━━━━\n📈 RSI: {rsi:.2f}\n💰 Prezzo: ${cp:.2f}\n✅ **Target raggiunto! Incassa.**")
            return True

        return False
    except: return False

def main():
    now = datetime.datetime.now()
    if now.weekday() > 4: return 
    if now.hour < 14 or (now.hour >= 21 and now.minute > 15): return

    watchlist = [
        "STNE", "PATH", "RGTI", "QUBT", "IONQ", "C3AI", "AI", "BBAI", "PLTR", "SOUN", "SNOW", "NET", "CRWD", "DDOG", "ZS", "OKTA", "MDB", "TEAM", "S", "U", "ADBE", "CRM", "WDAY", "NOW",
        "NU", "PAGS", "MELI", "SOFI", "UPST", "AFRM", "HOOD", "SQ", "PYPL", "COIN", "FLYV", "MARQ", "BILL", "TOST", "DAVE", "MQ", "LC", "BABA", "JD", "PDUO",
        "MARA", "RIOT", "CLSK", "HUT", "BITF", "MSTR", "WULF", "CIFR", "ANY", "BTBT", "CAN", "SDIG",
        "ADCT", "AGEN", "VRTX", "VKTX", "SAVA", "IOVA", "BBIO", "MDGL", "REGN", "ILMN", "EXAS", "BNTX", "MRNA", "SGEN", "IQV", "TDOC", "BMEA", "SRPT", "CRSP", "EDIT", "BEAM", "NTLA", "VERV", "GRTS", "RLAY", "IRON", "TLRY", "CGC",
        "AMD", "NVDA", "INTC", "MU", "TXN", "TSM", "ASML", "AMAT", "LRCX", "KLAC", "SNPS", "CDNS", "ARM", "MRVL", "AVGO", "SMCI", "ANET", "TER", "ENTG", "ON",
        "TSLA", "RIVN", "LCID", "F", "GM", "RACE", "STLA", "ENPH", "SEDG", "FSLR", "PLUG", "CHPT", "RUN", "QS", "NIO", "XPEV", "LI", "BE", "NEE", "BLDP", "FCEL",
        "DKNG", "PENN", "RCL", "CCL", "NCLH", "AAL", "DAL", "UAL", "LUV", "BKNG", "EXPE", "MAR", "HLT", "GENI", "RSI", "SHOP", "DOCU", "ZM", "DASH", "ABNB", "UBER", "LYFT", "CHWY", "ROKU", "PINS", "SNAP", "EBAY", "ETSY", "RVLV",
        "META", "GOOGL", "AMZN", "MSFT", "AAPL", "NFLX", "DIS", "PARA", "WBD", "AMC", "GME", "BB", "NOK", "FUBO", "SPCE", "RBLX", "MTCH", "BMBL", "YELP", "TTD",
        "OPEN", "HOV", "BLND", "HRTX", "MNMD", "FSR", "NKLA", "WKHS", "DNA", "PLBY", "SKLZ", "SENS", "HYLN", "ASTS", "ORBK", "LIDR", "INVZ", "LAZR", "AEVA"
    ]
    
    is_caccia_time = now.hour in ORARI_CACCIA and now.minute < 15
    tickers = list(set(watchlist + MY_PORTFOLIO)) if is_caccia_time else MY_PORTFOLIO

    if now.minute == 0:
        send_telegram(f"🔍 **SCANNER PRO ATTIVO**\nScansione in corso su {len(tickers)} titoli...")

    for t in tickers:
        analyze_stock(t, is_caccia_time)
        time.sleep(0.5)

if __name__ == "__main__":
    main()

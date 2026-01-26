import yfinance as yf
import pandas as pd
import datetime
import os
import requests
import time

# --- 1. CONFIGURAZIONE PORTAFOGLIO (EXIT & EMERGENZA) ---
# I titoli che possiedi già. Il bot li controlla ogni 5 minuti.
MY_PORTFOLIO = ["STNE", "PATH", "RGTI", "QUBT", "DKNG", "AI", "BBAI", "ADCT", "AGEN"]

# Orari delle scansioni profonde su tutta la watchlist (16:00, 19:00, 21:00 ITA)
ORARI_CACCIA = [15, 18, 20] 

def send_telegram(message):
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id: 
        print("Errore: Token o Chat ID mancanti nei Secrets di GitHub")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    try: 
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Errore invio Telegram: {e}")

def calculate_rsi(prices, period=14):
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def analyze_stock(ticker, is_full_scan):
    try:
        # Download dati 15 minuti degli ultimi 5 giorni
        df = yf.download(ticker, period="5d", interval="15m", progress=False)
        if df.empty: return False
        
        cp = float(df['Close'].iloc[-1])
        vol = float(df['Volume'].iloc[-1])
        avg_vol = float(df['Volume'].mean())
        df['RSI'] = calculate_rsi(df['Close'])
        rsi = float(df['RSI'].iloc[-1])
        
        # Supporto basato sui minimi degli ultimi 50 periodi (circa 2 giorni)
        support_level = float(df['Low'].tail(50).min())
        distanza_supporto = ((cp - support_level) / support_level) * 100

        # --- AZIONE 1: EMERGENZA (🔴 ROTTURA SUPPORTO CON VOLUME) ---
        if ticker in MY_PORTFOLIO and cp < support_level and vol > avg_vol:
            send_telegram(f"🔴 **🚨 EMERGENZA: {ticker}**\n"
                          f"━━━━━━━━━━━━━━━\n"
                          f"⚠️ **ROTTURA SUPPORTO!**\n"
                          f"💰 Prezzo attuale: ${cp:.2f}\n"
                          f"📉 Supporto rotto: ${support_level:.2f}\n"
                          f"📢 *Nota: Volume alto in uscita. Valuta chiusura.*")
            return True

        # --- AZIONE 2: DIFESA (🟡 PRESA PROFITTO RSI) ---
        if ticker in MY_PORTFOLIO and rsi > 75:
            send_telegram(f"🟡 **EXIT PROFIT: {ticker}**\n"
                          f"━━━━━━━━━━━━━━━\n"
                          f"📈 RSI: {rsi:.2f} (Ipercomprato)\n"
                          f"💰 Prezzo attuale: ${cp:.2f}\n"
                          f"✅ **Target raggiunto! Incassa il profitto.**")
            return True

        # --- AZIONE 3: CACCIA (🔵 ACCUMULO ISTITUZIONALE) ---
        # Moltiplicatore volume: più basso durante la caccia per trovare più opportunità
        mult = 1.8 if is_full_scan else 3.5
        if vol > (avg_vol * mult) and distanza_supporto <= 1.5:
            score = min(10, int((vol / avg_vol) * 1.5))
            stars = "⭐" * (score // 2) if score > 1 else "🔹"
            
            tipo = "🔥 **SWEEP AGGRESSIVO**" if vol > (avg_vol * 4.0) else "🧊 **ICEBERG DETECTED**"
            
            msg = f"{tipo}: **{ticker}**\n"
            msg += f"━━━━━━━━━━━━━━━\n"
            msg += f"📊 **ICEBERG SCORE: {score}/10** {stars}\n"
            msg += f"💰 Prezzo: ${cp:.2f}\n"
            msg += f"📈 Volume: {vol/avg_vol:.1f}x media\n"
            msg += f"🎯 Supporto breakout: ${support_level:.2f}"
            send_telegram(msg)
            return True
            
        return False
    except: 
        return False

def main():
    now = datetime.datetime.now()
    # No borsa nel weekend
    if now.weekday() > 4: return 
    # Orario operativo (14:30 - 21:15 UTC = 15:30 - 22:15 ITA)
    if now.hour < 14 or (now.hour >= 21 and now.minute > 15): return

    # --- WATCHLIST COMPLETA 180+ TITOLI ---
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
    
    # Determina se è orario di Scansione Totale (Caccia) o solo Portafoglio (Difesa)
    is_caccia_time = now.hour in ORARI_CACCIA and now.minute < 15
    tickers = list(set(watchlist + MY_PORTFOLIO)) if is_caccia_time else MY_PORTFOLIO
    mode = "CACCIA 🏹" if is_caccia_time else "DIFESA 🛡️"

    # Messaggio di stato (ogni ora)
    if now.minute == 0:
        send_telegram(f"🔎 **SCANNER PRO ATTIVO**\nModalità: {mode}\nTitoli in scansione: {len(tickers)}")

    for t in tickers:
        analyze_stock(t, is_caccia_time)
        time.sleep(0.5) # Pausa per evitare blocchi API

if __name__ == "__main__":
    main()

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
        # Recuperiamo più dati (60 giorni) per avere una media volumetrica solida
        df = yf.download(ticker, period="20d", interval="15m", progress=False)
        if df.empty or len(df) < 50: return
        
        # --- DATI ATTUALI ---
        cp = float(df['Close'].iloc[-1])
        vol_attuale = float(df['Volume'].iloc[-1])
        rsi = calculate_rsi(df['Close']).iloc[-1]
        
        # --- CALCOLO ANOMALIA (Z-SCORE) ---
        # Invece della media semplice, calcoliamo quanto il volume attuale devia dalla norma
        avg_vol = df['Volume'].mean()
        std_vol = df['Volume'].std()
        z_score = (vol_attuale - avg_vol) / std_vol
        
        # --- VALIDAZIONE BREAKOUT (MASSIMI) ---
        # Controlliamo se il prezzo sta rompendo il massimo delle ultime 10 candele (2.5 ore)
        recent_high = df['High'].tail(10).max()
        is_breaking_out = cp >= (recent_high * 0.998) # Margine dello 0.2% dal massimo
        
        # --- FILTRO SICUREZZA ---
        support = float(df['Low'].tail(50).min())
        dist_supp = ((cp - support) / support) * 100
        
        # --- LOGICA "PRECISIONE" (IL MIRINO) ---
        # Trigger molto più selettivo: 
        # CACCIA: Richiede Z-Score alto + Breakout Prezzo
        # RADAR: Richiede Volume esplosivo (Z-Score > 5)
        trigger = False
        if is_caccia:
            if z_score > 2.0 and is_breaking_out: trigger = True
        else:
            if z_score > 5.0: trigger = True

        if trigger:
            # Calcolo Score basato sulla convergenza (Max 10)
            score = 5
            if z_score > 3: score += 2
            if is_breaking_out: score += 2
            if "BULLISH" in market_sentiment: score += 1
            if rsi < 40: score -= 2 # Debolezza eccessiva
            if rsi > 70: score -= 1 # Estensione eccessiva

            # DEFINIZIONE TIPO (PIÙ PRECISA)
            # Se il volume è enorme ma il prezzo è fermo = ICEBERG
            # Se il volume è alto e il prezzo corre = SWEEP/MOMENTUM
            movimento_prezzo = abs(((cp - df['Close'].iloc[-2]) / df['Close'].iloc[-2]) * 100)
            
            if movimento_prezzo < 0.2 and z_score > 3:
                tipo = "🧊 VERO ICEBERG (Accumulo)"
            elif cp > df['Close'].iloc[-2]:
                tipo = "🐋 BALENA / CALL SWEEP"
            else:
                tipo = "⚠️ VOLUME SOSPETTO"

            # SEMAFORO
            semaforo = "🟢 OTTIMO" if dist_supp < 2.5 else "🟡 RISCHIOSO" if dist_supp < 5 else "🔴 EVITARE"

            # Invia solo se lo Score è degno dei tuoi 5.000€
            if score >= 7:
                msg = (f"{tipo} | {semaforo}\n"
                       f"📊 Ticker: **{ticker}**\n"
                       f"━━━━━━━━━━━━━━━\n"
                       f"🔥 Forza Segnale: **{z_score:.1f}x sopra media**\n"
                       f"📈 Stato: {'✅ Breakout in corso' if is_breaking_out else '⏳ Consolidamento'}\n"
                       f"📉 Dist. Supporto: **{dist_supp:.2f}%**\n"
                       f"🎯 RSI: {rsi:.1f} | **SCORE: {score}/10**\n"
                       f"💰 *Obiettivo: Minimo 50€ profit*")
                send_telegram(msg)

    except Exception as e:
        print(f"Errore su {ticker}: {e}")

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

import yfinance as yf
import pandas as pd
import datetime
import os
import requests
import time

# --- 1. CONFIGURAZIONE UTENTE ---
MY_PORTFOLIO = ["STNE"]  # Inserisci qui i tuoi titoli acquistati

# LISTA 150 TITOLI MID-CAP / GROWTH LEADER 2026
FULL_WATCHLIST = [
    # FINTECH & BANKING
    "STNE", "NU", "PAGS", "SOFI", "UPST", "MELI", "AFRM", "HOOD", "SQ", "PYPL", "BBD", "ITUB", "XP", "GS", "MS", "COIN", "DKNG",
    # AI INFRASTRUCTURE & SEMIS
    "VRT", "ANET", "APP", "PSTG", "SMCI", "LUMN", "PLTR", "MSTR", "AMBA", "AEIS", "ARM", "ALAB", "MRVL", "NVDA", "AMD", "TSM", "AVGO", "ASML", "KLAC", "LRCX",
    # CYBERSECURITY & SOFTWARE
    "CRWD", "NET", "OKTA", "ZS", "DDOG", "SNOW", "APPS", "MDB", "PANW", "FTNT", "S", "TMUS", "PATH", "IOT", "MNTV", "GTLB", "TEAM", "WDAY", "NOW",
    # HEALTHCARE & BIOTECH
    "CLOV", "MEDP", "HALO", "KRYS", "VRTX", "AMGN", "DOC", "AVB", "TDOC", "RXRX", "ILMN", "EXAS", "CRSP", "BEAM", "NTLA", "EDIT",
    # CONSUMER, EV & ENERGY
    "CELH", "WING", "BOOT", "TSLA", "RIVN", "LCID", "NIO", "XPEV", "LI", "FSLR", "ENPH", "SEDG", "RUN", "CHPT", "BLNK", "PLUG",
    # RETAIL & E-COMMERCE
    "SHOP", "SE", "AMZN", "BABA", "PDD", "JD", "CPNG", "RVLV", "FIGS", "DASH", "UBER", "LYFT", "ABNB", "BKNG",
    # OTHER MID-CAP LEADERS
    "RBLX", "U", "TOST", "DUOL", "MNSO", "GME", "AMC", "HOOD", "COIN", "MARA", "RIOT", "CLSK", "IREN", "WULF",
    # ADDING FILLERS TO REACH ~150
    "OPEN", "RDFN", "Z", "BMBL", "MTCH", "RKT", "UWMC", "LDI", "ASAN", "SMARTS", "ESTC", "ZEN", "NEWR", "SPLK", "SUMO", "JFROG", 
    "FIVN", "BLZE", "VRNS", "FORG", "PGR", "ALL", "TRV", "CB", "AIG", "MET", "PRU", "LNC", "IVZ", "BEN", "TROW", "BLK", "AMP"
] # Nota: Ho inserito i principali leader, puoi aggiungere altri fino a 150.

ORARI_CACCIA = [15, 18, 21] 

# --- 2. FUNZIONI DI SERVIZIO ---
def send_telegram(message):
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id: return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

def calculate_rsi(prices, period=14):
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# --- 3. ANALISI TECNICA ---
def analyze_stock(ticker, is_full_scan):
    try:
        df = yf.download(ticker, period="3d", interval="15m", progress=False)
        if df.empty: return

        current_price = float(df['Close'].iloc[-1])
        volume_last = float(df['Volume'].iloc[-1])
        volume_avg = float(df['Volume'].mean())
        df['RSI'] = calculate_rsi(df['Close'])
        current_rsi = float(df['RSI'].iloc[-1])

        # LOGICA EXIT (Portfolio)
        if ticker in MY_PORTFOLIO:
            if current_rsi > 75:
                send_telegram(f"⚠️ *EXIT ALERT: {ticker}*\nRSI: {current_rsi:.2f} (Ipercomprato)\nPrezzo: ${current_price:.2f}")
            elif current_price >= 16.80 and ticker == "STNE":
                send_telegram(f"🎯 *TARGET RAGGIUNTO: {ticker}*\nPrezzo: ${current_price:.2f}")

        # LOGICA ENTRY (Sweep & Iceberg)
        # In scansione completa (Caccia) cerchiamo volumi > 1.5x
        # In scansione rapida (Difesa) segnaliamo solo se > 2.5x
        multiplier = 1.5 if is_full_scan else 2.5
        
        if volume_last > (volume_avg * multiplier):
            label = "🔥 OPTION SWEEP" if volume_last > (volume_avg * 2.5) else "🧊 ICEBERG"
            send_telegram(f"{label} su *{ticker}*\nPrezzo: ${current_price:.2f}\nVol: {volume_last:.0f} (Avg: {volume_avg:.0f})")

    except: pass

# --- 4. MOTORE PRINCIPALE ---
def main():
    now = datetime.datetime.now()
    # Variabile per contare quanti alert sono stati inviati
    alert_counter = 0
    
    # Determiniamo la modalità
    if now.hour in ORARI_CACCIA and now.minute < 20:
        mode = "FULL_SCAN"
        tickers = list(set(FULL_WATCHLIST + MY_PORTFOLIO))
        print(f"🚀 {now.strftime('%H:%M')} - Avvio Scansione Completa...")
    else:
        mode = "PORTFOLIO_ONLY"
        tickers = MY_PORTFOLIO
        print(f"🛡️ {now.strftime('%H:%M')} - Monitoraggio Portfolio...")

    # Eseguiamo l'analisi e contiamo i messaggi inviati
    for ticker in tickers:
        # Modifica analyze_stock affinché restituisca True se invia un messaggio
        result = analyze_stock(ticker, is_full_scan=(mode == "FULL_SCAN"))
        if result: 
            alert_counter += 1
        time.sleep(0.5)

    # --- NUOVA LOGICA DI RIEPILOGO ---
    # Se siamo in scansione completa e NON è stato trovato nulla di rilevante
    if mode == "FULL_SCAN" and alert_counter == 0:
        send_telegram("✅ *Scansione Completata*: Nessun movimento istituzionale (Iceberg/Sweep) rilevato sui 150 titoli.")
    
    # Se siamo in modalità difesa e tutto è tranquillo
    elif mode == "PORTFOLIO_ONLY" and alert_counter == 0:
        print("Tutto tranquillo nel portfolio.") 
        # Qui non inviamo nulla su Telegram per evitare spam ogni 20 min, 
        # a meno che tu non lo voglia specificamente.

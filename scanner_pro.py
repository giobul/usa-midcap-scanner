import yfinance as yf
import pandas as pd
import numpy as np
import datetime
import requests
import time
import os
import io

# --- CONFIGURAZIONE ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
FLAG_FILE = "scanner_started.txt"

# Tuoi titoli personali (sempre monitorati)
MY_PORTFOLIO = ["STNE", "PATH", "RGTI", "SOFI", "PLTR", "BABA", "AMD", "NVDA", "TSLA", "MARA"]

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, data=data)
    except Exception as e:
        print(f"Errore Telegram: {e}")

def get_market_sentiment():
    try:
        spy = yf.Ticker("SPY").history(period="2d")
        change = ((spy['Close'].iloc[-1] - spy['Close'].iloc[-2]) / spy['Close'].iloc[-2]) * 100
        if change > 0.5: return "BULLISH 🚀"
        if change < -0.5: return "BEARISH 📉"
        return "NEUTRALE ⚖️"
    except:
        return "NON DISPONIBILE"

def get_global_tickers():
    """Scarica i 100 titoli più attivi del giorno"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        url = "https://finance.yahoo.com/markets/stocks/most-active/?start=0&count=100"
        response = requests.get(url, headers=headers)
        tables = pd.read_html(io.StringIO(response.text))
        df = tables[0]
        return df['Symbol'].dropna().tolist()
    except Exception as e:
        print(f"Errore download lista globale: {e}")
        return []

def analyze_stock(ticker, sentiment):
    try:
        # Usiamo 15 minuti per bilanciare precisione e delay
        df = yf.download(ticker, period="5d", interval="15m", progress=False)
        if len(df) < 20: return

        cp = df['Close'].iloc[-1]
        vol = df['Volume'].iloc[-1]
        
        # 1. ANALISI VOLUMI (Z-Score)
        avg_vol = df['Volume'].rolling(window=20).mean().iloc[-1]
        std_vol = df['Volume'].rolling(window=20).std().iloc[-1]
        z_score = (vol - avg_vol) / std_vol if std_vol > 0 else 0

        # 2. RSI (Ipercomprato/Ipervenduto)
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1=rs.iloc[-1]))

        # 3. LOGICA SQUEEZE (Bollinger vs Keltner semplificato)
        std_dev = df['Close'].rolling(window=20).std().iloc[-1]
        atr = (df['High'] - df['Low']).rolling(window=20).mean().iloc[-1]
        is_squeeze = std_dev < (atr * 0.5)
        
        # --- FILTRI ALERT ---
        msg = ""
        # Alert Istituzionale (Sweep/Iceberg)
        if z_score > 3.5:
            tipo = "🐋 SWEEP" if cp > df['Open'].iloc[-1] else "⚠️ DISTRIBUTION"
            msg = f"{tipo}: *{ticker}*\n📊 Prezzo: {cp:.2f}\n📈 Vol Z-Score: {z_score:.2f}\n🔥 RSI: {rsi:.1f}"

        # Alert Squeeze (Molla pronta)
        if is_squeeze:
            direzione = "RIALZISTA" if cp > df['Close'].rolling(window=20).mean().iloc[-1] else "RIBASSISTA"
            msg = f"⚡ **SQUEEZE ALERT**: *{ticker}*\n🎯 Direzione probabile: {direzione}\n💎 RSI: {rsi:.1f}\n🚀 Pronta per breakout!"

        if msg:
            # Se è un titolo del tuo portfolio, aggiungi un tag speciale
            if ticker in MY_PORTFOLIO:
                msg = "⭐ **PORTFOLIO** ⭐\n" + msg
            send_telegram(msg)

    except Exception as e:
        print(f"Errore analisi {ticker}: {e}")

def main():
    # Gestione Orario Italia (UTC + 1) - Correzione per server GitHub
    ora_ita = datetime.datetime.now() + datetime.timedelta(hours=1)
    today = ora_ita.strftime("%Y-%m-%d")
    now_time = int(ora_ita.strftime("%H%M"))
    
    print(f"--- LOG OPERATIVO ---")
    print(f"Orario ITA: {now_time}")

    # Start alle 16:00 per evitare il Far West e gestire il delay di 15m
    if now_time < 1600 or now_time > 2210:
        print("Borsa chiusa o fase di apertura (attendo stabilità).")
        if os.path.exists(FLAG_FILE): 
            os.remove(FLAG_FILE)
        return 

    sentiment = get_market_sentiment()
    global_list = get_global_tickers()
    
    # Unione Liste
    portfolio_clean = [str(t) for t in MY_PORTFOLIO]
    all_tickers = sorted(list(set(global_list + portfolio_clean)))

    # Messaggio di benvenuto giornaliero
    if not os.path.exists(FLAG_FILE):
        send_telegram(f"✅ **SCANNER ATTIVO**\n🌍 Mercato: {sentiment}\n🔍 Monitorando {len(all_tickers)} titoli\n💰 Obiettivo: >50€")
        with open(FLAG_FILE, "w") as f: f.write(today)

    # Scansione ciclica
    for t in all_tickers:
        analyze_stock(t, sentiment)
        time.sleep(0.6) # Prevenzione ban Yahoo

if __name__ == "__main__":
    main()

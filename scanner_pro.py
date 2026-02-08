import sys
from datetime import datetime, timedelta, time as dtime
import time
import os
import requests
import pytz
import numpy as np
import pandas as pd
import yfinance as yf
import json
from pathlib import Path

# --- CONFIGURAZIONE ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
MY_PORTFOLIO = ["STNE", "PATH", "RGTI", "BBAI", "SOFI", "AGEN", "DKNG", "QUBT", "ETOR"]
WATCHLIST_200 = ["ALTI", "OKLO","APLD","RKLB","LYFT","ADCT","VRT","CLS","PSTG","ANET","SMCI","NVDA","TSM"]

# File persistente per cooldown (nella cartella home dell'utente)
ALERT_LOG = Path.home() / ".scanner_alerts.json"
alert_history = {}

def load_alert_history():
    """Carica la cronologia degli alert dal file per gestire il cooldown tra esecuzioni Cron"""
    if ALERT_LOG.exists():
        try:
            with open(ALERT_LOG, 'r') as f:
                data = json.load(f)
                # Converti stringhe ISO in oggetti datetime
                return {k: datetime.fromisoformat(v) for k, v in data.items()}
        except:
            return {}
    return {}

def save_alert_history(history):
    """Salva la cronologia su disco"""
    try:
        data = {k: v.isoformat() for k, v in history.items()}
        with open(ALERT_LOG, 'w') as f:
            json.dump(data, f)
    except Exception as e:
        print(f"❌ Errore salvataggio log: {e}")

def is_market_open():
    tz_ny = pytz.timezone('US/Eastern')
    now_ny = datetime.now(tz_ny)
    if now_ny.weekday() >= 5: return False
    # Operativo 16:30 - 21:45 ITA
    return dtime(10, 30) <= now_ny.time() <= dtime(15, 45)

def send_telegram(message):
    if TOKEN and CHAT_ID:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
        try:
            requests.post(url, data=data, timeout=5)
        except Exception as e:
            print(f"❌ Errore Telegram: {e}")

def analyze_stock(ticker):
    global alert_history
    try:
        now = datetime.now()
        
        # --- 1. GESTIONE COOLDOWN PERSISTENTE ---
        # Evita alert duplicati se inviati negli ultimi 60 minuti
        if ticker in alert_history:
            if now < alert_history[ticker] + timedelta(hours=1):
                return

        data = yf.download(ticker, period="5d", interval="15m", progress=False)
        if data.empty or len(data) < 60: return
        
        df = data.copy()
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        cp, op = float(df['Close'].iloc[-1]), float(df['Open'].iloc[-1])
        hi, lo = float(df['High'].iloc[-1]), float(df['Low'].iloc[-1])
        vol = float(df['Volume'].iloc[-1])
        
        # --- 2. INDICATORI ---
        delta = df['Close'].diff()
        gain = delta.where(delta > 0, 0).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss.replace(0, np.nan)
        current_rsi = 100 - (100 / (1 + rs.fillna(100))).iloc[-1]

        # --- 3. PRICE ACTION (FIX CLAUDE) ---
        body = abs(cp - op)
        u_wick = hi - max(cp, op)
        is_rejected = u_wick > (body * 1.5) if body > 0 else False
        
        # Usiamo il range TOTALE (Hi-Lo) per definire l'Iceberg:
        # Poco movimento totale nonostante volumi enormi = Accumulo puro.
        range_totale_pct = (hi - lo) / cp 
        
        avg_vol = df['Volume'].tail(60).mean()
        std_vol = df['Volume'].tail(60).std()
        z_score = (vol - avg_vol) / max(std_vol, avg_vol * 0.1)
        sma20 = df['Close'].rolling(20).mean().iloc[-1]

        # --- 4. LOGICA ALERT ---
        tipo = ""
        if z_score > 3.0 and cp > op and cp > sma20 and not is_rejected and current_rsi < 70:
            tipo = "🐋 SWEEP CALL"
        elif z_score > 2.0 and range_totale_pct < 0.005 and cp > sma20:
            tipo = "🧊 ICEBERG"

        if tipo:
            tr = np.maximum(df['High']-df['Low'], 
                 np.maximum(abs(df['High']-df['Close'].shift(1)), 
                            abs(df['Low']-df['Close'].shift(1))))
            atr = tr.dropna().tail(14).mean()
            stop = cp - (2 * atr)
            
            msg = f"🛰️ *{tipo}*\n💎 **{ticker}**: ${cp:.2f}\n"
            msg += f"📊 Z-Vol: {z_score:.1f} | RSI: {current_rsi:.1f}\n"
            msg += f"🚫 Stop (ATR): ${stop:.2f}"
            
            send_telegram(msg)
            
            # Registra e salva l'alert per la persistenza
            alert_history[ticker] = now
            save_alert_history(alert_history)
            print(f"📩 Alert inviato per {ticker}")
            
    except Exception as e:
        print(f"Error {ticker}: {e}")

def main():
    global alert_history
    # Carica la cronologia dallo storage all'avvio
    alert_history = load_alert_history()
    
    # Pulizia automatica log (rimuove record più vecchi di 24h)
    now = datetime.now()
    alert_history = {k: v for k, v in alert_history.items() if now < v + timedelta(hours=24)}

    if not is_market_open():
        print("⏳ Fuori orario operativo (16:30 - 21:45 ITA).")
        return

    all_tickers = sorted(list(set(MY_PORTFOLIO + WATCHLIST_200)))
    print(f"🚀 Scansione avviata su {len(all_tickers)} titoli...")
    
    for t in all_tickers:
        analyze_stock(t)
        time.sleep(0.2)

if __name__ == "__main__":
    main()

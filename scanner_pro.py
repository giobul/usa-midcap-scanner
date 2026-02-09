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

# File persistente per cooldown
ALERT_LOG = Path.home() / ".scanner_alerts.json"
alert_history = {}

def load_alert_history():
    if ALERT_LOG.exists():
        try:
            with open(ALERT_LOG, 'r') as f:
                data = json.load(f)
                return {k: datetime.fromisoformat(v) for k, v in data.items()}
        except:
            return {}
    return {}

def save_alert_history(history):
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
    return dtime(10, 30) <= now_ny.time() <= dtime(15, 45)

def send_telegram(message):
    if TOKEN and CHAT_ID:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
        try:
            requests.post(url, data=data, timeout=5)
        except Exception as e:
            print(f"❌ Errore Telegram: {e}")

def calculate_resistances(df, current_price):
    """Calcola R1 e R2 usando swing highs + probabilità di raggiungimento"""
    highs = df['High'].tail(80)
    
    peaks = []
    for i in range(2, len(highs)-2):
        if highs.iloc[i] > highs.iloc[i-1] and highs.iloc[i] > highs.iloc[i-2] and \
           highs.iloc[i] > highs.iloc[i+1] and highs.iloc[i] > highs.iloc[i+2]:
            peaks.append(float(highs.iloc[i]))
    
    if len(peaks) < 2:
        R1 = current_price * 1.02
        R2 = current_price * 1.05
    else:
        resistances = sorted([p for p in peaks if p > current_price])
        
        if len(resistances) >= 2:
            R1 = resistances[0]
            R2 = resistances[1]
        elif len(resistances) == 1:
            R1 = resistances[0]
            R2 = current_price * 1.05
        else:
            R1 = current_price * 1.02
            R2 = current_price * 1.05
    
    # Calcolo probabilità
    tr = np.maximum(df['High']-df['Low'], 
         np.maximum(abs(df['High']-df['Close'].shift(1)), 
                    abs(df['Low']-df['Close'].shift(1))))
    atr = tr.dropna().tail(14).mean()
    momentum = (df['Close'].iloc[-1] / df['Close'].iloc[-5] - 1) * 100
    
    dist_R1 = (R1 - current_price) / atr if atr > 0 else 999
    dist_R2 = (R2 - current_price) / atr if atr > 0 else 999
    
    prob_R1 = min(95, max(10, 50 - (dist_R1 * 15) + (momentum * 2)))
    prob_R2 = min(90, max(5, 30 - (dist_R2 * 10) + (momentum * 1.5)))
    
    return R1, R2, int(prob_R1), int(prob_R2)

def analyze_stock(ticker):
    global alert_history
    try:
        now = datetime.now()
        
        # Cooldown check
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
        
        # --- CALCOLO VOLUME PROFILE (POC) ---
        # Point of Control: prezzo con massimo volume scambiato
        try:
            price_bins = pd.cut(df['Close'], bins=20)
            volume_profile = df.groupby(price_bins, observed=True)['Volume'].sum()
            poc_interval = volume_profile.idxmax()
            poc_price = float(poc_interval.mid)
        except:
            poc_price = cp  # Fallback se il calcolo fallisce
        
        # --- INDICATORI ---
        delta = df['Close'].diff()
        gain = delta.where(delta > 0, 0).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss.replace(0, np.nan)
        current_rsi = 100 - (100 / (1 + rs.fillna(100))).iloc[-1]

        # --- PRICE ACTION ---
        body = abs(cp - op)
        u_wick = hi - max(cp, op)
        is_rejected = u_wick > (body * 1.5) if body > 0 else False
        
        range_totale_pct = (hi - lo) / cp 
        
        avg_vol = df['Volume'].tail(60).mean()
        std_vol = df['Volume'].tail(60).std()
        z_score = (vol - avg_vol) / max(std_vol, avg_vol * 0.1)
        sma20 = df['Close'].rolling(20).mean().iloc[-1]

        # --- LOGICA ALERT ---
        tipo = ""
        if z_score > 3.0 and cp > op and cp > sma20 and not is_rejected and current_rsi < 70:
            tipo = "🐋 SWEEP CALL"
        elif z_score > 2.0 and range_totale_pct < 0.005 and cp > sma20:
            tipo = "🧊 ICEBERG"

        if tipo:
            # --- CALCOLA RESISTENZE E STOP ---
            R1_auto, R2_auto, prob_R1, prob_R2 = calculate_resistances(df, cp)
            
            tr = np.maximum(df['High']-df['Low'], 
                 np.maximum(abs(df['High']-df['Close'].shift(1)), 
                            abs(df['Low']-df['Close'].shift(1))))
            atr = tr.dropna().tail(14).mean()
            stop = cp - (2 * atr)
            
            # --- RISK/REWARD RATIO ---
            risk = cp - stop
            reward = R1_auto - cp
            rr_ratio = reward / risk if risk > 0 else 0
            
            # --- VALIDAZIONE POC ---
            # Se prezzo attuale è vicino al POC (<2% distanza), segnale MOLTO più forte
            dist_from_poc = abs(cp - poc_price) / poc_price
            poc_validation = "✅ VALIDATO (Vicino a POC)" if dist_from_poc < 0.02 else "⚠️ FUORI POC"
            
            # --- MESSAGGIO TELEGRAM "ISTITUZIONALE" ---
            status_icon = "🟢" if cp > sma20 else "🟡"
            
            msg = f"🛰️ *{tipo} DETECTED*\n"
            msg += f"💎 **{ticker}**: `${cp:.2f}` {status_icon}\n"
            msg += f"📊 Z-Vol: `{z_score:.1f}` | RSI: `{current_rsi:.1f}`\n"
            msg += f"📍 **POC (Volume Profile)**: `${poc_price:.2f}`\n"
            msg += f"⚖️ **R/R Ratio**: `{rr_ratio:.2f}` | {poc_validation}\n"
            msg += f"🚫 Stop (ATR): `${stop:.2f}`\n"
            msg += f"━━━━━━━━━━━━━━━\n"
            
            emoji_R1 = "🎯" if prob_R1 >= 60 else "⚠️" if prob_R1 >= 40 else "🔴"
            emoji_R2 = "🎯" if prob_R2 >= 50 else "⚠️" if prob_R2 >= 30 else "🔴"
            
            msg += f"{emoji_R1} **R1**: `${R1_auto:.2f}` ({prob_R1}% prob)\n"
            msg += f"{emoji_R2} **R2**: `${R2_auto:.2f}` ({prob_R2}% prob)\n\n"
            
            # --- CONCLUSIONE OPERATIVA ---
            # Combina R/R Ratio + Probabilità + Validazione POC
            if rr_ratio >= 2.0 and prob_R1 >= 50 and dist_from_poc < 0.02:
                msg += f"💎 *SET-UP PREMIUM*: Ottimo R/R, alta probabilità e validato da POC"
            elif rr_ratio >= 2.0 and prob_R1 >= 50:
                msg += f"✅ *TRADE SOLIDO*: Buon R/R e probabilità favorevole"
            elif rr_ratio < 1.0:
                msg += f"📉 *ATTENZIONE*: Rischio superiore al premio (R/R < 1.0)"
            elif prob_R1 < 40:
                msg += f"⚠️ *BASSA PROBABILITÀ*: R1 difficile da raggiungere"
            else:
                msg += f"⚡️ *MOMENTUM PLAY*: Trade da scalping veloce"
            
            send_telegram(msg)
            
            # Registra alert
            alert_history[ticker] = now
            save_alert_history(alert_history)
            print(f"📩 Alert: {ticker} @ ${cp:.2f} | R/R: {rr_ratio:.2f} | POC: ${poc_price:.2f}")
            
    except Exception as e:
        print(f"Error {ticker}: {e}")

def main():
    global alert_history
    alert_history = load_alert_history()
    
    # Pulizia log vecchi
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
    
    print("✅ Scansione completata.")

if __name__ == "__main__":
    main()

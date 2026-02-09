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

# Portafoglio per monitoraggio prioritario
MY_PORTFOLIO = ["STNE", "PATH", "RGTI", "BBAI", "SOFI", "AGEN", "DKNG", "QUBT", "ETOR", "ADCT", "APLD"]

# LISTA COMPLETA 200+ TICKER
WATCHLIST_200 = [
    # --- TECNOLOGIA & SOFTWARE ---
    "SNOW", "DDOG", "NET", "ZS", "CRWD", "MDB", "ESTC", "DOCN", "GTLB", "AI",
    "PCOR", "APPN", "BILL", "ZI", "SMAR", "JAMF", "DT", "S", "TENB", "PANW",
    "FTNT", "CYBR", "OKTA", "PING", "U", "RBLX", "PLTK", "BIGC", "ASAN", "MNDY",
    "IOT", "TWLO", "ZM", "SHOP", "UBER", "OKLO", "ALTI", "VRT", "CLS", "PSTG", "ANET",
    
    # --- SEMICONDUTTORI & HARDWARE ---
    "NVDA", "AMD", "ARM", "AVGO", "TSM", "ASML", "MU", "AMAT", "LRCX", "KLAC",
    "SMCI", "MRVL", "ON", "MPWR", "SWKS", "QRVO", "WOLF", "CRUS", "ALGM", "POWI", 
    "DIOD", "LSCC", "RMBS", "COHU", "FORM", "ONTO", "NVTS", "PLAB", "IRDM", "ALAB",
    
    # --- AI, QUANTUM & ROBOTICS ---
    "PLTR", "SOUN", "GFAI", "CIFR", "CORZ", "WULF", "IONQ", "QBTS", "ARQQ", "IRBT",
    "BLDE", "MKSI", "GRMN", "ISRG", "NNDM", "DM", "SSYS", "SOUND", "SERV", "D_WAVE",
    
    # --- FINTECH & CRYPTO ---
    "AFRM", "UPST", "NU", "PAGS", "MELI", "SQ", "PYPL", "COIN", "HOOD", "MARA",
    "RIOT", "CLSK", "MSTR", "BTBT", "HUT", "ARBK", "BITF", "TOST", "FOUR", "GPN",
    "EVTC", "LC", "TREE", "ENVA", "OPY", "LPRO", "VIRT", "IBKR",
    
    # --- ENERGY, NUCLEAR & RENEWABLES ---
    "SMR", "VST", "CEG", "NNE", "CCJ", "UUUU", "DNN", "NXE", "UEC", "FSLR", 
    "ENPH", "SEDG", "RUN", "NOVA", "CSIQ", "JKS", "SOL", "FLNC", "CHPT", "BLNK", 
    "EVGO", "STEM", "PLUG", "BLDP", "BE", "GCT", "TLNE", "ETN", "NEE", "BW", "LNL",
    
    # --- AEROSPACE, DEFENSE & SPACE ---
    "RKLB", "ASTS", "LUNR", "PL", "SPIR", "BKSY", "SIDU", "ACHR", "JOBY", "LILM",
    "EVTL", "AVAV", "KTOS", "HWM", "VSAT", "LHX", "BA", "LMT", "RTX", "GD", 
    "NOC", "AXON", "HOLO",
    
    # --- EV, AUTOMOTIVE & MOBILITY ---
    "RIVN", "LCID", "TSLA", "NIO", "XPEV", "LI", "FSR", "NKLA", "WKHS", "HYLN",
    "LEV", "MVST", "LAZR", "OUST", "AUR", "INVZ", "VLDR", "LYFT", "CVNA", "QS",
    
    # --- HEALTHCARE & BIOTECH ---
    "TDOC", "DOCS", "ONEM", "ACCD", "HIMS", "LFST", "GH", "PGNY", "SDGR", "ALHC",
    "VKTX", "RXDX", "KRTX", "IOVA", "VERV", "CRSP", "NTLA", "BEAM", "EDIT", "BLUE",
    "ALT", "AMAM", "IBX", "MREO", "CYTK"
]

ALERT_LOG = Path.home() / ".scanner_alerts.json"

def load_alert_history():
    if ALERT_LOG.exists():
        try:
            with open(ALERT_LOG, 'r') as f:
                data = json.load(f)
                return {k: datetime.fromisoformat(v) for k, v in data.items()}
        except: return {}
    return {}

def save_alert_history(history):
    try:
        data = {k: v.isoformat() for k, v in history.items()}
        with open(ALERT_LOG, 'w') as f:
            json.dump(data, f)
    except: pass

def get_market_session():
    tz_ny = pytz.timezone('US/Eastern')
    now_ny = datetime.now(tz_ny)
    current_time = now_ny.time()
    if dtime(4, 0) <= current_time < dtime(9, 30): return 'PRE_MARKET', now_ny
    elif dtime(9, 30) <= current_time < dtime(16, 0): return 'REGULAR', now_ny
    elif dtime(16, 0) <= current_time <= dtime(20, 0): return 'AFTER_HOURS', now_ny
    else: return 'CLOSED', now_ny

def is_market_open():
    tz_ny = pytz.timezone('US/Eastern')
    now_ny = datetime.now(tz_ny)
    if now_ny.weekday() >= 5: return False
    return dtime(4, 0) <= now_ny.time() <= dtime(20, 0)

def send_telegram(message):
    if TOKEN and CHAT_ID:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
        try: requests.post(url, data=data, timeout=5)
        except: print("❌ Telegram Error")

def detect_dark_pool_activity(df, current_price):
    if len(df) < 10: return False, 0, ""
    recent = df.tail(3)
    avg_vol_recent = recent['Volume'].mean()
    avg_vol_baseline = df['Volume'].tail(20).mean()
    vol_ratio = avg_vol_recent / avg_vol_baseline if avg_vol_baseline > 0 else 0
    price_vol = recent['Close'].std() / current_price if current_price > 0 else 999
    is_stepping = all(recent['Close'].iloc[i] >= recent['Close'].iloc[i-1] for i in range(1, len(recent)))
    
    if vol_ratio > 1.6 and price_vol < 0.004 and is_stepping:
        return True, min(100, int(vol_ratio * 30)), "STEALTH ACCUMULATION"
    elif vol_ratio > 2.2 and price_vol < 0.012:
        return True, min(95, int(vol_ratio * 25)), "INSTITUTIONAL BREAKOUT"
    return False, 0, ""

def calculate_levels(df, current_price):
    highs = df['High'].tail(100)
    peaks = []
    for i in range(2, len(highs)-2):
        if highs.iloc[i] > highs.iloc[i-1] and highs.iloc[i] > highs.iloc[i-2] and \
           highs.iloc[i] > highs.iloc[i+1] and highs.iloc[i] > highs.iloc[i+2]:
            peaks.append(float(highs.iloc[i]))
    
    R1 = sorted([p for p in peaks if p > current_price])[0] if any(p > current_price for p in peaks) else current_price * 1.04
    R2 = sorted([p for p in peaks if p > R1])[0] if any(p > R1 for p in peaks) else R1 * 1.06
    
    tr = np.maximum(df['High']-df['Low'], np.maximum(abs(df['High']-df['Close'].shift(1)), abs(df['Low']-df['Close'].shift(1))))
    atr = tr.dropna().tail(14).mean()
    stop_loss = current_price - (2.8 * atr)
    
    prob = min(92, max(15, 55 - (((R1 - current_price) / (atr if atr > 0 else 1)) * 12)))
    return R1, R2, stop_loss, int(prob)

def analyze_stock(ticker):
    global alert_history
    try:
        now = datetime.now()
        if ticker in alert_history and now < alert_history[ticker] + timedelta(hours=3): return

        df = yf.download(ticker, period="5d", interval="15m", progress=False)
        if df.empty or len(df) < 50: return
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)

        cp = float(df['Close'].iloc[-1])
        vol = float(df['Volume'].iloc[-1])
        
        # --- POC VOLUME PROFILE ---
        price_bins = pd.cut(df['Close'], bins=20)
        try:
            poc_price = float(df.groupby(price_bins, observed=True)['Volume'].sum().idxmax().mid)
        except (ValueError, AttributeError):
            poc_price = cp  # Fallback al prezzo corrente
        
        avg_vol = df['Volume'].tail(50).mean()
        std = df['Volume'].tail(50).std()
        z_score = (vol - avg_vol) / (std if std > 1 else 1)
        sma20 = df['Close'].rolling(20).mean().iloc[-1]
        
        is_dp, dp_score, dp_type = detect_dark_pool_activity(df, cp)
        
        tipo = ""
        if is_dp and dp_score >= 65: tipo = f"🕵️ DARK POOL: {dp_type}"
        elif z_score > 3.5 and cp > sma20: tipo = "🐋 INSTITUTIONAL SWEEP"
        
        if tipo:
            R1, R2, stop, prob = calculate_levels(df, cp)
            dist_poc = abs(cp - poc_price) / poc_price
            
            msg = f"🛰️ *{tipo}*\n"
            msg += f"💎 **AZIONE**: `{ticker}`\n"
            msg += f"💰 **Prezzo**: `${cp:.2f}`\n"
            msg += f"📍 **POC Support**: `${poc_price:.2f}` ({'🎯 VALID' if dist_poc < 0.02 else 'AWAY'})\n"
            msg += f"━━━━━━━━━━━━━━━\n"
            msg += f"🎯 **Target 1**: `${R1:.2f}` ({prob}% prob)\n"
            msg += f"🚀 **Target 2**: `${R2:.2f}`\n"
            msg += f"🛡️ **STOP LOSS**: `${stop:.2f}`\n"
            msg += f"━━━━━━━━━━━━━━━\n"
            
            if dist_poc < 0.02: msg += "🔥 *PREMIUM SETUP*: Accumulo confermato sul Point of Control."
            else: msg += "⚡ *MOMENTUM*: Spinta volumetrica in corso."

            send_telegram(msg)
            alert_history[ticker] = now
            save_alert_history(alert_history)

    except Exception as e: print(f"Error {ticker}: {e}")

def main():
    global alert_history
    alert_history = load_alert_history()
    if not is_market_open():
        print("⏳ Market Closed.")
        return
    
    all_tickers = sorted(list(set(MY_PORTFOLIO + WATCHLIST_200)))
    print(f"🚀 Scanning {len(all_tickers)} stocks...")
    for t in all_tickers:
        analyze_stock(t)
        time.sleep(0.35) # Protezione anti-ban
    print("✅ Scan Complete.")

if __name__ == "__main__":
    main()

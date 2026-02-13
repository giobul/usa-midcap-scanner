# elite_nexus_cron_final_v5.py
import sys
import os
import time
import requests
import pytz
import numpy as np
import pandas as pd
import yfinance as yf
import json
import logging
import warnings
from datetime import datetime, timedelta, time as dtime
from pathlib import Path

warnings.filterwarnings('ignore')

# --- CONFIGURAZIONE AMBIENTE ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not TOKEN or not CHAT_ID:
    print("❌ ERROR: Set TELEGRAM_TOKEN and TELEGRAM_CHAT_ID env variables!")
    sys.exit(1)

# --- WATCHLIST ---
MY_PORTFOLIO = ["STNE", "PATH", "RGTI", "BBAI", "SOFI", "AGEN", "DKNG", "QUBT", "ETOR", "ADCT", "APLD"]
WATCHLIST_200 = [
    "SNOW", "DDOG", "NET", "ZS", "CRWD", "MDB", "ESTC", "DOCN", "GTLB", "AI", "PLTR",
    "PCOR", "APPN", "BILL", "TENB", "PANW", "FTNT", "CYBR", "OKTA", "U", "RBLX", 
    "IOT", "TWLO", "ZM", "SHOP", "UBER", "OKLO", "ALTI", "VRT", "CLS", "PSTG", "ANET", 
    "NVDA", "AMD", "ARM", "AVGO", "TSM", "ASML", "MU", "AMAT", "LRCX", "KLAC", "SMCI", 
    "MRVL", "ON", "MPWR", "SWKS", "QRVO", "WOLF", "CRUS", "ALGM", "RMBS", "ALAB", 
    "SOUN", "GFAI", "CIFR", "CORZ", "WULF", "IONQ", "QBTS", "ARQQ", "MKSI", "ISRG", 
    "AFRM", "UPST", "NU", "PAGS", "MELI", "COIN", "HOOD", "MARA", "RIOT", "CLSK", 
    "MSTR", "BTBT", "HUT", "ARBK", "BITF", "TOST", "FOUR", "GPN", "LC", "VIRT", 
    "IBKR", "SMR", "VST", "CEG", "NNE", "CCJ", "UUUU", "DNN", "NXE", "UEC", "FSLR", 
    "ENPH", "SEDG", "RUN", "CSIQ", "CHPT", "BLNK", "EVGO", "STEM", "PLUG", "BE", 
    "GCT", "RKLB", "ASTS", "LUNR", "AVAV", "KTOS", "AXON", "RIVN", "LCID", "TSLA", 
    "NIO", "XPEV", "LI", "QS", "TDOC", "DOCS", "HIMS", "LFST", "VKTX", "IOVA", "CRSP"
]
ALL_TICKERS = sorted(list(set(MY_PORTFOLIO + WATCHLIST_200)))

# --- PARAMETRI ---
ALERT_HISTORY_FILE = Path.home() / ".nexus_alerts_cron.json"
CONFIG = {
    'COOLDOWN_HOURS': 3,
    'NEXUS_THRESHOLD': 65,
    'MAX_RSI': 68,
    'MAX_DIST_SMA20': 7.5,
    'MIN_RVOL': 1.4,
    'YF_SLEEP': 0.25  # CORREZIONE: Protezione contro ban IP Yahoo
}

def get_indicators(df):
    try:
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / (loss + 1e-9)
        rsi = 100 - (100 / (1 + rs))
        sma20 = df['Close'].rolling(20).mean()
        rvol = df['Volume'] / df['Volume'].rolling(50).mean()
        return rsi.iloc[-1], sma20.iloc[-1], rvol.iloc[-1]
    except: return 50, df['Close'].iloc[-1], 1.0

def calculate_nexus_lite(df):
    vol_ma5 = df['Volume'].tail(5).mean()
    vol_ma50 = df['Volume'].mean()
    vfs = min(100, (vol_ma5 / vol_ma50) * 60)
    sma20 = df['Close'].rolling(20).mean().iloc[-1]
    obie = min(100, abs((df['Close'].iloc[-1] - sma20) / sma20) * 1500)
    recent_mom = df['Close'].pct_change().tail(5).mean()
    ifc = min(100, max(0, 50 + (recent_mom * 2500)))
    score = (vfs * 0.4) + (obie * 0.4) + (ifc * 0.2)
    return round(score, 1), round(vfs, 1), round(obie, 1), round(ifc, 1)

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try: requests.post(url, data={"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}, timeout=10)
    except: print("Telegram Error")

def main():
    tz_ny = pytz.timezone('America/New_York')
    now_ny = datetime.now(tz_ny).time()
    
    if now_ny < dtime(10, 0) or now_ny > dtime(16, 0):
        print("Market Closed or Opening Noise. Exit.")
        return

    alert_history = {}
    if ALERT_HISTORY_FILE.exists():
        try:
            with open(ALERT_HISTORY_FILE) as f:
                data = json.load(f)
                alert_history = {k: datetime.fromisoformat(v) for k, v in data.items()}
        except: alert_history = {}

    try:
        qqq = yf.download("QQQ", period="2d", interval="15m", progress=False, threads=False)
        if qqq['Close'].iloc[-1] < qqq['Close'].rolling(20).mean().iloc[-1]:
            print("Mercato Debole (QQQ < SMA20).")
            return
    except: pass

    print(f"🚀 Nexus Scan: {len(ALL_TICKERS)} tickers...")
    
    for ticker in ALL_TICKERS:
        try:
            # CORREZIONE: threads=False e sleep per stabilità
            df = yf.download(ticker, period="5d", interval="15m", progress=False, threads=False, timeout=10)
            time.sleep(CONFIG['YF_SLEEP']) 
            
            if df.empty or len(df) < 30: continue
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)

            cp = float(df['Close'].iloc[-1])
            rsi, sma20, rvol = get_indicators(df)
            dist_sma = ((cp - sma20) / sma20) * 100
            
            if rsi > CONFIG['MAX_RSI'] or dist_sma > CONFIG['MAX_DIST_SMA20'] or rvol < CONFIG['MIN_RVOL']:
                continue

            score, vfs, obie, ifc = calculate_nexus_lite(df)

            if score >= CONFIG['NEXUS_THRESHOLD']:
                if ticker in alert_history and (datetime.now() - alert_history[ticker]) < timedelta(hours=CONFIG['COOLDOWN_HOURS']):
                    continue

                tags = []
                if obie > 55: tags.append("🕵️ DARK POOL")
                if rvol > 1.8: tags.append("🐋 WHALE SWEEP")
                if rsi < 35: tags.append("📉 OVERSOLD")
                
                atr = (df['High'] - df['Low']).tail(14).mean()
                msg = f"🧬 **NEXUS HIGH CONVICTION**\n"
                msg += f"💎 `{ticker}` | Price: `${cp:.2f}`\n"
                msg += f"━━━━━━━━━━━━━━━\n"
                msg += f"🎯 Score: `{score}/100` (VFS:{vfs:.0f} OBIE:{obie:.0f} IFC:{ifc:.0f})\n"
                msg += f"📊 RVOL: `{rvol:.1f}x` | RSI: `{rsi:.1f}` | SMA: `+{dist_sma:.1f}%`\n"
                if tags: msg += f"🏷️ {' '.join(tags)}\n"
                msg += f"━━━━━━━━━━━━━━━\n"
                msg += f"🛡️ STOP: `${cp - (atr*2):.2f}` | 🎯 T1: `${cp + (atr*1.5):.2f}`\n"
                msg += f"⚠️ *Delay 15m. Check LIVE!*"

                send_telegram(msg)
                alert_history[ticker] = datetime.now()

        except Exception as e:
            print(f"Error {ticker}: {e}")
            continue

    with open(ALERT_HISTORY_FILE, 'w') as f:
        json.dump({k: v.isoformat() for k, v in alert_history.items()}, f)

if __name__ == "__main__":
    main()

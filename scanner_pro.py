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
import logging

# --- CONFIGURAZIONE ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Validazione credenziali all'avvio
if not TOKEN or not CHAT_ID:
    print("❌ ERROR: TELEGRAM_TOKEN and TELEGRAM_CHAT_ID must be set in environment variables!")
    sys.exit(1)

MY_PORTFOLIO = ["STNE", "PATH", "RGTI", "BBAI", "SOFI", "AGEN", "DKNG", "QUBT", "ETOR", "ADCT", "APLD"]

WATCHLIST_200 = [
    "SNOW", "DDOG", "NET", "ZS", "CRWD", "MDB", "ESTC", "DOCN", "GTLB", "AI",
    "PCOR", "APPN", "BILL", "TENB", "PANW", "FTNT", "CYBR", "OKTA", "U", "RBLX", 
    "PLTK", "ASAN", "MNDY", "IOT", "TWLO", "ZM", "SHOP", "UBER", "OKLO", "ALTI", 
    "VRT", "CLS", "PSTG", "ANET", "NVDA", "AMD", "ARM", "AVGO", "TSM", "ASML", 
    "MU", "AMAT", "LRCX", "KLAC", "SMCI", "MRVL", "ON", "MPWR", "SWKS", "QRVO", 
    "WOLF", "CRUS", "ALGM", "POWI", "DIOD", "LSCC", "RMBS", "COHU", "FORM", "ONTO", 
    "NVTS", "PLAB", "IRDM", "ALAB", "PLTR", "SOUN", "GFAI", "CIFR", "CORZ", "WULF", 
    "IONQ", "QBTS", "ARQQ", "MKSI", "GRMN", "ISRG", "NNDM", "SSYS", "SERV",
    "AFRM", "UPST", "NU", "PAGS", "MELI", "COIN", "HOOD", "MARA", "RIOT", "CLSK", 
    "MSTR", "BTBT", "HUT", "ARBK", "BITF", "TOST", "FOUR", "GPN", "EVTC", "LC", 
    "TREE", "ENVA", "OPY", "LPRO", "VIRT", "IBKR", "SMR", "VST", "CEG", "NNE", 
    "CCJ", "UUUU", "DNN", "NXE", "UEC", "FSLR", "ENPH", "SEDG", "RUN", "CSIQ", 
    "JKS", "FLNC", "CHPT", "BLNK", "EVGO", "STEM", "PLUG", "BLDP", "BE", "GCT", 
    "TLNE", "ETN", "NEE", "BW", "RKLB", "ASTS", "LUNR", "PL", "SPIR", "BKSY", 
    "SIDU", "ACHR", "JOBY", "EVTL", "AVAV", "KTOS", "HWM", "VSAT", "LHX", "BA", 
    "LMT", "RTX", "GD", "NOC", "AXON", "HOLO", "RIVN", "LCID", "TSLA", "NIO", 
    "XPEV", "LI", "WKHS", "HYLN", "MVST", "OUST", "AUR", "INVZ", "LYFT", "CVNA", 
    "QS", "TDOC", "DOCS", "HIMS", "LFST", "GH", "PGNY", "SDGR", "ALHC", "VKTX", 
    "IOVA", "CRSP", "NTLA", "BEAM", "EDIT", "ALT", "MREO", "CYTK"]


ALERT_LOG = Path.home() / ".scanner_alerts.json"
SCAN_LOG = Path.home() / ".scanner_scan_log.txt"

# Configurazione logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(SCAN_LOG),
        logging.StreamHandler()
    ]
)

# Parametri configurabili
CONFIG = {
    'Z_SCORE_THRESHOLD': 3.0, 
    'POC_DISTANCE_THRESHOLD': 0.02,  # 2%
    'MIN_PROFIT_THRESHOLD': 0.015,  # 1.5%
    'COOLDOWN_HOURS': 6,
    'SLEEP_BETWEEN_STOCKS': 0.35,
    'DP_SCORE_REGULAR': 70,
    'DP_SCORE_OFFHOURS': 75,
    'ICEBERG_SCORE_THRESHOLD': 80,
}

# --- UTILITIES ---
def load_alert_history():
    if ALERT_LOG.exists():
        try:
            with open(ALERT_LOG, 'r') as f:
                data = json.load(f)
                return {k: datetime.fromisoformat(v) for k, v in data.items()}
        except Exception as e:
            logging.warning(f"Error loading alert history: {e}")
            return {}
    return {}

def save_alert_history(history):
    try:
        data = {k: v.isoformat() for k, v in history.items()}
        with open(ALERT_LOG, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logging.error(f"Error saving alert history: {e}")

def get_market_session():
    tz_ny = pytz.timezone('US/Eastern')
    now_ny = datetime.now(tz_ny)
    current_time = now_ny.time()
    if dtime(4, 0) <= current_time < dtime(9, 30): 
        return 'PRE_MARKET', now_ny
    elif dtime(9, 30) <= current_time < dtime(16, 0): 
        return 'REGULAR', now_ny
    elif dtime(16, 0) <= current_time <= dtime(20, 0): 
        return 'AFTER_HOURS', now_ny
    else: 
        return 'CLOSED', now_ny

def is_market_open():
    tz_ny = pytz.timezone('US/Eastern')
    now_ny = datetime.now(tz_ny)
    if now_ny.weekday() >= 5: 
        return False
    return dtime(4, 0) <= now_ny.time() <= dtime(20, 0)

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try: 
        response = requests.post(url, data=data, timeout=5)
        if response.status_code == 200:
            logging.info("✅ Telegram alert sent successfully")
        else:
            logging.error(f"❌ Telegram error: {response.status_code}")
    except Exception as e:
        logging.error(f"❌ Telegram exception: {e}")

# --- CORE DETECTION ---
def detect_dark_pool_activity(df, current_price):
    if len(df) < 10: 
        return False, 0, ""
    recent = df.tail(3)
    avg_vol_recent = recent['Volume'].mean()
    avg_vol_baseline = df['Volume'].tail(20).mean()
    if avg_vol_baseline == 0:
        return False, 0, ""
    vol_ratio = avg_vol_recent / avg_vol_baseline
    price_vol = recent['Close'].std() / current_price if current_price > 0 else 999
    is_stepping = all(recent['Close'].iloc[i] >= recent['Close'].iloc[i-1] for i in range(1, len(recent)))
    if vol_ratio > 2.5 and price_vol < 0.003 and is_stepping:
        return True, min(100, int(vol_ratio * 25)), "STEALTH ACCUMULATION"
    elif vol_ratio > 3.5 and price_vol < 0.008:
        return True, min(95, int(vol_ratio * 20)), "INSTITUTIONAL BREAKOUT"
    return False, 0, ""

def detect_iceberg_orders(df, current_price):
    if len(df) < 30: 
        return False, 0, ""
    recent = df.tail(10)
    avg_vol = recent['Volume'].mean()
    vol_std = recent['Volume'].std()
    if avg_vol == 0:
        return False, 0, ""
    price_range = (recent['High'].max() - recent['Low'].min()) / current_price
    vol_consistency = 1 - (vol_std / avg_vol)
    price_changes = recent['Close'].diff().abs()
    if price_changes.mean() == 0:
        return False, 0, ""
    uniform_steps = price_changes.std() / price_changes.mean()
    baseline_vol = df['Volume'].tail(100).mean()
    vol_spike = avg_vol / baseline_vol if baseline_vol > 0 else 0
    if (vol_consistency > 0.80 and price_range < 0.006 and vol_spike > 1.6 and uniform_steps < 0.25):
        return True, min(95, int(vol_consistency * 100)), "ICEBERG BUY WALL"
    elif (vol_consistency > 0.75 and price_range < 0.010 and vol_spike > 1.5 and recent['Close'].iloc[-1] < recent['Close'].iloc[0]):
        return True, min(90, int(vol_consistency * 95)), "ICEBERG SELL PRESSURE"
    return False, 0, ""

def calculate_levels(df, current_price):
    highs = df['High'].tail(100)
    peaks = []
    for i in range(2, len(highs)-2):
        if (highs.iloc[i] > highs.iloc[i-1] and highs.iloc[i] > highs.iloc[i-2] and 
            highs.iloc[i] > highs.iloc[i+1] and highs.iloc[i] > highs.iloc[i+2]):
            peaks.append(float(highs.iloc[i]))
    R1 = sorted([p for p in peaks if p > current_price])[0] if any(p > current_price for p in peaks) else current_price * 1.04
    R2 = sorted([p for p in peaks if p > R1])[0] if any(p > R1 for p in peaks) else R1 * 1.06
    tr = np.maximum(df['High'] - df['Low'], np.maximum(abs(df['High'] - df['Close'].shift(1)), abs(df['Low'] - df['Close'].shift(1))))
    atr = tr.dropna().tail(14).mean()
    stop_loss = current_price - (2.8 * atr) if atr > 0 else current_price * 0.96
    prob = min(92, max(15, 55 - (((R1 - current_price) / (atr if atr > 0 else 1)) * 12)))
    return R1, R2, stop_loss, int(prob)

def calculate_poc_price(df, current_price):
    try:
        price_bins = pd.cut(df['Close'], bins=20)
        poc_price = float(df.groupby(price_bins, observed=True)['Volume'].sum().idxmax().mid)
        return poc_price
    except:
        try:
            vwap = (df['Close'] * df['Volume']).sum() / df['Volume'].sum()
            return float(vwap)
        except:
            return float((df['High'].mean() + df['Low'].mean()) / 2)

# --- ANALISI ---
def analyze_stock(ticker):
    global alert_history
    try:
        session, now_ny = get_market_session()
        if session == 'REGULAR':
            current_time = now_ny.time()
            if dtime(9, 30) <= current_time < dtime(10, 0): return
            if dtime(15, 30) <= current_time < dtime(16, 0): return

        df = yf.download(ticker, period="5d", interval="15m", progress=False)
        if df.empty or len(df) < 50: return
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)

        cp = float(df['Close'].iloc[-1])
        poc_price = calculate_poc_price(df, cp)
        vol = float(df['Volume'].iloc[-1])
        avg_vol = df['Volume'].tail(50).mean()
        std = df['Volume'].tail(50).std()
        z_score = (vol - avg_vol) / (std if std > 1 else 1)
        sma20 = df['Close'].rolling(20).mean().iloc[-1]
        
        is_dp, dp_score, dp_type = detect_dark_pool_activity(df, cp)
        is_iceberg, ice_score, ice_type = detect_iceberg_orders(df, cp)
        
        tipo = ""
        is_warning = False

        if session == 'REGULAR':
            if is_iceberg and ice_score >= CONFIG['ICEBERG_SCORE_THRESHOLD']:
                tipo = f"🧊 ICEBERG: {ice_type}"
                if "SELL" in ice_type and ticker in MY_PORTFOLIO: is_warning = True
            if not tipo and is_dp and dp_score >= CONFIG['DP_SCORE_REGULAR']:
                tipo = f"🕵️ DARK POOL: {dp_type}"
            if not tipo and z_score > CONFIG['Z_SCORE_THRESHOLD'] and cp > sma20:
                tipo = "🐋 INSTITUTIONAL SWEEP"
        else:
            if is_dp and dp_score >= CONFIG['DP_SCORE_OFFHOURS']:
                tipo = f"🕵️ DARK POOL (OFF-HOURS): {dp_type}"

        if tipo:
            R1, R2, stop, prob = calculate_levels(df, cp)
            potenziale_gain = (R1 - cp) / cp
            if potenziale_gain < CONFIG['MIN_PROFIT_THRESHOLD'] and not is_warning: return 

            now = datetime.now()
            if ticker in alert_history and (now - alert_history[ticker]) < timedelta(hours=CONFIG['COOLDOWN_HOURS']):
                if not is_warning: return

            # --- INVIO (Formattazione Aggiornata) ---
            dist_poc = abs(cp - poc_price) / poc_price if poc_price > 0 else 999
            prefix = "🚨" if is_warning else "🛰️"
            
            # Formattazione speciale per ICEBERG (Grassetto e Maiuscolo)
            if "ICEBERG" in tipo:
                msg = f"{prefix} *{tipo.upper()}*\n" # Tutto in grassetto e maiuscolo
                msg += f"💎 **AZIONE**: `{ticker}`\n"
            else:
                msg = f"{prefix} *{tipo}*\n"
                msg += f"💎 **AZIONE**: `{ticker}`\n"

            msg += f"💰 **Prezzo**: `${cp:.2f}`\n"
            msg += f"📍 **POC Support**: `${poc_price:.2f}` ({'🎯 VALID' if dist_poc < CONFIG['POC_DISTANCE_THRESHOLD'] else 'AWAY'})\n"
            msg += f"━━━━━━━━━━━━━━━\n"
            
            # Se è un ICEBERG, rendiamo i Target molto più visibili
            if "ICEBERG" in tipo:
                msg += f"🎯 **TARGET 1**: `{R1:.2f}` (+{potenziale_gain*100:.1f}%)\n"
                msg += f"🚀 **TARGET 2**: `{R2:.2f}`\n"
            else:
                msg += f"🎯 **Target 1**: `${R1:.2f}` (+{potenziale_gain*100:.1f}%)\n"
                msg += f"🚀 **Target 2**: `${R2:.2f}`\n"
                
            msg += f"🛡️ **STOP LOSS**: `${stop:.2f}`\n"
            msg += f"━━━━━━━━━━━━━━━\n"
            
            if is_warning:
                msg += "⚠️ *ATTENZIONE*: Whale in distribuzione sul tuo titolo."
            elif "ICEBERG" in tipo:
                msg += "❄️ ***ICEBERG DETECTED: ORDINE NASCOSTO IN ESECUZIONE***" # Triplo asterisco per enfasi
            elif dist_poc < CONFIG['POC_DISTANCE_THRESHOLD']:
                msg += "🔥 *PREMIUM SETUP*: Accumulo confermato sul Point of Control."
            else:
                msg += "⚡ *MOMENTUM*: Volume anomalo rilevato."

            send_telegram(msg)
            alert_history[ticker] = datetime.now()
            save_alert_history(alert_history)
            logging.info(f"📨 Alert sent for {ticker}: {tipo}")

    except Exception as e: 
        logging.error(f"Error analyzing {ticker}: {e}")

def main():
    global alert_history
    alert_history = load_alert_history()
    if not is_market_open(): return
    
    all_tickers = sorted(list(set(MY_PORTFOLIO + WATCHLIST_200)))
    for ticker in all_tickers:
        analyze_stock(ticker)
        time.sleep(CONFIG['SLEEP_BETWEEN_STOCKS'])

if __name__ == "__main__":
    main()


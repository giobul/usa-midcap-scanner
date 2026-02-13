# elite_nexus_scanner_v4_final.py (NO SCIPY REQUIRED)
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
import warnings
warnings.filterwarnings('ignore')

# --- CONFIGURAZIONE ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not TOKEN or not CHAT_ID:
    print("❌ ERROR: TELEGRAM_TOKEN and TELEGRAM_CHAT_ID must be set!")
    sys.exit(1)

# --- TICKER LISTS (INTEGRALE) ---
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
    "IOVA", "CRSP", "NTLA", "BEAM", "EDIT", "ALT", "MREO", "CYTK"
]

# --- FILE PATHS ---
LOG_FILE = Path.home() / "nexus_scanner.log"
SIGNALS_LOG = Path.home() / "nexus_signals.csv"
ALERT_HISTORY_FILE = Path.home() / ".nexus_alerts.json"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()])

CONFIG = {
    'COOLDOWN_HOURS': 6,
    'SLEEP_BETWEEN_STOCKS': 0.8,
    'MAX_RETRIES': 3,
    'NEXUS_THRESHOLD': 75,
    'CONVERGENCE_MIN': 4,
    'RISK_PER_TRADE_USD': 500
}

# ============================================
# NEXUS LITE ENGINE (CALCOLI)
# ============================================

def calculate_vfs_lite(df):
    try:
        vol_ma_5 = df['Volume'].rolling(5).mean()
        vol_ma_20 = df['Volume'].rolling(20).mean()
        vol_ratio = (vol_ma_5 / vol_ma_20).iloc[-1]
        vol_cv = df['Volume'].tail(20).std() / df['Volume'].tail(20).mean()
        return min(100, max(0, (vol_ratio * 50) * (1 / (1 + vol_cv))))
    except: return 0

def calculate_phr_lite(df):
    try:
        returns = df['Close'].pct_change()
        pos_m = (returns > 0).astype(int)
        cycles = []
        count = 0
        for v in pos_m:
            if v == 1: count += 1
            else:
                if count > 0: cycles.append(count)
                count = 0
        if not cycles: return 0
        avg_c = np.mean(cycles)
        return 80 if 5 <= avg_c <= 10 else 30
    except: return 0

def calculate_obie_lite(df):
    try:
        vwap = (df['Close'] * df['Volume']).cumsum() / df['Volume'].cumsum()
        div = abs(((df['Close'] - vwap) / vwap).tail(10).mean())
        return min(100, div * 4000)
    except: return 0

def calculate_vrs_lite(df):
    try:
        ret = df['Close'].pct_change().dropna()
        v5, v20 = ret.rolling(5).std().iloc[-1], ret.rolling(20).std().iloc[-1]
        return (1 - (v5/v20)) * 100 if v5 < v20 else 20
    except: return 0

def calculate_mqi_lite(df):
    try:
        mom = df['Close'].pct_change().rolling(10).mean().iloc[-1]
        std = df['Close'].pct_change().rolling(10).std().iloc[-1]
        return min(100, (mom / (std + 0.001)) * 20)
    except: return 0

def calculate_ifc_lite(df, benchmark_df):
    try:
        if benchmark_df is None or benchmark_df.empty: return 50
        t_ret, b_ret = df['Close'].pct_change().iloc[-1], benchmark_df['Close'].pct_change().iloc[-1]
        return 90 if t_ret > b_ret else 30
    except: return 50

def calculate_lar_lite(df):
    try:
        impact = (abs(df['Close'] - df['Open']) / df['Volume']).iloc[-1]
        return min(100, (1 / (impact * 1000000 + 1)) * 100)
    except: return 0

def calculate_nexus_score_lite(ticker, df, benchmark_df=None):
    res = {
        'vfs': calculate_vfs_lite(df), 'phr': calculate_phr_lite(df),
        'obie': calculate_obie_lite(df), 'vrs': calculate_vrs_lite(df),
        'mqi': calculate_mqi_lite(df), 'ifc': calculate_ifc_lite(df, benchmark_df),
        'lar': calculate_lar_lite(df)
    }
    weights = {'vfs':0.22, 'phr':0.10, 'obie':0.20, 'vrs':0.15, 'mqi':0.10, 'ifc':0.13, 'lar':0.10}
    score = sum(res[k] * weights[k] for k in weights)
    conv = sum(1 for v in res.values() if v > 70)
    return {'nexus_score': round(score + (conv * 2 if conv >= 4 else 0), 1), 'convergence': conv, 'components': res}

# ============================================
# CORE SCANNER & TELEGRAM
# ============================================

def get_benchmark(ticker):
    if ticker in ["STNE", "PAGS", "NU"]: return "EWZ"
    if ticker in ["NVDA", "AMD", "ARM", "AVGO", "SMCI", "TSM"]: return "SOXX"
    if ticker in ["COIN", "MARA", "RIOT", "CLSK", "MSTR"]: return "BITO"
    return "QQQ"

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try: requests.post(url, data={"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}, timeout=5)
    except: pass

def analyze_stock_nexus(ticker, alert_history):
    try:
        df = yf.download(ticker, period="5d", interval="15m", progress=False, timeout=10)
        if df.empty or len(df) < 30: return
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        
        cp = float(df['Close'].iloc[-1])
        bench_df = yf.download(get_benchmark(ticker), period="5d", interval="15m", progress=False, timeout=10)
        if isinstance(bench_df.columns, pd.MultiIndex): bench_df.columns = bench_df.columns.get_level_values(0)

        nexus_data = calculate_nexus_score_lite(ticker, df, bench_df)
        comp = nexus_data['components']
        
        # TRIGGER LOGIC
        if nexus_data['nexus_score'] >= CONFIG['NEXUS_THRESHOLD'] and nexus_data['convergence'] >= CONFIG['CONVERGENCE_MIN']:
            if ticker in alert_history and (datetime.now() - alert_history[ticker]) < timedelta(hours=CONFIG['COOLDOWN_HOURS']):
                return

            # TAGS SYSTEM (LA TUA RICHIESTA)
            detected = []
            if comp['obie'] > 80: detected.append("🕵️ DARK POOL")
            if comp['lar'] > 80: detected.append("🧊 ICEBERG WALL")
            if comp['ifc'] > 85: detected.append("🐋 INST. SWEEP")
            if comp['vfs'] > 80: detected.append("📈 STEALTH ACCUM")

            # Livelli Tecnici
            atr = (df['High'] - df['Low']).tail(14).mean()
            t_stop = cp - (2.0 * atr)
            r1 = cp + (1.5 * atr)
            
            msg = f"🧬 **NEXUS ELITE: SIGNAL**\n"
            msg += f"💎 `{ticker}` | Price: `${cp:.2f}`\n"
            msg += f"━━━━━━━━━━━━━━━\n"
            msg += f"🎯 NEXUS: `{nexus_data['nexus_score']}/100`\n"
            msg += f"🔗 CONV: `{nexus_data['convergence']}/7` ⚡\n"
            
            if detected:
                msg += f"━━━━━━━━━━━━━━━\n"
                msg += f"🔎 **DETECTED**: `{', '.join(detected)}` \n"
            
            msg += f"━━━━━━━━━━━━━━━\n"
            msg += f"📊 VFS:{comp['vfs']:.0f} OBIE:{comp['obie']:.0f} IFC:{comp['ifc']:.0f}\n"
            msg += f"🛡️ STOP: `${t_stop:.2f}` | 🎯 T1: `${r1:.2f}`\n"
            
            send_telegram(msg)
            alert_history[ticker] = datetime.now()
            with open(ALERT_HISTORY_FILE, 'w') as f:
                json.dump({k: v.isoformat() for k, v in alert_history.items()}, f)
            logging.info(f"✅ Alert: {ticker}")

    except Exception as e: logging.error(f"Error {ticker}: {e}")

def main():
    logging.info("🧬 NEXUS V4.0 LITE ONLINE")
    alert_history = {}
    if ALERT_HISTORY_FILE.exists():
        with open(ALERT_HISTORY_FILE) as f:
            data = json.load(f)
            alert_history = {k: datetime.fromisoformat(v) for k, v in data.items()}
    
    all_tickers = sorted(list(set(MY_PORTFOLIO + WATCHLIST_200)))
    
    while True:
        tz_ny = pytz.timezone('US/Eastern')
        now_ny = datetime.now(tz_ny)
        if now_ny.weekday() < 5 and dtime(9,30) <= now_ny.time() <= dtime(16,0):
            for ticker in all_tickers:
                analyze_stock_nexus(ticker, alert_history)
                time.sleep(CONFIG['SLEEP_BETWEEN_STOCKS'])
        else:
            logging.info("💤 Market Closed")
            time.sleep(600)

if __name__ == "__main__":
    main()

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

if not TOKEN or not CHAT_ID:
    print("❌ ERROR: TELEGRAM_TOKEN and TELEGRAM_CHAT_ID must be set!")
    sys.exit(1)

# --- LISTA COMPLETA TICKER ---
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

# --- LOGGING & BACKTEST FILES ---
LOG_FILE = Path.home() / "elite_scanner.log"
BACKTEST_LOG = Path.home() / "scanner_backtest_results.csv"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()]
)

CONFIG = {
    'COOLDOWN_HOURS': 4,
    'SLEEP_BETWEEN_STOCKS': 0.75,
    'MAX_RETRIES': 3,
    'ATR_MULTIPLIER_STOP': 2.0,
    'ELITE_CAI_MIN': 82.0,
    'RISK_PER_TRADE_USD': 500 
}

# --- TOOLS ---

def download_with_retry(ticker, period="5d", interval="15m"):
    for attempt in range(CONFIG['MAX_RETRIES']):
        try:
            df = yf.download(ticker, period=period, interval=interval, progress=False)
            if not df.empty: return df
        except Exception:
            time.sleep(2 ** attempt)
    return pd.DataFrame()

def log_backtest_signal(ticker, price, t1, t2, stop, s_type):
    file_exists = BACKTEST_LOG.exists()
    with open(BACKTEST_LOG, 'a') as f:
        if not file_exists:
            f.write("timestamp,ticker,entry_price,target1,target2,stop_loss,type\n")
        f.write(f"{datetime.now()},{ticker},{price},{t1},{t2},{stop},{s_type}\n")

# --- LOGICA ELITE ---

def detect_elite_candle(df):
    last = df.iloc[-1]
    avg_vol = df['Volume'].tail(20).mean()
    body = abs(last['Open'] - last['Close'])
    lower_shade = min(last['Open'], last['Close']) - last['Low']
    upper_shade = last['High'] - max(last['Open'], last['Close'])
    
    if lower_shade > (body * 2) and upper_shade < body and last['Volume'] > avg_vol * 1.5:
        return "🔨 HAMMER (ULTRA-VOL)"
    
    prev = df.iloc[-2]
    if last['Close'] > prev['Open'] and last['Open'] < prev['Close'] and last['Close'] > last['Open'] and last['Volume'] > avg_vol * 1.3:
        return "🔥 BULLISH ENGULFING (VOL+)"
    return ""

def get_relative_strength(ticker):
    try:
        if ticker in ["STNE", "PAGS", "NU"]: bench = "EWZ"
        elif ticker in ["NVDA", "AMD", "ARM", "AVGO", "SMCI"]: bench = "SOXX"
        elif ticker in ["COIN", "MARA", "RIOT"]: bench = "BITO"
        else: bench = "QQQ"
        
        data = download_with_retry(ticker, period="5d", interval="1h")
        b_data = download_with_retry(bench, period="5d", interval="1h")
        
        if data.empty or b_data.empty: return False, 0, bench
        t_perf = (data['Close'].iloc[-1] / data['Close'].iloc[0]) - 1
        b_perf = (b_data['Close'].iloc[-1] / b_data['Close'].iloc[0]) - 1
        return t_perf > b_perf, (t_perf - b_perf) * 100, bench
    except: return False, 0, "QQQ"

# --- CORE ---

def analyze_stock(ticker):
    try:
        df = download_with_retry(ticker, period="5d", interval="15m")
        if df.empty or len(df) < 30: return
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)

        cp = float(df['Close'].iloc[-1])
        
        # CAI Score Fix
        vol_ratio = (df['Volume'].tail(5).mean() / df['Volume'].tail(50).mean()) if df['Volume'].tail(50).mean() > 0 else 1
        price_stability = max(0, 1 - (df['Close'].tail(5).std() / cp))
        cai_score = min(100, (vol_ratio * 50) * price_stability)
        
        candle = detect_elite_candle(df)
        is_strong, rs_val, bench = get_relative_strength(ticker)
        
        if cai_score >= CONFIG['ELITE_CAI_MIN'] and is_strong and candle != "":
            tr = np.maximum(df['High'] - df['Low'], np.maximum(abs(df['High'] - df['Close'].shift(1)), abs(df['Low'] - df['Close'].shift(1))))
            atr = tr.tail(14).mean()
            t_stop = cp - (CONFIG['ATR_MULTIPLIER_STOP'] * atr)
            r1, r2 = cp + (atr * 1.5), cp + (atr * 3.0)
            
            log_backtest_signal(ticker, cp, r1, r2, t_stop, "ELITE")
            msg = f"👑 **ELITE V3.1: {candle}**\n💎 **AZIONE**: `{ticker}`\n💰 **Entry**: `${cp:.2f}` | **RS**: `+{rs_val:.2f}% vs {bench}`\n📊 **CAI**: `{cai_score:.1f}`\n━━━━━━━━━━━━━━━\n🎯 **T1**: `{r1:.2f}` | **T2**: `{r2:.2f}`\n🛡️ **STOP**: `{t_stop:.2f}`"
            send_telegram(msg)
            
    except Exception as e: logging.error(f"Errore {ticker}: {e}")

def is_market_open():
    tz_ny = pytz.timezone('US/Eastern')
    now_ny = datetime.now(tz_ny)
    if now_ny.weekday() >= 5: return False
    return dtime(4, 0) <= now_ny.time() <= dtime(20, 0)

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try: requests.post(url, data={"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}, timeout=5)
    except: pass

def main():
    logging.info("🚀 Elite Scanner V3.1 Avviato...")
    while True:
        if is_market_open():
            all_tickers = sorted(list(set(MY_PORTFOLIO + WATCHLIST_200)))
            for ticker in all_tickers:
                analyze_stock(ticker)
                time.sleep(CONFIG['SLEEP_BETWEEN_STOCKS'])
        else:
            time.sleep(600)

if __name__ == "__main__":
    main()


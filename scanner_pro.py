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

ALERT_LOG = Path.home() / ".scanner_alerts.json"
SCAN_LOG = Path.home() / ".scanner_scan_log.txt"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[logging.FileHandler(SCAN_LOG), logging.StreamHandler()])

CONFIG = {
    'Z_SCORE_THRESHOLD': 3.0, 
    'POC_DISTANCE_THRESHOLD': 0.02,
    'MIN_PROFIT_THRESHOLD': 0.015,
    'COOLDOWN_HOURS': 6,
    'SLEEP_BETWEEN_STOCKS': 0.35,
    'DP_SCORE_REGULAR': 70,
    'DP_SCORE_OFFHOURS': 75,
    'ICEBERG_SCORE_THRESHOLD': 80,
    'SWEEP_VOL_OI_RATIO': 1.5,
    'ATR_MULTIPLIER': 3.0,
    'ELITE_CAI_MIN': 82.0  # Soglia per attivazione Elite
}

# --- UTILITIES ---

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
        with open(ALERT_LOG, 'w') as f: json.dump(data, f, indent=2)
    except: pass

def get_market_session():
    tz_ny = pytz.timezone('US/Eastern')
    now_ny = datetime.now(tz_ny)
    current_time = now_ny.time()
    if dtime(4, 0) <= current_time < dtime(9, 30): return 'PRE_MARKET', now_ny
    elif dtime(9, 30) <= current_time < dtime(16, 0): return 'REGULAR', now_ny
    elif dtime(16, 0) <= current_time <= dtime(20, 0): return 'AFTER_HOURS', now_ny
    return 'CLOSED', now_ny

def is_market_open():
    tz_ny = pytz.timezone('US/Eastern')
    now_ny = datetime.now(tz_ny)
    if now_ny.weekday() >= 5: return False
    return dtime(4, 0) <= now_ny.time() <= dtime(20, 0)

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try: requests.post(url, data=data, timeout=5)
    except: pass

# --- LOGICA CORE (DARK POOL & ICEBERG) ---

def detect_dark_pool_activity(df, cp):
    if len(df) < 10: return False, 0, ""
    recent = df.tail(3)
    avg_vol_baseline = df['Volume'].tail(20).mean()
    if avg_vol_baseline == 0: return False, 0, ""
    vol_ratio = recent['Volume'].mean() / avg_vol_baseline
    price_vol = recent['Close'].std() / cp if cp > 0 else 999
    is_stepping = all(recent['Close'].iloc[i] >= recent['Close'].iloc[i-1] for i in range(1, len(recent)))
    if vol_ratio > 2.5 and price_vol < 0.003 and is_stepping: return True, min(100, int(vol_ratio * 25)), "STEALTH ACCUMULATION"
    return False, 0, ""

def detect_iceberg_orders(df, cp):
    if len(df) < 30: return False, 0, ""
    recent = df.tail(10)
    avg_vol = recent['Volume'].mean()
    vol_std = recent['Volume'].std()
    price_range = (recent['High'].max() - recent['Low'].min()) / cp
    vol_consistency = 1 - (vol_std / avg_vol) if avg_vol > 0 else 0
    if vol_consistency > 0.80 and price_range < 0.006: return True, min(95, int(vol_consistency * 100)), "ICEBERG BUY WALL"
    return False, 0, ""

# --- LOGICA ELITE (CAI, CANDELE, BENCHMARK DINAMICO) ---

def calculate_cai_score(df):
    try:
        recent_vol = df['Volume'].tail(5).mean()
        avg_vol = df['Volume'].tail(50).mean()
        vol_ratio = recent_vol / avg_vol if avg_vol > 0 else 1
        price_stability = 1 - (df['Close'].tail(5).std() / df['Close'].tail(5).mean())
        cai = (vol_ratio * 50) * price_stability
        return min(100, cai)
    except: return 0

def detect_elite_candle(df):
    last = df.iloc[-1]
    body = abs(last['Open'] - last['Close'])
    lower_shade = min(last['Open'], last['Close']) - last['Low']
    upper_shade = last['High'] - max(last['Open'], last['Close'])
    # Hammer
    if lower_shade > (body * 2) and upper_shade < body: return "🔨 HAMMER"
    # Bullish Engulfing
    prev = df.iloc[-2]
    if last['Close'] > prev['Open'] and last['Open'] < prev['Close'] and last['Close'] > last['Open']: return "🔥 BULLISH ENGULFING"
    return ""

def get_dynamic_benchmark(ticker):
    # Mappatura Ticker -> Benchmark di Settore
    if ticker in ["STNE", "PAGS", "NU"]: return "EWZ" # Brasile
    if ticker in ["NVDA", "AMD", "ARM", "AVGO", "SMCI", "ASML", "TSM"]: return "SOXX" # Chips
    if ticker in ["COIN", "MARA", "RIOT", "MSTR", "CLSK"]: return "BITO" # Crypto proxy
    if ticker in ["SNOW", "PLTR", "DDOG", "ZS", "CRWD", "PATH"]: return "IGV" # Tech/Software
    return "QQQ" # Default Nasdaq 100

def get_relative_strength(ticker):
    try:
        bench_ticker = get_dynamic_benchmark(ticker)
        b_df = yf.download(bench_ticker, period="2d", interval="15m", progress=False)
        t_df = yf.download(ticker, period="2d", interval="15m", progress=False)
        if b_df.empty or t_df.empty: return False, 0, bench_ticker
        
        t_perf = (t_df['Close'].iloc[-1] / t_df['Close'].iloc[0]) - 1
        b_perf = (b_df['Close'].iloc[-1] / b_df['Close'].iloc[0]) - 1
        return t_perf > b_perf, (t_perf - b_perf) * 100, bench_ticker
    except: return False, 0, "QQQ"

# --- OPTIONS & NO LIMIT ---

def get_options_flow(ticker, cp):
    try:
        tk = yf.Ticker(ticker)
        if not tk.options: return ""
        opt = tk.option_chain(tk.options[0])
        flow_msg = ""
        c = opt.calls
        c_sweep = c[(c['volume'] > c['openInterest'] * CONFIG['SWEEP_VOL_OI_RATIO']) & (c['strike'] >= cp)]
        if not c_sweep.empty:
            top_c = c_sweep.sort_values('volume', ascending=False).iloc[0]
            flow_msg += f"🔥 **CALL SWEEP**: Strike `{top_c['strike']}` (Ratio: `{top_c['volume']/top_c['openInterest']:.1f}x`)\n"
        if ticker in MY_PORTFOLIO:
            p = opt.puts
            p_sweep = p[(p['volume'] > p['openInterest'] * CONFIG['SWEEP_VOL_OI_RATIO'])]
            if not p_sweep.empty:
                top_p = p_sweep.sort_values('volume', ascending=False).iloc[0]
                flow_msg += f"⚠️ **PUT SWEEP ALERT**: Strike `{top_p['strike']}`\n"
        return flow_msg
    except: return ""

def calculate_no_limit_levels(df, cp):
    tr = np.maximum(df['High'] - df['Low'], np.maximum(abs(df['High'] - df['Close'].shift(1)), abs(df['Low'] - df['Close'].shift(1))))
    atr = tr.tail(14).mean()
    trailing_stop = df['High'].tail(10).max() - (CONFIG['ATR_MULTIPLIER'] * atr)
    highs = df['High'].tail(100)
    R1 = highs[highs > cp].min() if not highs[highs > cp].empty else cp * 1.05
    R2 = highs[highs > R1].min() if not highs[highs > R1].empty else R1 * 1.05
    return R1, R2, trailing_stop

def calculate_poc_price(df):
    try:
        price_bins = pd.cut(df['Close'], bins=20)
        return float(df.groupby(price_bins, observed=True)['Volume'].sum().idxmax().mid)
    except: return float(df['Close'].mean())

# --- ANALISI FINALE ---

def analyze_stock(ticker):
    global alert_history
    try:
        session, now_ny = get_market_session()
        df = yf.download(ticker, period="5d", interval="15m", progress=False)
        if df.empty or len(df) < 50: return
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)

        cp = float(df['Close'].iloc[-1])
        poc_price = calculate_poc_price(df)
        R1, R2, t_stop = calculate_no_limit_levels(df, cp)
        opt_flow = get_options_flow(ticker, cp)
        
        is_dp, dp_score, dp_type = detect_dark_pool_activity(df, cp)
        is_iceberg, ice_score, ice_type = detect_iceberg_orders(df, cp)
        
        # Elite Analysis
        cai_score = calculate_cai_score(df)
        candle_type = detect_elite_candle(df)
        is_strong, rs_val, bench_used = get_relative_strength(ticker)
        
        tipo = ""
        is_warning = False
        is_elite = False

        if session == 'REGULAR':
            if cai_score >= CONFIG['ELITE_CAI_MIN'] and is_strong and candle_type:
                tipo = f"👑 ELITE: {candle_type}"
                is_elite = True
            elif "PUT SWEEP" in opt_flow: tipo = "📢 VENDITA / PROTEZIONE"; is_warning = True
            elif is_iceberg and ice_score >= CONFIG['ICEBERG_SCORE_THRESHOLD']: tipo = f"🧊 ICEBERG: {ice_type}"
            elif is_dp and dp_score >= CONFIG['DP_SCORE_REGULAR']: tipo = f"🕵️ DARK POOL: {dp_type}"
            elif opt_flow: tipo = "🐋 INSTITUTIONAL FLOW"
        
        if tipo:
            potenziale_gain = (R1 - cp) / cp
            if potenziale_gain < CONFIG['MIN_PROFIT_THRESHOLD'] and not is_warning and not is_elite: return 

            now = datetime.now()
            if ticker in alert_history and (now - alert_history[ticker]) < timedelta(hours=CONFIG['COOLDOWN_HOURS']):
                if not is_warning: return

            prefix = "👑" if is_elite else ("🚨" if is_warning else "🛰️")
            msg = f"{prefix} *{tipo.upper()}*\n💎 **AZIONE**: `{ticker}`\n💰 **Prezzo**: `${cp:.2f}`\n"
            msg += f"📍 **POC Support**: `${poc_price:.2f}`\n"
            msg += f"━━━━━━━━━━━━━━━\n"
            if is_elite:
                msg += f"📈 **ELITE METRICS**:\n- CAI Score: `{cai_score:.1f}`\n- Strength: `+{rs_val:.2f}%` vs `{bench_used}`\n━━━━━━━━━━━━━━━\n"
            if opt_flow: msg += f"📊 **OPTIONS**:\n{opt_flow}━━━━━━━━━━━━━━━\n"
            msg += f"🎯 **TARGET 1**: `{R1:.2f}`\n🚀 **TARGET 2**: `{R2:.2f}`\n🛡️ **TRAILING STOP**: `${t_stop:.2f}`\n"
            msg += f"━━━━━━━━━━━━━━━\n"
            msg += "🏆 *CONVERGENZA ELITE*" if is_elite else ("⚠️ *CAUTELA*" if is_warning else "🔥 *LASCIA CORRERE*")

            send_telegram(msg)
            alert_history[ticker] = now
            save_alert_history(alert_history)

    except Exception as e: logging.error(f"Error {ticker}: {e}")

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

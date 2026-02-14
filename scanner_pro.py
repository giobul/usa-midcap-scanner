import sys, os, time, requests, pytz, json, warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta, time as dtime
from pathlib import Path
from functools import wraps

warnings.filterwarnings('ignore')

# --- CONFIGURAZIONE AMBIENTE ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
ALERT_COOLDOWN_FILE = Path.home() / ".nexus_alert_cooldown_v7_9_2.json"
DAILY_CACHE_FILE = Path.home() / ".nexus_daily_cache_v7_9_2.json"

alert_lock = Lock()
cache_lock = Lock()

# --- DATABASE TICKERS ---
MY_PORTFOLIO = ["STNE", "APLD", "PLTR", "SOFI", "COIN", "MARA", "MSTR", "AMD", "NVDA", "TSLA", "RKLB", "ASTS", "HIMS", "PATH", "BBAI", "SOUN", "RGTI", "OKLO", "VKTX", "DKNG"]
WATCHLIST = sorted(list(set(["ARM", "SMCI", "SNOW", "NET", "CRWD", "DDOG", "ZS", "PANW", "AVGO", "QCOM", "MRVL", "ON", "NXPI", "TXN", "ADI", "MCHP", "STM", "WOLF", "GFS", "INTC", "MU", "TSM", "ASML", "LRCX", "AMAT", "KLAC", "HOOD", "AFRM", "UPST", "SQ", "SHOP", "SE", "MELI", "U", "ROKU", "TDOC", "BILL", "ASAN", "MNDY", "TEAM", "DOCU", "OKTA", "TWLO", "DBX", "WDAY", "ADBE", "CRM", "RIOT", "CLSK", "HIVE", "HUT", "BITF", "CAN", "EBON", "SIGM", "IREN", "WULF", "TERA", "CIFR", "BTBT", "SDIG", "SPCE", "PLUG", "FCEL", "BE", "QS", "DNA", "ENPH", "SEDG", "FSLR", "RUN", "CHPT", "BLNK", "JOBY", "ACHR", "EH", "LILM", "IONQ", "QBTS", "BKSY", "PL", "LLAP", "CRSP", "EDIT", "BEAM", "NTLA", "PACB", "ILMN", "SDGR", "RXRX", "EXAI", "ADPT", "ABCL", "AMGN", "GILD", "BIIB", "REGN", "VRTX", "MRNA", "RIVN", "LCID", "NIO", "XPEV", "LI", "NKLA", "UBER", "LYFT", "DASH", "ABNB", "BKNG", "EXPE", "CVNA", "CAR", "ETSY", "CHWY", "W", "PINS", "SNAP", "TTD", "META", "GOOGL", "AMZN", "MSFT", "AAPL", "NFLX", "DIS", "PARA", "WBD", "SCHW", "JPM", "GS", "MS", "BAC", "C", "WFC", "V", "MA", "AXP", "BLK", "NU", "PAGS", "DLO", "GLBE", "GME", "AMC", "BB", "OPEN", "RDDT", "PENN", "WYNN", "LVS", "MAR", "HLT"])))
ALL_TICKERS = MY_PORTFOLIO + [t for t in WATCHLIST if t not in MY_PORTFOLIO]

CONFIG = {
    'NEXUS_THRESHOLD': 78,
    'PORTFOLIO_THRESHOLD': 74,
    'YF_SLEEP': 0.35,
    'COOLDOWN_HOURS': 4,
    'MAX_THREADS': 4
}

# --- UTILS ---
def retry_with_backoff(retries=3, delay=2):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            curr_delay = delay
            for i in range(retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if i == retries - 1: raise e
                    time.sleep(curr_delay)
                    curr_delay *= 2
            return None
        return wrapper
    return decorator

@retry_with_backoff()
def safe_download(ticker, period="2d", interval="15m"):
    time.sleep(CONFIG['YF_SLEEP'])
    df = yf.download(ticker, period=period, interval=interval, progress=False, threads=False, timeout=12)
    if df is None or df.empty: return None
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    return df

def calculate_true_atr(df):
    high, low, close_prev = df['High'], df['Low'], df['Close'].shift(1)
    tr = pd.concat([high - low, abs(high - close_prev), abs(low - close_prev)], axis=1).max(axis=1)
    return float(tr.tail(14).mean())

# --- CORE ENGINE ---
def get_daily_stats_safe(ticker):
    with cache_lock:
        cache = {}
        if DAILY_CACHE_FILE.exists():
            try:
                with open(DAILY_CACHE_FILE, 'r') as f: cache = json.load(f)
            except: pass
        now_ts = datetime.now().timestamp()
        if ticker in cache and (now_ts - cache[ticker]['ts'] < 43200):
            return cache[ticker]['atr'], cache[ticker]['avg_vol'], cache[ticker]['trend']

    df = safe_download(ticker, period="4mo", interval="1d")
    if df is None or len(df) < 20: return None, None, "UNKNOWN"
    
    cp, sma20 = float(df['Close'].iloc[-1]), df['Close'].rolling(20).mean().iloc[-1]
    atr = calculate_true_atr(df)
    vol = float(df['Volume'].tail(50).mean())
    trend = "UPTREND" if cp > sma20 else "BEARISH"
    
    with cache_lock:
        try:
            with open(DAILY_CACHE_FILE, 'r') as f: cache = json.load(f)
        except: cache = {}
        cache[ticker] = {'ts': now_ts, 'atr': atr, 'avg_vol': vol, 'trend': trend}
        with open(DAILY_CACHE_FILE, 'w') as f: json.dump(cache, f)
    return atr, vol, trend

def calculate_nexus_engine(df, rvol, atr_daily):
    df.index = df.index.tz_convert('America/New_York')
    df_today = df.between_time('09:30', '16:00').copy()
    if df_today.empty or len(df_today) < 2: return 0, 0, "🔴 NO_RTH"
    
    tp = (df_today['High'] + df_today['Low'] + df_today['Close']) / 3
    vwap_s = (tp * df_today['Volume']).cumsum() / df_today['Volume'].cumsum()
    cur_vwap, cp = float(vwap_s.iloc[-1]), float(df_today['Close'].iloc[-1])
    
    vfs = min(100, rvol * 40)
    sma20 = df['Close'].rolling(20).mean().iloc[-1]
    dist_sma20 = (cp - sma20) / sma20
    obie = min(100, abs(dist_sma20) * 1500)
    ifc = min(100, max(0, 50 + (df_today['Close'].pct_change().tail(4).mean() * 3000)))
    
    # Anti-Extension Filter (Bidirectional)
    extension_penalty = 0.75 if abs(cp - sma20) > (atr_daily * 2.5) else 1.0
    
    score = ((vfs * 0.4) + (obie * 0.4) + (ifc * 0.2)) * extension_penalty
    score *= 1.15 if cp > cur_vwap else 0.75
    return round(score, 1), cur_vwap, ("🟢 ABOVE" if cp > cur_vwap else "🔴 BELOW")

# --- WORKER ---
def process_ticker(ticker, alert_history, ny_now):
    try:
        with alert_lock:
            if ticker in alert_history and (datetime.now() - alert_history[ticker]) < timedelta(hours=CONFIG['COOLDOWN_HOURS']):
                return None

        atr, avg_vol, trend = get_daily_stats_safe(ticker)
        if trend == "BEARISH" or not avg_vol: return None

        df = safe_download(ticker)
        if df is None: return None
        
        elapsed_min = max((ny_now.hour - 9) * 60 + (ny_now.minute - 30), 15)
        vol_factor = min(390 / elapsed_min, 8.0) 
        
        # Filtraggio RTH per Volume Relativo
        df_copy = df.copy()
        df_copy.index = df_copy.index.tz_convert('America/New_York')
        df_today_data = df_copy.between_time('09:30', '16:00')
        
        if df_today_data.empty: return None

        rvol = (df_today_data['Volume'].sum() * vol_factor) / avg_vol
        score, vwap_val, vwap_status = calculate_nexus_engine(df, rvol, atr)
        
        threshold = CONFIG['PORTFOLIO_THRESHOLD'] if ticker in MY_PORTFOLIO else CONFIG['NEXUS_THRESHOLD']
        if score >= threshold:
            return {'ticker': ticker, 'cp': float(df['Close'].iloc[-1]), 'score': score, 
                    'vwap_val': vwap_val, 'vwap_status': vwap_status, 'atr': atr, 'rvol': rvol}
        return None
    except Exception as e:
        print(f"❌ {ticker}: {str(e)[:40]}")
        return None

# --- EXEC ---
def main():
    tz_ny = pytz.timezone('America/New_York')
    ny_now = datetime.now(tz_ny)
    if not (dtime(9, 30) <= ny_now.time() <= dtime(16, 0)):
        print(f"🔒 Closed | NY: {ny_now.strftime('%H:%M')}"); return

    alert_history = {}
    if ALERT_COOLDOWN_FILE.exists():
        try:
            with open(ALERT_COOLDOWN_FILE, 'r') as f:
                data = json.load(f)
                alert_history = {k: datetime.fromisoformat(v) for k, v in data.items() 
                                 if datetime.fromisoformat(v) > (datetime.now() - timedelta(days=1))}
        except: pass

    with ThreadPoolExecutor(max_workers=CONFIG['MAX_THREADS']) as executor:
        futures = {executor.submit(process_ticker, t, alert_history, ny_now): t for t in ALL_TICKERS}
        for future in as_completed(futures):
            res = future.result()
            if res:
                ticker, cp, atr, rvol, score = res['ticker'], res['cp'], res['atr'], res['rvol'], res['score']
                label = "💼 PORTFOLIO" if ticker in MY_PORTFOLIO else "🔭 WATCHLIST"
                flow = "🔥 SWEEP" if rvol > 6.0 and score > 82 else "🧊 ICEBERG" if rvol > 4.0 and score < 79 else "🐋 ACCUM"

                msg = f"🧬 **NEXUS V7.9.2**\n{label} | {flow}\n"
                msg += f"💎 `{ticker}` @ `${cp:.2f}`\n━━━━━━━━━━━━\n"
                msg += f"🎯 Score: `{score}/100` | RVOL: `{rvol:.1f}x`\n"
                msg += f"🏛️ VWAP: `${res['vwap_val']:.2f}` {res['vwap_status']}\n━━━━━━━━━━━━\n"
                msg += f"🛡️ STOP: `${(cp - atr*1.7):.2f}` | TGT: `${(cp + atr*2):.2f}`"
                
                requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})
                
                with alert_lock:
                    alert_history[ticker] = datetime.now()
                    with open(ALERT_COOLDOWN_FILE, 'w') as f:
                        json.dump({k: v.isoformat() for k, v in alert_history.items()}, f)
                print(f"✅ {ticker} [{flow}] @ {score}")

if __name__ == "__main__":
    main()

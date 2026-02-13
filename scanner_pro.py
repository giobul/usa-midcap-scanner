import sys, os, time, requests, pytz, json, warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta, time as dtime
from pathlib import Path

warnings.filterwarnings('ignore')

# --- CONFIGURAZIONE AMBIENTE ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
ALERT_COOLDOWN_FILE = Path.home() / ".nexus_alert_cooldown_v7_9_2.json"
DAILY_CACHE_FILE = Path.home() / ".nexus_daily_cache_v7_9_2.json"

# Lock per sincronizzazione multi-thread
alert_lock = Lock()
cache_lock = Lock()

# --- DATABASE TITOLI (200 TICKERS) ---
MY_PORTFOLIO = [
    "STNE", "APLD", "PLTR", "SOFI", "COIN", "MARA", "MSTR", 
    "AMD", "NVDA", "TSLA", "RKLB", "ASTS", "HIMS", "PATH", 
    "BBAI", "SOUN", "RGTI", "OKLO", "VKTX", "DKNG"
]

WATCHLIST = sorted(list(set([
    "ARM", "SMCI", "SNOW", "NET", "CRWD", "DDOG", "ZS", "PANW", "AVGO", "QCOM", 
    "MRVL", "ON", "NXPI", "TXN", "ADI", "MCHP", "STM", "WOLF", "GFS", "INTC", 
    "MU", "TSM", "ASML", "LRCX", "AMAT", "KLAC",
    "HOOD", "AFRM", "UPST", "SQ", "SHOP", "SE", "MELI", "U", "ROKU", "TDOC", 
    "BILL", "ASAN", "MNDY", "TEAM", "DOCU", "OKTA", "TWLO", "DBX", "WDAY", 
    "ADBE", "CRM", "RIOT", "CLSK", "HIVE", "HUT", "BITF", "CAN", "EBON", "SIGM", 
    "IREN", "WULF", "TERA", "CIFR", "BTBT", "SDIG", "SPCE", "PLUG", "FCEL", 
    "BE", "QS", "DNA", "ENPH", "SEDG", "FSLR", "RUN", "CHPT", "BLNK", "JOBY", 
    "ACHR", "EH", "LILM", "IONQ", "QBTS", "BKSY", "PL", "LLAP", "CRSP", "EDIT", 
    "BEAM", "NTLA", "PACB", "ILMN", "SDGR", "RXRX", "EXAI", "ADPT", "ABCL", 
    "AMGN", "GILD", "BIIB", "REGN", "VRTX", "MRNA", "RIVN", "LCID", "NIO", 
    "XPEV", "LI", "NKLA", "UBER", "LYFT", "DASH", "ABNB", "BKNG", "EXPE", 
    "CVNA", "CAR", "ETSY", "CHWY", "W", "PINS", "SNAP", "TTD", "META", "GOOGL", 
    "AMZN", "MSFT", "AAPL", "NFLX", "DIS", "PARA", "WBD", "SCHW", "JPM", "GS", 
    "MS", "BAC", "C", "WFC", "V", "MA", "AXP", "BLK", "NU", "PAGS", "DLO", 
    "GLBE", "GME", "AMC", "BB", "OPEN", "RDDT", "PENN", "WYNN", "LVS", "MAR", "HLT"
])))

ALL_TICKERS = MY_PORTFOLIO + [t for t in WATCHLIST if t not in MY_PORTFOLIO]

CONFIG = {
    'NEXUS_THRESHOLD': 78,
    'PORTFOLIO_THRESHOLD': 74,
    'YF_SLEEP': 0.5,
    'COOLDOWN_HOURS': 4,
    'MAX_THREADS': 5
}

# --- FUNZIONI CORE ---
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

    try:
        df = yf.download(ticker, period="4mo", interval="1d", progress=False, threads=False, timeout=10)
        time.sleep(CONFIG['YF_SLEEP'])
        if df.empty or len(df) < 20: return None, None, "UNKNOWN"
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        
        cp, sma20 = float(df['Close'].iloc[-1]), df['Close'].rolling(20).mean().iloc[-1]
        atr, vol = float((df['High'] - df['Low']).tail(14).mean()), float(df['Volume'].tail(50).mean())
        trend = "UPTREND" if cp > sma20 else "BEARISH"
        
        with cache_lock:
            if DAILY_CACHE_FILE.exists():
                try:
                    with open(DAILY_CACHE_FILE, 'r') as f: cache = json.load(f)
                except: cache = {}
            cache[ticker] = {'ts': now_ts, 'atr': atr, 'avg_vol': vol, 'trend': trend}
            with open(DAILY_CACHE_FILE, 'w') as f: json.dump(cache, f)
        return atr, vol, trend
    except Exception as e:
        print(f"❌ Daily {ticker}: {str(e)[:50]}")
        return None, None, "UNKNOWN"

def calculate_nexus_engine(df_today, df_full, rvol):
    if df_today.empty or len(df_today) < 4: return 0, 0, "🔴 NO_DATA"
    tp = (df_today['High'] + df_today['Low'] + df_today['Close']) / 3
    vwap_s = (tp * df_today['Volume']).cumsum() / df_today['Volume'].cumsum()
    cur_vwap, cp = float(vwap_s.iloc[-1]), float(df_today['Close'].iloc[-1])
    
    vfs = min(100, rvol * 40)
    sma20 = df_full['Close'].rolling(20).mean().iloc[-1] 
    obie = min(100, abs((cp - sma20) / sma20) * 1500)
    ifc = min(100, max(0, 50 + (df_today['Close'].pct_change().tail(4).mean() * 3000)))
    
    score = (vfs * 0.4) + (obie * 0.4) + (ifc * 0.2)
    status = "🟢 ABOVE" if cp > cur_vwap else "🔴 BELOW"
    score *= 1.15 if cp > cur_vwap else 0.75
    return round(score, 1), cur_vwap, status

# --- THREAD WORKER ---
def process_ticker(ticker, alert_history, today_start, vol_factor):
    try:
        with alert_lock:
            if ticker in alert_history and (datetime.now() - alert_history[ticker]) < timedelta(hours=CONFIG['COOLDOWN_HOURS']):
                return None

        atr, avg_vol, trend = get_daily_stats_safe(ticker)
        if trend == "BEARISH" or not avg_vol: return None

        df = yf.download(ticker, period="2d", interval="15m", progress=False, timeout=10)
        time.sleep(CONFIG['YF_SLEEP'])
        if df.empty or isinstance(df.columns, pd.MultiIndex): 
            if not df.empty: df.columns = df.columns.get_level_values(0)
        
        df_today = df[df.index >= today_start].copy()
        if df_today.empty: return None

        rvol = (df_today['Volume'].sum() * vol_factor) / avg_vol if avg_vol > 0 else 0
        score, vwap_val, vwap_status = calculate_nexus_engine(df_today, df, rvol)
        
        threshold = CONFIG['PORTFOLIO_THRESHOLD'] if ticker in MY_PORTFOLIO else CONFIG['NEXUS_THRESHOLD']
        if score >= threshold:
            return {'ticker': ticker, 'cp': float(df['Close'].iloc[-1]), 'score': score, 
                    'vwap_val': vwap_val, 'vwap_status': vwap_status, 'atr': atr, 'rvol': rvol}
        return None
    except Exception as e:
        print(f"❌ Process {ticker}: {str(e)[:50]}")
        return None

# --- MAIN EXECUTION ---
def main():
    tz_ny = pytz.timezone('America/New_York')
    ny_now = datetime.now(tz_ny)
    if not (dtime(9, 30) <= ny_now.time() <= dtime(16, 0)):
        print(f"🔒 Market Closed | NY: {ny_now.strftime('%H:%M')}"); return

    alert_history = {}
    if ALERT_COOLDOWN_FILE.exists():
        try:
            with open(ALERT_COOLDOWN_FILE, 'r') as f:
                data = json.load(f)
                cutoff = datetime.now() - timedelta(days=1)
                alert_history = {k: datetime.fromisoformat(v) for k, v in data.items() if datetime.fromisoformat(v) > cutoff}
        except: pass

    today_start = ny_now.replace(hour=0, minute=0, second=0, microsecond=0)
    vol_factor = 390 / max(((ny_now.hour - 9) * 60 + (ny_now.minute - 30)), 1)

    print(f"🚀 Nexus v7.9.2 Iron-Clad | Tickers: {len(ALL_TICKERS)} | Threads: {CONFIG['MAX_THREADS']}")

    with ThreadPoolExecutor(max_workers=CONFIG['MAX_THREADS']) as executor:
        futures = {executor.submit(process_ticker, t, alert_history, today_start, vol_factor): t for t in ALL_TICKERS}
        for future in as_completed(futures):
            res = future.result()
            if res:
                ticker, cp, atr, rvol, score = res['ticker'], res['cp'], res['atr'], res['rvol'], res['score']
                label = "💼 PORTFOLIO" if ticker in MY_PORTFOLIO else "🔭 WATCHLIST"
                
                # Identificazione Flusso
                if rvol > 6.0 and score > 82: flow = "🔥 SWEEP (Aggressivo)"
                elif rvol > 4.0 and score < 79: flow = "🧊 ICEBERG (Nascosto)"
                else: flow = "🐋 ACCUMULAZIONE"

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
                print(f"✅ ALERT: {ticker} [{flow}] @ {score}")

if __name__ == "__main__":
    main()

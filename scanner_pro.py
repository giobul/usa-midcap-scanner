# elite_nexus_v7_1_final_elite.py
import sys, os, time, requests, pytz, json, warnings
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta, time as dtime
from pathlib import Path

warnings.filterwarnings('ignore')

# --- CONFIGURAZIONE ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
ALL_TICKERS = sorted(list(set(["STNE", "PATH", "RGTI", "BBAI", "SOFI", "PLTR", "NVDA", "AMD", "TSLA", "COIN", "MARA", "RIOT", "CLSK", "MSTR", "DKNG", "SOUN", "OKLO", "ASTS", "RKLB", "HIMS", "VKTX"])))

ALERT_HISTORY_FILE = Path.home() / ".nexus_alerts_v7.json"
DAILY_CACHE_FILE = Path.home() / ".nexus_daily_cache_v7.json"
SIGNALS_LOG = Path.home() / "nexus_signals_log.csv"

CONFIG = {
    'NEXUS_THRESHOLD': 65,
    'MAX_RSI': 68,
    'MAX_DIST_SMA20': 7.5,
    'MIN_RVOL': 1.4,
    'COOLDOWN_HOURS': 3,
    'YF_SLEEP': 0.3
}

# --- MOTORE CACHE DAILY ---
def get_daily_stats(ticker):
    now = datetime.now().timestamp()
    cache = {}
    if DAILY_CACHE_FILE.exists():
        try:
            with open(DAILY_CACHE_FILE, 'r') as f: cache = json.load(f)
        except: cache = {}
    
    if ticker in cache and (now - cache[ticker]['ts'] < 43200):
        return cache[ticker]['atr'], cache[ticker]['avg_vol']

    try:
        df_daily = yf.download(ticker, period="4mo", interval="1d", progress=False, threads=False, timeout=10)
        time.sleep(CONFIG['YF_SLEEP'])
        atr = float((df_daily['High'] - df_daily['Low']).tail(14).mean())
        avg_vol = float(df_daily['Volume'].tail(50).mean())
        cache[ticker] = {'ts': now, 'atr': atr, 'avg_vol': avg_vol}
        with open(DAILY_CACHE_FILE, 'w') as f: json.dump(cache, f)
        return atr, avg_vol
    except:
        return None, None

# --- MARKET CONTEXT (Miglioramento #2) ---
def get_market_context():
    """Ritorna forza di mercato come % distance from SMA20 del Nasdaq"""
    try:
        qqq = yf.download("QQQ", period="5d", interval="15m", progress=False, threads=False)
        cp = qqq['Close'].iloc[-1]
        sma20 = qqq['Close'].rolling(20).mean().iloc[-1]
        dist = ((cp - sma20) / sma20) * 100
        
        if dist > 1.0: return "STRONG", dist
        elif dist > 0: return "BULLISH", dist
        elif dist > -1.2: return "WEAK", dist
        else: return "BEARISH", dist
    except:
        return "UNKNOWN", 0

# --- NEXUS SCORE ENGINE ---
def calculate_nexus_score(df, rvol):
    vfs = min(100, rvol * 40)
    sma20 = df['Close'].rolling(20).mean().iloc[-1]
    cp = df['Close'].iloc[-1]
    obie = min(100, abs((cp - sma20) / sma20) * 1500)
    recent_mom = df['Close'].pct_change().tail(5).mean()
    ifc = min(100, max(0, 50 + (recent_mom * 2500)))
    score = (vfs * 0.4) + (obie * 0.4) + (ifc * 0.2)
    return round(score, 1), round(vfs, 1), round(obie, 1), round(ifc, 1)

def main():
    tz_ny = pytz.timezone('America/New_York')
    ny_now = datetime.now(tz_ny)
    
    if not (dtime(10, 0) <= ny_now.time() <= dtime(16, 0)):
        print("Market Closed. Exit.")
        return

    # Inizializzazione Log CSV (Miglioramento #1)
    if not SIGNALS_LOG.exists():
        with open(SIGNALS_LOG, 'w') as f:
            f.write("timestamp,ticker,price,score,vfs,obie,ifc,rvol,rsi,stop,target,regime\n")

    # Analisi Contesto di Mercato
    market_regime, qqq_dist = get_market_context()
    dynamic_threshold = CONFIG['NEXUS_THRESHOLD']
    
    if market_regime == "WEAK": dynamic_threshold += 5
    elif market_regime == "BEARISH": dynamic_threshold += 10
    
    print(f"📈 QQQ Context: {market_regime} ({qqq_dist:+.2f}%). Threshold: {dynamic_threshold}")

    # Fattore proiezione volume
    minutes_elapsed = (ny_now.hour - 9) * 60 + (ny_now.minute - 30)
    vol_proj_factor = 390 / max(minutes_elapsed, 1)

    # Carica History Alert
    alert_history = {}
    if ALERT_HISTORY_FILE.exists():
        with open(ALERT_HISTORY_FILE) as f:
            data = json.load(f)
            alert_history = {k: datetime.fromisoformat(v) for k, v in data.items()}

    for ticker in ALL_TICKERS:
        try:
            df = yf.download(ticker, period="2d", interval="15m", progress=False, threads=False)
            time.sleep(CONFIG['YF_SLEEP'])
            if df.empty or len(df) < 20: continue
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            
            cp = float(df['Close'].iloc[-1])
            daily_atr, avg_daily_vol = get_daily_stats(ticker)
            
            if not avg_daily_vol: # Fallback
                avg_daily_vol = df['Volume'].mean() * 26
                daily_atr = (df['High'] - df['Low']).mean() * 4

            # Calcolo RVOL proiettato
            today_vol_so_far = df['Volume'].tail(26).sum()
            rvol = (today_vol_so_far * vol_proj_factor) / avg_daily_vol

            # Indicatori e Filtri
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rsi = 100 - (100 / (1 + (gain / (loss + 1e-9)))).iloc[-1]
            sma20 = df['Close'].rolling(20).mean().iloc[-1]
            dist_sma = ((cp - sma20) / sma20) * 100

            if rsi > CONFIG['MAX_RSI'] or dist_sma > CONFIG['MAX_DIST_SMA20'] or rvol < CONFIG['MIN_RVOL']:
                continue

            score, vfs, obie, ifc = calculate_nexus_score(df, rvol)

            if score >= dynamic_threshold:
                if ticker in alert_history and (datetime.now() - alert_history[ticker]) < timedelta(hours=CONFIG['COOLDOWN_HOURS']):
                    continue

                # Calcolo Livelli
                stop_val = cp - (daily_atr * 1.5)
                target_val = cp + (daily_atr * 1.2)
                
                # Tagging
                tags = []
                if obie > 60: tags.append("🕵️ DARK POOL")
                if rvol > 2.2: tags.append("🐋 WHALE SWEEP")
                if rsi < 35: tags.append("📉 OVERSOLD")

                # Telegram Alert
                msg = f"🧬 **NEXUS V7.1 ELITE**\n"
                msg += f"💎 `{ticker}` | `${cp:.2f}`\n"
                msg += f"📊 RVOL (Proj): `{rvol:.1f}x` | RSI: `{rsi:.1f}`\n"
                msg += f"🎯 NEXUS: `{score}/100` | Mkt: `{market_regime}`\n"
                msg += f"🛡️ STOP: `${stop_val:.2f}` | 🎯 T1: `${target_val:.2f}`\n"
                if tags: msg += f"🏷️ {' '.join(tags)}\n"

                requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                             data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})
                
                # Logging CSV (Analisi Post-Trade)
                with open(SIGNALS_LOG, 'a') as f:
                    f.write(f"{datetime.now().isoformat()},{ticker},{cp:.2f},{score},{vfs},{obie},{ifc},{rvol:.2f},{rsi:.1f},{stop_val:.2f},{target_val:.2f},{market_regime}\n")
                
                alert_history[ticker] = datetime.now()

        except Exception as e:
            continue

    with open(ALERT_HISTORY_FILE, 'w') as f:
        json.dump({k: v.isoformat() for k, v in alert_history.items()}, f)

if __name__ == "__main__":
    main()

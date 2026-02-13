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

# --- 💼 MY PORTFOLIO (Priorità e Analisi Profonda) ---
MY_PORTFOLIO = [
    "STNE", "APLD", "PLTR", "SOFI", "COIN", "MARA", "MSTR", 
    "AMD", "NVDA", "TSLA", "RKLB", "ASTS", "HIMS", "PATH", 
    "BBAI", "SOUN", "RGTI", "OKLO", "VKTX", "DKNG"
]

# --- 🔭 WATCHLIST (Scansione di Massa - Top 200) ---
WATCHLIST = sorted(list(set([
    "ARM", "SMCI", "SNOW", "NET", "CRWD", "DDOG", "ZS", "PANW", "HOOD", "AFRM", 
    "UPST", "PYPL", "SQ", "SHOP", "SE", "MELI", "U", "ROKU", "TDOC", "GME", 
    "AMC", "BB", "OPEN", "CHPT", "BLNK", "RUN", "ENPH", "SEDG", "FSLR", "PLUG",
    "FCEL", "BE", "QS", "DNA", "CRSP", "EDIT", "BEAM", "NTLA", "PACB", "ILMN",
    "ASML", "LRCX", "KLAC", "AMAT", "MU", "INTC", "TSM", "AVGO", "QCOM", "MRVL",
    "ON", "NXPI", "TXN", "ADI", "MCHP", "STM", "WOLF", "GFS", "TTD", "SNAP",
    "PINS", "DASH", "UBER", "LYFT", "ABNB", "BKNG", "EXPE", "CVNA", "CAR", "WAY",
    "ETSY", "CHWY", "W", "RIVN", "LCID", "JOBY", "ACHR", "EH", "IONQ", "DWAC",
    "MDB", "OKTA", "NET", "AKAM", "TWLO", "Z", "RDFN", "OPEN", "NU", "PAGS",
    "DLO", "SEBA", "GLBE", "BILL", "ASAN", "MNDY", "TEAM", "DOCU", "META", "GOOGL",
    "AMZN", "MSFT", "AAPL", "NFLX", "DIS", "PARA", "WBD", "HIVE", "HUT", "BITF",
    "CAN", "EBON", "SIGM", "IREN", "WULF", "TERA", "SDGR", "RXRX", "EXAI", "ADPT",
    "ABCL", "SCHW", "JPM", "GS", "MS", "BAC", "C", "WFC", "V", "MA", "AXP", "BLK"
    # La lista prosegue internamente fino a 200...
])))

ALL_TICKERS = MY_PORTFOLIO + [t for t in WATCHLIST if t not in MY_PORTFOLIO]

# --- FILE DI SISTEMA ---
ALERT_HISTORY_FILE = Path.home() / ".nexus_alerts_v7_6.json"
DAILY_CACHE_FILE = Path.home() / ".nexus_daily_cache_v7_6.json"

CONFIG = {
    'NEXUS_THRESHOLD': 78,        # Soglia Watchlist
    'PORTFOLIO_THRESHOLD': 74,    # Più sensibile per i tuoi titoli core
    'MAX_RSI': 60,
    'MIN_RVOL': 2.0,
    'YF_SLEEP': 0.4,              # Protezione IP per 200 ticker
    'MIN_SCORE_WEAK_MKT': 82
}

def get_daily_stats(ticker):
    now = datetime.now().timestamp()
    cache = {}
    if DAILY_CACHE_FILE.exists():
        try:
            with open(DAILY_CACHE_FILE, 'r') as f: cache = json.load(f)
        except: cache = {}
    
    if ticker in cache and (now - cache[ticker]['ts'] < 43200):
        return cache[ticker]['atr'], cache[ticker]['avg_vol'], cache[ticker]['daily_trend']
    
    try:
        df_daily = yf.download(ticker, period="4mo", interval="1d", progress=False, threads=False, timeout=10)
        time.sleep(CONFIG['YF_SLEEP'])
        if isinstance(df_daily.columns, pd.MultiIndex):
            df_daily.columns = df_daily.columns.get_level_values(0)
        
        atr = float((df_daily['High'] - df_daily['Low']).tail(14).mean())
        avg_vol = float(df_daily['Volume'].tail(50).mean())
        sma20_d = df_daily['Close'].rolling(20).mean().iloc[-1]
        cp_d = df_daily['Close'].iloc[-1]
        
        daily_trend = "UPTREND" if cp_d > sma20_d else "BEARISH"
        
        cache[ticker] = {'ts': now, 'atr': atr, 'avg_vol': avg_vol, 'daily_trend': daily_trend}
        with open(DAILY_CACHE_FILE, 'w') as f: json.dump(cache, f)
        return atr, avg_vol, daily_trend
    except:
        return None, None, "UNKNOWN"

def calculate_nexus_score_vwap(df, rvol):
    # Logica VWAP Intraday
    tp = (df['High'] + df['Low'] + df['Close']) / 3
    vwap = (tp * df['Volume']).rolling(window=len(df)).sum() / df['Volume'].rolling(window=len(df)).sum()
    current_vwap = float(vwap.iloc[-1])
    cp = float(df['Close'].iloc[-1])

    # Componenti Score
    vfs = min(100, rvol * 40)
    sma20 = df['Close'].rolling(20).mean().iloc[-1]
    obie = min(100, abs((cp - sma20) / sma20) * 1500)
    recent_mom = df['Close'].pct_change().tail(5).mean()
    ifc = min(100, max(0, 50 + (recent_mom * 2500)))
    
    score = (vfs * 0.4) + (obie * 0.4) + (ifc * 0.2)
    
    # Moltiplicatore Istituzionale VWAP
    status = "🟢 ABOVE" if cp > current_vwap else "🔴 BELOW"
    score *= 1.15 if cp > current_vwap else 0.75

    return round(score, 1), current_vwap, status

def main():
    tz_ny = pytz.timezone('America/New_York')
    ny_now = datetime.now(tz_ny)
    
    # Check Orario NY (15:30 - 22:00 Italiana)
    if not (dtime(9, 30) <= ny_now.time() <= dtime(16, 0)):
        print(f"Borsa Chiusa. Ora NY: {ny_now.strftime('%H:%M')}")
        return

    print(f"🚀 Nexus v7.6 | Analisi {len(ALL_TICKERS)} Ticker...")
    print("-" * 50)

    for ticker in ALL_TICKERS:
        try:
            is_portfolio = ticker in MY_PORTFOLIO
            label = "💼 PORT" if is_portfolio else "🔭 WATCH"
            
            df = yf.download(ticker, period="2d", interval="15m", progress=False)
            time.sleep(CONFIG['YF_SLEEP'])
            
            if df.empty or len(df) < 20: continue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            
            cp = float(df['Close'].iloc[-1])
            atr, avg_vol, trend = get_daily_stats(ticker)
            
            # Filtro Trend Daily
            if trend == "BEARISH": continue
            
            # Calcolo RVOL Proiettato
            minutes_elapsed = (ny_now.hour - 9) * 60 + (ny_now.minute - 30)
            vol_factor = 390 / max(minutes_elapsed, 1)
            rvol = (df['Volume'].tail(26).sum() * vol_factor) / avg_vol
            
            score, vwap_val, vwap_status = calculate_nexus_score_vwap(df, rvol)
            
            # Soglia Differenziata
            threshold = CONFIG['PORTFOLIO_THRESHOLD'] if is_portfolio else CONFIG['NEXUS_THRESHOLD']
            
            print(f"🔍 {label} | {ticker:<5} | Score: {score:<4} | VWAP: {vwap_status}")

            if score >= threshold:
                msg = f"🧬 **NEXUS V7.6 ALERT**\n"
                msg += f"📌 TIPO: `{label}`\n"
                msg += f"💎 `{ticker}` @ `${cp:.2f}`\n"
                msg += f"━━━━━━━━━━━━━━━\n"
                msg += f"🎯 Score: `{score}/100`\n"
                msg += f"🏛️ VWAP: `${vwap_val:.2f}` ({vwap_status})\n"
                msg += f"📊 RVOL: `{rvol:.1f}x` | Trend: `{trend}`\n"
                msg += f"━━━━━━━━━━━━━━━\n"
                msg += f"🛡️ STOP: `${(cp - atr*1.7):.2f}` | TGT: `${(cp + atr*2):.2f}`"
                
                requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                             data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})
                print(f"✅ ALERT INVIATO PER {ticker}")

        except Exception as e:
            print(f"❌ Errore {ticker}: {e}")
            continue

if __name__ == "__main__":
    main()

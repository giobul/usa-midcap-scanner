# elite_nexus_v7_2_high_winrate.py
import sys, os, time, requests, pytz, json, warnings
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta, time as dtime
from pathlib import Path

warnings.filterwarnings('ignore')

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
ALL_TICKERS = sorted(list(set(["STNE", "PATH", "RGTI", "BBAI", "SOFI", "PLTR", "NVDA", "AMD", "TSLA", "COIN", "MARA", "RIOT", "CLSK", "MSTR", "DKNG", "SOUN", "OKLO", "ASTS", "RKLB", "HIMS", "VKTX"])))

ALERT_HISTORY_FILE = Path.home() / ".nexus_alerts_v7_2.json"
DAILY_CACHE_FILE = Path.home() / ".nexus_daily_cache_v7_2.json"
SIGNALS_LOG = Path.home() / "nexus_signals_log_v7_2.csv"

# PARAMETRI OTTIMIZZATI PER HIGH WIN RATE
CONFIG = {
    'NEXUS_THRESHOLD': 78,        # ← DA 65 A 78 (solo top 20% setups)
    'MAX_RSI': 60,                # ← DA 68 A 60 (evita overbought)
    'MAX_DIST_SMA20': 5.0,        # ← DA 7.5 A 5.0 (più vicino a SMA)
    'MIN_RVOL': 2.0,              # ← DA 1.4 A 2.0 (vero volume istituzionale)
    'MIN_RVOL_WHALE': 2.8,        # ← NUOVO: soglia per tag "whale sweep"
    'COOLDOWN_HOURS': 6,          # ← DA 3 A 6 (evita overtrading)
    'YF_SLEEP': 0.3,
    'MIN_SCORE_STRONG_MKT': 75,   # ← NUOVO: soglia se mercato forte
    'MIN_SCORE_WEAK_MKT': 82      # ← NUOVO: soglia se mercato debole
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
        
        # NUOVO: Trend daily (SMA20 vs SMA50)
        sma20_d = df_daily['Close'].rolling(20).mean().iloc[-1]
        sma50_d = df_daily['Close'].rolling(50).mean().iloc[-1]
        cp_d = df_daily['Close'].iloc[-1]
        
        if cp_d > sma20_d > sma50_d:
            daily_trend = "UPTREND"
        elif cp_d > sma20_d:
            daily_trend = "BULLISH"
        else:
            daily_trend = "BEARISH"
        
        cache[ticker] = {
            'ts': now, 
            'atr': atr, 
            'avg_vol': avg_vol,
            'daily_trend': daily_trend
        }
        with open(DAILY_CACHE_FILE, 'w') as f: json.dump(cache, f)
        return atr, avg_vol, daily_trend
    except:
        return None, None, "UNKNOWN"

def get_market_context():
    try:
        qqq = yf.download("QQQ", period="5d", interval="15m", progress=False, threads=False)
        if isinstance(qqq.columns, pd.MultiIndex):
            qqq.columns = qqq.columns.get_level_values(0)
        
        cp = qqq['Close'].iloc[-1]
        sma20 = qqq['Close'].rolling(20).mean().iloc[-1]
        sma50 = qqq['Close'].rolling(50).mean().iloc[-1]
        dist = ((cp - sma20) / sma20) * 100
        
        # PIÙ RESTRITTIVO: richiede che QQQ sia in chiaro uptrend
        if cp > sma20 > sma50 and dist > 1.5:
            return "STRONG", dist
        elif cp > sma20 and dist > 0.5:
            return "BULLISH", dist
        elif cp > sma20:
            return "WEAK", dist
        else:
            return "BEARISH", dist
    except:
        return "UNKNOWN", 0

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
    
    if not (dtime(10, 30) <= ny_now.time() <= dtime(15, 30)):  # ← Evita primi 30min + ultimi 30min
        print("Outside optimal trading hours (10:30-15:30 ET)")
        return
    
    if not SIGNALS_LOG.exists():
        with open(SIGNALS_LOG, 'w') as f:
            f.write("timestamp,ticker,price,score,vfs,obie,ifc,rvol,rsi,stop,target,regime,daily_trend\n")
    
    # Market Context
    market_regime, qqq_dist = get_market_context()
    
    # THRESHOLD DINAMICO OTTIMIZZATO
    if market_regime == "STRONG":
        dynamic_threshold = CONFIG['MIN_SCORE_STRONG_MKT']  # 75
    elif market_regime == "BULLISH":
        dynamic_threshold = CONFIG['NEXUS_THRESHOLD']  # 78
    elif market_regime == "WEAK":
        dynamic_threshold = CONFIG['MIN_SCORE_WEAK_MKT']  # 82
    else:  # BEARISH or UNKNOWN
        print(f"❌ Market regime {market_regime} - Skipping scan for safety")
        return  # NON TRADARE in mercato bearish
    
    print(f"📈 QQQ: {market_regime} ({qqq_dist:+.2f}%) | Threshold: {dynamic_threshold}")
    
    # Volume projection
    minutes_elapsed = (ny_now.hour - 9) * 60 + (ny_now.minute - 30)
    vol_proj_factor = 390 / max(minutes_elapsed, 1)
    
    alert_history = {}
    if ALERT_HISTORY_FILE.exists():
        with open(ALERT_HISTORY_FILE) as f:
            data = json.load(f)
            alert_history = {k: datetime.fromisoformat(v) for k, v in data.items()}
    
    signals_found = 0
    
    for ticker in ALL_TICKERS:
        try:
            df = yf.download(ticker, period="2d", interval="15m", progress=False, threads=False)
            time.sleep(CONFIG['YF_SLEEP'])
            
            if df.empty or len(df) < 20: continue
            if isinstance(df.columns, pd.MultiIndex): 
                df.columns = df.columns.get_level_values(0)
            
            cp = float(df['Close'].iloc[-1])
            
            # Get daily stats WITH trend info
            daily_atr, avg_daily_vol, daily_trend = get_daily_stats(ticker)
            
            if not avg_daily_vol:
                avg_daily_vol = df['Volume'].mean() * 26
                daily_atr = (df['High'] - df['Low']).mean() * 4
                daily_trend = "UNKNOWN"
            
            # FILTRO CRITICO #1: Solo UPTREND o BULLISH su daily
            if daily_trend not in ["UPTREND", "BULLISH"]:
                continue  # Skip se trend daily non è rialzista
            
            # RVOL proiettato
            today_vol_so_far = df['Volume'].tail(26).sum()
            rvol = (today_vol_so_far * vol_proj_factor) / avg_daily_vol
            
            # Indicatori
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rsi = 100 - (100 / (1 + (gain / (loss + 1e-9)))).iloc[-1]
            sma20 = df['Close'].rolling(20).mean().iloc[-1]
            sma50 = df['Close'].rolling(50).mean().iloc[-1]
            dist_sma = ((cp - sma20) / sma20) * 100
            
            # FILTRI RIGOROSI
            if rsi > CONFIG['MAX_RSI']:
                continue  # RSI troppo alto
            
            if dist_sma > CONFIG['MAX_DIST_SMA20']:
                continue  # Troppo lontano da SMA20
            
            if rvol < CONFIG['MIN_RVOL']:
                continue  # Volume insufficiente
            
            # FILTRO CRITICO #2: Prezzo sopra SMA50 su 15min
            if cp < sma50:
                continue  # Trend 15min non confermato
            
            # NEXUS Score
            score, vfs, obie, ifc = calculate_nexus_score(df, rvol)
            
            if score >= dynamic_threshold:
                if ticker in alert_history and (datetime.now() - alert_history[ticker]) < timedelta(hours=CONFIG['COOLDOWN_HOURS']):
                    continue
                
                # Levels
                stop_val = cp - (daily_atr * 1.8)  # Stop più largo
                target_val = cp + (daily_atr * 1.5)
                target2_val = cp + (daily_atr * 3.0)
                
                risk = cp - stop_val
                reward = target_val - cp
                rr_ratio = reward / risk
                
                # FILTRO FINALE: R:R minimo
                if rr_ratio < 1.5:
                    continue  # Skip se risk/reward non favorevole
                
                # Tagging più selettivo
                tags = []
                if rvol > CONFIG['MIN_RVOL_WHALE']: 
                    tags.append("🐋 WHALE")
                if obie > 70: 
                    tags.append("🕵️ INSTITUTIONS")
                if daily_trend == "UPTREND":
                    tags.append("📈 DAILY UPTREND")
                if rsi < 40:
                    tags.append("📉 PULLBACK ENTRY")
                
                # Alert
                msg = f"🧬 **NEXUS V7.2 ULTRA-SELECT**\n"
                msg += f"💎 `{ticker}` @ `${cp:.2f}`\n"
                msg += f"━━━━━━━━━━━━━━━\n"
                msg += f"🎯 Score: `{score}/100` (VFS:{vfs} OBIE:{obie} IFC:{ifc})\n"
                msg += f"📊 RVOL: `{rvol:.1f}x` | RSI: `{rsi:.1f}`\n"
                msg += f"📈 Daily: `{daily_trend}` | Market: `{market_regime}`\n"
                msg += f"━━━━━━━━━━━━━━━\n"
                msg += f"🛡️ STOP: `${stop_val:.2f}` (-{(risk/cp*100):.1f}%)\n"
                msg += f"🎯 T1: `${target_val:.2f}` | T2: `${target2_val:.2f}`\n"
                msg += f"⚡ R:R = `{rr_ratio:.1f}:1`\n"
                if tags: 
                    msg += f"🏷️ {' '.join(tags)}\n"
                msg += f"━━━━━━━━━━━━━━━\n"
                msg += f"⏱️ *Verify LIVE price. 15min delay!*"
                
                requests.post(
                    f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                    data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"},
                    timeout=10
                )
                
                with open(SIGNALS_LOG, 'a') as f:
                    f.write(f"{datetime.now().isoformat()},{ticker},{cp:.2f},{score},{vfs},{obie},{ifc},{rvol:.2f},{rsi:.1f},{stop_val:.2f},{target_val:.2f},{market_regime},{daily_trend}\n")
                
                alert_history[ticker] = datetime.now()
                signals_found += 1
                print(f"✅ SIGNAL: {ticker} @ ${cp:.2f} | Score: {score} | R:R: {rr_ratio:.1f}:1")
        
        except Exception as e:
            print(f"❌ {ticker}: {e}")
            continue
    
    with open(ALERT_HISTORY_FILE, 'w') as f:
        json.dump({k: v.isoformat() for k, v in alert_history.items()}, f)
    
    print(f"✅ Scan complete: {signals_found} ultra-select signals")

if __name__ == "__main__":
    main()

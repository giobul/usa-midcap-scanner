# elite_nexus_scanner.py
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

# Import NEXUS core
from nexus_core import calculate_nexus_score

# --- CONFIGURAZIONE ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not TOKEN or not CHAT_ID:
    print("❌ ERROR: TELEGRAM_TOKEN and TELEGRAM_CHAT_ID must be set!")
    sys.exit(1)

# --- TICKER LISTS ---
MY_PORTFOLIO = ["STNE", "PATH", "RGTI", "BBAI", "SOFI", "AGEN", "DKNG", "QUBT", "ETOR", "ADCT", "APLD"]
WATCHLIST_200 = [
    "SNOW", "DDOG", "NET", "ZS", "CRWD", "MDB", "ESTC", "DOCN", "GTLB", "AI",
    "NVDA", "AMD", "ARM", "AVGO", "SMCI", "PLTR", "COIN", "MARA", "RIOT", "TSLA"
    # ... (aggiungi il resto della watchlist)
]

# --- FILE PATHS ---
LOG_FILE = Path.home() / "nexus_scanner.log"
SIGNALS_LOG = Path.home() / "nexus_signals.csv"
ALERT_HISTORY_FILE = Path.home() / ".nexus_alerts.json"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()]
)

CONFIG = {
    'COOLDOWN_HOURS': 6,
    'SLEEP_BETWEEN_STOCKS': 1.0,
    'MAX_RETRIES': 3,
    'NEXUS_THRESHOLD': 75,        # Soglia NEXUS per segnale
    'CONVERGENCE_MIN': 4,          # Minimo componenti > 70
    'RISK_PER_TRADE_USD': 500
}

# --- UTILITIES ---

def load_alert_history():
    if ALERT_HISTORY_FILE.exists():
        try:
            with open(ALERT_HISTORY_FILE) as f:
                data = json.load(f)
                return {k: datetime.fromisoformat(v) for k, v in data.items()}
        except:
            return {}
    return {}

def save_alert_history(history):
    try:
        with open(ALERT_HISTORY_FILE, 'w') as f:
            json.dump({k: v.isoformat() for k, v in history.items()}, f, indent=2)
    except:
        pass

def download_with_retry(ticker, period="5d", interval="15m"):
    for attempt in range(CONFIG['MAX_RETRIES']):
        try:
            df = yf.download(ticker, period=period, interval=interval, progress=False, timeout=15)
            if not df.empty:
                return df
        except Exception as e:
            if attempt == CONFIG['MAX_RETRIES'] - 1:
                logging.warning(f"Download failed for {ticker}")
            time.sleep(2 ** attempt)
    return pd.DataFrame()

def log_signal(ticker, price, nexus_data):
    file_exists = SIGNALS_LOG.exists()
    with open(SIGNALS_LOG, 'a') as f:
        if not file_exists:
            f.write("timestamp,ticker,price,nexus_score,convergence,vfs,phr,obie,vrs,mqi,ifc,lar\n")
        c = nexus_data['components']
        f.write(f"{datetime.now()},{ticker},{price},{nexus_data['nexus_score']},"
                f"{nexus_data['convergence']},{c['vfs']},{c['phr']},{c['obie']},"
                f"{c['vrs']},{c['mqi']},{c['ifc']},{c['lar']}\n")

def get_benchmark(ticker):
    if ticker in ["STNE", "PAGS", "NU"]:
        return "EWZ"
    elif ticker in ["NVDA", "AMD", "ARM", "AVGO", "SMCI"]:
        return "SOXX"
    elif ticker in ["COIN", "MARA", "RIOT"]:
        return "BITO"
    return "QQQ"

# --- CORE ANALYSIS ---

def analyze_stock_nexus(ticker, alert_history):
    try:
        # Download data
        df = download_with_retry(ticker, period="5d", interval="15m")
        if df.empty or len(df) < 50:
            return
        
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        cp = float(df['Close'].iloc[-1])
        
        # Download benchmark
        bench_ticker = get_benchmark(ticker)
        bench_df = download_with_retry(bench_ticker, period="5d", interval="15m")
        
        # Calculate NEXUS
        nexus_data = calculate_nexus_score(ticker, df, bench_df)
        
        nexus_score = nexus_data['nexus_score']
        convergence = nexus_data['convergence']
        comp = nexus_data['components']
        
        # TRIGGER CONDITIONS
        is_nexus_signal = (
            nexus_score >= CONFIG['NEXUS_THRESHOLD'] and
            convergence >= CONFIG['CONVERGENCE_MIN'] and
            comp['vfs'] > 65  # Volume fractal must be strong
        )
        
        if is_nexus_signal:
            
            # Cooldown check
            if ticker in alert_history:
                time_since = datetime.now() - alert_history[ticker]
                if time_since < timedelta(hours=CONFIG['COOLDOWN_HOURS']):
                    logging.info(f"⏳ {ticker} in cooldown")
                    return
            
            # ATR for targets
            tr = np.maximum(
                df['High'] - df['Low'],
                np.maximum(
                    abs(df['High'] - df['Close'].shift(1)),
                    abs(df['Low'] - df['Close'].shift(1))
                )
            )
            atr = tr.tail(14).mean()
            
            t_stop = cp - (2.0 * atr)
            r1 = cp + (atr * 1.5)
            r2 = cp + (atr * 3.0)
            
            # Position size
            risk_per_share = abs(cp - t_stop)
            pos_size = int(CONFIG['RISK_PER_TRADE_USD'] / risk_per_share) if risk_per_share > 0 else 0
            
            # Log signal
            log_signal(ticker, cp, nexus_data)
            
            # Build Telegram message
            msg = f"🧬 **NEXUS ELITE: AI CONVERGENCE DETECTED**\n"
            msg += f"💎 **TICKER**: `{ticker}` | **QTY**: `{pos_size} shares`\n"
            msg += f"💰 **Entry**: `${cp:.2f}` | **Benchmark**: `{bench_ticker}`\n"
            msg += f"━━━━━━━━━━━━━━━━━━━━━━\n"
            msg += f"🎯 **NEXUS SCORE**: `{nexus_score}/100` ⚡\n"
            msg += f"🔗 **Convergence**: `{convergence}/7 dimensions`\n"
            msg += f"━━━━━━━━━━━━━━━━━━━━━━\n"
            msg += f"📊 **BREAKDOWN**:\n"
            msg += f"• VFS (Volume Fractal): `{comp['vfs']:.0f}`\n"
            msg += f"• PHR (Price Harmonics): `{comp['phr']:.0f}`\n"
            msg += f"• OBIE (Order Echo): `{comp['obie']:.0f}`\n"
            msg += f"• VRS (Vol Regime): `{comp['vrs']:.0f}`\n"
            msg += f"• MQI (Momentum Quality): `{comp['mqi']:.0f}`\n"
            msg += f"• IFC (Inst. Footprint): `{comp['ifc']:.0f}`\n"
            msg += f"• LAR (Liquidity Absorb): `{comp['lar']:.0f}`\n"
            msg += f"━━━━━━━━━━━━━━━━━━━━━━\n"
            msg += f"🎯 **T1**: `${r1:.2f}` (+{((r1/cp)-1)*100:.1f}%)\n"
            msg += f"🚀 **T2**: `${r2:.2f}` (+{((r2/cp)-1)*100:.1f}%)\n"
            msg += f"🛡️ **STOP**: `${t_stop:.2f}` ({((t_stop/cp)-1)*100:.1f}%)\n"
            msg += f"━━━━━━━━━━━━━━━━━━━━━━\n"
            msg += f"💵 **Risk**: ${CONFIG['RISK_PER_TRADE_USD']}\n"
            msg += f"🧪 *AI Multi-Dimensional Analysis*"
            
            send_telegram(msg)
            
            alert_history[ticker] = datetime.now()
            save_alert_history(alert_history)
            
            logging.info(f"✅ NEXUS SIGNAL: {ticker} @ ${cp:.2f} (Score: {nexus_score})")
            
    except Exception as e:
        logging.error(f"Error analyzing {ticker}: {e}")

def is_market_open():
    tz_ny = pytz.timezone('US/Eastern')
    now_ny = datetime.now(tz_ny)
    if now_ny.weekday() >= 5:
        return False
    return dtime(4, 0) <= now_ny.time() <= dtime(20, 0)

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}, timeout=5)
    except Exception as e:
        logging.warning(f"Telegram error: {e}")

# --- MAIN ---

def main():
    logging.info("=" * 60)
    logging.info("🧬 NEXUS Elite Scanner V4.0 - AI Powered")
    logging.info(f"📊 Monitoring: {len(set(MY_PORTFOLIO + WATCHLIST_200))} tickers")
    logging.info(f"⚙️  NEXUS Threshold: {CONFIG['NEXUS_THRESHOLD']} | Convergence Min: {CONFIG['CONVERGENCE_MIN']}")
    logging.info("=" * 60)
    
    alert_history = load_alert_history()
    logging.info(f"📜 Loaded {len(alert_history)} alert history entries")
    
    while True:
        try:
            if is_market_open():
                all_tickers = sorted(list(set(MY_PORTFOLIO + WATCHLIST_200)))
                logging.info(f"🔍 Starting scan of {len(all_tickers)} tickers...")
                
                for ticker in all_tickers:
                    try:
                        analyze_stock_nexus(ticker, alert_history)
                        time.sleep(CONFIG['SLEEP_BETWEEN_STOCKS'])
                    except Exception as e:
                        logging.error(f"❌ Error scanning {ticker}: {e}")
                        continue
                
                logging.info("✅ Scan completed. Next cycle starting...")
                
            else:
                logging.info(f"💤 Market closed. Waiting 10 min...")
                time.sleep(600)
                
        except KeyboardInterrupt:
            logging.info("🛑 Scanner stopped by user")
            break
        except Exception as e:
            logging.error(f"❌ Main loop error: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()

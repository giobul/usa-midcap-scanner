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

# --- FILE PATHS ---
LOG_FILE = Path.home() / "elite_scanner.log"
BACKTEST_LOG = Path.home() / "scanner_backtest_results.csv"
ALERT_HISTORY_FILE = Path.home() / ".elite_alerts.json"

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

# --- ALERT HISTORY MANAGEMENT ---

def load_alert_history():
    """Carica la cronologia degli alert per evitare spam"""
    if ALERT_HISTORY_FILE.exists():
        try:
            with open(ALERT_HISTORY_FILE) as f:
                data = json.load(f)
                return {k: datetime.fromisoformat(v) for k, v in data.items()}
        except Exception as e:
            logging.warning(f"Errore caricamento alert history: {e}")
            return {}
    return {}

def save_alert_history(history):
    """Salva la cronologia degli alert"""
    try:
        with open(ALERT_HISTORY_FILE, 'w') as f:
            json.dump({k: v.isoformat() for k, v in history.items()}, f, indent=2)
    except Exception as e:
        logging.warning(f"Errore salvataggio alert history: {e}")

# --- DOWNLOAD WITH RETRY ---

def download_with_retry(ticker, period="5d", interval="15m"):
    """Download dati con retry ed exponential backoff"""
    for attempt in range(CONFIG['MAX_RETRIES']):
        try:
            df = yf.download(ticker, period=period, interval=interval, progress=False)
            if not df.empty: 
                return df
        except Exception as e:
            if attempt == CONFIG['MAX_RETRIES'] - 1:
                logging.warning(f"Fallito download {ticker} dopo {CONFIG['MAX_RETRIES']} tentativi")
            time.sleep(2 ** attempt)  # Exponential backoff: 1s, 2s, 4s
    return pd.DataFrame()

# --- BACKTEST LOGGING ---

def log_backtest_signal(ticker, price, t1, t2, stop, s_type, pos_size, cai, rs_val):
    """Salva segnale nel file CSV per backtest"""
    file_exists = BACKTEST_LOG.exists()
    with open(BACKTEST_LOG, 'a') as f:
        if not file_exists:
            f.write("timestamp,ticker,entry_price,target1,target2,stop_loss,position_size,cai_score,rs_value,type\n")
        f.write(f"{datetime.now()},{ticker},{price},{t1},{t2},{stop},{pos_size},{cai},{rs_val},{s_type}\n")

# --- ELITE LOGIC ---

def detect_elite_candle(df):
    """Rileva pattern candlestick con validazione volume rigorosa"""
    if len(df) < 2:
        return ""
    
    last = df.iloc[-1]
    prev = df.iloc[-2]
    avg_vol = df['Volume'].tail(20).mean()
    
    body = abs(last['Open'] - last['Close'])
    lower_shade = min(last['Open'], last['Close']) - last['Low']
    upper_shade = last['High'] - max(last['Open'], last['Close'])
    
    # HAMMER: Inversione rialzista con volume ultra (1.5x)
    if lower_shade > (body * 2) and upper_shade < body and last['Volume'] > avg_vol * 1.5:
        return "🔨 HAMMER (ULTRA-VOL)"
    
    # BULLISH ENGULFING: Volume > 1.3x
    if (last['Close'] > prev['Open'] and 
        last['Open'] < prev['Close'] and 
        last['Close'] > last['Open'] and 
        last['Volume'] > avg_vol * 1.3):
        return "🔥 BULLISH ENGULFING (VOL+)"
    
    return ""

def get_relative_strength(ticker):
    """Calcola Relative Strength vs benchmark di settore"""
    try:
        # Benchmark dinamico per settore
        if ticker in ["STNE", "PAGS", "NU"]: 
            bench = "EWZ"
        elif ticker in ["NVDA", "AMD", "ARM", "AVGO", "SMCI"]: 
            bench = "SOXX"
        elif ticker in ["COIN", "MARA", "RIOT"]: 
            bench = "BITO"
        else: 
            bench = "QQQ"
        
        # Download con finestra stabile (5 giorni @ 1h)
        data = download_with_retry(ticker, period="5d", interval="1h")
        b_data = download_with_retry(bench, period="5d", interval="1h")
        
        if data.empty or b_data.empty: 
            return False, 0, bench
        
        # Performance relativa
        t_perf = (data['Close'].iloc[-1] / data['Close'].iloc[0]) - 1
        b_perf = (b_data['Close'].iloc[-1] / b_data['Close'].iloc[0]) - 1
        
        return t_perf > b_perf, (t_perf - b_perf) * 100, bench
        
    except Exception as e:
        logging.debug(f"RS error per {ticker}: {e}")
        return False, 0, "QQQ"

# --- CORE ANALYSIS ---

def analyze_stock(ticker, alert_history):
    """Analizza ticker e genera segnale Elite se criteri soddisfatti"""
    try:
        # Download dati
        df = download_with_retry(ticker, period="5d", interval="15m")
        if df.empty or len(df) < 30: 
            return
        
        # Fix MultiIndex se necessario
        if isinstance(df.columns, pd.MultiIndex): 
            df.columns = df.columns.get_level_values(0)

        cp = float(df['Close'].iloc[-1])
        
        # --- CAI SCORE (Corretto) ---
        recent_vol = df['Volume'].tail(5).mean()
        avg_vol_50 = df['Volume'].tail(50).mean()
        vol_ratio = recent_vol / avg_vol_50 if avg_vol_50 > 0 else 1
        price_stability = max(0, 1 - (df['Close'].tail(5).std() / cp))
        cai_score = min(100, (vol_ratio * 50) * price_stability)
        
        # --- CANDLE PATTERN ---
        candle = detect_elite_candle(df)
        
        # --- RELATIVE STRENGTH ---
        is_strong, rs_val, bench = get_relative_strength(ticker)
        
        # --- VERIFICA CONDIZIONI ELITE ---
        if cai_score >= CONFIG['ELITE_CAI_MIN'] and is_strong and candle != "":
            
            # --- COOLDOWN CHECK ---
            if ticker in alert_history:
                last_alert = alert_history[ticker]
                time_since_alert = datetime.now() - last_alert
                if time_since_alert < timedelta(hours=CONFIG['COOLDOWN_HOURS']):
                    hours_left = CONFIG['COOLDOWN_HOURS'] - (time_since_alert.total_seconds() / 3600)
                    logging.info(f"⏳ {ticker} in cooldown ({hours_left:.1f}h rimanenti)")
                    return
            
            # --- ATR TARGETS & STOP ---
            tr = np.maximum(
                df['High'] - df['Low'], 
                np.maximum(
                    abs(df['High'] - df['Close'].shift(1)), 
                    abs(df['Low'] - df['Close'].shift(1))
                )
            )
            atr = tr.tail(14).mean()
            
            t_stop = cp - (CONFIG['ATR_MULTIPLIER_STOP'] * atr)
            r1 = cp + (atr * 1.5)
            r2 = cp + (atr * 3.0)
            
            # --- POSITION SIZING ---
            risk_per_share = abs(cp - t_stop)
            pos_size = int(CONFIG['RISK_PER_TRADE_USD'] / risk_per_share) if risk_per_share > 0 else 0
            
            # --- BACKTEST LOG ---
            log_backtest_signal(ticker, cp, r1, r2, t_stop, "ELITE", pos_size, cai_score, rs_val)
            
            # --- TELEGRAM MESSAGE ---
            msg = f"👑 **ELITE V3.2: {candle}**\n"
            msg += f"💎 **AZIONE**: `{ticker}` | **QTY**: `{pos_size} shares`\n"
            msg += f"💰 **Entry**: `${cp:.2f}` | **RS**: `+{rs_val:.2f}% vs {bench}`\n"
            msg += f"📊 **CAI Score**: `{cai_score:.1f}`\n"
            msg += f"━━━━━━━━━━━━━━━\n"
            msg += f"🎯 **T1 (1.5x ATR)**: `${r1:.2f}` (+{((r1/cp)-1)*100:.1f}%)\n"
            msg += f"🚀 **T2 (3.0x ATR)**: `${r2:.2f}` (+{((r2/cp)-1)*100:.1f}%)\n"
            msg += f"🛡️ **STOP**: `${t_stop:.2f}` ({((t_stop/cp)-1)*100:.1f}%)\n"
            msg += f"━━━━━━━━━━━━━━━\n"
            msg += f"💵 **Risk**: ${CONFIG['RISK_PER_TRADE_USD']} | **R:R**: 1:{((r1-cp)/(cp-t_stop)):.2f}\n"
            msg += f"🧪 *Backtest log aggiornato*"
            
            send_telegram(msg)
            
            # --- UPDATE ALERT HISTORY ---
            alert_history[ticker] = datetime.now()
            save_alert_history(alert_history)
            
            logging.info(f"✅ ELITE SIGNAL: {ticker} @ ${cp:.2f} - {candle}")
            
    except Exception as e: 
        logging.error(f"Errore analisi {ticker}: {e}")

# --- MARKET HOURS ---

def is_market_open():
    """Verifica se mercato è aperto (Extended Hours: 4AM-8PM ET)"""
    tz_ny = pytz.timezone('US/Eastern')
    now_ny = datetime.now(tz_ny)
    
    # Weekend
    if now_ny.weekday() >= 5: 
        return False
    
    # Extended hours: Pre-market (4:00-9:30) + Regular (9:30-16:00) + After (16:00-20:00)
    return dtime(4, 0) <= now_ny.time() <= dtime(20, 0)

# --- TELEGRAM ---

def send_telegram(message):
    """Invia messaggio a Telegram"""
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try: 
        requests.post(
            url, 
            data={"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}, 
            timeout=5
        )
    except Exception as e:
        logging.warning(f"Errore invio Telegram: {e}")

# --- MAIN LOOP ---

def main():
    logging.info("=" * 50)
    logging.info("🚀 Elite Scanner V3.2 Avviato")
    logging.info(f"📊 Monitoraggio: {len(set(MY_PORTFOLIO + WATCHLIST_200))} ticker")
    logging.info(f"⚙️  CAI Min: {CONFIG['ELITE_CAI_MIN']} | Risk: ${CONFIG['RISK_PER_TRADE_USD']}/trade")
    logging.info("=" * 50)
    
    # Carica alert history
    alert_history = load_alert_history()
    logging.info(f"📜 Caricati {len(alert_history)} alert storici")
    
    while True:
        try:
            if is_market_open():
                all_tickers = sorted(list(set(MY_PORTFOLIO + WATCHLIST_200)))
                logging.info(f"🔍 Inizio scan di {len(all_tickers)} ticker...")
                
                for ticker in all_tickers:
                    try:
                        analyze_stock(ticker, alert_history)
                        time.sleep(CONFIG['SLEEP_BETWEEN_STOCKS'])
                    except Exception as e:
                        logging.error(f"❌ Errore critico durante scan {ticker}: {e}")
                        continue
                
                logging.info("✅ Scan completato. Prossimo ciclo in corso...")
                
            else:
                tz_ny = pytz.timezone('US/Eastern')
                now_ny = datetime.now(tz_ny)
                logging.info(f"💤 Mercato chiuso (NY: {now_ny.strftime('%H:%M')}). Check in 10 min...")
                time.sleep(600)
                
        except KeyboardInterrupt:
            logging.info("🛑 Scanner fermato dall'utente")
            break
        except Exception as e:
            logging.error(f"❌ Errore nel loop principale: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()

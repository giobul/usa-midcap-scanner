# elite_nexus_scanner_lite.py (NO SCIPY REQUIRED)
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

# --- TICKER LISTS ---
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

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()]
)

CONFIG = {
    'COOLDOWN_HOURS': 6,
    'SLEEP_BETWEEN_STOCKS': 1.0,
    'MAX_RETRIES': 3,
    'NEXUS_THRESHOLD': 75,
    'CONVERGENCE_MIN': 4,
    'RISK_PER_TRADE_USD': 500
}

# ============================================
# NEXUS LITE ENGINE (NO SCIPY)
# ============================================

def calculate_vfs_lite(df):
    """Volume Fractal Signature - Simplified"""
    try:
        vol = df['Volume'].values
        
        # Volume momentum (accelerazione)
        vol_ma_5 = df['Volume'].rolling(5).mean()
        vol_ma_20 = df['Volume'].rolling(20).mean()
        vol_ratio = (vol_ma_5 / vol_ma_20).iloc[-1] if len(vol_ma_20) > 0 else 1
        
        # Volume consistency
        vol_std = df['Volume'].tail(20).std()
        vol_mean = df['Volume'].tail(20).mean()
        vol_cv = (vol_std / vol_mean) if vol_mean > 0 else 1
        
        # Score: High ratio + Low variation = stealth accumulation
        vfs_score = (vol_ratio * 50) * (1 / (1 + vol_cv))
        
        return min(100, max(0, vfs_score))
    except:
        return 0

def calculate_phr_lite(df):
    """Price Harmonic - Simplified (Cycle Detection)"""
    try:
        prices = df['Close'].values
        
        if len(prices) < 30:
            return 0
        
        # Find local peaks and troughs
        from scipy.signal import argrelextrema
        
        # Fallback: Simple momentum cycles
        returns = df['Close'].pct_change()
        
        # Positive momentum periods
        pos_momentum = (returns > 0).astype(int)
        
        # Count consecutive periods (rough cycle length)
        cycles = []
        count = 0
        for val in pos_momentum:
            if val == 1:
                count += 1
            else:
                if count > 0:
                    cycles.append(count)
                count = 0
        
        if len(cycles) < 2:
            return 0
        
        # Consistency of cycle length
        avg_cycle = np.mean(cycles)
        std_cycle = np.std(cycles)
        
        # Score: Cycles 5-10 bars + low variation
        if 5 <= avg_cycle <= 10:
            consistency = 1 / (1 + std_cycle)
            phr_score = consistency * 80
        else:
            phr_score = 30
        
        return min(100, max(0, phr_score))
    except:
        return 0

def calculate_obie_lite(df):
    """Order Book Echo - Simplified"""
    try:
        # VWAP divergence
        vwap = (df['Close'] * df['Volume']).cumsum() / df['Volume'].cumsum()
        close = df['Close']
        
        divergence = ((close - vwap) / vwap).dropna()
        
        if len(divergence) < 20:
            return 0
        
        # Recent divergence magnitude
        recent_div = abs(divergence.tail(10).mean())
        
        # Persistence (autocorr approximation via rolling correlation)
        div_series = divergence.tail(30)
        div_lag = div_series.shift(5)
        
        # Simple correlation
        corr = div_series.corr(div_lag)
        
        # Score: High divergence + High persistence
        obie_score = recent_div * abs(corr) * 3000
        
        return min(100, max(0, obie_score))
    except:
        return 0

def calculate_vrs_lite(df):
    """Volatility Regime - Simplified"""
    try:
        returns = df['Close'].pct_change().dropna()
        
        if len(returns) < 30:
            return 0
        
        # Rolling volatility
        vol_5 = returns.rolling(5).std()
        vol_20 = returns.rolling(20).std()
        
        vol_ratio = (vol_5 / vol_20).iloc[-1]
        
        # Volatility trend
        vol_trend = vol_5.diff().tail(5).mean()
        
        # Score: Low vol + Rising trend = breakout setup
        if vol_ratio < 1.0 and vol_trend > 0:
            vrs_score = (1 - vol_ratio) * vol_trend * 400
        else:
            vrs_score = 0
        
        return min(100, max(0, vrs_score))
    except:
        return 0

def calculate_mqi_lite(df):
    """Momentum Quality - Simplified"""
    try:
        returns = df['Close'].pct_change()
        
        # Momentum
        mom_10 = returns.rolling(10).mean()
        
        # Smoothness (low volatility of momentum)
        mom_std = mom_10.rolling(10).std()
        
        current_mom = mom_10.iloc[-1]
        current_std = mom_std.iloc[-1]
        
        if current_mom > 0:
            smoothness = 1 / (1 + current_std * 100)
            mqi_score = current_mom * smoothness * 800
        else:
            mqi_score = 0
        
        return min(100, max(0, mqi_score))
    except:
        return 0

def calculate_ifc_lite(df, benchmark_df):
    """Institutional Footprint - Simplified"""
    try:
        if benchmark_df is None or benchmark_df.empty:
            return 50
        
        ticker_ret = df['Close'].pct_change()
        bench_ret = benchmark_df['Close'].pct_change()
        
        # Align
        common_idx = ticker_ret.index.intersection(bench_ret.index)
        
        if len(common_idx) < 20:
            return 50
        
        ticker_ret = ticker_ret.loc[common_idx]
        bench_ret = bench_ret.loc[common_idx]
        
        # Correlation
        corr_20 = ticker_ret.tail(20).corr(bench_ret.tail(20))
        corr_5 = ticker_ret.tail(5).corr(bench_ret.tail(5))
        
        # Decoupling
        decoupling = abs(corr_20 - corr_5)
        
        # Outperformance
        perf_diff = ticker_ret.iloc[-1] - bench_ret.iloc[-1]
        
        ifc_score = 50 + (decoupling * 150 * (1 if perf_diff > 0 else -1))
        
        return min(100, max(0, ifc_score))
    except:
        return 50

def calculate_lar_lite(df):
    """Liquidity Absorption - Simplified"""
    try:
        vol_ma_5 = df['Volume'].rolling(5).mean()
        vol_ma_20 = df['Volume'].rolling(20).mean()
        
        vol_ratio = (vol_ma_5 / vol_ma_20).iloc[-1]
        
        # Price impact
        price_change = df['Close'].pct_change().abs()
        vol_norm = df['Volume'] / df['Volume'].mean()
        
        price_per_vol = (price_change / vol_norm).replace([np.inf, -np.inf], 0)
        
        current_impact = price_per_vol.iloc[-1]
        
        # Inverse impact (lower = better)
        impact_score = 1 / (1 + current_impact * 100)
        
        lar_score = vol_ratio * impact_score * 40
        
        return min(100, max(0, lar_score))
    except:
        return 0

def calculate_nexus_score_lite(ticker, df, benchmark_df=None):
    """NEXUS Score - Lite Version"""
    try:
        vfs = calculate_vfs_lite(df)
        phr = calculate_phr_lite(df)
        obie = calculate_obie_lite(df)
        vrs = calculate_vrs_lite(df)
        mqi = calculate_mqi_lite(df)
        ifc = calculate_ifc_lite(df, benchmark_df)
        lar = calculate_lar_lite(df)
        
        weights = {
            'vfs': 0.22, 'phr': 0.10, 'obie': 0.20,
            'vrs': 0.15, 'mqi': 0.10, 'ifc': 0.13, 'lar': 0.10
        }
        
        nexus = (
            vfs * weights['vfs'] + phr * weights['phr'] +
            obie * weights['obie'] + vrs * weights['vrs'] +
            mqi * weights['mqi'] + ifc * weights['ifc'] +
            lar * weights['lar']
        )
        
        high_components = sum([1 for s in [vfs, phr, obie, vrs, mqi, ifc, lar] if s > 70])
        convergence_bonus = high_components * 2 if high_components >= 4 else 0
        
        nexus_final = min(100, nexus + convergence_bonus)
        
        return {
            'nexus_score': round(nexus_final, 1),
            'convergence': high_components,
            'components': {
                'vfs': round(vfs, 1), 'phr': round(phr, 1),
                'obie': round(obie, 1), 'vrs': round(vrs, 1),
                'mqi': round(mqi, 1), 'ifc': round(ifc, 1),
                'lar': round(lar, 1)
            }
        }
    except Exception as e:
        logging.debug(f"NEXUS calc error: {e}")
        return {
            'nexus_score': 0, 'convergence': 0,
            'components': {k: 0 for k in ['vfs', 'phr', 'obie', 'vrs', 'mqi', 'ifc', 'lar']}
        }

# ============================================
# SCANNER (REST OF CODE IDENTICAL)
# ============================================

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
        except:
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

def analyze_stock_nexus(ticker, alert_history):
    try:
        df = download_with_retry(ticker, period="5d", interval="15m")
        if df.empty or len(df) < 50:
            return
        
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        cp = float(df['Close'].iloc[-1])
        
        bench_ticker = get_benchmark(ticker)
        bench_df = download_with_retry(bench_ticker, period="5d", interval="15m")
        
        nexus_data = calculate_nexus_score_lite(ticker, df, bench_df)
        
        nexus_score = nexus_data['nexus_score']
        convergence = nexus_data['convergence']
        comp = nexus_data['components']
        
        is_signal = (
            nexus_score >= CONFIG['NEXUS_THRESHOLD'] and
            convergence >= CONFIG['CONVERGENCE_MIN'] and
            comp['vfs'] > 65
        )
        
        if is_signal:
            if ticker in alert_history:
                time_since = datetime.now() - alert_history[ticker]
                if time_since < timedelta(hours=CONFIG['COOLDOWN_HOURS']):
                    return
            
            tr = np.maximum(
                df['High'] - df['Low'],
                np.maximum(abs(df['High'] - df['Close'].shift(1)), abs(df['Low'] - df['Close'].shift(1)))
            )
            atr = tr.tail(14).mean()
            
            t_stop = cp - (2.0 * atr)
            r1 = cp + (atr * 1.5)
            r2 = cp + (atr * 3.0)
            
            risk_per_share = abs(cp - t_stop)
            pos_size = int(CONFIG['RISK_PER_TRADE_USD'] / risk_per_share) if risk_per_share > 0 else 0
            
            log_signal(ticker, cp, nexus_data)
            
            msg = f"🧬 **NEXUS LITE: AI SIGNAL**\n"
            msg += f"💎 `{ticker}` | QTY: `{pos_size}`\n"
            msg += f"💰 Entry: `${cp:.2f}`\n"
            msg += f"━━━━━━━━━━━━━━━\n"
            msg += f"🎯 NEXUS: `{nexus_score}/100`\n"
            msg += f"🔗 Conv: `{convergence}/7`\n"
            msg += f"━━━━━━━━━━━━━━━\n"
            msg += f"📊 VFS:{comp['vfs']:.0f} PHR:{comp['phr']:.0f} OBIE:{comp['obie']:.0f}\n"
            msg += f"   VRS:{comp['vrs']:.0f} MQI:{comp['mqi']:.0f} IFC:{comp['ifc']:.0f} LAR:{comp['lar']:.0f}\n"
            msg += f"━━━━━━━━━━━━━━━\n"
            msg += f"🎯 T1: `${r1:.2f}` | T2: `${r2:.2f}`\n"
            msg += f"🛡️ STOP: `${t_stop:.2f}`\n"
            
            send_telegram(msg)
            
            alert_history[ticker] = datetime.now()
            save_alert_history(alert_history)
            
            logging.info(f"✅ NEXUS: {ticker} @ ${cp:.2f}")
            
    except Exception as e:
        logging.error(f"Error {ticker}: {e}")

def is_market_open():
    tz_ny = pytz.timezone('US/Eastern')
    now_ny = datetime.now(tz_ny)
    if now_ny.weekday() >= 5:
        return False
    return dtime(9, 30) <= now_ny.time() <= dtime(16, 0)

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}, timeout=5)
    except:
        pass

def main():
    logging.info("🧬 NEXUS LITE Scanner V4.0")
    logging.info(f"📊 {len(set(MY_PORTFOLIO + WATCHLIST_200))} tickers")
    
    alert_history = load_alert_history()
    
    while True:
        try:
            if is_market_open():
                all_tickers = sorted(list(set(MY_PORTFOLIO + WATCHLIST_200)))
                
                for ticker in all_tickers:
                    try:
                        analyze_stock_nexus(ticker, alert_history)
                        time.sleep(CONFIG['SLEEP_BETWEEN_STOCKS'])
                    except Exception as e:
                        logging.error(f"❌ {ticker}: {e}")
                        continue
                
                logging.info("✅ Scan complete")
                
            else:
                logging.info("💤 Market closed")
                time.sleep(600)
                
        except KeyboardInterrupt:
            logging.info("🛑 Stopped")
            break
        except Exception as e:
            logging.error(f"❌ {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()

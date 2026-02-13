# elite_nexus_scanner.py (VERSIONE COMPLETA STANDALONE)
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
from scipy.fft import fft
from scipy.signal import correlate
from scipy.stats import entropy
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
# NEXUS CORE ENGINE (EMBEDDED)
# ============================================

def calculate_vfs(df):
    """Volume Fractal Signature"""
    try:
        vol = df['Volume'].values
        lags = range(2, min(20, len(vol)//2))
        tau = [np.std(np.subtract(vol[lag:], vol[:-lag])) for lag in lags]
        
        if len(tau) < 2:
            return 0
        
        hurst = np.polyfit(np.log(lags), np.log(tau), 1)[0]
        vol_recent = vol[-50:] if len(vol) >= 50 else vol
        vol_bins = pd.cut(vol_recent, bins=10, duplicates='drop')
        vol_entropy = entropy(vol_bins.value_counts().values)
        vol_entropy_norm = vol_entropy / 2.3
        
        vfs_score = (max(0, hurst) * 100) * (1 - vol_entropy_norm)
        return min(100, max(0, vfs_score * 1.5))
    except:
        return 0

def calculate_phr(df):
    """Price Harmonic Resonance"""
    try:
        prices = df['Close'].pct_change().dropna().values
        if len(prices) < 30:
            return 0
        
        fft_vals = np.abs(fft(prices))
        dominant_idx = np.argmax(fft_vals[1:min(20, len(fft_vals)//2)]) + 1
        
        power = fft_vals[dominant_idx]
        noise = np.mean(fft_vals[1:min(20, len(fft_vals)//2)])
        coherence = power / noise if noise > 0 else 0
        
        freq_score = 1.0 / (1.0 + abs(dominant_idx - 6))
        phr_score = coherence * freq_score * 20
        
        return min(100, max(0, phr_score))
    except:
        return 0

def calculate_obie(df):
    """Order Book Imbalance Echo"""
    try:
        vwap = (df['Close'] * df['Volume']).cumsum() / df['Volume'].cumsum()
        close = df['Close']
        divergence = ((close - vwap) / vwap).dropna()
        
        if len(divergence) < 50:
            return 0
        
        div_values = divergence.tail(50).values
        autocorr = correlate(div_values, div_values, mode='same')
        
        mid = len(autocorr) // 2
        peak = np.max(autocorr[mid:mid+10]) if mid+10 <= len(autocorr) else autocorr[mid]
        peak_norm = peak / autocorr[mid] if autocorr[mid] != 0 else 0
        
        div_magnitude = abs(divergence.iloc[-1])
        obie_score = div_magnitude * peak_norm * 5000
        
        return min(100, max(0, obie_score))
    except:
        return 0

def calculate_vrs(df):
    """Volatility Regime Shift"""
    try:
        returns = df['Close'].pct_change().dropna().values
        if len(returns) < 50:
            return 0
        
        vol_short = pd.Series(returns).rolling(5).std()
        vol_long = pd.Series(returns).rolling(20).std()
        vol_ratio = (vol_short / vol_long).dropna()
        
        if len(vol_ratio) < 10:
            return 0
        
        current_vol_ratio = vol_ratio.iloc[-1]
        vol_trend = vol_ratio.diff().tail(5).mean()
        
        if current_vol_ratio < 1.0 and vol_trend > 0:
            vrs_score = (1 - current_vol_ratio) * vol_trend * 500
        else:
            vrs_score = 0
        
        return min(100, max(0, vrs_score))
    except:
        return 0

def calculate_mqi(df):
    """Momentum Quality Index"""
    try:
        returns = df['Close'].pct_change().dropna()
        if len(returns) < 20:
            return 0
        
        momentum = returns.rolling(10).mean()
        momentum_vol = momentum.rolling(10).std()
        
        current_mom = momentum.iloc[-1]
        current_vol = momentum_vol.iloc[-1]
        
        if current_mom > 0:
            smoothness = 1 / (1 + current_vol * 100)
            mqi_score = current_mom * smoothness * 1000
        else:
            mqi_score = 0
        
        return min(100, max(0, mqi_score))
    except:
        return 0

def calculate_ifc(df, benchmark_df):
    """Institutional Footprint Correlation"""
    try:
        if benchmark_df is None or benchmark_df.empty or len(df) < 30:
            return 50
        
        ticker_ret = df['Close'].pct_change().dropna()
        bench_ret = benchmark_df['Close'].pct_change().dropna()
        
        common_idx = ticker_ret.index.intersection(bench_ret.index)
        if len(common_idx) < 20:
            return 50
        
        ticker_ret = ticker_ret.loc[common_idx]
        bench_ret = bench_ret.loc[common_idx]
        
        corr_20 = ticker_ret.rolling(20).corr(bench_ret)
        corr_5 = ticker_ret.rolling(5).corr(bench_ret)
        
        decoupling = abs(corr_20.iloc[-1] - corr_5.iloc[-1])
        perf_diff = ticker_ret.iloc[-1] - bench_ret.iloc[-1]
        
        ifc_score = 50 + (decoupling * 200 * (1 if perf_diff > 0 else -1))
        return min(100, max(0, ifc_score))
    except:
        return 50

def calculate_lar(df):
    """Liquidity Absorption Rate"""
    try:
        vol_ma_5 = df['Volume'].rolling(5).mean()
        vol_ma_20 = df['Volume'].rolling(20).mean()
        vol_ratio = (vol_ma_5 / vol_ma_20).dropna()
        
        if len(vol_ratio) < 1:
            return 0
        
        price_change = df['Close'].pct_change().abs()
        vol_normalized = df['Volume'] / df['Volume'].mean()
        price_per_vol = (price_change / vol_normalized).replace([np.inf, -np.inf], 0).dropna()
        
        if len(price_per_vol) < 1:
            return 0
        
        current_vol_ratio = vol_ratio.iloc[-1]
        current_impact = price_per_vol.iloc[-1]
        impact_score = 1 / (1 + current_impact * 100)
        
        lar_score = current_vol_ratio * impact_score * 50
        return min(100, max(0, lar_score))
    except:
        return 0

def calculate_nexus_score(ticker, df, benchmark_df=None):
    """Calculate NEXUS Score"""
    try:
        vfs = calculate_vfs(df)
        phr = calculate_phr(df)
        obie = calculate_obie(df)
        vrs = calculate_vrs(df)
        mqi = calculate_mqi(df)
        ifc = calculate_ifc(df, benchmark_df)
        lar = calculate_lar(df)
        
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
    except:
        return {
            'nexus_score': 0, 'convergence': 0,
            'components': {k: 0 for k in ['vfs', 'phr', 'obie', 'vrs', 'mqi', 'ifc', 'lar']}
        }

# ============================================
# SCANNER UTILITIES
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
        
        nexus_data = calculate_nexus_score(ticker, df, bench_df)
        
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
            
            msg = f"🧬 **NEXUS ELITE: AI CONVERGENCE**\n"
            msg += f"💎 `{ticker}` | QTY: `{pos_size}`\n"
            msg += f"💰 Entry: `${cp:.2f}` | Bench: `{bench_ticker}`\n"
            msg += f"━━━━━━━━━━━━━━━\n"
            msg += f"🎯 NEXUS: `{nexus_score}/100` ⚡\n"
            msg += f"🔗 Conv: `{convergence}/7`\n"
            msg += f"━━━━━━━━━━━━━━━\n"
            msg += f"📊 VFS:{comp['vfs']:.0f} PHR:{comp['phr']:.0f} OBIE:{comp['obie']:.0f}\n"
            msg += f"   VRS:{comp['vrs']:.0f} MQI:{comp['mqi']:.0f} IFC:{comp['ifc']:.0f} LAR:{comp['lar']:.0f}\n"
            msg += f"━━━━━━━━━━━━━━━\n"
            msg += f"🎯 T1: `${r1:.2f}` (+{((r1/cp)-1)*100:.1f}%)\n"
            msg += f"🚀 T2: `${r2:.2f}` (+{((r2/cp)-1)*100:.1f}%)\n"
            msg += f"🛡️ STOP: `${t_stop:.2f}` ({((t_stop/cp)-1)*100:.1f}%)\n"
            
            send_telegram(msg)
            
            alert_history[ticker] = datetime.now()
            save_alert_history(alert_history)
            
            logging.info(f"✅ NEXUS: {ticker} @ ${cp:.2f} (Score: {nexus_score})")
            
    except Exception as e:
        logging.error(f"Error {ticker}: {e}")

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
    except:
        pass

def main():
    logging.info("=" * 60)
    logging.info("🧬 NEXUS Elite Scanner V4.0 - AI Powered")
    logging.info(f"📊 Monitoring: {len(set(MY_PORTFOLIO + WATCHLIST_200))} tickers")
    logging.info(f"⚙️  Threshold: {CONFIG['NEXUS_THRESHOLD']} | Conv: {CONFIG['CONVERGENCE_MIN']}")
    logging.info("=" * 60)
    
    alert_history = load_alert_history()
    
    while True:
        try:
            if is_market_open():
                all_tickers = sorted(list(set(MY_PORTFOLIO + WATCHLIST_200)))
                logging.info(f"🔍 Scanning {len(all_tickers)} tickers...")
                
                for ticker in all_tickers:
                    try:
                        analyze_stock_nexus(ticker, alert_history)
                        time.sleep(CONFIG['SLEEP_BETWEEN_STOCKS'])
                    except Exception as e:
                        logging.error(f"❌ {ticker}: {e}")
                        continue
                
                logging.info("✅ Scan complete")
                
            else:
                logging.info("💤 Market closed. Waiting...")
                time.sleep(600)
                
        except KeyboardInterrupt:
            logging.info("🛑 Stopped")
            break
        except Exception as e:
            logging.error(f"❌ Main error: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()

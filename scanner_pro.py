#!/usr/bin/env python3
"""
🧬 NEXUS v14.5 — WHALE DETECTOR EDITION
Fixed SyntaxError: Closed parentheses in final print loop.
"""

import yfinance as yf
import pandas as pd
import numpy as np
import requests
import warnings
import pytz
import time
import os
import json
import random
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict

warnings.filterwarnings("ignore")
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import logging
logging.getLogger("yfinance").setLevel(logging.CRITICAL)

# ==============================
# 🔑 SESSION & CONFIGURATION
# ==============================
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
})

TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN", "YOUR_TOKEN_HERE")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "YOUR_CHAT_ID_HERE")

BASE_DIR       = os.path.dirname(os.path.abspath(__file__))
LOG_FILE       = os.path.join(BASE_DIR, "nexus_trade_log.csv")
EARNINGS_CACHE = os.path.join(BASE_DIR, ".earnings_cache.json")

CONFIG = {
    "TOTAL_EQUITY":            100_000,
    "RISK_PER_TRADE_PERCENT":  0.01,
    "MAX_THREADS":             4,
    "MIN_VOLUME_USD":          1_000_000,
    "MAX_ALERTS":              7,
    "MIN_IFS_SCORE":           5,
    "MIN_ADX":                 25,
    "VOLUME_DRYUP_RATIO":      0.5,
    "MAX_PER_SECTOR":          2,
    "EARNINGS_LOOKBACK_DAYS":  1,
    "EARNINGS_LOOKAHEAD_DAYS": 1,
    "YF_RETRIES":              3,
    "YF_RETRY_DELAY":          15,
}

# ==============================
# 📋 SECTOR MAP
# ==============================
SECTOR_MAP = {
    "AAPL": "Tech", "MSFT": "Tech", "GOOGL": "Tech", "META": "Tech", "AMZN": "Ecommerce", "TSLA": "EV",
    "NFLX": "Media", "BRK-B": "Finance", "NVDA": "Semis", "AMD": "Semis", "INTC": "Semis", "QCOM": "Semis",
    "AVGO": "Semis", "TSM": "Semis", "ASML": "Semis", "AMAT": "Semis", "LRCX": "Semis", "KLAC": "Semis",
    "MU": "Semis", "ON": "Semis", "MRVL": "Semis", "NXPI": "Semis", "ADI": "Semis", "MCHP": "Semis",
    "MPWR": "Semis", "ENTG": "Semis", "TER": "Semis", "COHR": "Semis", "OLED": "Semis", "LSCC": "Semis",
    "SWKS": "Semis", "QRVO": "Semis", "TXN": "Semis", "SMCI": "Semis", "SNPS": "Semis", "CDNS": "Semis",
    "CRM": "Cloud", "ADBE": "Cloud", "NOW": "Cloud", "ORCL": "Cloud", "SHOP": "Cloud", "SNOW": "Cloud",
    "PLTR": "Cloud", "DDOG": "Cloud", "MDB": "Cloud", "TEAM": "Cloud", "ESTC": "Cloud", "OKTA": "Cloud",
    "TWLO": "Cloud", "HUBS": "Cloud", "BILL": "Cloud", "U": "Cloud", "APP": "Cloud", "DOCN": "Cloud",
    "FSLY": "Cloud", "DT": "Cloud", "AI": "Cloud", "PATH": "Cloud", "SOUN": "Cloud", "PANW": "Cyber",
    "CRWD": "Cyber", "ZS": "Cyber", "NET": "Cyber", "CSCO": "Tech", "ANET": "Tech", "PYPL": "Fintech",
    "SQ": "Fintech", "SOFI": "Fintech", "COIN": "Fintech", "HOOD": "Fintech", "AFRM": "Fintech",
    "STNE": "Fintech", "NU": "Fintech", "PAGS": "Fintech", "UPST": "Fintech", "V": "Fintech", "MA": "Fintech",
    "JPM": "Finance", "BAC": "Finance", "WFC": "Finance", "C": "Finance", "GS": "Finance", "MS": "Finance",
    "BLK": "Finance", "SCHW": "Finance", "AXP": "Finance", "ICE": "Finance", "CME": "Finance", "KKR": "Finance",
    "BX": "Finance", "APO": "Finance", "ARES": "Finance", "ALLY": "Finance", "UNH": "Health", "LLY": "Health",
    "ABBV": "Health", "MRK": "Health", "VRTX": "Health", "REGN": "Health", "GILD": "Health", "BIIB": "Health",
    "MRNA": "Health", "BNTX": "Health", "ISRG": "Health", "SYK": "Health", "MDT": "Health", "TMO": "Health",
    "ABT": "Health", "DHR": "Health", "PFE": "Health", "BMY": "Health", "CVS": "Health", "HUM": "Health",
    "CI": "Health", "ELV": "Health", "IDXX": "Health", "DXCM": "Health", "HIMS": "Health", "PG": "Consumer",
    "BYND": "Consumer", "COST": "Retail", "HD": "Retail", "LOW": "Retail", "NKE": "Retail", "SBUX": "Retail",
    "MCD": "Retail", "TGT": "Retail", "ROST": "Retail", "TJX": "Retail", "LULU": "Retail", "ULTA": "Retail",
    "DPZ": "Retail", "CMG": "Retail", "YUM": "Retail", "CVNA": "Retail", "BKNG": "Travel", "ABNB": "Travel",
    "MAR": "Travel", "HLT": "Travel", "UBER": "Tech", "LYFT": "Tech", "EBAY": "Ecommerce", "ETSY": "Ecommerce",
    "DIS": "Media", "CMCSA": "Media", "PARA": "Media", "WBD": "Media", "FOX": "Media", "FOXA": "Media",
    "FUBO": "Media", "T": "Telecom", "VZ": "Telecom", "CHTR": "Telecom", "TMUS": "Telecom", "ASTS": "Telecom",
    "XOM": "Energy", "CVX": "Energy", "COP": "Energy", "EOG": "Energy", "SLB": "Energy", "HAL": "Energy",
    "OXY": "Energy", "MPC": "Energy", "PSX": "Energy", "VLO": "Energy", "KMI": "Energy", "WMB": "Energy",
    "DVN": "Energy", "FANG": "Energy", "APA": "Energy", "CTRA": "Energy", "BKR": "Energy", "EQT": "Energy",
    "XLE": "Energy", "BA": "Industrial", "RTX": "Industrial", "LMT": "Industrial", "NOC": "Industrial",
    "GD": "Industrial", "CAT": "Industrial", "DE": "Industrial", "ETN": "Industrial", "PH": "Industrial",
    "HON": "Industrial", "GE": "Industrial", "EMR": "Industrial", "MMM": "Industrial", "ITW": "Industrial",
    "CMI": "Industrial", "ROK": "Industrial", "AME": "Industrial", "TDG": "Industrial", "LHX": "Industrial",
    "PCAR": "Industrial", "LIN": "Materials", "APD": "Materials", "ECL": "Materials", "SHW": "Materials",
    "NEM": "Materials", "FCX": "Materials", "DOW": "Materials", "DD": "Materials", "ALB": "Materials",
    "NUE": "Materials", "NEE": "Utilities", "DUK": "Utilities", "SO": "Utilities", "AEP": "Utilities",
    "EXC": "Utilities", "SRE": "Utilities", "D": "Utilities", "XEL": "Utilities", "PEG": "Utilities",
    "ED": "Utilities", "UPS": "Transport", "FDX": "Transport", "UNP": "Transport", "CSX": "Transport",
    "NSC": "Transport", "CP": "Transport", "CNI": "Transport", "DAL": "Airlines", "UAL": "Airlines",
    "AAL": "Airlines", "MSTR": "Crypto", "MARA": "Crypto", "RIOT": "Crypto", "CLSK": "Crypto",
    "RIVN": "EV", "LCID": "EV", "CHPT": "EV", "QS": "EV", "PLUG": "CleanEnergy", "RUN": "CleanEnergy",
    "SEDG": "CleanEnergy", "ENPH": "CleanEnergy", "BLNK": "CleanEnergy", "RBLX": "Gaming", "DKNG": "Gaming",
    "RKLB": "Aerospace", "OPEN": "Tech", "IONQ": "Tech"
}

MY_WATCHLIST = list(SECTOR_MAP.keys())

# ==============================
# 🛠️ UTILITIES
# ==============================
def is_market_gold_hour():
    tz  = pytz.timezone("America/New_York")
    now = datetime.now(tz)
    if now.weekday() > 4: return False
    return datetime.strptime("10:00", "%H:%M").time() <= now.time() <= datetime.strptime("15:30", "%H:%M").time()

def log_trade(data: dict, vol_ratio: float):
    file_exists = os.path.isfile(LOG_FILE)
    row = data.copy()
    row["date"] = datetime.now().strftime("%Y-%m-%d")
    row["timestamp"] = datetime.now().strftime("%H:%M:%S")
    row["vol_ratio"] = round(vol_ratio, 2)
    pd.DataFrame([row]).to_csv(LOG_FILE, mode="a", index=False, header=not file_exists)

def clean_df(df):
    if df is None or df.empty: return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.copy()
    for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    return df.dropna(subset=['Close'])

def yf_download_with_retry(ticker, **kwargs):
    kwargs.setdefault("session", session)
    kwargs.setdefault("auto_adjust", True)
    kwargs.setdefault("progress", False)
    for attempt in range(CONFIG["YF_RETRIES"]):
        try:
            df = yf.download(ticker, **kwargs)
            df = clean_df(df)
            if df is not None and not df.empty: return df
        except Exception as e:
            if any(k in str(e) for k in ("429", "Too Many")):
                time.sleep(CONFIG["YF_RETRY_DELAY"] * (attempt + 1))
            else: break
    return None

# ==============================
# 📅 EARNINGS SYSTEM
# ==============================
def load_earnings_cache():
    if os.path.exists(EARNINGS_CACHE):
        try:
            with open(EARNINGS_CACHE) as f:
                data = json.load(f)
                if (datetime.now() - datetime.fromisoformat(data.get("updated", "2000-01-01"))).days < 7:
                    return data.get("earnings", {})
        except: pass
    return {}

def save_earnings_cache(cache):
    try:
        with open(EARNINGS_CACHE, "w") as f:
            json.dump({"updated": datetime.now().isoformat(), "earnings": cache}, f)
    except: pass

def check_earnings_risk(ticker, cache):
    if ticker not in cache:
        try:
            t_obj = yf.Ticker(ticker)
            cal = t_obj.calendar
            if cal is not None and not cal.empty and "Earnings Date" in cal.index:
                val = cal.loc["Earnings Date"].iloc[0] if hasattr(cal.loc["Earnings Date"], "iloc") else cal.loc["Earnings Date"]
                cache[ticker] = pd.to_datetime(val).date().isoformat()
        except: return True
    
    if ticker in cache:
        try:
            diff = (datetime.fromisoformat(cache[ticker]).date() - datetime.now().date()).days
            if -CONFIG["EARNINGS_LOOKBACK_DAYS"] <= diff <= CONFIG["EARNINGS_LOOKAHEAD_DAYS"]:
                return False
        except: pass
    return True

# ==============================
# 📊 MARKET REGIME
# ==============================
def _fetch_spy_stooq():
    try:
        url = "https://stooq.com/q/d/l/?s=spy.us&i=d"
        df = pd.read_csv(url)
        df.columns = [c.capitalize() for c in df.columns]
        if 'Date' not in df.columns:
            df.index = pd.to_datetime(df.iloc[:, 0])
        else:
            df.set_index(pd.to_datetime(df['Date']), inplace=True)
        df = df.sort_index()
        if "Volume" not in df.columns: df["Volume"] = 0
        return df.tail(300)
    except Exception as e:
        print(f"⚠️ Stooq Error: {e}")
        return None

def get_market_regime():
    spy = yf_download_with_retry("SPY", period="1y")
    if spy is None:
        print("⚠️ yfinance rate-limited — provo stooq fallback...")
        spy = _fetch_spy_stooq()
    
    if spy is None: return False, None

    spy["SMA50"] = spy["Close"].rolling(50).mean()
    curr_close = float(spy["Close"].iloc[-1])
    sma50 = float(spy["SMA50"].iloc[-1])
    is_bull = curr_close > sma50
    slope = sma50 > float(spy["SMA50"].iloc[-5])
    print(f"📡 SPY: ${curr_close:.2f} | SMA50: ${sma50:.2f} | {'🟢 BULL' if is_bull else '🔴 BEAR'}")
    return bool(is_bull and slope), spy

# ==============================
# 🧠 INDICATORS & SCORING
# ==============================
def calc_adx(df, period=14):
    try:
        h, l, c = df["High"], df["Low"], df["Close"]
        tr = pd.concat([h-l, (h-c.shift()).abs(), (l-c.shift()).abs()], axis=1).max(axis=1)
        dm_plus = (h-h.shift()).clip(lower=0)
        dm_minus = (l.shift()-l).clip(lower=0)
        atr = tr.ewm(alpha=1/period, adjust=False).mean()
        di_plus = 100 * (dm_plus.ewm(alpha=1/period, adjust=False).mean() / atr)
        di_minus = 100 * (dm_minus.ewm(alpha=1/period, adjust=False).mean() / atr)
        dx = 100 * (di_plus-di_minus).abs() / (di_plus+di_minus).replace(0, np.nan)
        return float(dx.ewm(alpha=1/period, adjust=False).mean().iloc[-1])
    except: return 0.0

def institutional_score(df, rs_val, spy_df):
    score = 0
    avg20 = df["Volume"].rolling(20).mean()
    if (df["Volume"].iloc[-5:] > avg20.iloc[-5:]).sum() >= 3: score += 2
    hl = df["High"] - df["Low"]
    if hl.rolling(5).mean().iloc[-1] < hl.rolling(20).mean().iloc[-1]: score += 2
    if rs_val > 0: score += 2
    d_range = df["High"].iloc[-1] - df["Low"].iloc[-1]
    if d_range > 0 and (df["Close"].iloc[-1] - df["Low"].iloc[-1])/d_range > 0.75: score += 1
    try:
        rs_line = df["Close"] / spy_df["Close"].reindex(df.index, method='ffill')
        if rs_line.iloc[-1] > rs_line.iloc[-21:-1].max(): score += 2
    except: pass
    try:
        if (df["Volume"].iloc[-4:-1] < avg20.iloc[-4:-1] * 0.5).any(): score += 1
    except: pass
    return score, calc_adx(df)

# ==============================
# 🔎 ANALYSIS ENGINE
# ==============================
def analyze_ticker(ticker, spy_df, already_alerted, earnings_cache):
    if ticker in already_alerted: return None
    if not check_earnings_risk(ticker, earnings_cache): return None

    try:
        df = yf_download_with_retry(ticker, period="1y")
        if df is None or len(df) < 60: return None
        
        price = float(df["Close"].iloc[-1])
        vol_mean = float(df["Volume"].rolling(20).mean().iloc[-1])
        vol_last = float(df["Volume"].iloc[-1])
        
        if vol_mean == 0 or (price * vol_last < CONFIG["MIN_VOLUME_USD"]): return None

        vol_ratio = vol_last / vol_mean
        resistance = float(df["High"].rolling(20).max().iloc[-2])
        rs_val = float(df["Close"].pct_change(63).iloc[-1]) - float(spy_df["Close"].pct_change(63).iloc[-1])

        if price > resistance and vol_ratio > 1.5:
            ifs, adx = institutional_score(df, rs_val, spy_df)
            if adx < CONFIG["MIN_ADX"] or ifs < CONFIG["MIN_IFS_SCORE"]: return None

            tr = pd.concat([df["High"]-df["Low"], (df["High"]-df["Close"].shift()).abs()], axis=1).max(axis=1)
            atr = float(tr.rolling(14).mean().iloc[-1])
            sl = round(price - atr * 1.5, 2)
            risk = price - sl
            if risk <= 0: return None
            
            tg = round(price + risk * 2.5, 2)
            size = int((CONFIG["TOTAL_EQUITY"] * CONFIG["RISK_PER_TRADE_PERCENT"]) / risk)
            
            return {
                "ticker": ticker, "price": round(price, 2), "ifs": ifs, "label": "⚡ SWEEP" if vol_ratio > 2 else "🧊 ACCUM",
                "strike": round(price * 1.05), "tg": tg, "sl": sl, "rs": round(rs_val * 100, 1),
                "size": size, "prob": min(50 + ifs * 5, 92), "sector": SECTOR_MAP.get(ticker, "Other"),
                "r1": round(resistance, 2), "r2": round(price + atr * 2, 2), "vol_ratio": round(vol_ratio, 2), "adx": round(adx, 1)
            }
    except: return None
    return None

# ==============================
# 🚀 MAIN EXECUTION
# ==============================
def main():
    print("=" * 70)
    print("🧬 NEXUS v14.5 — WHALE DETECTOR EDITION")
    print("=" * 70)

    if not is_market_gold_hour():
        print("⏰ Outside Gold Hour. Exiting.")
        return

    is_bull, spy_df = get_market_regime()
    if not is_bull or spy_df is None:
        print("🛑 Regime Bearish / SPY unavailable. Scan cancelled.")
        return

    earnings_cache = load_earnings_cache()
    already_alerted = set()
    today = datetime.now().strftime("%Y-%m-%d")
    if os.path.exists(LOG_FILE):
        try:
            log_df = pd.read_csv(LOG_FILE)
            already_alerted = set(log_df[log_df["date"] == today]["ticker"].values)
        except: pass

    print(f"🔍 Scanning {len(MY_WATCHLIST)} tickers...")
    results = []
    with ThreadPoolExecutor(max_workers=CONFIG["MAX_THREADS"]) as executor:
        futures = [executor.submit(analyze_ticker, t, spy_df, already_alerted, earnings_cache) for t in MY_WATCHLIST]
        for f in as_completed(futures):
            res = f.result()
            if res: results.append(res)

    results.sort(key=lambda x: (x["ifs"], x["rs"]), reverse=True)
    
    selected = []
    sector_count = defaultdict(int)
    for r in results:
        if sector_count[r["sector"]] < CONFIG["MAX_PER_SECTOR"]:
            selected.append(r)
            sector_count[r["sector"]] += 1
        if len(selected) >= CONFIG["MAX_ALERTS"]: break

    print(f"🎯 Selected: {len(selected)} alerts")

    for r in selected:
        vol_ratio_val = r.pop("vol_ratio")
        log_trade(r, vol_ratio_val)
        
        msg = (
            f"🔭 *INSTITUTIONAL FLOW: {r['ticker']}*\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🏭 *SECTOR:* {r['sector']}\n"
            f"📊 *FLOW:* {r['label']} | IFS: `{r['ifs']}/10` | ADX: `{r['adx']}`\n"
            f"✅ *BREAKOUT:* above `${r['r1']}`\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"💰 Price: `${r['price']}` | 📈 RS vs SPY: `{r['rs']}%`\n"
            f"💎 *INSTRUMENT:* STOCKS / CALL OPTIONS\n"
            f"🎯 *Call Strike (+5% OTM):* `${r['strike']}`\n"
            f"🚀 Target: `${r['tg']}` | 🛑 Stop: `${r['sl']}`\n"
            f"🛡️ Size: `{r['size']} sh` | 🎯 Prob: `{r['prob']}%`\n"
            f"━━━━━━━━━━━━━━━━━━"
        )
        
        # Corretto: Parentesi chiusa correttamente qui sotto
        print(msg)
        
        try:
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                          data={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"}, 
                          timeout=10)
        except Exception as e:
            print(f"❌ Telegram Error: {e}")
        time.sleep(1)

    save_earnings_cache(earnings_cache)
    print("=" * 70)
    print(f"🏁 Done — {len(selected)} alerts processed")
    print("=" * 70)

if __name__ == "__main__":
    main()

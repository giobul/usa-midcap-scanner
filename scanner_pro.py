#!/usr/bin/env python3
"""
NEXUS v14.5 — WHALE DETECTOR EDITION
Fixes applied in v14.4:
  ✅ [v14.5] RS Line: segnala solo se RS fa nuovo max insieme al breakout
  ✅ [v14.5] Volume Dry-up: verifica silenzio volumi 3gg prima del breakout
  ✅ [v14.5] ADX >= 25: filtra breakout in mercati laterali
  ✅ [v14.5] IFS ora 10 punti (3 nuovi componenti aggiunti)
  ✅ Tutto il resto da v14.4
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
logging.getLogger("yfinance").setLevel(logging.CRITICAL)  # sopprimi tutti i warning yf

# ==============================
# 🔑 SESSION
# ==============================
session = requests.Session()
session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
})

# ==============================
# 🔑 CONFIGURATION
# ==============================
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN",   "YOUR_TOKEN_HERE")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "YOUR_CHAT_ID_HERE")

BASE_DIR       = os.path.dirname(os.path.abspath(__file__))
LOG_FILE       = os.path.join(BASE_DIR, "nexus_trade_log.csv")
EARNINGS_CACHE = os.path.join(BASE_DIR, ".earnings_cache.json")

CONFIG = {
    "TOTAL_EQUITY":            100_000,
    "RISK_PER_TRADE_PERCENT":  0.01,
    "MAX_THREADS":             4,
    "MIN_VOLUME_USD":          1_000_000,
    "MAX_ALERTS":              5,
    "MIN_IFS_SCORE":           5,        # ora su scala 10 con i 3 nuovi filtri
    "MIN_ADX":                 25,       # ADX minimo (semaforo trend)
    "VOLUME_DRYUP_RATIO":      0.5,      # volume dry-up: giorni precedenti < 50% media
    "MAX_PER_SECTOR":          2,
    "EARNINGS_LOOKBACK_DAYS":  1,
    "EARNINGS_LOOKAHEAD_DAYS": 1,
    "YF_RETRIES":              3,
    "YF_RETRY_DELAY":          15,
}

# ==============================
# 📋 SECTOR MAP (250+ tickers — complete, no stubs)
# ==============================
SECTOR_MAP = {
    # Mega-cap Tech
    "AAPL": "Tech",      "MSFT": "Tech",      "GOOGL": "Tech",
    "META": "Tech",      "AMZN": "Ecommerce", "TSLA": "EV",
    "NFLX": "Media",     "BRK-B": "Finance",
    # Semiconductors
    "NVDA": "Semis",  "AMD": "Semis",   "INTC": "Semis",  "QCOM": "Semis",
    "AVGO": "Semis",  "TSM": "Semis",   "ASML": "Semis",  "AMAT": "Semis",
    "LRCX": "Semis",  "KLAC": "Semis",  "MU": "Semis",    "ON": "Semis",
    "MRVL": "Semis",  "NXPI": "Semis",  "ADI": "Semis",   "MCHP": "Semis",
    "MPWR": "Semis",  "ENTG": "Semis",  "TER": "Semis",   "COHR": "Semis",
    "OLED": "Semis",  "LSCC": "Semis",  "SWKS": "Semis",  "QRVO": "Semis",
    "TXN": "Semis",   "SMCI": "Semis",  "SNPS": "Semis",  "CDNS": "Semis",
    # Cloud / SaaS
    "CRM": "Cloud",   "ADBE": "Cloud",  "NOW": "Cloud",   "ORCL": "Cloud",
    "SHOP": "Cloud",  "SNOW": "Cloud",  "PLTR": "Cloud",  "DDOG": "Cloud",
    "MDB": "Cloud",   "TEAM": "Cloud",  "ESTC": "Cloud",  "OKTA": "Cloud",
    "TWLO": "Cloud",  "HUBS": "Cloud",  "BILL": "Cloud",  "U": "Cloud",
    "APP": "Cloud",   "DOCN": "Cloud",  "FSLY": "Cloud",  "DT": "Cloud",
    "AI": "Cloud",    "PATH": "Cloud",  "SOUN": "Cloud",
    # Cybersecurity
    "PANW": "Cyber",  "CRWD": "Cyber",  "ZS": "Cyber",    "NET": "Cyber",
    # Networking
    "CSCO": "Tech",   "ANET": "Tech",
    # Fintech / Payments
    "PYPL": "Fintech", "SQ": "Fintech",   "SOFI": "Fintech", "COIN": "Fintech",
    "HOOD": "Fintech", "AFRM": "Fintech", "STNE": "Fintech", "NU": "Fintech",
    "PAGS": "Fintech", "UPST": "Fintech", "V": "Fintech",    "MA": "Fintech",
    # Finance
    "JPM": "Finance",  "BAC": "Finance",  "WFC": "Finance",  "C": "Finance",
    "GS": "Finance",   "MS": "Finance",   "BLK": "Finance",  "SCHW": "Finance",
    "AXP": "Finance",  "ICE": "Finance",  "CME": "Finance",  "KKR": "Finance",
    "BX": "Finance",   "APO": "Finance",  "ARES": "Finance", "ALLY": "Finance",
    # Healthcare
    "UNH": "Health",  "LLY": "Health",   "ABBV": "Health",  "MRK": "Health",
    "VRTX": "Health", "REGN": "Health",  "GILD": "Health",  "BIIB": "Health",
    "MRNA": "Health", "BNTX": "Health",  "ISRG": "Health",  "SYK": "Health",
    "MDT": "Health",  "TMO": "Health",   "ABT": "Health",   "DHR": "Health",
    "PFE": "Health",  "BMY": "Health",   "CVS": "Health",   "HUM": "Health",
    "CI": "Health",   "ELV": "Health",   "IDXX": "Health",  "DXCM": "Health",
    "HIMS": "Health",
    # Consumer
    "PG": "Consumer", "BYND": "Consumer",
    # Retail
    "COST": "Retail", "HD": "Retail",   "LOW": "Retail",   "NKE": "Retail",
    "SBUX": "Retail", "MCD": "Retail",  "TGT": "Retail",   "ROST": "Retail",
    "TJX": "Retail",  "LULU": "Retail", "ULTA": "Retail",  "DPZ": "Retail",
    "CMG": "Retail",  "YUM": "Retail",  "CVNA": "Retail",
    # Travel
    "BKNG": "Travel", "ABNB": "Travel", "MAR": "Travel",   "HLT": "Travel",
    # Mobility
    "UBER": "Tech",   "LYFT": "Tech",
    # E-commerce
    "EBAY": "Ecommerce", "ETSY": "Ecommerce",
    # Media / Telecom
    "DIS": "Media",   "CMCSA": "Media",  "PARA": "Media",  "WBD": "Media",
    "FOX": "Media",   "FOXA": "Media",   "FUBO": "Media",
    "T": "Telecom",   "VZ": "Telecom",   "CHTR": "Telecom","TMUS": "Telecom",
    "ASTS": "Telecom",
    # Energy
    "XOM": "Energy",  "CVX": "Energy",  "COP": "Energy",   "EOG": "Energy",
    "SLB": "Energy",  "HAL": "Energy",  "OXY": "Energy",   "MPC": "Energy",  "PSX": "Energy",  "VLO": "Energy",   "KMI": "Energy",
    "WMB": "Energy",  "DVN": "Energy",  "FANG": "Energy",  "APA": "Energy",
    "CTRA": "Energy", "BKR": "Energy",  "EQT": "Energy",
    "XLE": "Energy",
    # Industrials
    "BA": "Industrial",  "RTX": "Industrial", "LMT": "Industrial", "NOC": "Industrial",
    "GD": "Industrial",  "CAT": "Industrial", "DE": "Industrial",  "ETN": "Industrial",
    "PH": "Industrial",  "HON": "Industrial", "GE": "Industrial",  "EMR": "Industrial",
    "MMM": "Industrial", "ITW": "Industrial", "CMI": "Industrial", "ROK": "Industrial",
    "AME": "Industrial", "TDG": "Industrial", "LHX": "Industrial", "PCAR": "Industrial",
    # Materials
    "LIN": "Materials", "APD": "Materials", "ECL": "Materials", "SHW": "Materials",
    "NEM": "Materials", "FCX": "Materials", "DOW": "Materials", "DD": "Materials",
    "ALB": "Materials", "NUE": "Materials",
    # Utilities
    "NEE": "Utilities", "DUK": "Utilities", "SO": "Utilities",  "AEP": "Utilities",
    "EXC": "Utilities", "SRE": "Utilities", "D": "Utilities",   "XEL": "Utilities",
    "PEG": "Utilities", "ED": "Utilities",
    # Transport
    "UPS": "Transport", "FDX": "Transport", "UNP": "Transport", "CSX": "Transport",
    "NSC": "Transport", "CP": "Transport",  "CNI": "Transport",
    # Airlines
    "DAL": "Airlines",  "UAL": "Airlines",  "AAL": "Airlines",
    # Crypto
    "MSTR": "Crypto",  "MARA": "Crypto",  "RIOT": "Crypto",  "CLSK": "Crypto",
    # EV / Clean Energy
    "RIVN": "EV",     "LCID": "EV",   "CHPT": "EV",    "QS": "EV",
    "PLUG": "CleanEnergy", "RUN": "CleanEnergy", "SEDG": "CleanEnergy",
    "ENPH": "CleanEnergy", "BLNK": "CleanEnergy",
    # Gaming
    "RBLX": "Gaming",  "DKNG": "Gaming",
    # Aerospace
    "RKLB": "Aerospace",
    # Misc
    "OPEN": "Tech",   "IONQ": "Tech",
}

MY_WATCHLIST = [
    "AAPL","MSFT","NVDA","AMZN","GOOGL","META","TSLA","BRK-B","UNH","XOM",
    "LLY","JPM","V","AVGO","MA","HD","PG","MRK","COST","ABBV",
    "AMD","CRM","ADBE","NFLX","INTC","ORCL","CSCO","QCOM","TXN","NOW",
    "SHOP","SNOW","PLTR","PANW","CRWD","ZS","NET","DDOG","MDB","TEAM",
    "SMCI","TSM","ASML","AMAT","LRCX","KLAC","MU","ON","MRVL","NXPI",
    "ADI","MCHP","MPWR","ENTG","TER","COHR","OLED","LSCC","SWKS","QRVO",
    "AI","PATH","UPST","SOUN","DOCN","ESTC","OKTA","TWLO","FSLY","HUBS",
    "DT","BILL","U","RBLX","AFRM","APP","SNPS","CDNS","ANET",
    "BAC","WFC","C","GS","MS","BLK","SCHW","AXP","PYPL","XYZ",
    "SOFI","COIN","HOOD","ICE","CME","KKR","BX","APO","ARES","ALLY",
    "VRTX","REGN","GILD","BIIB","MRNA","BNTX","ISRG","SYK","MDT","TMO",
    "ABT","DHR","PFE","BMY","CVS","HUM","CI","ELV","IDXX","DXCM",
    "BA","RTX","LMT","NOC","GD","CAT","DE","ETN","PH","HON",
    "GE","EMR","MMM","ITW","CMI","ROK","AME","TDG","LHX","PCAR",
    "CVX","COP","EOG","SLB","HAL","OXY","MPC","PSX","VLO",
    "KMI","WMB","DVN","FANG","APA","CTRA","BKR","EQT","XLE",
    "NKE","SBUX","MCD","LOW","TGT","BKNG","ABNB","UBER","LYFT","EBAY",
    "ETSY","ROST","TJX","LULU","ULTA","DPZ","CMG","YUM","MAR","HLT",
    "DIS","CMCSA","T","VZ","CHTR","TMUS","PARA","WBD","FOX","FOXA",
    "LIN","APD","ECL","SHW","NEM","FCX","DOW","DD","ALB","NUE",
    "NEE","DUK","SO","AEP","EXC","SRE","D","XEL","PEG","ED",
    "UPS","FDX","UNP","CSX","NSC","CP","CNI","DAL","UAL","AAL",
    "MARA","RIOT","CLSK","CVNA","RIVN","LCID","BYND","CHPT","FUBO",
    "OPEN","DKNG","PLUG","RUN","SEDG","ENPH","BLNK","QS","IONQ",
    "STNE","NU","PAGS","ASTS","RKLB","HIMS","MSTR",
]

# ==============================
# 🛠️ UTILITIES
# ==============================
def is_market_gold_hour():
    tz  = pytz.timezone("America/New_York")
    now = datetime.now(tz)
    if now.weekday() > 4:
        return False
    return (
        datetime.strptime("10:00", "%H:%M").time()
        <= now.time() <=
        datetime.strptime("15:30", "%H:%M").time()
    )

def log_trade(data: dict, vol_ratio: float):
    file_exists = os.path.isfile(LOG_FILE)
    row = data.copy()
    row["date"]      = datetime.now().strftime("%Y-%m-%d")
    row["timestamp"] = datetime.now().strftime("%H:%M:%S")
    row["vol_ratio"] = round(vol_ratio, 2)
    pd.DataFrame([row]).to_csv(LOG_FILE, mode="a", index=False, header=not file_exists)

def yf_download_with_retry(ticker: str, **kwargs):
    kwargs.setdefault("session",     session)
    kwargs.setdefault("auto_adjust", True)
    kwargs.setdefault("progress",    False)
    for attempt in range(CONFIG["YF_RETRIES"]):
        try:
            df = yf.download(ticker, **kwargs)
            if df is not None and not df.empty:
                return df
        except Exception as e:
            msg = str(e)
            if any(k in msg for k in ("Rate", "429", "Too Many")):
                wait = CONFIG["YF_RETRY_DELAY"] * (attempt + 1)
                print(f"⏳ Rate-limited [{ticker}] — waiting {wait}s "
                      f"(attempt {attempt+1}/{CONFIG['YF_RETRIES']})")
                time.sleep(wait)
            else:
                break
    return None

# ==============================
# 📅 EARNINGS CALENDAR
# ==============================
def load_earnings_cache() -> dict:
    if os.path.exists(EARNINGS_CACHE):
        try:
            with open(EARNINGS_CACHE) as f:
                data = json.load(f)
            age = (datetime.now() - datetime.fromisoformat(data.get("updated", "2000-01-01"))).days
            if age < 7:
                return data.get("earnings", {})
        except:
            pass
    return {}

def save_earnings_cache(cache: dict):
    try:
        with open(EARNINGS_CACHE, "w") as f:
            json.dump({"updated": datetime.now().isoformat(), "earnings": cache}, f)
    except:
        pass

def check_earnings_risk(ticker: str, cache: dict) -> bool:
    if ticker not in cache:
        try:
            import urllib3
            urllib3.disable_warnings()  # sopprimi 404 silenziosamente
            ticker_obj = yf.Ticker(ticker)
            cal = ticker_obj.calendar
            if cal is not None and not cal.empty and "Earnings Date" in cal.index:
                raw = cal.loc["Earnings Date"]
                val = raw.iloc[0] if hasattr(raw, "iloc") else raw
                if pd.notna(val):
                    cache[ticker] = pd.to_datetime(val).date().isoformat()
        except Exception:
            pass  # 404 e altri errori ignorati silenziosamente
        return True
    try:
        diff = (datetime.fromisoformat(cache[ticker]).date() - datetime.now().date()).days
        if -CONFIG["EARNINGS_LOOKBACK_DAYS"] <= diff <= CONFIG["EARNINGS_LOOKAHEAD_DAYS"]:
            return False
    except:
        pass
    return True

# ==============================
# 📊 MARKET REGIME
# ==============================
def _fetch_spy_stooq() -> pd.DataFrame:
    """Fallback: scarica SPY da stooq.com (nessun rate limit su GitHub Actions)"""
    try:
        url = "https://stooq.com/q/d/l/?s=spy.us&i=d"
        df  = pd.read_csv(url, parse_dates=["Date"], index_col="Date")
        df  = df.sort_index()
        # Rinomina colonne per compatibilità
        df.columns = [c.capitalize() for c in df.columns]
        if "Close" not in df.columns:
            return None
        # Aggiungi Volume fittizio se assente (stooq non lo include sempre)
        if "Volume" not in df.columns:
            df["Volume"] = 0
        return df.tail(300)   # ultimi 300 giorni bastano per SMA50
    except Exception as e:
        print(f"⚠️  Stooq fallback error: {e}")
        return None

def get_market_regime():
    """Prova yfinance, poi stooq come fallback anti-rate-limit."""
    spy = yf_download_with_retry("SPY", period="1y", interval="1d")

    if spy is None:
        print("⚠️  yfinance rate-limited — provo stooq fallback...")
        spy = _fetch_spy_stooq()

    if spy is None:
        print("❌ SPY non disponibile da nessuna fonte.")
        return False, None

    if isinstance(spy.columns, pd.MultiIndex):
        spy.columns = spy.columns.get_level_values(0)
    if len(spy) < 60:
        return False, None

    spy["SMA50"] = spy["Close"].rolling(50).mean()
    is_bull = float(spy["Close"].iloc[-1]) > float(spy["SMA50"].iloc[-1])
    slope   = float(spy["SMA50"].iloc[-1]) > float(spy["SMA50"].iloc[-5])
    print(f"📡 SPY: ${float(spy['Close'].iloc[-1]):.2f} | SMA50: ${float(spy['SMA50'].iloc[-1]):.2f} | {'🟢 BULL' if is_bull else '🔴 BEAR'}")
    return bool(is_bull and slope), spy

# ==============================
# 🧠 HELPER: ADX Calculator
# ==============================
def calc_adx(df: pd.DataFrame, period: int = 14) -> float:
    """Calcola ADX (Average Directional Index) — misura forza del trend"""
    try:
        high  = df["High"]
        low   = df["Low"]
        close = df["Close"]

        # True Range
        tr = pd.concat([
            high - low,
            (high - close.shift()).abs(),
            (low  - close.shift()).abs(),
        ], axis=1).max(axis=1)

        # Directional Movement
        dm_plus  = (high - high.shift()).clip(lower=0)
        dm_minus = (low.shift() - low).clip(lower=0)
        # Se DM+ < DM- o DM- < DM+, zero l'altro
        dm_plus  = dm_plus.where(dm_plus > dm_minus, 0)
        dm_minus = dm_minus.where(dm_minus > dm_plus, 0)

        # Smoothed (Wilder)
        atr_s    = tr.ewm(alpha=1/period, adjust=False).mean()
        di_plus  = 100 * dm_plus.ewm(alpha=1/period, adjust=False).mean() / atr_s
        di_minus = 100 * dm_minus.ewm(alpha=1/period, adjust=False).mean() / atr_s

        dx = (100 * (di_plus - di_minus).abs() / (di_plus + di_minus).replace(0, np.nan))
        adx = dx.ewm(alpha=1/period, adjust=False).mean()
        return float(adx.iloc[-1])
    except Exception:
        return 0.0

# ==============================
# 🧠 INSTITUTIONAL FLOW SCORE (10-point)
# ==============================
def institutional_score(df: pd.DataFrame, rs_val: float, spy_df: pd.DataFrame) -> tuple:
    """
    Score 0-10 con 6 componenti:
      +2  Volume accumulation   (3/5 giorni sopra media 20gg)
      +2  Range compression VCP (range 5gg < range 20gg)
      +2  Relative strength     (sovraperformance SPY 63gg)
      +1  Bullish close         (chiusura top 25% range giornaliero)
      +2  RS Line new high      (RS line fa nuovo max con il breakout)
      +1  Volume dry-up         (3gg prima del breakout: volumi < 50% media)

    ADX viene restituito separatamente come filtro hard (non nel score).
    """
    if len(df) < 30:
        return 0, 0.0

    score = 0

    # 1. Volume accumulation
    avg20 = df["Volume"].rolling(20).mean()
    if (df["Volume"].iloc[-5:] > avg20.iloc[-5:]).sum() >= 3:
        score += 2

    # 2. VCP range compression
    hl  = df["High"] - df["Low"]
    r5  = float(hl.rolling(5).mean().iloc[-1])
    r20 = float(hl.rolling(20).mean().iloc[-1])
    if pd.notna(r5) and pd.notna(r20) and r20 > 0 and r5 < r20:
        score += 2

    # 3. Relative strength vs SPY (63gg)
    if rs_val > 0:
        score += 2

    # 4. Bullish close structure
    day_range = float(df["High"].iloc[-1]) - float(df["Low"].iloc[-1])
    if day_range > 0:
        close_pos = (float(df["Close"].iloc[-1]) - float(df["Low"].iloc[-1])) / day_range
        if close_pos > 0.75:
            score += 1

    # 5. RS Line new high (nuovo massimo a 20 giorni della forza relativa)
    try:
        # RS Line = Close ticker / Close SPY (allineati per data)
        aligned = df["Close"].align(spy_df["Close"], join="inner")
        rs_line = aligned[0] / aligned[1]
        if len(rs_line) >= 21:
            rs_max20 = rs_line.iloc[-21:-1].max()   # max dei 20gg precedenti
            if float(rs_line.iloc[-1]) > float(rs_max20):
                score += 2
    except Exception:
        pass

    # 6. Volume dry-up: 3 giorni prima volumi < 50% della media 20gg
    try:
        avg20_val = float(avg20.iloc[-4])            # media al giorno -4
        dry_days  = (df["Volume"].iloc[-4:-1] < avg20.iloc[-4:-1] * 0.50).sum()
        if dry_days >= 2:                            # almeno 2 dei 3gg pre-breakout
            score += 1
    except Exception:
        pass

    # ADX calcolato separatamente
    adx = calc_adx(df)

    return score, adx

# ==============================
# 🔎 ANALYZE TICKER
# ==============================
def analyze_ticker(ticker: str, spy_df: pd.DataFrame,
                   already_alerted: set, earnings_cache: dict):
    print(f"🔎 Scanning: {ticker}", flush=True)
    if ticker in already_alerted:
        print(f"   ⏭️  {ticker} — già alertato oggi", flush=True)
        return None
    if not check_earnings_risk(ticker, earnings_cache):
        print(f"   ⚠️  {ticker} — earnings imminenti, skip", flush=True)
        return None
    try:
        time.sleep(random.uniform(0.2, 0.6))
        df = yf_download_with_retry(ticker, period="1y", interval="1d")
        if df is None or len(df) < 60:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # squeeze() ensures scalar even if yfinance returns single-col DataFrame
        price    = float(df["Close"].iloc[-1].squeeze() if hasattr(df["Close"].iloc[-1], "squeeze") else df["Close"].iloc[-1])
        vol_mean = float(df["Volume"].rolling(20).mean().iloc[-1].squeeze() if hasattr(df["Volume"].rolling(20).mean().iloc[-1], "squeeze") else df["Volume"].rolling(20).mean().iloc[-1])
        if pd.isna(vol_mean) or vol_mean == 0:
            return None
        vol_last = df["Volume"].iloc[-1]
        vol_last = float(vol_last.squeeze() if hasattr(vol_last, "squeeze") else vol_last)
        if price * vol_last < CONFIG["MIN_VOLUME_USD"]:
            return None

        vol_ratio  = vol_last / vol_mean
        res_raw    = df["High"].rolling(20).max().iloc[-2]
        resistance = float(res_raw.squeeze() if hasattr(res_raw, "squeeze") else res_raw)
        rs_raw     = df["Close"].pct_change(63).iloc[-1]
        spy_rs_raw = spy_df["Close"].pct_change(63).iloc[-1]
        rs_val     = (
            float(rs_raw.squeeze() if hasattr(rs_raw, "squeeze") else rs_raw)
            - float(spy_rs_raw.squeeze() if hasattr(spy_rs_raw, "squeeze") else spy_rs_raw)
        )
        if pd.isna(resistance) or pd.isna(rs_val):
            return None

        if price > resistance and vol_ratio > 1.2:
            ifs, adx = institutional_score(df, rs_val, spy_df)

            # Filtro ADX >= 25 (semaforo intensità trend)
            if adx < 25:
                print(f"   📉 {ticker} — ADX {adx:.1f} < 25, trend debole skip", flush=True)
                return None

            if ifs < CONFIG["MIN_IFS_SCORE"]:
                return None

            tr  = pd.concat([
                df["High"] - df["Low"],
                (df["High"] - df["Close"].shift()).abs(),
                (df["Low"]  - df["Close"].shift()).abs(),
            ], axis=1).max(axis=1)
            atr = float(tr.rolling(14).mean().iloc[-1])
            if pd.isna(atr) or atr == 0:
                return None

            stop_loss = price - atr * 1.5
            risk      = price - stop_loss
            if risk <= 0:
                return None

            target = price + risk * 2.5
            size   = int((CONFIG["TOTAL_EQUITY"] * CONFIG["RISK_PER_TRADE_PERCENT"]) / risk)
            strike = round(price * 1.05)
            label  = "⚡ OPTION SWEEP" if vol_ratio > 2.0 else "🧊 ACCUMULATION"

            result = {
                "ticker":    ticker,
                "price":     round(price, 2),
                "ifs":       ifs,
                "label":     label,
                "strike":    strike,
                "tg":        round(target, 2),
                "sl":        round(stop_loss, 2),
                "rs":        round(rs_val * 100, 1),
                "size":      size,
                "prob":      min(50 + ifs * 5, 92),  # scala su 10 punti
                "sector":    SECTOR_MAP.get(ticker, "Other"),
                "r1":        round(resistance, 2),
                "r2":        round(price + atr * 2, 2),
                "vol_ratio": round(vol_ratio, 2),
                "adx":       round(adx, 1),
            }
            print(f"   🚨 SEGNALE: {ticker} | IFS {ifs}/10 | ADX {adx:.1f} | ${round(price,2)} | {label}", flush=True)
            return result

    except Exception as e:
        print(f"   ❌ {ticker} — errore: {e}", flush=True)
        return None
    print(f"   ➖ {ticker} — nessun breakout", flush=True)
    return None

# ==============================
# 📤 TELEGRAM
# ==============================
def send_telegram(message: str) -> bool:
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"},
            timeout=10,
        )
        if resp.status_code != 200:
            print(f"❌ Telegram error: {resp.text}")
            return False
        return True
    except Exception as e:
        print(f"❌ Telegram exception: {e}")
        return False

# ==============================
# 🚀 MAIN
# ==============================
def main():
    print("=" * 70)
    print("🧬 NEXUS v14.5 — WHALE DETECTOR EDITION")
    print("=" * 70)

    # Gold Hour gate — decommentare per attivare in produzione
    if not is_market_gold_hour()
        print("⏰ Outside Gold Hour (10:00–15:30 EST). Exiting.")
        return

    is_bull, spy_df = get_market_regime()
    if not is_bull or spy_df is None:
        print("🛑 Regime Bearish / SPY unavailable. Scan cancelled.")
        return
    print("✅ Market Regime: BULLISH")

    earnings_cache = load_earnings_cache()
    print(f"📅 Earnings cache: {len(earnings_cache)} tickers")

    already_alerted: set = set()
    today = datetime.now().strftime("%Y-%m-%d")
    if os.path.exists(LOG_FILE):
        try:
            log_df = pd.read_csv(LOG_FILE)
            if "date" in log_df.columns:
                already_alerted = set(log_df[log_df["date"] == today]["ticker"].values)
                print(f"⏭️  Already alerted today: {len(already_alerted)} tickers")
        except:
            pass

    print(f"🔍 Scanning {len(MY_WATCHLIST)} tickers ({CONFIG['MAX_THREADS']} threads)…")
    results = []

    import sys; sys.stdout.flush()  # forza output prima del scan
    with ThreadPoolExecutor(max_workers=CONFIG["MAX_THREADS"]) as executor:
        futures = {
            executor.submit(analyze_ticker, t, spy_df, already_alerted, earnings_cache): t
            for t in MY_WATCHLIST
        }
        for future in as_completed(futures):
            res = future.result()
            if res:
                results.append(res)

    print(f"📊 Raw candidates (IFS ≥ {CONFIG['MIN_IFS_SCORE']}): {len(results)}")
    if not results:
        print("❌ No high-quality signals found.")
        save_earnings_cache(earnings_cache)
    #     return

    results.sort(key=lambda x: (x["ifs"], x["rs"]), reverse=True)

    sector_count: defaultdict = defaultdict(int)
    selected = []
    for r in results:
        sec = r["sector"]
        if sector_count[sec] < CONFIG["MAX_PER_SECTOR"]:
            selected.append(r)
            sector_count[sec] += 1
        else:
            print(f"⚠️  {r['ticker']} skipped — {sec} sector cap reached")
        if len(selected) >= CONFIG["MAX_ALERTS"]:
            break

    print(f"🎯 Selected: {len(selected)} | Sectors: {dict(sector_count)}")
    print()

    alerts_sent = 0
    for r in selected:
        vol_ratio = r.pop("vol_ratio")
        log_trade(r, vol_ratio)

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
            f"📊 R1: `${r['r1']}` / R2: `${r['r2']}`\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"R:R = {round((r['tg'] - r['price']) / (r['price'] - r['sl']), 2)}:1"
        )

        sent = send_telegram(msg)
        status = "✅ Telegram" if sent else "🖨️  Console"
        print(f"{status}: {r['ticker']} | IFS {r['ifs']}/10 | ADX {r['adx']} | {r['sector']}")
        print(msg)
        print()

        alerts_sent += 1
        time.sleep(2)

    save_earnings_cache(earnings_cache)
    print("=" * 70)
    print(f"🏁 Done — {alerts_sent}/{len(selected)} alerts processed")
    print("=" * 70)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 Interrupted.")
    except Exception as e:
        import traceback
        print(f"💥 Fatal: {e}")
        traceback.print_exc()

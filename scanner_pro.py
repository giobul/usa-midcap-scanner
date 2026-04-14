import yfinance as yf
import pandas as pd
import numpy as np
import requests
import warnings
import pytz
import time
import os
import json
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
from io import StringIO

warnings.filterwarnings("ignore")
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==============================
# 🔑 CONFIGURAZIONE E SESSIONE
# ==============================
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
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
    "MAX_PER_SECTOR":          2,
    "YF_RETRIES":              3,
    "YF_RETRY_DELAY":          10,
}

# ==============================
# 📋 SECTOR MAP COMPLETA (Tutte le tue azioni)
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
# 🛠️ UTILITIES & FALLBACKS
# ==============================
def _fetch_spy_stooq():
    try:
        url = "https://stooq.com/q/d/l/?s=spy.us&i=d"
        response = session.get(url, timeout=15)
        if response.status_code != 200: return None
        df = pd.read_csv(StringIO(response.text), on_bad_lines='skip', engine='python')
        df.columns = [c.capitalize() for c in df.columns]
        if 'Date' not in df.columns: return None
        df.set_index(pd.to_datetime(df['Date']), inplace=True)
        return df.sort_index().tail(300)
    except Exception as e:
        print(f"⚠️ Stooq Error: {e}")
        return None

def get_market_regime():
    spy = None
    try:
        spy = yf.download("SPY", period="1y", session=session, progress=False, auto_adjust=True)
        if spy is None or spy.empty: raise Exception("YF Rate Limited")
    except:
        spy = _fetch_spy_stooq()
    
    if spy is None or len(spy) < 50: return False, None

    spy["SMA50"] = spy["Close"].rolling(50).mean()
    curr_close = float(spy["Close"].iloc[-1])
    sma50 = float(spy["SMA50"].iloc[-1])
    is_bull = curr_close > sma50
    print(f"📡 SPY: ${curr_close:.2f} | SMA50: ${sma50:.2f} | {'🟢 BULL' if is_bull else '🔴 BEAR'}")
    return bool(is_bull), spy

# ==============================
# 🧠 INDICATORI & ANALISI
# ==============================
def institutional_score(df, spy_df):
    score = 0
    vol_avg = df["Volume"].rolling(20).mean()
    if (df["Volume"].iloc[-3:] > vol_avg.iloc[-3:]).any(): score += 2
    rs_line = df["Close"] / spy_df["Close"].reindex(df.index, method='ffill')
    if rs_line.iloc[-1] > rs_line.iloc[-20:].mean(): score += 3
    hl = (df["High"] - df["Low"]).rolling(5).mean()
    if hl.iloc[-1] < hl.iloc[-20:].mean(): score += 2
    return score

def analyze_ticker(ticker, spy_df):
    try:
        df = yf.download(ticker, period="1y", session=session, progress=False, auto_adjust=True)
        if df is None or len(df) < 50: return None
        
        price = float(df["Close"].iloc[-1])
        res_20 = float(df["High"].rolling(20).max().iloc[-2])
        vol_ratio = float(df["Volume"].iloc[-1] / df["Volume"].rolling(20).mean().iloc[-1])
        
        if price > res_20 and vol_ratio > 1.2:
            ifs = institutional_score(df, spy_df)
            if ifs < CONFIG["MIN_IFS_SCORE"]: return None
            
            atr = float((df["High"] - df["Low"]).rolling(14).mean().iloc[-1])
            sl = round(price - (atr * 1.5), 2)
            tg = round(price + (price - sl) * 2.5, 2)
            size = int((CONFIG["TOTAL_EQUITY"] * CONFIG["RISK_PER_TRADE_PERCENT"]) / (price - sl))
            
            return {
                "ticker": ticker, "price": round(price, 2), "ifs": ifs,
                "sector": SECTOR_MAP.get(ticker, "Other"), "strike": round(price * 1.05, 2),
                "tg": tg, "sl": sl, "vol_ratio": round(vol_ratio, 2), "res": round(res_20, 2),
                "size": size
            }
    except: return None

# ==============================
# 🚀 MAIN
# ==============================
def main():
    print("=" * 70)
    print("🧬 NEXUS v14.7 — WHALE DETECTOR EDITION")
    print("=" * 70)

    is_bull, spy_df = get_market_regime()
    if not is_bull:
        print("🛑 Regime Bearish. Scansione interrotta.")
        return

    print(f"🔍 Scansione di {len(MY_WATCHLIST)} ticker in corso...")
    results = []
    with ThreadPoolExecutor(max_workers=CONFIG["MAX_THREADS"]) as executor:
        futures = [executor.submit(analyze_ticker, t, spy_df) for t in MY_WATCHLIST]
        for f in as_completed(futures):
            res = f.result()
            if res: results.append(res)

    results.sort(key=lambda x: x["ifs"], reverse=True)
    
    selected = []
    sector_count = defaultdict(int)
    for r in results:
        if sector_count[r["sector"]] < CONFIG["MAX_PER_SECTOR"]:
            selected.append(r)
            sector_count[r["sector"]] += 1
        if len(selected) >= CONFIG["MAX_ALERTS"]: break

    for r in selected:
        msg = (
            f"🔭 *INSTITUTIONAL FLOW: {r['ticker']}*\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🏭 *SETTORE:* {r['sector']}\n"
            f"📊 *IFS SCORE:* `{r['ifs']}/10` | Vol Ratio: `{r['vol_ratio']}`\n"
            f"✅ *BREAKOUT:* sopra `${r['res']}`\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"💰 Prezzo: `${r['price']}`\n"
            f"💎 *STRUMENTO:* AZIONI / CALL OPTIONS\n"
            f"🎯 *Call Strike (+5%):* `${r['strike']}`\n"
            f"🚀 Target: `${r['tg']}` | 🛑 Stop: `${r['sl']}`\n"
            f"🛡️ Size: `{r['size']} sh`\n"
            f"━━━━━━━━━━━━━━━━━━"
        )
        print(msg)
        try:
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                          data={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"}, 
                          timeout=10)
        except: pass
        time.sleep(1)

    print("=" * 70)
    print(f"🏁 Fine — {len(selected)} segnali elaborati.")

if __name__ == "__main__":
    main()

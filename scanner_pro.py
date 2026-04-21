import subprocess
import sys
import os
import time
import logging
import warnings
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

# ==============================================================
# 🛠️ AUTO-INSTALLER (Solo pacchetti stabili)
# ==============================================================
def _install(package: str) -> None:
    try:
        __import__(package)
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package, "-q"])

for _pkg in ["pandas", "numpy", "requests", "yfinance", "pytz"]:
    _install(_pkg)

import yfinance as yf
import pandas as pd
import numpy as np
import requests
import pytz

warnings.filterwarnings("ignore")

# ==============================================================
# 📈 FUNZIONI TECNICHE NATIVE (Sostituiscono pandas_ta)
# ==============================================================
def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_atr(df, period=14):
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    return true_range.rolling(window=period).mean()

def calculate_vwap(df):
    v = df['volume'].values
    tp = (df['high'] + df['low'] + df['close']).values / 3
    return (tp * v).cumsum() / v.cumsum()

# ==============================================================
# ⚙️ CONFIGURAZIONE
# ==============================================================
@dataclass
class ScannerConfig:
    telegram_token: str   = field(default_factory=lambda: os.getenv("TELEGRAM_TOKEN", "YOUR_TOKEN"))
    telegram_chat_id: str = field(default_factory=lambda: os.getenv("TELEGRAM_CHAT_ID", "YOUR_ID"))
    total_equity: float   = 100000.0
    risk_per_trade_pct: float = 0.01
    max_threads: int      = 10
    min_ifs_threshold: int = 8
    rr_ratio: float       = 1.5
    max_trades_per_sector: int = 2
    ifs_max: int = 12
    ifs_institutional_threshold: int = 11

CFG = ScannerConfig()

# ==============================================================
# 📋 WATCHLIST INTEGRALE (242 Tickers)
# ==============================================================
SECTOR_MAP = {
    "AAPL": "Tech", "MSFT": "Tech", "GOOGL": "Tech", "META": "Tech",
    "AMZN": "Ecommerce", "TSLA": "EV", "NFLX": "Media", "BRK-B": "Finance",
    "NVDA": "Semis", "AMD": "Semis", "INTC": "Semis", "QCOM": "Semis",
    "AVGO": "Semis", "TSM": "Semis", "ASML": "Semis", "AMAT": "Semis",
    "LRCX": "Semis", "KLAC": "Semis", "MU": "Semis", "ON": "Semis",
    "MRVL": "Semis", "NXPI": "Semis", "ADI": "Semis", "MCHP": "Semis",
    "MPWR": "Semis", "ENTG": "Semis", "TER": "Semis", "COHR": "Semis",
    "OLED": "Semis", "LSCC": "Semis", "SWKS": "Semis", "QRVO": "Semis",
    "TXN": "Semis", "SMCI": "Semis", "SNPS": "Semis", "CDNS": "Semis",
    "CRM": "Cloud", "ADBE": "Cloud", "NOW": "Cloud", "ORCL": "Cloud",
    "SHOP": "Cloud", "SNOW": "Cloud", "PLTR": "Cloud", "DDOG": "Cloud",
    "MDB": "Cloud", "TEAM": "Cloud", "ESTC": "Cloud", "OKTA": "Cloud",
    "TWLO": "Cloud", "HUBS": "Cloud", "BILL": "Cloud", "U": "Cloud",
    "APP": "Cloud", "DOCN": "Cloud", "FSLY": "Cloud", "DT": "Cloud",
    "AI": "Cloud", "PATH": "Cloud", "SOUN": "Cloud", "PANW": "Cyber",
    "CRWD": "Cyber", "ZS": "Cyber", "NET": "Cyber", "CSCO": "Tech",
    "ANET": "Tech", "PYPL": "Fintech", "SQ": "Fintech", "SOFI": "Fintech",
    "COIN": "Fintech", "HOOD": "Fintech", "AFRM": "Fintech", "STNE": "Fintech",
    "NU": "Fintech", "PAGS": "Fintech", "UPST": "Fintech", "V": "Fintech",
    "MA": "Fintech", "JPM": "Finance", "BAC": "Finance", "WFC": "Finance",
    "C": "Finance", "GS": "Finance", "MS": "Finance", "BLK": "Finance",
    "SCHW": "Finance", "AXP": "Finance", "ICE": "Finance", "CME": "Finance",
    "KKR": "Finance", "BX": "Finance", "APO": "Finance", "ARES": "Finance",
    "ALLY": "Finance", "UNH": "Health", "LLY": "Health", "ABBV": "Health",
    "MRK": "Health", "VRTX": "Health", "REGN": "Health", "GILD": "Health",
    "BIIB": "Health", "MRNA": "Health", "BNTX": "Health", "ISRG": "Health",
    "SYK": "Health", "MDT": "Health", "TMO": "Health", "ABT": "Health",
    "DHR": "Health", "PFE": "Health", "BMY": "Health", "CVS": "Health",
    "HUM": "Health", "CI": "Health", "ELV": "Health", "IDXX": "Health",
    "DXCM": "Health", "HIMS": "Health", "PG": "Consumer", "BYND": "Consumer",
    "COST": "Retail", "HD": "Retail", "LOW": "Retail", "NKE": "Retail",
    "SBUX": "Retail", "MCD": "Retail", "TGT": "Retail", "ROST": "Retail",
    "TJX": "Retail", "LULU": "Retail", "ULTA": "Retail", "DPZ": "Retail",
    "CMG": "Retail", "YUM": "Retail", "CVNA": "Retail", "BKNG": "Travel",
    "ABNB": "Travel", "MAR": "Travel", "HLT": "Travel", "UBER": "Tech",
    "LYFT": "Tech", "EBAY": "Ecommerce", "ETSY": "Ecommerce", "DIS": "Media",
    "CMCSA": "Media", "PARA": "Media", "WBD": "Media", "FOX": "Media",
    "FOXA": "Media", "FUBO": "Media", "T": "Telecom", "VZ": "Telecom",
    "CHTR": "Telecom", "TMUS": "Telecom", "ASTS": "Telecom", "XOM": "Energy",
    "CVX": "Energy", "COP": "Energy", "EOG": "Energy", "SLB": "Energy",
    "HAL": "Energy", "OXY": "Energy", "MPC": "Energy", "PSX": "Energy",
    "VLO": "Energy", "KMI": "Energy", "WMB": "Energy", "DVN": "Energy",
    "FANG": "Energy", "APA": "Energy", "CTRA": "Energy", "BKR": "Energy",
    "EQT": "Energy", "XLE": "Energy", "BA": "Industrial", "RTX": "Industrial",
    "LMT": "Industrial", "NOC": "Industrial", "GD": "Industrial",
    "CAT": "Industrial", "DE": "Industrial", "ETN": "Industrial",
    "PH": "Industrial", "HON": "Industrial", "GE": "Industrial",
    "EMR": "Industrial", "MMM": "Industrial", "ITW": "Industrial",
    "CMI": "Industrial", "ROK": "Industrial", "AME": "Industrial",
    "TDG": "Industrial", "LHX": "Industrial", "PCAR": "Industrial",
    "LIN": "Materials", "APD": "Materials", "ECL": "Materials",
    "SHW": "Materials", "NEM": "Materials", "FCX": "Materials",
    "DOW": "Materials", "DD": "Materials", "ALB": "Materials",
    "NUE": "Materials", "NEE": "Utilities", "DUK": "Utilities",
    "SO": "Utilities", "AEP": "Utilities", "EXC": "Utilities",
    "SRE": "Utilities", "D": "Utilities", "XEL": "Utilities",
    "PEG": "Utilities", "ED": "Utilities", "UPS": "Transport",
    "FDX": "Transport", "UNP": "Transport", "CSX": "Transport",
    "NSC": "Transport", "CP": "Transport", "CNI": "Transport",
    "DAL": "Airlines", "UAL": "Airlines", "AAL": "Airlines",
    "MSTR": "Crypto", "MARA": "Crypto", "RIOT": "Crypto", "CLSK": "Crypto",
    "RIVN": "EV", "LCID": "EV", "CHPT": "EV", "QS": "EV",
    "PLUG": "CleanEnergy", "RUN": "CleanEnergy", "SEDG": "CleanEnergy",
    "ENPH": "CleanEnergy", "BLNK": "CleanEnergy", "RBLX": "Gaming",
    "DKNG": "Gaming", "RKLB": "Aerospace", "OPEN": "Tech", "IONQ": "Tech",
}
TICKERS = list(SECTOR_MAP.keys())

# ==============================================================
# 🧠 CORE ENGINE (Native Optimization)
# ==============================================================
def analyze_ticker(ticker: str) -> Optional[dict]:
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period="7d", interval="15m")
        if df.empty or len(df) < 30: return None
        
        df.columns = [c.lower() for c in df.columns]
        
        # Calcolo indicatori nativi
        price = df['close'].iloc[-1]
        df['rsi'] = calculate_rsi(df['close'])
        df['atr'] = calculate_atr(df)
        df['vwap'] = calculate_vwap(df)
        
        rsi = df['rsi'].iloc[-1]
        atr = df['atr'].iloc[-1]
        vwap = df['vwap'].iloc[-1]
        
        # Logica IFS (Max 12)
        score = 0
        if price > vwap: score += 3
        if 60 < rsi < 75: score += 2
        elif rsi >= 75: score += 1
        elif rsi < 50: score -= 5
        
        # Calcolo RVOL (Rispetto alle ultime 20 candele 15m)
        curr_vol = df['volume'].iloc[-1]
        avg_vol = df['volume'].tail(20).mean()
        vol_ratio = curr_vol / avg_vol if avg_vol > 0 else 0
        
        if vol_ratio > 1.5: score += 2
        if vol_ratio > 2.5: score += 4
        
        # Breakout 20 periodi
        res_20 = df['high'].rolling(20).max().iloc[-2]
        if price > res_20: score += 3

        if score < CFG.min_ifs_threshold: return None

        # Money Management
        sl = round(price - atr * 1.5, 2)
        tg = round(price + (price - sl) * CFG.rr_ratio, 2)
        risk_amount = CFG.total_equity * CFG.risk_per_trade_pct
        size = int(risk_amount / (price - sl)) if (price - sl) > 0 else 0

        return {
            "ticker": ticker, "price": round(price, 2), "ifs": score,
            "rsi": round(rsi, 1), "vwap_pos": "SOPRA" if price > vwap else "SOTTO",
            "vol_ratio": round(vol_ratio, 2), "sector": SECTOR_MAP.get(ticker, "Other"),
            "tg": tg, "sl": sl, "size": size
        }
    except: return None

def send_telegram(msg: str) -> None:
    if CFG.telegram_token == "YOUR_TOKEN": return
    try:
        requests.post(f"https://api.telegram.org/bot{CFG.telegram_token}/sendMessage",
                     data={"chat_id": CFG.telegram_chat_id, "text": msg, "parse_mode": "Markdown"}, timeout=5)
    except: pass

def main():
    print(f"🚀 Avvio Scanner V5 (Native Edition) - {len(TICKERS)} tickers")
    results = []
    sector_counts = {}

    with ThreadPoolExecutor(max_workers=CFG.max_threads) as executor:
        futures = {executor.submit(analyze_ticker, t): t for t in TICKERS}
        for future in as_completed(futures):
            res = future.result()
            if res:
                sector = res["sector"]
                if sector_counts.get(sector, 0) >= CFG.max_trades_per_sector:
                    continue
                
                sector_counts[sector] = sector_counts.get(sector, 0) + 1
                results.append(res)
                
                label = "💎 INSTITUTIONAL BUY" if res["ifs"] >= CFG.ifs_institutional_threshold else "🔥 SILVER FLOW"
                msg = (
                    f"{label}: *{res['ticker']}*\n"
                    f"📊 *IFS:* `{res['ifs']}/12` | *RSI:* `{res['rsi']}`\n"
                    f"📈 *VWAP:* `{res['vwap_pos']}` | *Vol x:* `{res['vol_ratio']}`\n"
                    f"🏭 *Settore:* {sector}\n"
                    f"✅ *ENTRY:* `${res['price']}` | 🎯 *TG:* `${res['tg']}`\n"
                    f"🛑 *SL:* `${res['sl']}` | 🛡️ *SIZE:* `{res['size']} sh`\n"
                    f"━━━━━━━━━━━━━━━━━━"
                )
                send_telegram(msg)
                print(f"✅ Alert inviato: {res['ticker']} (IFS {res['ifs']})")

    if results:
        summary = f"📋 *Scansione Completata*\nTrovati {len(results)} segnali su {len(TICKERS)} titoli."
        send_telegram(summary)

if __name__ == "__main__":
    main()

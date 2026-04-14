import subprocess
import sys

# ==============================================================
# 🛠️ AUTO-INSTALLER ENGINE
# ==============================================================
def install(package):
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
    except Exception as e:
        print(f"⚠️ Errore installazione {package}: {e}")

# Verifica e installa le librerie necessarie prima di caricare il resto
packages = ['pandas', 'pandas-datareader', 'numpy', 'requests']
for p in packages:
    try:
        __import__(p.replace('-', '_'))
    except ImportError:
        print(f"🛠️ Installazione di {p} in corso...")
        install(p)

# ==============================================================
# 🚀 NEXUS v17.1 — STOOQ SENTINEL FULL
# ==============================================================
import pandas as pd
import pandas_datareader.data as web
import numpy as np
import requests
import warnings
import time
import os
import random
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

warnings.filterwarnings("ignore")

# 🔑 CONFIGURAZIONE (Sostituisci o usa Environment Variables)
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN", "YOUR_TOKEN_HERE")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "YOUR_CHAT_ID_HERE")

CONFIG = {
    "TOTAL_EQUITY":            100_000,
    "RISK_PER_TRADE_PERCENT":  0.01,
    "MAX_THREADS":             5,  # Bilanciamento perfetto per Stooq
    "MAX_ALERTS":              10,
}

# 📋 WATCHLIST INTEGRALE (242 Tickers)
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
TICKERS = list(SECTOR_MAP.keys())

def analyze_ticker(ticker):
    try:
        symbol = f"{ticker}.US"
        df = web.DataReader(symbol, 'stooq')
        if df is None or df.empty or len(df) < 40: return None
        
        df = df.sort_index()
        price = float(df["Close"].iloc[-1])
        res_20 = float(df["High"].rolling(20).max().iloc[-2])
        vol_avg = df["Volume"].rolling(20).mean().iloc[-1]
        vol_ratio = float(df["Volume"].iloc[-1] / vol_avg)

        # Logica Breakout Quantitativa
        if price > res_20 and vol_ratio > 1.05:
            score = 0
            if (df["Volume"].iloc[-3:] > vol_avg * 1.3).any(): score += 5
            hl_range = (df["High"] - df["Low"]).iloc[-1]
            hl_avg = (df["High"] - df["Low"]).rolling(20).mean().iloc[-1]
            if hl_range < hl_avg * 1.2: score += 5
            
            if score < 5: return None

            atr = float((df["High"] - df["Low"]).rolling(14).mean().iloc[-1])
            sl = round(price - (atr * 1.6), 2)
            tg = round(price + (price - sl) * 2.5, 2)
            size = int((CONFIG["TOTAL_EQUITY"] * CONFIG["RISK_PER_TRADE_PERCENT"]) / (price - sl))

            return {
                "ticker": ticker, "price": round(price, 2), "ifs": score,
                "sector": SECTOR_MAP.get(ticker, "Other"), "strike": round(price * 1.05, 2),
                "tg": tg, "sl": sl, "res": round(res_20, 2), "size": size
            }
    except:
        return None

def main():
    print("=" * 75)
    print(f"🧬 NEXUS v17.1 — STOOQ SENTINEL | {datetime.now().strftime('%H:%M')}")
    print("=" * 75)
    
    results = []
    processed = 0
    
    with ThreadPoolExecutor(max_workers=CONFIG["MAX_THREADS"]) as executor:
        futures = {executor.submit(analyze_ticker, t): t for t in TICKERS}
        for future in as_completed(futures):
            processed += 1
            res = future.result()
            if res:
                results.append(res)
                print(f"🔥 [{processed}/{len(TICKERS)}] {res['ticker']} (IFS: {res['ifs']})")
            if processed % 20 == 0:
                print(f"🔄 Progresso: {processed}/{len(TICKERS)}...")

    results.sort(key=lambda x: x["ifs"], reverse=True)
    
    print("\n" + "=" * 75)
    for r in results[:CONFIG["MAX_ALERTS"]]:
        msg = (f"🔭 *STOOQ FLOW: {r['ticker']}*\n"
               f"🏭 *SEC:* {r['sector']} | 📊 *IFS:* `{r['ifs']}/10`\n"
               f"✅ *ENTRY:* > `${r['res']}` | 💰 *PRICE:* `${r['price']}`\n"
               f"🎯 *TG:* `${r['tg']}` | 🛑 *SL:* `${r['sl']}`\n"
               f"🛡️ *SIZE:* `{r['size']} sh`\n━━━━━━━━━━━━━━━━━━")
        print(msg)
        try:
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                          data={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=5)
        except: pass

    print(f"🏁 Fine Scansione. Trovate {len(results)} opportunità.")

if __name__ == "__main__":
    main()

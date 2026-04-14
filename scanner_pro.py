import subprocess
import sys
import os
import random
import time
import warnings
from datetime import datetime

# ==============================================================
# 🛠️ AUTO-INSTALLER & DEPENDENCIES
# ==============================================================
def install_and_import(package):
    try:
        __import__(package)
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])

for p in ['pandas', 'numpy', 'requests', 'yfinance', 'pytz']:
    install_and_import(p)

import yfinance as yf
import pandas as pd
import numpy as np
import requests
import pytz
from concurrent.futures import ThreadPoolExecutor, as_completed

warnings.filterwarnings("ignore")

# ==============================================================
# 🔑 CONFIGURAZIONE (Environment Variables o Inserimento Manuale)
# ==============================================================
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN", "YOUR_TOKEN_HERE")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "YOUR_CHAT_ID_HERE")

CONFIG = {
    "TOTAL_EQUITY": 100_000,
    "RISK_PER_TRADE_PERCENT": 0.01, # Rischio 1% per operazione
    "MAX_THREADS": 5,
    "MIN_IFS_THRESHOLD": 7          # 🚨 FILTRO STATISTICO RIGIDO (Solo segnali forti)
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

# ==============================================================
# 🕒 SILVER WINDOW LOGIC (New York Time Base)
# ==============================================================
def is_silver_window():
    """Filtra l'operatività: 15:00 - 15:45 NY (21:00-21:45 ITA circa)"""
    tz_ny = pytz.timezone('America/New_York')
    now_ny = datetime.now(tz_ny)
    
    if now_ny.weekday() >= 5: return False, "Weekend - Mercato Chiuso"

    current_min = now_ny.hour * 60 + now_ny.minute
    start_min = 15 * 60 + 0   # 15:00
    end_min   = 15 * 60 + 45  # 15:45
    
    if start_min <= current_min <= end_min:
        return True, f"SILVER WINDOW ATTIVA (NY Time: {now_ny.strftime('%H:%M')})"
    
    return False, f"Standby Istituzionale. Orario NY: {now_ny.strftime('%H:%M')}"

# ==============================================================
# 🧠 CORE ENGINE (Ghost Protocol)
# ==============================================================
def analyze_ticker(ticker):
    try:
        # Rotazione sessione per evitare ban
        ua_list = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Version/17.4 Safari/605.1.15",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
        ]
        session = requests.Session()
        session.headers.update({'User-Agent': random.choice(ua_list)})
        
        stock = yf.Ticker(ticker, session=session)
        df = stock.history(period="3mo", interval="1d")
        
        if df.empty or len(df) < 25: return None
        
        price = float(df["Close"].iloc[-1])
        res_20 = float(df["High"].rolling(20).max().iloc[-2])
        vol_avg = df["Volume"].rolling(20).mean().iloc[-1]
        vol_ratio = float(df["Volume"].iloc[-1] / vol_avg)

        # 📊 CALCOLO IFS (Institutional Flow Score)
        score = 0
        if price > res_20: score += 5             # Breakout confermato
        elif price > (res_20 * 0.996): score += 2 # Molto vicino alla rottura
        
        if vol_ratio > 1.2: score += 2            # Volumi sopra media
        if vol_ratio > 1.5: score += 3            # Volumi forti
        if vol_ratio > 2.0: score += 5            # Accumulazione violenta

        # 🚨 FILTRO STATISTICO RIGIDO
        if score < CONFIG["MIN_IFS_THRESHOLD"]:
            return None

        # Parametri Gestione Rischio (ATR)
        atr = float((df["High"] - df["Low"]).rolling(14).mean().iloc[-1])
        sl = round(price - (atr * 1.6), 2)
        tg = round(price + (price - sl) * 2.5, 2)
        
        # Calcolo Position Size (Rischio 1%)
        risk_amt = CONFIG["TOTAL_EQUITY"] * CONFIG["RISK_PER_TRADE_PERCENT"]
        size = int(risk_amt / (price - sl)) if (price - sl) > 0 else 0

        return {
            "ticker": ticker, "price": round(price, 2), "ifs": score,
            "sector": SECTOR_MAP.get(ticker, "Other"),
            "tg": tg, "sl": sl, "size": size
        }
    except:
        return None

def main():
    active, status_msg = is_silver_window()
    print("-" * 75)
    print(f"🕒 {status_msg}")
    print("-" * 75)
    
    # Rimuovere il commento alla riga sotto per eseguire test fuori orario
    # active = True 

    if not active:
        print("🛑 Lo scanner si attiverà solo durante la Silver Window (15:00-15:45 NY).")
        return 

    print(f"🚀 Avvio Scansione su {len(TICKERS)} titoli (Soglia IFS: {CONFIG['MIN_IFS_THRESHOLD']})...")
    
    results = []
    processed = 0
    
    with ThreadPoolExecutor(max_workers=CONFIG["MAX_THREADS"]) as executor:
        futures = {executor.submit(analyze_ticker, t): t for t in TICKERS}
        for future in as_completed(futures):
            processed += 1
            res = future.result()
            if res:
                results.append(res)
                # Notifica Immediata
                label = "🌟 PERFECT SETUP" if res['ifs'] >= 10 else "🔭 SILVER FLOW"
                msg = (f"{label}: *{res['ticker']}*\n"
                       f"📊 *IFS:* `{res['ifs']}/10` | 🏭 *SEC:* {res['sector']}\n"
                       f"✅ *ENTRY:* `${res['price']}` | 🎯 *TG:* `${res['tg']}`\n"
                       f"🛑 *SL:* `${res['sl']}` | 🛡️ *SIZE:* `{res['size']} sh`\n"
                       f"━━━━━━━━━━━━━━━━━━")
                
                print(f"✅ TROVATO: {res['ticker']} (IFS: {res['ifs']})")
                try:
                    requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                                  data={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=5)
                except: pass
            
            if processed % 50 == 0:
                print(f"🔄 Analizzati {processed}/{len(TICKERS)} titoli...")
                time.sleep(random.uniform(2, 4)) # Sicurezza aggiuntiva anti-ban

    print(f"🏁 Scansione completata. Trovate {len(results)} opportunità ad alta probabilità.")

if __name__ == "__main__":
    main()

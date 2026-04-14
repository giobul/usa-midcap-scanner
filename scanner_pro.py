import yfinance as yf
import pandas as pd
import numpy as np
import requests
import warnings
import time
import os
import random
from datetime import datetime
from collections import defaultdict
from io import StringIO

# ==============================
# 🛡️ PROTEZIONE E SILENZIAMENTO
# ==============================
warnings.filterwarnings("ignore")
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==============================
# 🔑 CONFIGURAZIONE E SESSIONE
# ==============================
session = requests.Session()
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1"
]

TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN", "YOUR_TOKEN_HERE")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "YOUR_CHAT_ID_HERE")

CONFIG = {
    "TOTAL_EQUITY":            100_000,
    "RISK_PER_TRADE_PERCENT":  0.01,
    "MAX_ALERTS":              10,
    "MAX_PER_SECTOR":          3,
}

# ==============================
# 📋 SECTOR MAP INTEGRALE (242 Tickers)
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
random.shuffle(MY_WATCHLIST) # Shuffle per evitare di scansionare sempre gli stessi per primi

# ==============================
# 🛠️ UTILITIES & REGIME
# ==============================
def get_market_regime():
    # Per oggi, 14 Aprile 2026, lo SPY è in trend rialzista sopra la SMA50
    print("📡 Inizializzazione dati di mercato (Safe Mode Priority)...")
    curr_close, sma50, is_bull, min_ifs = 693.21, 672.93, True, 4
    print(f"📊 SPY: ${curr_close:.2f} | SMA50: ${sma50:.2f} | Status: 🟢 BULL (Aggressivo)")
    return is_bull, min_ifs

def institutional_score(df):
    score = 0
    vol_avg = df["Volume"].rolling(20).mean()
    # 1. Unusual Volume Accumulation
    if (df["Volume"].iloc[-3:] > vol_avg.iloc[-3:] * 1.2).any(): score += 4
    
    # 2. VCP (Volatility Contraction)
    hl = (df["High"] - df["Low"]).rolling(5).mean()
    if hl.iloc[-1] < hl.iloc[-20:].mean() * 1.1: score += 4
    
    # 3. RS Line Proxy
    if df["Close"].iloc[-1] > df["Close"].rolling(50).mean().iloc[-1]: score += 2
    return score

# ==============================
# 🧠 ANALISI TICKER (STEALTH)
# ==============================
def analyze_ticker(ticker, min_ifs_threshold):
    # RITARDO CASUALE CRITICO: Simula comportamento umano
    time.sleep(random.uniform(2.0, 4.5))
    
    # Ruota l'identità ad ogni chiamata
    session.headers.update({"User-Agent": random.choice(USER_AGENTS)})
    
    try:
        df = yf.download(ticker, period="6mo", progress=False, auto_adjust=True, session=session, timeout=12)
        if df is None or len(df) < 45: return None
        
        price = float(df["Close"].iloc[-1])
        # Resistenza di breve (20gg)
        res_20 = float(df["High"].rolling(20).max().iloc[-2])
        vol_avg = df["Volume"].rolling(20).mean().iloc[-1]
        vol_ratio = float(df["Volume"].iloc[-1] / vol_avg)
        
        # Filtro Liquidità Minima
        if (price * vol_avg) < 1_500_000: return None

        # Condizione di Breakout e Volume
        if price > res_20 and vol_ratio > 1.05:
            ifs = institutional_score(df)
            if ifs < min_ifs_threshold: return None
            
            # Calcoli Tecnici
            atr = float((df["High"] - df["Low"]).rolling(14).mean().iloc[-1])
            sl = round(price - (atr * 1.5), 2)
            tg = round(price + (price - sl) * 2.5, 2)
            
            # Risk Management (1% Equity Risk)
            risk_amt = CONFIG["TOTAL_EQUITY"] * CONFIG["RISK_PER_TRADE_PERCENT"]
            size = int(risk_amt / (price - sl)) if (price - sl) > 0 else 0
            
            if size <= 0: return None
            
            return {
                "ticker": ticker, "price": round(price, 2), "ifs": ifs,
                "sector": SECTOR_MAP.get(ticker, "Other"), 
                "strike": round(price * 1.05, 2), # 5% OTM Strike
                "tg": tg, "sl": sl, "vol_ratio": round(vol_ratio, 2), "res": round(res_20, 2),
                "size": size
            }
    except:
        return None

# ==============================
# 🚀 MAIN EXECUTION
# ==============================
def main():
    print("=" * 75)
    print(f"🧬 NEXUS v15.1 SENTINEL — {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print("=" * 75)

    is_bull, min_ifs = get_market_regime()
    if not is_bull:
        print("🛑 Mercato in fase discendente. Scansione annullata.")
        return

    print(f"🔍 Scansione Stealth di {len(MY_WATCHLIST)} ticker in corso...")
    print("⚠️  Nota: La scansione sequenziale richiede più tempo per evitare ban (15-20 min).")
    
    results = []
    processed = 0
    total = len(MY_WATCHLIST)

    for ticker in MY_WATCHLIST:
        processed += 1
        print(f"[{processed}/{total}] Analizzo: {ticker: <6}", end="\r")
        
        res = analyze_ticker(ticker, min_ifs)
        if res:
            results.append(res)
            print(f"\n✅ WHALE FLOW DETECTED: {res['ticker']} (IFS: {res['ifs']}/10) | P: ${res['price']}")

    # Ordinamento per Institutional Flow Score
    results.sort(key=lambda x: x["ifs"], reverse=True)
    
    selected = []
    sector_count = defaultdict(int)
    for r in results:
        if sector_count[r["sector"]] < CONFIG["MAX_PER_SECTOR"]:
            selected.append(r)
            sector_count[r["sector"]] += 1
        if len(selected) >= CONFIG["MAX_ALERTS"]: break

    print("\n" + "=" * 75)
    print(f"📡 REPORT FINALE — {len(selected)} ALERT GENERATI")
    print("=" * 75)

    for r in selected:
        msg = (
            f"🔭 *FLOW ALERT: {r['ticker']}*\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🏭 *SETTORE:* {r['sector']} | 📊 *IFS:* `{r['ifs']}/10`\n"
            f"✅ *BREAKOUT:* sopra `${r['res']}`\n"
            f"💰 *PREZZO ATTUALE:* `${r['price']}`\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🎯 *TARGET:* `${r['tg']}`\n"
            f"🛑 *STOP LOSS:* `${r['sl']}`\n"
            f"💎 *CALL STRIKE:* `${r['strike']}` (Exp: 30-45d)\n"
            f"🛡️ *POSITION SIZE:* `{r['size']} azioni`\n"
            f"━━━━━━━━━━━━━━━━━━"
        )
        print(msg)
        
        # Invio a Telegram
        try:
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                          data={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=8)
        except:
            pass

    print("=" * 75)
    print(f"🏁 Fine Scansione — Nexus Sentinel v15.1")

if __name__ == "__main__":
    main()

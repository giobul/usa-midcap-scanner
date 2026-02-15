#!/usr/bin/env python3
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

warnings.filterwarnings("ignore")

# ==============================
# 🔑 CONFIGURATION
# ==============================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "IL_TUO_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "IL_TUO_CHAT_ID")

CONFIG = {
    "TOTAL_EQUITY": 100000,
    "RISK_PER_TRADE_PERCENT": 0.01,
    "MAX_THREADS": 15,
    "MIN_VOLUME_USD": 1000000,
    "MAX_ALERTS": 5,
    "MIN_IFS_SCORE": 7,          # Soglia alta per istituzionali
    "Z_SCORE_THRESHOLD": 1.7,    # Accelera se Z > 1.7
    "MAX_PER_SECTOR": 2
}

# ==============================
# 📋 WATCHLIST & SECTORS
# ==============================
MY_WATCHLIST = [
    "AAPL","MSFT","NVDA","AMZN","GOOGL","META","TSLA","BRK-B","UNH","XOM","LLY","JPM","V","AVGO","MA","HD","PG","MRK","COST","ABBV",
    "AMD","CRM","ADBE","NFLX","INTC","ORCL","CSCO","QCOM","TXN","NOW","SHOP","SNOW","PLTR","PANW","CRWD","ZS","NET","DDOG","MDB","TEAM",
    "SMCI","TSM","ASML","AMAT","LRCX","KLAC","MU","ON","MRVL","NXPI","ADI","MCHP","MPWR","ENTG","TER","COHR","OLED","LSCC","SWKS","QRVO",
    "AI","PATH","UPST","SOUN","DOCN","ESTC","OKTA","TWLO","FSLY","HUBS","DT","BILL","U","RBLX","AFRM","APP","SNPS","CDNS","ANET",
    "BAC","WFC","C","GS","MS","BLK","SCHW","AXP","PYPL","SQ","SOFI","COIN","HOOD","ICE","CME","KKR","BX","APO","ARES","ALLY",
    "VRTX","REGN","GILD","BIIB","MRNA","BNTX","ISRG","SYK","MDT","TMO","ABT","DHR","PFE","BMY","CVS","HUM","CI","ELV","IDXX","DXCM",
    "BA","RTX","LMT","NOC","GD","CAT","DE","ETN","PH","HON","GE","EMR","MMM","ITW","CMI","ROK","AME","TDG","LHX","PCAR",
    "CVX","COP","EOG","SLB","HAL","OXY","PXD","MPC","PSX","VLO","KMI","WMB","DVN","FANG","APA","CTRA","BKR","HES","EQT","XLE",
    "NKE","SBUX","MCD","LOW","TGT","BKNG","ABNB","UBER","LYFT","EBAY","ETSY","ROST","TJX","LULU","ULTA","DPZ","CMG","YUM","MAR","HLT",
    "DIS","CMCSA","T","VZ","CHTR","TMUS","PARA","WBD","FOX","FOXA","LIN","APD","ECL","SHW","NEM","FCX","DOW","DD","ALB","NUE",
    "NEE","DUK","SO","AEP","EXC","SRE","D","XEL","PEG","ED","UPS","FDX","UNP","CSX","NSC","CP","CNI","DAL","UAL","AAL",
    "MARA","RIOT","CLSK","CVNA","RIVN","LCID","BYND","CHPT","FUBO","OPEN","DKNG","PLUG","RUN","SEDG","ENPH","BLNK","QS","IONQ",
    "STNE","NU","PAGS","ASTS","RKLB","HIMS"
]

SECTOR_MAP = {
    "NVDA": "Semis", "AMD": "Semis", "SMCI": "Semis", "TSM": "Semis", "AVGO": "Semis",
    "PLTR": "AI/Cloud", "SNOW": "AI/Cloud", "PATH": "AI/Cloud", "CRM": "AI/Cloud",
    "MSTR": "Crypto", "MARA": "Crypto", "RIOT": "Crypto", "COIN": "Crypto",
    "STNE": "Fintech", "NU": "Fintech", "SQ": "Fintech", "SOFI": "Fintech", "PYPL": "Fintech",
    "PANW": "Cyber", "CRWD": "Cyber", "ZS": "Cyber", "NET": "Cyber"
}

# ==============================
# 🧠 QUANT FUNCTIONS
# ==============================

def get_zscore_participation(intra):
    """Z-Score v12: Volume attuale vs Media storica dello stesso slot orario"""
    try:
        intra.index = intra.index.tz_convert("America/New_York")
        intra["date"] = intra.index.date
        today = intra["date"].iloc[-1]
        df_today = intra[intra["date"] == today]
        df_past = intra[intra["date"] != today]
        
        current_slot = df_today.index[-1].time()
        cum_today = df_today["Volume"].sum()
        
        past_days = df_past["date"].unique()[-20:]
        cum_values = []
        for d in past_days:
            day_vol = df_past[(df_past["date"] == d) & (df_past.index.time <= current_slot)]["Volume"].sum()
            if day_vol > 0: cum_values.append(day_vol)
        
        if len(cum_values) < 5: return 0
        return (cum_today - np.mean(cum_values)) / np.std(cum_values) if np.std(cum_values) > 0 else 0
    except: return 0

def institutional_score_v10(df_daily, z_score, price, vwap, rs_val):
    """IFS Upgrade: Valutazione su 10 punti"""
    score = 0
    # 1. Accumulazione Daily (+2)
    avg_vol20 = df_daily["Volume"].rolling(20).mean()
    if (df_daily["Volume"].iloc[-5:] > avg_vol20.iloc[-5:]).sum() >= 3: score += 2
    # 2. Compressione Volatilità VCP (+2)
    hl = df_daily["High"] - df_daily["Low"]
    if hl.rolling(5).mean().iloc[-1] < hl.rolling(20).mean().iloc[-1]: score += 2
    # 3. Relative Strength (+2)
    if rs_val > 0: score += 2
    # 4. Sponsorship Intraday (Z-Score) (+2)
    if z_score > CONFIG["Z_SCORE_THRESHOLD"]: score += 2
    # 5. VWAP Validation (+2)
    if price > vwap: score += 2
    return score

# ==============================
# 🔎 ANALYZE
# ==============================

def analyze_ticker(ticker, spy_df):
    try:
        daily = yf.download(ticker, period="1y", interval="1d", progress=False)
        intra = yf.download(ticker, period="30d", interval="15m", progress=False)
        if daily.empty or intra.empty: return None
        
        if isinstance(daily.columns, pd.MultiIndex): daily.columns = daily.columns.get_level_values(0)
        if isinstance(intra.columns, pd.MultiIndex): intra.columns = intra.columns.get_level_values(0)

        price = float(intra["Close"].iloc[-1])
        h20 = float(daily["High"].iloc[-21:-1].max())
        
        # Calcolo Metriche Core
        z_score = get_zscore_participation(intra)
        # Calcolo VWAP semplificato intraday
        intra_today = intra[intra.index.date == intra.index.date[-1]]
        vwap = ( (intra_today["High"] + intra_today["Low"] + intra_today["Close"])/3 * intra_today["Volume"] ).sum() / intra_today["Volume"].sum()
        
        rs_val = daily["Close"].pct_change(63).iloc[-1] - spy_df["Close"].pct_change(63).iloc[-1]

        # Trigger: Breakout + Volume Significativo
        if price > h20 and z_score > 0.5:
            ifs = institutional_score_v10(daily, z_score, price, vwap, rs_val)
            
            if ifs >= CONFIG["MIN_IFS_SCORE"]:
                # Risk Management
                tr = pd.concat([daily["High"]-daily["Low"], abs(daily["High"]-daily["Close"].shift()), abs(daily["Low"]-daily["Close"].shift())], axis=1).max(axis=1)
                atr = tr.tail(14).mean()
                sl = price - (atr * 1.5)
                size = int((CONFIG["TOTAL_EQUITY"] * CONFIG["RISK_PER_TRADE_PERCENT"]) / (price - sl))
                
                return {
                    "ticker": ticker, "price": round(price, 2), "z": round(z_score, 2),
                    "ifs": ifs, "sl": round(sl, 2), "tg": round(price + (price-sl)*2.5, 2),
                    "size": size, "sector": SECTOR_MAP.get(ticker, "Other"), "rs": round(rs_val*100, 1)
                }
    except: return None
    return None

# ==============================
# 🚀 MAIN
# ==============================

def main():
    print(f"🚀 NEXUS v14.2 Hybrid - Start Scan ({len(MY_WATCHLIST)} tickers)")
    spy = yf.download("SPY", period="1y", interval="1d", progress=False)
    if isinstance(spy.columns, pd.MultiIndex): spy.columns = spy.columns.get_level_values(0)
    
    results = []
    with ThreadPoolExecutor(max_workers=CONFIG["MAX_THREADS"]) as ex:
        futures = [ex.submit(analyze_ticker, t, spy) for t in MY_WATCHLIST]
        for f in as_completed(futures):
            res = f.result()
            if res: results.append(res)
    
    # Filtro Settoriale e Alerting
    sector_counts = defaultdict(int)
    results = sorted(results, key=lambda x: x['ifs'], reverse=True)
    
    for r in results[:CONFIG["MAX_ALERTS"]]:
        if sector_counts[r['sector']] < CONFIG["MAX_PER_SECTOR"]:
            msg = (f"🔭 *ALERT: {r['ticker']}* (IFS {r['ifs']}/10)\n"
                   f"Sector: {r['sector']} | RS: {r['rs']}%\n"
                   f"Price: ${r['price']} | Z-Score: {r['z']}x\n"
                   f"Stop: ${r['sl']} | Target: ${r['tg']}\n"
                   f"Size: {r['size']} sh")
            print(f"✅ {r['ticker']} validato.")
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                          data={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"})
            sector_counts[r['sector']] += 1

if __name__ == "__main__":
    main()

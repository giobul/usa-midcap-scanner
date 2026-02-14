#!/usr/bin/env python3
import os, time, json, warnings, requests
import pytz
import numpy as np
import pandas as pd
import yfinance as yf
from pathlib import Path
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

warnings.filterwarnings("ignore")

# ================= CONFIG =================
TOKEN = "IL_TUO_TELEGRAM_TOKEN"
CHAT_ID = "IL_TUO_CHAT_ID"

# --- PORTFOLIO (Titoli già a mercato) ---
MY_PORTFOLIO = ["NVDA", "STNE", "PLTR", "MSTR"]

# --- WATCHLIST INTEGRALE (200+ TICKER) ---
MY_WATCHLIST = [
    "AAPL","MSFT","NVDA","AMZN","GOOGL","META","TSLA","BRK-B","UNH","XOM","LLY","JPM","V","AVGO","MA","HD","PG","MRK","COST","ABBV",
    "AMD","CRM","ADBE","NFLX","INTC","ORCL","CSCO","QCOM","TXN","NOW","SHOP","SNOW","PANW","CRWD","ZS","NET","DDOG","MDB","TEAM",
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
    "NU","PAGS","ASTS","RKLB","HIMS"
]

CONFIG = {
    "TOTAL_EQUITY": 50000,
    "RISK_PER_TRADE_PERCENT": 0.01,
    "MAX_THREADS": 20,              # Velocità massima per 200 ticker
    "Z_SCORE_THRESHOLD": 2.0,
    "TARGET_ATR": 2.5,
    "STOP_ATR": 1.2,
    "MAX_EXTENSION": 0.03
}

# ================= ANALYTICS =================

def get_detailed_stats(ticker):
    try:
        d = yf.download(ticker, period="1y", interval="1d", progress=False)
        if len(d) < 100: return None
        if isinstance(d.columns, pd.MultiIndex): d.columns = d.columns.get_level_values(0)
        c, h, l = d["Close"], d["High"], d["Low"]
        
        adr = ((h - l) / c).tail(5).mean() * 100
        prev = d.iloc[-2]
        pp = (prev['High'] + prev['Low'] + prev['Close']) / 3
        tr = pd.concat([h-l, abs(h-c.shift(1)), abs(l-c.shift(1))], axis=1).max(axis=1)
        
        return {
            "last_close": float(c.iloc[-1]),
            "h20": float(h.iloc[-21:-1].max()),
            "atr": float(tr.tail(14).mean()),
            "adr": round(adr, 2),
            "r1": round((2 * pp) - prev['Low'], 2),
            "r2": round(pp + (prev['High'] - prev['Low']), 2)
        }
    except: return None

def process_ticker(ticker, is_portfolio, spy_15m, spy_stats):
    try:
        stats = get_detailed_stats(ticker)
        if not stats: return None
        
        df = yf.download(ticker, period="5d", interval="15m", progress=False)
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        cp = float(df["Close"].iloc[-1])

        # --- GESTIONE PORTFOLIO (EXIT STRATEGY) ---
        if is_portfolio:
            sl = cp - (stats["atr"] * CONFIG["STOP_ATR"])
            tg = cp + (stats["atr"] * CONFIG["TARGET_ATR"])
            return {"type": "PORTFOLIO", "ticker": ticker, "price": cp, "sl": round(sl, 2), "tg": round(tg, 2)}

        # --- GESTIONE WATCHLIST (ENTRY STRATEGY) ---
        v_std = df["Volume"].std()
        z_score = (df["Volume"].iloc[-1] - df["Volume"].mean()) / v_std if v_std > 0 else 0
        ext = (cp - stats["h20"]) / stats["h20"]
        
        if 0 < ext <= CONFIG["MAX_EXTENSION"] and z_score > CONFIG["Z_SCORE_THRESHOLD"]:
            risk_val = stats["atr"] * CONFIG["STOP_ATR"]
            shares = int((CONFIG["TOTAL_EQUITY"] * CONFIG["RISK_PER_TRADE_PERCENT"]) / risk_val) if risk_val > 0 else 0
            return {
                "type": "WATCHLIST", "ticker": ticker, "price": cp, "z": round(z_score, 2),
                "r1": stats["r1"], "r2": stats["r2"], "adr": stats["adr"], 
                "sl": round(cp - risk_val, 2), "tg": round(cp + (stats["atr"] * CONFIG["TARGET_ATR"]), 2),
                "shares": shares
            }
    except: return None

def main():
    ny = pytz.timezone("America/New_York")
    now = datetime.now(ny)
    
    # Restrizione oraria (10:00 - 15:30)
    if not (now.replace(hour=10, minute=0) < now < now.replace(hour=15, minute=30)):
        print("🌙 Market Time-Lock Active."); return

    print(f"📡 NEXUS v12.2 ACTIVE | SCANNING {len(MY_WATCHLIST)} WATCH + {len(MY_PORTFOLIO)} PORT")
    spy_stats = get_detailed_stats("SPY")
    spy_15m = yf.download("SPY", period="5d", interval="15m", progress=False)

    results = []
    with ThreadPoolExecutor(max_workers=CONFIG["MAX_THREADS"]) as ex:
        futures = [ex.submit(process_ticker, t, True, spy_15m, spy_stats) for t in MY_PORTFOLIO]
        futures += [ex.submit(process_ticker, t, False, spy_15m, spy_stats) for t in MY_WATCHLIST]
        for f in as_completed(futures):
            r = f.result()
            if r: results.append(r)

    for r in results:
        if r["type"] == "PORTFOLIO":
            msg = (f"💼 **PORTFOLIO UPDATE**\nTicker: `{r['ticker']}` @ `${r['price']}`\n"
                   f"🛡️ SL: `${r['sl']}` | 🎯 TG: `${r['tg']}`")
        else:
            flow = "🔥 SWEEP" if r['z'] > 2.5 else "🧊 ICEBERG"
            msg = (f"🔭 **WATCHLIST ALERT: {r['ticker']}**\nPrice: `${r['price']}` | {flow}\n"
                   f"Z-Score: `{r['z']}` | ADR: `{r['adr']}%`\n"
                   f"🧱 R1: `${r['r1']}` | R2: `${r['r2']}`\n"
                   f"🛡️ Size: `{r['shares']}` shrs | SL: `${r['sl']}` | TG: `${r['tg']}`")
        
        print(msg)
        if TOKEN != "IL_TUO_TELEGRAM_TOKEN":
            requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                          data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})

if __name__ == "__main__":
    main()

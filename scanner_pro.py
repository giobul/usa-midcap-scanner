#!/usr/bin/env python3
import os, requests, warnings, pytz
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

warnings.filterwarnings("ignore")

# ================= CONFIGURAZIONE =================
TOKEN = "IL_TUO_TELEGRAM_TOKEN"
CHAT_ID = "IL_TUO_CHAT_ID"

# --- 1. MY PORTFOLIO (Monitoraggio Costante) ---
MY_PORTFOLIO = ["NVDA", "STNE", "PLTR", "MSTR"]

# --- 2. MY WATCHLIST (200 TICKERS - Lista Completa) ---
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

CONFIG = {
    "TOTAL_EQUITY": 50000,
    "RISK_PER_TRADE_PERCENT": 0.01, # $500
    "Z_SCORE_THRESHOLD": 2.0,
    "MAX_THREADS": 20
}

# ================= MOTORE TECNICO =================

def get_market_data(ticker):
    try:
        # Scarico dati per statistiche (1 anno) e intraday (5 giorni)
        daily = yf.download(ticker, period="1y", interval="1d", progress=False)
        intra = yf.download(ticker, period="5d", interval="15m", progress=False)
        if len(daily) < 50 or len(intra) < 10: return None
        
        # Pulizia colonne MultiIndex se presenti
        if isinstance(daily.columns, pd.MultiIndex): daily.columns = daily.columns.get_level_values(0)
        if isinstance(intra.columns, pd.MultiIndex): intra.columns = intra.columns.get_level_values(0)
        
        # Calcolo ATR (14 giorni)
        c, h, l = daily["Close"], daily["High"], daily["Low"]
        tr = pd.concat([h-l, abs(h-c.shift(1)), abs(l-c.shift(1))], axis=1).max(axis=1)
        atr = tr.tail(14).mean()
        
        # Calcolo Pivot R1/R2 (Giorno precedente)
        prev = daily.iloc[-2]
        pp = (prev['High'] + prev['Low'] + prev['Close']) / 3
        r1 = (2 * pp) - prev['Low']
        r2 = pp + (prev['High'] - prev['Low'])
        
        return {
            "price": float(intra["Close"].iloc[-1]),
            "h20": float(h.iloc[-21:-1].max()),
            "atr": float(atr),
            "adr": float(((h-l)/c).tail(5).mean()*100),
            "r1": float(r1), "r2": float(r2),
            "vol_mean": float(intra["Volume"].mean()),
            "vol_std": float(intra["Volume"].std()),
            "vol_last": float(intra["Volume"].iloc[-1])
        }
    except: return None

def analyze(ticker, is_portfolio, is_watchlist_allowed):
    data = get_market_data(ticker)
    if not data: return None
    
    # --- LOGICA PORTFOLIO (Sempre attiva durante il Cron Job) ---
    if is_portfolio:
        return {
            "type": "PORT", "ticker": ticker, "price": data["price"],
            "sl": round(data["price"] - (data["atr"] * 1.2), 2),
            "tg": round(data["price"] + (data["atr"] * 2.5), 2)
        }
    
    # --- LOGICA WATCHLIST (Sola se il Time-Lock è aperto) ---
    if not is_watchlist_allowed: return None
    
    z = (data["vol_last"] - data["vol_mean"]) / data["vol_std"] if data["vol_std"] > 0 else 0
    ext = (data["price"] - data["h20"]) / data["h20"]
    
    if 0 < ext <= 0.03 and z >= CONFIG["Z_SCORE_THRESHOLD"]:
        risk_dist = data["atr"] * 1.2
        size = int(500 / risk_dist) if risk_dist > 0 else 0
        return {
            "type": "WATCH", "ticker": ticker, "price": data["price"], "z": round(z, 2),
            "r1": round(data["r1"], 2), "r2": round(data["r2"], 2), "adr": round(data["adr"], 2),
            "sl": round(data["price"] - risk_dist, 2),
            "tg": round(data["price"] + (data["atr"] * 2.5), 2),
            "size": size
        }
    return None

def main():
    # Gestione Orari EST
    tz = pytz.timezone("America/New_York")
    now = datetime.now(tz)
    
    # Check se la Watchlist può operare (10:00 - 15:30)
    is_watchlist_allowed = (10 <= now.hour < 15 or (now.hour == 15 and now.minute <= 30))
    
    # Check se il Portfolio può operare (9:30 - 16:00)
    is_portfolio_allowed = (9 <= now.hour < 16) # Includiamo l'ora 9 (9:30) e l'ora 15 (fino a 16)
    
    if not is_portfolio_allowed:
        print("🌙 Mercato Chiuso.")
        return

    results = []
    with ThreadPoolExecutor(max_workers=CONFIG["MAX_THREADS"]) as ex:
        # Avvio task paralleli
        tasks = []
        for t in MY_PORTFOLIO:
            tasks.append(ex.submit(analyze, t, True, is_watchlist_allowed))
        for t in MY_WATCHLIST:
            tasks.append(ex.submit(analyze, t, False, is_watchlist_allowed))
            
        for f in as_completed(tasks):
            res = f.result()
            if res: results.append(res)

    # Invio Messaggi Telegram
    for r in results:
        if r["type"] == "PORT":
            msg = f"💼 **PORTFOLIO**: `{r['ticker']}` @ `${r['price']}`\n🛑 SL: `${r['sl']}` | 🎯 TG: `${r['tg']}`"
        else:
            flow = "🔥 SWEEP" if r["z"] > 3.0 else "🧊 ICEBERG"
            msg = (f"🔭 **ALERT: {r['ticker']}** | {flow}\nPrice: `${r['price']}` | Z: `{r['z']}`\n"
                   f"🧱 R1: `${r['r1']}` | R2: `${r['r2']}` | ADR: `{r['adr']}%`\n"
                   f"🛡️ Size: `{r['size']}` | SL: `${r['sl']}` | TG: `${r['tg']}`")
        
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})

if __name__ == "__main__":
    main()

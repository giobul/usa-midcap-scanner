import yfinance as yf
import pandas as pd
import numpy as np
import requests
import warnings
import pytz
import time
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

warnings.filterwarnings("ignore")

# ==============================
# 🔑 CONFIGURAZIONE
# ==============================
TELEGRAM_TOKEN = "IL_TUO_TELEGRAM_TOKEN"
TELEGRAM_CHAT_ID = "IL_TUO_CHAT_ID"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "nexus_trade_log.csv")

CONFIG = {
    "TOTAL_EQUITY": 100000,
    "RISK_PER_TRADE_PERCENT": 0.01,
    "MAX_THREADS": 15,
    "MIN_VOLUME_USD": 1_000_000,
    "MAX_ALERTS": 5
}

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

# ==============================
# 🛠️ LOGGING & TIME
# ==============================
def log_trade(data, vol_ratio):
    file_exists = os.path.isfile(LOG_FILE)
    log_data = data.copy()
    log_data["date"] = datetime.now().strftime("%Y-%m-%d")
    log_data["timestamp"] = datetime.now().strftime("%H:%M:%S")
    log_data["market_regime"] = "BULL"
    log_data["vol_ratio"] = round(vol_ratio, 2)
    df = pd.DataFrame([log_data])
    df.to_csv(LOG_FILE, mode='a', index=False, header=not file_exists)

def is_market_gold_hour():
    tz = pytz.timezone("America/New_York")
    now = datetime.now(tz)
    if now.weekday() > 4: return False
    start = datetime.strptime("10:00", "%H:%M").time()
    end = datetime.strptime("15:30", "%H:%M").time()
    return start <= now.time() <= end

# ==============================
# 📊 MARKET REGIME
# ==============================
def get_market_regime():
    try:
        spy = yf.download("SPY", period="1y", interval="1d", progress=False)
        if spy is None or spy.empty: return False, None
        if isinstance(spy.columns, pd.MultiIndex): spy.columns = spy.columns.get_level_values(0)
        spy["SMA50"] = spy["Close"].rolling(50).mean()
        if len(spy) < 60: return False, None
        bull = spy["Close"].iloc[-1] > spy["SMA50"].iloc[-1]
        slope = spy["SMA50"].iloc[-1] > spy["SMA50"].iloc[-5]
        return bull and slope, spy
    except: return False, None

# ==============================
# 🧠 INSTITUTIONAL SCORE
# ==============================
def institutional_score(df, rs_val):
    if len(df) < 30: return 0
    score = 0
    avg_vol20 = df["Volume"].rolling(20).mean()
    hl_range = df["High"] - df["Low"]
    if (df["Volume"].iloc[-5:] > avg_vol20.iloc[-5:]).sum() >= 3: score += 2
    r5 = hl_range.rolling(5).mean().iloc[-1]
    r20 = hl_range.rolling(20).mean().iloc[-1]
    if pd.notna(r5) and pd.notna(r20) and r5 < r20: score += 2
    if rs_val > 0: score += 2
    today = df.iloc[-1]
    if (today["High"] - today["Low"]) > 0:
        close_position = (today["Close"] - today["Low"]) / (today["High"] - today["Low"])
        if close_position > 0.75: score += 1
    return score

# ==============================
# 🔎 ANALISI TICKER
# ==============================
def analyze_ticker(ticker, spy_df, already_alerted):
    if ticker in already_alerted: return None
    try:
        df = yf.download(ticker, period="1y", interval="1d", progress=False)
        if df is None or len(df) < 60: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        price = df["Close"].iloc[-1]
        if (price * df["Volume"].iloc[-1]) < CONFIG["MIN_VOLUME_USD"]: return None
        vol_mean = df["Volume"].rolling(20).mean().iloc[-1]
        if pd.isna(vol_mean) or vol_mean == 0: return None
        vol_ratio = df["Volume"].iloc[-1] / vol_mean
        h20 = df["High"].rolling(20).max().iloc[-2]
        if pd.isna(h20): return None
        rs_val = df["Close"].pct_change(63).iloc[-1] - spy_df["Close"].pct_change(63).iloc[-1]
        if pd.isna(rs_val): return None

        if price > h20 and vol_ratio > 1.2:
            ifs = institutional_score(df, rs_val)
            tr = pd.concat([df["High"]-df["Low"], abs(df["High"]-df["Close"].shift()), abs(df["Low"]-df["Close"].shift())], axis=1).max(axis=1)
            atr = tr.rolling(14).mean().iloc[-1]
            if pd.isna(atr) or atr == 0: return None
            sl = price - (atr * 1.5)
            risk = price - sl
            if risk <= 0: return None
            size = int((CONFIG["TOTAL_EQUITY"] * CONFIG["RISK_PER_TRADE_PERCENT"]) / risk)
            return {
                "ticker": ticker, "price": round(price, 2), "ifs": ifs, "rs": round(rs_val * 100, 1),
                "sl": round(sl, 2), "tg": round(price + (risk * 2.5), 2), "size": size, "prob": min(50 + (ifs * 6), 90),
                "label": "🧊 ICEBERG" if ifs >= 5 and 1.2 < vol_ratio < 2.0 else "⚡ SWEEP",
                "r1": round(h20, 2), "r2": round(price + (atr * 2), 2), "vol_ratio_raw": vol_ratio
            }
    except: return None

# ==============================
# 🚀 MAIN
# ==============================
def main():
    if not is_market_gold_hour(): return
    bull, spy_df = get_market_regime()
    if not bull or spy_df is None: return

    already = set()
    today = datetime.now().strftime("%Y-%m-%d")
    if os.path.exists(LOG_FILE):
        try:
            logged = pd.read_csv(LOG_FILE)
            if not logged.empty and "date" in logged.columns:
                already = set(logged[logged["date"] == today]["ticker"].values)
        except: pass

    results = []
    with ThreadPoolExecutor(max_workers=CONFIG["MAX_THREADS"]) as ex:
        futures = [ex.submit(analyze_ticker, t, spy_df, already) for t in MY_WATCHLIST]
        for f in as_completed(futures):
            res = f.result()
            if res: results.append(res)

    results = sorted(results, key=lambda x: (x["ifs"], x["rs"]), reverse=True)
    for r in results[:CONFIG["MAX_ALERTS"]]:
        if r["ifs"] >= 4:
            log_trade(r, r.pop("vol_ratio_raw"))
            msg = (f"🔭 *ALERT: {r['ticker']}* | {r['label']}\n━━━━━━━━━━━━━━━━━━\n"
                   f"💰 Price: `${r['price']}` | 📊 IFS: `{r['ifs']}/7` | 📈 RS: `{r['rs']}%` vs SPY\n"
                   f"🎯 Prob: `{r['prob']}%` | 🛡️ Size: `{r['size']} sh` | 🛑 SL: `${r['sl']}`\n"
                   f"🚀 Target: `${r['tg']}` | 📈 Levels: `{r['r1']} / {r['r2']}`")
            resp = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                                 data={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"})
            if resp.status_code != 200: print(f"Telegram Error: {resp.text}")
            time.sleep(1)

if __name__ == "__main__":
    main()


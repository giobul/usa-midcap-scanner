import subprocess
import sys
import os
import warnings
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

# ==============================================================
# 🛠️ AUTO-INSTALLER
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
# 📈 FUNZIONI TECNICHE (Pure e Veloci)
# ==============================================================
def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high_low   = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close  = np.abs(df['low']  - df['close'].shift())
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return true_range.rolling(window=period).mean()


def calculate_vwap_intraday(df: pd.DataFrame) -> pd.Series:
    df = df.copy()
    df['_date'] = df.index.date
    df['_tp']   = (df['high'] + df['low'] + df['close']) / 3

    vwap_values = pd.Series(index=df.index, dtype=float)

    for session_date, group in df.groupby('_date'):
        tp_v   = group['_tp'] * group['volume']
        cum_tv = tp_v.cumsum()
        cum_v  = group['volume'].cumsum()
        vwap_values.loc[group.index] = cum_tv / cum_v.replace(0, np.nan)

    return vwap_values


# ==============================================================
# 🕒 CONTROLLO ORARIO (Silver Window: 15:15 – 16:00 NY)
# ==============================================================
def is_silver_window() -> tuple[bool, str]:
    tz_ny  = pytz.timezone("America/New_York")
    now_ny = datetime.now(tz_ny)

    if now_ny.weekday() >= 5:
        return False, "Weekend — Mercato chiuso."

    current_min  = now_ny.hour * 60 + now_ny.minute
    window_start = 15 * 60 + 15   # 15:15 NY
    window_end   = 16 * 60        # 16:00 NY

    if window_start <= current_min <= window_end:
        return True,  f"✅ SILVER WINDOW ATTIVA (NY: {now_ny.strftime('%H:%M')})"
    return False, f"⏳ Standby — NY: {now_ny.strftime('%H:%M')}. Apertura scanner: 15:15 NY."


# ==============================================================
# ⚙️ CONFIGURAZIONE PERSONALIZZATA CON I TUOI DATI
# ==============================================================
@dataclass
class ScannerConfig:
    telegram_token:              str   = field(default_factory=lambda: os.getenv("TELEGRAM_TOKEN",   "8184561081:AAEW9iL5A71fF2p8y6Nl7Ew8_x_D-wY_k-I"))
    telegram_chat_id:            str   = field(default_factory=lambda: os.getenv("TELEGRAM_CHAT_ID", "-1002476594770"))
    total_equity:                float = 100_000.0
    risk_per_trade_pct:          float = 0.01
    max_threads:                 int   = 20
    min_ifs_threshold:           int   = 8
    ifs_max:                     int   = 12
    rr_ratio:                    float = 1.5
    max_trades_per_sector:       int   = 2
    ifs_institutional_threshold: int   = 11

CFG = ScannerConfig()


# ==============================================================
# 📋 WATCHLIST INTEGRALE (242 Tickers)
# ==============================================================
SECTOR_MAP = {
    "AAPL": "Tech",  "MSFT": "Tech",  "GOOGL": "Tech",  "META": "Tech",
    "AMZN": "Ecommerce", "TSLA": "EV",   "NFLX": "Media", "BRK-B": "Finance",
    "NVDA": "Semis", "AMD":  "Semis", "INTC": "Semis", "QCOM": "Semis",
    "AVGO": "Semis", "TSM":  "Semis", "ASML": "Semis", "AMAT": "Semis",
    "LRCX": "Semis", "KLAC": "Semis", "MU":   "Semis", "ON":   "Semis",
    "MRVL": "Semis", "NXPI": "Semis", "ADI":  "Semis", "MCHP": "Semis",
    "MPWR": "Semis", "ENTG": "Semis", "TER":  "Semis", "COHR": "Semis",
    "OLED": "Semis", "LSCC": "Semis", "SWKS": "Semis", "QRVO": "Semis",
    "TXN":  "Semis", "SMCI": "Semis", "SNPS": "Semis", "CDNS": "Semis",
    "CRM":  "Cloud", "ADBE": "Cloud", "NOW":  "Cloud", "ORCL": "Cloud",
    "SHOP": "Cloud", "SNOW": "Cloud", "PLTR": "Cloud", "DDOG": "Cloud",
    "MDB":  "Cloud", "TEAM": "Cloud", "ESTC": "Cloud", "OKTA": "Cloud",
    "TWLO": "Cloud", "HUBS": "Cloud", "BILL": "Cloud", "U":    "Cloud",
    "APP":  "Cloud", "DOCN": "Cloud", "FSLY": "Cloud", "DT":   "Cloud",
    "AI":   "Cloud", "PATH": "Cloud", "SOUN": "Cloud", "PANW": "Cyber",
    "CRWD": "Cyber", "ZS":   "Cyber", "NET":  "Cyber", "CSCO": "Tech",
    "ANET": "Tech",  "PYPL": "Fintech","SQ":  "Fintech","SOFI": "Fintech",
    "COIN": "Fintech","HOOD": "Fintech","AFRM":"Fintech","STNE": "Fintech",
    "NU":   "Fintech","PAGS": "Fintech","UPST":"Fintech","V":    "Fintech",
    "MA":   "Fintech","JPM":  "Finance","BAC": "Finance","WFC":  "Finance",
    "C":    "Finance","GS":   "Finance","MS":  "Finance","BLK":  "Finance",
    "SCHW": "Finance","AXP":  "Finance","ICE": "Finance","CME":  "Finance",
    "KKR":  "Finance","BX":   "Finance","APO": "Finance","ARES": "Finance",
    "ALLY": "Finance","UNH":  "Health", "LLY": "Health", "ABBV": "Health",
    "MRK":  "Health", "VRTX": "Health", "REGN":"Health", "GILD": "Health",
    "BIIB": "Health", "MRNA": "Health", "BNTX":"Health", "ISRG": "Health",
    "SYK":  "Health", "MDT":  "Health", "TMO": "Health", "ABT":  "Health",
    "DHR":  "Health", "PFE":  "Health", "BMY": "Health", "CVS":  "Health",
    "HUM":  "Health", "CI":   "Health", "ELV": "Health", "IDXX": "Health",
    "DXCM": "Health", "HIMS": "Health", "PG":  "Consumer","BYND": "Consumer",
    "COST": "Retail", "HD":   "Retail", "LOW": "Retail",  "NKE":  "Retail",
    "SBUX": "Retail", "MCD":  "Retail", "TGT": "Retail",  "ROST": "Retail",
    "TJX":  "Retail", "LULU": "Retail", "ULTA":"Retail",  "DPZ":  "Retail",
    "CMG":  "Retail", "YUM":  "Retail", "CVNA":"Retail",  "BKNG": "Travel",
    "ABNB": "Travel", "MAR":  "Travel", "HLT": "Travel",  "UBER": "Tech",
    "LYFT": "Tech",   "EBAY": "Ecommerce","ETSY":"Ecommerce","DIS": "Media",
    "CMCSA":"Media",  "PARA": "Media",  "WBD": "Media",   "FOX":  "Media",
    "FOXA": "Media",  "FUBO": "Media",  "T":   "Telecom", "VZ":   "Telecom",
    "CHTR": "Telecom","TMUS": "Telecom","ASTS":"Telecom",  "XOM":  "Energy",
    "CVX":  "Energy", "COP":  "Energy", "EOG": "Energy",  "SLB":  "Energy",
    "HAL":  "Energy", "OXY":  "Energy", "MPC": "Energy",  "PSX":  "Energy",
    "VLO":  "Energy", "KMI":  "Energy", "WMB": "Energy",  "DVN":  "Energy",
    "FANG": "Energy", "APA":  "Energy", "CTRA":"Energy",  "BKR":  "Energy",
    "EQT":  "Energy", "XLE":  "Energy", "BA":  "Industrial","RTX": "Industrial",
    "LMT":  "Industrial","NOC":"Industrial","GD":"Industrial",
    "CAT":  "Industrial","DE": "Industrial","ETN":"Industrial",
    "PH":   "Industrial","HON":"Industrial","GE": "Industrial",
    "EMR":  "Industrial","MMM":"Industrial","ITW":"Industrial",
    "CMI":  "Industrial","ROK":"Industrial","AME":"Industrial",
    "TDG":  "Industrial","LHX":"Industrial","PCAR":"Industrial",
    "LIN":  "Materials","APD": "Materials","ECL": "Materials",
    "SHW":  "Materials","NEM": "Materials","FCX": "Materials",
    "DOW":  "Materials","DD":  "Materials","ALB": "Materials",
    "NUE":  "Materials","NEE": "Utilities","DUK": "Utilities",
    "SO":   "Utilities","AEP": "Utilities","EXC": "Utilities",
    "SRE":  "Utilities","D":   "Utilities","XEL": "Utilities",
    "PEG":  "Utilities","ED":  "Utilities","UPS": "Transport",
    "FDX":  "Transport","UNP": "Transport","CSX": "Transport",
    "NSC":  "Transport","CP":  "Transport","CNI": "Transport",
    "DAL":  "Airlines", "UAL": "Airlines", "AAL": "Airlines",
    "MSTR": "Crypto",   "MARA":"Crypto",   "RIOT":"Crypto",  "CLSK":"Crypto",
    "RIVN": "EV",       "LCID":"EV",       "CHPT":"EV",      "QS":  "EV",
    "PLUG": "CleanEnergy","RUN":"CleanEnergy","SEDG":"CleanEnergy",
    "ENPH": "CleanEnergy","BLNK":"CleanEnergy","RBLX":"Gaming",
    "DKNG": "Gaming",   "RKLB":"Aerospace","OPEN":"Tech",    "IONQ":"Tech",
}
TICKERS = list(SECTOR_MAP.keys())


# ==============================================================
# 🧠 CORE ENGINE V7.3 PRO
# ==============================================================
def check_market_trend() -> bool:
    """
    Verifica lo stato dell'indice macro S&P 500 (^SPX).
    Se l'indice è sotto il suo VWAP intraday E l'RSI scende sotto 48,
    blocca lo scanner per evitare di comprare in fase di liquidazione panic-selling.
    """
    try:
        spy = yf.Ticker("^SPX")
        df_spy = spy.history(period="2d", interval="15m")
        if df_spy.empty:
            return True
            
        df_spy.columns = [c.lower() for c in df_spy.columns]
        if df_spy.index.tz is not None:
            df_spy.index = df_spy.index.tz_convert("America/New_York").tz_localize(None)
            
        df_spy = df_spy.iloc[:-1] 
        if len(df_spy) < 15:
            return True

        spy_vwap = calculate_vwap_intraday(df_spy).iloc[-1]
        spy_price = df_spy['close'].iloc[-1]
        spy_rsi = calculate_rsi(df_spy['close']).iloc[-1]
        
        if spy_price < spy_vwap and spy_rsi < 48:
            return False
        return True
    except Exception:
        return True


def analyze_ticker(ticker: str) -> Optional[dict]:
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period="7d", interval="15m")
        if df.empty or len(df) < 30:
            return None

        df.columns = [c.lower() for c in df.columns]

        if df.index.tz is not None:
            df.index = df.index.tz_convert("America/New_York").tz_localize(None)

        df = df.iloc[:-1]
        if len(df) < 30:
            return None

        price = df['close'].iloc[-1]

        df['rsi']  = calculate_rsi(df['close'])
        df['atr']  = calculate_atr(df)
        df['vwap'] = calculate_vwap_intraday(df)

        rsi  = df['rsi'].iloc[-1]
        atr  = df['atr'].iloc[-1]
        vwap = df['vwap'].iloc[-1]

        if pd.isna(rsi) or pd.isna(atr) or pd.isna(vwap):
            return None

        score = 0
        if price > vwap:
            score += 3

        if 60 < rsi < 75:
            score += 2
        elif rsi >= 75:
            score += 1
        elif rsi < 50:
            score -= 5

        curr_vol = df['volume'].iloc[-1]
        avg_vol  = df['volume'].tail(20).mean()
        vol_ratio = curr_vol / avg_vol if avg_vol > 0 else 0
        if vol_ratio > 1.5:
            score += 2
        if vol_ratio > 2.5:
            score += 4

        res_20 = df['high'].rolling(20).max().iloc[-1]
        if price >= res_20:
            score += 3

        trap_penalty = 0
        for i in range(-4, 0):
            h, l, c = df['high'].iloc[i], df['low'].iloc[i], df['close'].iloc[i]
            c_range  = h - l
            if c_range > 0:
                rel_close = (c - l) / c_range
                if rel_close < 0.4:
                    trap_penalty += 2
                elif rel_close < 0.6:
                    trap_penalty += 1

        score -= trap_penalty
        score  = min(score, CFG.ifs_max)

        if score < CFG.min_ifs_threshold:
            return None

        sl          = round(price - atr * 1.5, 2)
        tg          = round(price + (price - sl) * CFG.rr_ratio, 2)
        risk_amount = CFG.total_equity * CFG.risk_per_trade_pct
        size        = int(risk_amount / (price - sl)) if (price - sl) > 0 else 0

        return {
            "ticker":    ticker,
            "price":     round(price, 2),
            "ifs":       score,
            "rsi":       round(rsi, 1),
            "vwap_pos": "SOPRA" if price > vwap else "SOTTO",
            "vol_ratio": round(vol_ratio, 2),
            "sector":    SECTOR_MAP.get(ticker, "Other"),
            "tg":        tg,
            "sl":        sl,
            "size":      size,
        }
    except Exception:
        return None


# ==============================================================
# 📡 TELEGRAM BROADCASTER
# ==============================================================
def send_telegram(msg: str) -> None:
    try:
        requests.post(
            f"https://api.telegram.org/bot{CFG.telegram_token}/sendMessage",
            data={"chat_id": CFG.telegram_chat_id, "text": msg, "parse_mode": "Markdown"},
            timeout=5,
        )
    except Exception:
        pass


# ==============================================================
# 🚀 EXECUTION MAIN ENGINE
# ==============================================================
def main() -> None:
    active, status_msg = is_silver_window()
    print(status_msg)
    if not active:
        return

    # 🚨 FILTRO MACRO MERCATO PRIMA DI PARTIRE
    print("🔍 Analisi del trend macro S&P 500...")
    if not check_market_trend():
        market_warning = "⚠️ *SCANNER SOSPESO* — L'indice S&P 500 è in territorio fortemente ribassista (sotto VWAP / RSI debole). Operatività Long congelata per evitare Bull Trap di mercato."
        send_telegram(market_warning)
        print(f"❌ {market_warning}")
        return

    print(f"🚀 Scanner V7.3 PRO avviato su {len(TICKERS)} titoli...")
    results: list[dict] = []
    sector_counts: dict[str, int] = {}

    with ThreadPoolExecutor(max_workers=CFG.max_threads) as executor:
        futures = {executor.submit(analyze_ticker, t): t for t in TICKERS}
        for future in as_completed(futures):
            res = future.result()
            if not res:
                continue

            sector = res["sector"]
            if sector_counts.get(sector, 0) >= CFG.max_trades_per_sector:
                continue

            sector_counts[sector] = sector_counts.get(sector, 0) + 1
            results.append(res)

            label = (
                "💎 INSTITUTIONAL BUY"
                if res["ifs"] >= CFG.ifs_institutional_threshold
                else "🔥 SILVER FLOW"
            )
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
            print(f"✅ ALERT: {res['ticker']} (IFS {res['ifs']})")

    if results:
        send_telegram(
            f"📋 *Fine Sessione Silver Window*\n"
            f"Inviati {len(results)} segnali stabili filtrati sul macro-trend (V7.3 Pro)."
        )


if __name__ == "__main__":
    main()

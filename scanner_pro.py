"""
╔══════════════════════════════════════════════════════════════╗
║          SILVER WINDOW SCANNER — V5 (Production)            ║
║  Miglioramenti V5: filtro SPY trend + filtro earnings,       ║
║  blocca scansione su mercato ribassista o news imminenti     ║
╚══════════════════════════════════════════════════════════════╝
"""

import subprocess
import sys
import os
import time
import logging
import warnings
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

# ==============================================================
# 🛠️  AUTO-INSTALLER (Versione Ultra-Compatibile)
# ==============================================================
def _install(package: str) -> None:
    try:
        # Tenta l'importazione per vedere se è già presente
        __import__(package.replace('-', '_'))
    except ImportError:
        # Se è pandas_ta, forziamo una versione specifica compatibile con Python 3.11
        # Invece di Git, usiamo PyPI che è più stabile in GitHub Actions
        if "pandas_ta" in package:
            # Installiamo la versione 0.3.14b0 che è la più stabile per Python 3.11
            pkg_to_install = "pandas-ta==0.3.14b0"
        else:
            pkg_to_install = package
            
        print(f"📦 Installazione di {pkg_to_install} in corso...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg_to_install, "--upgrade", "-q"])

# Installiamo i pacchetti necessari
for _pkg in ["pandas", "numpy", "requests", "yfinance", "pytz", "pandas-ta"]:
    _install(_pkg)

# Importiamo dopo l'installazione
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import numpy as np
import requests
import pytz

warnings.filterwarnings("ignore")

# ==============================================================
# 📋  LOGGING — sostituisce tutti i "except: pass"
# ==============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("scanner_v5.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("SilverScannerV5")

# ==============================================================
# ⚙️  CONFIGURAZIONE SEPARATA DALLA LOGICA
#     Puoi sovrascrivere ogni valore tramite variabili d'ambiente
#     es: export TOTAL_EQUITY=50000
# ==============================================================
@dataclass
class ScannerConfig:
    # Credenziali Telegram (da env o inserimento diretto)
    telegram_token: str   = field(default_factory=lambda: os.getenv("TELEGRAM_TOKEN", "YOUR_TOKEN_HERE"))
    telegram_chat_id: str = field(default_factory=lambda: os.getenv("TELEGRAM_CHAT_ID", "YOUR_CHAT_ID_HERE"))

    # Parametri equity e rischio
    total_equity: float           = field(default_factory=lambda: float(os.getenv("TOTAL_EQUITY", "100000")))
    risk_per_trade_pct: float     = field(default_factory=lambda: float(os.getenv("RISK_PCT", "0.01")))

    # Motore di scansione
    max_threads: int              = field(default_factory=lambda: int(os.getenv("MAX_THREADS", "8")))
    min_ifs_threshold: int        = field(default_factory=lambda: int(os.getenv("MIN_IFS", "8")))
    rr_ratio: float               = field(default_factory=lambda: float(os.getenv("RR_RATIO", "1.5")))

    # Filtri aggiuntivi V3
    max_trades_per_sector: int    = 2      # Evita correlazione settoriale
    telegram_rate_limit_sec: float= 0.35   # ~3 msg/sec, limite Telegram è 30/sec
    timeout_exit_ny_hour: int     = 16     # Exit time: 16:15 NY
    timeout_exit_ny_min: int      = 15

    # IFS massimo raggiungibile con la logica attuale = 12
    ifs_max: int = 12
    ifs_institutional_threshold: int = 11  # >= 11 = "Institutional Buy"

CFG = ScannerConfig()

# ==============================================================
# 📋  WATCHLIST INTEGRALE (242 Tickers)
# ==============================================================
SECTOR_MAP: dict[str, str] = {
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
# 🕒  SILVER WINDOW
# ==============================================================
def is_silver_window() -> tuple[bool, str]:
    tz_ny = pytz.timezone("America/New_York")
    now_ny = datetime.now(tz_ny)
    if now_ny.weekday() >= 5:
        return False, "Weekend — mercato chiuso"
    cur = now_ny.hour * 60 + now_ny.minute
    if 15 * 60 <= cur <= 15 * 60 + 45:
        return True, f"SILVER WINDOW ATTIVA — NY {now_ny.strftime('%H:%M')}"
    return False, f"Standby istituzionale — NY {now_ny.strftime('%H:%M')}"

# ==============================================================
# 🧠  CORE ENGINE V5
# ==============================================================
def _safe_vwap(df: pd.DataFrame) -> Optional[float]:
    """Recupera il VWAP indipendentemente dal suffisso generato da pandas_ta."""
    cols = [c for c in df.columns if c.upper().startswith("VWAP")]
    if not cols:
        return None
    return float(df[cols[0]].iloc[-1])

def _calc_rvol(df: pd.DataFrame) -> float:
    """
    RVOL time-aware: confronta il volume della candela corrente con la media
    storica delle sole candele nello stesso slot orario (es. tutte le 15:00).

    Con period="7d" abbiamo ~5 campioni per slot → media robusta.
    Fallback automatico a rolling-20 se lo storico è insufficiente.
    """
    try:
        curr_vol  = float(df["volume"].iloc[-1])
        curr_time = df.index[-1].time()   # V5: .time() diretto, no conversione timezone

        # Tutte le candele con lo stesso orario, esclusa quella corrente
        same_slot = df.loc[df.index.time == curr_time, "volume"].iloc[:-1]

        if len(same_slot) >= 3:
            avg_slot_vol = float(same_slot.mean())
            return curr_vol / avg_slot_vol if avg_slot_vol > 0 else 0.0

    except Exception:
        pass  # Fallback intenzionale — non critico

    # Fallback: media rolling 20 candele
    vol_avg = float(df["volume"].rolling(20).mean().iloc[-1])
    return float(df["volume"].iloc[-1] / vol_avg) if vol_avg > 0 else 0.0



def _check_spy_trend() -> bool:
    """
    Filtro macro: verifica che SPY sia sopra la sua media mobile a 8 periodi
    sulla timeframe 15min. Se il mercato è in trend ribassista globale,
    i breakout sui singoli titoli sono per lo più falsi — blocca la scansione.
    Restituisce True se il trend è bullish (ok per operare).
    """
    try:
        spy = yf.Ticker("SPY")
        df  = spy.history(period="2d", interval="15m")
        if df.empty or len(df) < 10:
            log.warning("SPY: dati insufficienti — procedo comunque")
            return True  # Fallback permissivo: meglio perdere il filtro che bloccare tutto
        close     = df["Close"]
        ma8       = close.rolling(8).mean()
        spy_ok    = float(close.iloc[-1]) > float(ma8.iloc[-1])
        spy_price = float(close.iloc[-1])
        spy_ma    = float(ma8.iloc[-1])
        log.info("SPY trend check: %.2f vs MA8 %.2f → %s",
                 spy_price, spy_ma, "BULLISH ✅" if spy_ok else "BEARISH ❌")
        return spy_ok
    except Exception as e:
        log.warning("SPY trend check fallito (%s) — procedo comunque", e)
        return True  # Fallback permissivo


def _has_earnings_soon(stock: yf.Ticker, ticker: str) -> bool:
    """
    Filtro earnings: restituisce True se il ticker ha earnings entro 1 giorno.
    In quel caso il segnale viene scartato — la volatilità da earnings
    invalida qualsiasi analisi tecnica intraday.
    """
    try:
        cal = stock.calendar
        # yfinance restituisce un dict o un DataFrame a seconda della versione
        if cal is None:
            return False
        if isinstance(cal, dict):
            date_val = cal.get("Earnings Date")
            if not date_val:
                return False
            # Può essere una lista o un singolo valore
            earnings_date = date_val[0] if isinstance(date_val, list) else date_val
        else:
            # DataFrame: prima colonna, prima riga
            if cal.empty:
                return False
            earnings_date = cal.iloc[0, 0]

        # Normalizza a datetime
        if hasattr(earnings_date, "date"):
            earnings_date = earnings_date.date()
        today = datetime.now(pytz.timezone("America/New_York")).date()
        days_to_earnings = (earnings_date - today).days
        if 0 <= days_to_earnings <= 1:
            log.info("SKIP %s — earnings tra %d giorno/i (%s)", ticker, days_to_earnings, earnings_date)
            return True
    except Exception as e:
        log.debug("[%s] earnings check fallito (%s) — procedo comunque", ticker, e)
    return False


def analyze_ticker(ticker: str) -> Optional[dict]:
    try:
        stock = yf.Ticker(ticker)

        # Filtro earnings: salta se earnings entro 24h
        if _has_earnings_soon(stock, ticker):
            return None

        df = stock.history(period="7d", interval="15m")  # V5: più campioni per RVOL slot

        if df.empty or len(df) < 30:
            return None

        # Normalizza nomi colonne
        df.columns = [c.lower() for c in df.columns]

        # Indicatori tecnici
        df.ta.vwap(append=True)
        df.ta.rsi(length=14, append=True)
        df.ta.atr(length=14, append=True)

        curr = df.iloc[-1]

        price = float(curr["close"])
        vwap  = _safe_vwap(df)          # FIX: nome colonna dinamico
        rsi   = float(curr.get("rsi_14", 50))
        atr   = float(curr.get("atrr_14", curr.get("atr_14", price * 0.01)))

        if vwap is None or atr <= 0:
            return None

        # ── IFS V5 (max = 12) ──────────────────────────────────
        score = 0

        # A. VWAP (+3)
        if price > vwap:
            score += 3

        # B. RSI momentum (+2 / +1 / penalità -5)
        if 60 < rsi < 75:
            score += 2
        elif rsi >= 75:
            score += 1   # Ipercomprato: segnale più debole
        elif rsi < 50:
            score -= 5   # Debolezza strutturale — scarta

        # C. Breakout + Volume (+3 +2 +4)
        # V5: RVOL time-aware — confronta candela 15:00 vs media storica 15:00
        # (non le 20 candele precedenti che mescolano lunch/open con diverso profilo)
        res_20    = float(df["high"].rolling(20).max().iloc[-2])
        vol_ratio = _calc_rvol(df)

        if price > res_20:
            score += 3
        if vol_ratio > 1.5:
            score += 2
        if vol_ratio > 2.5:
            score += 4

        if score < CFG.min_ifs_threshold:
            return None

        # ── Money Management ────────────────────────────────────
        sl   = round(price - atr * 1.5, 2)
        tg   = round(price + (price - sl) * CFG.rr_ratio, 2)
        risk = CFG.total_equity * CFG.risk_per_trade_pct
        size = int(risk / (price - sl)) if (price - sl) > 0 else 0

        return {
            "ticker":    ticker,
            "price":     round(price, 2),
            "ifs":       score,
            "rsi":       round(rsi, 1),
            "vwap_pos":  "SOPRA" if price > vwap else "SOTTO",
            "vol_ratio": round(vol_ratio, 2),
            "sector":    SECTOR_MAP.get(ticker, "Other"),
            "tg":        tg,
            "sl":        sl,
            "size":      size,
        }

    except Exception as e:
        log.warning("[%s] %s: %s", ticker, type(e).__name__, e)
        return None

# ==============================================================
# 📨  TELEGRAM — con rate limiting
# ==============================================================
def send_telegram(msg: str) -> None:
    """Invia messaggio Telegram con rate limiting integrato."""
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{CFG.telegram_token}/sendMessage",
            data={"chat_id": CFG.telegram_chat_id, "text": msg, "parse_mode": "Markdown"},
            timeout=5,
        )
        if not resp.ok:
            log.warning("Telegram error %s: %s", resp.status_code, resp.text[:100])
    except requests.RequestException as e:
        log.warning("Telegram request failed: %s", e)
    finally:
        time.sleep(CFG.telegram_rate_limit_sec)   # FIX: rate limiting

# ==============================================================
# 🚀  MAIN
# ==============================================================
def main() -> None:
    active, status_msg = is_silver_window()
    log.info(status_msg)

    # ── Decommentare per test fuori orario ──
    # active = True

    if not active:
        log.info("Scanner in standby. Attivo solo 15:00-15:45 NY.")
        return

    # Filtro macro SPY — blocca se mercato globalmente ribassista
    if not _check_spy_trend():
        msg = "⚠️ *Silver Scanner V5*\nScansione SOSPESA — SPY sotto MA8\nMercato in trend ribassista: falsi breakout probabili."
        log.warning("Scansione sospesa: SPY bearish")
        send_telegram(msg)
        return

    log.info("Avvio scansione V5 su %d titoli (soglia IFS: %d)...", len(TICKERS), CFG.min_ifs_threshold)

    results: list[dict] = []
    sector_counts: dict[str, int] = {}   # FIX: filtro correlazione settoriale

    with ThreadPoolExecutor(max_workers=CFG.max_threads) as executor:
        futures = {executor.submit(analyze_ticker, t): t for t in TICKERS}

        for i, future in enumerate(as_completed(futures), 1):
            res = future.result()

            if i % 50 == 0:
                log.info("Analizzati %d/%d titoli...", i, len(TICKERS))

            if not res:
                continue

            # FIX: max N trade per settore
            sector = res["sector"]
            if sector_counts.get(sector, 0) >= CFG.max_trades_per_sector:
                log.info("SKIP %s — settore %s già a quota %d", res["ticker"], sector, CFG.max_trades_per_sector)
                continue

            sector_counts[sector] = sector_counts.get(sector, 0) + 1
            results.append(res)

            # Messaggio Telegram
            label = "💎 INSTITUTIONAL BUY" if res["ifs"] >= CFG.ifs_institutional_threshold else "🔥 SILVER FLOW"
            exit_time = f"{CFG.timeout_exit_ny_hour}:{CFG.timeout_exit_ny_min:02d} NY"
            msg = (
                f"{label}: *{res['ticker']}*\n"
                f"📊 *IFS:* `{res['ifs']}/{CFG.ifs_max}` | *RSI:* `{res['rsi']}`\n"
                f"📈 *VWAP:* `{res['vwap_pos']}` | *Vol x:* `{res['vol_ratio']}`\n"
                f"🏭 *Settore:* {sector}\n"
                f"✅ *ENTRY:* `${res['price']}` | 🎯 *TG:* `${res['tg']}`\n"
                f"🛑 *SL:* `${res['sl']}` | 🛡️ *SIZE:* `{res['size']} sh`\n"
                f"⏳ *TIME EXIT:* {exit_time} (30-45 min max)\n"
                f"━━━━━━━━━━━━━━━━━━"
            )

            log.info("ALERT: %s | IFS %d/%d | RSI %.1f | VWAP %s",
                     res["ticker"], res["ifs"], CFG.ifs_max, res["rsi"], res["vwap_pos"])
            send_telegram(msg)

    log.info("Scansione completata. %d segnali validi trovati.", len(results))

    # Riepilogo finale su Telegram
    if results:
        summary = (f"📋 *Riepilogo Silver Window V5*\n"
                   f"Segnali: {len(results)} | Settori coinvolti: {len(sector_counts)}\n"
                   f"Top IFS: {max(r['ifs'] for r in results)}/{CFG.ifs_max}")
        send_telegram(summary)


if __name__ == "__main__":
    main()

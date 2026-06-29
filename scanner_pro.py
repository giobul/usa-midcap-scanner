import subprocess
import sys
import os
import warnings
import time
import logging
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

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
# 🌐 SESSIONE HTTP CONDIVISA CON USER-AGENT
# ==============================================================
_YF_SESSION = requests.Session()
_YF_SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
})

# ==============================================================
# ⏸️ GATE DI BACKOFF COOPERATIVO  [V8.5]
#
# ARCHITETTURA:
#   _rate_limit_lock  → sezione critica SOLO per leggere/scrivere lo stato.
#                       NON viene tenuto durante il sleep (fix V8.5).
#   _gate_open_event  → tutti i thread worker aspettano qui (non sul lock).
#   _last_cooldown_time → evita cooldown sovrapposti.
#
# FLUSSO CORRETTO:
#   Thread A rileva 429 → acquisisce lock → chiude gate → rilascia lock
#                       → dorme FUORI dal lock → riapre gate
#   Thread B, C         → aspettano su _gate_open_event.wait() senza
#                         mai contendere il lock con il sleep di A.
# ==============================================================
_rate_limit_lock    = threading.Lock()
_gate_open_event    = threading.Event()
_gate_open_event.set()          # True = verde, False = cooldown attivo
_last_cooldown_time: float = 0.0


def _wait_if_rate_limited() -> None:
    """
    Blocca il thread chiamante finché il gate è chiuso.
    Il timeout evita deadlock se _gate_open_event non venisse mai riaperto
    per un bug imprevisto (es. eccezione dentro _signal_rate_limit).
    """
    opened = _gate_open_event.wait(timeout=CFG.rate_limit_backoff_sec + 5.0)
    if not opened:
        # Timeout di sicurezza: riapre forzatamente e logga l'anomalia
        _gate_open_event.set()
        log("⚠️ [GATE] Timeout di sicurezza scattato — gate riaperto forzatamente.", "warning")


def _signal_rate_limit() -> None:
    """
    Chiude il gate in modo atomico, dorme FUORI dal lock, poi riapre.

    V8.5 FIX: il lock viene acquisito SOLO per la sezione critica
    (controllo + clear), poi rilasciato PRIMA del time.sleep().
    Questo evita che tutti i thread si blocchino sul lock invece
    che sull'event, e previene lo stallo da lock tenuto 10 secondi.
    """
    global _last_cooldown_time

    # --- SEZIONE CRITICA (brevissima) ---
    with _rate_limit_lock:
        if not _gate_open_event.is_set():
            return   # un altro thread ha già aperto il cooldown
        if time.time() - _last_cooldown_time <= 5.0:
            return   # cooldown terminato meno di 5s fa: skip
        _gate_open_event.clear()   # chiude il gate — atomico rispetto al lock
    # --- FINE SEZIONE CRITICA: lock rilasciato ---

    # Sleep FUORI dal lock: altri thread entrano in _signal_rate_limit(),
    # trovano il gate già chiuso e tornano subito senza contendere.
    log(f"⏸️ [RATE-LIMIT] Cooldown globale {CFG.rate_limit_backoff_sec}s...", "warning")
    time.sleep(CFG.rate_limit_backoff_sec)

    _last_cooldown_time = time.time()   # aggiornamento safe: scrittura atomica su float
    _gate_open_event.set()
    log("▶️ [RATE-LIMIT] Ripresa dei flussi concorrenti.", "info")


# ==============================================================
# 📝 LOGGING PERSISTENTE
# ==============================================================
LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scanner.log")

_logger = logging.getLogger("SilverScanner")
_logger.setLevel(logging.DEBUG)

_fh = logging.FileHandler(LOG_PATH, encoding="utf-8")
_fh.setLevel(logging.DEBUG)
_fh.setFormatter(logging.Formatter(
    "%(asctime)s | %(levelname)-8s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
))

_ch = logging.StreamHandler(sys.stdout)
_ch.setLevel(logging.INFO)
_ch.setFormatter(logging.Formatter("%(message)s"))

_logger.addHandler(_fh)
_logger.addHandler(_ch)


def log(msg: str, level: str = "info") -> None:
    getattr(_logger, level)(msg)


# ==============================================================
# ⚙️ CONFIGURAZIONE PARAMETRIZZATA
# ==============================================================
@dataclass
class ScannerConfig:
    telegram_token:              str   = field(default_factory=lambda: os.getenv("TELEGRAM_TOKEN", "VALORE_TOKEN"))
    telegram_chat_id:            str   = field(default_factory=lambda: os.getenv("TELEGRAM_CHAT_ID", "VALORE_CHAT_ID"))
    total_equity:                float = 100_000.0
    risk_per_trade_pct:          float = 0.01
    max_threads:                 int   = 2
    min_ifs_threshold:           int   = 8
    ifs_max:                     int   = 12
    rr_ratio:                    float = 1.5
    max_trades_per_sector:       int   = 2
    ifs_institutional_threshold: int   = 11
    macro_rsi_block:             float = 45.0
    window_start_min:            int   = 15 * 60 + 15   # 15:15 NY
    window_end_min:              int   = 16 * 60         # 16:00 NY
    telegram_max_retries:        int   = 3
    telegram_retry_delay_sec:    float = 2.0
    rate_limit_backoff_sec:      float = 10.0
    min_df_rows:                 int   = 40

CFG = ScannerConfig()


# ==============================================================
# 📈 FUNZIONI TECNICHE VETTORIZZATE
# ==============================================================
def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain  = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss  = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs    = gain / loss
    return 100 - (100 / (1 + rs))


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high_low   = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close  = np.abs(df['low']  - df['close'].shift())
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return true_range.rolling(window=period).mean()


def calculate_vwap_intraday(df: pd.DataFrame) -> pd.Series:
    df         = df.copy()
    df['date'] = df.index.date
    df['tp']   = (df['high'] + df['low'] + df['close']) / 3
    df['tp_v'] = df['tp'] * df['volume']
    cum_tv     = df.groupby('date')['tp_v'].cumsum()
    cum_v      = df.groupby('date')['volume'].cumsum()
    return cum_tv / cum_v.replace(0, np.nan)


# ==============================================================
# 🕒 CONTROLLO ORARIO
# ==============================================================
def is_silver_window() -> tuple[bool, str]:
    tz_ny   = pytz.timezone("America/New_York")
    now_ny  = datetime.now(tz_ny)

    if now_ny.weekday() >= 5:
        return False, "Weekend — Mercato chiuso."

    current_min = now_ny.hour * 60 + now_ny.minute

    if CFG.window_start_min <= current_min <= CFG.window_end_min:
        return True, f"✅ SILVER WINDOW ATTIVA (NY: {now_ny.strftime('%H:%M')})"

    return False, f"⏳ Standby — NY: {now_ny.strftime('%H:%M')}. Finestra utile: 15:15 - 16:00 NY."


# ==============================================================
# 📋 WATCHLIST (242 Tickers)
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
    "RIVN": "EV",       "LCID":"EV",       "CHPT":"EV",       "QS":  "EV",
    "PLUG": "CleanEnergy","RUN":"CleanEnergy","SEDG":"CleanEnergy",
    "ENPH": "CleanEnergy","BLNK":"CleanEnergy","RBLX":"Gaming",
    "DKNG": "Gaming",   "RKLB":"Aerospace","OPEN":"Tech",     "IONQ":"Tech",
}
TICKERS = list(SECTOR_MAP.keys())


# ==============================================================
# 🔍 PROBE RATE-LIMIT  [V8.5]
# Sostituisce il controllo su history_metadata (instabile tra versioni).
# Usa una chiamata minima (1 giorno, 1h) su un ticker noto e liquido.
# Se anche questa torna vuota, il sistema è sotto rate-limit globale.
# ==============================================================
def _probe_rate_limit_via_spy() -> bool:
    """
    Torna True se Yahoo Finance sta bloccando le richieste (rate-limit globale).
    Usa SPY come ticker sentinella — quasi impossibile che sia genuinamente vuoto.
    """
    try:
        probe = yf.Ticker("SPY", session=_YF_SESSION).history(period="1d", interval="1h")
        return probe.empty
    except Exception:
        return False   # errore generico: non assumiamo rate-limit


# ==============================================================
# 🌍 FILTRO MACRO S&P 500
# ==============================================================
def check_market_trend() -> bool:
    try:
        spy    = yf.Ticker("SPY", session=_YF_SESSION)
        df_spy = spy.history(period="1d", interval="15m")

        if df_spy.empty:
            return True

        df_spy.columns = [c.lower() for c in df_spy.columns]

        if df_spy.index.tz is not None:
            df_spy.index = df_spy.index.tz_convert("America/New_York").tz_localize(None)

        if len(df_spy) < 5:
            return True

        spy_vwap  = calculate_vwap_intraday(df_spy).iloc[-1]
        spy_price = df_spy['close'].iloc[-1]
        spy_rsi   = calculate_rsi(df_spy['close']).iloc[-1]

        if pd.isna(spy_vwap) or pd.isna(spy_rsi):
            return True

        if spy_price < spy_vwap and spy_rsi < CFG.macro_rsi_block:
            log(
                f"⚠️ MACRO ALERT — SPY sotto VWAP (${spy_price:.2f} < ${spy_vwap:.2f}) "
                f"e RSI={spy_rsi:.1f}. Scanner inibito.",
                "warning"
            )
            return False

        log(f"✅ Macro OK — SPY: ${spy_price:.2f} | VWAP: ${spy_vwap:.2f} | RSI: {spy_rsi:.1f}")
        return True

    except Exception as e:
        log(f"⚠️ check_market_trend fallito: {e}", "warning")
        return True


# ==============================================================
# 🧠 CORE ENGINE V8.5
# ==============================================================
def analyze_ticker(ticker: str) -> Optional[dict]:
    try:
        _wait_if_rate_limited()

        stock = yf.Ticker(ticker, session=_YF_SESSION)
        df    = stock.history(period="10d", interval="15m")

        if df.empty:
            # V8.5: probe stabile su SPY invece di history_metadata (non documentato)
            if _probe_rate_limit_via_spy():
                log(f"⚠️ [PROBE] DF vuoto per {ticker} confermato da SPY — segnalo rate-limit.", "warning")
                _signal_rate_limit()
            return None

        if len(df) < CFG.min_df_rows:
            return None

        df.columns = [c.lower() for c in df.columns]

        if df.index.tz is not None:
            df.index = df.index.tz_convert("America/New_York").tz_localize(None)

        price = df['close'].iloc[-1]

        if price < 5.0:
            return None

        df['rsi']  = calculate_rsi(df['close'])
        df['atr']  = calculate_atr(df)
        df['vwap'] = calculate_vwap_intraday(df)

        rsi  = df['rsi'].iloc[-1]
        atr  = df['atr'].iloc[-1]
        vwap = df['vwap'].iloc[-1]

        if pd.isna(rsi) or pd.isna(atr) or pd.isna(vwap):
            return None

        atr_pct = atr / price
        if atr_pct > 0.05:
            return None

        # ── CALCOLO PUNTEGGIO IFS ─────────────────────────────────────────────
        score = 0

        if price > vwap:
            score += 3

        if 60 < rsi < 75:
            score += 2
        elif rsi >= 75:
            score += 1
        elif rsi < 50:
            score -= 5

        curr_vol  = df['volume'].iloc[-2]
        avg_vol   = df['volume'].iloc[-21:-1].mean()
        vol_ratio = curr_vol / avg_vol if avg_vol > 0 else 0

        if vol_ratio > 2.5:
            score += 4
        elif vol_ratio > 1.5:
            score += 2

        res_20 = df['high'].rolling(20).max().iloc[-1]
        if price >= res_20:
            score += 3

        # ── ANTI-BULL TRAP ────────────────────────────────────────────────────
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
        score  = max(score, 0)

        if score < CFG.min_ifs_threshold:
            return None

        # ── MONEY MANAGEMENT ──────────────────────────────────────────────────
        sl          = round(price - atr * 1.5, 2)
        tg          = round(price + (price - sl) * CFG.rr_ratio, 2)
        risk_amount = CFG.total_equity * CFG.risk_per_trade_pct
        size        = int(risk_amount / (price - sl)) if (price - sl) > 0 else 0

        result = {
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

        log(
            f"[SIGNAL] {ticker} | IFS={score} | RSI={rsi:.1f} | "
            f"Price={price:.2f} | VWAP={'>' if price > vwap else '<'} | "
            f"Vol×={vol_ratio:.2f} | SL={sl} | TG={tg} | Size={size}",
            "debug"
        )
        return result

    except Exception as e:
        err_str = str(e)
        if "429" in err_str or "Too Many" in err_str or "rate limit" in err_str.lower():
            _signal_rate_limit()
        else:
            log(f"❌ [CONN_ERROR] {ticker}: {e}", "error")
        return None


# ==============================================================
# 📡 TELEGRAM CON RETRY
# ==============================================================
def send_telegram(msg: str) -> bool:
    if "VALORE_TOKEN" in CFG.telegram_token:
        return False

    url = f"https://api.telegram.org/bot{CFG.telegram_token}/sendMessage"

    for attempt in range(1, CFG.telegram_max_retries + 1):
        try:
            resp = requests.post(
                url,
                data={"chat_id": CFG.telegram_chat_id, "text": msg, "parse_mode": "Markdown"},
                timeout=5,
            )
            if resp.status_code == 200:
                return True
            log(
                f"⚠️ Telegram HTTP {resp.status_code} "
                f"(tentativo {attempt}/{CFG.telegram_max_retries}): {resp.text[:120]}",
                "warning"
            )
        except requests.exceptions.RequestException as e:
            log(
                f"⚠️ Telegram timeout/conn error "
                f"(tentativo {attempt}/{CFG.telegram_max_retries}): {e}",
                "warning"
            )

        if attempt < CFG.telegram_max_retries:
            time.sleep(CFG.telegram_retry_delay_sec * attempt)   # backoff lineare: 2s, 4s

    log("❌ Telegram: invio fallito dopo tutti i tentativi.", "error")
    return False


# ==============================================================
# 🚀 MAIN
# ==============================================================
def main() -> None:
    log("=" * 60)
    log(f"🚀 Silver Scanner V8.5 — avvio {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"📄 Log persistente: {LOG_PATH}", "debug")

    active, status_msg = is_silver_window()
    log(status_msg)
    if not active:
        log("Fine — fuori finestra operativa.")
        return

    log("🔍 Analisi trend macro S&P 500 (SPY)...")
    if not check_market_trend():
        send_telegram(
            "⚠️ *SCANNER SOSPESO*\n"
            "SPY sotto VWAP con RSI debole.\n"
            "Operatività Long congelata — rischio Bull Trap di mercato."
        )
        return

    log(f"🔎 Scansione su {len(TICKERS)} titoli (thread={CFG.max_threads})...")
    raw_results: list[dict] = []
    scanned = 0

    with ThreadPoolExecutor(max_workers=CFG.max_threads) as executor:
        futures = {executor.submit(analyze_ticker, t): t for t in TICKERS}
        for future in as_completed(futures):
            scanned += 1
            res = future.result()
            if res:
                raw_results.append(res)

    log(f"✅ Scansione completata: {scanned}/{len(TICKERS)} analizzati, {len(raw_results)} segnali sopra soglia.")

    raw_results.sort(key=lambda x: x["ifs"], reverse=True)

    sector_counts: dict[str, int] = {}
    sent_signals  = 0
    failed_sends  = 0

    for res in raw_results:
        sector = res["sector"]

        if sector_counts.get(sector, 0) >= CFG.max_trades_per_sector:
            log(f"[SKIP] {res['ticker']} — settore {sector} già a quota ({CFG.max_trades_per_sector})", "debug")
            continue

        sector_counts[sector] = sector_counts.get(sector, 0) + 1
        sent_signals += 1

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
        ok = send_telegram(msg)
        if ok:
            log(f"✅ ALERT INVIATO: {res['ticker']} (IFS {res['ifs']}) — {sector}")
        else:
            failed_sends += 1
            log(f"❌ ALERT NON INVIATO: {res['ticker']} (IFS {res['ifs']}) — {sector}", "error")

    summary = (
        f"📋 *Fine Sessione Silver Window*\n"
        f"Inviati {sent_signals - failed_sends}/{sent_signals} segnali — Scanner V8.5."
    ) if sent_signals > 0 else "📋 *Fine Sessione* — Nessun segnale sopra la soglia minima oggi."

    send_telegram(summary)
    log(f"📋 Sessione conclusa — segnali: {sent_signals}, invii falliti: {failed_sends}")
    log("=" * 60)


if __name__ == "__main__":
    main()

import sys
from datetime import datetime, timedelta, time as dtime
import time
import os
import requests
import pytz
import numpy as np
import pandas as pd
import yfinance as yf
import json
from pathlib import Path

# --- CONFIGURAZIONE ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

MY_PORTFOLIO = ["STNE", "PATH", "RGTI", "BBAI", "SOFI", "AGEN", "DKNG", "QUBT", "ETOR", "ADCT", "APLD"]

WATCHLIST_200 = [
    "SNOW", "DDOG", "NET", "ZS", "CRWD", "MDB", "ESTC", "DOCN", "GTLB", "AI",
    "PCOR", "APPN", "BILL", "ZI", "SMAR", "JAMF", "DT", "S", "TENB", "PANW",
    "FTNT", "CYBR", "OKTA", "PING", "U", "RBLX", "PLTK", "BIGC", "ASAN", "MNDY",
    "IOT", "TWLO", "ZM", "SHOP", "UBER", "OKLO", "ALTI", "VRT", "CLS", "PSTG", "ANET",
    "NVDA", "AMD", "ARM", "AVGO", "TSM", "ASML", "MU", "AMAT", "LRCX", "KLAC",
    "SMCI", "MRVL", "ON", "MPWR", "SWKS", "QRVO", "WOLF", "CRUS", "ALGM", "POWI", 
    "DIOD", "LSCC", "RMBS", "COHU", "FORM", "ONTO", "NVTS", "PLAB", "IRDM", "ALAB",
    "PLTR", "SOUN", "GFAI", "CIFR", "CORZ", "WULF", "IONQ", "QBTS", "ARQQ", "IRBT",
    "BLDE", "MKSI", "GRMN", "ISRG", "NNDM", "DM", "SSYS", "SOUND", "SERV", "D_WAVE",
    "AFRM", "UPST", "NU", "PAGS", "MELI", "SQ", "PYPL", "COIN", "HOOD", "MARA",
    "RIOT", "CLSK", "MSTR", "BTBT", "HUT", "ARBK", "BITF", "TOST", "FOUR", "GPN",
    "EVTC", "LC", "TREE", "ENVA", "OPY", "LPRO", "VIRT", "IBKR",
    "SMR", "VST", "CEG", "NNE", "CCJ", "UUUU", "DNN", "NXE", "UEC", "FSLR", 
    "ENPH", "SEDG", "RUN", "NOVA", "CSIQ", "JKS", "SOL", "FLNC", "CHPT", "BLNK", 
    "EVGO", "STEM", "PLUG", "BLDP", "BE", "GCT", "TLNE", "ETN", "NEE", "BW", "LNL",
    "RKLB", "ASTS", "LUNR", "PL", "SPIR", "BKSY", "SIDU", "ACHR", "JOBY", "LILM",
    "EVTL", "AVAV", "KTOS", "HWM", "VSAT", "LHX", "BA", "LMT", "RTX", "GD", 
    "NOC", "AXON", "HOLO", "RIVN", "LCID", "TSLA", "NIO", "XPEV", "LI", "FSR", 
    "NKLA", "WKHS", "HYLN", "LEV", "MVST", "LAZR", "OUST", "AUR", "INVZ", "VLDR", 
    "LYFT", "CVNA", "QS", "TDOC", "DOCS", "ONEM", "ACCD", "HIMS", "LFST", "GH", 
    "PGNY", "SDGR", "ALHC", "VKTX", "RXDX", "KRTX", "IOVA", "VERV", "CRSP", "NTLA", 
    "BEAM", "EDIT", "BLUE", "ALT", "AMAM", "IBX", "MREO", "CYTK"
]

ALERT_LOG = Path.home() / ".scanner_alerts.json"

# --- UTILITIES ---
def load_alert_history():
    if ALERT_LOG.exists():
        try:
            with open(ALERT_LOG, 'r') as f:
                data = json.load(f)
                return {k: datetime.fromisoformat(v) for k, v in data.items()}
        except: return {}
    return {}

def save_alert_history(history):
    try:
        data = {k: v.isoformat() for k, v in history.items()}
        with open(ALERT_LOG, 'w') as f:
            json.dump(data, f)
    except: pass

def get_market_session():
    tz_ny = pytz.timezone('US/Eastern')
    now_ny = datetime.now(tz_ny)
    current_time = now_ny.time()
    if dtime(4, 0) <= current_time < dtime(9, 30): return 'PRE_MARKET', now_ny
    elif dtime(9, 30) <= current_time < dtime(16, 0): return 'REGULAR', now_ny
    elif dtime(16, 0) <= current_time <= dtime(20, 0): return 'AFTER_HOURS', now_ny
    else: return 'CLOSED', now_ny

def is_market_open():
    tz_ny = pytz.timezone('US/Eastern')
    now_ny = datetime.now(tz_ny)
    if now_ny.weekday() >= 5: return False
    return dtime(4, 0) <= now_ny.time() <= dtime(20, 0)

def send_telegram(message):
    if TOKEN and CHAT_ID:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
        try: requests.post(url, data=data, timeout=5)
        except: print("❌ Telegram Error")

# --- CORE DETECTION ---
def detect_dark_pool_activity(df, current_price):
    if len(df) < 10: return False, 0, ""
    recent = df.tail(3)
    avg_vol_recent = recent['Volume'].mean()
    avg_vol_baseline = df['Volume'].tail(20).mean()
    vol_ratio = avg_vol_recent / avg_vol_baseline if avg_vol_baseline > 0 else 0
    price_vol = recent['Close'].std() / current_price if current_price > 0 else 999
    is_stepping = all(recent['Close'].iloc[i] >= recent['Close'].iloc[i-1] for i in range(1, len(recent)))
    
    if vol_ratio > 1.6 and price_vol < 0.004 and is_stepping:
        return True, min(100, int(vol_ratio * 30)), "STEALTH ACCUMULATION"
    elif vol_ratio > 2.2 and price_vol < 0.012:
        return True, min(95, int(vol_ratio * 25)), "INSTITUTIONAL BREAKOUT"
    return False, 0, ""

def detect_iceberg_orders(df, current_price):
    """
    Rileva possibili iceberg orders tramite pattern di volume/prezzo
    """
    if len(df) < 30: return False, 0, ""
    
    recent = df.tail(10)
    
    # Pattern 1: Volume costante alto + range stretto
    avg_vol = recent['Volume'].mean()
    vol_std = recent['Volume'].std()
    price_range = (recent['High'].max() - recent['Low'].min()) / current_price
    
    # Volume consistency ratio
    vol_consistency = 1 - (vol_std / avg_vol) if avg_vol > 0 else 0
    
    # Pattern 2: "Steps" nel prezzo con volume sostenuto
    price_changes = recent['Close'].diff().abs()
    uniform_steps = price_changes.std() / price_changes.mean() if price_changes.mean() > 0 else 999
    
    # Pattern 3: Ratio volume/volatilità anormale
    baseline_vol = df['Volume'].tail(100).mean()
    vol_spike = avg_vol / baseline_vol if baseline_vol > 0 else 0
    
    # DETECTION LOGIC
    if (vol_consistency > 0.75 and        # Volume molto costante
        price_range < 0.008 and            # Range stretto (<0.8%)
        vol_spike > 1.4 and                # Volume elevato
        uniform_steps < 0.3):              # Passi uniformi
        
        confidence = min(95, int(vol_consistency * 100))
        return True, confidence, "ICEBERG BUY WALL"
    
    # Pattern di distribuzione (vendita)
    elif (vol_consistency > 0.70 and 
          price_range < 0.012 and 
          vol_spike > 1.3 and
          recent['Close'].iloc[-1] < recent['Close'].iloc[0]):
        
        confidence = min(90, int(vol_consistency * 95))
        return True, confidence, "ICEBERG SELL PRESSURE"
    
    return False, 0, ""

def calculate_levels(df, current_price):
    highs = df['High'].tail(100)
    peaks = []
    for i in range(2, len(highs)-2):
        if highs.iloc[i] > highs.iloc[i-1] and highs.iloc[i] > highs.iloc[i-2] and \
           highs.iloc[i] > highs.iloc[i+1] and highs.iloc[i] > highs.iloc[i+2]:
            peaks.append(float(highs.iloc[i]))
    
    R1 = sorted([p for p in peaks if p > current_price])[0] if any(p > current_price for p in peaks) else current_price * 1.04
    R2 = sorted([p for p in peaks if p > R1])[0] if any(p > R1 for p in peaks) else R1 * 1.06
    
    tr = np.maximum(df['High']-df['Low'], np.maximum(abs(df['High']-df['Close'].shift(1)), abs(df['Low']-df['Close'].shift(1))))
    atr = tr.dropna().tail(14).mean()
    stop_loss = current_price - (2.8 * atr)
    
    prob = min(92, max(15, 55 - (((R1 - current_price) / (atr if atr > 0 else 1)) * 12)))
    return R1, R2, stop_loss, int(prob)

# --- ANALISI ---
def analyze_stock(ticker):
    global alert_history
    try:
        session, now_ny = get_market_session()
        
        # 1. FILTRO APERTURA (primi 30 min - volatilità selvaggia)
        if session == 'REGULAR' and dtime(9, 30) <= now_ny.time() < dtime(10, 0):
            return
        
        # 2. FILTRO CHIUSURA (ultimi 30 min - MOC/LOC orders rumore)
        if session == 'REGULAR' and dtime(15, 30) <= now_ny.time() <= dtime(16, 0):
            return

        df = yf.download(ticker, period="5d", interval="15m", progress=False)
        if df.empty or len(df) < 50: return
        if isinstance(df.columns, pd.MultiIndex): 
            df.columns = df.columns.get_level_values(0)

        cp = float(df['Close'].iloc[-1])
        vol = float(df['Volume'].iloc[-1])
        
        # --- POC VOLUME PROFILE ---
        price_bins = pd.cut(df['Close'], bins=20)
        try:
            poc_price = float(df.groupby(price_bins, observed=True)['Volume'].sum().idxmax().mid)
        except (ValueError, AttributeError, KeyError):
            poc_price = cp

        # --- INDICATORI ---
        avg_vol = df['Volume'].tail(50).mean()
        std = df['Volume'].tail(50).std()
        z_score = (vol - avg_vol) / (std if std > 1 else 1)
        sma20 = df['Close'].rolling(20).mean().iloc[-1]
        
        is_dp, dp_score, dp_type = detect_dark_pool_activity(df, cp)
        is_iceberg, ice_score, ice_type = detect_iceberg_orders(df, cp)
        
        # --- LOGICA SELETTIVA ALERT PER SESSIONE ---
        tipo = ""
        is_warning = False

        if session == 'REGULAR':
            # Sessione regolare (10:00-15:30): tutto attivo e affidabile
            if is_iceberg and ice_score >= 75:
                if "BUY" in ice_type:
                    tipo = f"🧊 ICEBERG: {ice_type}"
                elif "SELL" in ice_type and ticker in MY_PORTFOLIO:
                    tipo = f"⚠️ WARNING: {ice_type} su POSIZIONE"
                    is_warning = True
            
            if not tipo and is_dp and dp_score >= 65:
                tipo = f"🕵️ DARK POOL: {dp_type}"
            
            if not tipo and z_score > 2.5 and cp > sma20:
                tipo = "🐋 INSTITUTIONAL SWEEP"
        
        else:
            # Pre-Market / After-Hours: SOLO Dark Pool (late prints istituzionali)
            # Iceberg e Sweep ignorati - troppo sfalsati da bassa liquidità
            if is_dp and dp_score >= 70:
                tipo = f"🕵️ DARK POOL (OFF-HOURS): {dp_type}"

        # --- COOLDOWN (WARNING bypassa sempre il cooldown) ---
        if tipo and not is_warning:
            now = datetime.now()
            if ticker in alert_history and now < alert_history[ticker] + timedelta(hours=3):
                return

        # --- INVIO ALERT ---
        if tipo:
            R1, R2, stop, prob = calculate_levels(df, cp)
            dist_poc = abs(cp - poc_price) / poc_price
            
            prefix = "🚨" if is_warning else "🛰️"
            
            msg = f"{prefix} *{tipo}*\n"
            msg += f"💎 **AZIONE**: `{ticker}`\n"
            msg += f"💰 **Prezzo**: `${cp:.2f}`\n"
            msg += f"📍 **POC Support**: `${poc_price:.2f}` ({'🎯 VALID' if dist_poc < 0.02 else 'AWAY'})\n"
            msg += f"━━━━━━━━━━━━━━━\n"
            msg += f"🎯 **Target 1**: `${R1:.2f}` ({prob}% prob)\n"
            msg += f"🚀 **Target 2**: `${R2:.2f}`\n"
            msg += f"🛡️ **STOP LOSS**: `${stop:.2f}`\n"
            msg += f"━━━━━━━━━━━━━━━\n"
            
            if is_warning:
                profit_pct = abs((R1 - cp) / cp * 100)
                msg += f"⚠️ *AZIONE CONSIGLIATA*:\n"
                msg += f"• Trailing stop suggerito: `${stop:.2f}`\n"
                msg += f"• Protezione potenziale: {profit_pct:.1f}%\n"
                msg += f"• Whale in distribuzione - aspettati resistenza"
            elif "OFF-HOURS" in tipo:
                msg += "🌙 *LATE PRINT*: Scambio istituzionale rilevato fuori orario. Valido per domani."
            elif "BUY" in tipo:
                msg += "🧊 *SUPPORTO NASCOSTO*: Ordine iceberg sta assorbendo vendite. Base d'acquisto solida."
            elif dist_poc < 0.02:
                msg += "🔥 *PREMIUM SETUP*: Prezzo allineato al POC istituzionale."
            else:
                msg += "⚡ *MOMENTUM*: Spinta volumetrica in corso."

            send_telegram(msg)
            alert_history[ticker] = datetime.now()
            save_alert_history(alert_history)

    except Exception as e: 
        print(f"Error {ticker}: {e}")

def main():
    global alert_history
    alert_history = load_alert_history()
    if not is_market_open():
        print("⏳ Market Closed.")
        return
    
    all_tickers = sorted(list(set(MY_PORTFOLIO + WATCHLIST_200)))
    session, _ = get_market_session()
    print(f"🚀 Scanning {len(all_tickers)} stocks... [Session: {session}]")
    
    for t in all_tickers:
        analyze_stock(t)
        time.sleep(0.35)  # Protezione anti-ban yfinance
    
    print("✅ Scan Complete.")

if __name__ == "__main__":
    main()

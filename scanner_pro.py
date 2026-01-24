import yfinance as yf
import pandas as pd
import datetime
import os
import requests
import time

# --- 1. CONFIGURAZIONE ---
MY_PORTFOLIO = ["STNE"]
ORARI_CACCIA = [15, 18, 20] # 16:00, 19:00, 21:00 ITA

# DATI PER CHIAMATA
PHONE_NUMBER = "39XXXXXXXXXX" # Sostituisci con il tuo numero
CALL_API_KEY = os.getenv("CALL_API_KEY") 

FULL_WATCHLIST = ["STNE", "NU", "PAGS", "MELI", "SOFI", "UPST", "AFRM", "HOOD", "SQ", "PYPL", "COIN", "XP", "BBD", "ITUB", "GS", "MS", "TOST", "FLYR", "BILL", "ADYEN", "VRT", "ANET", "APP", "PSTG", "SMCI", "LUMN", "PLTR", "MSTR", "NVDA", "AMD", "AVGO", "ARM", "MRVL", "ALAB", "AMBA", "AEIS", "BSX", "TSM", "ASML", "KLAC", "LRCX", "MU", "TDC", "HPE", "DELL", "CRWD", "NET", "OKTA", "ZS", "DDOG", "SNOW", "PANW", "FTNT", "S", "PATH", "IOT", "GTLB", "TEAM", "WDAY", "NOW", "MDB", "ESTC", "SPLK", "ZEN", "APPS", "DOCU", "TWLO", "GDDY", "ADBE", "CRM", "SHOP", "SE", "U", "RBLX", "DUOL", "MNSO", "DASH", "UBER", "LYFT", "ABNB", "BKNG", "CPNG", "RVLV", "FIGS", "PINS", "SNAP", "ROKU", "ETSY", "DKNG", "SKLZ", "CLOV", "MEDP", "HALO", "KRYS", "VRTX", "AMGN", "TDOC", "RXRX", "ILMN", "EXAS", "CRSP", "BEAM", "NTLA", "EDIT", "mRNA", "BNTX", "SAVA", "CERE", "BIIB", "REGN", "ON", "TER", "ENTG", "WOLF", "LSCC", "QRVO", "SWKS", "MP", "INDI", "POWI", "RMBS", "MTSI", "SIAB", "MXL", "DIOD", "TSLA", "RIVN", "LCID", "NIO", "XPEV", "LI", "FSLR", "ENPH", "SEDG", "RUN", "CHPT", "BLNK", "PLUG", "SPCE", "RKLB", "BOWL", "QS", "PSNY", "NKLA", "BE", "MARA", "RIOT", "CLSK", "IREN", "WULF", "HIVE", "BITF", "BTBT", "CORZ", "CIFR", "CELH", "WING", "BOOT", "LULU", "ONON", "SKX", "DECK", "BIRK", "ELF", "MNST", "SBUX", "CMG", "SHAK", "CAVA"]

# --- 2. FUNZIONI DI SERVIZIO ---
def send_telegram(message):
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id: return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

def make_call(ticker, reason):
    if not CALL_API_KEY: return
    text = f"Attenzione! Segnale di {reason} su {ticker}. Controlla Telegram."
    url = f"https://api.callmebot.com/start.php?user={PHONE_NUMBER}&text={text}&apikey={CALL_API_KEY}"
    try: requests.get(url, timeout=10)
    except: pass

def calculate_rsi(prices, period=14):
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# --- 3. CORE ANALISI ---
def analyze_stock(ticker, is_full_scan):
    try:
        df = yf.download(ticker, period="5d", interval="15m", progress=False)
        if df.empty: return False

        cp = float(df['Close'].iloc[-1])
        lp = float(df['Close'].iloc[-2])
        vol = float(df['Volume'].iloc[-1])
        avg_vol = float(df['Volume'].mean())
        df['RSI'] = calculate_rsi(df['Close'])
        rsi = float(df['RSI'].iloc[-1])
        
        support_level = float(df['Low'].tail(100).min())
        is_at_support = cp <= (support_level * 1.015) 
        
        found = False

        # 🛡️ EXIT ALERT: Messaggio + Chiamata ⚠️
        if ticker in MY_PORTFOLIO and rsi > 75:
            send_telegram(f"⚠️ *EXIT ALERT*: {ticker}\nRILEVATO ECCESSO RSI: {rsi:.2f}\nPrezzo: ${cp:.2f}")
            make_call(ticker, "VENDITA")
            found = True

        # 🚀 SCANSIONE VOLUMI
        mult = 1.5 if is_full_scan else 2.5
        if vol > (avg_vol * mult):
            trend_emoji = "📈" if cp > lp else "📉"
            
            # OPTION SWEEP: Messaggio + Chiamata 🔥
            if vol > (avg_vol * 2.5):
                label = "🔥 *OPTION SWEEP*"
                send_telegram(f"{label} su *{ticker}*\nStato: RISALITA AGGRESSIVA {trend_emoji}\nPrezzo: ${cp:.2f}\nVol: {vol:.0f}\nRSI: {rsi:.2f}")
                make_call(ticker, "URGENZA ISTITUZIONALE")
            
            # ICEBERG: Solo Messaggio 🧊
            else:
                label = "🧊 *ICEBERG DETECTED*"
                extra_tip = "\n🎯 *LIVELLO OTTIMALE (Vicino Supporto)*" if (is_at_support and cp <= lp) else ""
                send_telegram(f"{label} su *{ticker}*\nStato: {'RISALITA' if cp > lp else 'ACCUMULO'} {trend_emoji}\nPrezzo: ${cp:.2f}\nRSI: {rsi:.2f}{extra_tip}")
            
            found = True
        return found
    except: return False

def main():
    now = datetime.datetime.now()
    # if now.weekday() > 4: return  <-- DISATTIVATO PER TEST
    # if now.hour < 14 or (now.hour >= 21 and now.minute > 15): return <-- DISATTIVATO PER TEST

    if True: # FORZA CACCIA PER TEST
        tickers = list(set(FULL_WATCHLIST + MY_PORTFOLIO))
        mode = "CACCIA"
        head = f"🚀 *TEST FUNZIONAMENTO* ({now.strftime('%H:%M')} UTC)"
    else:
        tickers = MY_PORTFOLIO
        mode = "DIFESA"
        head = f"🛡️ *CHECK DIFESA* ({now.strftime('%H:%M')} UTC)"

    alert_count = 0
    for t in tickers:
        if analyze_stock(t, mode == "CACCIA"): alert_count += 1
        time.sleep(0.3)

    send_telegram(f"{head}\n🏁 Test completato. Trovati {alert_count} segnali.")

import yfinance as yf
import pandas as pd
import datetime
import os
import requests
import time

# --- 1. CONFIGURAZIONE ---
MY_PORTFOLIO = ["STNE"] # I tuoi titoli
ORARI_CACCIA = [14, 17, 20] # 15:00, 18:00, 21:00 Italiane

FULL_WATCHLIST = [
    "STNE", "NU", "PAGS", "MELI", "SOFI", "UPST", "AFRM", "HOOD", "SQ", "PYPL", "COIN", "XP", "BBD", "ITUB", "GS", "MS", "TOST", "FLYR", "BILL", "ADYEN",
    "VRT", "ANET", "APP", "PSTG", "SMCI", "LUMN", "PLTR", "MSTR", "NVDA", "AMD", "AVGO", "ARM", "MRVL", "ALAB", "AMBA", "AEIS", "BSX", "TSM", "ASML", "KLAC", "LRCX", "MU", "TDC", "HPE", "DELL",
    "CRWD", "NET", "OKTA", "ZS", "DDOG", "SNOW", "PANW", "FTNT", "S", "PATH", "IOT", "GTLB", "TEAM", "WDAY", "NOW", "MDB", "ESTC", "SPLK", "ZEN", "APPS", "DOCU", "TWLO", "GDDY", "ADBE", "CRM",
    "SHOP", "SE", "U", "RBLX", "DUOL", "MNSO", "DASH", "UBER", "LYFT", "ABNB", "BKNG", "CPNG", "RVLV", "FIGS", "PINS", "SNAP", "ROKU", "ETSY", "DKNG", "SKLZ",
    "CLOV", "MEDP", "HALO", "KRYS", "VRTX", "AMGN", "TDOC", "RXRX", "ILMN", "EXAS", "CRSP", "BEAM", "NTLA", "EDIT", "mRNA", "BNTX", "SAVA", "CERE", "BIIB", "REGN",
    "ON", "TER", "ENTG", "WOLF", "LSCC", "QRVO", "SWKS", "MP", "INDI", "POWI", "RMBS", "MTSI", "SIAB", "MXL", "DIOD",
    "TSLA", "RIVN", "LCID", "NIO", "XPEV", "LI", "FSLR", "ENPH", "SEDG", "RUN", "CHPT", "BLNK", "PLUG", "SPCE", "RKLB", "BOWL", "QS", "PSNY", "NKLA", "BE",
    "MARA", "RIOT", "CLSK", "IREN", "WULF", "HIVE", "BITF", "BTBT", "CORZ", "CIFR",
    "CELH", "WING", "BOOT", "LULU", "ONON", "SKX", "DECK", "BIRK", "ELF", "MNST", "SBUX", "CMG", "SHAK", "CAVA"
]

# --- 2. FUNZIONI ---
def send_telegram(message):
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id: return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

def calculate_rsi(prices, period=14):
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def analyze_stock(ticker, is_full_scan):
    try:
        df = yf.download(ticker, period="3d", interval="15m", progress=False)
        if df.empty: return False

        cp = float(df['Close'].iloc[-1])
        lp = float(df['Close'].iloc[-2])
        vol = float(df['Volume'].iloc[-1])
        avg_vol = float(df['Volume'].mean())
        df['RSI'] = calculate_rsi(df['Close'])
        rsi = float(df['RSI'].iloc[-1])
        
        found = False

        # --- LOGICA EXIT (PORTFOLIO) ---
        if ticker in MY_PORTFOLIO and rsi > 75:
            send_telegram(f"⚠️ *EXIT ALERT*: {ticker}\nRSI: {rsi:.2f} (Eccesso)\nPrezzo: ${cp:.2f}")
            found = True

        # --- LOGICA CACCIA (ICEBERG/SWEEP) ---
        mult = 1.5 if is_full_scan else 2.5
        if vol > (avg_vol * mult):
            trend = "📈" if cp > lp else "📉"
            stato = "IN RISALITA" if cp > lp else "IN COSTRUZIONE (Accumulo sui minimi)"
            label = "🔥 *OPTION SWEEP*" if vol > (avg_vol * 2.5) else "🧊 *ICEBERG DETECTED*"
            
            send_telegram(f"{label} su *{ticker}*\nStato: {stato} {trend}\nPrezzo: ${cp:.2f}\nVol: {vol:.0f} (vs Avg: {avg_vol:.0f})\nRSI: {rsi:.2f}")
            found = True
        return found
    except: return False

def main():
    now = datetime.datetime.now()
    if now.hour in ORARI_CACCIA and now.minute < 25:
        mode, tickers = "CACCIA", list(set(FULL_WATCHLIST + MY_PORTFOLIO))
        head = f"🚀 *SCANSIONE CACCIA* ({now.strftime('%H:%M')} UTC)"
    else:
        mode, tickers = "DIFESA", MY_PORTFOLIO
        head = f"🛡️ *CHECK DIFESA* ({now.strftime('%H:%M')} UTC)"

    alert_count = 0
    for t in tickers:
        if analyze_stock(t, mode == "CACCIA"): alert_count += 1
        time.sleep(0.3)

    if alert_count == 0:
        msg = "Nessun movimento istituzionale." if mode == "CACCIA" else "Portafoglio sotto controllo, nessun segnale."
        send_telegram(f"{head}\n✅ *OK*: {msg}")

if __name__ == "__main__":
    main()

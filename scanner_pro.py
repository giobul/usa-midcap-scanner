import yfinance as yf
import pandas as pd
import os
import requests
import datetime
import logging

logging.getLogger('yfinance').setLevel(logging.CRITICAL)

# --- CONFIGURAZIONE ---
MY_PORTFOLIO = ["STNE", "PATH", "RGTI", "QUBT", "DKNG", "AI", "BBAI", "ADCT", "AGEN", "STX"]
FLAG_FILE = "scanner_started.txt" # File per ricordarsi dell'avvio giornaliero

def send_telegram(message):
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id: return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    try: requests.post(url, json=payload, timeout=10)
    except: pass

def get_market_sentiment():
    try:
        idx = yf.download("QQQ", period="2d", interval="1d", progress=False)
        change = ((idx['Close'].iloc[-1] - idx['Close'].iloc[-2]) / idx['Close'].iloc[-2]) * 100
        if change > 0.5: return "🚀 BULLISH"
        if change < -0.5: return "📉 BEARISH"
        return "⚖️ NEUTRALE"
    except: return "❓ INCERTO"

def get_global_tickers():
    try:
        most_active = pd.read_html('https://finance.yahoo.com/most-active')[0]
        return most_active['Symbol'].tolist()
    except:
        return ["PLTR", "NVDA", "AMD", "TSLA"]

def analyze_stock(ticker, sentiment):
    # ... (La logica di analisi rimane la stessa delle versioni precedenti)
    try:
        df = yf.download(ticker, period="5d", interval="15m", progress=False, threads=False)
        if df.empty or len(df) < 25: return
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        
        cp = float(df['Close'].iloc[-1])
        lp = float(df['Close'].iloc[-2])
        vol_series = df['Volume'].tail(20)
        z_score = (float(df['Volume'].iloc[-1]) - vol_series.mean()) / vol_series.std() if vol_series.std() > 0 else 0
        rsi_val = (100 - (100 / (1 + (df['Close'].diff().where(df['Close'].diff() > 0, 0).rolling(14).mean() / -df['Close'].diff().where(df['Close'].diff() < 0, 0).rolling(14).mean())))).iloc[-1]
        var_pct_candela = abs((cp - lp) / lp) * 100
        res = float(df['High'].iloc[-21:-1].max())
        sup = float(df['Low'].iloc[-21:-1].min())
        
        soglia_z = 1.3 if ticker in MY_PORTFOLIO else 3.5 # Soglia più alta per il globale via Cron
        
        if z_score > soglia_z:
            if z_score > 5.0 and var_pct_candela <= 0.30:
                send_telegram(f"🌍 **CLIMA:** {sentiment}\n🌑 **DARK POOL: {ticker}**\nZ: {z_score:.1f}\nRSI: {rsi_val:.1f}")
            elif var_pct_candela <= 0.50:
                send_telegram(f"🌍 **CLIMA:** {sentiment}\n🧊 **ICEBERG: {ticker}**\nZ: {z_score:.1f}")
        
        if ticker in MY_PORTFOLIO and rsi_val >= 70.0:
            send_telegram(f"🏁 **TARGET {ticker}**: RSI {rsi_val:.1f}. Gain > 50€?")
    except: pass

def main():
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    now_time = int(datetime.datetime.now().strftime("%H%M"))
    
    # Esegui solo se la borsa è aperta (15:30 - 22:10)
    if now_time < 1530 or now_time > 2210:
        # Se la borsa è chiusa, cancelliamo il file flag per domani
        if os.path.exists(FLAG_FILE): os.remove(FLAG_FILE)
        return

    sentiment = get_market_sentiment()
    global_list = get_global_tickers()
    all_tickers = sorted(list(set(global_list + MY_PORTFOLIO)))

    # --- LOGICA MESSAGGIO DI AVVIO UNICO ---
    # Controlliamo se abbiamo già inviato il messaggio oggi
    already_started = False
    if os.path.exists(FLAG_FILE):
        with open(FLAG_FILE, "r") as f:
            if f.read().strip() == today:
                already_started = True

    if not already_started:
        send_telegram(f"✅ **SCANNER ATTIVO**\n🌍 Mercato: {sentiment}\n🔍 Analisi su {len(all_tickers)} titoli\n🚀 Caccia aperta!")
        with open(FLAG_FILE, "w") as f:
            f.write(today)

    # --- ESECUZIONE SINGOLA SCANSIONE (Il Cron Job la ripeterà) ---
    for t in all_tickers:
        analyze_stock(t, sentiment)

if __name__ == "__main__":
    main()

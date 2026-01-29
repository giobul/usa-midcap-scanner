import yfinance as yf
import pandas as pd
import datetime
import requests
import os
import time
import io
import numpy as np

# --- CONFIGURAZIONE ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
FLAG_FILE = "scanner_started.txt"

# Tuo Portfolio (Monitoraggio prioritario per Target 50€)
MY_PORTFOLIO = ["STNE", "PATH", "RGTI", "PLTR", "SOUN", "IONQ", "BBAI", "HIMS", "CLSK", "MARA"]

def send_telegram(message):
    if TOKEN and CHAT_ID:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
        try:
            requests.post(url, data=data)
        except Exception as e:
            print(f"Errore Telegram: {e}")

def get_market_sentiment():
    try:
        spy = yf.Ticker("SPY").history(period="2d")
        if len(spy) < 2: return "INDETERMINATO"
        change = ((spy['Close'].iloc[-1] - spy['Close'].iloc[-2]) / spy['Close'].iloc[-2]) * 100
        if change > 0.5: return "RIALZISTA 🚀"
        if change < -0.5: return "RIBASSISTA ⚠️"
        return "LATERALE ⚖️"
    except:
        return "NON DISPONIBILE"

def get_global_tickers():
    try:
        url = "https://finance.yahoo.com/markets/stocks/most-active/"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers)
        tables = pd.read_html(io.StringIO(response.text))
        df = tables[0]
        return df['Symbol'].head(100).tolist()
    except Exception as e:
        print(f"Errore recupero Top 100: {e}")
        return []

def analyze_stock(ticker, sentiment):
    try:
        df = yf.download(ticker, period="5d", interval="15m", progress=False)
        if df.empty or len(df) < 20: return

        cp = df['Close'].iloc[-1]
        lp = df['Close'].iloc[-2]
        open_p = df['Open'].iloc[-1]
        vol = df['Volume'].iloc[-1]
        
        # --- ANALISI VOLUMI (Soglia Test: 0.5) ---
        avg_vol = df['Volume'].rolling(window=10).mean().iloc[-1]
        std_vol = df['Volume'].rolling(window=10).std().iloc[-1]
        z_score = (vol - avg_vol) / std_vol if std_vol > 0 else 0

        # --- ANALISI RSI (Per Target 50€) ---
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss.replace(0, 0.001)
        rsi_val = float(100 - (100 / (1 + rs.iloc[-1])))

        # --- ANALISI SQUEEZE ---
        std_dev = df['Close'].rolling(window=20).std().iloc[-1]
        atr = (df['High'] - df['Low']).rolling(window=20).mean().iloc[-1]
        is_squeeze = std_dev < (atr * 0.5)

        header = "⭐ **PORTFOLIO** ⭐\n" if ticker in MY_PORTFOLIO else "✅ **ATTIVO**\n"
        var_pct_candela = ((cp - open_p) / open_p) * 100
        info = f"\n💰 Prezzo: ${cp:.2f} ({var_pct_candela:+.2f}%)\n🔥 RSI: {rsi_val:.1f}"

        # 1. LOGICA ALERT VOLUMI (Aggressiva)
        if z_score > 0.5 and cp > open_p:
            if z_score > 5.0 and abs(var_pct_candela) <= 0.25:
                send_telegram(f"{header}🌑 **DARK POOL: {ticker}**\nZ-Vol: {z_score:.1f}" + info)
            elif abs(var_pct_candela) <= 0.45:
                send_telegram(f"{header}🧊 **ICEBERG: {ticker}**\nZ-Vol: {z_score:.1f}" + info)
            else:
                send_telegram(f"{header}🐋 **SWEEP: {ticker}**\nZ-Vol: {z_score:.1f}" + info)

        # 2. LOGICA PROFITTO (Solo Portfolio)
        if ticker in MY_PORTFOLIO:
            if rsi_val >= 70.0: 
                send_telegram(f"🏁 **TARGET {ticker}**\nRSI: {rsi_val:.1f}\n📢 **AZIONE:** Valuta chiusura per profitto (>50€)!")
            
            if is_squeeze:
                ma20 = df['Close'].rolling(window=20).mean().iloc[-1]
                direzione = "📈 Rialzista" if cp > ma20 else "📉 Ribassista"
                send_telegram(f"⚡ **SQUEEZE {ticker}**\nDirezione: {direzione}\nPronto al Breakout!")

    except Exception as e:
        print(f"Errore analisi {ticker}: {e}")

def main():
    # Orario Italia (UTC+1)
    ora_ita = datetime.datetime.now() + datetime.timedelta(hours=1)
    today = ora_ita.strftime("%Y-%m-%d")
    now_time = int(ora_ita.strftime("%H%M"))
    
    print(f"--- LOG OPERATIVO ---")
    print(f"Orario ITA: {now_time}")

    # Rimosso blocco orario per permetterti il test immediato
    sentiment = get_market_sentiment()
    global_list = get_global_tickers()
    
    # Pulizia liste
    portfolio_clean = [str(t) for t in MY_PORTFOLIO if pd.notna(t)]
    global_clean = [str(t) for t in global_list if pd.notna(t)]
    all_tickers = sorted(list(set(portfolio_clean + global_clean)))

    if not os.path.exists(FLAG_FILE):
        send_telegram(f"🚀 **SCANNER TEST AVVIATO**\n🌍 Mercato: {sentiment}\n🔍 Analizzo {len(all_tickers)} titoli...")
        with open(FLAG_FILE, "w") as f: f.write(today)

    for t in all_tickers:
        analyze_stock(t, sentiment)
        time.sleep(0.5)

if __name__ == "__main__":
    main()

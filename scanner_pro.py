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
        c1 = float(spy['Close'].iloc[-1].item())
        c2 = float(spy['Close'].iloc[-2].item())
        change = ((c1 - c2) / c2) * 100
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

def analyze_stock(ticker):
    try:
        df = yf.download(ticker, period="5d", interval="15m", progress=False)
        if df.empty or len(df) < 20: return None

        cp = float(df['Close'].iloc[-1].item())
        open_p = float(df['Open'].iloc[-1].item())
        vol = float(df['Volume'].iloc[-1].item())
        
        avg_vol = float(df['Volume'].rolling(window=10).mean().iloc[-1].item())
        std_vol = float(df['Volume'].rolling(window=10).std().iloc[-1].item())
        z_score = (vol - avg_vol) / std_vol if std_vol > 0 else 0

        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss.replace(0, 0.001)
        rsi_val = float(100 - (100 / (1 + float(rs.iloc[-1].item()))))

        if cp > open_p and z_score > 0.5:
            var_pct = ((cp - open_p) / open_p) * 100
            header = "⭐ **PORTFOLIO** ⭐\n" if ticker in MY_PORTFOLIO else "✅ **ATTIVO**\n"
            msg = f"{header}Ticker: *{ticker}*\n💰 Prezzo: ${cp:.2f} ({var_pct:+.2f}%)\n📊 Z-Vol: {z_score:.2f}\n🔥 RSI: {rsi_val:.1f}"
            send_telegram(msg)
            return True
        return False
    except:
        return None

def main():
    ora_ita = datetime.datetime.now() + datetime.timedelta(hours=1)
    
    sentiment = get_market_sentiment()
    global_list = get_global_tickers()
    
    portfolio_clean = [str(t) for t in MY_PORTFOLIO if pd.notna(t)]
    global_clean = [str(t) for t in global_list if pd.notna(t)]
    all_tickers = sorted(list(set(portfolio_clean + global_clean)))

    send_telegram(f"🚀 **AVVIO SCANSIONE**\n🌍 Mercato: {sentiment}\n🔍 Analizzo {len(all_tickers)} titoli...")

    analizzati = []
    segnali_count = 0

    for t in all_tickers:
        # Chiamata corretta senza sentiment (allineamento fisso)
        risultato = analyze_stock(t)
        if risultato is not None:
            analizzati.append(t)
            if risultato is True:
                segnali_count += 1
        time.sleep(0.5)

    lista_txt = ", ".join(analizzati)
    report = (f"🏁 **FINE SCANSIONE**\n"
              f"📊 Titoli elaborati: {len(analizzati)}\n"
              f"📈 Segnali inviati: {segnali_count}\n"
              f"📋 Lista completa:\n`{lista_txt}`")
    
    send_telegram(report)

if __name__ == "__main__":
    main()

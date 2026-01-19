import subprocess
import sys
import os

# --- SISTEMA DI AUTO-INSTALLAZIONE ---
def install_and_import(package, import_name=None):
    if import_name is None:
        import_name = package
    try:
        __import__(import_name)
    except ImportError:
        print(f"Installazione forzata di {package}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])

# Lista delle librerie necessarie
install_and_import('pandas')
install_and_import('yfinance')
install_and_import('requests')
install_and_import('pandas-ta', 'pandas_ta')
install_and_import('google-generativeai', 'google.generativeai')

# --- IMPORTAZIONE EFFETTIVA ---
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import requests
import google.generativeai as genai
from datetime import datetime, timedelta

# --- CONFIGURAZIONE ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Configura Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# Lista Mid-Cap (Esempio principali Mid-Cap e titoli caldi)
TICKERS = [
    'PLTR', 'MSTR', 'RBLX', 'AFRM', 'U', 'SNOW', 'PATH', 'SHOP', 'NET', 'DDOG',
    'ZS', 'OKTA', 'COIN', 'HOOD', 'DKNG', 'PINS', 'SNAP', 'TWLO', 'MTTR', 'AI',
    'SOFI', 'UPST', 'LCID', 'RIVN', 'NIO', 'XPEV', 'LI', 'GME', 'AMC', 'MARA',
    'RIOT', 'CLSK', 'MDB', 'TEAM', 'WDAY', 'NOW', 'SNPS', 'CDNS', 'ANSS', 'SPLK',
    'CRWD', 'PANW', 'FTNT', 'NET', 'S', 'SENT', 'CELH', 'DUOL', 'MELI', 'SE'
]

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Errore Telegram: {e}")

def analyze_stock(ticker):
    try:
        df = yf.download(ticker, period="60d", interval="1d", progress=False)
        if df.empty or len(df) < 30:
            return None

        # Calcolo Indicatori Tecnici con pandas_ta
        df['RSI'] = ta.rsi(df['Close'], length=14)
        df['SMA20'] = ta.sma(df['Close'], length=20)
        df['SMA50'] = ta.sma(df['Close'], length=50)
        
        last_row = df.iloc[-1]
        prev_row = df.iloc[-2]
        
        current_price = last_row['Close']
        volume_ma = df['Volume'].tail(20).mean()
        current_volume = last_row['Volume']
        
        # FILTRI: Prezzo > SMA20, Volume > 1.5x media, RSI non in ipercomprato estremo
        if current_price > last_row['SMA20'] and current_volume > (volume_ma * 1.5) and last_row['RSI'] < 70:
            return {
                "ticker": ticker,
                "price": round(float(current_price), 2),
                "rsi": round(float(last_row['RSI']), 2),
                "vol_increase": round(float(current_volume / volume_ma), 2)
            }
    except Exception as e:
        print(f"Errore analisi {ticker}: {e}")
    return None

def get_ai_insight(data):
    prompt = f"""
    Analizza brevemente questo titolo Mid-Cap: {data['ticker']}.
    Prezzo: {data['price']}, RSI: {data['rsi']}, Incremento Volume: {data['vol_increase']}x.
    Identifica livelli di breakout e se c'è accumulazione istituzionale visibile dai volumi. 
    Sii sintetico e professionale.
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except:
        return "Insight AI non disponibile."

def main():
    print(f"Avvio scansione alle {datetime.now()}")
    found_stocks = []
    
    for ticker in TICKERS:
        result = analyze_stock(ticker)
        if result:
            found_stocks.append(result)
    
    if found_stocks:
        for stock in found_stocks:
            ai_text = get_ai_insight(stock)
            msg = (f"🚀 *SEGNALE MID-CAP: {stock['ticker']}*\n\n"
                   f"💰 Prezzo: ${stock['price']}\n"
                   f"📊 RSI: {stock['rsi']}\n"
                   f"📈 Volume: {stock['vol_increase']}x media\n\n"
                   f"🤖 *Analisi Gemini:* \n{ai_text}")
            send_telegram_message(msg)
            print(f"Inviato segnale per {stock['ticker']}")
    else:
        print("Nessun titolo soddisfa i criteri al momento.")

if __name__ == "__main__":
    main()

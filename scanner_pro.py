import os
import yfinance as yf
import requests
import pandas_ta as ta
import google.generativeai as genai
from datetime import datetime

# --- CARICAMENTO SEGRETI DA GITHUB ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

TICKERS = ["NVDA", "AMD", "SMCI", "PLTR", "ARM", "AVGO", "TSM", "MSFT", "GOOGL", "META", "MSTR", "MARA", "COIN", "CLSK", "RIOT", "HUT", "WULF", "VST", "SMR", "CCJ", "OKLO", "UUUU", "CEG", "NNE", "POWL", "APPF", "PSTG", "AA", "LITE", "FLEX", "UTHR", "GCT", "CELH", "SOUN", "BBAI", "IONQ", "RKLB", "PATH", "SNOW", "DDOG", "NET", "MU", "AMAT", "LRCX", "KLAC", "ASML", "ANET", "VRT", "PANW", "CRWD"]

def send_msg(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"})

def run_scanner():
    print(f"Inizio scansione: {datetime.now()}")
    for ticker in TICKERS:
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period="60d")
            if len(df) < 20: continue
            df['OBV'] = ta.obv(df['Close'], df['Volume'])
            obv_trend = "Crescente" if df['OBV'].iloc[-1] > df['OBV'].iloc[-5] else "Neutro"
            bbands = ta.bbands(df['Close'], length=20)
            bandwidth = (bbands['BBU_20_2.0'] - bbands['BBL_20_2.0']) / bbands['BBM_20_2.0']
            is_squeeze = "SQUEEZE" if bandwidth.iloc[-1] < 0.05 else "Range Ampio"
            last_price, last_vol = df['Close'].iloc[-1], df['Volume'].iloc[-1]
            avg_vol = df['Volume'].tail(20).mean()
            vol_ratio = round(last_vol/avg_vol, 1)

            if vol_ratio > 1.5 and obv_trend == "Crescente":
                prompt = f"Analizza {ticker} a ${last_price}. Volumi {vol_ratio}x, OBV {obv_trend}, {is_squeeze}. Verifica Option Sweeps istituzionali e breakout. Sii sintetico."
                analisi = model.generate_content(prompt).text
                send_msg(f"🚀 *GITHUB ALERT: {ticker}*\n💰 ${last_price:.2f} | 📊 {vol_ratio}x\n📈 OBV: {obv_trend}\n🤖 *IA:* {analisi}")
        except Exception as e: print(f"Errore {ticker}: {e}")

if __name__ == "__main__":
    run_scanner()

import os
import yfinance as yf
import requests
import pandas as pd
import pandas_ta as ta  # Nuova libreria per analisi tecnica avanzata
import google.generativeai as genai

# --- CONFIGURAZIONE ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-1.5-flash')

TICKERS = [
    "RUN", "ADCT", "DKNG", "APLD", "AXON", "CRWD", "ABCL", "ADBE", "AGEN", 
    "ALLR", "AMPX", "ACHR", "ARQT", "ARWR", "ADSK", "BBAI", "BBIO", "CARS", 
    "CSCO", "COGT", "COIN", "CRWV", "CRSP", "QBTS", "ETOR", "EXTR", "GILD", 
    "GOGO", "INOD", "ISP", "INTZ", "IONQ", "KRMN", "KPTI", "LYFT", "MU", 
    "MRNA", "NEGG", "NMIH", "NVDA", "OKLO", "OKTA", "ON", "OSCR", "OUST", 
    "PLTR", "PTCT", "QUBT", "RXRX", "RGC", "RNW", "RGTI", "SPMI", "SLDP", 
    "SOUN", "STLA", "SMCI", "SUPN", "SYM", "PATH", "VKTX", "VIR", "VOYG", 
    "NUVL", "WSBC", "STX", "MSTR", "AMD", "IBRX"
]

def send_msg(text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"})

def run_scanner():
    print("🚀 Inizio scansione professionale con filtri anti-falso...")
    for ticker in TICKERS:
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period="1y")
            if df.empty or len(df) < 200: continue
            
            # --- CALCOLI TECNICI ---
            # 1. Prezzo e SMA 200
            last_close = df['Close'].iloc[-1]
            sma_200 = df['Close'].rolling(window=200).mean().iloc[-1]
            
            # 2. Volume Ratio
            last_vol = df['Volume'].iloc[-1]
            avg_vol = df['Volume'].tail(20).mean()
            vol_ratio = last_vol / avg_vol
            
            # 3. RSI (Filtro Ipercomprato)
            df['RSI'] = ta.rsi(df['Close'], length=14)
            current_rsi = df['RSI'].iloc[-1]
            
            # 4. ATR ed Espansione del Range (Filtro Forza Reale)
            df['ATR'] = ta.atr(df['High'], df['Low'], df['Close'], length=14)
            avg_atr = df['ATR'].tail(10).mean()
            current_range = df['High'].iloc[-1] - df['Low'].iloc[-1]
            
            # --- LOGICA DEL FILTRO "ANTI-FALSO" ---
            is_bullish = last_close > sma_200
            is_volume_spike = vol_ratio > 1.5
            is_not_overbought = current_rsi < 70 # Non compriamo se è già troppo alto
            is_price_expansion = current_range > avg_atr # La candela deve essere "decisa"

            if is_bullish and is_volume_spike and is_not_overbought and is_price_expansion:
                
                prompt = (f"Analisi Professionale {ticker}. Prezzo: ${last_close:.2f}. "
                          f"Sopra SMA 200, Volume {vol_ratio:.1f}x, RSI: {current_rsi:.1f}. "
                          f"Verifica accumulazione istituzionale e identifica breakout validati dai flussi "
                          f"sopra le resistenze chiave. Cerca Option Sweeps insoliti.")
                
                analisi = model.generate_content(prompt).text
                
                msg = (f"💎 *DIAMOND SIGNAL: {ticker}*\n"
                       f"📊 Volume: *{vol_ratio:.1f}x* | RSI: *{current_rsi:.1f}*\n"
                       f"📈 Range: *Espansione rilevata* (> ATR)\n"
                       f"💰 Prezzo: ${last_close:.2f} (Sopra SMA 200)\n\n"
                       f"🤖 *ANALISI IA:* \n{analisi}")
                
                send_msg(msg)
                print(f"✅ SEGNALE VALIDATO: {ticker}")
            else:
                print(f"❌ {ticker}: Scartato (Filtri tecnici non superati)")
                
        except Exception as e:
            print(f"Errore su {ticker}: {e}")

if __name__ == "__main__":
    run_scanner()

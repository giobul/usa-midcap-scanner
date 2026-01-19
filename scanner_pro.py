import os
import sys
import pandas as pd
import yfinance as yf
import requests
import google.generativeai as genai
from datetime import datetime

# Gestione libreria tecnica
try:
    import pandas_ta as ta
    HAS_PANDAS_TA = True
except ImportError:
    HAS_PANDAS_TA = False

# Configurazione
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT = os.getenv("CHAT_ID")
API_KEY = os.getenv("GEMINI_API_KEY")

def get_ai_analysis(ticker, price, vol_ratio, stop_loss, target):
    if not API_KEY: return "Analisi AI non disponibile."
    try:
        genai.configure(api_key=API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = (f"Analizza breakout di {ticker} a ${price}. Volume {vol_ratio}x la media. "
                  f"Abbiamo impostato uno Stop Loss a ${stop_loss} e un Target a ${target}. "
                  f"Confermi che i livelli sono tecnici corretti? Indica eventuali resistenze vicine.")
        response = model.generate_content(prompt)
        return response.text
    except:
        return "Insight AI momentaneamente non disponibile."

def calculate_indicators(df):
    if HAS_PANDAS_TA:
        df['RSI'] = ta.rsi(df['Close'], length=14)
        df['SMA20'] = ta.sma(df['Close'], length=20)
        df['ATR'] = ta.atr(df['High'], df['Low'], df['Close'], length=14)
    else:
        # Calcolo manuale RSI e SMA
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / (loss + 1e-9)
        df['RSI'] = 100 - (100 / (1 + rs))
        df['SMA20'] = df['Close'].rolling(window=20).mean()
        df['ATR'] = (df['High'] - df['Low']).rolling(window=14).mean() # Semplificato
    return df

def main():
    # LISTA COMPLETA 110+ TITOLI
    tickers = [
        'ADCT', 'PLTR', 'MSTR', 'RBLX', 'AFRM', 'U', 'SNOW', 'PATH', 'SHOP', 'NET', 
        'DDOG', 'ZS', 'OKTA', 'COIN', 'HOOD', 'DKNG', 'PINS', 'SNAP', 'TWLO', 'MTTR', 
        'AI', 'SOFI', 'UPST', 'LCID', 'RIVN', 'NIO', 'XPEV', 'LI', 'GME', 'AMC', 
        'MARA', 'RIOT', 'CLSK', 'MDB', 'TEAM', 'WDAY', 'NOW', 'SNPS', 'CDNS', 'ANSS', 
        'CRWD', 'PANW', 'FTNT', 'S', 'SENT', 'CELH', 'DUOL', 'MELI', 'SE', 'ABNB', 
        'UBER', 'LYFT', 'DASH', 'RMD', 'TTD', 'ROKU', 'Z', 'EXPE', 'BKNG', 'PYPL', 
        'SQ', 'DOCU', 'ZM', 'BILL', 'VEEV', 'ARM', 'VRT', 'SMCI', 'RUN', 'APLD', 
        'AXON', 'ABCL', 'ADBE', 'AGEN', 'ALLR', 'AMPX', 'ACHR', 'ARQT', 'ARWR', 
        'ADSK', 'BBAI', 'BMPS', 'EMII', 'BBIO', 'CARS', 'CSCO', 'COGT', 'CRWV', 
        'CRSP', 'QBTS', 'ETOR', 'EXTR', 'GILD', 'GOGO', 'INOD', 'ISP', 'INTZ', 
        'IONQ', 'KRMN', 'KPTI', 'MU', 'MRNA', 'NEGG', 'NMIH', 'NVDA', 'OKLO', 
        'ON', 'OSCR', 'OUST', 'PTCT', 'QUBT', 'QS', 'RXRX', 'RGC', 'RNW', 'RGTI', 
        'SPMI', 'SLDP', 'SOUN', 'STLA', 'SUPN', 'SYM', 'TLIT', 'VKTX', 'VIR', 
        'VOYG', 'JUNS', 'NUVL', 'WSBC', 'STX'
    ]
    
    for t in tickers:
        try:
            df = yf.download(t, period="60d", interval="1d", progress=False)
            if df.empty: continue
            df = calculate_indicators(df)
            last = df.iloc[-1]
            vol_ratio = round(float(last['Volume'] / df['Volume'].tail(20).mean()), 2)
            
            if last['Close'] > last['SMA20'] and vol_ratio > 1.5:
                # CALCOLO LIVELLI OPERATIVI
                price = round(float(last['Close']), 2)
                # Stop Loss: sotto la SMA20 o 2 volte l'ATR (volatilità)
                stop_loss = round(price - (float(last['ATR']) * 1.5), 2)
                # Target: Rischio/Rendimento 1:2
                target = round(price + (price - stop_loss) * 2, 2)
                
                ai_text = get_ai_analysis(t, price, vol_ratio, stop_loss, target)
                
                msg = (f"🎯 **PIANO OPERATIVO: {t}**\n"
                       f"💰 Prezzo Entrata: **${price}**\n"
                       f"📈 Vol Ratio: {vol_ratio}x\n"
                       f"🛡️ Stop Loss: `${stop_loss}`\n"
                       f"🚀 Target Price: `${target}`\n"
                       f"📊 RSI: {round(float(last['RSI']), 2)}\n\n"
                       f"🤖 **Analisi:** {ai_text}")
                
                requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                              json={"chat_id": CHAT, "text": msg, "parse_mode": "Markdown"})
        except: continue

if __name__ == "__main__":
    main()

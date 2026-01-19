import os
import sys
import pandas as pd
import yfinance as yf
import requests
import google.generativeai as genai
from datetime import datetime

# Gestione libreria tecnica (Calcolo manuale se fallisce import)
try:
    import pandas_ta as ta
    HAS_PANDAS_TA = True
except ImportError:
    HAS_PANDAS_TA = False

# Configurazione
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT = os.getenv("CHAT_ID")
API_KEY = os.getenv("GEMINI_API_KEY")

def get_ai_analysis(ticker, price, vol_ratio):
    if not API_KEY: return "Analisi AI non disponibile."
    try:
        genai.configure(api_key=API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = (f"Analizza breakout di {ticker} a ${price}. Volume {vol_ratio}x la media. "
                  f"Identifica se ci sono resistenze chiave e se il segnale indica accumulazione istituzionale.")
        response = model.generate_content(prompt)
        return response.text
    except:
        return "Insight AI momentaneamente non disponibile."

def calculate_indicators(df):
    if HAS_PANDAS_TA:
        df['RSI'] = ta.rsi(df['Close'], length=14)
        df['SMA20'] = ta.sma(df['Close'], length=20)
    else:
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / (loss + 1e-9)
        df['RSI'] = 100 - (100 / (1 + rs))
        df['SMA20'] = df['Close'].rolling(window=20).mean()
    return df

def main():
    print(f"Scanner Online - Avvio scansione su {len(tickers_list)} titoli alle {datetime.now().strftime('%H:%M')}")
    
    # LISTA COMPLETA UNIFICATA (Precedenti + Immagine, senza duplicati)
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
        'IONQ', 'KRMN', 'KPTI', 'LYSDY', 'MU', 'MRNA', 'NEGG', 'NMIH', 'NVDA', 
        'OKLO', 'ON', 'OSCR', 'OUST', 'PTCT', 'QUBT', 'QS', 'RXRX', 'RGC', 'RNW', 
        'RGTI', 'SPMI', 'SLDP', 'SOUN', 'STLA', 'SUPN', 'SYM', 'TLIT', 'VKTX', 
        'VIR', 'VOYG', 'JUNS', 'NUVL', 'WSBC', 'STX'
    ]
    
    found_any = False
    for t in tickers:
        try:
            df = yf.download(t, period="60d", interval="1d", progress=False)
            if df.empty or len(df) < 20: continue
            
            df = calculate_indicators(df)
            last = df.iloc[-1]
            vol_ma = df['Volume'].tail(20).mean()
            vol_ratio = round(float(last['Volume'] / vol_ma), 2)
            
            # FILTRO: Prezzo > SMA20 e Volume > 1.5x (Accumulazione Istituzionale)
            if last['Close'] > last['SMA20'] and vol_ratio > 1.5:
                found_any = True
                ai_text = get_ai_analysis(t, round(float(last['Close']), 2), vol_ratio)
                
                status = "🔥 VOLUME ANOMALO" if vol_ratio > 2.5 else "🚀 ACCUMULAZIONE"
                
                msg = (f"{status}: *{t}*\n"
                       f"💰 Prezzo: ${round(float(last['Close']), 2)}\n"
                       f"📈 Vol Ratio: {vol_ratio}x\n"
                       f"📊 RSI: {round(float(last['RSI']), 2)}\n\n"
                       f"🤖 *Analisi Gemini:* \n{ai_text}")
                
                requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                              json={"chat_id": CHAT, "text": msg, "parse_mode": "Markdown"})
                print(f"Segnale inviato per {t}")
        except Exception as e:
            print(f"Errore su {t}: {e}")

    if not found_any:
        print("Scansione completata. Nessun movimento rilevante.")

if __name__ == "__main__":
    main()

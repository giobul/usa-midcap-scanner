import os
import yfinance as yf
import requests
import google.generativeai as genai
from datetime import datetime

# Configurazione Segreti
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT = os.getenv("TELEGRAM_CHAT_ID")
API_KEY = os.getenv("GEMINI_API_KEY")

def get_ai_analysis(ticker, price, vol_ratio, iceberg_score, stop_loss, target):
    if not API_KEY: return "Analisi AI non disponibile."
    try:
        genai.configure(api_key=API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = (f"Analizza brevemente $ {ticker} a ${price}. Volume {vol_ratio}x la media. "
                  f"Iceberg Strength: {iceberg_score}/100. Valida l'accumulazione.")
        response = model.generate_content(prompt)
        return response.text
    except:
        return "Insight AI momentaneamente non disponibile."

def main():
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

    found_alerts = 0
    total_scanned = len(tickers)
    print(f"Avvio scansione su {total_scanned} titoli...")

    for t in tickers:
        try:
            df = yf.download(t, period="60d", interval="1d", progress=False)
            if df.empty or len(df) < 20: continue
            
            last = df.iloc[-1]
            sma20 = df['Close'].rolling(window=20).mean().iloc[-1]
            vol_ma = df['Volume'].tail(20).mean()
            vol_ratio = round(float(last['Volume'] / vol_ma), 2)
            
            price_range = abs(last['High'] - last['Low']) / last['Close']
            iceberg_score = int(min((vol_ratio / (price_range * 50 + 0.01)) * 10, 100))
            
            # FILTRO ORIGINALE RIPRISTINATO
            if last['Close'] > sma20 and vol_ratio > 1.2:
                found_alerts += 1
                price = round(float(last['Close']), 2)
                atr = (df['High'] - df['Low']).tail(14).mean()
                stop_loss = round(min(float(sma20), price - (float(atr) * 1.5)), 2)
                target = round(price + (price - stop_loss) * 2, 2)
                
                ai_text = get_ai_analysis(t, price, vol_ratio, iceberg_score, stop_loss, target)
                
                header = "🧊 ICEBERG ALERT" if iceberg_score > 70 else "🚀 BREAKOUT"
                msg = (f"{header}: *{t}*\n💰 Prezzo: **${price}**\n📊 Iceberg: `{iceberg_score}/100`\n"
                       f"📈 Vol Ratio: {vol_ratio}x\n🛡️ SL: `${stop_loss}` | TP: `${target}`\n🤖 AI: {ai_text}")
                
                requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                              json={"chat_id": CHAT, "text": msg, "parse_mode": "Markdown"})
        except Exception as e:
            print(f"Errore su {t}: {e}")

    # Messaggio finale di stato
    if found_alerts == 0:
        print("Nessun segnale trovato. Invio messaggio di stato...")
        status_msg = (f"☕ *Scansione Completata*\n"
                      f"Analizzati {total_scanned} titoli.\n"
                      f"Nessun segnale rilevato con i filtri attuali (Prezzo > SMA20 e Vol > 1.2x).")
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                      json={"chat_id": CHAT, "text": status_msg, "parse_mode": "Markdown"})

if __name__ == "__main__":
    main()

import os
import yfinance as yf
import requests
import google.generativeai as genai
import pandas as pd
from datetime import datetime

# Configurazione Segreti
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT = os.getenv("TELEGRAM_CHAT_ID")
API_KEY = os.getenv("GEMINI_API_KEY")

def get_ai_analysis(ticker, price, vol_ratio, iceberg_score, earn_date):
    if not API_KEY: return "Analisi AI non disponibile."
    try:
        genai.configure(api_key=API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = (f"Analizza $ {ticker} a ${price}. Volume {vol_ratio}x. Iceberg Score: {iceberg_score}/100. "
                  f"Trimestrali il: {earn_date}. Valuta se è un accumulo sano per un 'run-up' pre-earnings "
                  f"o se è un rischio speculativo eccessivo.")
        response = model.generate_content(prompt)
        return response.text
    except:
        return "Insight AI momentaneamente non disponibile."

def main():
    # Lista Mid-Cap USA
    tickers = ['ADCT', 'PLTR', 'MSTR', 'RBLX', 'AFRM', 'U', 'SNOW', 'PATH', 'SHOP', 'NET', 'DDOG', 'ZS', 'OKTA', 'COIN', 'HOOD', 'DKNG', 'PINS', 'SNAP', 'TWLO', 'MTTR', 'AI', 'SOFI', 'UPST', 'LCID', 'RIVN', 'NIO', 'XPEV', 'LI', 'GME', 'AMC', 'MARA', 'RIOT', 'CLSK', 'MDB', 'TEAM', 'WDAY', 'NOW', 'SNPS', 'CDNS', 'ANSS', 'CRWD', 'PANW', 'FTNT', 'S', 'SENT', 'CELH', 'DUOL', 'MELI', 'SE', 'ABNB', 'UBER', 'LYFT', 'DASH', 'RMD', 'TTD', 'ROKU', 'Z', 'EXPE', 'BKNG', 'PYPL', 'SQ', 'DOCU', 'ZM', 'BILL', 'VEEV', 'ARM', 'VRT', 'SMCI', 'RUN', 'APLD', 'AXON', 'ABCL', 'ADBE', 'AGEN', 'ALLR', 'AMPX', 'ACHR', 'ARQT', 'ARWR', 'ADSK', 'BBAI', 'BMPS', 'EMII', 'BBIO', 'CARS', 'CSCO', 'COGT', 'CRWV', 'CRSP', 'QBTS', 'ETOR', 'EXTR', 'GILD', 'GOGO', 'INOD', 'ISP', 'INTZ', 'IONQ', 'KRMN', 'KPTI', 'MU', 'MRNA', 'NEGG', 'NMIH', 'NVDA', 'OKLO', 'ON', 'OSCR', 'OUST', 'PTCT', 'QUBT', 'QS', 'RXRX', 'RGC', 'RNW', 'RGTI', 'SPMI', 'SLDP', 'SOUN', 'STLA', 'SUPN', 'SYM', 'TLIT', 'VKTX', 'VIR', 'VOYG', 'JUNS', 'NUVL', 'WSBC', 'STX']

    found_alerts = 0
    print(f"Inizio scansione su {len(tickers)} titoli...")

    for t in tickers:
        try:
            stock = yf.Ticker(t)
            df = stock.history(period="60d")
            if df.empty or len(df) < 20: continue
            
            last = df.iloc[-1]
            vol_ma = df['Volume'].tail(20).mean()
            vol_ratio = round(float(last['Volume'] / vol_ma), 2)
            sma20 = df['Close'].rolling(window=20).mean().iloc[-1]
            
            # FILTRI: Prezzo > Media e Volume anomalo
            if last['Close'] > sma20 and vol_ratio > 1.2:
                # Recupero Data Earnings
                earn_date = "N/A"
                calendar = stock.calendar
                if calendar is not None and 'Earnings Date' in calendar:
                    next_earn = calendar['Earnings Date'][0]
                    earn_date = next_earn.strftime('%Y-%m-%d')
                    days_to_earn = (next_earn.replace(tzinfo=None) - datetime.now()).days
                    warn = "⚠️" if 0 <= days_to_earn <= 3 else "📅"
                else:
                    warn = "📅"

                found_alerts += 1
                price = round(float(last['Close']), 2)
                price_range = abs(last['High'] - last['Low']) / last['Close']
                iceberg_score = int(min((vol_ratio / (price_range * 50 + 0.01)) * 10, 100))
                
                ai_analysis = get_ai_analysis(t, price, vol_ratio, iceberg_score, earn_date)
                
                msg = (f"🧊 *ICEBERG ALERT*: ${t}\n"
                       f"💰 Prezzo: **${price}**\n"
                       f"📊 Vol Ratio: `{vol_ratio}x` | Score: `{iceberg_score}/100`\n"
                       f"{warn} Earnings: {earn_date}\n"
                       f"🤖 *AI:* {ai_analysis}")
                
                requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                              json={"chat_id": CHAT, "text": msg, "parse_mode": "Markdown"})
        except Exception as e:
            print(f"Errore su {t}: {e}")

    if found_alerts == 0:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                      json={"chat_id": CHAT, "text": "☕ *Scansione Completata*\nNessun segnale rilevato.", "parse_mode": "Markdown"})

if __name__ == "__main__":
    main()

import os
import yfinance as yf
import requests
import google.generativeai as genai
import pandas as pd
from datetime import datetime
import time

# Configurazione Segreti
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT = os.getenv("TELEGRAM_CHAT_ID")
API_KEY = os.getenv("GEMINI_API_KEY")

def get_dynamic_tickers():
    # Carica i leader del mercato (S&P 500 / NASDAQ)
    url = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/master/data/constituents.csv"
    try:
        df = pd.read_csv(url)
        return df['Symbol'].tolist()[:150]
    except:
        return ['AAPL', 'MSFT', 'NVDA', 'TSLA', 'PLTR', 'MSTR', 'ASML', 'AMD', 'NFLX', 'COIN', 'META', 'DE', 'STX']

def get_ai_analysis(ticker, price, vol_ratio, iceberg_score, earn_date):
    if not API_KEY: return "Analisi AI non disponibile."
    try:
        genai.configure(api_key=API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = (f"Analizza $ {ticker} a ${price}. Volume {vol_ratio}x. Iceberg Score: {iceberg_score}/100. "
                  f"Earnings: {earn_date}. Valuta se è accumulo istituzionale o rischio. Sii molto sintetico.")
        response = model.generate_content(prompt)
        return response.text
    except:
        return "Insight AI momentaneamente non disponibile."

def main():
    tickers = get_dynamic_tickers()
    found_alerts = 0
    print(f"Inizio scansione Iceberg su {len(tickers)} titoli...")

    for t in tickers:
        try:
            t = t.replace('.', '-') 
            stock = yf.Ticker(t)
            df = stock.history(period="30d")
            if df.empty or len(df) < 20: continue
            
            last = df.iloc[-1]
            vol_ma = df['Volume'].tail(20).mean()
            vol_ratio = round(float(last['Volume'] / vol_ma), 2)
            sma20 = df['Close'].rolling(window=20).mean().iloc[-1]
            
            # --- CALCOLO SCORE E FILTRO ---
            # Calcoliamo la volatilità intraday (Price Range)
            price_range = abs(last['High'] - last['Low']) / (last['Close'] + 0.001)
            # Score: più alto è il volume e più piccolo è il movimento, più alto è lo score
            iceberg_score = int(min((vol_ratio / (price_range * 50 + 0.01)) * 10, 100))

            # FILTRI: Prezzo sopra media + Volume anomalo + Score di Qualità > 60
            if last['Close'] > sma20 and vol_ratio > 1.2 and iceberg_score > 60:
                earn_date = "N/A"
                try:
                    cal = stock.calendar
                    if cal is not None and not cal.empty:
                        date_val = cal.iloc[0, 0] if isinstance(cal, pd.DataFrame) else cal.get('Earnings Date', ["N/A"])[0]
                        earn_date = date_val.strftime('%Y-%m-%d') if hasattr(date_val, 'strftime') else str(date_val)
                except:
                    earn_date = "Vedi Calendario"

                found_alerts += 1
                price = round(float(last['Close']), 2)
                ai_analysis = get_ai_analysis(t, price, vol_ratio, iceberg_score, earn_date)
                
                warn_emoji = "⚠️" if "N/A" not in earn_date else "📅"
                
                # MESSAGGIO CON FORMATTAZIONE RICHIESTA
                msg = (f"🧊 *ICEBERG ALERT (Dynamic)*: ${t}\n"
                       f"💰 Prezzo: **${price}**\n"
                       f"📊 Vol Ratio: `{vol_ratio}x` | Score: `{iceberg_score}/100`\n"
                       f"{warn_emoji} Earnings: {earn_date}\n"
                       f"🤖 *AI:* {ai_analysis}")
                
                requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                              json={"chat_id": CHAT, "text": msg, "parse_mode": "Markdown"})
                
                time.sleep(1.5) # Pausa per evitare spam
                
        except Exception as e:
            continue

    if found_alerts == 0:
        print("Scansione terminata: nessun segnale di qualità trovato.")

if __name__ == "__main__":
    main()

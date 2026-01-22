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
                  f"Earnings: {earn_date}. Valuta se è accumulo istituzionale sano o rischio. Sii brevissimo.")
        response = model.generate_content(prompt)
        return response.text
    except:
        return "Insight AI non disponibile."

def main():
    tickers = get_dynamic_tickers()
    candidates = []
    print(f"Inizio analisi competitiva su {len(tickers)} titoli...")

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
            
            # Calcolo Score Iceberg
            price_range = abs(last['High'] - last['Low']) / (last['Close'] + 0.001)
            iceberg_score = int(min((vol_ratio / (price_range * 50 + 0.01)) * 10, 100))

            # Filtro di ammissione: Trend + Volume + Score minimo
            if last['Close'] > sma20 and vol_ratio > 1.2 and iceberg_score > 50:
                candidates.append({
                    'ticker': t,
                    'price': round(float(last['Close']), 2),
                    'vol_ratio': vol_ratio,
                    'score': iceberg_score,
                    'stock': stock
                })
        except:
            continue

    # ORDINA PER PROBABILITÀ (Score più alto per primo)
    candidates = sorted(candidates, key=lambda x: x['score'], reverse=True)
    top_5 = candidates[:5]

    if not top_5:
        print("Nessun segnale ad alta probabilità trovato.")
        return

    for item in top_5:
        # Recupero data earnings
        earn_date = "N/A"
        try:
            cal = item['stock'].calendar
            if cal is not None and not cal.empty:
                date_val = cal.iloc[0, 0] if isinstance(cal, pd.DataFrame) else cal.get('Earnings Date', ["N/A"])[0]
                earn_date = date_val.strftime('%Y-%m-%d') if hasattr(date_val, 'strftime') else str(date_val)
        except:
            earn_date = "Controllare"

        ai_analysis = get_ai_analysis(item['ticker'], item['price'], item['vol_ratio'], item['score'], earn_date)
        
        # Titolo speciale per la classifica
        prob_emoji = "🔥" if item['score'] > 80 else "💎"
        
        msg = (f"{prob_emoji} *TOP ICEBERG PROBABILITY*: ${item['ticker']}\n"
               f"🎯 *Probabilità:* `{item['score']}/100` (Score)\n"
               f"📊 Vol Ratio: `{item['vol_ratio']}x` | Prezzo: **${item['price']}**\n"
               f"📅 Earnings: {earn_date}\n"
               f"🤖 *AI:* {ai_analysis}")
        
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                      json={"chat_id": CHAT, "text": msg, "parse_mode": "Markdown"})
        time.sleep(1.5)

if __name__ == "__main__":
    main()

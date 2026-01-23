import os
import requests
import pandas as pd
import yfinance as yf

# --- CONFIGURAZIONE ---
TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# [IMPORTANTE] Inserisci qui i ticker che compri effettivamente
watchlist_vendita = ["ABT"] 

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Errore invio Telegram: {e}")

def analyze_market():
    # LISTA 150 LEADER 2026 (Big Tech, Semiconductors, Solar, AI & Mid-Caps)
    tickers = [
        "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "AVGO", "LLY", "V",
        "MA", "ORCL", "COST", "NFLX", "AMD", "ADBE", "CRM", "QCOM", "INTC", "AMAT",
        "PLTR", "ISRG", "CAT", "AXP", "MS", "BKNG", "MU", "ETN", "LRCX", "BSX",
        "PANW", "GILD", "ADI", "ANET", "KLAC", "CRWD", "MAR", "ADSK", "HCA", "VRT",
        "APP", "MSTR", "HOOD", "COIN", "SOFI", "SHOP", "SNOW", "DDOG", "NET", "ZS",
        "TEAM", "MDB", "SQ", "AFRM", "PATH", "PINS", "ENPH", "RUN", "FSLR", "DKNG",
        "MELI", "SE", "BABA", "PYPL", "GME", "DELL", "HPE", "SMCI", "ARM", "ASML",
        "TSM", "ON", "STLA", "RACE", "TMO", "ABT", "DHR", "GEHC", "ALGN", "VLO",
        "MPC", "PSX", "IBM", "UBER", "SNPS", "CDNS", "WDAY", "ROP", "MCHP", "TEL",
        "APH", "STX", "WDC", "LULU", "CPRT", "T", "VZ", "BA", "RTX", "LMT",
        "GEV", "HON", "DE", "CAT", "LOW", "HD", "TJX", "PGR", "CB", "BLK",
        "JPM", "BAC", "WFC", "C", "GS", "SCHW", "ABBV", "JNJ", "PFE", "MRK",
        "UNH", "ELV", "CI", "COR", "SYK", "ZTS", "IDXX", "WMT", "TGT", "PG",
        "KO", "PEP", "PM", "MO", "XOM", "CVX", "SLB", "HAL", "OXY", "LIN"
    ]
    
    segnali_buy = []
    segnali_sell = []

    print(f"Analisi in corso su {len(tickers)} titoli...")

    for ticker in tickers:
        try:
            # Recupero dati (intervallo giornaliero dell'ultimo mese)
            data = yf.download(ticker, period="1mo", interval="1d", progress=False)
            if data.empty or len(data) < 20: continue

            # Rimuoviamo eventuali valori nulli
            data = data.dropna()
            
            current_price = data['Close'].iloc[-1]
            sma20 = data['Close'].rolling(window=20).mean().iloc[-1]
            avg_vol = data['Volume'].rolling(window=20).mean().iloc[-1]
            curr_vol = data['Volume'].iloc[-1]

            # 1. AZIONE: RILEVAMENTO ACQUISTO (ICEBERG)
            # Verifica se il prezzo è sopra la media 20 e se il volume è esploso (>50% della media)
            if current_price > sma20 and curr_vol > (avg_vol * 1.5):
                score = min(100, int((curr_vol / avg_vol) * 20))
                if score > 50:
                    segnali_buy.append(f"🔥 *ICEBERG DETECTED*: {ticker}\nPrezzo: ${current_price:.2f}\nScore: {score}/100\nStatus: Accumulo Istituzionale")

            # 2. AZIONE: PROTEZIONE VENDITA (EXIT STRATEGY)
            # Se hai il titolo in portafoglio e rompe la media a 20 giorni
            if ticker in watchlist_vendita:
                if current_price < sma20:
                    segnali_sell.append(f"⚠️ *SELL ALERT*: {ticker}\nPrezzo attuale: ${current_price:.2f}\nSegnale: Rottura SMA20 (Trend compromesso)")
        
        except Exception as e:
            print(f"Salto {ticker} per errore dati.")

    # INVIO MESSAGGI SU TELEGRAM
    if segnali_buy:
        send_telegram_message("🚀 **OPPORTUNITÀ DI INGRESSO** 🚀\n\n" + "\n\n".join(segnali_buy))
    
    if segnali_sell:
        send_telegram_message("📢 **ALERT CHIUSURA POSIZIONI** 📢\n\n" + "\n\n".join(segnali_sell))

if __name__ == "__main__":
    analyze_market()

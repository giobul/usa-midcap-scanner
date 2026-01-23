import os
import requests
import pandas as pd
import yfinance as yf

# --- 1. CONFIGURAZIONE CHIAVI ---
# Assicurati che su GitHub Secrets i nomi siano ESATTAMENTE questi
TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

def send_telegram_message(message):
    if not TOKEN or not CHAT_ID:
        print("ERRORE: Chiavi TOKEN o CHAT_ID mancanti nei Secrets di GitHub!")
        return
    
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        r = requests.post(url, json=payload)
        print(f"Invio a Telegram: {r.status_code} - {r.text}")
    except Exception as e:
        print(f"Errore di rete: {e}")

def analyze_market():
    # TEST: Se inserisci ABT e il bot funziona, DEVE arrivarti l'alert di vendita
    watchlist_vendita = ["ABT"] 

    # LISTA 150 LEADER 2026
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
        "GEV", "HON", "DE", "LOW", "HD", "TJX", "PGR", "CB", "BLK", "JPM",
        "BAC", "WFC", "C", "GS", "SCHW", "ABBV", "JNJ", "PFE", "MRK", "UNH",
        "ELV", "CI", "COR", "SYK", "ZTS", "IDXX", "WMT", "TGT", "PG", "KO",
        "PEP", "PM", "MO", "XOM", "CVX", "SLB", "HAL", "OXY", "LIN", "LYTS"
    ]
    
    segnali_buy = []
    segnali_sell = []

    print(f"Analisi avviata su {len(tickers)} titoli...")

    for ticker in tickers:
        try:
            data = yf.download(ticker, period="1mo", interval="1d", progress=False).dropna()
            if len(data) < 20: continue

            price = data['Close'].iloc[-1]
            sma20 = data['Close'].rolling(20).mean().iloc[-1]
            vol = data['Volume'].iloc[-1]
            avg_vol = data['Volume'].rolling(20).mean().iloc[-1]

            # AZIONE 1: Rilevamento BUY (Iceberg)
            if price > sma20 and vol > (avg_vol * 1.5):
                score = min(100, int((vol / avg_vol) * 20))
                if score > 50:
                    segnali_buy.append(f"🔥 *ICEBERG*: {ticker}\nPrezzo: ${price:.2f}\nScore: {score}/100")

            # AZIONE 2: Rilevamento SELL (Watchlist)
            if ticker in watchlist_vendita:
                if price < sma20:
                    segnali_sell.append(f"⚠️ *SELL*: {ticker}\nPrezzo: ${price:.2f} (Sotto SMA20)")

        except Exception as e:
            continue

    # --- INVIO REPORT ---
    if segnali_buy:
        send_telegram_message("🚀 **NUOVE OPPORTUNITÀ** 🚀\n\n" + "\n\n".join(segnali_buy))
    
    if segnali_sell:
        send_telegram_message("📢 **ALERT VENDITA** 📢\n\n" + "\n\n".join(segnali_sell))
    
    if not segnali_buy and not segnali_sell:
        send_telegram_message("✅ *Scansione completata*: Nessun segnale rilevante al momento.")

if __name__ == "__main__":
    # Messaggio iniziale per confermare che il bot è vivo
    print("Avvio script...")
    analyze_market()

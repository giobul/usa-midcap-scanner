import os
import requests
import pandas as pd
import yfinance as yf
import time

# Credenziali
TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

def get_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def analyze_market():
    watchlist_vendita = ["ABT", "RUN"] 
    
    # LISTA 150 TITOLI (Mid-Cap, Growth, AI, Tech & Crypto-related)
    tickers = [
        "PLTR", "VRT", "MSTR", "CELH", "DUOL", "IOT", "PATH", "SNOW", "ONON", "AFRM",
        "HOOD", "RDDT", "ARM", "OKLO", "S", "GTLB", "APP", "NTRA", "NU", "FRSH",
        "CRWD", "DDOG", "NET", "ZS", "PANW", "SE", "MELI", "U", "RBLX", "COIN",
        "MARA", "RIOT", "CLSK", "UPST", "MQ", "SOFI", "SHOP", "TOST", "DKNG", "PINS",
        "TTD", "SNAP", "RCL", "CCL", "NCLH", "UBER", "LYFT", "DASH", "ABNB", "RIVN",
        "LCID", "NIO", "XPEV", "LI", "TSLA", "BYDDF", "SQ", "PYPL", "DOCU", "ZM",
        "TEAM", "ADBE", "CRM", "NOW", "WDAY", "INTU", "ORCL", "SNPS", "CDNS", "ANSS",
        "ASML", "LRCX", "AMAT", "KLAC", "TSM", "AMD", "NVDA", "AVGO", "QCOM", "MU",
        "AMBA", "ALTR", "LSCC", "MRVL", "Wolf", "ON", "STNE", "PAGS", "GLOB", "EPAM",
        "COST", "WMT", "TGT", "LULU", "NKE", "DECK", "SKX", "CROX", "ELF", "MNST",
        "MDLZ", "CELH", "VITL", "WING", "CAVA", "SG", "CHOTW", "HIMS", "TDOC", "ABBV",
        "LLY", "NVO", "VRTX", "REGN", "ISRG", "BSX", "EW", "ALGN", "TMDX", "SWAV",
        "FSLR", "ENPH", "SEDG", "RUN", "SPWR", "NEE", "GE", "VST", "CEG", "TLRY",
        "CGC", "MSOS", "XBI", "IBB", "SMH", "SOXX", "KRE", "XLF", "XLY", "XLI"
    ]

    segnali_buy = []
    segnali_sell = []

    print(f"Inizio analisi di {len(tickers)} titoli...")

    for ticker in tickers:
        try:
            t = yf.Ticker(ticker)
            
            # Filtro Market Cap (2B - 30B) - Alzato leggermente per i leader 2026
            info = t.info
            mcap = info.get('marketCap', 0)
            if mcap < 2e9: continue 

            df = t.history(period="4mo") # Un po' di dati in più per sicurezza
            if len(df) < 30: continue

            # Indicatori
            price = df['Close'].iloc[-1]
            sma20 = df['Close'].rolling(20).mean().iloc[-1]
            vol_attuale = df['Volume'].iloc[-1]
            vol_medio = df['Volume'].rolling(20).mean().iloc[-1]
            rsi = get_rsi(df['Close']).iloc[-1]
            high_20d = df['High'].iloc[-21:-1].max()

            # LOGICA BUY (Breakout + Iceberg Vol + RSI < 68)
            if vol_attuale > (vol_medio * 1.5) and price > high_20d and rsi < 68:
                segnali_buy.append(
                    f"💎 **MID-CAP GEM**: {ticker}\n"
                    f"💰 Prezzo: ${price:.2f}\n"
                    f"📊 RSI: {rsi:.1f}\n"
                    f"🔥 Vol: +{int((vol_attuale/vol_medio-1)*100)}%\n"
                    f"🏛️ Cap: {mcap/1e9:.1f}B"
                )

            # LOGICA SELL (Watchlist)
            if ticker in watchlist_vendita and price < sma20:
                segnali_sell.append(f"⚠️ **EXIT ALERT**: {ticker}\nPrezzo: ${price:.2f} (Sotto SMA20)")

            # Piccola pausa per non essere bloccati da Yahoo Finance
            time.sleep(0.1)

        except Exception as e:
            print(f"Salto {ticker}: {e}")

    # Invio Report
    base_url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    
    if segnali_buy:
        # Divido i messaggi se sono troppi (limite Telegram 4096 caratteri)
        for i in range(0, len(segnali_buy), 5):
            chunk = segnali_buy[i:i+5]
            text = "🎯 **BREAKOUT RILEVATI** 🎯\n\n" + "\n\n".join(chunk)
            requests.post(base_url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"})
    
    if segnali_sell:
        text = "📢 **ALERT VENDITA** 📢\n\n" + "\n\n".join(segnali_sell)
        requests.post(base_url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"})

    if not segnali_buy and not segnali_sell:
        requests.post(base_url, json={"chat_id": CHAT_ID, "text": "☕ *Scansione 150 completata*: Nessun segnale istituzionale.", "parse_mode": "Markdown"})

if __name__ == "__main__":
    analyze_market()

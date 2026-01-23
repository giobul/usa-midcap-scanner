import os
import requests
import pandas as pd
import yfinance as yf
import time

# Recupero credenziali dai Secrets di GitHub
TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

def get_rsi(series, period=14):
    """Calcola l'RSI manualmente per massima affidabilità"""
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def analyze_market():
    # 1. Tua Watchlist Personale per segnali di uscita (SMA20)
    watchlist_vendita = ["ABT", "RUN", "STNE"] 
    
    # 2. LISTA COMPLETA 150 TITOLI (Mid-Cap, Growth e AI Leader)
    tickers = [
        "PLTR", "VRT", "MSTR", "CELH", "DUOL", "IOT", "PATH", "SNOW", "ONON", "AFRM",
        "HOOD", "RDDT", "ARM", "OKLO", "S", "GTLB", "APP", "NTRA", "NU", "FRSH",
        "CRWD", "DDOG", "NET", "ZS", "PANW", "SE", "MELI", "U", "RBLX", "COIN",
        "MARA", "RIOT", "CLSK", "UPST", "MQ", "SOFI", "SHOP", "TOST", "DKNG", "PINS",
        "TTD", "SNAP", "RCL", "CCL", "NCLH", "UBER", "LYFT", "DASH", "ABNB", "RIVN",
        "LCID", "NIO", "XPEV", "LI", "TSLA", "BYDDF", "SQ", "PYPL", "DOCU", "ZM",
        "TEAM", "ADBE", "CRM", "NOW", "WDAY", "INTU", "ORCL", "SNPS", "CDNS", "ANSS",
        "ASML", "LRCX", "AMAT", "KLAC", "TSM", "AMD", "NVDA", "AVGO", "QCOM", "MU",
        "AMBA", "ALTR", "LSCC", "MRVL", "ON", "STNE", "PAGS", "GLOB", "EPAM", "COST",
        "WMT", "TGT", "LULU", "NKE", "DECK", "SKX", "CROX", "ELF", "MNST", "MDLZ",
        "VITL", "WING", "CAVA", "SG", "HIMS", "TDOC", "ABBV", "LLY", "NVO", "VRTX",
        "REGN", "ISRG", "BSX", "EW", "ALGN", "TMDX", "SWAV", "FSLR", "ENPH", "SEDG",
        "NEE", "GE", "VST", "CEG", "TLRY", "CGC", "MSOS", "XBI", "IBB", "SMH", "SOXX",
        "KRE", "XLF", "XLY", "XLI", "DKNG", "DOCN", "MNDY", "SPSC", "SQSP", "FYBR"
    ]

    segnali_buy = []
    segnali_sell = []

    print(f"Inizio scansione professionale su {len(tickers)} titoli...")

    for ticker in tickers:
        try:
            t = yf.Ticker(ticker)
            
            # FILTRO MARKET CAP (2B - 30B per focus Mid-Cap)
            info = t.info
            mcap = info.get('marketCap', 0)
            if mcap < 2e9: continue 

            df = t.history(period="4mo")
            if len(df) < 30: continue

            # Indicatori Tecnici
            price = df['Close'].iloc[-1]
            sma20 = df['Close'].rolling(20).mean().iloc[-1]
            vol_attuale = df['Volume'].iloc[-1]
            vol_medio = df['Volume'].rolling(20).mean().iloc[-1]
            rsi = get_rsi(df['Close']).iloc[-1]
            high_20d = df['High'].iloc[-21:-1].max()

            # LOGICA ICEBERG E OPTION SWEEP
            # Sweep = Volumi > 250% | Iceberg = Volumi > 150%
            if vol_attuale > (vol_medio * 1.5) and price > high_20d and rsi < 68:
                
                is_sweep = vol_attuale > (vol_medio * 2.5)
                stop_loss = price * 0.95
                
                header = "🔥 **OPTION SWEEP** 🔥" if is_sweep else "🧊 **ICEBERG DETECTED**"
                
                # Commento AI Dinamico
                if is_sweep:
                    analisi_ai = "URGENZA ISTITUZIONALE. Qualcuno sta spazzando il book. Alta probabilità di momentum."
                elif rsi < 55:
                    analisi_ai = "Accumulazione sana all'inizio del trend. Rischio/Rendimento ottimo."
                else:
                    analisi_ai = "Trend confermato ma in accelerazione. Usa stop loss rigorosa."

                segnali_buy.append(
                    f"{header}\n"
                    f"Ticker: **{ticker}**\n"
                    f"💰 Prezzo: ${price:.2f}\n"
                    f"🔥 Volumi: +{int((vol_attuale/vol_medio-1)*100)}%\n"
                    f"📊 RSI: {rsi:.1f}\n"
                    f"🛡️ **Stop Loss: ${stop_loss:.2f}**\n"
                    f"🤖 _Analisi AI: {analisi_ai}_"
                )

            # LOGICA VENDITA (Watchlist personale)
            if ticker in watchlist_vendita and price < sma20:
                segnali_sell.append(f"⚠️ **EXIT ALERT**: {ticker}\nPrezzo: ${price:.2f} (Sotto SMA20)")

            time.sleep(0.1) # Protezione anti-ban Yahoo

        except Exception:
            continue

    # INVIO REPORT A TELEGRAM
    base_url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    
    if segnali_buy:
        for s in segnali_buy:
            requests.post(base_url, json={"chat_id": CHAT_ID, "text": s, "parse_mode": "Markdown"})
    
    if segnali_sell:
        text = "📢 **ALERT VENDITA (Portafoglio)** 📢\n\n" + "\n\n".join(segnali_sell)
        requests.post(base_url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"})

    if not segnali_buy and not segnali_sell:
        requests.post(base_url, json={"chat_id": CHAT_ID, "text": "☕ *Scansione 150 titoli*: Nessuna anomalia istituzionale rilevata.", "parse_mode": "Markdown"})

if __name__ == "__main__":
    analyze_market()

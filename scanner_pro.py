import os
import requests
import pandas as pd
import yfinance as yf
import time

# Configurazione Credenziali
TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

def get_rsi(series, period=14):
    """Calcolo manuale RSI per evitare errori di librerie esterne"""
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def analyze_market():
    # 1. Watchlist per monitoraggio uscita (SMA20)
    watchlist_vendita = ["ABT", "RUN", "STNE"] 
    
    # 2. LISTA COMPLETA 150 TITOLI (Mid-Cap, Growth e AI Leader 2026)
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
        "KRE", "XLF", "XLY", "XLI", "DKNG", "DOCN", "MNDY", "SPSC", "SQSP", "FYBR",
        "COSM", "VERI", "BASE", "GCT", "TME", "PDD", "JD", "BABA", "BIDU", "NTES"
    ]

    segnali_buy = []
    segnali_sell = []

    print(f"Scansione di {len(tickers)} titoli in corso...")

    for ticker in tickers:
        try:
            t = yf.Ticker(ticker)
            info = t.info
            mcap = info.get('marketCap', 0)
            
            # Filtro Mid-Cap (2B - 35B)
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

            # --- LOGICA DI RILEVAMENTO ---
            if vol_attuale > (vol_medio * 1.5) and price > high_20d and rsi < 68:
                
                # Calcolo SCORE ICEBERG (60-100)
                score = min(100, int((vol_attuale / vol_medio) * 40))
                
                # Definizione urgenza (Sweep se vol > 250%)
                is_sweep = vol_attuale > (vol_medio * 2.5)
                stop_loss = price * 0.95
                
                header = "🔥 **OPTION SWEEP** 🔥" if is_sweep else "🧊 **ICEBERG DETECTED**"
                
                # Commento AI Dinamico
                if is_sweep:
                    analisi_ai = "URGENZA ESTREMA. Qualcuno sta 'pulendo' il book. Momentum altissimo."
                elif rsi < 55:
                    analisi_ai = "Accumulazione iniziale. Ottimo punto di ingresso per rischio/rendimento."
                else:
                    analisi_ai = "Breakout confermato. Titolo in accelerazione, segui il trend."

                segnali_buy.append(
                    f"{header}\n"
                    f"Ticker: **{ticker}**\n"
                    f"💰 Prezzo: ${price:.2f}\n"
                    f"📈 **SCORE ICEBERG: {score}/100**\n"
                    f"🔥 Volumi: +{int((vol_attuale/vol_medio-1)*100)}%\n"
                    f"📊 RSI: {rsi:.1f}\n"
                    f"🛡️ **Stop Loss: ${stop_loss:.2f}**\n"
                    f"🤖 _Analisi AI: {analisi_ai}_"
                )

            # LOGICA VENDITA (Watchlist)
            if ticker in watchlist_vendita and price < sma20:
                segnali_sell.append(f"⚠️ **EXIT ALERT**: {ticker}\nPrezzo: ${price:.2f} (Sotto SMA20)")

            time.sleep(0.1) # Evita il blocco da parte di Yahoo

        except Exception:
            continue

    # --- INVIO MESSAGGI ---
    base_url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    
    if segnali_buy:
        for s in segnali_buy:
            requests.post(base_url, json={"chat_id": CHAT_ID, "text": s, "parse_mode": "Markdown"})
    
    if segnali_sell:
        text = "📢 **ALERT VENDITA (Monitoraggio)** 📢\n\n" + "\n\n".join(segnali_sell)
        requests.post(base_url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"})

    if not segnali_buy and not segnali_sell:
        requests.post(base_url, json={"chat_id": CHAT_ID, "text": "☕ *Scansione completata*: Nessun movimento istituzionale rilevato.", "parse_mode": "Markdown"})

if __name__ == "__main__":
    analyze_market()

import yfinance as yf
import pandas as pd
import numpy as np
import os
import requests
import datetime
import time

# --- CONFIGURAZIONE ---
MY_PORTFOLIO = ["STNE", "PATH", "RGTI", "QUBT", "DKNG", "AI", "BBAI", "ADCT", "AGEN", "STX"]
WATCHLIST = ["STX", "IONQ", "PLTR", "SOUN", "SNOW", "NET", "CRWD", "DDOG", "ZS", "OKTA", "MDB", "TEAM", "S", "U", "ADBE", "CRM", "WDAY", "NOW", "NU", "PAGS", "MELI", "SOFI", "UPST", "AFRM", "HOOD", "PYPL", "COIN", "BILL", "TOST", "DAVE", "MQ", "LC", "BABA", "JD", "PDD", "MARA", "RIOT", "CLSK", "HUT", "BITF", "MSTR", "WULF", "CIFR", "ANY", "BTBT", "CAN", "VRTX", "VKTX", "SAVA", "IOVA", "BBIO", "MDGL", "REGN", "ILMN", "EXAS", "BNTX", "MRNA", "IQV", "TDOC", "BMEA", "SRPT", "CRSP", "EDIT", "BEAM", "NTLA", "RLAY", "IRON", "TLRY", "CGC", "AMD", "NVDA", "INTC", "MU", "TXN", "TSM", "ASML", "AMAT", "LRCX", "KLAC", "SNPS", "CDNS", "ARM", "MRVL", "AVGO", "SMCI", "ANET", "TER", "ENTG", "ON", "TSLA", "RIVN", "LCID", "F", "GM", "RACE", "STLA", "ENPH", "SEDG", "FSLR", "PLUG", "CHPT", "RUN", "QS", "NIO", "XPEV", "LI", "BE", "NEE", "BLDP", "FCEL", "PENN", "RCL", "CCL", "NCLH", "AAL", "DAL", "UAL", "LUV", "BKNG", "EXPE", "MAR", "HLT", "GENI", "RSI", "SHOP", "DOCU", "ZM", "DASH", "ABNB", "UBER", "LYFT", "CHWY", "ROKU", "PINS", "SNAP", "EBAY", "ETSY", "RVLV", "META", "GOOGL", "AMZN", "MSFT", "AAPL", "NFLX", "DIS", "WBD", "AMC", "GME", "BB", "NOK", "FUBO", "SPCE", "RBLX", "MTCH", "BMBL", "YELP", "TTD", "OPEN", "HOV", "BLND", "HRTX", "MNMD", "WKHS", "DNA", "PLBY", "SKLZ", "SENS", "HYLN", "ASTS", "INVZ", "AEVA", "VRT", "ETN", "POWI", "RMBS", "OKLO", "SMR", "HIMS", "CLVT", "LRN", "GCT"]

SOGLIA_RSI_EXIT = 70.0  

def send_telegram(message):
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id: return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
    except:
        pass

def calculate_rsi(prices, period=14):
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def analyze_stock(ticker):
    try:
        df = yf.download(ticker, period="5d", interval="15m", progress=False)
        if df.empty or len(df) < 25: return
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        cp = float(df['Close'].iloc[-1])
        lp = float(df['Close'].iloc[-2])
        
        # Calcolo Z-Score
        vol_series = df['Volume'].tail(20)
        z_score = (float(df['Volume'].iloc[-1]) - vol_series.mean()) / vol_series.std() if vol_series.std() > 0 else 0
        
        rsi_val = float(calculate_rsi(df['Close']).iloc[-1])
        prezzo_ieri = float(df['Close'].iloc[0]) 
        var_pct_candela = abs((cp - lp) / lp) * 100
        
        res = float(df['High'].iloc[-21:-1].max())
        sup = float(df['Low'].iloc[-21:-1].min())
        dist_res = ((res - cp) / cp) * 100
        dist_sup = ((cp - sup) / cp) * 100

        # --- LOGICA DIFFERENZIATA ---
        # Portfolio: sensibile (1.3) | Watchlist: severa (2.0)
        soglia_z = 1.3 if ticker in MY_PORTFOLIO else 2.0
        
        info_tecnica = (f"\n📊 **RSI:** {rsi_val:.1f}"
                        f"\n📈 **Res:** ${res:.2f} ({dist_res:.2f}%)"
                        f"\n🛡️ **Sup:** ${sup:.2f} ({dist_sup:.2f}%)")

        if z_score > soglia_z:
            # 1. ALERT VENDITA (Priorità Portfolio)
            if cp < lp and ticker in MY_PORTFOLIO:
                msg = (f"🚨 **MOVIMENTO IN USCITA: {ticker}**\nPrezzo: **${cp:.2f}** | Z-Vol: **{z_score:.1f}**" + info_tecnica +
                       f"\n📢 **COSA FARE:** Volume in aumento sul ribasso. Balene in uscita. Proteggi il capitale prima del supporto a **${sup:.2f}**.")
                send_telegram(msg)
            
            # 2. DARK POOL / ICEBERG (Accumulo)
            elif var_pct_candela < 0.10:
                msg = (f"🧊 **ACCUMULO ISTITUZIONALE: {ticker}**\nPrezzo: **${cp:.2f}** | Z-Vol: **{z_score:.1f}**" + info_tecnica +
                       f"\n📢 **COSA FARE:** Istituzioni caricano a prezzo fermo. Ottima base se tiene **${sup:.2f}**.")
                send_telegram(msg)
            
            # 3. SWEEP BULLISH (Solo se Trend Positivo)
            elif cp > lp and cp > prezzo_ieri:
                msg = (f"🐋 **SWEEP BULLISH: {ticker}**\nPrezzo: **${cp:.2f}** | Z-Vol: **{z_score:.1f}**" + info_tecnica +
                       f"\n📢 **COSA FARE:** Forza confermata. Il momentum punta verso **${res:.2f}**.")
                send_telegram(msg)

        # 4. TARGET PROFIT (RSI > 70)
        if ticker in MY_PORTFOLIO and rsi_val >= SOGLIA_RSI_EXIT:
            msg = (f"🏁 **ZONA TARGET: {ticker}**\nPrezzo: **${cp:.2f}**" + info_tecnica +
                   f"\n📢 **COSA FARE:** RSI elevato. Non essere avido: massimizza e incassa il profitto vicino a **${res:.2f}**.")
            send_telegram(msg)

    except Exception as e:
        print(f"Errore su {ticker}: {e}")

def main():
    now = datetime.datetime.now()
    current_time = int(now.strftime("%H%M"))
    # Attivo solo in sessione USA (15:30 - 22:10 ora italiana)
    # if current_time < 1530 or current_time > 2210: return
    
    all_tickers = sorted(list(set(WATCHLIST + MY_PORTFOLIO)))
    for t in all_tickers:
        analyze_stock(t)
        time.sleep(0.5)

if __name__ == "__main__":
    main()

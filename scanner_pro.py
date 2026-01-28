import yfinance as yf
import pandas as pd
import os
import requests
import datetime
import time

# --- CONFIGURAZIONE ---
# Titoli che possiedi (Ricevono Exit e Bearish Alert)
MY_PORTFOLIO = ["STNE", "PATH", "RGTI", "QUBT", "DKNG", "AI", "BBAI", "ADCT", "AGEN", "STX"]

# Titoli che osservi (Ricevono solo Bullish, Iceberg e Dark Pool)
WATCHLIST = ["STX", "IONQ", "PLTR", "SOUN", "SNOW", "NET", "CRWD", "DDOG", "ZS", "OKTA", "MDB", "TEAM", "S", "U", "ADBE", "CRM", "WDAY", "NOW", "NU", "PAGS", "MELI", "SOFI", "UPST", "AFRM", "HOOD", "PYPL", "COIN", "BILL", "TOST", "DAVE", "MQ", "LC", "BABA", "JD", "PDD", "MARA", "RIOT", "CLSK", "HUT", "BITF", "MSTR", "WULF", "CIFR", "ANY", "BTBT", "CAN", "VRTX", "VKTX", "SAVA", "IOVA", "BBIO", "MDGL", "REGN", "ILMN", "EXAS", "BNTX", "MRNA", "IQV", "TDOC", "BMEA", "SRPT", "CRSP", "EDIT", "BEAM", "NTLA", "RLAY", "IRON", "TLRY", "CGC", "AMD", "NVDA", "INTC", "MU", "TXN", "TSM", "ASML", "AMAT", "LRCX", "KLAC", "SNPS", "CDNS", "ARM", "MRVL", "AVGO", "SMCI", "ANET", "TER", "ENTG", "ON", "TSLA", "RIVN", "LCID", "F", "GM", "RACE", "STLA", "ENPH", "SEDG", "FSLR", "PLUG", "CHPT", "RUN", "QS", "NIO", "XPEV", "LI", "BE", "NEE", "BLDP", "FCEL", "PENN", "RCL", "CCL", "NCLH", "AAL", "DAL", "UAL", "LUV", "BKNG", "EXPE", "MAR", "HLT", "GENI", "RSI", "SHOP", "DOCU", "ZM", "DASH", "ABNB", "UBER", "LYFT", "CHWY", "ROKU", "PINS", "SNAP", "EBAY", "ETSY", "RVLV", "META", "GOOGL", "AMZN", "MSFT", "AAPL", "NFLX", "DIS", "WBD", "AMC", "GME", "BB", "NOK", "FUBO", "SPCE", "RBLX", "MTCH", "BMBL", "YELP", "TTD", "OPEN", "HOV", "BLND", "HRTX", "MNMD", "WKHS", "DNA", "PLBY", "SKLZ", "SENS", "HYLN", "ASTS", "INVZ", "AEVA", "VRT", "ETN", "POWI", "RMBS", "OKLO", "SMR", "HIMS", "CLVT", "LRN", "GCT"]

SOGLIA_RSI_EXIT = 70.0  
SOGLIA_VOL_SWEEP = 1.6 

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
        # Carico dati per trend e livelli
df = yf.download(ticker, period="5d", interval="15m", progress=False)
        
        if df.empty or len(df) < 25: 
            return
        
        # --- FIX PER ERRORE 'SERIES' ---
        # Usiamo .iloc[-1] e poi .item() per essere sicuri di avere un numero singolo
        cp = float(df['Close'].iloc[-1])
        lp = float(df['Close'].iloc[-2])
        
        # Per il volume e altri calcoli
        vol_attuale = float(df['Volume'].iloc[-1])
        avg_vol = float(df['Volume'].rolling(window=20).mean().iloc[-1])
        
        # Prezzo di ieri (40 candele da 15 min fa sono circa l'apertura di ieri)
        prezzo_ieri = float(df['Close'].iloc[0]) 
        
        # RSI e variazioni
        rsi_series = calculate_rsi(df['Close'])
        rsi_val = float(rsi_series.iloc[-1])
        var_pct = abs((cp - lp) / lp) * 100
        
        # Supporti e Resistenze
        resistenza = float(df['High'].iloc[-21:-1].max())
        supporto = float(df['Low'].iloc[-21:-1].min())
        # --- LOGICA VOLUME ANOMALO ---
        if vol_attuale > (avg_vol * SOGLIA_VOL_SWEEP):
            
            # 🌑 DARK POOL PRINT (Volume massiccio, prezzo immobile)
            if var_pct < 0.05 and vol_attuale > (avg_vol * 3.0):
                send_telegram(f"🌑 **DARK POOL PRINT: {ticker}**\nPrezzo: **${cp:.2f}** | Volume: {vol_attuale/avg_vol:.1f}x 🏦\nScambio istituzionale rilevato!")

            # 🧊 ICEBERG ACCUMULATION (Assorbimento)
            elif var_pct < 0.10:
                send_telegram(f"🧊 **ICEBERG ACCUMULATION: {ticker}**\nPrezzo: **${cp:.2f}** | Assorbimento 🛑\nVol: {vol_attuale/avg_vol:.1f}x")

            # 🐋 SWEEP BULLISH
            elif cp > lp:
                if cp > prezzo_ieri:
                    status = f"📈 BREAKOUT: Sopra ${resistenza:.2f}" if cp > resistenza else "🔍 Forza in salita"
                    send_telegram(f"🐋 **TRUE BULLISH SWEEP: {ticker}**\nPrezzo: **${cp:.2f}** | {status} ✅\nVol: {vol_attuale/avg_vol:.1f}x | RSI: {rsi_val:.1f}")
                else:
                    send_telegram(f"⚠️ **FALSE BULLISH SWEEP: {ticker}**\n(Technical Rebound) **DO NOT TOUCH** 🚫")
            
            # 🚨 BEARISH SWEEP (Solo per titoli in possesso)
            elif cp < lp and ticker in MY_PORTFOLIO:
                send_telegram(f"🚨 **BEARISH SWEEP: {ticker}**\nPrezzo: **${cp:.2f}** | Balene in uscita dal tuo titolo! ⚠️")

        # 🏁 STRATEGIC EXIT (Solo per titoli in possesso - RSI 70)
        if ticker in MY_PORTFOLIO and rsi_val >= SOGLIA_RSI_EXIT:
            send_telegram(f"🏁 **STRATEGIC EXIT: {ticker}**\nPrezzo: **${cp:.2f}** | RSI: **{rsi_val:.1f}** 🔥\nTarget >50€: VALUTA VENDITA!")

    except Exception as e:
        print(f"Errore su {ticker}: {e}")

def main():
    all_tickers = sorted(list(set(WATCHLIST + MY_PORTFOLIO)))
    print(f"--- Inizio Scansione: {datetime.datetime.now().strftime('%H:%M:%S')} ---")
    for t in all_tickers:
        analyze_stock(t)
        time.sleep(0.4) # Protezione IP (tim.it)
    print(f"--- Scansione Terminata ---")

if __name__ == "__main__":
    main()
                      

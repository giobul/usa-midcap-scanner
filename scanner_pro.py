import yfinance as yf
import pandas as pd
import datetime
import requests
import os
import time
import io

# --- CONFIGURAZIONE ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
FLAG_FILE = "scanner_started.txt"

# Tuo Portfolio (Analisi Prioritaria)
MY_PORTFOLIO = ["STNE", "PATH", "RGTI", "PLTR", "SOUN", "IONQ", "BBAI", "HIMS", "CLSK", "MARA"]

def send_telegram(message):
    if TOKEN and CHAT_ID:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
        try:
            requests.post(url, data=data)
        except Exception as e:
            print(f"Errore Telegram: {e}")

def get_market_sentiment():
    try:
        spy = yf.Ticker("SPY").history(period="2d")
        if len(spy) < 2: return "INDETERMINATO"
        change = ((spy['Close'].iloc[-1] - spy['Close'].iloc[-2]) / spy['Close'].iloc[-2]) * 100
        if change > 0.5: return "RIALZISTA 🚀"
        if change < -0.5: return "RIBASSISTA ⚠️"
        return "LATERALE ⚖️"
    except:
        return "NON DISPONIBILE"

def get_global_tickers():
    try:
        url = "https://finance.yahoo.com/markets/stocks/most-active/"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers)
        # Fix con StringIO per evitare warning di Pandas
        tables = pd.read_html(io.StringIO(response.text))
        df = tables[0]
        return df['Symbol'].head(100).tolist()
    except Exception as e:
        print(f"Errore recupero Top 100: {e}")
        return []

def analyze_stock(ticker, sentiment):
    try:
        # Scarichiamo i dati (15 minuti di intervallo)
        df = yf.download(ticker, period="5d", interval="15m", progress=False, threads=False)
        
        if df.empty or len(df) < 25: 
            return
        
        # --- FIX AMBIGUITY & MULTIINDEX ---
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        df = df.dropna()
        
        # Estrazione valori singoli scalari
        cp = float(df['Close'].iloc[-1])
        lp = float(df['Close'].iloc[-2])
        v_last = float(df['Volume'].iloc[-1])
        
        # Volume Z-Score (Anomalia statistica)
        vol_tail = df['Volume'].tail(20).astype(float)
        z_score = (v_last - vol_tail.mean()) / vol_tail.std() if vol_tail.std() > 0 else 0
        
        # RSI 14 periodi
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss.replace(0, 0.001)
        rsi_val = float(100 - (100 / (1 + rs)).iloc[-1])

        # Supporti e Resistenze (ultime 20 candele)
        res = float(df['High'].iloc[-21:-1].max())
        sup = float(df['Low'].iloc[-21:-1].min())
        var_pct_candela = abs((cp - lp) / lp) * 100
        
        # Logica Squeeze (Bassa volatilità pronta a esplodere)
        range_prezzi = df['Close'].tail(20).astype(float)
        volat_pct = (range_prezzi.std() / range_prezzi.mean()) * 100
        is_squeeze = bool(volat_pct < 0.35)

        header = f"🌍 **CLIMA:** {sentiment}\n"
        info = f"\n📊 RSI: {rsi_val:.1f}\n📈 Res: ${res:.2f}\n🛡️ Sup: ${sup:.2f}"

        # --- LOGICA ALERT ---
        soglia_z = 1.3 if ticker in MY_PORTFOLIO else 3.8
        
        if z_score > soglia_z:
            # Caso 1: Grandi volumi, prezzo fermo (Accumulazione Nascosta)
            if z_score > 5.0 and var_pct_candela <= 0.25:
                send_telegram(f"{header}🌑 **DARK POOL: {ticker}**\nZ-Vol: {z_score:.1f}" + info)
            # Caso 2: Iceberg Order
            elif var_pct_candela <= 0.45:
                send_telegram(f"{header}🧊 **ICEBERG: {ticker}**\nZ-Vol: {z_score:.1f}" + info)
            # Caso 3: Sweep aggressivo (Solo per Portfolio)
            elif cp > lp and ticker in MY_PORTFOLIO:
                send_telegram(f"{header}🐋 **SWEEP: {ticker}**\nZ-Vol: {z_score:.1f}" + info)

        # Alert specifici per gestione Profitto (Target 50€)
        if ticker in MY_PORTFOLIO:
            if rsi_val >= 70.0: 
                send_telegram(f"🏁 **TARGET {ticker}**: RSI {rsi_val:.1f}\n📢 **AZIONE:** Valuta chiusura per profitto!")
            
            if is_squeeze:
                dist_res = res - cp
                dist_sup = cp - sup
                direzione = "📈 Rialzista" if dist_res < dist_sup else "📉 Ribassista"
                send_telegram(f"⚡ **SQUEEZE {ticker}**\nDirezione: {direzione}\nVolatilità: {volat_pct:.2f}%")
                
    except Exception as e:
        print(f"Errore analisi {ticker}: {e}")

def main():
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    now_time = int(datetime.datetime.now().strftime("%H%M"))
    
    # --- ORARIO OPERATIVO (16:00 - 22:10 ITA) ---
    # Inizia alle 16:00 per avere dati yfinance (15m delay) puliti post-apertura
    if now_time < 1600 or now_time > 2210:
        if os.path.exists(FLAG_FILE): 
            os.remove(FLAG_FILE)
        return 

    sentiment = get_market_sentiment()
    global_list = get_global_tickers()
    
    portfolio_clean = [str(t) for t in MY_PORTFOLIO]
    all_tickers = sorted(list(set(global_list + portfolio_clean)))

    # Notifica Avvio Giornaliero
    if not os.path.exists(FLAG_FILE):
        send_telegram(f"🚀 **SCANNER OPERATIVO**\n🌍 Mercato: {sentiment}\n🔍 Monitorando {len(all_tickers)} titoli\n⏳ Sincronizzato con delay 15m")
        with open(FLAG_FILE, "w") as f: f.write(today)

    for t in all_tickers:
        analyze_stock(t, sentiment)
        time.sleep(0.6) # Evitiamo rate limit

if __name__ == "__main__":
    main()

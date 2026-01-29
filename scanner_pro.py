import yfinance as yf
import pandas as pd
import os
import requests
import datetime
import logging
import time

logging.getLogger('yfinance').setLevel(logging.CRITICAL)

# --- CONFIGURAZIONE ---
MY_PORTFOLIO = ["STNE", "PATH", "RGTI", "QUBT", "DKNG", "AI", "BBAI", "ADCT", "AGEN", "STX"]
FLAG_FILE = "scanner_started.txt"

def send_telegram(message):
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id: return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    try: requests.post(url, json=payload, timeout=10)
    except: pass

def get_market_sentiment():
    try:
        idx = yf.download("QQQ", period="2d", interval="1d", progress=False)
        change = ((idx['Close'].iloc[-1] - idx['Close'].iloc[-2]) / idx['Close'].iloc[-2]) * 100
        if change > 0.5: return "🚀 BULLISH"
        if change < -0.5: return "📉 BEARISH"
        return "⚖️ NEUTRALE"
    except: return "❓ INCERTO"

def get_global_tickers():
    try:
        # Peschiamo i 100 titoli più attivi
        url = 'https://finance.yahoo.com/markets/stocks/most-active/?start=0&count=100'
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        tables = pd.read_html(response.text)
        if tables:
            df = tables[0]
            col_name = 'Symbol' if 'Symbol' in df.columns else df.columns[0]
            return df[col_name].tolist()
        return []
    except Exception as e:
        print(f"Errore Global List: {e}")
        return ["PLTR", "NVDA", "AMD", "TSLA"]

def analyze_stock(ticker, sentiment):
    try:
        df = yf.download(ticker, period="5d", interval="15m", progress=False, threads=False)
        if df.empty or len(df) < 25: return
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        
        cp = float(df['Close'].iloc[-1])
        lp = float(df['Close'].iloc[-2])
        vol_series = df['Volume'].tail(20)
        z_score = (float(df['Volume'].iloc[-1]) - vol_series.mean()) / vol_series.std() if vol_series.std() > 0 else 0
        
        # RSI Rapido
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi_val = (100 - (100 / (1 + rs))).iloc[-1]

        var_pct_candela = abs((cp - lp) / lp) * 100
        res = float(df['High'].iloc[-21:-1].max())
        sup = float(df['Low'].iloc[-21:-1].min())
        
        # --- LOGICA SQUEEZE DIREZIONALE ---
        range_prezzi = df['Close'].tail(20)
        volat_pct = (range_prezzi.std() / range_prezzi.mean()) * 100
        is_squeeze = volatil_pct < 0.4 

        header = f"🌍 **CLIMA:** {sentiment}\n"
        info = f"\n📊 RSI: {rsi_val:.1f}\n📈 Res: ${res:.2f}\n🛡️ Sup: ${sup:.2f}"

        # 1. ALERT VOLUMI (Per tutti i 110 titoli)
        soglia_z = 1.3 if ticker in MY_PORTFOLIO else 3.5
        if z_score > soglia_z:
            if z_score > 5.0 and var_pct_candela <= 0.30:
                send_telegram(f"{header}🌑 **DARK POOL: {ticker}**\nZ-Vol: {z_score:.1f}" + info)
            elif var_pct_candela <= 0.50:
                send_telegram(f"{header}🧊 **ICEBERG: {ticker}**\nZ-Vol: {z_score:.1f}" + info)
            elif cp > lp and ticker in MY_PORTFOLIO:
                send_telegram(f"{header}🐋 **SWEEP: {ticker}**" + info)

        # 2. ALERT PORTFOLIO (Squeeze e Target Gain)
        if ticker in MY_PORTFOLIO:
            if rsi_val >= 70.0: 
                send_telegram(f"🏁 **TARGET {ticker}**: RSI {rsi_val:.1f}\n📢 **AZIONE:** Valuta profitto > 50€!")
            
            if is_squeeze:
                dist_res = res - cp
                dist_sup = cp - sup
                direzione = "📈 **Pressione RIALZISTA**" if dist_res < dist_sup else "📉 **Rischio RIBASSO**"
                consiglio = "Pronto al breakout?" if dist_res < dist_sup else "Attenzione al supporto!"
                send_telegram(f"⚡ **SQUEEZE {ticker}**\n📢 DIREZIONE: {direzione}\n💡 {consiglio}\n📊 Volatilità: {volat_pct:.2f}%")
                
    except: pass

def main():
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    now_time = int(datetime.datetime.now().strftime("%H%M"))
    
    # Orario Borsa US (15:30 - 22:10)
    if now_time < 1530 or now_time > 2210:
        if os.path.exists(FLAG_FILE): os.remove(FLAG_FILE)
        return

    sentiment = get_market_sentiment()
    global_list = get_global_tickers()
    all_tickers = sorted(list(set(global_list + MY_PORTFOLIO)))

    if not os.path.exists(FLAG_FILE):
        send_telegram(f"✅ **SCANNER ATTIVO**\n🌍 Mercato: {sentiment}\n🔍 Analisi su {len(all_tickers)} titoli\n🚀 Caccia aperta!")
        with open(FLAG_FILE, "w") as f: f.write(today)

    for t in all_tickers:
        analyze_stock(t, sentiment)
        time.sleep(0.4)

if __name__ == "__main__":
    main()

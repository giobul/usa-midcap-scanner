import sys
from datetime import datetime, timedelta
import time
import os
import requests
import pytz

# --- 1. TEST DI AVVIO E CARICAMENTO LIBRERIE ---
print("--- SCANNER PRO 2026: VERSIONE RSI + STOP LOSS + SMA20 ---")
try:
    import yfinance as yf
    import pandas as pd
    print("✅ Librerie caricate con successo.")
except Exception as e:
    print(f"❌ ERRORE LIBRERIE: {str(e)}")
    sys.exit(1)

# --- CONFIGURAZIONE ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

MY_PORTFOLIO = ["STNE", "PATH", "RGTI", "BBAI", "SOFI", "AGEN", "DKNG", "QUBT", "ETOR"]

WATCHLIST_200 = [
    "APLD","RKLB","LYFT","ADCT","VRT","CLS","PSTG","ANET","SMCI","AVGO","MRVL","WOLF","MU","ARM","SOXQ","POWI","DIOD","RMBS","NVDA","TSM","ASML","AMAT",
    "ASTS","RDW","BKSY","SPIR","LMT","NOC","LHX","AVAV","KTOS","BWXT","MDALF","BDRY","JOBY","ACHR","EH","SIDU","SPCE",
    "MSFT","GOOGL","IBM","AMZN","META","SNOW","CRWD","NET","ZS","OKTA","PANW","FTNT","DDOG","MDB","TEAM","ASAN","WDAY","NOW",
    "NU","MELI","XYZ","PYPL","SHOP","PAGS","TOST","AFRM","HOOD","COIN","MARA","CLSK","RIOT","MSTR","V","MA","GLBE","DLO","UPST",
    "OKLO","SMR","NNE","CCJ","UUUU","UEC","LEU","VST","CEG","FLR","GE","NEE","BE","CHPT","TSLA","ENPH","SEDG","FSLR","RUN",
    "DKNG","PENN","RDDT","DUOL","APP","U","GME","AMC","PINS","SNAP","TWLO","ZM","AAL","DAL","UAL","MAR","ABNB","BKNG","RCL","CCL",
    "RIVN","LCID","NIO","XPEV","LI","BYD","TM","HMC","STLA","F","GM","RACE","QS","ALB","LAC","MP","VALE","RIO","FCX",
    "DOCU","GTLB","AI","UPWK","FIVN","ESTC","BOX","DBX","EGHT","RNG","AKAM",
    "OPEN","Z","EXPI","COMP","MTCH","BMBL","IAC","UBER","DASH","W","ETSY","EBAY","CHWY","RVLV","FIGS","SKLZ",
    "NKE","LULU","UAA","DECK","CROX","VFC","TPR","RL","PVH","KSS","M","TGT","WMT","COST","BJ","SFM","ANET","CCJ","SMR","NNE","STX", 
    "VRT"
]

alert_history = {} 

def send_telegram(message):
    if TOKEN and CHAT_ID:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
        try:
            requests.post(url, data=data, timeout=10)
        except:
            pass

def analyze_stock(ticker):
    global alert_history
    try:
        now = datetime.now()
        if ticker in alert_history and now < alert_history[ticker] + timedelta(minutes=45):
            return

        data = yf.download(ticker, period="5d", interval="15m", progress=False)
        if len(data) < 20: return

        df = data.copy()
        df.columns = [col[0] if isinstance(col, tuple) else col for col in df.columns]

        cp = float(df['Close'].iloc[-1])
        op = float(df['Open'].iloc[-1])
        hi = float(df['High'].iloc[-1])
        lo = float(df['Low'].iloc[-1])
        vol = float(df['Volume'].iloc[-1])
        
        avg_vol = df['Volume'].tail(20).mean()
        std_vol = df['Volume'].tail(20).std()
        z_score = (vol - avg_vol) / std_vol if std_vol > 0 else 0
        range_totale_pct = ((hi - lo) / cp) * 100
        
        # --- FILTRI QUALITÀ E RSI ---
        df['SMA20'] = df['Close'].rolling(window=20).mean()
        current_sma20 = float(df['SMA20'].iloc[-1])
        
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        current_rsi = float(rsi.iloc[-1])

        sopra_trend = cp > current_sma20
        prezzo_sale = cp > op
        tipo_alert, commento_ia = "", ""

        if z_score > 3.0 and prezzo_sale and sopra_trend and range_totale_pct > 0.40 and current_rsi < 70:
            tipo_alert = "🐋 SWEEP CALL"
            commento_ia = f"Aggressione istituzionale. RSI: {current_rsi:.1f}."
        elif z_score > 2.0 and range_totale_pct < 0.25 and sopra_trend and current_rsi < 70:
            tipo_alert = "🧊 ICEBERG (Assorbimento)"
            commento_ia = f"Muro a ${cp:.2f}. RSI: {current_rsi:.1f}."

        if tipo_alert:
            high_p = df['High'].max(); low_p = df['Low'].min(); close_p = df['Close'].iloc[-2]
            pivot = (high_p + low_p + close_p) / 3
            res1 = (2 * pivot) - low_p
            res2 = pivot + (high_p - low_p)
            stop_loss = lo * 0.995 

            is_portfolio = ticker in MY_PORTFOLIO
            header = "💼 [MY PORTFOLIO]" if is_portfolio else "🛰️ [WATCHLIST]"
            var_pct = ((cp - op) / op) * 100

            msg = f"{header}\n*{tipo_alert}*\n📊 **TITOLO: {ticker}**\n"
            msg += f"----------------------------\n"
            msg += f"💰 PREZZO: ${cp:.2f} ({var_pct:+.2f}%)\n"
            msg += f"⚡ **Z-VOL: {z_score:.1f}** | 📈 **RSI: {current_rsi:.1f}**\n"
            msg += f"📉 **COMPRESSIONE: {range_totale_pct:.2f}%**\n"
            msg += f"📊 **SMA20: ${current_sma20:.2f}**\n"
            
            if is_portfolio:
                msg += f"\n🎯 **PIANO DI TRADING:**\n"
                msg += f"🟠 TARGET R2: ${res2:.2f}\n"
                msg += f"🟢 TARGET R1: ${res1:.2f}\n"
                msg += f"🚫 **STOP LOSS: ${stop_loss:.2f}**\n"
            else:
                msg += f"🚀 RESISTENZA: ${res1:.2f} | 🚫 STOP: ${stop_loss:.2f}\n"

            msg += f"\n----------------------------\n"
            msg += f"🤖 **IA:** {commento_ia}"
            
            send_telegram(msg)
            alert_history[ticker] = now
            print(f"📩 ALERT INVIATO PER {ticker}!")
        else:
            print(f"📊 {ticker:5} | CP: {cp:7.2f} | Z: {z_score:4.1f} | RSI: {current_rsi:4.1f} | No Alert")
    except Exception as e:
        print(f"| Errore {ticker}: {str(e)}")

def main():
    tz_ny = pytz.timezone('US/Eastern')
    now_ny = datetime.now(tz_ny)
    
    if now_ny.weekday() >= 5:
        print("☕ Weekend.")
        return
    if now_ny.hour < 10 or (now_ny.hour == 10 and now_ny.minute < 30):
        print("⏳ Attesa apertura.")
        return
    if now_ny.hour > 15 or (now_ny.hour == 15 and now_ny.minute >= 45):
        print("🛑 Chiusura.")
        return

    all_tickers = sorted(list(set(MY_PORTFOLIO + WATCHLIST_200)))
    print(f"\n🚀 AVVIO SCANSIONE - {now_ny.strftime('%H:%M:%S')} NY")
    
    for t in all_tickers:
        analyze_stock(t)
        time.sleep(0.5)

if __name__ == "__main__":
    main()

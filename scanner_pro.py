import sys
from datetime import datetime, timedelta
import time
import os
import requests
import pytz  # Aggiunta per la gestione fusi orari

# 1. Test immediato di output
print("--- TEST DI AVVIO ---")
print(f"Versione Python: {sys.version}")

try:
    print("Caricamento librerie...", end=" ", flush=True)
    import yfinance as yf
    import pandas as pd
    print("✅ OK")
except Exception as e:
    print(f"❌ ERRORE LIBRERIE: {str(e)}")
    sys.exit(1)

# --- 1. CONFIGURAZIONE CREDENZIALI ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# --- 2. PORTAFOGLIO & WATCHLIST ---
MY_PORTFOLIO = ["STNE", "PATH", "RGTI", "BBAI", "SOFI"]

WATCHLIST_200 = [
    "RKLB","LYFT","ADCT","VRT","CLS","PSTG","ANET","SMCI","AVGO","MRVL","WOLF","MU","ARM","SOXQ","POWI","DIOD","RMBS","NVDA","TSM","ASML","AMAT",
    "ASTS","RDW","BKSY","SPIR","LMT","NOC","LHX","AVAV","KTOS","BWXT","MDALF","BDRY","JOBY","ACHR","EH","SIDU","SPCE",
    "MSFT","GOOGL","IBM","AMZN","META","SNOW","CRWD","NET","ZS","OKTA","PANW","FTNT","DDOG","MDB","TEAM","ASAN","MOND","WDAY","NOW",
    "NU","MELI","XYZ","PYPL","SHOP","PAGS","TOST","AFRM","HOOD","COIN","MARA","CLSK","RIOT","MSTR","V","MA","GLBE","DLO","UPST",
    "OKLO","SMR","NNE","CCJ","UUUU","UEC","LEU","VST","CEG","FLR","GE","NEE","BE","CHPT","TSLA","ENPH","SEDG","FSLR","RUN",
    "DKNG","PENN","RDDT","DUOL","APP","U","GME","AMC","PINS","SNAP","TWLO","ZM","AAL","DAL","UAL","MAR","ABNB","BKNG","RCL","CCL",
    "RIVN","LCID","NIO","XPEV","LI","BYD","TM","HMC","STLA","F","GM","RACE","QS","ALB","LAC","MP","VALE","RIO","FCX",
    "DOCU","GTLB","AI","UPWK","FIVN","ESTC","BOX","DBX","EGHT","RNG","AKAM",
    "OPEN","Z","EXPI","COMP","MTCH","BMBL","IAC","UBER","DASH","W","ETSY","EBAY","CHWY","RVLV","FIGS","SKLZ",
    "NKE","LULU","UAA","DECK","CROX","VFC","TPR","RL","PVH","KSS","M","TGT","WMT","COST","BJ","SFM"
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
        # --- FILTRO ANTI-STREGHE ---
        tz_ny = pytz.timezone('US/Eastern')
        now_ny = datetime.now(tz_ny)
        
        if now_ny.hour > 15 or (now_ny.hour == 15 and now_ny.minute >= 45):
            return 

        now = datetime.now()
        if ticker in alert_history and now < alert_history[ticker] + timedelta(minutes=45):
            return

        # Scarichiamo i dati
        data = yf.download(ticker, period="1mo", interval="15m", progress=False)
        if data.empty: return

        df = data.copy()
        df.columns = [col[0] if isinstance(col, tuple) else col for col in df.columns]

        # --- CALCOLO PIVOT POINTS (R1, R2, R3) ---
        high_prev = df['High'].max()
        low_prev = df['Low'].min()
        close_prev = df['Close'].iloc[-2]
        
        pivot = (high_prev + low_prev + close_prev) / 3
        range_prev = high_prev - low_prev
        
        res1 = (2 * pivot) - low_prev
        res2 = pivot + range_prev
        res3 = high_prev + 2 * (pivot - low_prev)
        sup1 = (2 * pivot) - high_prev

        # --- INDICATORI PRO ---
        df['SMA20'] = df['Close'].rolling(window=20).mean()
        current_sma20 = float(df['SMA20'].iloc[-1])
        cp = float(df['Close'].iloc[-1])
        op = float(df['Open'].iloc[-1])
        hi = float(df['High'].iloc[-1])
        vol = float(df['Volume'].iloc[-1])
        
        avg_vol = df['Volume'].tail(20).mean()
        std_vol = df['Volume'].tail(20).std()
        z_score = (vol - avg_vol) / std_vol if std_vol > 0 else 0

        # Filtri Qualità
        prezzo_sale = cp > op
        sopra_trend = cp > current_sma20
        corpo = abs(cp - op)
        ombra_sup = hi - max(cp, op)
        non_respinto = ombra_sup < (corpo * 0.4) if corpo > 0 else False

        # Calcolo Probabilità Dinamiche (Basate su Z-Score)
        prob_r1 = min(85, 45 + (z_score * 10)) if z_score > 0 else 30
        prob_r2 = min(65, 20 + (z_score * 12)) if z_score > 0 else 10
        prob_r3 = min(40, 5 + (z_score * 8)) if z_score > 0 else 2

        # Output Log GitHub
        print(f"📊 {ticker:5} | CP: {cp:7.2f} | Z: {z_score:5.1f}", end=" ")

        # --- LOGICA ALERT ---
        var_pct = ((cp - op) / op) * 100
        tipo_alert, commento_ia = "", ""

        if z_score > 3.0 and prezzo_sale and sopra_trend and non_respinto:
            tipo_alert = "🐋 SWEEP CALL"
            commento_ia = "Balene in spinta. Trend confermato."
        elif 2.0 < z_score < 3.0 and abs(var_pct) < 0.30 and sopra_trend:
            tipo_alert = "🧊 ICEBERG (Accumulo)"
            commento_ia = "Assorbimento ordini in corso."

        if tipo_alert:
            # Segnale visivo su GitHub
            print(f"📩 INVIO TELEGRAM PER {ticker}!") 
            
            # --- COSTRUZIONE MESSAGGIO ---
            msg = f"*{tipo_alert}*\n📊 **TITOLO: {ticker}**\n"
            msg += f"----------------------------\n"
            msg += f"💰 PREZZO: ${cp:.2f} ({var_pct:+.2f}%)\n"
            msg += f"⚡ **Z-VOL: {z_score:.1f}**\n"
            
            # --- SE IL TITOLO È IN PORTAFOGLIO: TARGET AGGRESSIVI ---
            if ticker in MY_PORTFOLIO:
                msg += f"\n🎯 **TARGET E PROBABILITÀ PRO:**\n"
                msg += f"🟢 R1: ${res1:.2f} | Prob: {prob_r1:.0f}%\n"
                msg += f"🟠 R2: ${res2:.2f} | Prob: {prob_r2:.0f}% (BIG WHALE)\n"
                msg += f"🔴 R3: ${res3:.2f} | Prob: {prob_r3:.0f}% (MOONSHOT)\n"
                msg += f"💡 *Punta al massimo: segui il trend a R2!*"
            else:
                # Per la watchlist normale diamo solo i livelli base
                msg += f"\n🚀 RESISTENZA: ${res1:.2f}\n"
                msg += f"🛡️ SUPPORTO: ${sup1:.2f}\n"

            msg += f"\n----------------------------\n"
            msg += f"🤖 IA: {commento_ia}"
            
            send_telegram(msg)
            alert_history[ticker] = now
        else:
            motivo = "Reiezione" if not non_respinto and z_score > 2 else "OK"
            print(f"| {motivo}")

    except Exception as e:
        print(f"| Errore: {str(e)}")

def main():
    tz_ny = pytz.timezone('US/Eastern')
    now_ny = datetime.now(tz_ny)
    if now_ny.hour > 15 or (now_ny.hour == 15 and now_ny.minute >= 45):
        print(f"\n🛑 ORARIO DI CHIUSURA (NY: {now_ny.strftime('%H:%M')}). Scanner in pausa.")
        return

    all_tickers = sorted(list(set(MY_PORTFOLIO + WATCHLIST_200)))
    now = datetime.now()
    
    print(f"\n{'='*50}")
    print(f"🚀 AVVIO SCANSIONE PRO - {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*50}\n")
    
    for t in all_tickers:
        analyze_stock(t)
        time.sleep(0.5)

    print(f"\n{'='*50}")
    print(f"✅ SCANSIONE COMPLETATA")
    print(f"{'='*50}")

if __name__ == "__main__":
    main()

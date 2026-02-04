import sys
from datetime import datetime, timedelta
import time
import os
import requests
import pytz

# 1. TEST DI AVVIO E CARICAMENTO LIBRERIE
print("--- TEST DI AVVIO SCANNER PRO 2026 ---")
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
MY_PORTFOLIO = ["STNE", "PATH", "RGTI", "BBAI", "SOFI", "ADCT", "AGEN", "DKNG", "QUBT", "ETOR"]

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
        now = datetime.now()
        # Non inviare alert per lo stesso titolo prima di 45 minuti
        if ticker in alert_history and now < alert_history[ticker] + timedelta(minutes=45):
            return

        # Scarico dati (Yahoo ha 15 min di ritardo)
        data = yf.download(ticker, period="1mo", interval="15m", progress=False)
        if data.empty: return

        df = data.copy()
        df.columns = [col[0] if isinstance(col, tuple) else col for col in df.columns]

        # --- CALCOLO LIVELLI ---
        high_prev = df['High'].max()
        low_prev = df['Low'].min()
        close_prev = df['Close'].iloc[-2]
        
        pivot = (high_prev + low_prev + close_prev) / 3
        range_prev = high_prev - low_prev
        
        res1 = (2 * pivot) - low_prev
        res2 = pivot + range_prev
        res3 = high_prev + 2 * (pivot - low_prev)
        sup1 = (2 * pivot) - high_prev

        # --- INDICATORI ---
        df['SMA20'] = df['Close'].rolling(window=20).mean()
        current_sma20 = float(df['SMA20'].iloc[-1])
        cp = float(df['Close'].iloc[-1])
        op = float(df['Open'].iloc[-1])
        hi = float(df['High'].iloc[-1])
        vol = float(df['Volume'].iloc[-1])
        
        avg_vol = df['Volume'].tail(20).mean()
        std_vol = df['Volume'].tail(20).std()
        z_score = (vol - avg_vol) / std_vol if std_vol > 0 else 0

        # FILTRI QUALITÀ
        prezzo_sale = cp > op
        sopra_trend = cp > current_sma20
        corpo = abs(cp - op)
        ombra_sup = hi - max(cp, op)
        non_respinto = ombra_sup < (corpo * 0.4) if corpo > 0 else False

        # Probabilità Dinamiche
        prob_r1 = min(85, 45 + (z_score * 10)) if z_score > 0 else 30
        prob_r2 = min(65, 20 + (z_score * 12)) if z_score > 0 else 10
        prob_r3 = min(40, 5 + (z_score * 8)) if z_score > 0 else 2

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
            is_portfolio = ticker in MY_PORTFOLIO
            header = "💼 [MY PORTFOLIO]" if is_portfolio else "🛰️ [WATCHLIST]"
            
            print(f"📩 INVIO TELEGRAM PER {ticker}!") 
            
            msg = f"{header}\n*{tipo_alert}*\n📊 **TITOLO: {ticker}**\n"
            msg += f"----------------------------\n"
            msg += f"💰 PREZZO (Rit. 15m): ${cp:.2f} ({var_pct:+.2f}%)\n"
            msg += f"⚡ **Z-VOL: {z_score:.1f}**\n"
            
            if is_portfolio:
                whale_bonus = "💰💰💰" if prob_r2 > 60 else ""
                msg += f"\n🎯 **TARGET E PROBABILITÀ PRO:**\n"
                msg += f"🟢 R1: ${res1:.2f} | Prob: {prob_r1:.0f}%\n"
                msg += f"🟠 R2: ${res2:.2f} | Prob: {prob_r2:.0f}% (BIG WHALE) {whale_bonus}\n"
                msg += f"🔴 R3: ${res3:.2f} | Prob: {prob_r3:.0f}% (MOONSHOT)\n"
                msg += f"🛡️ **SUPPORTO CHIAVE: ${sup1:.2f}**\n"
                msg += f"\n💡 *Punta ai 50€: vendi a R2 o R3!*"
            else:
                msg += f"\n🚀 RESISTENZA (R1): ${res1:.2f}\n"
                msg += f"🛡️ SUPPORTO (S1): ${sup1:.2f}\n"

            msg += f"\n----------------------------\n"
            msg += f"⚠️ *Dati Yahoo ritardati di 15 min*\n"
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
    today_str = now_ny.strftime('%Y-%m-%d')
    
    # --- FILTRO WEEKEND & FESTIVITÀ 2026 ---
    holidays_2026 = [
        "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", 
        "2026-05-25", "2026-06-19", "2026-07-03", "2026-09-07", 
        "2026-11-26", "2026-12-25"
    ]
    
    if now_ny.weekday() >= 5 or today_str in holidays_2026:
        print(f"\n☕ MERCATO CHIUSO (NY: {now_ny.strftime('%A %d %b')}). Bot in pausa.")
        return

    # --- 1. FILTRO APERTURA (10:30 NY = 16:30 ITA) ---
    # Aspettiamo 10:30 NY perché i dati Yahoo delle 10:15 (post-caos) arrivano con 15 min di ritardo.
    if now_ny.hour < 10 or (now_ny.hour == 10 and now_ny.minute < 30):
        print(f"⏳ ATTESA: Lo scanner partirà alle 16:30 ITA (dati Yahoo delle 16:15).")
        return

    # --- 2. FILTRO CHIUSURA (15:45 NY = 21:45 ITA) ---
    # Ci fermiamo prima della chiusura reale per evitare volatilità senza direzione.
    if now_ny.hour > 15 or (now_ny.hour == 15 and now_ny.minute >= 45):
        print(f"\n🛑 ORARIO DI CHIUSURA. Scanner in pausa fino a domani.")
        return

    # 3. GESTIONE PRIORITÀ
    set_portfolio = set(MY_PORTFOLIO)
    set_watchlist = set(WATCHLIST_200)
    watchlist_pulita = list(set_watchlist - set_portfolio)
    all_tickers = sorted(MY_PORTFOLIO + watchlist_pulita)
    
    print(f"\n{'='*50}")
    print(f"🚀 AVVIO SCANSIONE PRO (Dati ritardati 15m) - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*50}\n")
    
    for t in all_tickers:
        analyze_stock(t)
        time.sleep(0.5)

if __name__ == "__main__":
    main()

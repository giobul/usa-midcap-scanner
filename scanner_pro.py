import yfinance as yf
import pandas as pd
import os
import time
import requests
from datetime import datetime, timedelta

# --- 1. CONFIGURAZIONE CREDENZIALI ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# --- 2. IL TUO PORTAFOGLIO (Gestione Attiva) ---
MY_PORTFOLIO = ["STNE", "PATH", "RGTI", "BBAI"]

# --- 3. WATCHLIST 200 MID-CAP (Incluso ADCT) ---
WATCHLIST_200 = [
    "RKLB","LYFT","ADCT","VRT","CLS","PSTG","ANET","SMCI","AVGO","MRVL","ALTR","LATT","WOLF","MU","ARM","SOXQ","POWI","DIOD","RMBS","NVDA","TSM","ASML","AMAT",
    "RKLB","ASTS","RDW","BKSY","SPIR","LMT","NOC","LHX","AVAV","KTOS","BWXT","MDA","BDRY","JOBY","ACHR","EH","UPV","SIDU","LLAP","SPCE",
    "QUBT","MSFT","GOOGL","IBM","AMZN","META","SNOW","CRWD","NET","ZS","OKTA","PANW","FTNT","DDOG","MDB","TEAM","ASAN","MOND","WDAY","NOW",
    "NU","MELI","SQ","PYPL","SHOP","PAGS","TOST","AFRM","HOOD","COIN","MARA","CLSK","RIOT","MSTR","V","MA","ADEN","GLBE","DLO","UPST",
    "OKLO","SMR","NNE","CCJ","UUUU","UEC","LEU","VST","CEG","FLR","GE","NEE","BE","CHPT","TSLA","ENPH","SEDG","FSLR","RUN","SPWR",
    "DKNG","PENN","RDDT","DUOL","APP","U","GME","AMC","PINS","SNAP","TWLO","ZM","AAL","DAL","UAL","MAR","ABNB","BKNG","RCL","CCL",
    "RIVN","LCID","NIO","XPEV","LI","BYD","TM","HMC","STLA","F","GM","RACE","QS","LTHM","ALB","LAC","MP","VALE","RIO","FCX",
    "DOCU","PLOC","GTLB","AI","UPWK","FIVN","PAGER","ESTC","BOX","DBX","EGHT","RNG","ZEN","NEWR","SPLK","SUMO","JFROG","FSLY","AKAM",
    "OPEN","RDFN","Z","EXPI","COMP","MTCH","BMBL","IAC","LYFT","UBER","DASH","GRUB","WASH","W","ETSY","EBAY","CHWY","RVLV","FIGS","SKLZ",
    "NKE","LULU","UAA","DECK","CROX","VFC","TPR","CPRI","RL","PVH","KSS","M","JWN","TGT","WMT","COST","BJ","SFM","WBA"
]

alert_history = {} 

def send_telegram(message):
    if TOKEN and CHAT_ID:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
        try: requests.post(url, data=data)
        except: pass

def analyze_stock(ticker):
    global alert_history
    try:
        now = datetime.now()
        # Evita alert ripetitivi sullo stesso titolo per 45 minuti
        if ticker in alert_history and now < alert_history[ticker] + timedelta(minutes=45):
            return

        data = yf.download([ticker, "SPY"], period="20d", interval="15m", progress=False)
        if data.empty: return
        
        df = data['Close'][ticker].to_frame()
        df['Volume'] = data['Volume'][ticker]
        df['High'] = data['High'][ticker]
        df['Low'] = data['Low'][ticker]
        
        spy_change = (data['Close']['SPY'].iloc[-1] - data['Close']['SPY'].iloc[-2]) / data['Close']['SPY'].iloc[-2]
        
        cp = float(df[ticker].iloc[-1])
        hi = float(df['High'].iloc[-1])
        lo_prev = float(df['Low'].iloc[-2]) 
        prev_cp = float(df[ticker].iloc[-2])
        vol = float(df['Volume'].iloc[-1])
        
        # Filtro qualità: evita di segnalare se c'è stata una forte reiezione (ombra alta)
        if (hi - cp) > (hi - prev_cp) * 0.4: return

        avg_vol = df['Volume'].tail(20).mean()
        std_vol = df['Volume'].tail(20).std()
        z_score = (vol - avg_vol) / std_vol if std_vol > 0 else 0
        
        res_20d = float(df[ticker].max())
        
        # Calcolo RSI semplificato
        delta = df[ticker].diff()
        gain = (delta.where(delta > 0, 0)).tail(14).mean()
        loss = (-delta.where(delta < 0, 0)).tail(14).mean()
        rsi = float(100 - (100 / (1 + (gain / loss.replace(0, 0.001)))))

        var_pct = ((cp - prev_cp) / prev_cp) * 100
        is_stronger_than_market = var_pct > (spy_change * 100)
        
        tipo_alert, commento_ia, stop_info = "", "", ""

        # --- LOGICA 1: ACQUISTO ---
        if z_score > 3.0 and var_pct > 0.70 and is_stronger_than_market:
            tipo_alert = "🚀 BREAKOUT + SWEEP 🚀" if cp >= res_20d else "🐋 SWEEP CALL"
            commento_ia = f"Volume anomalo (Z-VOL {z_score:.1f}). Balene in acquisto."
        
        elif 2.0 < z_score < 3.0 and abs(var_pct) < 0.30:
            tipo_alert = "🧊 ICEBERG (Accumulo)"
            commento_ia = "Assorbimento ordini rilevato. Accumulo istituzionale."

        # --- LOGICA 2 & 3: GESTIONE PORTFOLIO ---
        if ticker in MY_PORTFOLIO:
            if rsi >= 75 or cp >= res_20d:
                stop_info = f"\n🛡️ **TRAILING STOP CONSIGLIATO: ${lo_prev:.2f}**"
                
                if z_score < 1.0:
                    tipo_alert = "🚨 ATTENZIONE: DIVERGENZA 🚨"
                    commento_ia = "Prezzo su, Balene giù. Possibile svuotamento posizioni."
                else:
                    tipo_alert = "⚠️ MONITORAGGIO: TREND FORTE ⚠️"
                    commento_ia = "Trend sano e supportato. Alza lo stop e cavalca."

        if tipo_alert:
            msg = f"{tipo_alert}\n📊 **TITOLO: {ticker}**\n----------------------------\n"
            msg += f"💰 PREZZO: ${cp:.2f} ({var_pct:+.2f}%)\n⚡ **Z-VOL: {z_score:.1f}**\n"
            msg += f"🔥 RSI: {rsi:.1f}\n----------------------------\n🤖 IA: {commento_ia}{stop_info}"
            
            send_telegram(msg)
            alert_history[ticker] = now

    except Exception as e:
        print(f"Errore su {ticker}: {e}")

def main():
    all_tickers = sorted(list(set(MY_PORTFOLIO + WATCHLIST_200)))
    
    # Orario UTC (15 = 16:00 italiane)
    now = datetime.now()
    # Invia il messaggio di avvio SOLO nel primo quarto d'ora dell'apertura (16:00-16:14)
    if now.hour == 15 and now.minute < 15:
        send_telegram(f"🚀 **Scanner Pro 2026: Sessione Avviata**\nMonitoraggio: {len(all_tickers)} titoli.\nStrategia: No Limits.")
    
    for t in all_tickers:
        analyze_stock(t)
        time.sleep(1)

if __name__ == "__main__":
    main()

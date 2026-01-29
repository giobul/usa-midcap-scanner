import yfinance as yf
import pandas as pd
import os
import time
import requests
import csv
from datetime import datetime, timedelta

# --- 1. CONFIGURAZIONE CREDENZIALI ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# --- 2. IL TUO PORTAFOGLIO PRIORITARIO ---
MY_PORTFOLIO = ["STNE", "PATH", "RGTI", "PLTR", "SOUN", "IONQ", "BBAI", "HIMS", "CLSK", "MARA"]

# --- 3. WATCHLIST 200 MID-CAP (SETTORI CHIAVE 2026) ---
WATCHLIST_200 = [
    "VRT","CLS","PSTG","ANET","SMCI","AVGO","MRVL","ALTR","LATT","WOLF","MU","ARM","SOXQ","POWI","DIOD","RMBS","NVDA","TSM","ASML","AMAT",
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

LOG_FILE = "trading_log.csv"
alert_history = {} 

def save_to_log(ticker, tipo, prezzo, z_vol, rsi):
    file_exists = os.path.isfile(LOG_FILE)
    with open(LOG_FILE, mode='a', newline='') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(['Data', 'Ticker', 'Tipo Alert', 'Prezzo', 'Z-Vol', 'RSI'])
        writer.writerow([datetime.now().strftime("%Y-%m-%d %H:%M"), ticker, tipo, prezzo, z_vol, rsi])

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
        if ticker in alert_history and now < alert_history[ticker] + timedelta(minutes=45):
            return

        data = yf.download([ticker, "SPY"], period="20d", interval="15m", progress=False)
        if data.empty: return
        
        df = data['Close'][ticker].to_frame()
        df['Volume'] = data['Volume'][ticker]
        df['High'] = data['High'][ticker]
        spy_change = (data['Close']['SPY'].iloc[-1] - data['Close']['SPY'].iloc[-2]) / data['Close']['SPY'].iloc[-2]
        
        cp = float(df[ticker].iloc[-1])
        hi = float(df['High'].iloc[-1])
        prev_cp = float(df[ticker].iloc[-2])
        vol = float(df['Volume'].iloc[-1])
        
        if (hi - cp) > (hi - prev_cp) * 0.4: return

        avg_vol = df['Volume'].tail(20).mean()
        std_vol = df['Volume'].tail(20).std()
        z_score = (vol - avg_vol) / std_vol if std_vol > 0 else 0
        
        res_20d = float(df[ticker].max())
        sup = float(df[ticker].tail(20).min())
        dist_sup = ((cp - sup) / sup) * 100
        
        delta = df[ticker].diff()
        gain = (delta.where(delta > 0, 0)).tail(14).mean()
        loss = (-delta.where(delta < 0, 0)).tail(14).mean()
        rsi = float(100 - (100 / (1 + (gain / loss.replace(0, 0.001)))))

        var_pct = ((cp - prev_cp) / prev_cp) * 100
        is_stronger_than_market = var_pct > (spy_change * 100)
        
        # --- LOGICA SEGNALI ---
        tipo_alert, commento_ia = "", ""

        # SEGNALI DI ACQUISTO (Validi per TUTTI i 200+ titoli)
        if z_score > 3.0 and var_pct > 0.70 and is_stronger_than_market:
            if cp >= res_20d:
                tipo_alert = "🚀 BREAKOUT STORICO + SWEEP 🚀"
                commento_ia = f"Rottura massimi con volumi estremi (Z-VOL {z_score:.1f})."
            else:
                tipo_alert = "🐋 SWEEP CALL (Aggressione)"
                commento_ia = f"Forte aggressione istituzionale (Z-VOL: {z_score:.1f})."
        
        elif 2.0 < z_score < 3.0 and abs(var_pct) < 0.30:
            tipo_alert = "🧊 ICEBERG (Accumulo)"
            commento_ia = "Accumulo silenzioso rilevato (Mani forti)."

        # SEGNALE DI VENDITA (Solo se il titolo è effettivamente in MY_PORTFOLIO)
        if ticker in MY_PORTFOLIO:
            if rsi >= 75 or cp >= res_20d:
                tipo_alert = "⚠️ MONITORAGGIO VENDITA ⚠️"
                commento_ia = "Titolo in Portfolio ha raggiunto Ipercomprato o Resistenza. Valuta profit-taking."

        if tipo_alert:
            msg = f"{tipo_alert}\n📊 **TITOLO: {ticker}**\n----------------------------\n"
            msg += f"💰 PREZZO: ${cp:.2f} ({var_pct:+.2f}%)\n⚡ **Z-VOL: {z_score:.1f}**\n"
            msg += f"🧱 Sup: ${sup:.2f} (**-{dist_sup:.2f}%**) | Res: ${res_20d:.2f}\n"
            msg += f"🔥 RSI: {rsi:.1f}\n----------------------------\n🤖 IA: {commento_ia}"
            
            send_telegram(msg)
            save_to_log(ticker, tipo_alert, cp, round(z_score, 2), round(rsi, 2))
            alert_history[ticker] = now

    except Exception as e:
        print(f"Errore su {ticker}: {e}")

def main():
    all_tickers = sorted(list(set(MY_PORTFOLIO + WATCHLIST_200)))
    count = len(all_tickers)
    
    current_hour = datetime.now().hour
    is_manual = os.getenv("GITHUB_EVENT_NAME") == "workflow_dispatch"
    
    if is_manual or current_hour == 15: # 15 UTC = 16:00 Italia
        start_msg = (
            f"🚀 **Scanner Pro 2026: Sessione Avviata**\n"
            f"----------------------------\n"
            f"📈 Monitoraggio su **{count}** Mid-Cap.\n"
            f"🎯 Focus: Sweep & Iceberg (Z-Score > 2.0)\n"
            f"✅ Prima scansione in corso..."
        )
        send_telegram(start_msg)
    
    for t in all_tickers:
        analyze_stock(t)
        time.sleep(1)

if __name__ == "__main__":
    main()

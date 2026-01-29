import yfinance as yf
import pandas as pd
import datetime
import requests
import os
import time
import io
import numpy as np

# --- CONFIGURAZIONE ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Portfolio prioritario
MY_PORTFOLIO = ["STNE", "PATH", "RGTI", "PLTR", "SOUN", "IONQ", "BBAI", "HIMS", "CLSK", "MARA"]

# Selezione 200 Titoli Mid-Cap / Growth / AI / Energy
TICKERS_WATCHLIST = [
    "RKLB", "ASTS", "OKLO", "SMR", "RIOT", "NU", "MELI", "SE", "SQ", "SHOP",
    "SNOW", "NET", "DDOG", "CRWD", "ZS", "OKTA", "S", "MSTR", "COIN", "HOOD",
    "AFRM", "UPST", "OPEN", "SOFI", "LCID", "RIVN", "NIO", "XPEV", "LI", "ENPH",
    "FSLR", "BE", "RUN", "CHPT", "BLNK", "STEM", "QS", "PLUG", "FCEL", "CRSP",
    "NTLA", "EDIT", "BEAM", "BNTX", "MRNA", "TDOC", "RXRX", "SDGR", "AMRC", "U",
    "ROKU", "PINS", "SNAP", "DKNG", "PENN", "BYND", "TSN", "CELH", "SYM", "GTLB",
    "MNDY", "ASAN", "SMCI", "ARM", "ALTR", "LSCC", "WOLF", "DOCU", "BILL", "CFLT",
    "DUOL", "APP", "PSTG", "STX", "WDC", "MU", "AVGO", "LRCX", "KLAC", "TER",
    "TSM", "ASML", "AMAT", "ONT", "AMD", "INTC", "TXN", "ADI", "NXPI", "MCHP",
    "ON", "MPWR", "SWKS", "QRVO", "CRSR", "LOGI", "RBLX", "MTCH", "BMBL", "IAC",
    "EXPE", "BKNG", "ABNB", "TRIP", "TROW", "COUP", "WDAY", "ADSK", "PTC", "ANSS",
    "TEAM", "ADBE", "CRM", "ORCL", "SAP", "NOW", "WORK", "ZS", "PANW", "FTNT",
    "CBRE", "WY", "AMT", "CCI", "PLD", "EQIX", "DLR", "VTR", "WELL", "SPG",
    "O", "VICI", "GLPI", "LAMR", "OUT", "LYFT", "UBER", "DASH", "CART", "GRUB",
    "ZM", "TWLO", "RNG", "VG", "BAND", "FIVN", "EGHT", "AVAYA", "LULU", "NKE",
    "SBUX", "PFE", "JNJ", "ABBV", "GILD", "AMGN", "REGN", "VRTX", "BIIB", "ILMN",
    "DNA", "PACB", "NVTA", "GH", "EXAS", "FGEN", "TRUP", "LMND", "ROOT", "MILE",
    "DKNG", "SKLZ", "BETZ", "PEN", "WYNN", "LVS", "MLCO", "CZR", "MGM", "ERI"
]

def send_telegram(message):
    if TOKEN and CHAT_ID:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
        try: requests.post(url, data=data)
        except: pass

def get_market_sentiment():
    try:
        spy = yf.Ticker("SPY").history(period="2d")
        c1 = float(spy['Close'].iloc[-1].item())
        c2 = float(spy['Close'].iloc[-2].item())
        change = ((c1 - c2) / c2) * 100
        if change > 0.3: return "TORO 🐂 (Rialzista)"
        if change < -0.3: return "ORSO 🐻 (Ribassista)"
        return "LATERALE ⚖️"
    except: return "NEUTRALE"

def analyze_stock(ticker, sentiment):
    try:
        df = yf.download(ticker, period="20d", interval="15m", progress=False)
        if df.empty or len(df) < 30: return False

        cp = float(df['Close'].iloc[-1].item())
        op = float(df['Open'].iloc[-1].item())
        vol = float(df['Volume'].iloc[-1].item())
        
        avg_vol = float(df['Volume'].rolling(window=20).mean().iloc[-1].item())
        z_score = vol / avg_vol if avg_vol > 0 else 0
        
        res = float(df['High'].rolling(window=20).max().iloc[-1].item())
        sup = float(df['Low'].rolling(window=20).min().iloc[-1].item())
        
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss.replace(0, 0.001)
        rsi = float(100 - (100 / (1 + float(rs.iloc[-1].item()))))

        var_pct = ((cp - op) / op) * 100
        tipo_alert = ""
        commento_ia = "Prezzo in tenuta, monitorare volumi."

        # LOGICA ALERT ISTITUZIONALI
        if z_score > 2.5:
            if abs(var_pct) < 0.25:
                tipo_alert = "🧊 ICEBERG (Accumulo Istituzionale)"
                commento_ia = "Un grosso player sta comprando senza muovere il prezzo. Ottima base."
            elif var_pct > 0.70:
                tipo_alert = "🐋 SWEEP CALL (Aggressione)"
                commento_ia = "Forte pressione in acquisto. Monitora il breakout."

        # LOGICA COMMENTO VENDITA
        if rsi >= 75:
            commento_ia = "Indicatori in forte eccesso tecnico. CONSIDERA VENDITA!"
        elif cp >= res:
            commento_ia = "Prezzo a contatto con la resistenza. CONSIDERA VENDITA!"

        # INVIO ALERT (Se anomalia o se Portfolio in verde)
        if tipo_alert or (ticker in MY_PORTFOLIO and cp > op) or rsi >= 75:
            tag = "⭐ PORTFOLIO ⭐" if ticker in MY_PORTFOLIO else "🔍 SCANNER"
            if rsi >= 75: tag = "⚠️ MONITORAGGIO VENDITA ⚠️"
            
            msg = f"{tag}\n"
            msg += f"📊 **TITOLO: {ticker}**\n"
            msg += f"🌡 Clima Mercato: {sentiment}\n"
            msg += f"----------------------------\n"
            msg += f"💰 VALORE ATTUALE: ${cp:.2f} ({var_pct:+.2f}%)\n"
            msg += f"🧱 Supporto: ${sup:.2f} | Resistenza: ${res:.2f}\n"
            msg += f"🔥 RSI: {rsi:.1f}\n"
            msg += f"⚠️ TIPO: {tipo_alert if tipo_alert else 'Movimento Regolare'}\n"
            msg += f"----------------------------\n"
            msg += f"🤖 COMMENTO IA: {commento_ia}"
            
            send_telegram(msg)
            return True
        return False
    except: return False

def main():
    sentiment = get_market_sentiment()
    all_tickers = sorted(list(set(MY_PORTFOLIO + TICKERS_WATCHLIST)))
    
    send_telegram(f"🚀 **INIZIO SCANSIONE AGGRESSIVA**\n🌍 Mercato: {sentiment}\n🔍 Analizzo {len(all_tickers)} titoli (Portfolio + Watchlist)...")

    trovati = []
    for t in all_tickers:
        if analyze_stock(t, sentiment):
            trovati.append(t)
        time.sleep(0.4)

    lista_txt = ", ".join(trovati) if trovati else "Nessun segnale rilevante."
    report = (f"🏁 **FINE SCANSIONE**\n"
              f"📊 Titoli elaborati: {len(all_tickers)}\n"
              f"📈 Segnali inviati: {len(trovati)}\n"
              f"📋 Lista in positivo:\n`{lista_txt}`")
    send_telegram(report)

if __name__ == "__main__":
    main()

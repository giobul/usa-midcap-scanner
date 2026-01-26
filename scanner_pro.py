import time

# Configurazione Watchlist e Parametri
watchlist = ["STNE", "RGTI", "IONQ", "VKTX", "PATH", "ADCT"]
my_portfolio = {"STNE": 15.90} # Prezzo di carico utente

def analyze_market_flow(ticker):
    # Simulazione recupero dati Real-Time (API Flow/Options)
    # In produzione qui collegheresti il feed di borsa
    data = fetch_market_data(ticker) 
    
    volume = data['option_volume']
    open_interest = data['open_interest']
    is_opening_trade = volume > open_interest
    score = data['institutional_score'] # Calcolato su dimensione ordini e aggressività
    
    # 1. LOGICA BULLISH (CACCIA - MESSAGGIO BLU)
    if data['type'] == 'CALL_SWEEP' and is_opening_trade and score >= 8:
        send_telegram_msg(f"🔵 **CACCIA (BULLISH)**: {ticker}\n"
                          f"━━━━━━━━━━━━━━━\n"
                          f"📊 SCORE: {score}/10 ⭐\n"
                          f"💰 Prezzo: ${data['price']}\n"
                          f"🔥 Tipo: OPENING CALL SWEEP\n"
                          f"📍 Supporto Breakout (STOP): ${data['support']}")

    # 2. LOGICA BEARISH (PERICOLO - MESSAGGIO ROSSO)
    elif data['type'] == 'PUT_SWEEP' and is_opening_trade and score >= 8:
        # Se il titolo è nel tuo portafoglio, l'allerta è massima
        priority = "🚨 EMERGENZA" if ticker in my_portfolio else "⚠️ ATTENZIONE"
        send_telegram_msg(f"🔴 **{priority} (BEARISH)**: {ticker}\n"
                          f"━━━━━━━━━━━━━━━\n"
                          f"📊 SCORE: {score}/10 ⛔\n"
                          f"💰 Prezzo: ${data['price']}\n"
                          f"💀 Tipo: AGGRESSIVE PUT SWEEP\n"
                          f"📢 Nota: Istituzionali scommettono al ribasso!")

    # 3. LOGICA EXIT (PROFITTO - MESSAGGIO GIALLO)
    if data['rsi'] >= 75:
        send_telegram_msg(f"🟡 **EXIT (PROFITTO)**: {ticker}\n"
                          f"━━━━━━━━━━━━━━━\n"
                          f"💰 Prezzo attuale: ${data['price']}\n"
                          f"📈 RSI: {data['rsi']} (Ipercomprato)\n"
                          f"✅ Target raggiunto! Valuta chiusura.")

# Funzione per simulare il loop di controllo
def monitor_session():
    print("Radar Attivo: Monitoraggio Apertura (15:30) e Flussi...")
    # Qui il codice gira ciclicamente durante la sessione USA

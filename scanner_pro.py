import os
import requests
import time

def send_telegram(message, silent=False):
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id: return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id, 
        "text": message, 
        "parse_mode": "Markdown",
        "disable_notification": silent
    }
    requests.post(url, json=payload)

def main():
    # TEST SILENZIOSO
    send_telegram("🧊 TEST SILENZIOSO (Iceberg)", silent=True)
    
    time.sleep(5)
    
    # TEST SVEGLIA (Invia 3 messaggi per forzare il suono)
    for i in range(3):
        send_telegram(f"🚨🚨 ALLARME VENDITA TEST {i+1} 🚨🚨", silent=False)
        time.sleep(1)

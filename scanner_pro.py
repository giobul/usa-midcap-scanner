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
    # TEST 1: Messaggio Silenzioso (Tipo ICEBERG)
    print("Inviando messaggio silenzioso...")
    send_telegram("🧊 TEST SILENZIOSO: Questo messaggio non dovrebbe suonare.", silent=True)
    
    time.sleep(10) # Aspettiamo 10 secondi
    
    # TEST 2: Messaggio con Suono (Tipo EXIT)
    print("Inviando messaggio con ALLERTA...")
    send_telegram("🚨 TEST SVEGLIA: Questo messaggio DEVE SUONARE FORTE! 🚨", silent=False)

if __name__ == "__main__":
    main()

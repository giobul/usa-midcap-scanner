import os
import requests
import time

def send_telegram(message):
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id: return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

def main():
    print("Inizio test martellamento distanziato...")
    
    alert_text = "🚨🚨 **VENDITA STNE** 🚨🚨\nTest segnale EXIT (3 avvisi distanziati)"
    
    for i in range(3):
        send_telegram(f"{alert_text} [{i+1}/3]")
        print(f"Inviato messaggio {i+1}, ora aspetto 5 secondi...")
        if i < 2: # Non aspettare dopo l'ultimo messaggio
            time.sleep(5) 

if __name__ == "__main__":
    main()

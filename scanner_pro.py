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
    print("Inizio test raffica di messaggi...")
    
    # Simuliamo l'allerta di vendita
    alert_text = "🚨🚨 **TEST VENDITA URGENTE** 🚨🚨\nQuesto è un test del segnale EXIT!"
    
    for i in range(5):
        send_telegram(f"{alert_text} (Messaggio {i+1}/5)")
        print(f"Inviato messaggio {i+1}")
        time.sleep(1.5) # Pausa breve per far suonare il telefono più volte

if __name__ == "__main__":
    main()

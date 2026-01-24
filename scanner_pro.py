import os
import requests

def main():
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    # Test base senza parametri extra
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id, 
        "text": "🚨 TEST FINALE: Se leggi questo, il collegamento funziona!"
    }
    
    r = requests.post(url, json=payload)
    print(f"Stato invio: {r.status_code}") # Questo apparirà nei log di GitHub

if __name__ == "__main__":
    main()

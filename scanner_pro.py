import os
import requests

token = os.getenv("TELEGRAM_TOKEN")
chat_id = os.getenv("CHAT_ID")

def test_diretto():
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": "🚨 TEST CONNESSIONE: Se leggi questo, il bot è configurato bene!"
    }
    r = requests.post(url, json=payload)
    print(f"Status Code: {r.status_code}")
    print(f"Risposta: {r.text}")

if __name__ == "__main__":
    test_diretto()

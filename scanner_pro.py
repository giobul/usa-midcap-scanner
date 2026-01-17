import os
import requests

# Test rapido dei segreti
token = os.getenv("TELEGRAM_TOKEN")
chat_id = os.getenv("CHAT_ID")

def test_telegram():
    if not token or not chat_id:
        print("ERRORE: Secrets non configurati correttamente su GitHub!")
        return
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = {"chat_id": chat_id, "text": "✅ CONNESSIONE GITHUB STABILITA! Il bot è pronto per lunedì."}
    res = requests.post(url, json=data)
    if res.status_code == 200:
        print("Messaggio inviato con successo!")
    else:
        print(f"Errore Telegram: {res.text}")

if __name__ == "__main__":
    test_telegram()

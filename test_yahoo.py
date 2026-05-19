import yfinance as yf
import pandas as pd

def test_puro():
    ticker = "SPY"
    print(f"🔄 Tentativo di download storico 15m per {ticker}...")
    
    try:
        df = yf.download(ticker, period="5d", interval="15m", progress=False)
        
        if df.empty:
            print("❌ Errore: Il DataFrame è vuoto. Yahoo non sta rispondendo.")
            return
            
        print("✅ Connessione riuscita! Dati ricevuti.")
        print(f"📊 Numero di candele caricate: {len(df)}")
        print("\n--- Ultime 3 candele disponibili nel database di Yahoo: ---")
        print(df[['Open', 'High', 'Low', 'Close', 'Volume']].tail(3))
        
        df_consolidato = df.iloc[:-1]
        print(f"\n✂️ Taglio candela live applicato. Righe rimanenti per l'analisi: {len(df_consolidato)}")
        
    except Exception as e:
        print(f"💥 Il codice è andato in crash! Errore tecnico: {e}")

if __name__ == "__main__":
    test_puro()

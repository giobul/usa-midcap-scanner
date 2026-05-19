name: Test Immediato Yahoo Finance
on:
  workflow_dispatch:

jobs:
  run-test:
    runs-on: ubuntu-latest
    steps:
    - name: Checkout del codice
      uses: actions/checkout@v4

    - name: Configura Python
      uses: actions/setup-python@v5
      with:
        python-version: '3.10'

    - name: Installa le librerie
      run: |
        pip install yfinance pandas

    - name: Mostra dove sono i file (Debug)
      run: |
        echo "=== Dove mi trovo ==="
        pwd
        echo "=== Contenuto della cartella ==="
        ls -la

    - name: Esegui lo script di test
      run: |
        if [ -f "test_yahoo.py" ]; then
          python test_yahoo.py
        else
          echo "❌ Errore: test_yahoo.py non è nella cartella principale! Controllo nelle sotto-cartelle..."
          find . -name "test_yahoo.py" -exec python {} \;
        fi

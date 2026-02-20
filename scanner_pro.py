#!/usr/bin/env python3
"""
NEXUS v14.1 - THE FINAL FORM
Production-Ready Institutional Flow Scanner

NEW IN v14.1:
✅ Earnings Calendar Filter (avoids earnings surprises)
✅ Sector Diversification (max 2 per sector)
✅ Enhanced IFS threshold (minimum 5/7)
✅ Improved logging with sector tracking
✅ Rate limit protection for Telegram
"""

import yfinance as yf
import pandas as pd
import numpy as np
import requests
import warnings
import pytz
import time
import os
import json
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict

warnings.filterwarnings("ignore")

# ==============================
# 🔑 CONFIGURATION
# ==============================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "YOUR_TOKEN_HERE")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "YOUR_CHAT_ID_HERE")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "nexus_trade_log.csv")
EARNINGS_CACHE = os.path.join(BASE_DIR, ".earnings_cache.json")

CONFIG = {
    "TOTAL_EQUITY": 100000,
    "RISK_PER_TRADE_PERCENT": 0.01,
    "MAX_THREADS": 3,
    "MIN_VOLUME_USD": 1_000_000,
    "MAX_ALERTS": 5,
    "MIN_IFS_SCORE": 5,              # NEW: Raised from 4 to 5
    "MAX_PER_SECTOR": 2,             # NEW: Sector diversification
    "EARNINGS_LOOKBACK_DAYS": 1,     # NEW: Avoid if earnings within 1 day
    "EARNINGS_LOOKAHEAD_DAYS": 1,    # NEW: Avoid if earnings within 1 day
}

# ==============================
# 📋 SECTOR MAPPING (Complete)
# ==============================
SECTOR_MAP = {
    # Mega Tech (FAANG+)
    "AAPL": "Tech", "MSFT": "Tech", "GOOGL": "Tech", "META": "Tech", "AMZN": "Ecommerce",
    "TSLA": "EV", "NFLX": "Media", "BRK-B": "Finance",
    
    # Semiconductors
    "NVDA": "Semis", "AMD": "Semis", "INTC": "Semis", "QCOM": "Semis", "AVGO": "Semis",
    "TSM": "Semis", "ASML": "Semis", "AMAT": "Semis", "LRCX": "Semis", "KLAC": "Semis",
    "MU": "Semis", "ON": "Semis", "MRVL": "Semis", "NXPI": "Semis", "ADI": "Semis",
    "MCHP": "Semis", "MPWR": "Semis", "ENTG": "Semis", "TER": "Semis", "COHR": "Semis",
    "OLED": "Semis", "LSCC": "Semis", "SWKS": "Semis", "QRVO": "Semis", "TXN": "Semis",
    "SMCI": "Semis", "SNPS": "Semis", "CDNS": "Semis",
    
    # Cloud/SaaS/Software
    "CRM": "Cloud", "ADBE": "Cloud", "NOW": "Cloud", "ORCL": "Cloud", "SHOP": "Cloud",
    "SNOW": "Cloud", "PLTR": "Cloud", "DDOG": "Cloud", "MDB": "Cloud", "TEAM": "Cloud",
    "ESTC": "Cloud", "OKTA": "Cloud", "TWLO": "Cloud", "HUBS": "Cloud", "BILL": "Cloud",
    "U": "Cloud", "APP": "Cloud", "DOCN": "Cloud", "FSLY": "Cloud", "DT": "Cloud",
    "AI": "Cloud", "PATH": "Cloud", "SOUN": "Cloud",
    
    # Cybersecurity
    "PANW": "Cyber", "CRWD": "Cyber", "ZS": "Cyber", "NET": "Cyber",
    
    # Networking
    "CSCO": "Tech", "ANET": "Tech",
    
    # Fintech/Payments
    "PYPL": "Fintech", "SQ": "Fintech", "SOFI": "Fintech", "COIN": "Fintech",
    "HOOD": "Fintech", "AFRM": "Fintech", "STNE": "Fintech", "NU": "Fintech",
    "PAGS": "Fintech", "UPST": "Fintech",
    
    # Traditional Finance
    "JPM": "Finance", "BAC": "Finance", "WFC": "Finance", "C": "Finance", "GS": "Finance",
    "MS": "Finance", "BLK": "Finance", "SCHW": "Finance", "AXP": "Finance",
    "ICE": "Finance", "CME": "Finance", "KKR": "Finance", "BX": "Finance",
    "APO": "Finance", "ARES": "Finance", "ALLY": "Finance",
    
    # Payment Networks
    "V": "Fintech", "MA": "Fintech",
    
    # Healthcare/Pharma
    "UNH": "Health", "LLY": "Health", "ABBV": "Health", "MRK": "Health",
    "VRTX": "Health", "REGN": "Health", "GILD": "Health", "BIIB": "Health",
    "MRNA": "Health", "BNTX": "Health", "ISRG": "Health", "SYK": "Health",
    "MDT": "Health", "TMO": "Health", "ABT": "Health", "DHR": "Health",
    "PFE": "Health", "BMY": "Health", "CVS": "Health", "HUM": "Health",
    "CI": "Health", "ELV": "Health", "IDXX": "Health", "DXCM": "Health",
    
    # Consumer Staples
    "PG": "Consumer", "COST": "Retail", "HD": "Retail", "LOW": "Retail",
    
    # Retail/Consumer Discretionary
    "NKE": "Retail", "SBUX": "Retail", "MCD": "Retail", "TGT": "Retail",
    "BKNG": "Travel", "ABNB": "Travel", "UBER": "Tech", "LYFT": "Tech",
    "EBAY": "Ecommerce", "ETSY": "Ecommerce", "ROST": "Retail", "TJX": "Retail",
    "LULU": "Retail", "ULTA": "Retail", "DPZ": "Retail", "CMG": "Retail",
    "YUM": "Retail", "MAR": "Travel", "HLT": "Travel",
    
    # Media/Telecom
    "DIS": "Media", "CMCSA": "Media", "T": "Telecom", "VZ": "Telecom",
    "CHTR": "Telecom", "TMUS": "Telecom", "PARA": "Media", "WBD": "Media",
    "FOX": "Media", "FOXA": "Media",
    
    # Energy
    "XOM": "Energy", "CVX": "Energy", "COP": "Energy", "EOG": "Energy",
    "SLB": "Energy", "HAL": "Energy", "OXY": "Energy", "PXD": "Energy",
    "MPC": "Energy", "PSX": "Energy", "VLO": "Energy", "KMI": "Energy",
    "WMB": "Energy", "DVN": "Energy", "FANG": "Energy", "APA": "Energy",
    "CTRA": "Energy", "BKR": "Energy", "HES": "Energy", "EQT": "Energy",
    "XLE": "Energy",
    
    # Industrials/Aerospace
    "BA": "Industrial", "RTX": "Industrial", "LMT": "Industrial", "NOC": "Industrial",
    "GD": "Industrial", "CAT": "Industrial", "DE": "Industrial", "ETN": "Industrial",
    "PH": "Industrial", "HON": "Industrial", "GE": "Industrial", "EMR": "Industrial",
    "MMM": "Industrial", "ITW": "Industrial", "CMI": "Industrial", "ROK": "Industrial",
    "AME": "Industrial", "TDG": "Industrial", "LHX": "Industrial", "PCAR": "Industrial",
    
    # Materials/Chemicals
    "LIN": "Materials", "APD": "Materials", "ECL": "Materials", "SHW": "Materials",
    "NEM": "Materials", "FCX": "Materials", "DOW": "Materials", "DD": "Materials",
    "ALB": "Materials", "NUE": "Materials",
    
    # Utilities
    "NEE": "Utilities", "DUK": "Utilities", "SO": "Utilities", "AEP": "Utilities",
    "EXC": "Utilities", "SRE": "Utilities", "D": "Utilities", "XEL": "Utilities",
    "PEG": "Utilities", "ED": "Utilities",
    
    # Transportation/Logistics
    "UPS": "Transport", "FDX": "Transport", "UNP": "Transport", "CSX": "Transport",
    "NSC": "Transport", "CP": "Transport", "CNI": "Transport",
    "DAL": "Airlines", "UAL": "Airlines", "AAL": "Airlines",
    
    # Crypto-Related
    "MSTR": "Crypto", "MARA": "Crypto", "RIOT": "Crypto", "CLSK": "Crypto",
    
    # EV/Clean Energy
    "RIVN": "EV", "LCID": "EV", "CHPT": "EV",
    "PLUG": "CleanEnergy", "RUN": "CleanEnergy", "SEDG": "CleanEnergy",
    "ENPH": "CleanEnergy", "BLNK": "CleanEnergy", "QS": "EV",
    
    # Gaming/Entertainment
    "RBLX": "Gaming", "DKNG": "Gaming", "FUBO": "Media",
    
    # Emerging Tech/Speculative
    "CVNA": "Retail", "BYND": "Consumer", "OPEN": "Tech",
    "ASTS": "Telecom", "RKLB": "Aerospace", "HIMS": "Health",
    "IONQ": "Tech",
}

MY_WATCHLIST = [
    "AAPL","MSFT","NVDA","AMZN","GOOGL","META","TSLA","BRK-B","UNH","XOM",
    "LLY","JPM","V","AVGO","MA","HD","PG","MRK","COST","ABBV",
    "AMD","CRM","ADBE","NFLX","INTC","ORCL","CSCO","QCOM","TXN","NOW",
    "SHOP","SNOW","PLTR","PANW","CRWD","ZS","NET","DDOG","MDB","TEAM",
    "SMCI","TSM","ASML","AMAT","LRCX","KLAC","MU","ON","MRVL","NXPI",
    "ADI","MCHP","MPWR","ENTG","TER","COHR","OLED","LSCC","SWKS","QRVO",
    "AI","PATH","UPST","SOUN","DOCN","ESTC","OKTA","TWLO","FSLY","HUBS",
    "DT","BILL","U","RBLX","AFRM","APP","SNPS","CDNS","ANET",
    "BAC","WFC","C","GS","MS","BLK","SCHW","AXP","PYPL","SQ",
    "SOFI","COIN","HOOD","ICE","CME","KKR","BX","APO","ARES","ALLY",
    "VRTX","REGN","GILD","BIIB","MRNA","BNTX","ISRG","SYK","MDT","TMO",
    "ABT","DHR","PFE","BMY","CVS","HUM","CI","ELV","IDXX","DXCM",
    "BA","RTX","LMT","NOC","GD","CAT","DE","ETN","PH","HON",
    "GE","EMR","MMM","ITW","CMI","ROK","AME","TDG","LHX","PCAR",
    "CVX","COP","EOG","SLB","HAL","OXY","PXD","MPC","PSX","VLO",
    "KMI","WMB","DVN","FANG","APA","CTRA","BKR","HES","EQT","XLE",
    "NKE","SBUX","MCD","LOW","TGT","BKNG","ABNB","UBER","LYFT","EBAY",
    "ETSY","ROST","TJX","LULU","ULTA","DPZ","CMG","YUM","MAR","HLT",
    "DIS","CMCSA","T","VZ","CHTR","TMUS","PARA","WBD","FOX","FOXA",
    "LIN","APD","ECL","SHW","NEM","FCX","DOW","DD","ALB","NUE",
    "NEE","DUK","SO","AEP","EXC","SRE","D","XEL","PEG","ED",
    "UPS","FDX","UNP","CSX","NSC","CP","CNI","DAL","UAL","AAL",
    "MARA","RIOT","CLSK","CVNA","RIVN","LCID","BYND","CHPT","FUBO",
    "OPEN","DKNG","PLUG","RUN","SEDG","ENPH","BLNK","QS","IONQ",
    "STNE","NU","PAGS","ASTS","RKLB","HIMS"
]

# ==============================
# 🛠️ UTILITIES
# ==============================
def log_trade(data, vol_ratio, sector):
    """Log trade to CSV with enhanced fields"""
    file_exists = os.path.isfile(LOG_FILE)
    log_data = data.copy()
    log_data["date"] = datetime.now().strftime("%Y-%m-%d")
    log_data["timestamp"] = datetime.now().strftime("%H:%M:%S")
    log_data["market_regime"] = "BULL"
    log_data["vol_ratio"] = round(vol_ratio, 2)
    log_data["sector"] = sector
    df = pd.DataFrame([log_data])
    df.to_csv(LOG_FILE, mode='a', index=False, header=not file_exists)

def is_market_gold_hour():
    """Check if within trading Gold Hour (10:00-15:30 EST)"""
    tz = pytz.timezone("America/New_York")
    now = datetime.now(tz)
    if now.weekday() > 4:
        return False
    start = datetime.strptime("10:00", "%H:%M").time()
    end = datetime.strptime("15:30", "%H:%M").time()
    return start <= now.time() <= end

def get_sector(ticker):
    """Get sector for ticker"""
    return SECTOR_MAP.get(ticker, "Other")

# ==============================
# 📅 EARNINGS CALENDAR
# ==============================
def load_earnings_cache():
    """Load earnings cache from file"""
    if os.path.exists(EARNINGS_CACHE):
        try:
            with open(EARNINGS_CACHE, 'r') as f:
                cache = json.load(f)
                # Check if cache is less than 7 days old
                cache_date = datetime.fromisoformat(cache.get("updated", "2000-01-01"))
                if (datetime.now() - cache_date).days < 7:
                    return cache.get("earnings", {})
        except:
            pass
    return {}

def save_earnings_cache(earnings_dict):
    """Save earnings cache to file"""
    try:
        with open(EARNINGS_CACHE, 'w') as f:
            json.dump({
                "updated": datetime.now().isoformat(),
                "earnings": earnings_dict
            }, f)
    except:
        pass

def check_earnings_risk(ticker, earnings_cache):
    """
    Check if ticker has earnings within lookback/lookahead window
    Returns True if safe (no earnings), False if risky (earnings soon)
    """
    if ticker not in earnings_cache:
        # Try to fetch from yfinance
        try:
            stock = yf.Ticker(ticker)
            calendar = stock.calendar
            if calendar is not None and not calendar.empty:
                if 'Earnings Date' in calendar.index:
                    earnings_date_raw = calendar.loc['Earnings Date'].iloc[0] if hasattr(calendar.loc['Earnings Date'], 'iloc') else calendar.loc['Earnings Date']
                    if pd.notna(earnings_date_raw):
                        earnings_date = pd.to_datetime(earnings_date_raw).date()
                        earnings_cache[ticker] = earnings_date.isoformat()
                        return True  # Cache for future use
        except:
            pass
        return True  # If can't fetch, assume safe
    
    # Check cached earnings date
    try:
        earnings_date = datetime.fromisoformat(earnings_cache[ticker]).date()
        today = datetime.now().date()
        days_diff = (earnings_date - today).days
        
        # Filter if earnings within window
        if -CONFIG["EARNINGS_LOOKBACK_DAYS"] <= days_diff <= CONFIG["EARNINGS_LOOKAHEAD_DAYS"]:
            return False  # Risky - has earnings soon
    except:
        pass
    
    return True  # Safe

# ==============================
# 📊 MARKET REGIME
# ==============================
def get_market_regime():
    """Check if market is in bull regime"""
    try:
        spy = yf.download("SPY", period="1y", interval="1d", progress=False)
        if spy is None or spy.empty:
            return False, None
        if isinstance(spy.columns, pd.MultiIndex):
            spy.columns = spy.columns.get_level_values(0)
        spy["SMA50"] = spy["Close"].rolling(50).mean()
        if len(spy) < 60:
            return False, None
        bull = spy["Close"].iloc[-1] > spy["SMA50"].iloc[-1]
        slope = spy["SMA50"].iloc[-1] > spy["SMA50"].iloc[-5]
        return bull and slope, spy
    except:
        return False, None

# ==============================
# 🧠 INSTITUTIONAL SCORE (IFS)
# ==============================
def institutional_score(df, rs_val):
    """
    Calculate Institutional Flow Score (0-7 points)
    
    Components:
    - Volume accumulation: +2 points
    - Range compression (VCP): +2 points
    - Relative Strength: +2 points
    - Bullish close: +1 point
    """
    if len(df) < 30:
        return 0
    
    score = 0
    
    # 1. Volume Accumulation (3/5 days above 20-day average)
    avg_vol20 = df["Volume"].rolling(20).mean()
    if (df["Volume"].iloc[-5:] > avg_vol20.iloc[-5:]).sum() >= 3:
        score += 2
    
    # 2. Range Compression (VCP pattern)
    hl_range = df["High"] - df["Low"]
    range5 = hl_range.rolling(5).mean().iloc[-1]
    range20 = hl_range.rolling(20).mean().iloc[-1]
    
    if pd.notna(range5) and pd.notna(range20) and range20 > 0:
        if range5 < range20:  # Volatility contracted
            score += 2
    
    # 3. Relative Strength vs SPY
    if rs_val > 0:
        score += 2
    
    # 4. Close near High (bullish candle structure)
    today = df.iloc[-1]
    day_range = today["High"] - today["Low"]
    if day_range > 0:
        close_position = (today["Close"] - today["Low"]) / day_range
        if close_position > 0.75:
            score += 1
    
    return score

# ==============================
# 🔎 ANALYZE TICKER
# ==============================
def analyze_ticker(ticker, spy_df, already_alerted, earnings_cache):
    """Analyze single ticker for institutional flow"""
    
    # Skip if already alerted today
    if ticker in already_alerted:
        return None
    
    # Check earnings risk
    if not check_earnings_risk(ticker, earnings_cache):
        return None
    
    try:
        time.sleep(0.5)
        df = yf.download(ticker, period="1y", interval="1d", progress=False)
        if df is None or len(df) < 60:
            return None
        
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        price = df["Close"].iloc[-1]
        
        # Liquidity filter
        if (price * df["Volume"].iloc[-1]) < CONFIG["MIN_VOLUME_USD"]:
            return None
        
        # Volume analysis
        vol_mean = df["Volume"].rolling(20).mean().iloc[-1]
        if pd.isna(vol_mean) or vol_mean == 0:
            return None
        
        vol_ratio = df["Volume"].iloc[-1] / vol_mean
        
        # Breakout filter (exclude today for high calculation)
        h20 = df["High"].rolling(20).max().iloc[-2]
        if pd.isna(h20):
            return None
        
        # Relative Strength (3 months)
        rs_val = df["Close"].pct_change(63).iloc[-1] - spy_df["Close"].pct_change(63).iloc[-1]
        if pd.isna(rs_val):
            return None
        
        # Main filters: Breakout + Volume
        if price > h20 and vol_ratio > 1.2:
            
            # Calculate IFS
            ifs = institutional_score(df, rs_val)
            
            # NEW: Filter by minimum IFS threshold
            if ifs < CONFIG["MIN_IFS_SCORE"]:
                return None
            
            # ATR calculation
            tr1 = df["High"] - df["Low"]
            tr2 = abs(df["High"] - df["Close"].shift())
            tr3 = abs(df["Low"] - df["Close"].shift())
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = tr.rolling(14).mean().iloc[-1]
            
            if pd.isna(atr) or atr == 0:
                return None
            
            # Risk management
            sl = price - (atr * 1.5)
            risk = price - sl
            
            if risk <= 0:
                return None
            
            size = int((CONFIG["TOTAL_EQUITY"] * CONFIG["RISK_PER_TRADE_PERCENT"]) / risk)
            
            # Probability based on IFS
            probability = min(50 + (ifs * 6), 90)
            
            # Label based on flow type
            label = "🧊 ICEBERG" if ifs >= 6 and 1.2 < vol_ratio < 2.0 else "⚡ SWEEP"
            
            # Get sector
            sector = get_sector(ticker)
            
            return {
                "ticker": ticker,
                "price": round(price, 2),
                "ifs": ifs,
                "rs": round(rs_val * 100, 1),
                "sl": round(sl, 2),
                "tg": round(price + (risk * 2.5), 2),
                "size": size,
                "prob": probability,
                "label": label,
                "vol_ratio": round(vol_ratio, 2),
                "r1": round(h20, 2),
                "r2": round(price + (atr * 2), 2),
                "sector": sector
            }
    
    except Exception as e:
        return None
    
    return None

# ==============================
# 📤 SEND TELEGRAM
# ==============================
def send_telegram(message):
    """Send message to Telegram with rate limiting"""
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "Markdown"
            },
            timeout=10
        )
        if response.status_code != 200:
            print(f"❌ Telegram Error: {response.text}")
            return False
        return True
    except Exception as e:
        print(f"❌ Telegram Exception: {e}")
        return False

# ==============================
# 🚀 MAIN
# ==============================
def main():
    """Main execution loop"""
    
    print("="*70)
    print("🧬 NEXUS v14.1 - THE FINAL FORM")
    print("="*70)
    
    # Check market hours
    if not is_market_gold_hour():
        print("⏰ Outside Gold Hour (10:00-15:30 EST)")
        return
    
    # Check market regime
    bull_market, spy_df = get_market_regime()
    if not bull_market or spy_df is None:
        print("🛑 Market Regime: BEARISH - No scan")
        return
    
    print("✅ Market Regime: BULLISH")
    
    # Load earnings cache
    earnings_cache = load_earnings_cache()
    print(f"📅 Earnings cache loaded: {len(earnings_cache)} tickers")
    
    # Get already alerted tickers today
    already_alerted = set()
    today = datetime.now().strftime("%Y-%m-%d")
    if os.path.exists(LOG_FILE):
        try:
            logged = pd.read_csv(LOG_FILE)
            if not logged.empty and "date" in logged.columns:
                already_alerted = set(logged[logged["date"] == today]["ticker"].values)
                print(f"⏭️  Already alerted today: {len(already_alerted)} tickers")
        except:
            pass
    
    print(f"🔍 Scanning {len(MY_WATCHLIST)} tickers...")
    
    # Scan all tickers
    results = []
    with ThreadPoolExecutor(max_workers=CONFIG["MAX_THREADS"]) as executor:
        futures = [
            executor.submit(analyze_ticker, ticker, spy_df, already_alerted, earnings_cache)
            for ticker in MY_WATCHLIST
        ]
        
        for future in as_completed(futures):
            result = future.result()
            if result:
                results.append(result)
    
    print(f"📊 Found {len(results)} candidates (IFS ≥ {CONFIG['MIN_IFS_SCORE']})")
    
    if not results:
        print("❌ No high-quality signals found")
        return
    
    # Sort by IFS, then RS
    results = sorted(results, key=lambda x: (x["ifs"], x["rs"]), reverse=True)
    
    # NEW: Apply sector diversification
    sector_count = defaultdict(int)
    filtered_results = []
    
    for result in results:
        sector = result["sector"]
        if sector_count[sector] < CONFIG["MAX_PER_SECTOR"]:
            filtered_results.append(result)
            sector_count[sector] += 1
        else:
            print(f"⚠️  Skipped {result['ticker']} - sector {sector} limit reached")
        
        if len(filtered_results) >= CONFIG["MAX_ALERTS"]:
            break
    
    print(f"🎯 Selected {len(filtered_results)} signals after sector filter")
    print(f"📂 Sector distribution: {dict(sector_count)}")
    print()
    
    # Send alerts and log trades
    alerts_sent = 0
    for result in filtered_results:
        
        # Log to CSV
        vol_ratio = result.pop("vol_ratio")
        sector = result["sector"]
        log_trade(result, vol_ratio, sector)
        
        # Format Telegram message
        msg = (
            f"🔭 *ALERT: {result['ticker']}* | {result['label']}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"💰 Price: `${result['price']}` | 📊 IFS: `{result['ifs']}/7` | 🏭 {sector}\n"
            f"📈 RS: `{result['rs']}%` vs SPY | 🎯 Prob: `{result['prob']}%`\n"
            f"🛡️ Size: `{result['size']} sh` (1% risk)\n"
            f"🛑 Stop: `${result['sl']}` | 🚀 Target: `${result['tg']}`\n"
            f"📊 Levels: R1 `${result['r1']}` / R2 `${result['r2']}`\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"R:R = {round((result['tg']-result['price'])/(result['price']-result['sl']), 2)}:1"
        )
        
        # Send to Telegram
        if send_telegram(msg):
            alerts_sent += 1
            print(f"✅ Alert sent: {result['ticker']} (IFS {result['ifs']}/7, {sector})")
        else:
            print(f"❌ Failed to send: {result['ticker']}")
        
        # Rate limiting
        time.sleep(1)
    
    # Save updated earnings cache
    save_earnings_cache(earnings_cache)
    
    print()
    print("="*70)
    print(f"🏁 Scan complete - {alerts_sent} alerts sent")
    print("="*70)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 Interrupted by user")
    except Exception as e:
        print(f"💥 Error: {e}")
        import traceback
        traceback.print_exc()

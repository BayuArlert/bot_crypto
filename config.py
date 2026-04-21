import os
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# 1. API CREDENTIALS
# ============================================================
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
BINANCE_SECRET  = os.getenv("BINANCE_SECRET_KEY", "")
GROQ_API_KEY    = os.getenv("GROQ_API_KEY", "") # Pindah ke Groq Llama-3

# ============================================================
# 2. MARKET SETTINGS
# ============================================================
MARKET_TYPE = "SPOT"

# Koin-koin favorit yang akan dipantau AI 
SYMBOL_LIST = [
    'BTCUSDT',  # Bitcoin
    'ETHUSDT',  # Ethereum
    'SOLUSDT',  # Solana
    'BNBUSDT',  # Binance Coin
    'XRPUSDT',  # Ripple
    'ADAUSDT',  # Cardano
    'AVAXUSDT', # Avalanche   - Volatilitas tinggi, sering bouncing tajam
    'LINKUSDT', # Chainlink   - Favorit scalper, reversal cepat
    'DOGEUSDT', # Dogecoin    - Volume Binance sangat besar, micro-bounce rutin
]

# Timeframe yang ditangkap (15m sangat pas untuk napas Scalping cepat)
TIMEFRAME = "15m"

# ============================================================
# 3. RISIKO & MODAL (Mazhab A: Cut Loss Ketat)
# ============================================================
# Bot hanya diizinkan membeli dengan modal statis per koin, 
# Tujuannya agar saldo pecah/terbagi rata jika AI menyuruh beli semua koin di atas.
BUDGET_PER_TRADE_USDT = 10.0  # $10 per tembakan (AI max 2 posisi = $20, sisa $5 buffer)
MAX_OPEN_POSITIONS    = 2     # Maksimal posisi aktif sekaligus (2×$10=$20 dari $25 modal)
SL_COOLDOWN_LOOPS     = 3     # Loop cooldown pasca Cut Loss (3 loop × 60 detik = 3 menit jeda)

STOP_LOSS_PCT   = 0.01  # -1% otomatis Cut loss (ketat, cocok untuk scalping rutin)
TAKE_PROFIT_PCT = 0.015 # +1.5% otomatis Jual Untung (realistis & rutin di timeframe 15m)

# ============================================================
# 4. BOT INTERVAL
# ============================================================
# Berapa detik bot mengulang pekerjaannya (Aman untuk CPU & Kuota: 1 Menit)
LOOP_INTERVAL_SECONDS = 60

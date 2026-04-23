import os
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# 1. API CREDENTIALS
# ============================================================
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
BINANCE_SECRET  = os.getenv("BINANCE_SECRET_KEY", "")
GROQ_API_KEY    = os.getenv("GROQ_API_KEY", "")

# ============================================================
# 2. MARKET SETTINGS
# ============================================================
MARKET_TYPE = "SPOT"

SYMBOL_LIST = [
    'BTCUSDT',  # Bitcoin
    'ETHUSDT',  # Ethereum
    'SOLUSDT',  # Solana
    'BNBUSDT',  # Binance Coin
    'XRPUSDT',  # Ripple
    'ADAUSDT',  # Cardano
    'AVAXUSDT', # Avalanche
    'LINKUSDT', # Chainlink
    'DOGEUSDT', # Dogecoin
]

TIMEFRAME   = "15m"
MTF_INTERVAL = "1h"

# ============================================================
# 3. RISIKO & MODAL
# ============================================================
BUDGET_PER_TRADE_USDT = 10.0
MAX_OPEN_POSITIONS    = 2
SL_COOLDOWN_LOOPS     = 10    # 10 menit jeda setelah SL (lebih konservatif)
BB_PCT_THRESHOLD      = 35    # Hanya untuk strategi RANGE
AI_MIN_CONFIDENCE     = 7

# ============================================================
# 4. TP/SL DINAMIS PER REGIME
#    Menggunakan multiplier ATR agar otomatis menyesuaikan volatilitas
# ============================================================

# Regime RANGE (Sideways) — Mean Reversion Bounce
# Target kecil, cepat keluar, SL ketat
RANGE_TP_ATR_MULT = 1.5   # TP = harga_beli + 1.5 × ATR
RANGE_SL_ATR_MULT = 1.0   # SL = harga_beli - 1.0 × ATR

# Regime BULL (Uptrend Kuat) — Trend Following
# Target lebih lebar, SL sedikit lebih longgar karena momentum membantu
BULL_TP_ATR_MULT  = 2.5   # TP = harga_beli + 2.5 × ATR
BULL_SL_ATR_MULT  = 1.2   # SL = harga_beli - 1.2 × ATR

# Fallback persen jika ATR = 0 (sangat jarang)
FALLBACK_TP_PCT = 0.015   # 1.5%
FALLBACK_SL_PCT = 0.010   # 1.0%

# ============================================================
# 5. MARKET REGIME THRESHOLDS
# ============================================================
# Persentase minimum koin yang downtrend agar dianggap BEAR MARKET
BEAR_DOWNTREND_THRESHOLD_PCT = 60   # 60% koin harus downtrend
BEAR_ADX_THRESHOLD           = 35   # Rata-rata ADX harus >= 35

# Persentase minimum koin yang uptrend agar dianggap BULL MARKET
BULL_UPTREND_THRESHOLD_PCT   = 55   # 55% koin harus uptrend

# ============================================================
# 6. BOT INTERVAL
# ============================================================
LOOP_INTERVAL_SECONDS = 60

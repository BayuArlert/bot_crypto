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
SL_COOLDOWN_LOOPS     = 15    # 15 loop jeda setelah SL (lebih konservatif)
BB_PCT_THRESHOLD      = 30    # Lebih ketat: harga harus benar-benar di dekat lower band
AI_MIN_CONFIDENCE     = 8     # Naikkan dari 7 → 8 agar AI lebih selektif

# Filter tambahan untuk presisi entry
BULL_EMA_PROXIMITY    = 1.008 # Harga max 0.8% di ATAS EMA20 (harus benar-benar pullback)
MIN_VOL_RATIO         = 1.0   # Volume minimal setara rata-rata (bukan lesu)

# ============================================================
# 4. TP/SL DINAMIS PER REGIME
#    Menggunakan multiplier ATR agar otomatis menyesuaikan volatilitas
# ============================================================

# Regime RANGE (Sideways) — Mean Reversion Bounce
# Target 2x lebih besar dari SL → RR = 2.5:1
RANGE_TP_ATR_MULT = 2.0   # TP = harga_beli + 2.0 × ATR  (naik dari 1.5)
RANGE_SL_ATR_MULT = 0.8   # SL = harga_beli - 0.8 × ATR  (lebih ketat → RR 2.5:1)

# Regime BULL (Uptrend Kuat) — Trend Following
# Scalping 15m butuh TP yang lebih dekat/realistis agar tidak selalu kena pullback balikan
BULL_TP_ATR_MULT  = 1.8   # TP = harga_beli + 1.8 × ATR  (diturunkan dari 3.0 agar sering hit)
BULL_SL_ATR_MULT  = 1.0   # SL = harga_beli - 1.0 × ATR  (RR 1.8:1)

# Fallback persen jika ATR = 0 (sangat jarang)
FALLBACK_TP_PCT = 0.018   # 1.8%
FALLBACK_SL_PCT = 0.008   # 0.8%

# ============================================================
# 4.5. EXIT RULES (TRAILING & TIMEOUT)
# ============================================================
MAX_HOLD_LOOPS         = 120   # Keluar paksa (cutloss/take profit seadanya) jika posisi > 2 jam (120 menit)
TRAILING_ACTIVATE_MULT = 0.8   # Trailing aktif saat untung 0.8 ATR
TRAILING_LOCK_MULT     = 0.1   # SL dipindah ke +0.1 ATR (Breakeven plus fee)

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

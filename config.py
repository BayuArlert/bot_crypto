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
# 3.5. BIAYA TRADING (FEE)
# ============================================================
# Binance Spot fee standar: 0.1% per sisi (buy + sell = 0.2% round-trip)
# Pakai BNB untuk bayar fee: hemat jadi 0.075%/sisi = 0.15% round-trip
TRADING_FEE_PCT       = 0.001  # 0.1% per sisi (standar tanpa BNB discount)

# ============================================================
# 4. TP/SL DINAMIS PER REGIME
#    Menggunakan multiplier ATR agar otomatis menyesuaikan volatilitas
# ============================================================

# Regime RANGE (Sideways) — Mean Reversion Bounce
# Target 2x lebih besar dari SL → RR = 2.5:1
RANGE_TP_ATR_MULT = 2.0   # TP = harga_beli + 2.0 × ATR  (naik dari 1.5)
RANGE_SL_ATR_MULT = 0.8   # SL = harga_beli - 0.8 × ATR  (lebih ketat → RR 2.5:1)

# Regime BULL (Uptrend Kuat) — Trend Following
# Dinaikkan ke 2.2 agar RR 2.2:1 — cukup aman setelah dipotong fee 0.2%
BULL_TP_ATR_MULT  = 2.2   # TP = harga_beli + 2.2 × ATR  (dinaikkan dari 1.8 → 2.2, RR 2.2:1)
BULL_SL_ATR_MULT  = 1.0   # SL = harga_beli - 1.0 × ATR

# Fallback persen jika ATR = 0 (sangat jarang)
FALLBACK_TP_PCT = 0.018   # 1.8%
FALLBACK_SL_PCT = 0.008   # 0.8%

# ============================================================
# 4.5. EXIT RULES (TRAILING & TIMEOUT)
# ============================================================
MAX_HOLD_LOOPS         = 120   # Keluar paksa (cutloss/take profit seadanya) jika posisi > 2 jam (120 menit)
TRAILING_ACTIVATE_MULT = 0.8   # Trailing aktif saat untung 0.8 ATR
TRAILING_LOCK_MULT     = 0.35  # SL dipindah ke +0.35 ATR (dinaikkan dari 0.1 agar cukup menutupi fee 0.2%)

# ============================================================
# 5. MARKET REGIME THRESHOLDS
# ============================================================
# Persentase minimum koin yang downtrend agar dianggap BEAR MARKET
BEAR_DOWNTREND_THRESHOLD_PCT = 50   # Diturunkan 60→50: 50% koin downtrend sudah cukup bahaya
BEAR_ADX_THRESHOLD           = 30   # Diturunkan 35→30: ADX 30 sudah menunjukkan downtrend bertenaga

# Persentase minimum koin yang uptrend agar dianggap BULL MARKET
BULL_UPTREND_THRESHOLD_PCT   = 55   # 55% koin harus uptrend

# ============================================================
# 6. BOT INTERVAL
# ============================================================
LOOP_INTERVAL_SECONDS = 60

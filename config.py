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

# Dynamic symbol list — top koin by volume
USE_DYNAMIC_SYMBOLS   = True   # True = pakai top N koin by volume, False = pakai SYMBOL_LIST
TOP_N_SYMBOLS         = 30     # Ambil top 30 koin berdasarkan volume 24h
SYMBOL_REFRESH_HOURS  = 24     # Refresh daftar koin setiap 24 jam

TIMEFRAME   = "15m"
MTF_INTERVAL = "1h"

# ============================================================
# 3. RISIKO & MODAL
# ============================================================
BUDGET_PER_TRADE_USDT = 10.0
MAX_OPEN_POSITIONS    = 2
SL_COOLDOWN_LOOPS     = 20    # 20 loop jeda setelah SL (makin konservatif)
BB_PCT_THRESHOLD      = 25    # Lebih ketat: harga wajib di bawah 25% BB (dekat lower band)
AI_MIN_CONFIDENCE     = 8     # AI harus confidence 8+ untuk BUY

# Filter tambahan untuk presisi entry
BULL_EMA_PROXIMITY    = 1.005 # Harga max 0.5% di ATAS EMA20 (benar-benar pullback)
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
# RR 2.8:1 → setelah fee 0.2%, net RR masih 2.5:1
RANGE_TP_ATR_MULT = 2.2   # TP = harga_beli + 2.2 × ATR
RANGE_SL_ATR_MULT = 0.8   # SL = harga_beli - 0.8 × ATR  → RR ≈ 2.75:1

# Regime BULL (Uptrend Kuat) — Trend Following
# RR 2.5:1 → setelah fee, net profit lebih signifikan
BULL_TP_ATR_MULT  = 2.5   # TP = harga_beli + 2.5 × ATR  (naik dari 2.2)
BULL_SL_ATR_MULT  = 1.0   # SL = harga_beli - 1.0 × ATR

# Fallback persen jika ATR = 0 (sangat jarang)
FALLBACK_TP_PCT = 0.020   # 2.0% (naik dari 1.8%)
FALLBACK_SL_PCT = 0.008   # 0.8%

# ============================================================
# 4.5. EXIT RULES (TRAILING & TIMEOUT)
# ============================================================
MAX_HOLD_LOOPS         = 80    # Keluar paksa jika posisi > 80 menit (dari 120 → lebih cepat exit trade macet)
TRAILING_ACTIVATE_MULT = 0.7   # Trailing aktif lebih cepat — saat untung 0.7 ATR (dari 0.8)
TRAILING_LOCK_MULT     = 0.4   # SL dipindah ke +0.4 ATR dari entry (dari 0.35 → lebih aman, di atas fee)

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

import os
from pathlib import Path
from dotenv import load_dotenv

# Selalu baca .env dari folder bot_crypto_v2 (bukan root repo)
_V2_DIR = Path(__file__).resolve().parent
load_dotenv(_V2_DIR / '.env')

# ── API Credentials ──
BINANCE_API_KEY    = os.getenv("BINANCE_API_KEY", "")
BINANCE_SECRET_KEY = os.getenv("BINANCE_SECRET_KEY", "")
GROQ_API_KEY       = os.getenv("GROQ_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_ENABLED   = True   # Set False untuk matikan notifikasi Telegram

# ── Modal & Risiko ──
INITIAL_BALANCE       = 25.0    # modal awal simulasi
BUDGET_PER_TRADE      = 10.0    # budget per trade (tetap $10)
TRADING_FEE_PCT       = 0.001   # 0.1% per sisi
# MAX posisi = floor(saldo / budget), capped 5
MAX_OPEN_POSITIONS    = min(int(INITIAL_BALANCE // BUDGET_PER_TRADE), 5)

# ── TP/SL ──
TP_PCT                = 0.05    # Take profit 5%
SL_PCT                = 0.03    # Stop loss 3%
TRAILING_ACTIVATE_PCT = 0.025   # Trailing aktif saat profit 2.5%
TRAILING_LOCK_PCT     = 0.015   # Lock profit 1.5% saat trailing aktif
MAX_HOLD_MINUTES      = 120     # Force exit setelah 2 jam

# ── Signal Thresholds ──
MIN_VOLUME_SPIKE_RATIO = 2.5    # Naik dari 2.0 setelah backtest fast PF<1
MIN_VOLUME_USDT_1H     = 200_000 # Minimum volume 1h: $200K

SM_MIN_INFLOW_USD      = 20000  # Minimal SM inflow $20K
SM_MIN_TRADERS         = 2      # Minimal 2 SM wallet

SOCIAL_MIN_HYPE_SCORE  = 100
SOCIAL_SENTIMENT       = "Positive"

MIN_SIGNAL_SCORE       = 5      # Minimal 5/10 (backtest fast @4 → PF 0.87)
AI_MIN_CONFIDENCE      = 8      # AI harus confidence 8+ untuk approve entry (naik dari 7)

# ── Universe Koin ──
MIN_QUOTE_VOLUME_24H   = 10_000_000  # Min volume 24h $10M
MAX_SYMBOLS_TO_SCAN    = 50
EXCLUDE_STABLECOINS    = ['USDC', 'BUSD', 'TUSD', 'USDP', 'DAI', 'FDUSD', 'USDE', 'U', 'USDD', 'AEUR']
EXCLUDE_LEVERAGED      = ['UPUSDT', 'DOWNUSDT', 'BULLUSDT', 'BEARUSDT']
# Token pegged/synthetic — volume spike tanpa price change = normal, bukan sinyal
EXCLUDE_PEGGED_PREFIXES = ['XUSD', 'RLUSD', 'USD1', 'EUR', 'GBP', 'PAXG', 'WBTC', 'EURI']

# ── Cache & Refresh ──
SIGNAL_CACHE_SECONDS   = 300    # Cache signal 5 menit
SYMBOL_REFRESH_HOURS   = 6      # Refresh daftar koin setiap 6 jam
LOOP_INTERVAL_SECONDS  = 60     # Loop setiap 60 detik
QUIET_HOURS_UTC        = (22, 3) # Jam sepi: 22:00-03:00 UTC

# ── Cooldown ──
SL_COOLDOWN_MINUTES    = 30     # Cooldown 30 menit setelah SL

# ── Trading mode ──
# paper = virtual balance | testnet | live (Spot API keys required for latter two)
TRADING_MODE           = os.getenv("TRADING_MODE", "paper").lower()
USE_TESTNET            = os.getenv("USE_TESTNET", "true").lower() in ("1", "true", "yes")
# Testnet: scan pakai data mainnet (volume real), order pakai API testnet
TESTNET_USE_MAINNET_DATA = os.getenv("TESTNET_USE_MAINNET_DATA", "true").lower() in ("1", "true", "yes")
REQUIRE_MANUAL_CONFIRM = os.getenv("REQUIRE_MANUAL_CONFIRM", "true").lower() in ("1", "true", "yes")
MAX_DAILY_LOSS_USD     = float(os.getenv("MAX_DAILY_LOSS_USD", "5.0"))

# ── Backtest / paper validation targets (informative) ──
BACKTEST_MIN_PROFIT_FACTOR = 1.2
BACKTEST_MAX_DRAWDOWN_PCT  = 25.0
BACKTEST_MIN_WIN_RATE_PCT  = 40.0

# ── Binance Web3 API Headers ──
BW3_HEADERS = {
    "Content-Type": "application/json",
    "Accept-Encoding": "identity",
    "User-Agent": "binance-web3/2.1 (Skill)"
}

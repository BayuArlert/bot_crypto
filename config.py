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
    'ADAUSDT'   # Cardano
]

# Timeframe yang ditangkap (15m sangat pas untuk napas Scalping cepat)
TIMEFRAME = "15m"

# ============================================================
# 3. RISIKO & MODAL (Mazhab A: Cut Loss Ketat)
# ============================================================
# Bot hanya diizinkan membeli dengan modal statis per koin, 
# Tujuannya agar saldo pecah/terbagi rata jika AI menyuruh beli semua koin di atas.
BUDGET_PER_TRADE_USDT = 20.0  # Contoh: $20 per tembakan beli

STOP_LOSS_PCT   = 0.015 # -1.5% otomatis Cut loss (sangat ketat, cocok untuk day trader)
TAKE_PROFIT_PCT = 0.03  # +3% otomatis Jual Untung (mudah tersentuh dalam hitungan jam)

# ============================================================
# 4. BOT INTERVAL
# ============================================================
# Berapa detik bot mengulang pekerjaannya (Aman untuk CPU & Kuota: 1 Menit)
LOOP_INTERVAL_SECONDS = 60

# Bot Trading v1 (arsip)

Strategi **regime + indikator teknikal** (EMA, ADX, BULL/RANGE/BEAR) + AI portfolio (Groq).

**Status:** Diarsipkan — tidak dikembangkan lagi. Bot aktif ada di [`bot_crypto_v2/`](../../bot_crypto_v2/).

## Isi folder

| File | Fungsi |
|------|--------|
| `bot_binance.py` | Loop utama v1 |
| `backtest.py` | Backtest strategi v1 |
| `config.py` | Konfigurasi v1 |
| `indicators.py` | Indikator & regime |
| `ai_portfolio.py` | Skor & AI entry |
| `dashboard.py` | Dashboard Flask (port legacy) |
| `analytics.py` | Statistik trade |
| `notifier.py` | Telegram |
| `state_manager.py` | State `bot_state.json` |
| `scratch/` | Skrip eksperimen |

## Menjalankan (hanya jika perlu referensi)

```bash
cd archive/bot_v1
pip install -r requirements.txt
cp ../../bot_crypto_v2/.env.example .env   # isi API key sendiri
python bot_binance.py
```

Jalankan dari folder **`archive/bot_v1`** agar import `config`, `indicators`, dll. benar.

State disimpan sebagai `bot_state.json` di folder ini (gitignored).

## Perbedaan dengan v2

| | v1 (arsip) | v2 (aktif) |
|---|------------|------------|
| Sinyal | Indikator lagging + regime | Volume spike Spot + Binance Skills Hub |
| Backtest | `backtest.py` di folder ini | `bot_crypto_v2/backtest.py` |
| Live/Testnet | Paper saja | Paper + executor testnet/live |

Diarsipkan: 2026-05.

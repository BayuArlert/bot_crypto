# Momentum Bot v2

Bot trading Spot (paper / testnet / live) berbasis volume spike + sinyal publik [Binance crypto-market-rank](https://www.binance.com/en/skills/detail/binance-web3/crypto-market-rank).

> Bot v1 (indikator/regime) diarsipkan di [`../archive/bot_v1/`](../archive/bot_v1/) — gunakan **hanya folder ini** untuk trading harian.

## Setup

```bash
cd bot_crypto_v2
pip install -r requirements.txt
cp .env.example .env
# Isi BINANCE_API_KEY, BINANCE_SECRET_KEY, GROQ_API_KEY (opsional Telegram)
```

Jalankan selalu dari folder `bot_crypto_v2` agar state file dan import benar.

## Mode trading

| `TRADING_MODE` | Deskripsi |
|----------------|-----------|
| `paper` (default) | Saldo virtual, tidak ada order |
| `testnet` | Order nyata di [Binance Spot Testnet](https://testnet.binance.vision/) |
| `live` | Mainnet — wajib ketik `CONFIRM` per order jika `REQUIRE_MANUAL_CONFIRM=true` |

**Testnet / live:** saldo = **USDT free dari exchange** (bukan virtual $25). Riwayat trade & cooldown tetap di `bot_state_v2.json`. Scan volume dari **mainnet** jika `TESTNET_USE_MAINNET_DATA=true`.

Env contoh:

```
TRADING_MODE=paper
USE_TESTNET=true
REQUIRE_MANUAL_CONFIRM=true
MAX_DAILY_LOSS_USD=5.0
```

## Alur disarankan

1. **Backtest** — validasi strategi volume + scorer:
   ```bash
   python backtest.py --fast
   python backtest.py
   python backtest.py --bear-gate   # uji filter BEAR opsional
   ```
2. **Tune** — jika profit factor < 1.2 atau drawdown > 25%, naikkan threshold di `config.py`.  
   Hasil `python backtest.py --fast` (BTC/ETH/SOL, 3 bulan):
   - Skor 4 + spike 2.0x → PF 0.87, 149 trade
   - Skor 5 + spike 2.5x → PF 0.97, 34 trade (default saat ini)
   Lanjutkan dengan `python backtest.py` (20 koin, 6 bulan) sebelum paper panjang.
3. **Paper run 2–4 minggu**:
   ```bash
   python main.py
   ```
   Dashboard: http://127.0.0.1:5001  
   Export CSV: `trade_history_v2.csv` (setiap 60 loop)
4. **Testnet** — set `TRADING_MODE=testnet`, API key Testnet, jalankan minimal 1–2 minggu.
5. **Live kecil** — sub-account, IP whitelist, tanpa withdrawal, `TRADING_MODE=live`.

## Kriteria lanjut ke paper panjang

- Backtest: profit factor ≥ 1.2, win rate ≥ 40%, max drawdown ≤ 25%
- Paper: metrik mingguan mendekati backtest (selisih besar = bug atau overfit)

## File penting

| File | Fungsi |
|------|--------|
| `main.py` | Loop utama |
| `backtest.py` | Simulasi historis |
| `config.py` | Threshold & mode |
| `signals/market_rank.py` | API Skills Hub (publik) |
| `signals/volume_scan.py` | Volume spike Spot |
| `core/executor.py` | Order testnet/live |
| `bot_state_v2.json` | State (gitignored) |

## Keamanan

- Jangan commit `.env` atau `bot_state_v2.json`
- API key: read-only untuk paper; trade-only + IP restrict untuk live
- Jangan enable withdrawal pada key bot

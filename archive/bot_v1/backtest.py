"""
Backtest Engine — Validasi strategi menggunakan data historis Binance.
Jalankan: python backtest.py

Menggunakan 4 layer filtering yang 100% identik dengan bot_binance.py:
1. Regime Detection (1h)
2. Pre-filter 9 syarat ketat
3. Scoring deterministik
4. AI_MIN_CONFIDENCE check
"""

import sys
sys.stdout.reconfigure(encoding='utf-8')
import pandas as pd
import numpy as np
from binance.client import Client
from datetime import datetime
from indicators import hitung_indikator, get_market_summary
from ai_portfolio import score_bull_setup, score_range_setup, MIN_SCORE_TO_TRADE
import config

# ============================================================
# KONFIGURASI BACKTEST
# ============================================================
BACKTEST_SYMBOLS  = config.SYMBOL_LIST   # koin yang ditest
BACKTEST_PERIOD   = "12 months ago UTC"  # bisa: "6 months ago UTC", "1 Jan 2024", dll
BACKTEST_INTERVAL = Client.KLINE_INTERVAL_15MINUTE
INITIAL_BALANCE   = 100.0                # modal simulasi backtest
BUDGET_PER_TRADE  = 10.0                 # budget per trade
MAX_POSITIONS     = 2                    # max posisi bersamaan
MIN_SCORE         = MIN_SCORE_TO_TRADE   # skor minimum entry (dari ai_portfolio.py)

# Mode cepat untuk testing — set True untuk test 3 bulan saja
FAST_MODE         = False   
BULL_THRESHOLD_OVERRIDE = None
if FAST_MODE:
    BACKTEST_PERIOD  = "3 months ago UTC"
    BACKTEST_SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']
    BULL_THRESHOLD_OVERRIDE = 0.34
    print("⚡ FAST MODE: 3 bulan, 3 koin")


def fetch_historical_interval(symbol: str, period: str, interval=Client.KLINE_INTERVAL_15MINUTE) -> pd.DataFrame:
    """Fetch data historis dengan interval tertentu."""
    client = Client()
    klines = client.get_historical_klines(symbol, interval, period)
    df = pd.DataFrame(klines, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'qav', 'num_trades',
        'taker_base_vol', 'taker_quote_vol', 'ignore'
    ])
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = pd.to_numeric(df[col])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df.set_index('timestamp')
    return df


def determine_regime(market_snapshot_15m: dict, snapshot_1h: dict) -> str:
    """
    Deteksi regime pakai data 1h untuk trend (lebih stabil dari 15m).
    ADX dari 1h untuk konfirmasi kekuatan trend.
    Identik dengan detect_market_regime() di indicators.py.
    """
    total = len(snapshot_1h)
    if total == 0:
        return 'RANGE'

    uptrend_cnt = sum(1 for d in snapshot_1h.values() if d.get('trend_ema') == 'Strong Uptrend')
    down_cnt    = sum(1 for d in snapshot_1h.values() if d.get('trend_ema') == 'Strong Downtrend')
    adx_vals    = [d.get('adx', 0) for d in snapshot_1h.values() if d.get('adx', 0) > 0]
    avg_adx     = sum(adx_vals) / len(adx_vals) if adx_vals else 0

    uptrend_pct  = uptrend_cnt / total * 100
    down_pct     = down_cnt / total * 100
    
    threshold = BULL_THRESHOLD_OVERRIDE * 100 if BULL_THRESHOLD_OVERRIDE is not None else config.BULL_UPTREND_THRESHOLD_PCT

    if down_pct >= config.BEAR_DOWNTREND_THRESHOLD_PCT and avg_adx >= config.BEAR_ADX_THRESHOLD:
        return 'BEAR'
    elif uptrend_pct >= threshold:
        return 'BULL'
    return 'RANGE'


def filter_bull_candidates(market_snapshot: dict, htf_cache_1h: dict, htf_cache_4h: dict,
                            loop_count: int, sl_cooldown: dict) -> dict:
    """
    Identik dengan BinanceBot._filter_bull_candidates() di bot_binance.py.
    Semua 9 syarat harus terpenuhi sebelum masuk scoring.
    """
    candidates = {}

    for koin, data in market_snapshot.items():
        # [1] Harus dalam uptrend di 15m
        is_uptrend = data.get('trend_ema') == 'Strong Uptrend'

        # [2] RSI zona pullback KETAT (40-55)
        rsi = data.get('rsi', 0)
        is_pullback = 40 <= rsi <= 55

        # [3] Harga harus benar-benar dekat atau di bawah EMA20 (max 0.5% di atas)
        price = data.get('price', 0)
        ema20 = data.get('ema20', price)
        near_ema = price <= ema20 * config.BULL_EMA_PROXIMITY

        # [4] Konfirmasi Momentum Naik & Candle Bullish
        rsi_slope = data.get('rsi_slope', 0)
        is_momentum_up = rsi_slope > 0

        candle_color = data.get('candle_color', 'bearish')
        is_bullish_candle = candle_color == 'bullish'

        # [5] Volume harus lebih dari rata-rata
        has_volume = data.get('vol_ratio', 1.0) >= config.MIN_VOL_RATIO

        # [6] MACD Histogram positif
        is_macd_bullish = data.get('macd_hist', 0) > 0

        # [7] ADX > 20 — tren harus punya tenaga
        has_adx_strength = data.get('adx', 0) > 20

        # [8] Cooldown setelah SL
        loops_since_sl = loop_count - sl_cooldown.get(koin, -999)
        is_on_cooldown = loops_since_sl < config.SL_COOLDOWN_LOOPS

        if not (is_uptrend and is_pullback and near_ema and has_volume and
                is_momentum_up and is_bullish_candle and is_macd_bullish and
                has_adx_strength and not is_on_cooldown):
            continue

        # [9] Konfirmasi MTF 1h dan 4h
        if koin not in htf_cache_1h or koin not in htf_cache_4h:
            continue

        htf_1h_trend = htf_cache_1h[koin][1]
        htf_4h_trend = htf_cache_4h[koin][1]

        if htf_1h_trend == 'Strong Downtrend':
            continue
        if htf_4h_trend == 'Strong Downtrend':
            continue

        data['htf_1h_trend'] = htf_1h_trend
        data['htf_4h_trend'] = htf_4h_trend
        candidates[koin] = data

    return candidates


def filter_range_candidates(market_snapshot: dict, htf_cache_1h: dict, htf_cache_4h: dict,
                             loop_count: int, sl_cooldown: dict) -> dict:
    """
    Identik dengan BinanceBot._filter_range_candidates() di bot_binance.py.
    """
    candidates = {}

    for koin, data in market_snapshot.items():
        # Guard NaN
        if not data.get('stoch_rsi_valid') or not data.get('atr_valid'):
            continue

        rsi              = data.get('rsi', 0)
        stoch_rsi        = data.get('stoch_rsi', 0)
        bb_pct           = data.get('bb_pct', 50)
        vol_ratio        = data.get('vol_ratio', 1.0)
        candle_color     = data.get('candle_color', 'bearish')
        rsi_slope        = data.get('rsi_slope', 0)
        lower_shadow_pct = data.get('lower_shadow_pct', 0)
        adx              = data.get('adx', 0)

        # [1] Oversold KEDUANYA wajib (AND, bukan OR)
        is_oversold = rsi < 38 and stoch_rsi < 25

        # [2] Candle WAJIB bullish
        is_bullish_candle = candle_color == 'bullish'

        # [3] Momentum WAJIB sudah berbalik naik
        is_momentum_up = rsi_slope > 0

        # [4] Harus ada lower shadow / wick bawah
        has_rejection = lower_shadow_pct > 10

        # [5] Blok downtrend kuat
        is_dangerous = (data.get('trend_ema') == 'Strong Downtrend' and adx > 30)

        # [6] ADX tidak boleh terlalu tinggi
        is_ranging = adx < 35

        # [7] Volume setara rata-rata
        has_volume = vol_ratio >= config.MIN_VOL_RATIO

        # [8] Harga harus benar-benar di dekat lower band
        near_lower_band = bb_pct < config.BB_PCT_THRESHOLD

        # [9] Cooldown setelah SL
        loops_since_sl = loop_count - sl_cooldown.get(koin, -999)
        is_on_cooldown = loops_since_sl < config.SL_COOLDOWN_LOOPS

        all_pass = (is_oversold and is_bullish_candle and is_momentum_up and
                    has_rejection and not is_dangerous and is_ranging and
                    has_volume and near_lower_band and not is_on_cooldown)

        if not all_pass:
            continue

        # Konfirmasi MTF 1h dan 4h
        if koin not in htf_cache_1h or koin not in htf_cache_4h:
            continue

        htf_1h_trend = htf_cache_1h[koin][1]
        htf_4h_trend = htf_cache_4h[koin][1]

        if htf_1h_trend == 'Strong Downtrend':
            continue
        if htf_4h_trend == 'Strong Downtrend':
            continue

        data['htf_1h_trend'] = htf_1h_trend
        data['htf_4h_trend'] = htf_4h_trend
        candidates[koin] = data

    return candidates


def run_backtest():
    print("\n" + "="*60)
    print("🔬 BACKTEST ENGINE — Bot Trading Crypto")
    print("="*60)
    print(f"Periode  : {BACKTEST_PERIOD}")
    print(f"Koin     : {BACKTEST_SYMBOLS}")
    print(f"Interval : 15 menit (plus 1h & 4h HTF)")
    print(f"Modal    : ${INITIAL_BALANCE}")
    print(f"Per trade: ${BUDGET_PER_TRADE}")
    print(f"Min score: {MIN_SCORE}/10")
    print("="*60)

    # ── 1. Fetch semua data historis ──
    print("\n📥 Mengambil data historis 15m dari Binance...")
    all_data = {}
    for sym in BACKTEST_SYMBOLS:
        try:
            print(f"  Fetching {sym} 15m...")
            df = fetch_historical_interval(sym, BACKTEST_PERIOD, BACKTEST_INTERVAL)
            df = hitung_indikator(df)
            all_data[sym] = df
        except Exception as e:
            print(f"  ⚠️ Gagal fetch {sym}: {e}")

    # Fetch data 1h untuk HTF confirmation
    print("\n📥 Mengambil data 1h untuk HTF confirmation...")
    all_data_1h = {}
    for sym in BACKTEST_SYMBOLS:
        try:
            df_1h = fetch_historical_interval(sym, BACKTEST_PERIOD, Client.KLINE_INTERVAL_1HOUR)
            all_data_1h[sym] = df_1h
            print(f"  ✅ {sym} 1h: {len(df_1h)} candle")
        except Exception as e:
            print(f"  ⚠️ Gagal fetch {sym} 1h: {e}")

    # Fetch data 4h untuk HTF confirmation
    print("\n📥 Mengambil data 4h untuk HTF confirmation...")
    all_data_4h = {}
    for sym in BACKTEST_SYMBOLS:
        try:
            df_4h = fetch_historical_interval(sym, BACKTEST_PERIOD, Client.KLINE_INTERVAL_4HOUR)
            all_data_4h[sym] = df_4h
            print(f"  ✅ {sym} 4h: {len(df_4h)} candle")
        except Exception as e:
            print(f"  ⚠️ Gagal fetch {sym} 4h: {e}")

    if not all_data:
        print("❌ Tidak ada data. Periksa koneksi internet.")
        return

    # ── 2. Align semua candle ke index yang sama ──
    ref_sym   = list(all_data.keys())[0]
    ref_index = all_data[ref_sym].index
    min_candles = 60  # minimal candle untuk indikator stabil

    # ── 3. Inisialisasi variabel simulasi ──
    balance       = INITIAL_BALANCE
    positions     = {}
    trades        = []
    sl_cooldown   = {}
    loop_count    = 0
    regime_counts = {}

    print(f"\n🔄 Simulasi {len(ref_index)} candle...")
    
    total_candles = len(ref_index) - min_candles
    checkpoint = total_candles // 10  # print setiap 10%
    if checkpoint == 0: checkpoint = 1

    htf_cache_1h = {}  # sym: (last_hour, trend, adx)
    htf_cache_4h = {}  # sym: (last_4h_block, trend)

    for i in range(min_candles, len(ref_index)):
        candle_time = ref_index[i]
        loop_count += 1

        # Progress update setiap 10%
        progress = i - min_candles
        if progress > 0 and progress % checkpoint == 0:
            pct = progress / total_candles * 100
            open_pos = len(positions)
            total_trades_so_far = len(trades)
            print(f"   [{pct:.0f}%] Candle {i}/{len(ref_index)} | "
                  f"Trade: {total_trades_so_far} | Posisi: {open_pos} | "
                  f"Saldo: ${balance:.2f}")

        # Buat market_state snapshot di candle ke-i
        market_snapshot = {}
        for sym, df in all_data.items():
            df_slice = df.iloc[:i+1]
            if len(df_slice) < min_candles:
                continue
            try:
                summary = get_market_summary(df_slice)
                market_snapshot[sym] = summary
            except Exception:
                continue

        if not market_snapshot:
            continue

        # Proses HTF Cache dan Lookup
        current_hour = candle_time.floor('1h')
        current_4h   = candle_time.floor('4h')

        for sym, data in market_snapshot.items():
            # Cache 1h
            if sym not in htf_cache_1h or htf_cache_1h[sym][0] != current_hour:
                htf_1h_trend = 'Sideways / Choppy'
                adx_1h = 0
                if sym in all_data_1h:
                    df_1h_sym = all_data_1h[sym]
                    past_1h = df_1h_sym[df_1h_sym.index <= candle_time]
                    if len(past_1h) >= 52:
                        try:
                            past_1h_ind = hitung_indikator(past_1h.iloc[-60:])
                            summary_1h = get_market_summary(past_1h_ind)
                            htf_1h_trend = summary_1h['trend_ema']
                            adx_1h = summary_1h.get('adx', 0)
                        except Exception:
                            pass
                htf_cache_1h[sym] = (current_hour, htf_1h_trend, adx_1h)
                
            # Cache 4h
            if sym not in htf_cache_4h or htf_cache_4h[sym][0] != current_4h:
                htf_4h_trend = 'Sideways / Choppy'
                if sym in all_data_4h:
                    df_4h_sym = all_data_4h[sym]
                    past_4h = df_4h_sym[df_4h_sym.index <= candle_time]
                    if len(past_4h) >= 52:
                        try:
                            past_4h_ind = hitung_indikator(past_4h.iloc[-60:])
                            summary_4h = get_market_summary(past_4h_ind)
                            htf_4h_trend = summary_4h['trend_ema']
                        except Exception:
                            pass
                htf_cache_4h[sym] = (current_4h, htf_4h_trend)

        # ── Cek TP/SL untuk posisi yang sedang open ──
        for sym in list(positions.keys()):
            if sym not in all_data:
                continue
            df_sym = all_data[sym]
            if i >= len(df_sym):
                continue

            candle  = df_sym.iloc[i]
            pos     = positions[sym]
            high    = candle['high']
            low     = candle['low']
            close   = candle['close']
            atr     = pos.get('atr', 0)

            # Trailing stop
            if not pos.get('trailing_active') and atr > 0:
                if close >= pos['buy_price'] + (config.TRAILING_ACTIVATE_MULT * atr):
                    new_sl = pos['buy_price'] + (config.TRAILING_LOCK_MULT * atr)
                    if new_sl > pos['sl']:
                        pos['sl'] = new_sl
                        pos['trailing_active'] = True

            # Timeout setelah MAX_HOLD_LOOPS candle
            hold_duration = loop_count - pos['entry_idx']
            if hold_duration > config.MAX_HOLD_LOOPS:
                pnl_pct = (close - pos['buy_price']) / pos['buy_price']
                pnl_usdt = pnl_pct * BUDGET_PER_TRADE - (BUDGET_PER_TRADE * config.TRADING_FEE_PCT * 2)
                balance += BUDGET_PER_TRADE + pnl_usdt
                trades.append({
                    'symbol': sym, 'strategy': pos['strategy'], 'regime': pos.get('regime', 'UNKNOWN'),
                    'type': 'TIME_TP' if pnl_usdt > 0 else 'TIME_SL',
                    'entry': pos['buy_price'], 'exit': close,
                    'pnl': round(pnl_usdt, 4), 'time': candle_time,
                    'hold_candles': hold_duration
                })
                del positions[sym]
                if pnl_usdt <= 0:
                    sl_cooldown[sym] = loop_count
                continue

            # Cek TP dulu (optimistis: high menyentuh TP)
            if high >= pos['tp']:
                fee = BUDGET_PER_TRADE * config.TRADING_FEE_PCT * 2
                profit = ((pos['tp'] - pos['buy_price']) / pos['buy_price']) * BUDGET_PER_TRADE - fee
                balance += BUDGET_PER_TRADE + profit
                trades.append({
                    'symbol': sym, 'strategy': pos['strategy'], 'regime': pos.get('regime', 'UNKNOWN'),
                    'type': 'TP', 'entry': pos['buy_price'],
                    'exit': pos['tp'], 'pnl': round(profit, 4),
                    'time': candle_time, 'hold_candles': hold_duration
                })
                del positions[sym]

            # Cek SL (low menyentuh SL)
            elif low <= pos['sl']:
                fee = BUDGET_PER_TRADE * config.TRADING_FEE_PCT * 2
                loss = ((pos['buy_price'] - pos['sl']) / pos['buy_price']) * BUDGET_PER_TRADE + fee
                balance += BUDGET_PER_TRADE - loss
                sl_cooldown[sym] = loop_count
                trades.append({
                    'symbol': sym, 'strategy': pos['strategy'], 'regime': pos.get('regime', 'UNKNOWN'),
                    'type': 'SL', 'entry': pos['buy_price'],
                    'exit': pos['sl'], 'pnl': round(-loss, 4),
                    'time': candle_time, 'hold_candles': hold_duration
                })
                del positions[sym]

        # ── LAYER 1: Regime Detection (pakai 1h, bukan 15m) ──
        snapshot_1h_now = {}
        for sym in market_snapshot.keys():
            if sym in htf_cache_1h:
                cached = htf_cache_1h[sym]
                snapshot_1h_now[sym] = {'trend_ema': cached[1], 'adx': cached[2]}

        regime = determine_regime(market_snapshot, snapshot_1h_now)

        # Catat distribusi regime
        if regime not in regime_counts:
            regime_counts[regime] = 0
        regime_counts[regime] += 1

        # ── BEAR: Tidak ada entry, hanya monitor posisi aktif ──
        if regime == 'BEAR':
            continue

        # ── Tidak bisa entry jika posisi sudah penuh ──
        if len(positions) >= MAX_POSITIONS:
            continue

        # ── LAYER 2: Pre-filter berdasarkan regime ──
        if regime == 'BULL':
            candidates = filter_bull_candidates(
                market_snapshot, htf_cache_1h, htf_cache_4h,
                loop_count, sl_cooldown
            )
        else:  # RANGE
            candidates = filter_range_candidates(
                market_snapshot, htf_cache_1h, htf_cache_4h,
                loop_count, sl_cooldown
            )

        if not candidates:
            continue

        # ── LAYER 3: Scoring deterministik ──
        scored = []
        for sym, data in candidates.items():
            if sym in positions:
                continue
            if sym in sl_cooldown and (loop_count - sl_cooldown[sym]) < config.SL_COOLDOWN_LOOPS:
                continue

            if regime == 'BULL':
                score, _ = score_bull_setup(data)
            else:
                score, _ = score_range_setup(data)

            if score >= MIN_SCORE:
                scored.append((sym, score, data))

        if not scored:
            continue

        # Ambil kandidat terbaik
        scored.sort(key=lambda x: x[1], reverse=True)
        sym, score, data = scored[0]

        # ── LAYER 4: AI_MIN_CONFIDENCE check ──
        if score < config.AI_MIN_CONFIDENCE:
            continue

        # ── Entry ──
        if balance < BUDGET_PER_TRADE:
            continue

        entry_price = data['price']
        atr         = data.get('atr', 0)
        strategy    = 'BULL-Pullback' if regime == 'BULL' else 'RANGE-Bounce'

        if atr > 0:
            if regime == 'BULL':
                tp = entry_price + config.BULL_TP_ATR_MULT * atr
                sl = entry_price - config.BULL_SL_ATR_MULT * atr
            else:
                tp = entry_price + config.RANGE_TP_ATR_MULT * atr
                sl = entry_price - config.RANGE_SL_ATR_MULT * atr
        else:
            tp = entry_price * (1 + config.FALLBACK_TP_PCT)
            sl = entry_price * (1 - config.FALLBACK_SL_PCT)

        balance -= BUDGET_PER_TRADE
        positions[sym] = {
            'buy_price':      entry_price,
            'tp':             tp,
            'sl':             sl,
            'strategy':       strategy,
            'regime':         regime,
            'entry_idx':      loop_count,
            'score':          score,
            'trailing_active': False,
            'atr':            atr,
        }

    # ── 4. Tutup semua posisi yang masih open di akhir ──
    last_candle_time = ref_index[-1]
    for sym, pos in positions.items():
        if sym in all_data:
            close = all_data[sym].iloc[-1]['close']
            fee   = BUDGET_PER_TRADE * config.TRADING_FEE_PCT * 2
            pnl   = ((close - pos['buy_price']) / pos['buy_price']) * BUDGET_PER_TRADE - fee
            balance += BUDGET_PER_TRADE + pnl
            trades.append({
                'symbol': sym, 'strategy': pos['strategy'], 'regime': pos.get('regime', 'UNKNOWN'),
                'type': 'OPEN_CLOSE', 'entry': pos['buy_price'],
                'exit': close, 'pnl': round(pnl, 4),
                'time': last_candle_time, 'hold_candles': loop_count - pos['entry_idx']
            })

    # ── 5. Hitung dan tampilkan hasil ──
    print_backtest_result(trades, INITIAL_BALANCE, balance, regime_counts)


def print_backtest_result(trades: list, initial: float, final: float, regime_counts: dict):
    """Print hasil backtest dalam format lengkap."""
    
    print(f"\n--- Distribusi Regime (dari {sum(regime_counts.values())} candle aktif) ---")
    for r, count in sorted(regime_counts.items()):
        pct = count / sum(regime_counts.values()) * 100 if sum(regime_counts.values()) > 0 else 0
        print(f"  {r:6s} : {count:5d} candle ({pct:.1f}%)")
            
    if not trades:
        print("\n❌ Tidak ada trade yang terjadi selama periode backtest.")
        print("   Kemungkinan: filter 4 lapis sangat ketat dan memblokir semua sinyal kotor.")
        return

    wins   = [t for t in trades if t['pnl'] > 0]
    losses = [t for t in trades if t['pnl'] <= 0]

    win_rate     = len(wins) / len(trades) * 100
    gross_profit = sum(t['pnl'] for t in wins)
    gross_loss   = abs(sum(t['pnl'] for t in losses))
    net_pnl      = final - initial
    pf           = gross_profit / gross_loss if gross_loss > 0 else float('inf')
    avg_hold     = sum(t['hold_candles'] for t in trades) / len(trades)

    # Max drawdown
    equity = initial
    peak   = initial
    max_dd = 0
    for t in trades:
        equity += t['pnl']
        peak    = max(peak, equity)
        dd      = (peak - equity) / peak * 100
        max_dd  = max(max_dd, dd)

    # Per strategi
    strat_stats = {}
    for t in trades:
        s = t['strategy']
        if s not in strat_stats:
            strat_stats[s] = {'wins': 0, 'losses': 0, 'pnl': 0}
        if t['pnl'] > 0:
            strat_stats[s]['wins'] += 1
        else:
            strat_stats[s]['losses'] += 1
        strat_stats[s]['pnl'] += t['pnl']

    print("\n" + "="*60)
    print("📊  HASIL BACKTEST")
    print("="*60)
    print(f"Modal Awal     : ${initial:.2f}")
    print(f"Modal Akhir    : ${final:.2f}")
    print(f"Net PnL        : ${net_pnl:+.2f} ({net_pnl/initial*100:+.1f}%)")
    print(f"Total Trade    : {len(trades)}")
    print(f"Win Rate       : {win_rate:.1f}%  ({len(wins)}W / {len(losses)}L)")
    print(f"Profit Factor  : {pf:.2f}" if pf != float('inf') else f"Profit Factor  : ∞")
    print(f"Avg Hold       : {avg_hold:.0f} candle ({avg_hold*15/60:.1f} jam)")
    print(f"Max Drawdown   : {max_dd:.1f}%")
    print(f"\n--- Per Strategi ---")
    for s, st in strat_stats.items():
        total = st['wins'] + st['losses']
        wr    = st['wins'] / total * 100 if total > 0 else 0
        print(f"  {s:20s} | {total} trade | WR {wr:.0f}% | PnL ${st['pnl']:+.2f}")
        
    print(f"\n--- Distribusi Regime saat Entry ---")
    regime_stats = {}
    for t in trades:
        r = t.get('regime', 'UNKNOWN')
        if r not in regime_stats:
            regime_stats[r] = {'wins': 0, 'losses': 0, 'pnl': 0}
        if t['pnl'] > 0:
            regime_stats[r]['wins'] += 1
        else:
            regime_stats[r]['losses'] += 1
        regime_stats[r]['pnl'] += t['pnl']

    for r, rs in regime_stats.items():
        total = rs['wins'] + rs['losses']
        wr = rs['wins'] / total * 100 if total > 0 else 0
        print(f"  {r:8s} | {total} trade | WR {wr:.0f}% | PnL ${rs['pnl']:+.2f}")

    print(f"\n--- 10 Trade Terakhir ---")
    for t in trades[-10:]:
        sign = '+' if t['pnl'] > 0 else ''
        print(f"  {str(t['time'])[:16]} | {t['symbol']:10s} | {t['type']:8s} | {sign}${t['pnl']:.2f}")
    print("="*60)


if __name__ == "__main__":
    run_backtest()

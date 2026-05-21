"""
Backtest Engine v2 — validasi strategi momentum (volume + scorer).
Mode A: volume + scorer deterministik (tanpa SM/hype/AI).
Mode B: + optional regime gate BEAR dari v1 (USE_BEAR_GATE).

Jalankan dari folder bot_crypto_v2:
  python backtest.py
  python backtest.py --fast
"""
import sys
import os
import argparse

sys.stdout.reconfigure(encoding='utf-8')
# Pastikan import dari folder v2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timezone, timedelta
from binance.client import Client

import config
from signals.volume_scan import volume_spike_from_klines, get_active_usdt_symbols
from core.scorer import score_opportunity
from core.risk import calc_tp_sl, check_trailing_stop, parse_time
from utils.analytics import calculate_stats, print_report

# ── Backtest settings (override via CLI) ──
BACKTEST_PERIOD       = "6 months ago UTC"
BACKTEST_SYMBOLS_MAX  = 20
FAST_MODE_SYMBOLS     = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']
FAST_MODE_PERIOD      = "3 months ago UTC"
USE_BEAR_GATE         = False   # set True untuk uji regime filter v1


class BacktestPortfolio:
    """Portfolio simulator dengan logika exit sama production."""

    def __init__(self, initial_balance: float):
        self.balance     = initial_balance
        self.positions   = {}
        self.history     = []
        self.sl_cooldown = {}

    def can_open(self, symbol: str, max_positions: int, budget: float) -> bool:
        if symbol in self.positions:
            return False
        if len(self.positions) >= max_positions:
            return False
        if self.balance < budget:
            return False
        from core.risk import is_sl_cooldown
        if is_sl_cooldown(symbol, self.sl_cooldown):
            return False
        return True

    def open(self, symbol: str, price: float, score: int, entry_time: datetime):
        tp, sl = calc_tp_sl(price)
        self.balance -= config.BUDGET_PER_TRADE
        self.positions[symbol] = {
            'symbol':          symbol,
            'buy_price':       price,
            'tp_price':        tp,
            'sl_price':        sl,
            'score':           score,
            'trailing_active': False,
            'entry_time':      entry_time.isoformat(),
        }

    def check_bar(self, symbol: str, high: float, low: float, close: float,
                  bar_time: datetime) -> dict | None:
        if symbol not in self.positions:
            return None

        pos = self.positions[symbol]
        pos = check_trailing_stop(pos, close)

        exit_reason = None
        exit_price  = close

        if high >= pos['tp_price']:
            exit_reason = 'TP'
            exit_price  = pos['tp_price']
        elif low <= pos['sl_price']:
            exit_reason = 'SL'
            exit_price  = low
        else:
            entry_dt = parse_time(pos.get('entry_time'))
            if entry_dt:
                hold_min = (bar_time - entry_dt).total_seconds() / 60
                if hold_min > config.MAX_HOLD_MINUTES:
                    exit_reason = 'TIMEOUT'
                    exit_price  = close

        if not exit_reason:
            return None

        entry      = pos['buy_price']
        pct_change = (exit_price - entry) / entry
        gross_pnl  = pct_change * config.BUDGET_PER_TRADE
        fee        = config.BUDGET_PER_TRADE * config.TRADING_FEE_PCT * 2
        net_pnl    = gross_pnl - fee
        self.balance += config.BUDGET_PER_TRADE + net_pnl

        if exit_reason == 'SL' or (exit_reason == 'TIMEOUT' and net_pnl < 0):
            self.sl_cooldown[symbol] = bar_time.isoformat()

        trade = {
            'symbol':     symbol,
            'type':       exit_reason,
            'buy_price':  entry,
            'exit_price': exit_price,
            'pnl':        round(net_pnl, 2),
            'pnl_pct':    round(pct_change * 100, 2),
            'score':      pos['score'],
            'time':       bar_time.strftime('%d/%m %H:%M'),
        }
        self.history.append(trade)
        del self.positions[symbol]
        return trade


def _fetch_klines(client: Client, symbol: str, period: str) -> list:
    return client.get_historical_klines(
        symbol, Client.KLINE_INTERVAL_1HOUR, period)


def _detect_bear_gate(client: Client, symbols: list[str], bar_time_ms: int) -> bool:
    """
    Simplified BEAR gate: jika >40% sample koin 1h trend down kuat, skip new entries.
    """
    if not USE_BEAR_GATE:
        return False
    sample = symbols[:10]
    down = 0
    total = 0
    for sym in sample:
        try:
            klines = client.get_klines(
                symbol=sym, interval=Client.KLINE_INTERVAL_1HOUR,
                limit=30, endTime=bar_time_ms)
            if len(klines) < 5:
                continue
            o = float(klines[-2][1])
            c = float(klines[-2][4])
            if o > 0 and (c - o) / o < -0.01:
                down += 1
            total += 1
        except Exception:
            continue
    return total > 0 and (down / total) >= 0.4


def run_backtest(fast: bool = False) -> dict:
    client = Client(config.BINANCE_API_KEY, config.BINANCE_SECRET_KEY)
    period = FAST_MODE_PERIOD if fast else BACKTEST_PERIOD

    if fast:
        symbols = FAST_MODE_SYMBOLS
        print(f"FAST MODE: {len(symbols)} koin, {period}")
    else:
        symbols = get_active_usdt_symbols(client)[:BACKTEST_SYMBOLS_MAX]
        print(f"Backtest: {len(symbols)} koin, {period}")

    portfolio = BacktestPortfolio(config.INITIAL_BALANCE)
    max_pos   = config.MAX_OPEN_POSITIONS
    signals   = 0

    for sym in symbols:
        try:
            klines = _fetch_klines(client, sym, period)
        except Exception as e:
            print(f"   Skip {sym}: {e}")
            continue
        if len(klines) < 30:
            continue

        print(f"   Simulasi {sym} ({len(klines)} bars)...")

        for i in range(24, len(klines)):
            candle   = klines[i]
            bar_ms   = int(candle[0])
            bar_time = datetime.fromtimestamp(bar_ms / 1000, tz=timezone.utc)
            high     = float(candle[2])
            low      = float(candle[3])
            close    = float(candle[4])

            portfolio.check_bar(sym, high, low, close, bar_time)

            if not portfolio.can_open(sym, max_pos, config.BUDGET_PER_TRADE):
                continue

            if _detect_bear_gate(client, symbols, bar_ms):
                continue

            vol_data = volume_spike_from_klines(sym, klines, i)
            if vol_data is None:
                continue
            if not vol_data['is_spike']:
                continue
            if vol_data['current_volume_1h'] < config.MIN_VOLUME_USDT_1H:
                continue

            score, _reasons = score_opportunity(
                symbol=sym,
                volume_data=vol_data,
                in_sm_inflow=False,
                sm_inflow_usd=0,
                sm_traders=0,
                in_social_hype=False,
                hype_score=0,
                in_trending=False,
            )

            if score < config.MIN_SIGNAL_SCORE:
                continue

            entry_price = vol_data['price']
            portfolio.open(sym, entry_price, score, bar_time)
            signals += 1

    stats = calculate_stats(portfolio.history, config.INITIAL_BALANCE)
    stats['final_balance'] = round(portfolio.balance, 2)
    stats['open_positions'] = len(portfolio.positions)
    stats['signals_taken']  = signals
    return stats


def main():
    parser = argparse.ArgumentParser(description='Backtest Momentum Bot v2')
    parser.add_argument('--fast', action='store_true', help='3 bulan, 3 koin')
    parser.add_argument('--bear-gate', action='store_true',
                        help='Aktifkan filter BEAR sederhana')
    args = parser.parse_args()

    global USE_BEAR_GATE
    if args.bear_gate:
        USE_BEAR_GATE = True

    print("=" * 50)
    print("BACKTEST v2 — Volume + Scorer (no AI / no SM)")
    print("=" * 50)
    print(f"  MIN_SIGNAL_SCORE     = {config.MIN_SIGNAL_SCORE}")
    print(f"  MIN_VOLUME_SPIKE     = {config.MIN_VOLUME_SPIKE_RATIO}x")
    print(f"  TP/SL                = {config.TP_PCT*100:.0f}% / {config.SL_PCT*100:.0f}%")
    print(f"  MAX_HOLD             = {config.MAX_HOLD_MINUTES} min")
    print(f"  BEAR gate            = {USE_BEAR_GATE}")
    print("=" * 50)

    stats = run_backtest(fast=args.fast)
    print_report(stats)

    if stats.get('total', 0) > 0:
        final = stats.get('final_balance', config.INITIAL_BALANCE)
        print(f"\n  Saldo akhir simulasi : ${final:.2f}")
        print(f"  Sinyal entry         : {stats.get('signals_taken', 0)}")
        pf = stats.get('profit_factor', 0)
        wr = stats.get('win_rate', 0)
        dd = stats.get('max_drawdown', 0)
        if (pf >= config.BACKTEST_MIN_PROFIT_FACTOR
                and wr >= config.BACKTEST_MIN_WIN_RATE_PCT
                and dd <= config.BACKTEST_MAX_DRAWDOWN_PCT):
            print("  ✅ Kriteria paper-run terpenuhi (PF>1.2, WR>=40%, DD<=25%)")
        else:
            print("  ⚠️ Belum memenuhi kriteria — pertimbangkan naikkan MIN_SIGNAL_SCORE")
    else:
        print("\n  Tidak ada trade — longgarkan threshold atau perpanjang periode.")


if __name__ == '__main__':
    main()

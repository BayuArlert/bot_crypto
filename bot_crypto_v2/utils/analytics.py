"""
Analytics — hitung dan cetak statistik performa trading.
"""
import csv
import os

import config

HISTORY_CSV = "trade_history_v2.csv"


def calculate_stats(history: list[dict], initial_balance: float = None) -> dict:
    """Hitung statistik lengkap dari history trades."""
    initial = initial_balance or config.INITIAL_BALANCE
    if not history:
        return {'total': 0}

    wins   = [t for t in history if t.get('pnl', 0) > 0]
    losses = [t for t in history if t.get('pnl', 0) <= 0]

    win_rate    = len(wins) / len(history) * 100 if history else 0
    gross_profit = sum(t['pnl'] for t in wins)
    gross_loss   = abs(sum(t['pnl'] for t in losses))
    net_pnl      = sum(t['pnl'] for t in history)
    pf           = gross_profit / gross_loss if gross_loss > 0 else float('inf')

    # Max drawdown (running equity dari initial)
    equity = initial
    peak   = initial
    max_dd = 0.0
    for t in reversed(history):  # history disimpan reversed (newest first)
        equity += t['pnl']
        peak    = max(peak, equity)
        dd      = (peak - equity) / peak * 100
        max_dd  = max(max_dd, dd)

    # Win streak / loss streak
    best_streak  = 0
    worst_streak = 0
    cur_streak   = 0
    for t in reversed(history):
        if t['pnl'] > 0:
            cur_streak = max(cur_streak + 1, 1) if cur_streak >= 0 else 1
        else:
            cur_streak = min(cur_streak - 1, -1) if cur_streak <= 0 else -1
        best_streak  = max(best_streak, cur_streak)
        worst_streak = min(worst_streak, cur_streak)

    # Per-type breakdown
    type_stats: dict[str, dict] = {}
    for t in history:
        tp = t.get('type', 'UNKNOWN')
        if tp not in type_stats:
            type_stats[tp] = {'count': 0, 'pnl': 0.0}
        type_stats[tp]['count'] += 1
        type_stats[tp]['pnl']   += t.get('pnl', 0)

    return {
        'total':        len(history),
        'wins':         len(wins),
        'losses':       len(losses),
        'win_rate':     round(win_rate, 1),
        'net_pnl':      round(net_pnl, 2),
        'gross_profit': round(gross_profit, 2),
        'gross_loss':   round(gross_loss, 2),
        'profit_factor': round(pf, 2) if pf != float('inf') else 9999,
        'max_drawdown': round(max_dd, 1),
        'best_streak':  best_streak,
        'worst_streak': worst_streak,
        'type_stats':   type_stats,
    }


def export_history_csv(history: list[dict],
                       path: str = HISTORY_CSV) -> None:
    """Export riwayat trade ke CSV untuk analisis paper run."""
    if not history:
        return
    fields = ['time', 'symbol', 'type', 'buy_price', 'exit_price',
              'pnl', 'pnl_pct', 'score']
    try:
        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
            writer.writeheader()
            for t in history:
                writer.writerow(t)
        print(f"   [Analytics] History exported → {path} ({len(history)} trades)")
    except Exception as e:
        print(f"   [Analytics] CSV export error: {e}")


def print_report(stats: dict) -> None:
    """Cetak laporan statistik ke terminal."""
    if stats.get('total', 0) == 0:
        print("   [Analytics] Belum ada trade.")
        return

    print("\n" + "─" * 50)
    print(f"📊  ANALYTICS REPORT ({stats['total']} trade)")
    print("─" * 50)
    print(f"  Win Rate      : {stats['win_rate']}%  "
          f"({stats['wins']}W / {stats['losses']}L)")
    print(f"  Net PnL       : ${stats['net_pnl']:+.2f}")
    print(f"  Profit Factor : {stats['profit_factor']:.2f}")
    print(f"  Max Drawdown  : {stats['max_drawdown']}%")
    print(f"  Best Streak   : {stats['best_streak']} | "
          f"Worst: {stats['worst_streak']}")

    if stats.get('type_stats'):
        print(f"  Per tipe exit:")
        for tp, ts in stats['type_stats'].items():
            print(f"    {tp:8s}: {ts['count']} trade | PnL ${ts['pnl']:+.2f}")
    print("─" * 50)

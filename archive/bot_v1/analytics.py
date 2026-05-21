"""
Performance Analytics — Hitung statistik performa trading yang komprehensif.
Dipanggil dari bot untuk generate laporan performa.
"""
from datetime import datetime


def calculate_stats(trade_history: list, initial_balance: float = 25.0) -> dict:
    """
    Hitung statistik lengkap dari trade_history.
    
    Returns dict berisi semua metrik performa.
    """
    if not trade_history:
        return {'error': 'Belum ada trade'}

    profits = [t['pnl'] for t in trade_history if t['pnl'] > 0]
    losses  = [t['pnl'] for t in trade_history if t['pnl'] <= 0]

    total_trades  = len(trade_history)
    total_wins    = len(profits)
    total_losses  = len(losses)
    win_rate      = (total_wins / total_trades * 100) if total_trades > 0 else 0

    gross_profit  = sum(profits) if profits else 0
    gross_loss    = abs(sum(losses)) if losses else 0
    net_pnl       = gross_profit - gross_loss
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float('inf')

    avg_profit    = (gross_profit / total_wins)   if total_wins   > 0 else 0
    avg_loss      = (gross_loss   / total_losses) if total_losses > 0 else 0
    avg_rr        = (avg_profit   / avg_loss)     if avg_loss     > 0 else 0

    # Max drawdown — tracking equity curve
    equity = initial_balance
    peak   = initial_balance
    max_dd = 0
    for t in reversed(trade_history):  # reversed karena insert(0,...)
        equity += t['pnl']
        if equity > peak:
            peak = equity
        dd = (peak - equity) / peak * 100
        if dd > max_dd:
            max_dd = dd

    # Statistik per strategi
    strategies = {}
    for t in trade_history:
        strat = t.get('strategy', 'Unknown')
        if strat not in strategies:
            strategies[strat] = {'wins': 0, 'losses': 0, 'pnl': 0}
        if t['pnl'] > 0:
            strategies[strat]['wins'] += 1
        else:
            strategies[strat]['losses'] += 1
        strategies[strat]['pnl'] += t['pnl']

    strat_stats = {}
    for strat, s in strategies.items():
        total = s['wins'] + s['losses']
        strat_stats[strat] = {
            'trades':   total,
            'win_rate': round(s['wins'] / total * 100, 1) if total > 0 else 0,
            'net_pnl':  round(s['pnl'], 2),
        }

    # Statistik per koin
    coins = {}
    for t in trade_history:
        sym = t.get('symbol', 'Unknown')
        if sym not in coins:
            coins[sym] = {'wins': 0, 'losses': 0, 'pnl': 0}
        if t['pnl'] > 0:
            coins[sym]['wins'] += 1
        else:
            coins[sym]['losses'] += 1
        coins[sym]['pnl'] += t['pnl']

    coin_stats = {}
    for sym, c in coins.items():
        total = c['wins'] + c['losses']
        coin_stats[sym] = {
            'trades':   total,
            'win_rate': round(c['wins'] / total * 100, 1) if total > 0 else 0,
            'net_pnl':  round(c['pnl'], 2),
        }

    # Exit type breakdown
    exit_types = {}
    for t in trade_history:
        et = t.get('type', 'Unknown')
        exit_types[et] = exit_types.get(et, 0) + 1

    return {
        'total_trades':   total_trades,
        'win_rate':       round(win_rate, 1),
        'total_wins':     total_wins,
        'total_losses':   total_losses,
        'gross_profit':   round(gross_profit, 2),
        'gross_loss':     round(gross_loss, 2),
        'net_pnl':        round(net_pnl, 2),
        'profit_factor':  round(profit_factor, 2) if profit_factor != float('inf') else '∞',
        'avg_profit':     round(avg_profit, 2),
        'avg_loss':       round(avg_loss, 2),
        'avg_rr':         round(avg_rr, 2),
        'max_drawdown_pct': round(max_dd, 1),
        'per_strategy':   strat_stats,
        'per_coin':       coin_stats,
        'exit_types':     exit_types,
        'generated_at':   datetime.now().strftime('%d/%m/%Y %H:%M'),
    }


def print_report(stats: dict):
    """Print laporan performa ke console dalam format yang mudah dibaca."""
    if 'error' in stats:
        print(f"[ANALYTICS] {stats['error']}")
        return

    print("\n" + "="*55)
    print("📊  PERFORMANCE REPORT")
    print("="*55)
    print(f"Total Trade    : {stats['total_trades']}")
    print(f"Win Rate       : {stats['win_rate']}%  ({stats['total_wins']}W / {stats['total_losses']}L)")
    print(f"Net PnL        : ${stats['net_pnl']:.2f}")
    print(f"Profit Factor  : {stats['profit_factor']}")
    print(f"Avg Profit     : +${stats['avg_profit']:.2f}")
    print(f"Avg Loss       : -${stats['avg_loss']:.2f}")
    print(f"Avg RR Aktual  : {stats['avg_rr']:.2f}:1")
    print(f"Max Drawdown   : {stats['max_drawdown_pct']}%")
    print(f"\n--- Per Strategi ---")
    for strat, s in stats['per_strategy'].items():
        print(f"  {strat:20s} | {s['trades']} trade | WR {s['win_rate']}% | PnL ${s['net_pnl']:.2f}")
    print(f"\n--- Per Koin (top PnL) ---")
    sorted_coins = sorted(stats['per_coin'].items(), key=lambda x: x[1]['net_pnl'], reverse=True)
    for sym, c in sorted_coins[:10]:
        print(f"  {sym:12s} | {c['trades']} trade | WR {c['win_rate']}% | PnL ${c['net_pnl']:.2f}")
    print(f"\n--- Exit Type Breakdown ---")
    for et, count in stats['exit_types'].items():
        print(f"  {et:12s} : {count}")
    print(f"\nGenerated: {stats['generated_at']}")
    print("="*55 + "\n")

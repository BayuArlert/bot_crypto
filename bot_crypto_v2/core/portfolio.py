"""
Portfolio Manager — manajemen posisi aktif dan trade history.
Paper: saldo virtual. Testnet/live: saldo dari exchange (USDT free).
"""
import config
from datetime import datetime, timezone
from binance.client import Client
from core.risk import calc_tp_sl, check_trailing_stop, is_timeout, _utc_now


class Portfolio:
    def __init__(self):
        self.balance     = config.INITIAL_BALANCE
        self.positions   = {}
        self.history     = []
        self.sl_cooldown = {}
        self.loop_count  = 0

    @staticmethod
    def uses_exchange_balance() -> bool:
        return config.TRADING_MODE in ('testnet', 'live')

    def sync_balance_from_exchange(self, client: Client) -> float:
        """Ambil USDT free dari akun Spot (testnet/mainnet)."""
        acct = client.get_account()
        usdt = next((b for b in acct['balances'] if b['asset'] == 'USDT'), None)
        self.balance = float(usdt['free']) if usdt else 0.0
        return self.balance

    def max_open_positions(self) -> int:
        if self.uses_exchange_balance():
            return max(1, min(int(self.balance // config.BUDGET_PER_TRADE), 5))
        return config.MAX_OPEN_POSITIONS

    def can_open_position(self, symbol: str) -> tuple[bool, str]:
        if symbol in self.positions:
            return False, f"Sudah ada posisi {symbol}"
        max_pos = self.max_open_positions()
        if len(self.positions) >= max_pos:
            return False, f"Posisi penuh ({len(self.positions)}/{max_pos})"
        if self.balance < config.BUDGET_PER_TRADE:
            return False, f"Saldo tidak cukup (${self.balance:.2f})"
        return True, "OK"

    def open_position(self, symbol: str, price: float,
                      strategy: str, score: int,
                      ai_confidence: int = 0,
                      quantity: float | None = None) -> bool:
        can_open, _reason = self.can_open_position(symbol)
        if not can_open:
            return False

        tp, sl = calc_tp_sl(price)
        if not self.uses_exchange_balance():
            self.balance -= config.BUDGET_PER_TRADE

        qty = quantity if quantity is not None else config.BUDGET_PER_TRADE / price
        self.positions[symbol] = {
            'symbol':          symbol,
            'buy_price':       price,
            'tp_price':        tp,
            'sl_price':        sl,
            'quantity':        qty,
            'strategy':        strategy,
            'score':           score,
            'ai_confidence':   ai_confidence,
            'trailing_active': False,
            'entry_loop':      self.loop_count,
            'entry_time':      _utc_now().isoformat(),
        }
        return True

    def check_positions(self, prices: dict) -> list[dict]:
        closed = []
        now = _utc_now()

        for sym in list(self.positions.keys()):
            if sym not in prices:
                continue

            pos   = self.positions[sym]
            price = prices[sym]

            pos = check_trailing_stop(pos, price)

            exit_reason = None
            exit_price  = price

            if price >= pos['tp_price']:
                exit_reason = 'TP'
                exit_price  = pos['tp_price']
            elif price <= pos['sl_price']:
                exit_reason = 'SL'
                exit_price  = price
            elif is_timeout(pos, now):
                exit_reason = 'TIMEOUT'
                exit_price  = price

            if exit_reason:
                trade = self._close_position(sym, exit_price, exit_reason)
                closed.append(trade)

        return closed

    def _close_position(self, symbol: str, exit_price: float,
                        exit_type: str) -> dict:
        pos        = self.positions[symbol]
        entry      = pos['buy_price']
        pct_change = (exit_price - entry) / entry
        gross_pnl  = pct_change * config.BUDGET_PER_TRADE
        fee        = config.BUDGET_PER_TRADE * config.TRADING_FEE_PCT * 2
        net_pnl    = gross_pnl - fee

        if not self.uses_exchange_balance():
            self.balance += config.BUDGET_PER_TRADE + net_pnl

        if exit_type == 'SL' or (exit_type == 'TIMEOUT' and net_pnl < 0):
            self.sl_cooldown[symbol] = _utc_now().isoformat()

        trade = {
            'symbol':     symbol,
            'type':       exit_type,
            'strategy':   pos['strategy'],
            'buy_price':  entry,
            'exit_price': exit_price,
            'quantity':   pos.get('quantity', config.BUDGET_PER_TRADE / entry),
            'pnl':        round(net_pnl, 2),
            'pnl_pct':    round(pct_change * 100, 2),
            'score':      pos['score'],
            'time':       datetime.now(timezone.utc).strftime('%d/%m %H:%M'),
        }

        self.history.insert(0, trade)
        if len(self.history) > 200:
            self.history = self.history[:200]

        del self.positions[symbol]
        return trade

    @property
    def total_value(self) -> float:
        return self.balance + len(self.positions) * config.BUDGET_PER_TRADE

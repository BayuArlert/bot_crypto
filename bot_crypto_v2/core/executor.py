"""
Spot order executor — Testnet / Mainnet.
Paper mode: no-op (portfolio handles virtual trades).
"""
import math
import config
from binance.client import Client
from binance.exceptions import BinanceAPIException


class SpotExecutor:
    def __init__(self, client: Client):
        self.client = client
        self._precision_cache: dict[str, int] = {}
        self._min_notional: dict[str, float] = {}
        self._daily_loss_usd = 0.0

    @property
    def is_live(self) -> bool:
        return config.TRADING_MODE in ('testnet', 'live')

    def _get_lot_precision(self, symbol: str) -> int:
        if symbol in self._precision_cache:
            return self._precision_cache[symbol]
        info = self.client.get_symbol_info(symbol)
        step_size = None
        for f in info.get('filters', []):
            if f['filterType'] == 'LOT_SIZE':
                step_size = float(f['stepSize'])
                break
        if not step_size:
            self._precision_cache[symbol] = 2
            return 2
        prec = int(round(-math.log(step_size, 10), 0))
        self._precision_cache[symbol] = prec
        return prec

    def _round_qty(self, symbol: str, qty: float) -> float:
        prec = self._get_lot_precision(symbol)
        factor = 10 ** prec
        return math.floor(qty * factor) / factor

    def _confirm_live(self, action: str, symbol: str, detail: str) -> bool:
        if config.TRADING_MODE != 'live':
            return True
        if not config.REQUIRE_MANUAL_CONFIRM:
            return True
        print(f"\n   [LIVE] {action} {symbol} — {detail}")
        print("   Ketik CONFIRM untuk melanjutkan (Enter = batal): ", end='')
        try:
            answer = input().strip().upper()
        except EOFError:
            return False
        return answer == 'CONFIRM'

    def _check_daily_loss(self) -> bool:
        if self._daily_loss_usd >= config.MAX_DAILY_LOSS_USD:
            print(f"   [Executor] Daily loss limit ${config.MAX_DAILY_LOSS_USD:.2f} tercapai — stop entries")
            return False
        return True

    def record_closed_pnl(self, pnl: float) -> None:
        if pnl < 0:
            self._daily_loss_usd += abs(pnl)

    def market_buy(self, symbol: str, usdt_budget: float) -> tuple[bool, float, str]:
        """
        Market buy dengan budget USDT.
        Returns: (success, fill_price, message)
        """
        if not self.is_live:
            return True, 0.0, 'paper mode'

        if not self._check_daily_loss():
            return False, 0.0, 'daily loss limit'

        try:
            price = float(self.client.get_symbol_ticker(symbol=symbol)['price'])
            qty   = self._round_qty(symbol, usdt_budget / price)
            if qty <= 0:
                return False, 0.0, 'quantity too small'

            detail = f"~{qty} @ ${price:.6f} (${usdt_budget:.2f})"
            if not self._confirm_live('BUY', symbol, detail):
                return False, 0.0, 'not confirmed'

            order = self.client.order_market_buy(symbol=symbol, quantity=qty)
            fills = order.get('fills', [])
            if fills:
                total_qty = sum(float(f['qty']) for f in fills)
                total_val = sum(float(f['qty']) * float(f['price']) for f in fills)
                fill_price = total_val / total_qty if total_qty else price
            else:
                fill_price = price

            return True, fill_price, f"order {order.get('orderId')}"

        except BinanceAPIException as e:
            return False, 0.0, str(e)
        except Exception as e:
            return False, 0.0, str(e)

    def market_sell(self, symbol: str, quantity: float) -> tuple[bool, float, str]:
        """Market sell seluruh quantity posisi."""
        if not self.is_live:
            return True, 0.0, 'paper mode'

        try:
            qty = self._round_qty(symbol, quantity)
            if qty <= 0:
                return False, 0.0, 'quantity too small'

            if not self._confirm_live('SELL', symbol, f"qty={qty}"):
                return False, 0.0, 'not confirmed'

            order = self.client.order_market_sell(symbol=symbol, quantity=qty)
            fills = order.get('fills', [])
            if fills:
                total_qty = sum(float(f['qty']) for f in fills)
                total_val = sum(float(f['qty']) * float(f['price']) for f in fills)
                fill_price = total_val / total_qty if total_qty else 0.0
            else:
                fill_price = float(self.client.get_symbol_ticker(symbol=symbol)['price'])

            return True, fill_price, f"order {order.get('orderId')}"

        except BinanceAPIException as e:
            return False, 0.0, str(e)
        except Exception as e:
            return False, 0.0, str(e)

"""
Bot Trading CEX v2 — Momentum + Smart Money Following
Berbasis Binance Skills Hub real-time signals.

Jalankan: python main.py
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import time
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from binance.client import Client

import config
from signals.market_rank import (build_sm_inflow_map, get_positive_hype_symbols,
                                  get_trending_symbols)
from signals.volume_scan import get_active_usdt_symbols, scan_volume_anomalies
from core.scorer import score_opportunity
from core.portfolio import Portfolio
from core.executor import SpotExecutor
from core.risk import is_sl_cooldown
from ai.validator import AIValidator
from utils.notifier import (notify_buy, notify_close, notify_bot_start,
                             notify_error)
from utils.state import save_state, load_state
from utils.analytics import calculate_stats, print_report, export_history_csv
from utils import dashboard


def _make_data_client() -> Client:
    """
    Client untuk klines/ticker/scan.
    Testnet volume sangat tipis — pakai mainnet (public, tanpa key).
    """
    if config.TRADING_MODE == 'testnet' and config.TESTNET_USE_MAINNET_DATA:
        return Client()
    kwargs = {
        'api_key':    config.BINANCE_API_KEY,
        'api_secret': config.BINANCE_SECRET_KEY,
    }
    if config.TRADING_MODE == 'testnet' and config.USE_TESTNET:
        kwargs['testnet'] = True
    return Client(**kwargs)


def _make_trade_client() -> Client:
    """Client untuk order & saldo — testnet atau mainnet."""
    kwargs = {
        'api_key':    config.BINANCE_API_KEY,
        'api_secret': config.BINANCE_SECRET_KEY,
    }
    if config.TRADING_MODE == 'testnet' and config.USE_TESTNET:
        kwargs['testnet'] = True
    return Client(**kwargs)


def _testnet_tradable_usdt(client: Client) -> set[str]:
    info = client.get_exchange_info()
    return {
        s['symbol'] for s in info['symbols']
        if s['symbol'].endswith('USDT') and s.get('status') == 'TRADING'
    }


class MomentumBot:
    def __init__(self):
        self.data_client  = _make_data_client()
        self.trade_client = _make_trade_client()
        self.client       = self.trade_client  # alias untuk executor
        self.executor     = SpotExecutor(self.trade_client)
        self.ai        = AIValidator()
        self.portfolio = Portfolio()
        self.loop_count = 0

        self.active_symbols      = []
        self.last_symbol_refresh = None

        load_state(self)
        mode = config.TRADING_MODE
        print(f"   [Mode] TRADING_MODE={mode}"
              + (" (Testnet)" if mode == 'testnet' else ""))
        if mode == 'testnet' and config.TESTNET_USE_MAINNET_DATA:
            print("   [Mode] Sinyal/scan: mainnet | Order/saldo: testnet")
        if self.portfolio.uses_exchange_balance():
            self.portfolio.sync_balance_from_exchange(self.trade_client)
        self._print_balance_summary()

    def _should_refresh_symbols(self) -> bool:
        if self.last_symbol_refresh is None:
            return True
        elapsed = (datetime.now(timezone.utc) - self.last_symbol_refresh).total_seconds()
        return elapsed >= config.SYMBOL_REFRESH_HOURS * 3600

    def _is_quiet_hour(self) -> bool:
        hour  = datetime.now(timezone.utc).hour
        start, end = config.QUIET_HOURS_UTC
        if start > end:  # wrap midnight
            return hour >= start or hour < end
        return start <= hour < end

    def _print_balance_summary(self) -> None:
        if self.portfolio.uses_exchange_balance():
            print(f"   [Saldo] USDT exchange ({config.TRADING_MODE}): "
                  f"${self.portfolio.balance:,.2f} | "
                  f"Max posisi: {self.portfolio.max_open_positions()} | "
                  f"History: {len(self.portfolio.history)} trade")
        else:
            print(f"   [Saldo] Virtual (paper): ${self.portfolio.balance:.2f} | "
                  f"History: {len(self.portfolio.history)} trade")

    def _get_current_prices(self, symbols: list[str]) -> dict[str, float]:
        """Harga untuk monitor posisi — pakai trade client (testnet/mainnet)."""
        price_client = self.trade_client
        result = {}

        if len(symbols) <= 5:
            for sym in symbols:
                for attempt in range(3):
                    try:
                        result[sym] = float(
                            price_client.get_symbol_ticker(symbol=sym)['price'])
                        break
                    except Exception as e:
                        if attempt == 2:
                            print(f"   ⚠️ Gagal fetch harga {sym}: {e}")
                        else:
                            time.sleep(3)
        else:
            for attempt in range(3):
                try:
                    tickers = price_client.get_all_tickers()
                    result  = {
                        t['symbol']: float(t['price'])
                        for t in tickers if t['symbol'] in symbols
                    }
                    break
                except Exception as e:
                    wait = 5 * (2 ** attempt)
                    print(f"   ⚠️ Gagal fetch harga (attempt {attempt+1}/3): {e}")
                    if attempt < 2:
                        time.sleep(wait)

        return result


    def run(self) -> None:
        dashboard.start_dashboard(5001)
        notify_bot_start(self.portfolio.balance, len(self.active_symbols))
        print("🚀 Momentum Bot v2 Aktif — Binance Skills Hub Signals")
        dashboard.add_log("🚀 Momentum Bot v2 Aktif!")
        _update_dashboard(self.portfolio)  # inisialisasi saldo awal di dashboard

        while True:
            try:
                self.loop_count += 1
                self.portfolio.loop_count = self.loop_count

                if self.portfolio.uses_exchange_balance():
                    self.portfolio.sync_balance_from_exchange(self.trade_client)

                # ── Jam Sepi ──
                if self._is_quiet_hour():
                    hour = datetime.now(timezone.utc).hour
                    msg  = (f"🌙 Jam sepi ({hour:02d}:xx UTC = {(hour+7)%24:02d}:xx WIB)"
                            f" — monitoring posisi saja...")
                    print(f"\n{msg}")
                    dashboard.add_log(msg)

                    # Pantau posisi aktif setiap 5 menit selama jam sepi
                    for _ in range(6):
                        time.sleep(300)
                        if self.portfolio.positions:
                            prices = self._get_current_prices(
                                list(self.portfolio.positions.keys()))
                            closed = self.portfolio.check_positions(prices)
                            self._handle_closed_trades(closed)
                    continue

                # ── Refresh Symbol List ──
                if self._should_refresh_symbols():
                    symbols = get_active_usdt_symbols(self.data_client)
                    if config.TRADING_MODE == 'testnet':
                        tradable = _testnet_tradable_usdt(self.trade_client)
                        symbols  = [s for s in symbols if s in tradable]
                    if symbols:
                        self.active_symbols = symbols
                        self.last_symbol_refresh = datetime.now(timezone.utc)
                        src = ("mainnet→testnet"
                               if config.TRADING_MODE == 'testnet'
                               and config.TESTNET_USE_MAINNET_DATA else "exchange")
                        print(f"\n📊 Symbol list diperbarui: {len(self.active_symbols)} "
                              f"koin ({src})")
                    else:
                        # Jangan update last_symbol_refresh — retry di loop berikutnya
                        print("   ⚠️ Gagal fetch symbol list — akan retry 60 detik lagi")
                        time.sleep(60)
                        continue

                if not self.active_symbols:
                    # Reset supaya _should_refresh_symbols() = True di loop berikutnya
                    self.last_symbol_refresh = None
                    print("   ⚠️ Symbol list kosong — akan coba refresh 60 detik lagi")
                    time.sleep(60)
                    continue

                # ── Step 1: Monitor Posisi Aktif ──
                if self.portfolio.positions:
                    prices = self._get_current_prices(
                        list(self.portfolio.positions.keys()))
                    closed = self.portfolio.check_positions(prices)
                    self._handle_closed_trades(closed)

                # ── Step 2: Skip scan jika tidak bisa buka posisi baru ──
                max_pos       = self.portfolio.max_open_positions()
                posisi_penuh  = len(self.portfolio.positions) >= max_pos
                saldo_kurang  = self.portfolio.balance < config.BUDGET_PER_TRADE
                if posisi_penuh or saldo_kurang:
                    alasan = (f"posisi penuh ({len(self.portfolio.positions)}/{max_pos})"
                              if posisi_penuh else
                              f"saldo ${self.portfolio.balance:.2f} < ${config.BUDGET_PER_TRADE:.0f}/trade")
                    print(f"   💤 {alasan} — monitoring posisi saja")
                    _update_dashboard(self.portfolio)
                    save_state(self)
                    time.sleep(config.LOOP_INTERVAL_SECONDS)
                    continue

                # ── Step 3: Fetch All Signals (parallel) ──
                now_str = datetime.now().strftime('%H:%M:%S')
                print(f"\n[{now_str}] Loop #{self.loop_count} "
                      f"— Scanning {len(self.active_symbols)} koin...")

                spot_tickers = {
                    sym.replace('USDT', '') for sym in self.active_symbols
                }

                with ThreadPoolExecutor(max_workers=4) as executor:
                    f_volume   = executor.submit(
                        scan_volume_anomalies, self.data_client, self.active_symbols)
                    f_sm       = executor.submit(build_sm_inflow_map, spot_tickers)
                    f_hype     = executor.submit(
                        get_positive_hype_symbols, spot_tickers)
                    f_trending = executor.submit(
                        get_trending_symbols, spot_tickers)

                    volume_spikes  = f_volume.result()
                    sm_inflow_map  = f_sm.result()
                    hype_symbols   = f_hype.result()
                    trending_syms  = f_trending.result()

                print(f"   Volume spikes: {len(volume_spikes)} | "
                      f"SM inflow (Spot): {len(sm_inflow_map)} | "
                      f"Hype (Spot): {len(hype_symbols)} | "
                      f"Trending (Spot): {len(trending_syms)}")

                if not volume_spikes:
                    print("   Tidak ada volume spike yang terdeteksi.")
                    _update_dashboard(self.portfolio)
                    save_state(self)
                    time.sleep(config.LOOP_INTERVAL_SECONDS)
                    continue

                # ── Step 4: Score kandidat ──
                candidates = []
                for vol_data in volume_spikes:
                    sym    = vol_data['symbol']
                    ticker = sym.replace('USDT', '')

                    if sym in self.portfolio.positions:
                        continue
                    if is_sl_cooldown(sym, self.portfolio.sl_cooldown):
                        continue

                    sm_data    = sm_inflow_map.get(ticker, {})
                    sm_inflow  = float(sm_data.get('sm_inflow_usd', 0))
                    sm_traders = int(sm_data.get('sm_traders_count', 0))
                    in_sm      = (
                        bool(sm_data)
                        and sm_inflow >= config.SM_MIN_INFLOW_USD
                        and sm_traders >= config.SM_MIN_TRADERS
                    )

                    in_hype    = ticker in hype_symbols
                    hype_score = hype_symbols.get(ticker, 0)  # ambil score asli, bukan 0
                    in_trend   = ticker in trending_syms

                    score, reasons = score_opportunity(
                        symbol        = sym,
                        volume_data   = vol_data,
                        in_sm_inflow  = in_sm,
                        sm_inflow_usd = sm_inflow,
                        sm_traders    = sm_traders,
                        in_social_hype = in_hype,
                        hype_score    = hype_score,
                        in_trending   = in_trend,
                    )

                    if score > 0:
                        print(f"   [SCORE] {sym}: {score}/10 | "
                              f"{' | '.join(reasons[:2])}")

                    if score >= config.MIN_SIGNAL_SCORE:
                        candidates.append({
                            'symbol':  sym,
                            'score':   score,
                            'reasons': reasons,
                            'vol_data': vol_data,
                            'sm_data':  sm_data,
                        })

                if not candidates:
                    print("   Tidak ada kandidat yang memenuhi skor minimum.")
                    _update_dashboard(self.portfolio)
                    save_state(self)
                    time.sleep(config.LOOP_INTERVAL_SECONDS)
                    continue

                candidates.sort(key=lambda x: x['score'], reverse=True)
                print(f"\n   🎯 {len(candidates)} kandidat ditemukan!")

                # ── Step 5: AI Validation + Entry ──
                for cand in candidates:
                    if len(self.portfolio.positions) >= self.portfolio.max_open_positions():
                        break

                    sym   = cand['symbol']
                    score = cand['score']

                    should_buy, confidence, ai_reason = self.ai.validate_entry(
                        symbol      = sym,
                        score       = score,
                        reasons     = cand['reasons'],
                        volume_data = cand['vol_data'],
                        sm_data     = {
                            'inflow_usd': float(cand['sm_data'].get('sm_inflow_usd', 0)),
                            'traders':    int(cand['sm_data'].get('sm_traders_count', 0)),
                        },
                    )

                    ai_verdict = 'BUY' if should_buy else 'SKIP'
                    print(f"   [AI] {sym}: {ai_verdict} [Conf:{confidence}/10] — {ai_reason}")

                    if not should_buy or confidence < config.AI_MIN_CONFIDENCE:
                        continue

                    # Cek harga realtime — validasi drift
                    try:
                        live_price     = float(
                            self.trade_client.get_symbol_ticker(symbol=sym)['price'])
                        analysis_price = cand['vol_data']['price']
                        drift          = abs(live_price - analysis_price) / analysis_price
                        if drift > 0.01:
                            print(f"   ⏭️ SKIP {sym}: harga drift {drift*100:.1f}% sejak analisis")
                            continue
                    except Exception as e:
                        print(f"   ⚠️ Gagal fetch live price {sym}: {e}")
                        continue

                    entry_price = live_price
                    entry_qty   = config.BUDGET_PER_TRADE / live_price

                    if self.executor.is_live:
                        ok, fill, msg = self.executor.market_buy(
                            sym, config.BUDGET_PER_TRADE)
                        if not ok:
                            print(f"   ⏭️ SKIP {sym}: order gagal — {msg}")
                            continue
                        if fill > 0:
                            entry_price = fill
                            entry_qty   = config.BUDGET_PER_TRADE / fill

                    success = self.portfolio.open_position(
                        symbol        = sym,
                        price         = entry_price,
                        strategy      = 'Momentum-SM',
                        score         = score,
                        ai_confidence = confidence,
                        quantity      = entry_qty,
                    )

                    if success:
                        if self.portfolio.uses_exchange_balance():
                            self.portfolio.sync_balance_from_exchange(
                                self.trade_client)
                        pos = self.portfolio.positions[sym]
                        msg = (f"🚀 BUY {sym} @ ${entry_price:.4f} | "
                               f"Score: {score}/10 | Conf: {confidence}/10 | "
                               f"TP: ${pos['tp_price']:.4f} | SL: ${pos['sl_price']:.4f}")
                        print(f"   {msg}")
                        dashboard.add_log(msg)
                        notify_buy(sym, entry_price, pos['tp_price'], pos['sl_price'],
                                   'Momentum-SM', confidence)

                if self.portfolio.uses_exchange_balance():
                    self.portfolio.sync_balance_from_exchange(self.trade_client)

                # ── Step 6: Update Dashboard & Save ──
                _update_dashboard(self.portfolio)
                save_state(self)

                # Analytics setiap 60 loop
                if self.loop_count % 60 == 0 and self.portfolio.history:
                    stats = calculate_stats(self.portfolio.history, config.INITIAL_BALANCE)
                    print_report(stats)
                    export_history_csv(self.portfolio.history)

                time.sleep(config.LOOP_INTERVAL_SECONDS)

            except KeyboardInterrupt:
                print("\n⏹️ Bot dihentikan.")
                save_state(self)
                break
            except Exception as e:
                print(f"\n⚠️ Error di main loop: {e}")
                notify_error("main loop", str(e))
                time.sleep(30)


    def _handle_closed_trades(self, closed: list[dict]) -> None:
        for trade in closed:
            if self.executor.is_live:
                qty = trade.get('quantity', 0)
                if qty > 0:
                    ok, _fill, msg = self.executor.market_sell(
                        trade['symbol'], qty)
                    if not ok:
                        print(f"   ⚠️ SELL gagal {trade['symbol']}: {msg}")
                self.executor.record_closed_pnl(trade['pnl'])
                self.portfolio.sync_balance_from_exchange(self.trade_client)
            _log_close(trade)
            notify_close(trade)


# ─────────────────────────────────────────────────────────
# Helper functions
# ─────────────────────────────────────────────────────────
def _log_close(trade: dict) -> None:
    icon = "✅" if trade['pnl'] > 0 else "❌"
    msg  = (f"{icon} CLOSE {trade['symbol']} [{trade['type']}] "
            f"PnL: {'+' if trade['pnl']>0 else ''}${trade['pnl']:.2f}")
    print(f"   {msg}")
    dashboard.add_log(msg)


def _update_dashboard(portfolio: Portfolio) -> None:
    tp_count = sum(1 for t in portfolio.history if t['type'] == 'TP')
    sl_count = sum(1 for t in portfolio.history
                   if t['type'] in ('SL', 'TIMEOUT'))
    if portfolio.uses_exchange_balance():
        total_pnl = sum(t.get('pnl', 0) for t in portfolio.history)
    else:
        total_pnl = round(portfolio.balance - config.INITIAL_BALANCE, 2)
    dashboard.update_state(
        virtual_balance = portfolio.balance,
        total_profit    = round(total_pnl, 2),
        positions       = list(portfolio.positions.values()),
        trade_history   = portfolio.history,
        tp_count        = tp_count,
        sl_count        = sl_count,
    )


if __name__ == "__main__":
    bot = MomentumBot()
    bot.run()

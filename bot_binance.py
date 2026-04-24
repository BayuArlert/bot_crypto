import time
from datetime import datetime
import pandas as pd
from binance.client import Client
from binance.exceptions import BinanceAPIException
import config
from indicators import hitung_indikator, get_market_summary, detect_market_regime
from ai_portfolio import AIPortfolioManager
import math
import dashboard


class BinanceBot:
    def __init__(self):
        self.client    = Client(config.BINANCE_API_KEY, config.BINANCE_SECRET)
        self.ai        = AIPortfolioManager(config.GROQ_API_KEY)
        self.virtual_portfolio = {}
        self.virtual_balance   = 25.0
        self.sl_cooldown       = {}
        self.loop_count        = 0
        self.trade_history     = []

    def _get_precision(self, symbol):
        """Membaca presisi desimal koin dari Binance agar tidak ditolak"""
        info      = self.client.get_symbol_info(symbol)
        step_size = None
        for f in info['filters']:
            if f['filterType'] == 'LOT_SIZE':
                step_size = float(f['stepSize'])
        if step_size is None:
            return 2
        return int(round(-math.log(step_size, 10), 0))

    def get_historical_data(self, symbol, interval=None, limit=100) -> pd.DataFrame:
        if interval is None:
            interval = config.TIMEFRAME
        try:
            klines = self.client.get_klines(symbol=symbol, interval=interval, limit=limit)
            df = pd.DataFrame(klines, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'qav', 'num_trades',
                'taker_base_vol', 'taker_quote_vol', 'ignore'
            ])
            for col in ['close', 'high', 'low', 'open']:
                df[col] = pd.to_numeric(df[col])
            return df
        except Exception as e:
            print(f"⚠️ Gagal menarik candle Binance untuk {symbol}: {e}")
            return pd.DataFrame()

    # ──────────────────────────────────────────────────────
    # TP/SL DINAMIS BERBASIS ATR & REGIME
    # ──────────────────────────────────────────────────────
    def _calc_tp_sl(self, buy_price: float, atr: float, regime: str):
        """
        Hitung TP dan SL secara otomatis berdasarkan ATR dan kondisi pasar.
        Ini menggantikan angka hardcode 1% dan 1.5% yang tidak adaptif.
        """
        if atr and atr > 0:
            if regime == 'BULL':
                tp_price = buy_price + config.BULL_TP_ATR_MULT * atr
                sl_price = buy_price - config.BULL_SL_ATR_MULT * atr
            else:  # RANGE
                tp_price = buy_price + config.RANGE_TP_ATR_MULT * atr
                sl_price = buy_price - config.RANGE_SL_ATR_MULT * atr
        else:
            # Fallback ke persentase jika ATR tidak tersedia
            tp_price = buy_price * (1 + config.FALLBACK_TP_PCT)
            sl_price = buy_price * (1 - config.FALLBACK_SL_PCT)

        return tp_price, sl_price

    # ──────────────────────────────────────────────────────
    # CEK TP/SL VIRTUAL PORTFOLIO
    # ──────────────────────────────────────────────────────
    def check_virtual_portfolio(self, symbol, current_price):
        """Mengecek apakah posisi virtual sudah menyentuh TP atau SL"""
        if symbol not in self.virtual_portfolio:
            return
        pos = self.virtual_portfolio[symbol]

        if current_price >= pos['tp_price']:
            profit = pos['tp_price'] - pos['buy_price']
            profit_usdt = (profit / pos['buy_price']) * config.BUDGET_PER_TRADE_USDT
            self.virtual_balance += config.BUDGET_PER_TRADE_USDT + profit_usdt

            msg = (f"🎉 TAKE PROFIT {symbol}! "
                   f"Entry: {pos['buy_price']:.4f} → TP: {current_price:.4f} | "
                   f"Untung: +${profit_usdt:.2f} | Saldo: ${self.virtual_balance:.2f}")
            dashboard.add_log(msg)
            print(msg)

            self.trade_history.insert(0, {
                'type':       'TP',
                'symbol':     symbol,
                'strategy':   pos.get('strategy', '-'),
                'buy_price':  pos['buy_price'],
                'exit_price': current_price,
                'pnl':        round(profit_usdt, 2),
                'time':       datetime.now().strftime('%d/%m %H:%M')
            })
            del self.virtual_portfolio[symbol]

        elif current_price <= pos['sl_price']:
            loss       = pos['buy_price'] - pos['sl_price']
            loss_usdt  = (loss / pos['buy_price']) * config.BUDGET_PER_TRADE_USDT
            self.virtual_balance += config.BUDGET_PER_TRADE_USDT - loss_usdt

            msg = (f"💔 CUT LOSS {symbol}! "
                   f"Entry: {pos['buy_price']:.4f} → SL: {current_price:.4f} | "
                   f"Rugi: -${loss_usdt:.2f} | Saldo: ${self.virtual_balance:.2f}")
            dashboard.add_log(msg)
            print(msg)

            self.trade_history.insert(0, {
                'type':       'SL',
                'symbol':     symbol,
                'strategy':   pos.get('strategy', '-'),
                'buy_price':  pos['buy_price'],
                'exit_price': current_price,
                'pnl':        round(-loss_usdt, 2),
                'time':       datetime.now().strftime('%d/%m %H:%M')
            })
            del self.virtual_portfolio[symbol]
            self.sl_cooldown[symbol] = self.loop_count

        if len(self.trade_history) > 100:
            self.trade_history = self.trade_history[:100]

    def has_open_orders(self, symbol):
        return symbol in self.virtual_portfolio

    def buy_with_safety_net(self, symbol, current_price, atr, regime, strategy_label):
        """Beli virtual dengan TP/SL dinamis berbasis ATR & regime"""
        if self.virtual_balance < config.BUDGET_PER_TRADE_USDT:
            msg = f"❌ BATAL: Saldo ${self.virtual_balance:.2f} tidak cukup untuk trade ${config.BUDGET_PER_TRADE_USDT}!"
            dashboard.add_log(msg)
            print(msg)
            return

        self.virtual_balance -= config.BUDGET_PER_TRADE_USDT

        tp_price, sl_price = self._calc_tp_sl(current_price, atr, regime)

        tp_pct = ((tp_price - current_price) / current_price) * 100
        sl_pct = ((current_price - sl_price) / current_price) * 100

        msg1 = (f"📝 [{strategy_label}] BELI {symbol} @ {current_price:.4f} | "
                f"TP: {tp_price:.4f} (+{tp_pct:.1f}%) | SL: {sl_price:.4f} (-{sl_pct:.1f}%)")
        dashboard.add_log(msg1)
        print(msg1)

        self.virtual_portfolio[symbol] = {
            'buy_price': current_price,
            'tp_price':  tp_price,
            'sl_price':  sl_price,
            'strategy':  strategy_label,
            'atr':       atr,
        }

    # ──────────────────────────────────────────────────────
    # PRE-FILTER: BULL MARKET — Pullback ke EMA
    # ──────────────────────────────────────────────────────
    def _filter_bull_candidates(self, market_state: dict) -> dict:
        """
        Strategi BULL: cari koin yang pullback KE EMA20 dalam uptrend.
        RSI harus di zona pullback KETAT (40-52), bukan mendekati puncak.
        Harga juga harus benar-benar dekat atau di bawah EMA20.
        """
        candidates = {}
        for koin, data in market_state.items():
            # [1] Harus dalam uptrend di 15m
            is_uptrend = data['trend_ema'] == 'Strong Uptrend'

            # [2] RSI zona pullback KETAT (40-52) — bukan mendekati overbought
            rsi = data['rsi']
            is_pullback = 40 <= rsi <= 52

            # [3] Harga harus benar-benar dekat atau di bawah EMA20
            #     Mencegah bot beli koin yang sudah jauh di atas EMA
            price = data['price']
            ema20 = data.get('ema20', price)
            near_ema = price <= ema20 * config.BULL_EMA_PROXIMITY

            # [4] Volume minimal setara rata-rata (bukan lesu)
            has_volume = data.get('vol_ratio', 1.0) >= config.MIN_VOL_RATIO

            # [5] Cooldown setelah SL
            loops_since_sl = self.loop_count - self.sl_cooldown.get(koin, -999)
            is_on_cooldown = loops_since_sl < config.SL_COOLDOWN_LOOPS

            if is_uptrend and is_pullback and near_ema and has_volume and not is_on_cooldown:
                # Konfirmasi MTF 1h — harus uptrend atau sideways
                df_1h = self.get_historical_data(koin, interval=config.MTF_INTERVAL, limit=60)
                if not df_1h.empty:
                    df_1h     = hitung_indikator(df_1h)
                    htf       = get_market_summary(df_1h)
                    htf_trend = htf['trend_ema']
                    if htf_trend == 'Strong Downtrend':
                        print(f"   [BULL MTF ❌] {koin}: 1h={htf_trend} — skip")
                    else:
                        data['htf_1h_trend'] = htf_trend
                        candidates[koin]     = data
                        candle_info = data.get('candle_color', '?')
                        print(f"   [BULL MTF ✅] {koin}: RSI={rsi} | EMA20={ema20:.4f} vs Price={price:.4f} | Candle={candle_info} | 1h={htf_trend} → lolos ke AI")
            else:
                # Log alasan skip agar mudah di-debug
                skip_reasons = []
                if not is_uptrend:   skip_reasons.append(f"trend={data['trend_ema']}")
                if not is_pullback:  skip_reasons.append(f"RSI={rsi} (butuh 40-52)")
                if not near_ema:     skip_reasons.append(f"price={price:.4f} jauh dari EMA20={ema20:.4f}")
                if not has_volume:   skip_reasons.append(f"vol={data.get('vol_ratio',0):.2f} (butuh ≥1.0)")
                if is_on_cooldown:   skip_reasons.append(f"cooldown SL")
                print(f"   [BULL SKIP] {koin}: {', '.join(skip_reasons)}")

        return candidates

    # ──────────────────────────────────────────────────────
    # PRE-FILTER: RANGE MARKET — Bounce dari Lower BB
    # ──────────────────────────────────────────────────────
    def _filter_range_candidates(self, market_state: dict) -> dict:
        """
        Strategi RANGE: cari koin oversold ekstrem dekat lower Bollinger Band.
        Filter diperketat: volume harus ada, candle bullish jadi poin plus.
        """
        candidates = {}
        for koin, data in market_state.items():
            rsi       = data['rsi']
            stoch_rsi = data['stoch_rsi']
            bb_pct    = data.get('bb_pct', 50)
            vol_ratio = data.get('vol_ratio', 1.0)

            # [1] Oversold: RSI < 35 ATAU stoch_rsi sangat rendah
            is_oversold    = rsi < 35 or stoch_rsi < 15

            # [2] Blok downtrend kuat
            is_dangerous   = (data['trend_ema'] == 'Strong Downtrend' and data['adx'] > 35)

            # [3] Volume setara rata-rata (bukan lesu) — naik dari 0.8 ke 1.0
            has_volume     = vol_ratio >= config.MIN_VOL_RATIO

            # [4] Harga harus benar-benar di dekat lower band (30, lebih ketat dari 35)
            near_lower_band = bb_pct < config.BB_PCT_THRESHOLD

            # [5] Cooldown setelah SL
            loops_since_sl = self.loop_count - self.sl_cooldown.get(koin, -999)
            is_on_cooldown = loops_since_sl < config.SL_COOLDOWN_LOOPS

            if is_oversold and not is_dangerous and has_volume and near_lower_band and not is_on_cooldown:
                # Konfirmasi MTF 1h
                df_1h = self.get_historical_data(koin, interval=config.MTF_INTERVAL, limit=60)
                if not df_1h.empty:
                    df_1h     = hitung_indikator(df_1h)
                    htf       = get_market_summary(df_1h)
                    htf_trend = htf['trend_ema']
                    if htf_trend == 'Strong Downtrend':
                        print(f"   [RANGE MTF ❌] {koin}: 1h={htf_trend} — skip meski 15m oversold")
                    else:
                        data['htf_1h_trend'] = htf_trend
                        candidates[koin]     = data
                        candle_info = data.get('candle_color', '?')
                        print(f"   [RANGE MTF ✅] {koin}: RSI={rsi} | StochRSI={stoch_rsi} | BB={bb_pct:.1f}% | Candle={candle_info} | 1h={htf_trend} → lolos ke AI")
            else:
                skip_reasons = []
                if not is_oversold:       skip_reasons.append(f"RSI={rsi} StochRSI={stoch_rsi} (belum oversold)")
                if is_dangerous:          skip_reasons.append(f"downtrend kuat ADX={data['adx']}")
                if not has_volume:        skip_reasons.append(f"vol={vol_ratio:.2f} (butuh ≥1.0)")
                if not near_lower_band:   skip_reasons.append(f"bb_pct={bb_pct:.1f} (butuh <{config.BB_PCT_THRESHOLD})")
                if is_on_cooldown:        skip_reasons.append("cooldown SL")
                print(f"   [RANGE SKIP] {koin}: {', '.join(skip_reasons)}")

        return candidates

    # ──────────────────────────────────────────────────────
    # MAIN LOOP
    # ──────────────────────────────────────────────────────
    def run(self):
        dashboard.start_dashboard(5001)
        dashboard.add_log("🚀 Adaptive Multi-Regime Bot Aktif! (BEAR/BULL/RANGE Auto-Switch)")

        while True:
            self.loop_count += 1
            market_state = {}
            radar_list   = []

            print(f"\n🔄 Loop #{self.loop_count} — Memindai pasar...")

            # ── 1. Kumpulkan data semua koin ──
            for sym in config.SYMBOL_LIST:
                df = self.get_historical_data(sym, interval=config.TIMEFRAME)
                if not df.empty:
                    df               = hitung_indikator(df)
                    market_state[sym] = get_market_summary(df)

                    radar_list.append({
                        'symbol':    sym,
                        'price':     market_state[sym]['price'],
                        'rsi':       market_state[sym]['rsi'],
                        'trend':     market_state[sym]['trend_ema'],
                        'adx':       market_state[sym]['adx'],
                        'vol_ratio': market_state[sym].get('vol_ratio', 1.0),
                        'bb_pct':    market_state[sym].get('bb_pct', 50),
                    })

                    self.check_virtual_portfolio(sym, market_state[sym]['price'])
                    print(f"   [{sym}] {market_state[sym]['price']:.4f} | RSI:{market_state[sym]['rsi']} | {market_state[sym]['trend_ema']} | ADX:{market_state[sym]['adx']}")

            # ── 2. Deteksi Market Regime ──
            regime = detect_market_regime(market_state)
            regime_name = regime['regime']
            print(f"\n{'='*60}")
            print(f"🌐 MARKET REGIME: {regime['description']}")
            print(f"   Uptrend: {regime['uptrend_pct']}% | Downtrend: {regime['downtrend_pct']}% | ADX avg: {regime['avg_adx']} | RSI avg: {regime['avg_rsi']}")
            print(f"{'='*60}")
            dashboard.add_log(f"🌐 REGIME: {regime['description']}")

            # ── 3. Kalkulasi portofolio untuk dashboard ──
            active_pos_list = []
            for psym, pdata in self.virtual_portfolio.items():
                cur_price  = market_state[psym]['price'] if psym in market_state else pdata['buy_price']
                pct_change = (cur_price - pdata['buy_price']) / pdata['buy_price']
                fake_pnl   = pct_change * config.BUDGET_PER_TRADE_USDT
                active_pos_list.append({
                    'symbol':    psym,
                    'strategy':  pdata.get('strategy', '-'),
                    'buy_price': pdata['buy_price'],
                    'price':     cur_price,
                    'pnl':       fake_pnl,
                    'tp':        pdata['tp_price'],
                    'sl':        pdata['sl_price'],
                })

            deployed       = len(self.virtual_portfolio) * config.BUDGET_PER_TRADE_USDT
            unrealized     = sum(p['pnl'] for p in active_pos_list)
            total_portfolio = self.virtual_balance + deployed + unrealized

            tp_count = sum(1 for t in self.trade_history if t['type'] == 'TP')
            sl_count = sum(1 for t in self.trade_history if t['type'] == 'SL')

            dashboard.update_state(
                virtual_balance=self.virtual_balance,
                total_profit=round(total_portfolio - 25.0, 2),
                market_radar=radar_list,
                positions=active_pos_list,
                trade_history=self.trade_history,
                tp_count=tp_count,
                sl_count=sl_count,
                market_regime=regime,
            )

            # ── 4. Routing Strategi Berdasarkan Regime ──

            # ████ BEAR MARKET — BOT DIAM ████
            if regime_name == 'BEAR':
                wait_msg = (f"🐻 BEAR MARKET — Bot menunggu kondisi aman. "
                            f"Downtrend {regime['downtrend_pct']}% | ADX {regime['avg_adx']}. "
                            f"Modal dilindungi.")
                dashboard.add_log(wait_msg)
                print(f"\n{wait_msg}\n")

            # ████ BULL MARKET — TREND FOLLOWING ████
            elif regime_name == 'BULL':
                print(f"\n🐂 BULL MARKET — Mencari entry pullback ke EMA...")
                koin_potensial = self._filter_bull_candidates(market_state)

                if not koin_potensial:
                    print("⏳ Tidak ada koin dengan setup pullback valid.")
                else:
                    print(f"\n🧠 {len(koin_potensial)} kandidat BULL ditemukan! Konsultasi ke AI...")
                    ai_decisions = self.ai.analyze_opportunity(koin_potensial, regime)

                    for dec in ai_decisions:
                        sym        = dec.get('symbol')
                        action     = dec.get('decision')
                        confidence = dec.get('confidence', 0)
                        reason     = dec.get('reason', '')

                        if action == 'BUY' and sym in koin_potensial:
                            if confidence < config.AI_MIN_CONFIDENCE:
                                msg = f"⏭️ SKIP {sym}: confidence {confidence}/10 terlalu rendah"
                                dashboard.add_log(msg); print(msg)
                                continue

                            if len(self.virtual_portfolio) >= config.MAX_OPEN_POSITIONS:
                                msg = f"⏭️ SKIP: Sudah {config.MAX_OPEN_POSITIONS} posisi aktif."
                                dashboard.add_log(msg); print(msg)
                                break
                            elif self.has_open_orders(sym):
                                dashboard.add_log(f"⏭️ SKIP: Masih hold {sym}.")
                            else:
                                msg = f"🚀 AI → BELI {sym} [Conf:{confidence}/10] — {reason}"
                                dashboard.add_log(msg); print(msg)
                                self.buy_with_safety_net(
                                    sym,
                                    market_state[sym]['price'],
                                    market_state[sym].get('atr', 0),
                                    regime_name,
                                    'BULL-Pullback'
                                )

            # ████ RANGE MARKET — MEAN REVERSION BOUNCE ████
            else:
                print(f"\n📊 RANGING MARKET — Mencari entry bounce di BB bawah...")
                koin_potensial = self._filter_range_candidates(market_state)

                if not koin_potensial:
                    print("⏳ Tidak ada koin oversold di dekat lower Bollinger Band.")
                else:
                    print(f"\n🧠 {len(koin_potensial)} kandidat RANGE ditemukan! Konsultasi ke AI...")
                    ai_decisions = self.ai.analyze_opportunity(koin_potensial, regime)

                    for dec in ai_decisions:
                        sym        = dec.get('symbol')
                        action     = dec.get('decision')
                        confidence = dec.get('confidence', 0)
                        reason     = dec.get('reason', '')

                        if action == 'BUY' and sym in koin_potensial:
                            if confidence < config.AI_MIN_CONFIDENCE:
                                msg = f"⏭️ SKIP {sym}: confidence {confidence}/10 terlalu rendah"
                                dashboard.add_log(msg); print(msg)
                                continue

                            if len(self.virtual_portfolio) >= config.MAX_OPEN_POSITIONS:
                                msg = f"⏭️ SKIP: Sudah {config.MAX_OPEN_POSITIONS} posisi aktif."
                                dashboard.add_log(msg); print(msg)
                                break
                            elif self.has_open_orders(sym):
                                dashboard.add_log(f"⏭️ SKIP: Masih hold {sym}.")
                            else:
                                msg = f"🚀 AI → BELI {sym} [Conf:{confidence}/10] — {reason}"
                                dashboard.add_log(msg); print(msg)
                                self.buy_with_safety_net(
                                    sym,
                                    market_state[sym]['price'],
                                    market_state[sym].get('atr', 0),
                                    regime_name,
                                    'RANGE-Bounce'
                                )

            time.sleep(config.LOOP_INTERVAL_SECONDS)


if __name__ == "__main__":
    bot = BinanceBot()
    bot.run()

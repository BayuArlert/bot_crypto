import time
import pandas as pd
from binance.client import Client
from binance.exceptions import BinanceAPIException
import config
from indicators import hitung_indikator, get_market_summary
from ai_portfolio import AIPortfolioManager
import math
import dashboard

class BinanceBot:
    def __init__(self):
        self.client = Client(config.BINANCE_API_KEY, config.BINANCE_SECRET)
        self.ai = AIPortfolioManager(config.GROQ_API_KEY) # Terhubung ke Groq Llama-3 API
        self.virtual_portfolio = {}  # MENYIMPAN TRANSAKSI PALSU
        self.virtual_balance = 25.0  # Modal Simulasi $25 (sesuai rencana top up Binance)
        self.sl_cooldown = {}         # {symbol: loop_count} — jeda re-beli pasca Cut Loss
        self.loop_count  = 0          # Counter siklus loop berjalan
        
    def _get_precision(self, symbol):
        """Membaca presisi desimal koin dari server Binance agar tidak ditolak"""
        info = self.client.get_symbol_info(symbol)
        step_size = None
        for f in info['filters']:
            if f['filterType'] == 'LOT_SIZE':
                step_size = float(f['stepSize'])
        if step_size is None:
            return 2  # Default kasar jika error
        return int(round(-math.log(step_size, 10), 0))
        
    def get_historical_data(self, symbol, interval=None, limit=100) -> pd.DataFrame:
        # [FIX] Default selalu ikut config.TIMEFRAME, bukan hardcoded "1h"
        if interval is None:
            interval = config.TIMEFRAME
        try:
            klines = self.client.get_klines(symbol=symbol, interval=interval, limit=limit)
            df = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'qav', 'num_trades', 'taker_base_vol', 'taker_quote_vol', 'ignore'])
            df['close'] = pd.to_numeric(df['close'])
            df['high'] = pd.to_numeric(df['high'])
            df['low'] = pd.to_numeric(df['low'])
            df['open'] = pd.to_numeric(df['open'])
            return df
        except Exception as e:
            print(f"⚠️ Gagal menarik candle Binance untuk {symbol}: {e}")
            return pd.DataFrame()

    def check_virtual_portfolio(self, symbol, current_price):
        """Mengecek apakah koin palsu yang kita pegang sudah menyentuh target SL/TP"""
        if symbol in self.virtual_portfolio:
            pos = self.virtual_portfolio[symbol]
            if current_price >= pos['tp_price']:
                profit = config.BUDGET_PER_TRADE_USDT * config.TAKE_PROFIT_PCT
                # Kembalikan modal + profit ke saldo
                self.virtual_balance += config.BUDGET_PER_TRADE_USDT + profit
                msg = f"🎉 TAKE PROFIT TERSENTUH untuk {symbol}! Untung: +${profit:.2f} | Saldo: ${self.virtual_balance:.2f}"
                dashboard.add_log(msg)
                print(msg)
                del self.virtual_portfolio[symbol]
                
            elif current_price <= pos['sl_price']:
                loss = config.BUDGET_PER_TRADE_USDT * config.STOP_LOSS_PCT
                # Kembalikan modal dikurangi loss ke saldo
                self.virtual_balance += config.BUDGET_PER_TRADE_USDT - loss
                msg = f"💔 CUT LOSS TERSENTUH untuk {symbol}! Rugi: -${loss:.2f} | Saldo: ${self.virtual_balance:.2f}"
                dashboard.add_log(msg)
                print(msg)
                del self.virtual_portfolio[symbol]
                # [BARU] Catat cooldown — bot tidak akan re-beli koin ini selama beberapa loop
                self.sl_cooldown[symbol] = self.loop_count


    def has_open_orders(self, symbol):
        """Mengecek apakah kita sedang memegang koin ini di memori komputer"""
        return symbol in self.virtual_portfolio

    def buy_with_safety_net(self, symbol, current_price):
        """
        [MODE SIMULASI] Tidak akan benar-benar terkirim ke Binance.
        Hanya numpang mencatat di buku catatan virtual bot.
        """
        if self.virtual_balance < config.BUDGET_PER_TRADE_USDT:
            msg = f"❌ TRANSAKSI SIMULASI BATAL: Saldo ${self.virtual_balance:.2f} tidak cukup untuk trade ${config.BUDGET_PER_TRADE_USDT}!"
            dashboard.add_log(msg)
            print(msg)
            return
        
        # Potong modal dari saldo saat beli (simulasi nyata)
        self.virtual_balance -= config.BUDGET_PER_TRADE_USDT

        msg1 = f"📝 Simulasi AI mengeklik BELI {symbol} senilai ${config.BUDGET_PER_TRADE_USDT} di harga {current_price}"
        dashboard.add_log(msg1)
        print(msg1)
        
        tp_price = current_price * (1 + config.TAKE_PROFIT_PCT)
        sl_price = current_price * (1 - config.STOP_LOSS_PCT)
        
        self.virtual_portfolio[symbol] = {
            'buy_price': current_price,
            'tp_price': tp_price,
            'sl_price': sl_price
        }
        
        msg2 = f"🛡️ Jaring OCO Virtual Pasang: TP: {tp_price:.4f} | SL: {sl_price:.4f}"
        dashboard.add_log(msg2)
        print(msg2)
            
    def run(self):
        dashboard.start_dashboard(5001)
        dashboard.add_log("Mesin Spot Crypto (Mode Paper Trading) Siap Meluncur!")
        
        while True:
            self.loop_count += 1  # Increment counter tiap siklus untuk tracking cooldown
            market_state = {}
            radar_list = []
            
            print("\n🔄 Mengamankan Peta Radars...")
            for sym in config.SYMBOL_LIST:
                df = self.get_historical_data(sym, interval=config.TIMEFRAME)
                if not df.empty:
                    df = hitung_indikator(df)
                    market_state[sym] = get_market_summary(df)
                    
                    # Tambahkan ke radar dashboard UI
                    radar_list.append({
                        'symbol':    sym,
                        'price':     market_state[sym]['price'],
                        'rsi':       market_state[sym]['rsi'],
                        'trend':     market_state[sym]['trend_ema'],
                        'adx':       market_state[sym]['adx'],
                        'vol_ratio': market_state[sym].get('vol_ratio', 1.0),
                        'bb_pct':    market_state[sym].get('bb_pct', 50),
                    })
                    
                    # Cek apakah TP/SL fiktif kita sudah tersentuh
                    self.check_virtual_portfolio(sym, market_state[sym]['price'])
                    print(f"   [{sym}] Harga: {market_state[sym]['price']:.4f} | RSI: {market_state[sym]['rsi']} | Tren: {market_state[sym]['trend_ema']}")
            
            # Format UI Positions
            active_pos_list = []
            for psym, pdata in self.virtual_portfolio.items():
                cur_price = market_state[psym]['price'] if psym in market_state else pdata['buy_price']
                # Kalkulasi (Price Now - Buy Price) / Buy Price * Saldo 
                pct_change = (cur_price - pdata['buy_price']) / pdata['buy_price']
                fake_pnl = pct_change * config.BUDGET_PER_TRADE_USDT
                active_pos_list.append({
                    'symbol': psym,
                    'buy_price': pdata['buy_price'],
                    'price': cur_price,
                    'pnl': fake_pnl,
                    'tp': pdata['tp_price'],
                    'sl': pdata['sl_price']
                })
                
            # Lempar semburan ke Web
            dashboard.update_state(
                virtual_balance=self.virtual_balance,
                total_profit=self.virtual_balance - 25.0,  # Baseline modal awal $25
                market_radar=radar_list,
                positions=active_pos_list
            )

            # ========================================================
            # 🛡️ PENCEGAHAN LIMIT API: PRE-FILTER TEKNIKAL
            # ========================================================
            # Hanya bangunkan AI jika koin tersebut BENAR-BENAR anjlok (Oversold Parah)
            koin_potensial = {}
            for koin, data in market_state.items():
                # Filter 1: RSI < 35 atau StochRSI < 15 (oversold)
                is_oversold = data['rsi'] < 35 or data['stoch_rsi'] < 15
                # Filter 2: Tolak downtrend brutal (jatuh bebas = jebakan SL)
                is_dangerous_downtrend = (
                    data['trend_ema'] == "Strong Downtrend" and data['adx'] > 25
                )
                # [BARU] Filter 3: Volume minimal 80% dari rata-rata (hindari dead market)
                has_volume = data.get('vol_ratio', 1.0) >= 0.8
                # [BARU] Filter 4: Cooldown — jangan re-beli koin yang baru kena Cut Loss
                loops_since_sl = self.loop_count - self.sl_cooldown.get(koin, -999)
                is_on_cooldown = loops_since_sl < config.SL_COOLDOWN_LOOPS

                if is_oversold and not is_dangerous_downtrend and has_volume and not is_on_cooldown:
                    koin_potensial[koin] = data

            if not koin_potensial:
                print("⏳ Status: Pasar Kripto membosankan (Tidak ada indikasi Oversold). Groq Llama-3 tertidur santai (Hemat Kuota Limit).")
            else:
                print(f"\n🧠 Ada {len(koin_potensial)} koin berpotensi! Membangunkan Groq Llama-3 untuk seleksi ketat...")
                ai_decisions = self.ai.analyze_opportunity(koin_potensial)
                
                if not ai_decisions:
                    print("⚠️ AI Memutuskan: Batal beli, risiko masih terlalu besar.")
                
                for dec in ai_decisions:
                    sym = dec.get('symbol')
                    action = dec.get('decision')
                    reason = dec.get('reason')
                    
                    if action == 'BUY' and sym in koin_potensial:
                        res_msg = f"🚀 Keputusan Final AI -> BELI {sym}\nAlasan: {reason}"
                        dashboard.add_log(res_msg)
                        print(res_msg)
                        
                        if len(self.virtual_portfolio) >= config.MAX_OPEN_POSITIONS:
                            skip_msg = f"⏭️ SKIP: Sudah ada {config.MAX_OPEN_POSITIONS} posisi aktif. Tunggu TP/SL dulu sebelum buka posisi baru."
                            dashboard.add_log(skip_msg)
                            print(skip_msg)
                            break  # Hentikan loop koin, tidak perlu cek selanjutnya
                        elif self.has_open_orders(sym):
                            dashboard.add_log(f"⏭️ SKIP PEMBELIAN: Dompet Binance Anda masih memegang {sym}.")
                        else:
                            current_price = market_state[sym]['price']
                            self.buy_with_safety_net(sym, current_price)
                            
            # ========================================================
                        
            # Tidur selama interval dan kembali menyapu market
            time.sleep(config.LOOP_INTERVAL_SECONDS)

if __name__ == "__main__":
    bot = BinanceBot()
    bot.run()

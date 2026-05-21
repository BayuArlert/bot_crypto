"""
Volume Anomaly Scanner — gunakan Binance Spot API (python-binance).
Deteksi koin yang volume-nya spike secara signifikan dibanding rata-rata.
Sinyal paling reliable untuk momentum entry di CEX.
"""
from binance.client import Client
from concurrent.futures import ThreadPoolExecutor, as_completed
import config


def get_active_usdt_symbols(client: Client) -> list[str]:
    """
    Ambil top N koin USDT by volume 24h dari Binance Spot.
    Filter: exclude stablecoin, leveraged token, volume < MIN_QUOTE_VOLUME_24H.
    Returns: list of symbol strings sorted by quoteVolume desc.
    """
    import time as _time
    tickers = None
    for attempt in range(3):
        try:
            tickers = client.get_ticker()
            break
        except Exception as e:
            wait = 2 ** attempt * 5  # 5s, 10s, 20s
            print(f"   [VolumeScanner] get_ticker() error (attempt {attempt+1}/3): {e}")
            if attempt < 2:
                _time.sleep(wait)

    if not tickers:
        return []

    filtered = []
    for t in tickers:
        sym  = t.get('symbol', '')
        qvol = float(t.get('quoteVolume', 0) or 0)

        # Harus berakhiran USDT
        if not sym.endswith('USDT'):
            continue

        # Exclude stablecoins
        base = sym.replace('USDT', '')
        if any(base == sc for sc in config.EXCLUDE_STABLECOINS):
            continue

        # Exclude leveraged tokens (suffix pattern)
        if any(sym.endswith(lt) for lt in config.EXCLUDE_LEVERAGED):
            continue

        # Exclude pegged/synthetic tokens (prefix pattern)
        pegged = getattr(config, 'EXCLUDE_PEGGED_PREFIXES', [])
        if any(base.startswith(p) for p in pegged):
            continue

        # Minimum volume 24h
        if qvol < config.MIN_QUOTE_VOLUME_24H:
            continue

        filtered.append({'symbol': sym, 'quoteVolume': qvol})

    # Sort by volume desc, ambil top N
    filtered.sort(key=lambda x: x['quoteVolume'], reverse=True)
    return [item['symbol'] for item in filtered[:config.MAX_SYMBOLS_TO_SCAN]]


def volume_spike_from_klines(symbol: str, klines_1h: list,
                           idx: int, price_change_15m: float = 0.0) -> dict | None:
    """
    Hitung volume spike pada indeks candle tertutup (untuk backtest).
    idx = indeks candle 1h yang baru close; butuh minimal 24 candle sebelumnya.
    """
    if idx < 24 or idx >= len(klines_1h):
        return None

    current_candle  = klines_1h[idx]
    history_candles = klines_1h[idx - 24:idx]

    try:
        current_vol_quote = float(current_candle[7])
        open_price        = float(current_candle[1])
        close_price       = float(current_candle[4])
        history_vols      = [float(k[7]) for k in history_candles if float(k[7]) > 0]
        if not history_vols:
            return None
        avg_volume_24h = sum(history_vols) / len(history_vols)
        if avg_volume_24h <= 0:
            return None

        spike_ratio     = current_vol_quote / avg_volume_24h
        price_change_1h = ((close_price - open_price) / open_price * 100
                           if open_price > 0 else 0)

        return {
            'symbol':              symbol,
            'current_volume_1h':   round(current_vol_quote, 2),
            'avg_volume_24h':      round(avg_volume_24h, 2),
            'spike_ratio':         round(spike_ratio, 2),
            'price':               close_price,
            'price_change_1h_pct': round(price_change_1h, 3),
            'price_change_15m_pct': round(price_change_15m, 3),
            'is_spike':            spike_ratio >= config.MIN_VOLUME_SPIKE_RATIO,
            'candle_time':         int(current_candle[0]),
        }
    except Exception:
        return None


def calculate_volume_spike(client: Client, symbol: str) -> dict | None:
    """
    Hitung volume spike ratio untuk satu koin.
    
    Metode:
    - Ambil 25 candle 1h terakhir
    - avg_volume_24h = rata-rata volume dari 24 candle sebelumnya (candle ke-2 s.d. ke-25)
    - current_volume_1h = volume candle 1h terakhir yang sudah CLOSED (candle ke-2 dari akhir)
    - spike_ratio = current_volume_1h / avg_volume_24h
    
    Returns dict atau None jika gagal / data tidak cukup.
    """
    try:
        klines = client.get_klines(
            symbol=symbol,
            interval=Client.KLINE_INTERVAL_1HOUR,
            limit=26  # 26 candle: 1 live + 25 closed
        )
        klines_15m = client.get_klines(
            symbol=symbol,
            interval=Client.KLINE_INTERVAL_15MINUTE,
            limit=3   # ambil 3 candle 15m: 1 live + 2 closed
        )
    except Exception as e:
        print(f"   [VolumeScanner] Klines error {symbol}: {e}")
        return None

    if len(klines) < 26:
        return None

    # Candle yang sudah closed — exclude candle paling akhir (masih berjalan)
    closed_klines = klines[:-1]          # 25 closed candles
    current_candle = closed_klines[-1]   # candle 1h yang baru saja closed
    history_candles = closed_klines[:-1] # 24 candle sebelumnya untuk avg

    try:
        current_vol_base  = float(current_candle[5])   # volume base
        current_vol_quote = float(current_candle[7])   # volume dalam quote (USDT)
        open_price        = float(current_candle[1])
        close_price       = float(current_candle[4])
        
        # Rata-rata volume quote per jam dari 24 candle lalu
        history_vols = [float(k[7]) for k in history_candles if float(k[7]) > 0]
        if not history_vols:
            return None
        avg_volume_24h = sum(history_vols) / len(history_vols)

        if avg_volume_24h <= 0:
            return None

        spike_ratio      = current_vol_quote / avg_volume_24h
        price_change_1h  = (close_price - open_price) / open_price * 100 if open_price > 0 else 0

        # 15m momentum — candle 15m terakhir yang sudah closed
        price_change_15m = 0.0
        try:
            if len(klines_15m) >= 2:
                c15 = klines_15m[-2]  # candle 15m closed terakhir
                o15 = float(c15[1])
                c15_close = float(c15[4])
                price_change_15m = (c15_close - o15) / o15 * 100 if o15 > 0 else 0
        except Exception:
            pass

        return {
            'symbol':              symbol,
            'current_volume_1h':   round(current_vol_quote, 2),
            'avg_volume_24h':      round(avg_volume_24h, 2),
            'spike_ratio':         round(spike_ratio, 2),
            'price':               close_price,
            'price_change_1h_pct': round(price_change_1h, 3),
            'price_change_15m_pct': round(price_change_15m, 3),
            'is_spike':            spike_ratio >= config.MIN_VOLUME_SPIKE_RATIO,
        }

    except Exception as e:
        print(f"   [VolumeScanner] Calc error {symbol}: {e}")
        return None


def scan_volume_anomalies(client: Client, symbols: list[str],
                          debug: bool = True) -> list[dict]:
    """
    Scan semua symbol untuk volume anomaly secara parallel.
    Filter: is_spike=True DAN current_volume_1h >= MIN_VOLUME_USDT_1H.
    Sort: by spike_ratio descending.
    Returns: list of volume spike dicts.
    """
    all_results = []

    with ThreadPoolExecutor(max_workers=10) as executor:
        future_map = {
            executor.submit(calculate_volume_spike, client, sym): sym
            for sym in symbols
        }
        for future in as_completed(future_map):
            try:
                data = future.result()
                if data is not None:
                    all_results.append(data)
            except Exception as e:
                sym = future_map[future]
                print(f"   [VolumeScanner] Future error {sym}: {e}")

    # Sort by spike_ratio untuk debug
    all_results.sort(key=lambda x: x['spike_ratio'], reverse=True)


    # Filter final
    results = [
        d for d in all_results
        if d['is_spike'] and d['current_volume_1h'] >= config.MIN_VOLUME_USDT_1H
    ]
    return results

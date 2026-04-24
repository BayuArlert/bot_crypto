import pandas as pd
import numpy as np

def hitung_indikator(df: pd.DataFrame) -> pd.DataFrame:
    """Modifikasi khusus Crypto (Sangat bergantung pada Volatilitas dan Oversold ekstrem)"""
    df = df.copy()

    # Pastikan kolom numerik (volume sering masuk sebagai string dari Binance API)
    df['volume'] = pd.to_numeric(df['volume'], errors='coerce')

    # EMA (Pendeteksi Tren Garis Besar)
    df['ema_20'] = df['close'].ewm(span=20, adjust=False).mean()
    df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()

    # RSI (Kekuatan Banteng / Beruang Momentum)
    delta = df['close'].diff()
    gain  = delta.clip(lower=0).rolling(14).mean()
    loss  = (-delta.clip(upper=0)).rolling(14).mean()
    rs    = gain / loss.replace(0, np.nan)
    df['rsi_14'] = 100 - (100 / (1 + rs))

    # ADX (Apakah koin ini sedang trending keras atau jalan di tempat?)
    high_diff = df['high'].diff()
    low_diff  = -df['low'].diff()

    pos_dm = np.where((high_diff > low_diff) & (high_diff > 0), high_diff, 0.0)
    neg_dm = np.where((low_diff > high_diff) & (low_diff > 0), low_diff, 0.0)

    tr1 = df['high'] - df['low']
    tr2 = (df['high'] - df['close'].shift()).abs()
    tr3 = (df['low']  - df['close'].shift()).abs()
    tr  = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    df['atr_14'] = tr.rolling(14).mean()
    atr14        = df['atr_14'].replace(0, np.nan)

    plus_di  = 100 * (pd.Series(pos_dm).rolling(14).mean() / atr14)
    minus_di = 100 * (pd.Series(neg_dm).rolling(14).mean() / atr14)
    dx       = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    df['adx_14'] = dx.rolling(14).mean()

    # Stochastic RSI (Untuk melacak pantulan instan crypto)
    rsi         = df['rsi_14']
    min_rsi     = rsi.rolling(14).min()
    max_rsi     = rsi.rolling(14).max()
    df['stoch_rsi'] = (rsi - min_rsi) / (max_rsi - min_rsi).replace(0, np.nan) * 100

    # Bollinger Bands (Sinyal bounce kuat saat harga menyentuh lower band)
    df['bb_mid']   = df['close'].rolling(20).mean()
    df['bb_std']   = df['close'].rolling(20).std()
    df['bb_upper'] = df['bb_mid'] + 2 * df['bb_std']
    df['bb_lower'] = df['bb_mid'] - 2 * df['bb_std']
    bb_range       = (df['bb_upper'] - df['bb_lower']).replace(0, np.nan)
    # bb_pct: 0 = harga di lower band (oversold kuat), 100 = harga di upper band (overbought)
    df['bb_pct']   = (df['close'] - df['bb_lower']) / bb_range * 100

    # Volume Ratio vs rata-rata 20 candle (>1.5 = volume spike = sinyal lebih kuat)
    df['vol_ma_20'] = df['volume'].rolling(20).mean()
    df['vol_ratio'] = df['volume'] / df['vol_ma_20'].replace(0, np.nan)

    return df


def get_market_summary(df: pd.DataFrame) -> dict:
    """Ringkasan indikator yang dikirim ke AI — menggunakan candle yang sudah CLOSED"""
    # iloc[-2] = candle yang sudah DITUTUP (closed) → data valid dan terkonfirmasi
    curr = df.iloc[-2]

    # Analisis Tipe Trend berdasarkan posisi harga vs EMA
    if curr['close'] > curr['ema_20'] and curr['ema_20'] > curr['ema_50']:
        trend = "Strong Uptrend"
    elif curr['close'] < curr['ema_20'] and curr['ema_20'] < curr['ema_50']:
        trend = "Strong Downtrend"
    else:
        trend = "Sideways / Choppy"

    # Warna candle yang sudah closed: bullish = close >= open
    candle_color = 'bullish' if curr['close'] >= curr['open'] else 'bearish'

    return {
        'price':        curr['close'],
        'rsi':          round(curr['rsi_14'],    2) if not pd.isna(curr['rsi_14'])    else 50,
        'stoch_rsi':    round(curr['stoch_rsi'], 2) if not pd.isna(curr['stoch_rsi']) else 50,
        'adx':          round(curr['adx_14'],    2) if not pd.isna(curr['adx_14'])    else 0,
        'trend_ema':    trend,
        'atr':          round(curr['atr_14'],    6) if not pd.isna(curr['atr_14'])    else 0,
        # bb_pct: 0=di lower band (oversold), 50=tengah, 100=upper band (overbought)
        'bb_pct':       round(curr['bb_pct'],    2) if not pd.isna(curr['bb_pct'])    else 50,
        # vol_ratio: 1.0=normal, >1.5=volume tinggi (sinyal kuat), <0.8=volume lesu
        'vol_ratio':    round(curr['vol_ratio'], 2) if not pd.isna(curr['vol_ratio']) else 1.0,
        # ema20: harga absolut EMA20 — untuk cek apakah harga benar-benar dekat EMA
        'ema20':        round(curr['ema_20'],    6) if not pd.isna(curr['ema_20'])    else curr['close'],
        # candle_color: konfirmasi arah candle terakhir yang closed
        'candle_color': candle_color,
    }


def detect_market_regime(market_state: dict) -> dict:
    """
    Menganalisis semua koin secara kolektif untuk menentukan kondisi pasar global.
    
    Returns dict:
        regime      : 'BEAR' | 'BULL' | 'RANGE'
        description : Penjelasan singkat kondisi pasar
        uptrend_pct : % koin yang sedang uptrend
        downtrend_pct: % koin yang sedang downtrend
        avg_adx     : Rata-rata ADX semua koin (kekuatan trend global)
        avg_rsi     : Rata-rata RSI semua koin
    """
    if not market_state:
        return {
            'regime': 'RANGE',
            'description': 'Data tidak tersedia, mode default RANGE',
            'uptrend_pct': 0,
            'downtrend_pct': 0,
            'avg_adx': 0,
            'avg_rsi': 50,
        }

    total        = len(market_state)
    uptrend_cnt  = 0
    down_cnt     = 0
    adx_vals     = []
    rsi_vals     = []

    for data in market_state.values():
        trend = data.get('trend_ema', 'Sideways / Choppy')
        adx   = data.get('adx', 0)
        rsi   = data.get('rsi', 50)

        if trend == 'Strong Uptrend':
            uptrend_cnt += 1
        elif trend == 'Strong Downtrend':
            down_cnt += 1

        adx_vals.append(adx)
        rsi_vals.append(rsi)

    uptrend_pct   = (uptrend_cnt / total) * 100
    downtrend_pct = (down_cnt / total) * 100
    avg_adx       = sum(adx_vals) / len(adx_vals)
    avg_rsi       = sum(rsi_vals) / len(rsi_vals)

    # ==============================================================
    # ATURAN PENENTUAN REGIME
    # ==============================================================
    # BEAR: Mayoritas downtrend kuat — bot diam, lindungi modal
    if downtrend_pct >= 60 and avg_adx >= 35:
        regime      = 'BEAR'
        description = f"🐻 BEAR MARKET — {int(downtrend_pct)}% koin downtrend, ADX rata {avg_adx:.1f}. Bot DIAM lindungi modal."

    # BULL: Mayoritas uptrend — strategi trend following (pullback ke EMA)
    elif uptrend_pct >= 55:
        regime      = 'BULL'
        description = f"🐂 BULL MARKET — {int(uptrend_pct)}% koin uptrend. Bot cari entry pullback ke EMA."

    # RANGE: Pasar sideways / mixed — strategi bounce mean reversion
    else:
        regime      = 'RANGE'
        description = f"📊 RANGING MARKET — Pasar mixed/sideways, ADX {avg_adx:.1f}. Bot cari bounce di BB bawah."

    return {
        'regime':        regime,
        'description':   description,
        'uptrend_pct':   round(uptrend_pct,   1),
        'downtrend_pct': round(downtrend_pct, 1),
        'avg_adx':       round(avg_adx,       1),
        'avg_rsi':       round(avg_rsi,       1),
    }

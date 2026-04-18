import pandas as pd
import numpy as np

def hitung_indikator(df: pd.DataFrame) -> pd.DataFrame:
    """Modifikasi khusus Crypto (Sangat bergantung pada Volatilitas dan Oversold ekstrem)"""
    df = df.copy()
    
    # EMA (Pendeteksi Tren Garis Besar)
    df['ema_20'] = df['close'].ewm(span=20, adjust=False).mean()
    df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
    
    # RSI (Kekuatan Banteng / Beruang Momentum)
    delta = df['close'].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    df['rsi_14'] = 100 - (100 / (1 + rs))
    
    # ADX (Apakah koin ini sedang trending keras atau jalan di tempat?)
    high_diff = df['high'].diff()
    low_diff = -df['low'].diff()
    
    pos_dm = np.where((high_diff > low_diff) & (high_diff > 0), high_diff, 0.0)
    neg_dm = np.where((low_diff > high_diff) & (low_diff > 0), low_diff, 0.0)
    
    tr1 = df['high'] - df['low']
    tr2 = (df['high'] - df['close'].shift()).abs()
    tr3 = (df['low'] - df['close'].shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    df['atr_14'] = tr.rolling(14).mean()
    atr14 = df['atr_14'].replace(0, np.nan)
    
    plus_di = 100 * (pd.Series(pos_dm).rolling(14).mean() / atr14)
    minus_di = 100 * (pd.Series(neg_dm).rolling(14).mean() / atr14)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    df['adx_14'] = dx.rolling(14).mean()

    # Stochastic RSI (Untuk melacak pantulan instan crypto)
    rsi = df['rsi_14']
    min_rsi = rsi.rolling(14).min()
    max_rsi = rsi.rolling(14).max()
    df['stoch_rsi'] = (rsi - min_rsi) / (max_rsi - min_rsi).replace(0, np.nan) * 100

    return df

def get_market_summary(df: pd.DataFrame) -> dict:
    """Ringkasan yang akan dibaca oleh Gemini"""
    curr = df.iloc[-1]
    
    # Analisis Tipe Trend
    if curr['close'] > curr['ema_20'] and curr['ema_20'] > curr['ema_50']:
        trend = "Strong Uptrend"
    elif curr['close'] < curr['ema_20'] and curr['ema_20'] < curr['ema_50']:
        trend = "Strong Downtrend"
    else:
        trend = "Sideways / Choppy"
        
    return {
        'price': curr['close'],
        'rsi': round(curr['rsi_14'], 2) if not pd.isna(curr['rsi_14']) else 50,
        'stoch_rsi': round(curr['stoch_rsi'], 2) if not pd.isna(curr['stoch_rsi']) else 50,
        'adx': round(curr['adx_14'], 2) if not pd.isna(curr['adx_14']) else 0,
        'trend_ema': trend
    }

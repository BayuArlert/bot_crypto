"""
Multi-Signal Scorer — gabungkan semua signal menjadi satu skor 0-10.
Tidak ada indikator teknikal lagging. Semua berbasis real market activity.
"""
import config


def score_opportunity(
    symbol: str,
    volume_data: dict,
    in_sm_inflow: bool,
    sm_inflow_usd: float,
    sm_traders: int,
    in_social_hype: bool,
    hype_score: float,
    in_trending: bool,
) -> tuple[int, list[str]]:
    """
    Scoring engine berbasis momentum dan smart money activity.
    
    Skor (total max 10):
    
    [VOLUME ANOMALY — max 4 poin, WAJIB ada]
      spike_ratio >= 3x   : +2
      spike_ratio >= 5x   : +1 bonus
      spike_ratio >= 10x  : +1 bonus lagi
      price_change_1h > 0 : +1 (harga ikut naik, bukan dump volume)
    
    [SMART MONEY — max 3 poin]
      in_sm_inflow        : +2
      sm_traders >= min   : +1 bonus
      sm_inflow >= $100K  : +0.5 bonus
    
    [SOCIAL & TRENDING — max 2 poin]
      in_social_hype      : +1
      hype_score >= 500   : +0.5 bonus
      in_trending         : +1
    
    [MOMENTUM KONFIRMASI — max 1 poin]
      price_change_1h > 1%: +0.5
      price_change_1h > 3%: +0.5 lagi
    """
    score   = 0
    reasons = []

    spike_ratio      = volume_data.get('spike_ratio', 0)
    price_change_1h  = volume_data.get('price_change_1h_pct', 0)
    price_change_15m = volume_data.get('price_change_15m_pct', 0)

    # ── Knockout 1: volume harus spike ──
    if spike_ratio < config.MIN_VOLUME_SPIKE_RATIO:
        return 0, [f"Volume spike {spike_ratio:.1f}x < minimum {config.MIN_VOLUME_SPIKE_RATIO}x"]

    # ── Knockout 2: harga HARUS positif atau flat saat volume spike ──
    # Volume spike + harga turun = distribusi/selling bukan akumulasi
    if price_change_1h < 0 and price_change_15m < 0:
        # Keduanya negatif = distribusi jelas
        return 0, [f"Distribusi: 1h {price_change_1h:.2f}% & 15m {price_change_15m:.2f}%"]
    if price_change_1h < -1.0:
        # 1h turun lebih dari 1% = terlalu bearish
        return 0, [f"Bearish kuat: harga 1h {price_change_1h:.2f}%"]

    # ── Volume scoring ──
    score += 2
    reasons.append(f"Volume spike {spike_ratio:.1f}x")
    if spike_ratio >= 3:
        score += 1
        reasons.append(f"Spike kuat ({spike_ratio:.1f}x >= 3x)")
    if spike_ratio >= 5:
        score += 1
        reasons.append(f"Momentum sangat kuat ({spike_ratio:.1f}x)")
    if spike_ratio >= 10:
        score += 1
        reasons.append(f"Exceptional momentum ({spike_ratio:.1f}x)")
    if price_change_1h > 0:
        score += 1
        reasons.append(f"Harga ikut naik +{price_change_1h:.1f}%")

    # ── Smart Money scoring ──
    if in_sm_inflow:
        score += 2
        reasons.append(f"SM inflow ${sm_inflow_usd:,.0f} | {sm_traders} wallets")
        if sm_traders >= config.SM_MIN_TRADERS:
            score += 1
            reasons.append(f"Multiple SM wallets ({sm_traders})")
        if sm_inflow_usd >= 100_000:
            score += 0.5
            reasons.append("Large SM inflow (>$100K)")

    # ── Social & Trending scoring ──
    if in_social_hype:
        score += 1
        reasons.append(f"Positive social hype (score: {hype_score:.0f})")
        if hype_score >= 500:
            score += 0.5
            reasons.append("Viral social buzz")
    if in_trending:
        score += 1
        reasons.append("Trending di Binance")

    # ── Momentum konfirmasi ──
    if price_change_1h > 1:
        score += 0.5
        reasons.append(f"Momentum positif +{price_change_1h:.1f}%")
    if price_change_1h > 3:
        score += 0.5
        reasons.append(f"Momentum kuat +{price_change_1h:.1f}%")

    return round(min(score, 10)), reasons

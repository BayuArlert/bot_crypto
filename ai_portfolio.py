import json
from groq import Groq

# ─────────────────────────────────────────────────────────────────
# SCORING ENGINE — Deterministik, transparan, tidak bergantung LLM
# Setiap kondisi diberi bobot. Trade hanya masuk jika skor >= MIN_SCORE
# ─────────────────────────────────────────────────────────────────

def score_bull_setup(data: dict) -> tuple[int, list[str]]:
    """
    Hitung skor teknikal untuk setup BULL Pullback ke EMA20.
    Skor maksimal = 10. Trade minimal skor 7.
    Returns: (score, list_of_reasons)
    """
    score = 0
    reasons = []

    # Syarat WAJIB (Knockout) — jika gagal, skor langsung 0
    if data.get('trend_ema') != 'Strong Uptrend':
        return 0, ['❌ trend bukan Strong Uptrend']
    if not (40 <= data.get('rsi', 999) <= 55):
        return 0, [f"❌ RSI={data.get('rsi')} di luar zona pullback 40-55"]
    if data.get('rsi_slope', 0) <= 0:
        return 0, [f"❌ rsi_slope={data.get('rsi_slope')} <= 0 (momentum masih turun)"]
    if data.get('candle_color') != 'bullish':
        return 0, ['❌ candle bearish (pisau jatuh)']
    if data.get('macd_hist', 0) <= 0:
        return 0, [f"❌ macd_hist={data.get('macd_hist'):.5f} <= 0"]
    if data.get('htf_4h_trend') == 'Strong Downtrend':
        return 0, ['❌ 4h downtrend — melawan tren besar']
    if data.get('htf_1h_trend') == 'Strong Downtrend':
        return 0, ['❌ 1h downtrend — melawan arus']
    if data.get('adx', 0) < 20:
        return 0, [f"❌ ADX={data.get('adx')} < 20 — trend lemah"]

    # EMA Proximity (wajib: harga max 0.5% di atas EMA20)
    price = data.get('price', 0)
    ema20 = data.get('ema20', price)
    if ema20 > 0 and price > ema20 * 1.005:
        return 0, [f"❌ price={price:.4f} terlalu jauh dari EMA20={ema20:.4f}"]

    # ── Poin Bonus (semua syarat dasar sudah terpenuhi) ──
    score = 6  # base score jika semua syarat wajib terpenuhi
    reasons.append(f"RSI={data.get('rsi')} pullback | slope={data.get('rsi_slope')} | MACD+")

    rsi_slope = data.get('rsi_slope', 0)
    vol_ratio = data.get('vol_ratio', 0)
    body_pct  = data.get('body_pct', 0)
    lower_shadow = data.get('lower_shadow_pct', 0)
    adx = data.get('adx', 0)

    if rsi_slope > 2:
        score += 1; reasons.append(f"momentum kuat (slope={rsi_slope})")
    if vol_ratio >= 1.3:
        score += 1; reasons.append(f"volume tinggi ({vol_ratio:.1f}x)")
    elif vol_ratio >= 1.1:
        score += 0.5
    if body_pct > 50:
        score += 0.5; reasons.append(f"candle kuat (body={body_pct}%)")
    if lower_shadow > 20:
        score += 0.5; reasons.append(f"rejection wick bawah ({lower_shadow}%)")
    if adx > 30:
        score += 0.5; reasons.append(f"ADX kuat ({adx})")
    if data.get('htf_1h_trend') == 'Strong Uptrend':
        score += 0.5; reasons.append("1h juga uptrend")
    if data.get('htf_4h_trend') == 'Strong Uptrend':
        score += 0.5; reasons.append("4h juga uptrend")

    return round(score), reasons


def score_range_setup(data: dict) -> tuple[int, list[str]]:
    """
    Hitung skor teknikal untuk setup RANGE Bounce dari Lower BB.
    Skor maksimal = 10. Trade minimal skor 7.
    Returns: (score, list_of_reasons)
    """
    score = 0
    reasons = []

    rsi       = data.get('rsi', 999)
    stoch_rsi = data.get('stoch_rsi', 999)
    bb_pct    = data.get('bb_pct', 100)
    adx       = data.get('adx', 0)
    rsi_slope = data.get('rsi_slope', 0)
    candle    = data.get('candle_color', 'bearish')
    lower_sh  = data.get('lower_shadow_pct', 0)

    # Syarat WAJIB (Knockout) — jika gagal, skor langsung 0
    if not (rsi < 38 and stoch_rsi < 25):
        return 0, [f"❌ Oversold tidak terpenuhi KEDUANYA: RSI={rsi}(butuh<38) Stoch={stoch_rsi}(butuh<25)"]
    if candle != 'bullish':
        return 0, ['❌ candle bearish — JANGAN beli saat masih turun (pisau jatuh!)']
    if rsi_slope <= 0:
        return 0, [f"❌ rsi_slope={rsi_slope} <= 0 — momentum belum berbalik, terlalu dini"]
    if lower_sh <= 10:
        return 0, [f"❌ lower_shadow={lower_sh}% <= 10% — tidak ada bukti rejection/pembeli di bawah"]
    if bb_pct >= 25:
        return 0, [f"❌ bb_pct={bb_pct:.1f} >= 25 — harga belum di lower band"]
    if data.get('htf_4h_trend') == 'Strong Downtrend':
        return 0, ['❌ 4h downtrend — melawan tren besar, sangat berbahaya']
    if data.get('htf_1h_trend') == 'Strong Downtrend':
        return 0, ['❌ 1h downtrend — melawan arus 1 jam']
    if adx >= 35:
        return 0, [f"❌ ADX={adx} >= 35 — tren terlalu kuat, bukan sideways sejati"]
    if data.get('trend_ema') == 'Strong Downtrend' and adx > 30:
        return 0, [f"❌ downtrend kuat ADX={adx} — jangan lawan"]

    # ── Poin Bonus ──
    score = 6  # base score
    reasons.append(f"RSI={rsi} Stoch={stoch_rsi} | candle bullish | slope={rsi_slope} | shadow={lower_sh}%")

    vol_ratio = data.get('vol_ratio', 0)
    body_pct  = data.get('body_pct', 0)

    if lower_sh > 30:
        score += 1; reasons.append(f"rejection kuat (shadow={lower_sh}%)")
    elif lower_sh > 20:
        score += 0.5

    if rsi_slope > 2:
        score += 1; reasons.append(f"momentum berbalik kuat (slope={rsi_slope})")
    elif rsi_slope > 1:
        score += 0.5

    if vol_ratio >= 1.3:
        score += 1; reasons.append(f"volume konfirmasi ({vol_ratio:.1f}x)")
    elif vol_ratio >= 1.1:
        score += 0.5

    if body_pct > 40:
        score += 0.5; reasons.append(f"candle kuat (body={body_pct}%)")

    if stoch_rsi < 10:
        score += 0.5; reasons.append(f"stoch sangat oversold ({stoch_rsi})")

    if adx < 20:
        score += 0.5; reasons.append(f"pasar benar-benar sideways (ADX={adx})")

    return round(score), reasons


# ─────────────────────────────────────────────────────────────────
# PORTFOLIO MANAGER — Scoring utama + AI sebagai second opinion
# ─────────────────────────────────────────────────────────────────

MIN_SCORE_TO_TRADE = 7   # Skor minimum untuk masuk trade (dari 10)

class AIPortfolioManager:
    def __init__(self, api_key: str):
        self.client = Groq(api_key=api_key)
        self.model  = 'llama-3.3-70b-versatile'

    def analyze_opportunity(self, market_data: dict, regime: dict) -> list[dict]:
        """
        Sistem hybrid:
        1. Scoring Engine deterministik — evaluasi semua kandidat, ambil yang skor >= MIN_SCORE
        2. AI Second Opinion — konfirmasi akhir hanya untuk kandidat terbaik
        
        Jika AI tidak bisa dihubungi → fallback ke scoring saja.
        """
        regime_name = regime.get('regime', 'RANGE')

        scored_candidates = []

        # ── Fase 1: Scoring Deterministik ──
        for sym, data in market_data.items():
            if regime_name == 'BULL':
                score, reasons = score_bull_setup(data)
            else:
                score, reasons = score_range_setup(data)

            reason_str = ' | '.join(reasons)
            print(f"   [SCORE] {sym}: {score}/10 — {reason_str}")

            if score >= MIN_SCORE_TO_TRADE:
                scored_candidates.append({
                    'symbol':     sym,
                    'score':      score,
                    'reason':     reason_str,
                    'data':       data,
                })

        if not scored_candidates:
            print("   [SCORE] Tidak ada kandidat yang mencapai skor minimum.")
            return []

        # Urutkan dari skor tertinggi, ambil top 1
        scored_candidates.sort(key=lambda x: x['score'], reverse=True)
        best = scored_candidates[0]

        print(f"\n   [SCORE WINNER] {best['symbol']} skor {best['score']}/10 → AI second opinion...")

        # ── Fase 2: AI Second Opinion (konfirmasi akhir) ──
        try:
            ai_result = self._ai_confirm(best, regime_name, regime)
            if ai_result:
                return ai_result
            else:
                # AI tidak yakin tapi skor tinggi — percaya scoring
                print(f"   [HYBRID] AI ragu, tapi skor {best['score']}/10 → TRUST SCORING")
                return [{
                    'symbol':     best['symbol'],
                    'decision':   'BUY',
                    'confidence': best['score'],
                    'reason':     f"[SCORING] {best['reason']}",
                }]
        except Exception as e:
            # AI error → fallback ke scoring saja
            print(f"   [FALLBACK] AI error ({e}) → pakai scoring deterministik")
            return [{
                'symbol':     best['symbol'],
                'decision':   'BUY',
                'confidence': best['score'],
                'reason':     f"[SCORING ONLY] {best['reason']}",
            }]

    def _ai_confirm(self, candidate: dict, regime_name: str, regime: dict) -> list[dict]:
        """
        AI hanya dikonsultasi untuk 1 kandidat terbaik sebagai second opinion.
        Lebih fokus = keputusan lebih akurat.
        """
        sym  = candidate['symbol']
        data = candidate['data']
        score = candidate['score']

        if regime_name == 'BULL':
            checklist = """
Konfirmasi BULL Pullback ke EMA20. Semua syarat wajib harus terpenuhi:
- trend_ema = 'Strong Uptrend', RSI 40-55, rsi_slope > 0
- candle_color = 'bullish', macd_hist > 0
- htf_1h & htf_4h BUKAN 'Strong Downtrend'
- adx > 20, price <= ema20 * 1.005
"""
        else:
            checklist = """
Konfirmasi RANGE Bounce dari Lower BB. Semua syarat wajib harus terpenuhi:
- RSI < 38 DAN stoch_rsi < 25 (keduanya!)
- candle_color = 'bullish' (WAJIB, jangan beli candle merah)
- rsi_slope > 0 (momentum sudah berbalik)
- lower_shadow_pct > 10 (ada rejection/wick bawah)
- bb_pct < 25 (benar-benar di lower band)
- adx < 35, htf_1h & htf_4h BUKAN 'Strong Downtrend'
"""

        prompt = f"""
Anda adalah AI validator trading crypto. Scoring system telah memberi {sym} skor {score}/10.
Tugasmu: konfirmasi apakah setup ini layak BUY atau sebaiknya SKIP.

{checklist}

DATA {sym}:
{json.dumps(data, indent=2)}

Evaluasi satu per satu: apakah ada syarat yang dilanggar?
Jika TIDAK ada yang dilanggar → BUY dengan confidence={score}
Jika ADA yang dilanggar → SKIP dengan jelaskan alasannya

JSON Output:
{{"decisions":[{{"symbol":"{sym}","decision":"BUY","confidence":{score},"reason":"konfirmasi singkat"}}]}}
Atau: {{"decisions":[{{"symbol":"{sym}","decision":"SKIP","confidence":0,"reason":"alasan spesifik"}}]}}
"""
        completion = self.client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Kamu adalah validator trade crypto. "
                        "Output HANYA JSON valid. Tidak ada teks di luar JSON."
                    )
                },
                {"role": "user", "content": prompt}
            ],
            model=self.model,
            temperature=0.1,
            response_format={"type": "json_object"}
        )

        result_text = completion.choices[0].message.content
        parsed      = json.loads(result_text)
        decisions   = parsed.get("decisions", [])

        # Filter: hanya return BUY, SKIP diabaikan (scoring sudah approve)
        buy_decisions = [d for d in decisions if d.get('decision') == 'BUY']
        skip_decisions = [d for d in decisions if d.get('decision') == 'SKIP']

        if skip_decisions:
            reason = skip_decisions[0].get('reason', '?')
            print(f"   [AI SKIP] {sym}: {reason}")
            print(f"   [DEBUG SCORE] {sym}: raw={score}, rounded={round(score)}, override_threshold=9")
            # Jika skor sangat tinggi (>=9), override AI yang ragu
            if score >= 9:
                print(f"   [OVERRIDE] Skor {score}/10 terlalu tinggi, override AI SKIP → BUY")
                return [{'symbol': sym, 'decision': 'BUY', 'confidence': round(score),
                         'reason': f"[HIGH SCORE OVERRIDE] {candidate['reason']}"}]
            return []  # AI SKIP + skor normal → ikuti AI

        return buy_decisions

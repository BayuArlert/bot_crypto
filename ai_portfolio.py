import json
from groq import Groq

class AIPortfolioManager:
    def __init__(self, api_key: str):
        self.client = Groq(api_key=api_key)
        self.model  = 'llama-3.3-70b-versatile'

    def analyze_opportunity(self, market_data: dict, regime: dict) -> list[dict]:
        """
        AI menerima konteks regime pasar global sehingga keputusannya
        lebih relevan dengan kondisi aktual.
        """
        regime_name = regime.get('regime', 'RANGE')
        regime_desc = regime.get('description', '')
        avg_adx     = regime.get('avg_adx', 0)
        avg_rsi     = regime.get('avg_rsi', 50)

        if regime_name == 'BULL':
            strategy_guide = """
PENTING: Setiap trade kena fee 0.2% round-trip. Minimum RR yang layak adalah 2.0:1.
Tolak setup dengan potensi TP < 2x SL, tidak peduli seberapa bagus indikator lainnya.

REGIME: BULL MARKET — Strategi TREND FOLLOWING (Pullback ke EMA20).

SYARAT BUY — semua wajib terpenuhi:
  [1] trend_ema = 'Strong Uptrend' di 15m  ← WAJIB, tidak bisa dikecualikan
  [2] RSI antara 40–55                      ← zona pullback sehat
  [3] rsi_slope > 0                         ← WAJIB: momentum harus sudah mulai naik!
  [4] candle_color = 'bullish'              ← WAJIB: harus ada tanda reversal/buying
  [5] htf_1h_trend BUKAN 'Strong Downtrend' ← jangan lawan tren 1 jam
  [6] htf_4h_trend BUKAN 'Strong Downtrend' ← WAJIB: jangan lawan tren 4 jam (tren besar)
  [7] vol_ratio >= 1.0                      ← volume tidak lesu
  [8] adx > 20                              ← trend punya tenaga
  [9] macd_hist > 0                         ← WAJIB: histogram MACD harus positif (momentum bullish)

LARANGAN (langsung SKIP tanpa pengecualian):
  ✗ rsi_slope <= 0      → momentum masih turun (pisau jatuh), JANGAN DITANGKAP!
  ✗ RSI > 55            → sudah terlalu naik, telat entry
  ✗ adx < 15            → pasar terlalu lemah untuk trend following
  ✗ htf_1h_trend = 'Strong Downtrend' → melawan arus 1 jam
  ✗ htf_4h_trend = 'Strong Downtrend' → melawan arus besar 4 jam
  ✗ macd_hist <= 0      → momentum belum terkonfirmasi secara MACD

SCORING:
  8 = syarat [1]–[9] semua terpenuhi
  9 = semua syarat terpenuhi + rsi_slope > 2 + body_pct > 50 + macd_hist positif kuat
  Jika ada 1 syarat yang tidak terpenuhi → SKIP, bukan BUY
"""
        else:  # RANGE
            strategy_guide = """
PENTING: Setiap trade kena fee 0.2% round-trip. Minimum RR yang layak adalah 2.0:1.
Tolak setup dengan potensi TP < 2x SL, tidak peduli seberapa bagus indikator lainnya.

REGIME: RANGING/SIDEWAYS MARKET — Strategi MEAN REVERSION (Bounce Lower BB).

SYARAT BUY — semua wajib terpenuhi:
  [1] bb_pct < 30                            ← harga harus di dekat lower band
  [2] RSI < 35 DAN stoch_rsi < 20           ← oversold yang terkonfirmasi
  [3] candle_color = 'bullish'              ← bounce harus sudah mulai terlihat
  [4] htf_1h_trend BUKAN 'Strong Downtrend' ← jangan lawan tren 1 jam
  [5] htf_4h_trend BUKAN 'Strong Downtrend' ← WAJIB: jangan lawan tren besar 4 jam
  [6] adx < 30 (diutamakan)                 ← trend lemah = pantul lebih aman

LARANGAN (langsung SKIP tanpa pengecualian):
  ✗ bb_pct > 30          → harga belum di lower band, terlalu dini
  ✗ stoch_rsi > 25       → momentum belum benar-benar oversold
  ✗ trend_ema = 'Strong Downtrend' AND adx > 35 → downtrend kuat, jangan lawan
  ✗ htf_4h_trend = 'Strong Downtrend' → melawan tren besar 4 jam, sangat berbahaya

SCORING:
  8 = syarat [1]–[5] semua terpenuhi
  9 = semua syarat terpenuhi + vol_ratio > 1.2 + lower_shadow_pct > 30 (ada rejection)
  Jika ada 1 syarat yang tidak terpenuhi → SKIP, bukan BUY
"""

        n_candidates = len(market_data)
        prompt = f"""
Anda adalah AI Crypto Scalper Senior. Misi utama Anda:
HANYA menyetujui trade dengan setup SEMPURNA. Tolak semua yang meragukan.

MOTTO: "Better miss a trade than take a bad one."

KONDISI PASAR GLOBAL:
- Regime : {regime_name} — {regime_desc}
- ADX avg: {avg_adx} | RSI avg: {avg_rsi}
- Jumlah kandidat yang sudah lolos pre-filter: {n_candidates} koin
  (Karena pre-filter sudah ketat, kandidat ini SEHARUSNYA layak — namun tetap evaluasi ulang secara kritis)

{strategy_guide}

DATA KOIN KANDIDAT:
{json.dumps(market_data, indent=2)}

LEGENDA INDIKATOR:
- rsi              : momentum (< 35 = oversold, > 65 = overbought)
- rsi_slope        : arah momentum (> 0 artinya mulai naik, < 0 artinya masih turun)
- body_pct         : seberapa kuat body candle (> 50% berarti dominan/tegas)
- lower_shadow_pct : penolakan harga bawah (> 30% berarti ada support kuat)
- stoch_rsi        : momentum cepat (< 15 = sangat oversold)
- bb_pct           : posisi di BB (0 = lower band, 50 = tengah, 100 = upper band)
- vol_ratio        : rasio volume vs rata-rata 20 candle (> 1.2 kuat, < 0.8 lesu)
- adx              : kekuatan trend (> 40 trending keras, < 20 sideways)
- ema20            : harga EMA20 absolut (bandingkan dengan 'price' untuk cek proximity)
- candle_color     : warna candle terakhir yang closed ('bullish' = hijau, 'bearish' = merah)
- htf_1h_trend     : konfirmasi tren dari timeframe 1 jam (prioritas TINGGI)
- htf_4h_trend     : konfirmasi tren dari timeframe 4 jam (prioritas SANGAT TINGGI — tren besar)
- macd_hist        : histogram MACD (> 0 = momentum bullish terkonfirmasi, < 0 = bearish/pelemahan)

INSTRUKSI:
1. Cek setiap koin terhadap checklist syarat di atas satu per satu
2. Jika ADA SATU LARANGAN yang dilanggar → langsung SKIP koin tersebut
3. Pilih MAKSIMAL 1 koin dengan setup paling solid
4. Confidence 8+ HANYA jika SEMUA syarat wajib terpenuhi tanpa terkecuali
5. Tulis reason dalam 1 kalimat: sebutkan 2-3 faktor kunci yang menentukan keputusan
6. Jika tidak ada koin yang lolos semua syarat → kembalikan decisions kosong

JSON Output (tanpa teks di luar JSON):
{{"decisions":[{{"symbol":"XXXUSDT","decision":"BUY","confidence":8,"reason":"RSI 45 pullback ke EMA20, candle bullish, 1h uptrend, vol 1.3x"}}]}}
Jika tidak ada: {{"decisions":[]}}
"""
        try:
            completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Kamu adalah sistem analisis trading crypto berbasis JSON. "
                            "Tugasmu: evaluasi data indikator teknikal dan putuskan apakah layak BUY atau SKIP. "
                            "Output HANYA berupa JSON valid sesuai format yang diminta. "
                            "Jangan tambahkan teks, penjelasan, atau komentar di luar JSON."
                        )
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                model=self.model,
                temperature=0.1,
                response_format={"type": "json_object"}
            )

            result_text = completion.choices[0].message.content
            parsed_data = json.loads(result_text)
            return parsed_data.get("decisions", [])

        except Exception as e:
            print(f"⚠️ Kegagalan Koneksi Groq Llama-3: {e}")
            return []

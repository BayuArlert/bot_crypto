import json
from groq import Groq

class AIPortfolioManager:
    def __init__(self, api_key: str):
        self.client = Groq(api_key=api_key)
        self.model  = 'llama-3.1-8b-instant'

    def analyze_opportunity(self, market_data: dict, regime: dict) -> list[dict]:
        """
        AI menerima konteks regime pasar global sehingga keputusannya
        lebih relevan dengan kondisi aktual.
        """
        regime_name = regime.get('regime', 'RANGE')
        regime_desc = regime.get('description', '')
        avg_adx     = regime.get('avg_adx', 0)
        avg_rsi     = regime.get('avg_rsi', 50)

        # Panduan strategi berdasarkan regime yang dikirim ke AI
        if regime_name == 'BULL':
            strategy_guide = """
REGIME: BULL MARKET — Strategi TREND FOLLOWING.
- Cari koin yang sedang pullback (RSI 40-55) ke EMA20 dalam uptrend
- bb_pct boleh 30-60 (tidak harus di lower band seperti di RANGE)
- adx > 20 dan trend Strong Uptrend adalah KONDISI IDEAL
- htf_1h_trend harus Uptrend atau Sideways (BUKAN Downtrend)
- Hindari koin yang RSI-nya sudah > 70 (overbought, sudah telat entry)
LARANGAN: Jangan beli koin yang masih Strong Downtrend meski RSI oversold.
"""
        else:  # RANGE
            strategy_guide = """
REGIME: RANGING/SIDEWAYS MARKET — Strategi MEAN REVERSION.
- Cari koin yang oversold ekstrem: RSI < 35 DAN stoch_rsi < 15
- bb_pct HARUS < 35 (harga dekat lower Bollinger Band)
- adx < 25 DIUTAMAKAN (trend lemah = pantul lebih aman)
- htf_1h_trend harus Sideways atau Uptrend (BUKAN Strong Downtrend)
LARANGAN: Jangan beli jika Strong Downtrend + adx > 40.
"""

        prompt = f"""
Anda adalah AI Crypto Scalper Profesional. Analisis peluang trading berdasarkan kondisi pasar saat ini.

KONDISI PASAR GLOBAL SAAT INI:
- Regime: {regime_name} — {regime_desc}
- Rata-rata ADX semua koin: {avg_adx}
- Rata-rata RSI semua koin: {avg_rsi}

{strategy_guide}

DATA KOIN KANDIDAT (Candle Closed, sudah lolos pre-filter teknikal):
{json.dumps(market_data, indent=2)}

PANDUAN INDIKATOR:
- rsi: nilai momentum (< 35 = oversold, > 65 = overbought)
- stoch_rsi: momentum cepat (< 15 = sangat oversold)
- bb_pct: posisi harga di Bollinger Band (0 = lower, 100 = upper)
- vol_ratio: kekuatan volume (> 1.2 = kuat, < 0.8 = lemah — hindari)
- adx: kekuatan trend (> 40 = trending kuat, < 20 = sideways)
- htf_1h_trend: konfirmasi timeframe 1 jam

Pilih MAKSIMAL 1-2 koin terbaik. Sertakan confidence 1-10 (min 7 untuk BUY).
Jika tidak ada setup yang valid, kembalikan decisions kosong.

JSON Output WAJIB:
{{"decisions":[{{"symbol":"X","decision":"BUY","confidence":8,"reason":"alasan singkat"}}]}}
Jika tidak ada: {{"decisions":[]}}
"""
        try:
            completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": "You are a professional JSON Crypto Bot. You MUST output ONLY valid JSON. Never include text outside JSON."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                model=self.model,
                temperature=0.2,
                response_format={"type": "json_object"}
            )

            result_text = completion.choices[0].message.content
            parsed_data = json.loads(result_text)
            return parsed_data.get("decisions", [])

        except Exception as e:
            print(f"⚠️ Kegagalan Koneksi Groq Llama-3: {e}")
            return []

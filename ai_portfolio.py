import json
from groq import Groq

class AIPortfolioManager:
    def __init__(self, api_key: str):
        # Menyambung langsung ke otak Llama-3.1 milik Groq
        self.client = Groq(api_key=api_key)
        # Menggunakan seri Llama 8B (Limit Kuotanya jauh lebih raksasa)
        self.model = 'llama-3.3-70b-versatile'  # [UPGRADE] Model 70B jauh lebih akurat untuk analisis entry
        
    def analyze_opportunity(self, market_data: dict) -> list[dict]:
        """
        Groq sangat membutuhkan format instruksi JSON Object yang jelas di level Sistem.
        """
        prompt = f"""
Anda adalah AI Crypto Scalper Berkecepatan Tinggi.
Anda beroperasi di Timeframe 15-Menit dengan target Take Profit +1.5% dan Stop Loss -1%.
Misi Anda: Cari peluang bounce/reversal cepat yang SANGAT meyakinkan. Frekuensi menang > besarnya profit.

Data Pasar (Candle Closed Terakhir):
{json.dumps(market_data, indent=2)}

Panduan Membaca Data:
- rsi       : <35=Oversold kuat | >65=Overbought
- stoch_rsi : <15=Oversold ekstrem | >85=Overbought ekstrem
- bb_pct    : 0=Harga di Lower Bollinger Band (zona bounce) | 50=Tengah | 100=Upper Band
- vol_ratio : <0.8=Volume lesu | 1.0=Normal | >1.5=Volume spike (sinyal makin kuat)
- adx       : <20=Sideways/Choppy (surga scalping) | >25=Trending kuat
- trend_ema : Strong Uptrend / Strong Downtrend / Sideways Choppy

Kriteria Prioritas BELI (urutkan penilaian dari yang terkuat):
1. RSI < 35 ATAU StochRSI < 15 (wajib terpenuhi salah satu)
2. bb_pct < 20 = Harga dekat Lower Bollinger Band (sinyal bounce sangat kuat)
3. vol_ratio >= 1.2 = Volume di atas normal (bounce lebih meyakinkan)
4. trend_ema = Sideways/Choppy + adx < 20 (kondisi terbaik untuk scalping reversal)

LARANGAN KERAS:
- JANGAN beli jika trend_ema = "Strong Downtrend" DAN adx > 25 (jatuh bebas, SL -1% habis dalam menit!)
- JANGAN beli jika vol_ratio < 0.8 (pasar mati, tidak ada partisipan yang menggerakkan harga)

Tugas: Pilih MAKSIMAL 1-2 koin terbaik. Berikan alasan spesifik mengacu pada angka aktual di data.

Output WAJIB JSON murni dengan format:
{{
  "decisions": [
    {{"symbol": "DOGEUSDT", "decision": "BUY", "reason": "RSI 28.5 + bb_pct 8.3 (dekat lower BB) + vol_ratio 1.6 (volume spike) = bounce kuat"}}
  ]
}}
Jika tidak ada yang layak, kembalikan: {{"decisions": []}}
"""
        try:
            completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": "You are a professional JSON Crypto Bot. You MUST output ONLY valid JSON format. Never include introductory text."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                model=self.model,
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            result_text = completion.choices[0].message.content
            parsed_data = json.loads(result_text)
            
            return parsed_data.get("decisions", [])
            
        except Exception as e:
            print(f"⚠️ Kegagalan Koneksi Groq Llama-3: {e}")
            return []

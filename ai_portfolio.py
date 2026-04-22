import json
from groq import Groq

class AIPortfolioManager:
    def __init__(self, api_key: str):
        # Menyambung langsung ke otak Llama-3.1 milik Groq
        self.client = Groq(api_key=api_key)
        # Menggunakan seri Llama 8B (Limit Kuotanya jauh lebih raksasa)
        self.model = 'llama-3.1-8b-instant'  # 500K token/hari (5x lebih banyak dari 70B)
        
    def analyze_opportunity(self, market_data: dict) -> list[dict]:
        """
        Groq sangat membutuhkan format instruksi JSON Object yang jelas di level Sistem.
        """
        prompt = f"""
Anda adalah AI Crypto Scalper. Target: TP +1.5%, SL -1%, Timeframe 15m.

Data Pasar (Candle Closed):
{json.dumps(market_data, indent=2)}

Panduan:
- rsi/stoch_rsi: <35/<15 = Oversold (WAJIB ada)
- bb_pct: 0=Lower BB (zona bounce terbaik), 100=Upper BB
- vol_ratio: >1.2=Volume kuat, <0.8=Volume lesu (hindari)
- htf_1h_trend: Trend 1 jam, Sideways/Uptrend = aman untuk bounce
- adx<20+Sideways/Choppy = kondisi scalping terbaik

LARANGAN: Jangan beli jika Strong Downtrend+adx>25 atau vol_ratio<0.8

Pilih MAKS 1-2 koin terbaik. Sertakan confidence 1-10 (min 7 untuk BUY).

JSON Output:
{{"decisions":[{{"symbol":"X","decision":"BUY","confidence":8,"reason":"..alasan singkat.."}}]}}
Jika tidak ada: {{"decisions":[]}}
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

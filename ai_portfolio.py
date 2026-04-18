import json
from groq import Groq

class AIPortfolioManager:
    def __init__(self, api_key: str):
        # Menyambung langsung ke otak Llama-3.1 milik Groq
        self.client = Groq(api_key=api_key)
        # Menggunakan seri Llama 8B (Limit Kuotanya jauh lebih raksasa)
        self.model = 'llama-3.1-8b-instant'
        
    def analyze_opportunity(self, market_data: dict) -> list[dict]:
        """
        Groq sangat membutuhkan format instruksi JSON Object yang jelas di level Sistem.
        """
        prompt = f"""
Anda adalah Manager Portofolio Kripto AI level Institusional berkemampuan tinggi.
Anda bertugas meraup peluang koin SPOT MARKET murah yang sangat berpotensi.

Data Kondisi Pasar Saat Ini:
{json.dumps(market_data, indent=2)}

Tugas Anda:
Pilih MAKSIMAL 1 atau 2 koin TERBAIK dari daftar di atas yang layak di-BUY detik ini juga.
Syarat mutlak Beli:
1. Berada dalam momentum pantulan (RSI < 45 atau Stoch RSI < 20).
2. Jika semua data tren menunjukkan "Strong Downtrend" tak berdasar, tolak. (Kecuali RSI benar-benar sangat oversold < 20).
3. Anda harus memberikan ALASAN RASIONAL MENDALAM mengapa Anda merekomendasikan hal tersebut.

Output HARUS WAJIB JSON murni dengan Root Key "decisions" yang merupakan Array.
Format yang Diharapkan:
{{
  "decisions": [
    {{"symbol": "BTCUSDT", "decision": "BUY", "reason": "RSI di tahap ekstrem oversold dan..."}}
  ]
}}
Jika market jelek, kembalikan json dengan array kosong: {{"decisions": []}}
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

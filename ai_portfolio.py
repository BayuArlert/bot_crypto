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
Anda adalah AI Crypto Scalper Berkecepatan Tinggi.
Anda beroperasi di Timeframe 15-Menit dan bertugas mencari peluang pantulan cepat (Rebound Scalping) yang SANGAT minim risiko.
Peringatan: Toleransi kerugian otomatis algoritma Anda SANGAT KETAT yaitu Stop Loss -1.5% dan Take Profit +3%.

Data Kondisi Pasar Saat Ini:
{json.dumps(market_data, indent=2)}

Tugas Anda:
Pilih MAKSIMAL 1 atau 2 koin TERBAIK dari daftar di atas yang layak di-BUY detik ini juga.
Syarat mutlak Beli Scalping:
1. Sedang dalam kondisi Oversold secara wajar di grafik 15-Menit (RSI < 35 atau Stoch RSI < 15).
2. Hindari/TOLAK MENTAH-MENTAH koin jika tren aslinya sedang "Strong Downtrend" brutal. Kebijakan ini penting karena Stop Loss kita sangat tipis (hanya 1.5%), kita akan otomatis terbuang/cut-loss dari pasar dalam hitungan menit jika AI memaksakan masuk ke koin yang sedang jatuh bebas!
3. Anda WAJIB memberikan ALASAN RASIONAL mengapa Anda yakin harganya akan lebih dulu memantul naik menyentuh TP +3% sebelum terseret The Wicks ke SL -1.5%!

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

import json
import time
from groq import Groq
import config


class AIValidator:
    def __init__(self):
        self.client = Groq(api_key=config.GROQ_API_KEY)
        self.model  = 'llama-3.1-8b-instant'  # lebih hemat token vs 70b
        self._cache: dict = {}  # {cache_key: (result, timestamp)}
        self._CACHE_TTL = 300   # cache 5 menit

    def _get_cache_key(self, symbol: str, score: int, volume_data: dict) -> str:
        spike = volume_data.get('spike_ratio', 0)
        p1h   = volume_data.get('price_change_1h_pct', 0)
        p15   = volume_data.get('price_change_15m_pct', 0)
        return f"{symbol}:{score}:{spike:.2f}:{p1h:.2f}:{p15:.2f}"

    def validate_entry(self, symbol: str, score: int, reasons: list[str],
                       volume_data: dict, sm_data: dict) -> tuple[bool, int, str]:
        """
        Validasi apakah entry layak dilakukan.
        Returns: (should_buy: bool, confidence: int, reason: str)
        """
        # Cek cache dulu
        cache_key = self._get_cache_key(symbol, score, volume_data)
        if cache_key in self._cache:
            result, ts = self._cache[cache_key]
            if time.time() - ts < self._CACHE_TTL:
                return result

        # Prompt ringkas untuk hemat token, dengan rule ketat
        prompt = (
            f"Symbol: {symbol} | Score: {score}/10\n"
            f"Signal: {' | '.join(reasons[:3])}\n"
            f"Vol spike: {volume_data.get('spike_ratio',0):.1f}x | "
            f"Price 1h: {volume_data.get('price_change_1h_pct',0):.2f}% | "
            f"Price 15m: {volume_data.get('price_change_15m_pct',0):.2f}% | "
            f"SM inflow: ${sm_data.get('inflow_usd',0):,.0f}\n\n"
            f"Apakah momentum ini genuine? TP 5% SL 3%.\n"
            f"RULES: Beri confidence RENDAH (<5) JIKA price change < 0.5% ATAU SM inflow sangat kecil/nol.\n"
            f'Jawab JSON: {{"buy":true/false,"confidence":1-10,"reason":"1 kalimat"}}'
        )
        try:
            resp = self.client.chat.completions.create(
                messages=[
                    {"role": "system",
                     "content": "Crypto momentum validator. Output ONLY valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                model=self.model,
                temperature=0.1,
                max_tokens=150,  # cukup untuk JSON response
                response_format={"type": "json_object"}
            )
            parsed     = json.loads(resp.choices[0].message.content)
            should_buy = parsed.get('buy', False)
            confidence = int(parsed.get('confidence', 0))
            reason     = parsed.get('reason', '')
            result = (should_buy, confidence, reason)

        except Exception as e:
            err_str = str(e)
            if '429' in err_str:
                print(f"   [AI] Rate limit — skip kandidat (aman)")
            else:
                print(f"   [AI] Error: {e}")
            # SAFE fallback: selalu SKIP saat AI error
            result = (False, 0, "AI unavailable — skip")

        # Simpan ke cache
        self._cache[cache_key] = (result, time.time())
        return result

"""
Binance crypto-market-rank API wrapper.
Semua endpoint PUBLIC — tidak butuh auth.
Source: github.com/binance/binance-skills-hub/crypto-market-rank
"""
import requests
import config
from datetime import datetime, timezone

BASE_URL = "https://web3.binance.com/bapi/defi/v1/public/wallet-direct"

# Cache keyed by request params — avoids BSC/Solana cross-contamination
_api_cache: dict[str, dict] = {}


def _cache_get(key: str) -> list | None:
    entry = _api_cache.get(key)
    if not entry or entry['last_fetch'] is None:
        return None
    elapsed = (datetime.now(timezone.utc) - entry['last_fetch']).total_seconds()
    if elapsed >= config.SIGNAL_CACHE_SECONDS:
        return None
    return entry['data']


def _cache_set(key: str, data: list) -> None:
    _api_cache[key] = {
        'data':       data,
        'last_fetch': datetime.now(timezone.utc),
    }


def _extract_list(raw: dict, *keys: str) -> list:
    """Parse API response per skill docs (leaderBoardList, tokens, etc.)."""
    data = raw.get('data', raw.get('result', []))
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in keys:
            items = data.get(key)
            if isinstance(items, list):
                return items
        for fallback in ('list', 'data'):
            items = data.get(fallback)
            if isinstance(items, list):
                return items
    return []


def _normalize_ticker(symbol: str) -> str:
    return symbol.upper().replace('USDT', '').strip()


# ─────────────────────────────────────────────────────────
# API 1: Social Hype Leaderboard
# ─────────────────────────────────────────────────────────
def get_social_hype_rank(chain_id: str = "56", sentiment: str = "Positive",
                          time_range: int = 1) -> list[dict]:
    """
    Fetch social hype leaderboard dari Binance.
    Returns: list of {symbol, price_change_pct, hype_score, sentiment, summary}
    """
    cache_key = f"hype:{chain_id}:{sentiment}:{time_range}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    url = (f"{BASE_URL}/buw/wallet/market/token/pulse/social/hype/rank"
           f"/leaderboard/ai")
    params = {
        "chainId":         chain_id,
        "sentiment":       sentiment,
        "targetLanguage":  "en",
        "timeRange":       time_range,
        "socialLanguage":  "en",
    }
    try:
        resp = requests.get(url, params=params, headers=config.BW3_HEADERS, timeout=10)
        resp.raise_for_status()
        data = _extract_list(resp.json(), 'leaderBoardList')

        result = []
        for item in data:
            meta   = item.get('metaInfo', item)
            market = item.get('marketInfo', {})
            social = item.get('socialHypeInfo', {})
            result.append({
                'symbol':          meta.get('symbol', item.get('symbol', '')),
                'price_change_pct': float(market.get('priceChange', item.get('priceChange', 0)) or 0),
                'hype_score':      float(social.get('socialHype', item.get('socialHype', 0)) or 0),
                'sentiment':       social.get('sentiment', item.get('sentiment', '')),
                'summary':         social.get('socialSummaryBriefTranslated',
                                              item.get('socialSummaryBriefTranslated', '')),
            })

        _cache_set(cache_key, result)
        return result

    except Exception as e:
        print(f"   [MarketRank] Social hype error ({chain_id}): {e}")
        stale = _api_cache.get(cache_key, {}).get('data', [])
        return stale


# ─────────────────────────────────────────────────────────
# API 2: Unified Token Rank (Trending)
# ─────────────────────────────────────────────────────────
def get_trending_tokens(chain_id: str = "56", size: int = 50) -> list[dict]:
    """
    Fetch trending tokens dari Binance unified rank.
    Returns: list of {symbol, price, pct_change_1h, ...}
    """
    cache_key = f"trending:{chain_id}:{size}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    url = f"{BASE_URL}/buw/wallet/market/token/pulse/unified/rank/list/ai"
    body = {
        "rankType":  10,
        "chainId":   chain_id,
        "period":    30,
        "sortBy":    70,
        "size":      size,
    }
    try:
        resp = requests.post(url, json=body, headers=config.BW3_HEADERS, timeout=10)
        resp.raise_for_status()
        data = _extract_list(resp.json(), 'tokens')

        result = []
        for item in data:
            audit = item.get('auditInfo', {})
            result.append({
                'symbol':           item.get('symbol', ''),
                'price':            float(item.get('price', 0) or 0),
                'pct_change_1h':    float(item.get('percentChange1h', 0) or 0),
                'pct_change_24h':   float(item.get('percentChange24h', 0) or 0),
                'volume_1h':        float(item.get('volume1h', 0) or 0),
                'volume_24h':       float(item.get('volume24h', 0) or 0),
                'tx_count_1h':      int(item.get('count1h', 0) or 0),
                'unique_traders_1h': int(item.get('uniqueTrader1h', 0) or 0),
                'risk_level':       audit.get('riskLevel', item.get('riskLevel', 0)),
            })

        _cache_set(cache_key, result)
        return result

    except Exception as e:
        print(f"   [MarketRank] Trending tokens error ({chain_id}): {e}")
        return _api_cache.get(cache_key, {}).get('data', [])


# ─────────────────────────────────────────────────────────
# API 3: Smart Money Inflow Rank
# ─────────────────────────────────────────────────────────
def get_sm_inflow_rank(chain_id: str = "56", period: str = "1h") -> list[dict]:
    """
    Fetch smart money inflow rank.
    Returns: list of {symbol, sm_inflow_usd, sm_traders_count, ...}
    """
    cache_key = f"sm:{chain_id}:{period}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    url = f"{BASE_URL}/tracker/wallet/token/inflow/rank/query/ai"
    body = {
        "chainId": chain_id,
        "period":  period,
        "tagType": 2,
    }
    try:
        resp = requests.post(url, json=body, headers=config.BW3_HEADERS, timeout=10)
        resp.raise_for_status()
        data = _extract_list(resp.json())

        result = []
        for item in data:
            result.append({
                'symbol':           item.get('tokenName', item.get('symbol', '')),
                'price':            float(item.get('price', 0) or 0),
                'price_change_pct': float(item.get('priceChangeRate', 0) or 0),
                'volume':           float(item.get('volume', 0) or 0),
                'sm_inflow_usd':    float(item.get('inflow', 0) or 0),
                'sm_traders_count': int(item.get('traders', 0) or 0),
                'market_cap':       float(item.get('marketCap', 0) or 0),
                'risk_level':       item.get('tokenRiskLevel', 0),
            })

        _cache_set(cache_key, result)
        return result

    except Exception as e:
        print(f"   [MarketRank] SM inflow error ({chain_id}): {e}")
        return _api_cache.get(cache_key, {}).get('data', [])


# ─────────────────────────────────────────────────────────
# Helper functions — return sets/dicts filtered for Spot tickers
# ─────────────────────────────────────────────────────────
def get_positive_hype_symbols(spot_tickers: set[str] | None = None) -> dict[str, float]:
    """Return dict {ticker: hype_score} — BSC + Solana, Positive sentiment."""
    combined: dict[str, float] = {}
    for chain_id in ("56", "CT_501"):
        for item in get_social_hype_rank(chain_id=chain_id, sentiment="Positive"):
            sym   = _normalize_ticker(item['symbol'])
            if not sym:
                continue
            if spot_tickers is not None and sym not in spot_tickers:
                continue
            score = float(item.get('hype_score', 0) or 0)
            if score >= config.SOCIAL_MIN_HYPE_SCORE:
                combined[sym] = max(combined.get(sym, 0), score)
    return combined


def get_trending_symbols(spot_tickers: set[str] | None = None) -> set[str]:
    """Return set of tickers yang sedang trending (BSC rank)."""
    result = set()
    for item in get_trending_tokens(chain_id="56"):
        sym = _normalize_ticker(item['symbol'])
        if not sym:
            continue
        if spot_tickers is not None and sym not in spot_tickers:
            continue
        result.add(sym)
    return result


def build_sm_inflow_map(spot_tickers: set[str]) -> dict[str, dict]:
    """
    Merge SM inflow BSC + Solana, keyed by Spot ticker.
    Only includes tokens with positive inflow meeting minimum thresholds.
    """
    sm_map: dict[str, dict] = {}
    for chain_id in ("56", "CT_501"):
        for item in get_sm_inflow_rank(chain_id=chain_id, period="1h"):
            raw = item.get('symbol', '')
            if not raw or not raw.replace('-', '').replace('_', '').isalnum():
                continue
            ticker = _normalize_ticker(raw)
            if ticker not in spot_tickers:
                continue
            inflow = float(item.get('sm_inflow_usd', 0))
            if inflow < config.SM_MIN_INFLOW_USD:
                continue
            if int(item.get('sm_traders_count', 0)) < config.SM_MIN_TRADERS:
                continue
            existing = sm_map.get(ticker)
            if existing is None or inflow > float(existing.get('sm_inflow_usd', 0)):
                sm_map[ticker] = item
    return sm_map


def get_sm_inflow_symbols(min_inflow: float = None,
                           min_traders: int = None,
                           spot_tickers: set[str] | None = None) -> set[str]:
    """Return set of tickers dengan SM inflow kuat."""
    min_inflow  = min_inflow or config.SM_MIN_INFLOW_USD
    min_traders = min_traders or config.SM_MIN_TRADERS
    if spot_tickers is None:
        spot_tickers = set()
        for item in get_sm_inflow_rank():
            sym = _normalize_ticker(item.get('symbol', ''))
            if sym:
                spot_tickers.add(sym)
    return set(build_sm_inflow_map(spot_tickers).keys())

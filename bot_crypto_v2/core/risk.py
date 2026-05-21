"""
Risk Manager — TP/SL/Trailing Stop berbasis persentase.
Timeout dan SL cooldown berbasis wall-clock UTC.
"""
import config
from datetime import datetime, timezone, timedelta


def calc_tp_sl(entry_price: float) -> tuple[float, float]:
    """Hitung TP dan SL dari entry price."""
    tp = entry_price * (1 + config.TP_PCT)
    sl = entry_price * (1 - config.SL_PCT)
    return tp, sl


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_time(value) -> datetime | None:
    """Parse ISO timestamp atau legacy loop_count (returns None for legacy)."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def check_trailing_stop(pos: dict, current_price: float) -> dict:
    """
    Update trailing stop jika profit sudah mencapai threshold.
    Modifikasi pos dict secara in-place dan return pos.
    """
    entry      = pos['buy_price']
    profit_pct = (current_price - entry) / entry

    if not pos.get('trailing_active'):
        if profit_pct >= config.TRAILING_ACTIVATE_PCT:
            new_sl = entry * (1 + config.TRAILING_LOCK_PCT)
            if new_sl > pos['sl_price']:
                pos['sl_price']        = new_sl
                pos['trailing_active'] = True
    else:
        potential_sl = current_price * (1 - config.SL_PCT * 0.5)
        if potential_sl > pos['sl_price']:
            pos['sl_price'] = potential_sl

    return pos


def is_timeout(pos: dict, now: datetime | None = None) -> bool:
    """Cek apakah posisi melebihi MAX_HOLD_MINUTES (wall-clock)."""
    entry_dt = parse_time(pos.get('entry_time'))
    if entry_dt is None:
        return False
    now = now or _utc_now()
    hold_minutes = (now - entry_dt).total_seconds() / 60
    return hold_minutes > config.MAX_HOLD_MINUTES


def is_sl_cooldown(symbol: str, sl_cooldown: dict,
                   now: datetime | None = None) -> bool:
    """Cek apakah koin masih dalam cooldown setelah SL (wall-clock)."""
    if symbol not in sl_cooldown:
        return False
    cooldown_dt = parse_time(sl_cooldown[symbol])
    if cooldown_dt is None:
        return False
    now = now or _utc_now()
    elapsed_minutes = (now - cooldown_dt).total_seconds() / 60
    return elapsed_minutes < config.SL_COOLDOWN_MINUTES


def cooldown_expires_at(symbol: str, sl_cooldown: dict) -> datetime | None:
    """Waktu cooldown berakhir (untuk logging)."""
    cooldown_dt = parse_time(sl_cooldown.get(symbol))
    if cooldown_dt is None:
        return None
    return cooldown_dt + timedelta(minutes=config.SL_COOLDOWN_MINUTES)

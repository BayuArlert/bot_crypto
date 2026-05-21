"""
State Manager — persistensi state bot ke JSON.
Menggunakan atomic write (tmp + rename) agar tidak korup saat crash.
"""
import json
import os
from datetime import datetime, timezone

import config

STATE_FILE = "bot_state_v2.json"


def _normalize_sl_cooldown(raw: dict) -> dict:
    """Load cooldown timestamps; ignore legacy loop_count integers."""
    result = {}
    for symbol, value in raw.items():
        if isinstance(value, str):
            result[symbol] = value
    return result


def save_state(bot) -> None:
    """Simpan state bot ke JSON. Silent-fail jika error."""
    try:
        portfolio = bot.portfolio
        state = {
            'balance':              portfolio.balance,
            'positions':            portfolio.positions,
            'history':              portfolio.history[:50],
            'sl_cooldown':          portfolio.sl_cooldown,
            'loop_count':           bot.loop_count,
            'active_symbols':       bot.active_symbols,
            'last_symbol_refresh':  (
                bot.last_symbol_refresh.isoformat()
                if bot.last_symbol_refresh else None
            ),
            'saved_at':             datetime.now(timezone.utc).isoformat(),
        }
        tmp = STATE_FILE + '.tmp'
        with open(tmp, 'w') as f:
            json.dump(state, f, indent=2, default=str)
        os.replace(tmp, STATE_FILE)
    except Exception as e:
        print(f"   [State] Save error: {e}")


def load_state(bot) -> None:
    """Load state dari JSON jika file ada. Silent-fail jika error atau tidak ada."""
    if not os.path.exists(STATE_FILE):
        return
    try:
        with open(STATE_FILE, 'r') as f:
            state = json.load(f)

        portfolio = bot.portfolio
        exchange_mode = config.TRADING_MODE in ('testnet', 'live')

        if not exchange_mode:
            portfolio.balance = state.get('balance', portfolio.balance)

        portfolio.positions   = state.get('positions', {})
        portfolio.history     = state.get('history', [])
        portfolio.sl_cooldown = _normalize_sl_cooldown(
            state.get('sl_cooldown', {}))

        bot.loop_count = state.get('loop_count', 0)
        # Testnet/live: jangan pakai symbol list lama dari era paper/testnet tipis
        if exchange_mode:
            bot.active_symbols      = []
            bot.last_symbol_refresh = None
        else:
            bot.active_symbols = state.get('active_symbols', [])
            raw_refresh = state.get('last_symbol_refresh')
            if raw_refresh:
                try:
                    bot.last_symbol_refresh = datetime.fromisoformat(raw_refresh)
                except Exception:
                    bot.last_symbol_refresh = None

        if exchange_mode:
            print(f"   [State] Loaded — mode {config.TRADING_MODE}: saldo dari exchange | "
                  f"Posisi: {len(portfolio.positions)} | History: {len(portfolio.history)}")
        else:
            print(f"   [State] Loaded — Balance: ${portfolio.balance:.2f} | "
                  f"Posisi: {len(portfolio.positions)} | History: {len(portfolio.history)}")
    except Exception as e:
        print(f"   [State] Load error: {e}")

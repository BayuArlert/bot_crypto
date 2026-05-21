"""
State Manager — Simpan dan load state bot ke/dari file JSON.
Dipanggil setiap loop untuk memastikan state tidak hilang saat crash.
"""
import json
import os
from datetime import datetime

STATE_FILE = "bot_state.json"

def save_state(bot) -> bool:
    """
    Simpan state bot ke JSON.
    Dipanggil di akhir setiap loop di run().
    Returns True jika berhasil, False jika gagal.
    """
    try:
        state = {
            'saved_at':          datetime.now().isoformat(),
            'virtual_balance':   bot.virtual_balance,
            'loop_count':        bot.loop_count,
            'virtual_portfolio': bot.virtual_portfolio,
            'trade_history':     bot.trade_history[:100],  # simpan max 100
            'sl_cooldown':       bot.sl_cooldown,
            'active_symbols':    bot.active_symbols,
            'last_symbol_refresh': bot.last_symbol_refresh.isoformat() if bot.last_symbol_refresh else None,
            'last_1h_refresh':   bot.last_1h_refresh.isoformat() if bot.last_1h_refresh else None,
            'last_4h_refresh':   bot.last_4h_refresh.isoformat() if bot.last_4h_refresh else None,
        }
        # Tulis ke file temp dulu, baru rename — mencegah file corrupt saat crash
        tmp_file = STATE_FILE + ".tmp"
        with open(tmp_file, 'w') as f:
            json.dump(state, f, indent=2, default=str)
        os.replace(tmp_file, STATE_FILE)
        return True
    except Exception as e:
        print(f"⚠️ Gagal simpan state: {e}")
        return False


def load_state(bot) -> bool:
    """
    Load state bot dari JSON jika file ada.
    Dipanggil sekali di awal __init__() atau run().
    Returns True jika berhasil load, False jika tidak ada file.
    """
    if not os.path.exists(STATE_FILE):
        print("ℹ️ Tidak ada state tersimpan — mulai fresh.")
        return False
    try:
        with open(STATE_FILE, 'r') as f:
            state = json.load(f)

        bot.virtual_balance   = state.get('virtual_balance', 25.0)
        bot.loop_count        = state.get('loop_count', 0)
        bot.virtual_portfolio = state.get('virtual_portfolio', {})
        bot.trade_history     = state.get('trade_history', [])
        bot.sl_cooldown       = state.get('sl_cooldown', {})
        bot.active_symbols    = state.get('active_symbols', bot.active_symbols)

        # Parse timestamps
        from datetime import timezone
        def parse_ts(val):
            if val is None:
                return None
            try:
                dt = datetime.fromisoformat(val)
                return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
            except:
                return None

        bot.last_symbol_refresh = parse_ts(state.get('last_symbol_refresh'))
        bot.last_1h_refresh     = parse_ts(state.get('last_1h_refresh'))
        bot.last_4h_refresh     = parse_ts(state.get('last_4h_refresh'))

        saved_at = state.get('saved_at', 'unknown')
        posisi   = len(bot.virtual_portfolio)
        print(f"✅ State berhasil di-load dari {saved_at}")
        print(f"   Saldo: ${bot.virtual_balance:.2f} | Posisi aktif: {posisi} | Loop: {bot.loop_count}")

        if bot.virtual_portfolio:
            print(f"   Posisi yang dilanjutkan: {list(bot.virtual_portfolio.keys())}")

        return True
    except Exception as e:
        print(f"⚠️ Gagal load state ({e}) — mulai fresh.")
        return False


def delete_state():
    """Hapus state file — untuk reset bot ke kondisi awal."""
    if os.path.exists(STATE_FILE):
        os.remove(STATE_FILE)
        print("🗑️ State file dihapus — bot direset ke kondisi awal.")
    else:
        print("ℹ️ Tidak ada state file untuk dihapus.")

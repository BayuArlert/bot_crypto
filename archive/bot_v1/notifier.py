"""
Telegram Notifier — Kirim notifikasi event penting bot ke Telegram.
Semua fungsi non-blocking (tidak crash bot jika Telegram gagal).
"""
import requests
import config
from datetime import datetime

TELEGRAM_API = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"


def _send(message: str, parse_mode: str = "HTML") -> bool:
    """Internal send — return True jika berhasil."""
    if not config.TELEGRAM_ENABLED:
        return False
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        return False
    try:
        resp = requests.post(TELEGRAM_API, json={
            'chat_id':    config.TELEGRAM_CHAT_ID,
            'text':       message,
            'parse_mode': parse_mode,
        }, timeout=5)
        return resp.status_code == 200
    except Exception:
        return False  # silent fail — jangan crash bot karena notif gagal


def notify_buy(symbol: str, price: float, tp: float, sl: float,
               strategy: str, confidence: int, regime: str):
    msg = (
        f"🚀 <b>BELI {symbol}</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"💰 Entry  : <code>${price:.4f}</code>\n"
        f"🎯 TP     : <code>${tp:.4f}</code> (+{((tp-price)/price*100):.1f}%)\n"
        f"🛡️ SL     : <code>${sl:.4f}</code> (-{((price-sl)/price*100):.1f}%)\n"
        f"📊 Strategi: {strategy}\n"
        f"🤖 Conf   : {confidence}/10\n"
        f"🌐 Regime : {regime}\n"
        f"🕐 Waktu  : {datetime.now().strftime('%d/%m %H:%M')}"
    )
    _send(msg)


def notify_tp(symbol: str, entry: float, exit_price: float,
              pnl: float, strategy: str, trade_type: str = 'TP'):
    emoji = "🎉" if trade_type == 'TP' else "⏳"
    label = "TAKE PROFIT" if trade_type == 'TP' else "TIMEOUT PROFIT"
    msg = (
        f"{emoji} <b>{label} {symbol}</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📥 Entry  : <code>${entry:.4f}</code>\n"
        f"📤 Exit   : <code>${exit_price:.4f}</code>\n"
        f"💵 PnL    : <b>+${pnl:.2f}</b>\n"
        f"📊 Strategi: {strategy}\n"
        f"🕐 Waktu  : {datetime.now().strftime('%d/%m %H:%M')}"
    )
    _send(msg)


def notify_sl(symbol: str, entry: float, exit_price: float,
              pnl: float, strategy: str, trade_type: str = 'SL'):
    emoji = "💔" if trade_type == 'SL' else "⏳"
    label = "CUT LOSS" if trade_type == 'SL' else "TIMEOUT LOSS"
    msg = (
        f"{emoji} <b>{label} {symbol}</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📥 Entry  : <code>${entry:.4f}</code>\n"
        f"📤 Exit   : <code>${exit_price:.4f}</code>\n"
        f"💵 PnL    : <b>-${abs(pnl):.2f}</b>\n"
        f"📊 Strategi: {strategy}\n"
        f"🕐 Waktu  : {datetime.now().strftime('%d/%m %H:%M')}"
    )
    _send(msg)


def notify_bear_exit(symbol: str, entry: float, exit_price: float, pnl: float):
    sign = "+" if pnl >= 0 else ""
    msg = (
        f"🐻 <b>BEAR EXIT {symbol}</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📥 Entry  : <code>${entry:.4f}</code>\n"
        f"📤 Exit   : <code>${exit_price:.4f}</code>\n"
        f"💵 PnL    : <b>{sign}${pnl:.2f}</b>\n"
        f"⚠️ Alasan : Bear market terdeteksi\n"
        f"🕐 Waktu  : {datetime.now().strftime('%d/%m %H:%M')}"
    )
    _send(msg)


def notify_regime_change(old_regime: str, new_regime: str, description: str):
    """Kirim notif hanya saat regime BERUBAH — tidak setiap loop."""
    emoji = {'BULL': '🐂', 'BEAR': '🐻', 'RANGE': '📊'}.get(new_regime, '🌐')
    msg = (
        f"{emoji} <b>REGIME CHANGE</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"Dari : {old_regime}\n"
        f"Ke   : <b>{new_regime}</b>\n"
        f"Info : {description}\n"
        f"🕐 Waktu: {datetime.now().strftime('%d/%m %H:%M')}"
    )
    _send(msg)


def notify_bot_start(balance: float, symbols_count: int):
    msg = (
        f"🤖 <b>Bot Trading Aktif</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"💰 Saldo awal : ${balance:.2f}\n"
        f"🪙 Koin dipantau: {symbols_count}\n"
        f"🕐 Start: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    )
    _send(msg)


def notify_error(context: str, error: str):
    """Notif error kritis — hanya untuk error yang butuh perhatian segera."""
    msg = (
        f"⚠️ <b>ERROR BOT</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"Konteks : {context}\n"
        f"Error   : <code>{error[:200]}</code>\n"
        f"🕐 Waktu: {datetime.now().strftime('%d/%m %H:%M')}"
    )
    _send(msg)

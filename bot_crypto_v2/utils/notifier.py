"""
Telegram Notifier — kirim notifikasi real-time ke Telegram.
Non-blocking: semua error di-silent agar bot tidak crash.
"""
import requests
import config


def _send(text: str) -> None:
    if not getattr(config, 'TELEGRAM_ENABLED', True):
        return
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={
            "chat_id":    config.TELEGRAM_CHAT_ID,
            "text":       text,
            "parse_mode": "HTML",
        }, timeout=5)
    except Exception:
        pass


def notify_bot_start(balance: float, symbols_count: int) -> None:
    _send(
        f"<b>🚀 Momentum Bot v2 Aktif</b>\n"
        f"Saldo: <code>${balance:.2f}</code>\n"
        f"Scanning: <code>{symbols_count}</code> koin"
    )


def notify_buy(symbol: str, price: float, tp: float, sl: float,
               strategy: str, confidence: int) -> None:
    _send(
        f"<b>🟢 BUY {symbol}</b>\n"
        f"Entry: <code>${price:.4f}</code>\n"
        f"TP: <code>${tp:.4f}</code> | SL: <code>${sl:.4f}</code>\n"
        f"Strategi: {strategy} | Conf: {confidence}/10"
    )


def notify_close(trade: dict) -> None:
    icon = "✅" if trade['pnl'] > 0 else "❌"
    _send(
        f"<b>{icon} {trade['type']} {trade['symbol']}</b>\n"
        f"Entry: <code>${trade['buy_price']:.4f}</code> → "
        f"Exit: <code>${trade['exit_price']:.4f}</code>\n"
        f"PnL: <code>${trade['pnl']:+.2f}</code> ({trade['pnl_pct']:+.2f}%)"
    )


def notify_regime_change(old: str, new: str, description: str = '') -> None:
    _send(
        f"<b>🔄 Regime Change: {old} → {new}</b>\n"
        f"{description}"
    )


def notify_error(context: str, error: str) -> None:
    _send(
        f"<b>⚠️ Error di {context}</b>\n"
        f"<code>{error[:200]}</code>"
    )

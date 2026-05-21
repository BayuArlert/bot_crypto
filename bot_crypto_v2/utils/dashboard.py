"""
Terminal Dashboard — serve web dashboard via Flask di port 5001.
Berjalan di background thread agar tidak blocking main loop.
"""
import threading
import json
from datetime import datetime

_state = {
    'virtual_balance': 0.0,
    'total_profit':    0.0,
    'positions':       [],
    'trade_history':   [],
    'tp_count':        0,
    'sl_count':        0,
    'logs':            [],
}
_lock = threading.Lock()


def update_state(**kwargs) -> None:
    """Update dashboard state. Thread-safe."""
    with _lock:
        for k, v in kwargs.items():
            if k in _state:
                _state[k] = v


def add_log(msg: str) -> None:
    """Tambahkan log entry ke dashboard."""
    ts  = datetime.now().strftime('%H:%M:%S')
    entry = f"[{ts}] {msg}"
    with _lock:
        _state['logs'].insert(0, entry)
        if len(_state['logs']) > 100:
            _state['logs'] = _state['logs'][:100]
    print(f"   LOG: {msg}")


def start_dashboard(port: int = 5001) -> None:
    """Start Flask dashboard di background thread."""
    try:
        from flask import Flask, jsonify, render_template_string
    except ImportError:
        print("   [Dashboard] Flask tidak terinstall. Dashboard tidak aktif.")
        print("   Install dengan: pip install flask")
        return

    app = Flask(__name__)

    HTML = """<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="UTF-8">
<meta http-equiv="refresh" content="10">
<title>Momentum Bot v2</title>
<style>
  :root { --bg:#0f1117; --card:#1a1d2e; --accent:#6c63ff; --green:#00d26a; --red:#ff4d4f; }
  * { box-sizing:border-box; margin:0; padding:0; }
  body { background:var(--bg); color:#e2e8f0; font-family:'Segoe UI',sans-serif; padding:20px; }
  h1 { color:var(--accent); margin-bottom:20px; font-size:1.6rem; }
  .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:16px; margin-bottom:24px; }
  .card { background:var(--card); border-radius:12px; padding:20px; }
  .card h3 { font-size:.8rem; color:#94a3b8; margin-bottom:8px; text-transform:uppercase; letter-spacing:.05em; }
  .card .val { font-size:1.8rem; font-weight:700; }
  .green { color:var(--green); } .red { color:var(--red); }
  table { width:100%; border-collapse:collapse; font-size:.85rem; }
  th { color:#94a3b8; text-align:left; padding:8px 12px; border-bottom:1px solid #2d3748; }
  td { padding:8px 12px; border-bottom:1px solid #1e2532; }
  .section { background:var(--card); border-radius:12px; padding:20px; margin-bottom:16px; }
  .section h2 { font-size:1rem; color:var(--accent); margin-bottom:14px; }
  .log-entry { font-family:monospace; font-size:.78rem; color:#94a3b8; padding:3px 0; }
</style>
</head>
<body>
<h1>⚡ Momentum Bot v2 — Live Dashboard</h1>
<div class="grid">
  <div class="card"><h3>Saldo Virtual</h3><div class="val" id="bal">-</div></div>
  <div class="card"><h3>Total P&L</h3><div class="val" id="pnl">-</div></div>
  <div class="card"><h3>Take Profits</h3><div class="val green" id="tp">-</div></div>
  <div class="card"><h3>Stop Losses</h3><div class="val red" id="sl">-</div></div>
  <div class="card"><h3>Posisi Aktif</h3><div class="val" id="pos">-</div></div>
</div>

<div class="section">
  <h2>Posisi Aktif</h2>
  <table id="positions-table">
    <tr><th>Symbol</th><th>Entry</th><th>TP</th><th>SL</th><th>Skor Signal</th><th>AI Conf</th><th>Entry Time</th></tr>
  </table>
</div>

<div class="section">
  <h2>Riwayat Trade</h2>
  <table id="history-table">
    <tr><th>Waktu</th><th>Symbol</th><th>Tipe</th><th>Entry</th><th>Exit</th><th>PnL</th></tr>
  </table>
</div>

<div class="section">
  <h2>Log</h2>
  <div id="log-container"></div>
</div>

<script>
async function refresh() {
  const r = await fetch('/api/state');
  const d = await r.json();
  document.getElementById('bal').textContent = '$' + d.virtual_balance.toFixed(2);
  const pnl = d.total_profit;
  const pel = document.getElementById('pnl');
  pel.textContent = (pnl >= 0 ? '+' : '') + '$' + pnl.toFixed(2);
  pel.className = 'val ' + (pnl >= 0 ? 'green' : 'red');
  document.getElementById('tp').textContent = d.tp_count;
  document.getElementById('sl').textContent = d.sl_count;
  document.getElementById('pos').textContent = d.positions.length;

  const pt = document.getElementById('positions-table');
  pt.innerHTML = '<tr><th>Symbol</th><th>Entry</th><th>TP</th><th>SL</th><th>Skor Signal</th><th>AI Conf</th><th>Entry Time</th></tr>';
  d.positions.forEach(p => {
    const tr = pt.insertRow();
    const entryTime = p.entry_time ? p.entry_time.substring(11,16) : '-';
    const aiConf = p.ai_confidence ?? '-';
    const aiColor = (p.ai_confidence >= 7) ? '#00d26a' : (p.ai_confidence >= 5) ? '#f6ad55' : '#ff4d4f';
    tr.innerHTML = `<td><b>${p.symbol}</b></td><td>$${p.buy_price?.toFixed(4)}</td><td style="color:#00d26a">$${p.tp_price?.toFixed(4)}</td><td style="color:#ff4d4f">$${p.sl_price?.toFixed(4)}</td><td>${p.score}/10</td><td style="color:${aiColor}">${aiConf}/10</td><td>${entryTime}</td>`;
  });

  const ht = document.getElementById('history-table');
  ht.innerHTML = '<tr><th>Waktu</th><th>Symbol</th><th>Tipe</th><th>Entry</th><th>Exit</th><th>PnL</th></tr>';
  d.trade_history.slice(0,20).forEach(t => {
    const tr = ht.insertRow();
    tr.style.color = t.pnl > 0 ? '#00d26a' : '#ff4d4f';
    tr.innerHTML = `<td>${t.time}</td><td>${t.symbol}</td><td>${t.type}</td><td>$${t.buy_price?.toFixed(4)}</td><td>$${t.exit_price?.toFixed(4)}</td><td>${t.pnl > 0 ? '+' : ''}$${t.pnl?.toFixed(2)}</td>`;
  });

  const lc = document.getElementById('log-container');
  lc.innerHTML = d.logs.slice(0,30).map(l => `<div class="log-entry">${l}</div>`).join('');
}
refresh();
setInterval(refresh, 10000);
</script>
</body>
</html>"""

    @app.route('/')
    def index():
        return render_template_string(HTML)

    @app.route('/api/state')
    def api_state():
        with _lock:
            return jsonify({
                'virtual_balance': _state['virtual_balance'],
                'total_profit':    _state['total_profit'],
                'positions':       list(_state['positions']) if isinstance(_state['positions'], dict) else _state['positions'],
                'trade_history':   _state['trade_history'],
                'tp_count':        _state['tp_count'],
                'sl_count':        _state['sl_count'],
                'logs':            _state['logs'],
            })

    def _run():
        import logging
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)
        app.run(host='127.0.0.1', port=port, debug=False, use_reloader=False)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    print(f"   [Dashboard] Aktif di http://localhost:{port}")

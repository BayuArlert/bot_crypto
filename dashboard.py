import threading
import json
import time
from datetime import datetime
from flask import Flask, Response, render_template_string

# ──────────────────────────────────────────────────────────────
# Global State Kripto Tervirtualisasi
# ──────────────────────────────────────────────────────────────
_state = {
    'last_update': '-',
    'virtual_balance': 25.0,
    'total_profit': 0.0,
    'tp_count': 0,
    'sl_count': 0,
    'trade_history': [],
    
    # List of object {symbol, price, buy_price, pnl, tp, sl}
    'positions': [],
    
    # List of object {symbol, price, rsi, trend, adx}
    'market_radar': [],
    
    # 50 baris terbawah
    'logs': []
}

def update_state(**kwargs):
    _state.update(kwargs)
    _state['last_update'] = datetime.now().strftime('%H:%M:%S')

def add_log(msg: str):
    timestamp = datetime.now().strftime('%H:%M:%S')
    _state['logs'].insert(0, f"[{timestamp}] {msg}")
    if len(_state['logs']) > 50:
        _state['logs'] = _state['logs'][:50]

app = Flask(__name__)

HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Binance AI Spot - Paper Trading</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;800&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #0b0e14;
            --card: #151a23;
            --accent: #fcd535; /* Binance yellow */
            --green: #0ecb81;
            --red: #f6465d;
            --text: #eaecef;
            --muted: #848e9c;
            --border: #2b3139;
        }
        
        * { box-sizing: border-box; margin: 0; padding: 0; }
        
        body {
            font-family: 'Inter', sans-serif;
            background: var(--bg);
            color: var(--text);
            min-height: 100vh;
        }

        .header {
            background: #1e2329;
            padding: 16px 32px;
            border-bottom: 2px solid var(--accent);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .title { font-size: 20px; font-weight: 800; color: var(--accent); }
        .subtitle { font-size: 12px; color: var(--muted); }

        .container {
            padding: 24px 32px;
            max-width: 1400px;
            margin: 0 auto;
            display: grid;
            grid-template-columns: 1fr 3fr;
            gap: 20px;
        }

        .card {
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 20px;
        }

        .card-title {
            font-size: 13px;
            text-transform: uppercase;
            font-weight: 600;
            color: var(--muted);
            margin-bottom: 12px;
            letter-spacing: 1px;
        }

        .balance-big {
            font-family: 'JetBrains Mono', monospace;
            font-size: 36px;
            font-weight: 800;
            color: var(--accent);
        }

        /* Tables for Coins */
        table { width: 100%; border-collapse: collapse; }
        th, td {
            text-align: left;
            padding: 12px 8px;
            border-bottom: 1px solid var(--border);
            line-height: 1.4;
        }
        th { font-size: 11px; text-transform: uppercase; color: var(--muted); font-weight: 600; }
        td { font-size: 14px; font-family: 'JetBrains Mono', monospace; font-weight: 700; }
        
        .green { color: var(--green); }
        .red { color: var(--red); }
        
        /* Logs */
        .log-box {
            background: #000;
            border-radius: 8px;
            padding: 16px;
            max-height: 500px;
            overflow-y: auto;
            font-family: 'JetBrains Mono', monospace;
            font-size: 12px;
        }
        .log-entry { margin-bottom: 10px; color: #a0a0a0; white-space: pre-wrap; }
        .log-entry:first-child { color: #fff; border-left: 3px solid var(--accent); padding-left: 8px; }

    </style>
</head>
<body>

<div class="header">
    <div>
        <div class="title">BINANCE AI BOT (SIMULATION)</div>
        <div class="subtitle">Multi-Coin Spot Scanner & Virtual Paper Trading</div>
    </div>
    <div style="text-align: right;">
        <span style="color:var(--muted); font-size: 12px;">Last Update:</span>
        <div id="last-update" style="font-family:'JetBrains Mono'; font-weight: bold;">-</div>
    </div>
</div>

<div class="container">
    <div>
        <!-- Balance Panel -->
        <div class="card">
            <div class="card-title">Dompet Virtual Anda</div>
            <div class="balance-big" id="virtual-balance">$25.00</div>
            <div style="font-size: 12px; margin-top: 5px; color:var(--muted)">PnL Total: <span id="total-pnl">$0.00</span></div>
            <div style="font-size: 12px; margin-top: 8px; display:flex; gap:12px;">
                <span style="color:var(--green)">TP: <strong id="tp-count">0</strong></span>
                <span style="color:var(--red)">SL: <strong id="sl-count">0</strong></span>
                <span style="color:var(--muted)">WR: <strong id="win-rate">-%</strong></span>
            </div>
        </div>
        
        <!-- Positions Panel -->
        <div class="card">
            <div class="card-title">Tas Koin (Hold)</div>
            <div id="positions-html">
                <div style="text-align:center; color:var(--muted); padding: 20px; font-size:12px;">Kosong</div>
            </div>
        </div>
    </div>

    <div>
        <!-- Market Scanner -->
        <div class="card">
            <div class="card-title">📡 Radar Market Tembakan AI</div>
            <table id="market-table">
                <thead>
                    <tr>
                        <th>Symbol</th>
                        <th>Price</th>
                        <th>Trend (EMA)</th>
                        <th>RSI</th>
                        <th>ADX</th>
                        <th>VOL</th>
                        <th>BB%</th>
                    </tr>
                </thead>
                <tbody id="market-html">
                    <tr><td colspan="7" style="text-align:center; color:var(--muted)">Scaning...</td></tr>
                </tbody>
            </table>
        </div>

        <!-- System Logs -->
        <div class="card">
            <div class="card-title">🖥️ Log Aktivitas AI</div>
            <div class="log-box" id="log-html">
                <div class="log-entry">Menunggu sistem menyala...</div>
            </div>
        </div>
    </div>
</div>

<!-- Histori Trade Full Width -->
<div style="padding: 0 32px 32px; max-width: 1400px; margin: 0 auto;">
    <div class="card">
        <div class="card-title">📊 Histori Trade Sesi Ini</div>
        <div style="overflow-x: auto;">
            <table>
                <thead>
                    <tr>
                        <th>Waktu</th>
                        <th>Symbol</th>
                        <th>Tipe</th>
                        <th>Harga Beli</th>
                        <th>Harga Keluar</th>
                        <th>PnL</th>
                    </tr>
                </thead>
                <tbody id="history-html">
                    <tr><td colspan="6" style="text-align:center; color:var(--muted); font-size:12px; padding:20px">Belum ada trade di sesi ini...</td></tr>
                </tbody>
            </table>
        </div>
    </div>
</div>

<script>
    const evtSource = new EventSource('/stream');
    evtSource.onmessage = function(event) {
        const s = JSON.parse(event.data);
        
        // Update Header & Balances
        document.getElementById('last-update').innerText = s.last_update;
        document.getElementById('virtual-balance').innerText = '$' + s.virtual_balance.toFixed(2);
        
        const pnlEl = document.getElementById('total-pnl');
        pnlEl.innerText = (s.total_profit >= 0 ? '+$' : '-$') + Math.abs(s.total_profit).toFixed(2);
        pnlEl.className = s.total_profit >= 0 ? 'green' : 'red';
        
        // Update Market Radar
        if (s.market_radar && s.market_radar.length > 0) {
            document.getElementById('market-html').innerHTML = s.market_radar.map(m => `
                <tr>
                    <td>${m.symbol}</td>
                    <td>$${m.price.toFixed(4)}</td>
                    <td style="color:${m.trend.includes('Up') ? 'var(--green)' : m.trend.includes('Down') ? 'var(--red)' : '#888'}">${m.trend}</td>
                    <td style="color:${m.rsi<35 ? 'var(--green)' : m.rsi>65 ? 'var(--red)' : '#888'}">${m.rsi}</td>
                    <td>${m.adx}</td>
                    <td style="color:${(m.vol_ratio||1)>=1.5 ? 'var(--green)' : (m.vol_ratio||1)<0.8 ? 'var(--red)' : '#888'}">${(m.vol_ratio||1).toFixed(2)}x</td>
                    <td style="color:${(m.bb_pct||50)<20 ? 'var(--green)' : (m.bb_pct||50)>80 ? 'var(--red)' : '#888'}">${(m.bb_pct||50).toFixed(1)}%</td>
                </tr>
            `).join('');
        }
        
        // Update Positions
        if (s.positions && s.positions.length > 0) {
            document.getElementById('positions-html').innerHTML = s.positions.map(p => `
                <div style="border-left: 3px solid var(--accent); padding: 8px 12px; margin-bottom: 10px; background: rgba(255,255,255,0.03); border-radius: 4px;">
                    <div style="display:flex; justify-content:space-between; margin-bottom: 4px;">
                        <span style="font-weight: 800; color: #fff;">${p.symbol}</span>
                        <span class="${p.pnl >= 0 ? 'green' : 'red'}">${p.pnl >= 0 ? '+' : ''}$${p.pnl.toFixed(2)}</span>
                    </div>
                    <div style="font-size:11px; color:var(--muted); line-height:1.5;">
                        Entry: $${p.buy_price.toFixed(4)} <br/>
                        Now  : $${p.price.toFixed(4)} <br/>
                        🛡️ TP/SL: $${p.tp.toFixed(4)} / $${p.sl.toFixed(4)}
                    </div>
                </div>
            `).join('');
        } else {
            document.getElementById('positions-html').innerHTML = '<div style="text-align:center; color:var(--muted); padding: 20px; font-size:12px;">Portofolio Mainan Anda Kosong</div>';
        }
        
        // Update Logs
        if (s.logs && s.logs.length > 0) {
            document.getElementById('log-html').innerHTML = s.logs.map(l => `<div class="log-entry">${l}</div>`).join('');
        }

        // Update Win Rate Stats
        const total = (s.tp_count || 0) + (s.sl_count || 0);
        document.getElementById('tp-count').innerText = s.tp_count || 0;
        document.getElementById('sl-count').innerText = s.sl_count || 0;
        document.getElementById('win-rate').innerText = total > 0 ? Math.round((s.tp_count/total)*100) + '%' : '-%';

        // Update Trade History
        if (s.trade_history && s.trade_history.length > 0) {
            document.getElementById('history-html').innerHTML = s.trade_history.map(t => `
                <tr>
                    <td style="font-size:12px; color:var(--muted)">${t.time}</td>
                    <td>${t.symbol}</td>
                    <td style="color:${t.type==='TP'?'var(--green)':'var(--red)'}; font-weight:800">${t.type==='TP'?'🎉 TP':'💔 SL'}</td>
                    <td>$${t.buy_price.toFixed(4)}</td>
                    <td>$${t.exit_price.toFixed(4)}</td>
                    <td class="${t.pnl>=0?'green':'red'}">${t.pnl>=0?'+':''}$${Math.abs(t.pnl).toFixed(2)}</td>
                </tr>
            `).join('');
        }
    };
</script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/stream')
def stream():
    def generate():
        while True:
            yield f"data: {json.dumps(_state)}\n\n"
            time.sleep(1)
    return Response(generate(), mimetype='text/event-stream')

def start_dashboard(port: int = 5001):
    import os
    # SERVER CLOUD (Railway) akan mendikte PORT lewat variabel lingkungan
    deploy_port = int(os.environ.get("PORT", port)) 
    
    thread = threading.Thread(
        target=lambda: app.run(host='0.0.0.0', port=deploy_port, debug=False, use_reloader=False),
        daemon=True
    )
    thread.start()
    print(f"✅ Crypto Dashboard Web Aktif: Merespons PORT {deploy_port}")

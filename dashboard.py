import threading, json, time
from datetime import datetime
from flask import Flask, Response, render_template_string

_state = {
    'last_update': '-', 'virtual_balance': 25.0, 'total_profit': 0.0,
    'tp_count': 0, 'sl_count': 0, 'trade_history': [], 'positions': [],
    'market_radar': [],
    'market_regime': {'regime':'LOADING','description':'Menunggu...','uptrend_pct':0,'downtrend_pct':0,'avg_adx':0,'avg_rsi':50},
    'logs': []
}

def update_state(**kwargs):
    _state.update(kwargs)
    _state['last_update'] = datetime.now().strftime('%H:%M:%S')

def add_log(msg: str):
    ts = datetime.now().strftime('%H:%M:%S')
    _state['logs'].insert(0, f"[{ts}] {msg}")
    if len(_state['logs']) > 50:
        _state['logs'] = _state['logs'][:50]

app = Flask(__name__)

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
<title>Binance AI Bot</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#0b0e14;--card:#151c28;--border:#1e2a3a;--accent:#f0b90b;--green:#0ecb81;--red:#f6465d;--blue:#3d8eff;--text:#e2e8f0;--muted:#4a5568;--sub:#8892a4}
html{overflow-x:hidden;width:100%}
body{font-family:'Inter',sans-serif;background:var(--bg);color:var(--text);min-height:100vh;font-size:14px;overflow-x:hidden;width:100%}

/* HEADER */
header{background:#0f1520;border-bottom:2px solid var(--accent);padding:12px 16px;position:sticky;top:0;z-index:99}
.hdr{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:8px;max-width:1400px;margin:0 auto}
.hdr-left h1{font-size:15px;font-weight:800;color:var(--accent);letter-spacing:.5px}
.hdr-left p{font-size:10px;color:var(--muted);margin-top:1px}
.hdr-right{display:flex;align-items:center;gap:8px;flex-shrink:0}
#regime-badge{padding:5px 12px;border-radius:20px;font-size:11px;font-weight:700;border:1px solid var(--border);background:var(--card);color:var(--sub);transition:all .3s;white-space:nowrap}
.uptime{font-family:'JetBrains Mono';font-size:10px;color:var(--muted);white-space:nowrap}

/* BANNER */
#regime-banner{font-size:11px;padding:7px 16px;text-align:center;display:none;word-break:break-word;line-height:1.5}

/* MAIN */
.wrap{max-width:1400px;margin:0 auto;padding:12px 12px 24px;overflow-x:hidden}

/* STAT ROW */
.stats{display:grid;grid-template-columns:repeat(2,1fr);gap:10px;margin-bottom:12px}
@media(min-width:768px){.stats{grid-template-columns:repeat(4,1fr)}}

.stat{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:14px}
.stat-lbl{font-size:9px;text-transform:uppercase;letter-spacing:1px;color:var(--muted);margin-bottom:6px}
.stat-val{font-family:'JetBrains Mono';font-size:22px;font-weight:700}
.stat-sub{font-size:11px;color:var(--sub);margin-top:5px}

/* GRID BODY */
.body-grid{display:grid;gap:12px;grid-template-columns:1fr}
@media(min-width:900px){.body-grid{grid-template-columns:300px 1fr}}

.bot-grid{display:grid;gap:12px;grid-template-columns:1fr;margin-top:12px}
@media(min-width:900px){.bot-grid{grid-template-columns:1fr 1fr}}

/* CARD */
.card{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:14px}
.card-title{font-size:10px;text-transform:uppercase;letter-spacing:1px;color:var(--muted);font-weight:700;margin-bottom:12px;display:flex;align-items:center;gap:6px}
.card-title::before{content:'';width:3px;height:11px;background:var(--accent);border-radius:2px;flex-shrink:0}

/* POSITIONS */
.pos-card{background:rgba(255,255,255,.03);border:1px solid var(--border);border-left:3px solid var(--accent);border-radius:8px;padding:10px;margin-bottom:8px}
.pos-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px}
.pos-sym{font-weight:700;font-size:13px}
.pos-pnl{font-family:'JetBrains Mono';font-size:13px;font-weight:700}
.pos-grid{display:grid;grid-template-columns:1fr 1fr;gap:4px;font-size:11px;color:var(--sub)}
.pos-grid span{display:block;font-family:'JetBrains Mono';font-size:12px;color:var(--text);margin-top:1px}
.prog{height:3px;background:var(--border);border-radius:2px;margin-top:8px;overflow:hidden}
.prog-bar{height:100%;background:linear-gradient(90deg,var(--red),var(--accent),var(--green));border-radius:2px;transition:width .4s}
.empty{text-align:center;padding:28px 10px;color:var(--muted);font-size:12px}
.empty-ico{font-size:24px;margin-bottom:6px}

/* TABLE */
.tbl-wrap{overflow-x:auto;-webkit-overflow-scrolling:touch;max-width:100%}
.tbl-wrap table{width:100%;border-collapse:collapse}
#tbl-radar{min-width:360px}
#tbl-hist{min-width:340px}
table th{font-size:10px;text-transform:uppercase;letter-spacing:.5px;color:var(--muted);padding:7px 6px;text-align:left;border-bottom:1px solid var(--border);white-space:nowrap}
table td{padding:8px 6px;font-size:11.5px;font-family:'JetBrains Mono';border-bottom:1px solid rgba(30,42,58,.6);white-space:nowrap}
table tr:last-child td{border-bottom:none}
table tbody tr:hover{background:rgba(255,255,255,.02)}
.up{color:var(--green)}.dn{color:var(--red)}.sd{color:var(--sub)}
.g{color:var(--green)}.r{color:var(--red)}

/* BADGE */
.bdg{display:inline-block;padding:2px 8px;border-radius:10px;font-size:10px;font-weight:700;font-family:Inter}
.bdg-g{background:rgba(14,203,129,.12);color:var(--green)}
.bdg-r{background:rgba(246,70,93,.12);color:var(--red)}
.bdg-b{background:rgba(61,142,255,.12);color:var(--blue)}

/* MINI PILLS */
.pills{display:flex;gap:6px;flex-wrap:wrap;margin-top:6px}
.pill{display:inline-flex;align-items:center;gap:4px;padding:3px 9px;border-radius:10px;font-size:11px;font-weight:600}
.pill-g{background:rgba(14,203,129,.12);color:var(--green)}
.pill-r{background:rgba(246,70,93,.12);color:var(--red)}

/* LOG */
.log-box{background:#060a10;border-radius:8px;padding:10px;height:240px;overflow-y:auto;font-family:'JetBrains Mono';font-size:10.5px;scrollbar-width:thin;scrollbar-color:var(--border) transparent}
.log-box::-webkit-scrollbar{width:3px}
.log-box::-webkit-scrollbar-thumb{background:var(--border);border-radius:2px}
.log-item{padding:4px 6px;margin-bottom:3px;border-radius:3px;color:var(--muted);line-height:1.5;word-break:break-word}
.log-item:first-child{color:#c8d4e4;background:rgba(240,185,11,.07);border-left:2px solid var(--accent);padding-left:7px}

/* DIST BAR */
.dist{display:flex;gap:10px;margin-top:6px}
.dist-item{flex:1}
.dist-lbl{font-size:10px;margin-bottom:3px}
.dist-bar{height:5px;background:var(--border);border-radius:3px;overflow:hidden}
.dist-fill{height:100%;border-radius:3px;transition:width .5s}
.dist-val{font-size:11px;margin-top:2px;font-family:'JetBrains Mono'}

/* FOOTER */
footer{text-align:center;padding:16px;font-size:10px;color:var(--muted);border-top:1px solid var(--border)}

/* MOBILE < 600px: sembunyikan kolom sekunder agar tabel muat di layar */
@media(max-width:599px){
  /* Radar — sembunyikan Vol(6) dan BB%(7) */
  #tbl-radar thead th:nth-child(6),
  #tbl-radar thead th:nth-child(7),
  #tbl-radar tbody td:nth-child(6),
  #tbl-radar tbody td:nth-child(7){ display:none }

  /* History — sembunyikan Strategi(4) dan Exit(6) */
  #tbl-hist thead th:nth-child(4),
  #tbl-hist thead th:nth-child(6),
  #tbl-hist tbody td:nth-child(4),
  #tbl-hist tbody td:nth-child(6){ display:none }

  table th{ padding:6px 4px; font-size:9px; letter-spacing:0 }
  table td{ padding:7px 4px; font-size:10.5px }
  .wrap{ padding:8px 8px 20px }
  .stats{ gap:8px }
  .stat-val{ font-size:20px }
}
</style>
</head>
<body>

<header>
  <div class="hdr">
    <div class="hdr-left">
      <h1>&#x20BF; BINANCE AI BOT</h1>
      <p>Paper Trading &bull; Adaptive Regime Strategy</p>
    </div>
    <div class="hdr-right">
      <div id="regime-badge">&#x23F3; LOADING</div>
      <div class="uptime">&#x1F551; <span id="last-update">-</span></div>
    </div>
  </div>
</header>

<div id="regime-banner"></div>

<div class="wrap">

  <!-- STAT CARDS -->
  <div class="stats">
    <div class="stat">
      <div class="stat-lbl">Saldo Virtual</div>
      <div class="stat-val" id="s-balance" style="color:var(--accent)">$25.00</div>
      <div class="stat-sub" id="s-pnl">PnL: $0.00</div>
    </div>
    <div class="stat">
      <div class="stat-lbl">Win Rate</div>
      <div class="stat-val" id="s-wr">-%</div>
      <div class="pills">
        <span class="pill pill-g">TP: <b id="s-tp">0</b></span>
        <span class="pill pill-r">SL: <b id="s-sl">0</b></span>
      </div>
    </div>
    <div class="stat">
      <div class="stat-lbl">Market Regime</div>
      <div class="stat-val" id="s-regime" style="font-size:18px">-</div>
      <div class="stat-sub" id="s-adx">ADX: - &bull; RSI: -</div>
    </div>
    <div class="stat">
      <div class="stat-lbl">Distribusi Trend</div>
      <div class="dist">
        <div class="dist-item">
          <div class="dist-lbl" style="color:var(--green)">&#x25B2; Up</div>
          <div class="dist-bar"><div id="bar-up" class="dist-fill" style="background:var(--green);width:0%"></div></div>
          <div class="dist-val g" id="pct-up">0%</div>
        </div>
        <div class="dist-item">
          <div class="dist-lbl" style="color:var(--red)">&#x25BC; Down</div>
          <div class="dist-bar"><div id="bar-down" class="dist-fill" style="background:var(--red);width:0%"></div></div>
          <div class="dist-val r" id="pct-down">0%</div>
        </div>
      </div>
    </div>
  </div>

  <!-- POSITIONS + RADAR -->
  <div class="body-grid">
    <div class="card">
      <div class="card-title">Posisi Aktif</div>
      <div id="pos-wrap">
        <div class="empty"><div class="empty-ico">&#x1F4BC;</div>Belum ada posisi</div>
      </div>
    </div>
    <div class="card">
      <div class="card-title">Radar Market</div>
      <div class="tbl-wrap">
        <table id="tbl-radar">
          <thead><tr><th>Koin</th><th>Harga</th><th>Trend</th><th>RSI</th><th>ADX</th><th>Vol</th><th>BB%</th></tr></thead>
          <tbody id="radar-tbody"><tr><td colspan="7" style="text-align:center;color:var(--muted);padding:20px">Memuat...</td></tr></tbody>
        </table>
      </div>
    </div>
  </div>

  <!-- HISTORY + LOGS -->
  <div class="bot-grid">
    <div class="card">
      <div class="card-title">Histori Trade</div>
      <div class="tbl-wrap">
        <table id="tbl-hist">
          <thead><tr><th>Waktu</th><th>Koin</th><th>Hasil</th><th>Strategi</th><th>Entry</th><th>Exit</th><th>PnL</th></tr></thead>
          <tbody id="hist-tbody"><tr><td colspan="7" style="text-align:center;color:var(--muted);padding:20px;font-family:Inter">Belum ada trade</td></tr></tbody>
        </table>
      </div>
    </div>
    <div class="card">
      <div class="card-title">Log Aktivitas AI</div>
      <div class="log-box" id="log-box">
        <div class="log-item">Menunggu bot aktif...</div>
      </div>
    </div>
  </div>

</div>

<footer>Binance AI Bot &mdash; Simulation Only &bull; Data: Binance Public API</footer>

<script>
const sse = new EventSource('/stream');
sse.onmessage = e => {
  const s = JSON.parse(e.data);

  document.getElementById('last-update').innerText = s.last_update || '-';

  // Balance & PnL
  const bal = s.virtual_balance || 25;
  const pnl = s.total_profit || 0;
  document.getElementById('s-balance').innerText = '$' + bal.toFixed(2);
  const pnlEl = document.getElementById('s-pnl');
  pnlEl.innerText = 'PnL: ' + (pnl >= 0 ? '+' : '') + '$' + pnl.toFixed(2);
  pnlEl.style.color = pnl >= 0 ? 'var(--green)' : 'var(--red)';

  // Win Rate
  const tp = s.tp_count || 0, sl = s.sl_count || 0, tot = tp + sl;
  document.getElementById('s-tp').innerText = tp;
  document.getElementById('s-sl').innerText = sl;
  const wr = tot > 0 ? Math.round(tp / tot * 100) : null;
  const wrEl = document.getElementById('s-wr');
  wrEl.innerText = wr !== null ? wr + '%' : '-%';
  wrEl.style.color = wr !== null ? (wr >= 50 ? 'var(--green)' : 'var(--red)') : 'var(--text)';

  // Regime
  const r = s.market_regime || {};
  const RM = {
    BEAR:    {lbl:'&#x1F43B; BEAR',   bg:'#2a1218',border:'#f6465d',col:'#f6465d',bbg:'rgba(246,70,93,.1)'},
    BULL:    {lbl:'&#x1F402; BULL',   bg:'#0d2118',border:'#0ecb81',col:'#0ecb81',bbg:'rgba(14,203,129,.1)'},
    RANGE:   {lbl:'&#x1F4CA; RANGE',  bg:'#1c1a08',border:'#f0b90b',col:'#f0b90b',bbg:'rgba(240,185,11,.08)'},
    LOADING: {lbl:'&#x23F3; ...',     bg:'#151c28',border:'#1e2a3a',col:'#4a5568',bbg:'transparent'},
  };
  const rs = RM[r.regime] || RM.LOADING;
  const badge = document.getElementById('regime-badge');
  badge.innerHTML = rs.lbl;
  badge.style.cssText = `padding:5px 12px;border-radius:20px;font-size:11px;font-weight:700;border:1px solid ${rs.border};background:${rs.bg};color:${rs.col};transition:all .3s;white-space:nowrap`;
  badge.title = r.description || '';

  const banner = document.getElementById('regime-banner');
  if(r.regime && r.regime !== 'LOADING') {
    banner.style.cssText = `display:block;background:${rs.bbg};color:${rs.col};font-size:11px;padding:7px 16px;text-align:center;word-break:break-word;line-height:1.6;border-bottom:1px solid ${rs.border}22`;
    banner.innerHTML = '<b>' + (r.regime||'') + ':</b> ' + (r.description||'');
  } else { banner.style.display = 'none'; }

  const rEl = document.getElementById('s-regime');
  rEl.innerHTML = rs.lbl; rEl.style.color = rs.col;
  document.getElementById('s-adx').innerText = 'ADX: ' + (r.avg_adx||'-') + ' \u2022 RSI: ' + (r.avg_rsi||'-');
  document.getElementById('bar-up').style.width = (r.uptrend_pct||0) + '%';
  document.getElementById('bar-down').style.width = (r.downtrend_pct||0) + '%';
  document.getElementById('pct-up').innerText = (r.uptrend_pct||0) + '%';
  document.getElementById('pct-down').innerText = (r.downtrend_pct||0) + '%';

  // Positions
  const pos = s.positions || [];
  const posWrap = document.getElementById('pos-wrap');
  if(pos.length > 0) {
    posWrap.innerHTML = pos.map(p => {
      const c = p.pnl >= 0 ? 'var(--green)' : 'var(--red)';
      const rng = p.tp - p.sl;
      const pct = rng > 0 ? Math.max(0, Math.min(100, (p.price - p.sl) / rng * 100)) : 50;
      return `<div class="pos-card">
        <div class="pos-head">
          <div><span class="pos-sym">${p.symbol}</span>${p.strategy?`<span class="bdg bdg-b" style="margin-left:6px;font-size:9px">${p.strategy}</span>`:''}</div>
          <span class="pos-pnl" style="color:${c}">${p.pnl>=0?'+':''}$${p.pnl.toFixed(2)}</span>
        </div>
        <div class="pos-grid">
          <div>Entry<span>$${p.buy_price.toFixed(4)}</span></div>
          <div>Harga<span>$${p.price.toFixed(4)}</span></div>
          <div>TP<span style="color:var(--green)">$${p.tp.toFixed(4)}</span></div>
          <div>SL<span style="color:var(--red)">$${p.sl.toFixed(4)}</span></div>
        </div>
        <div class="prog"><div class="prog-bar" style="width:${pct}%"></div></div>
      </div>`;
    }).join('');
  } else {
    posWrap.innerHTML = `<div class="empty"><div class="empty-ico">&#x1F4BC;</div>Belum ada posisi<br><small style="color:var(--muted);margin-top:4px;display:block">Bot memantau peluang...</small></div>`;
  }

  // Radar
  const radar = s.market_radar || [];
  if(radar.length > 0) {
    document.getElementById('radar-tbody').innerHTML = radar.map(m => {
      const tCls = m.trend.includes('Up') ? 'up' : m.trend.includes('Down') ? 'dn' : 'sd';
      const tLbl = m.trend.includes('Up') ? '&#x25B2; Up' : m.trend.includes('Down') ? '&#x25BC; Down' : '&#x25C6; Side';
      const rsi = m.rsi || 50;
      const rC = rsi < 35 ? 'var(--green)' : rsi > 65 ? 'var(--red)' : 'var(--sub)';
      const adx = m.adx || 0;
      const aC = adx > 40 ? 'var(--red)' : adx > 25 ? 'var(--accent)' : 'var(--sub)';
      const vr = m.vol_ratio || 1;
      const vC = vr >= 1.5 ? 'var(--green)' : vr < 0.8 ? 'var(--red)' : 'var(--sub)';
      const bb = m.bb_pct || 50;
      const bC = bb < 20 ? 'var(--green)' : bb > 80 ? 'var(--red)' : 'var(--sub)';
      const price = m.price;
      const pStr = price < 1 ? price.toFixed(4) : price < 100 ? price.toFixed(2) : price.toFixed(1);
      return `<tr>
        <td style="font-weight:700;color:var(--text)">${m.symbol.replace('USDT','')}<small style="color:var(--muted)">/USDT</small></td>
        <td>$${pStr}</td>
        <td class="${tCls}">${tLbl}</td>
        <td style="color:${rC}">${rsi}</td>
        <td style="color:${aC}">${adx}</td>
        <td style="color:${vC}">${vr.toFixed(2)}x</td>
        <td style="color:${bC}">${bb.toFixed(1)}%</td>
      </tr>`;
    }).join('');
  }

  // History
  const hist = s.trade_history || [];
  if(hist.length > 0) {
    document.getElementById('hist-tbody').innerHTML = hist.map(t =>
      `<tr>
        <td style="color:var(--sub);font-size:10px">${t.time}</td>
        <td style="font-weight:700">${t.symbol.replace('USDT','')}</td>
        <td><span class="bdg ${t.type==='TP'?'bdg-g':'bdg-r'}">${t.type}</span></td>
        <td><span class="bdg bdg-b" style="font-size:9px">${t.strategy||'-'}</span></td>
        <td>$${t.buy_price.toFixed(4)}</td>
        <td>$${t.exit_price.toFixed(4)}</td>
        <td style="color:${t.pnl>=0?'var(--green)':'var(--red)'};font-weight:700">${t.pnl>=0?'+':''}$${Math.abs(t.pnl).toFixed(2)}</td>
      </tr>`
    ).join('');
  }

  // Logs
  const logs = s.logs || [];
  if(logs.length > 0) {
    document.getElementById('log-box').innerHTML = logs.map(l =>
      `<div class="log-item">${l}</div>`
    ).join('');
  }
};
sse.onerror = () => { document.getElementById('last-update').innerText = 'Error koneksi'; };
</script>
</body>
</html>"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/stream')
def stream():
    def gen():
        while True:
            yield f"data: {json.dumps(_state)}\n\n"
            time.sleep(1)
    return Response(gen(), mimetype='text/event-stream')

def start_dashboard(port: int = 5001):
    import os
    p = int(os.environ.get("PORT", port))
    t = threading.Thread(target=lambda: app.run(host='0.0.0.0', port=p, debug=False, use_reloader=False), daemon=True)
    t.start()
    print(f"Dashboard aktif di PORT {p}")

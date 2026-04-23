import threading
import json
import time
from datetime import datetime
from flask import Flask, Response, render_template_string

_state = {
    'last_update': '-',
    'virtual_balance': 25.0,
    'total_profit': 0.0,
    'tp_count': 0,
    'sl_count': 0,
    'trade_history': [],
    'positions': [],
    'market_radar': [],
    'market_regime': {
        'regime': 'LOADING',
        'description': 'Menunggu data pasar...',
        'uptrend_pct': 0,
        'downtrend_pct': 0,
        'avg_adx': 0,
        'avg_rsi': 50,
    },
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

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Binance AI Bot - Paper Trading</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#0b0e14;--surface:#131820;--card:#1a2030;--border:#242d3d;
  --accent:#f0b90b;--green:#0ecb81;--red:#f6465d;--blue:#1890ff;
  --text:#e8ecf0;--muted:#5e6a7d;--muted2:#8b97a8;
}
html{scroll-behavior:smooth}
body{font-family:'Inter',sans-serif;background:var(--bg);color:var(--text);min-height:100vh;font-size:14px}

/* ── HEADER ── */
.header{
  background:linear-gradient(135deg,#0f1623 0%,#131d2e 100%);
  border-bottom:1px solid var(--border);
  padding:0 20px;
  position:sticky;top:0;z-index:100;
}
.header-inner{
  max-width:1400px;margin:0 auto;
  display:flex;align-items:center;justify-content:space-between;
  height:60px;gap:12px;flex-wrap:wrap;
  padding:8px 0;
}
.logo{display:flex;flex-direction:column;gap:2px}
.logo-title{font-size:15px;font-weight:800;color:var(--accent);letter-spacing:.5px}
.logo-sub{font-size:10px;color:var(--muted);letter-spacing:.3px}
.header-right{display:flex;align-items:center;gap:10px;flex-shrink:0}
.regime-badge{
  padding:6px 14px;border-radius:20px;font-size:12px;font-weight:700;
  letter-spacing:.5px;border:1px solid;transition:all .4s ease;
  background:#1a2030;color:var(--muted);border-color:var(--border);
}
.update-time{font-family:'JetBrains Mono';font-size:11px;color:var(--muted2);white-space:nowrap}

/* ── REGIME BANNER ── */
.regime-banner{
  padding:10px 20px;font-size:12px;font-weight:500;text-align:center;
  transition:all .4s ease;display:none;
}

/* ── LAYOUT ── */
.main{max-width:1400px;margin:0 auto;padding:16px}
.grid-top{display:grid;gap:14px;grid-template-columns:1fr}
.grid-mid{display:grid;gap:14px;grid-template-columns:1fr;margin-top:14px}
.grid-bot{display:grid;gap:14px;grid-template-columns:1fr;margin-top:14px}

@media(min-width:640px){
  .grid-top{grid-template-columns:repeat(2,1fr)}
}
@media(min-width:1024px){
  .grid-top{grid-template-columns:repeat(4,1fr)}
  .grid-mid{grid-template-columns:1fr 2fr}
  .grid-bot{grid-template-columns:1fr 1fr}
}

/* ── CARDS ── */
.card{
  background:var(--card);border:1px solid var(--border);
  border-radius:14px;padding:16px;
}
.card-title{
  font-size:10px;text-transform:uppercase;letter-spacing:1.2px;
  font-weight:600;color:var(--muted);margin-bottom:12px;
  display:flex;align-items:center;gap:6px;
}
.card-title::before{content:'';width:3px;height:12px;border-radius:2px;background:var(--accent)}

/* ── STAT CARDS ── */
.stat-value{font-family:'JetBrains Mono';font-size:26px;font-weight:700;line-height:1.1}
.stat-label{font-size:11px;color:var(--muted2);margin-top:4px}
.stat-sub{font-size:12px;margin-top:8px;color:var(--muted2)}
.pill{display:inline-flex;align-items:center;gap:4px;padding:3px 10px;border-radius:12px;font-size:11px;font-weight:600}
.pill-green{background:rgba(14,203,129,.12);color:var(--green)}
.pill-red{background:rgba(246,70,93,.12);color:var(--red)}
.pill-muted{background:rgba(94,106,125,.15);color:var(--muted2)}

/* ── POSITIONS ── */
.pos-item{
  background:rgba(255,255,255,.03);border:1px solid var(--border);
  border-radius:10px;padding:12px;margin-bottom:8px;
  border-left:3px solid var(--accent);
}
.pos-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}
.pos-symbol{font-weight:800;font-size:14px}
.pos-pnl{font-family:'JetBrains Mono';font-size:14px;font-weight:700}
.pos-details{display:grid;grid-template-columns:1fr 1fr;gap:4px;font-size:11px;color:var(--muted2)}
.pos-detail-row{display:flex;flex-direction:column;gap:2px}
.pos-detail-row span:last-child{color:var(--text);font-family:'JetBrains Mono';font-size:12px}
.pos-progress{
  height:4px;background:var(--border);border-radius:2px;margin-top:8px;overflow:hidden
}
.pos-progress-bar{height:100%;background:linear-gradient(90deg,var(--red),var(--accent),var(--green));border-radius:2px;transition:width .3s}
.empty-state{text-align:center;padding:32px 16px;color:var(--muted);font-size:12px}
.empty-icon{font-size:28px;margin-bottom:8px}

/* ── TABLE ── */
.table-wrap{overflow-x:auto;-webkit-overflow-scrolling:touch}
table{width:100%;border-collapse:collapse;min-width:480px}
thead tr{border-bottom:1px solid var(--border)}
th{font-size:10px;text-transform:uppercase;letter-spacing:.8px;color:var(--muted);padding:8px 10px;text-align:left;white-space:nowrap;font-weight:600}
td{padding:10px 10px;font-size:13px;font-family:'JetBrains Mono';border-bottom:1px solid rgba(36,45,61,.5);white-space:nowrap}
tbody tr:hover{background:rgba(255,255,255,.02)}
tbody tr:last-child td{border-bottom:none}
.trend-up{color:var(--green)}
.trend-down{color:var(--red)}
.trend-side{color:var(--muted2)}
.green{color:var(--green)}
.red{color:var(--red)}

/* ── LOG ── */
.log-wrap{
  background:#080b10;border-radius:10px;padding:12px;
  height:260px;overflow-y:auto;font-family:'JetBrains Mono';font-size:11px;
  scrollbar-width:thin;scrollbar-color:var(--border) transparent;
}
.log-wrap::-webkit-scrollbar{width:4px}
.log-wrap::-webkit-scrollbar-track{background:transparent}
.log-wrap::-webkit-scrollbar-thumb{background:var(--border);border-radius:2px}
.log-entry{
  padding:5px 8px;margin-bottom:4px;border-radius:4px;
  color:#6b7a8d;line-height:1.4;word-break:break-all;
}
.log-entry:first-child{color:#c8d3e0;background:rgba(240,185,11,.06);border-left:2px solid var(--accent);padding-left:8px}

/* ── HISTORY TABLE ── */
.badge-tp{background:rgba(14,203,129,.12);color:var(--green);padding:2px 8px;border-radius:10px;font-size:11px;font-weight:700}
.badge-sl{background:rgba(246,70,93,.12);color:var(--red);padding:2px 8px;border-radius:10px;font-size:11px;font-weight:700}
.badge-strat{background:rgba(24,144,255,.12);color:var(--blue);padding:2px 6px;border-radius:8px;font-size:10px}

/* ── FOOTER ── */
.footer{text-align:center;padding:20px;font-size:11px;color:var(--muted);border-top:1px solid var(--border);margin-top:20px}

/* ── PULSE ANIM ── */
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.5}}
.pulse{animation:pulse 2s infinite}
@keyframes fadeIn{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:translateY(0)}}
.fadein{animation:fadeIn .4s ease}

/* ── RSI BAR ── */
.rsi-bar{width:50px;height:4px;background:var(--border);border-radius:2px;display:inline-block;vertical-align:middle;margin-left:4px;overflow:hidden}
.rsi-fill{height:100%;border-radius:2px;transition:width .3s}
</style>
</head>
<body>

<div class="header">
  <div class="header-inner">
    <div class="logo">
      <div class="logo-title">BINANCE AI BOT</div>
      <div class="logo-sub">Simulation · Adaptive Multi-Regime Strategy</div>
    </div>
    <div class="header-right">
      <div id="regime-badge" class="regime-badge">⏳ LOADING</div>
      <div class="update-time">Update: <span id="last-update">-</span></div>
    </div>
  </div>
</div>

<div id="regime-banner" class="regime-banner"></div>

<div class="main">

  <!-- STAT CARDS -->
  <div class="grid-top">
    <div class="card fadein">
      <div class="card-title">Portofolio</div>
      <div class="stat-value" id="total-portfolio" style="color:var(--accent)">$25.00</div>
      <div class="stat-sub">Modal Awal: <span style="color:var(--muted2)">$25.00</span></div>
      <div style="margin-top:8px" id="pnl-pill"></div>
    </div>
    <div class="card fadein">
      <div class="card-title">Win Rate</div>
      <div class="stat-value" id="wr-value" style="color:var(--text)">-%</div>
      <div class="stat-sub" style="margin-top:8px;display:flex;gap:6px;flex-wrap:wrap">
        <span class="pill pill-green">TP: <strong id="tp-count">0</strong></span>
        <span class="pill pill-red">SL: <strong id="sl-count">0</strong></span>
      </div>
    </div>
    <div class="card fadein">
      <div class="card-title">Kondisi Pasar</div>
      <div class="stat-value" id="regime-stat" style="font-size:18px">-</div>
      <div class="stat-sub" id="regime-adx">ADX: - | RSI: -</div>
    </div>
    <div class="card fadein">
      <div class="card-title">Distribusi Trend</div>
      <div style="display:flex;gap:8px;align-items:center;margin-top:4px">
        <div style="flex:1">
          <div style="font-size:10px;color:var(--green);margin-bottom:3px">Uptrend</div>
          <div style="height:6px;background:var(--border);border-radius:3px;overflow:hidden">
            <div id="bar-up" style="height:100%;background:var(--green);border-radius:3px;transition:width .5s;width:0%"></div>
          </div>
          <div style="font-size:11px;color:var(--green);margin-top:2px" id="pct-up">0%</div>
        </div>
        <div style="flex:1">
          <div style="font-size:10px;color:var(--red);margin-bottom:3px">Downtrend</div>
          <div style="height:6px;background:var(--border);border-radius:3px;overflow:hidden">
            <div id="bar-down" style="height:100%;background:var(--red);border-radius:3px;transition:width .5s;width:0%"></div>
          </div>
          <div style="font-size:11px;color:var(--red);margin-top:2px" id="pct-down">0%</div>
        </div>
      </div>
    </div>
  </div>

  <!-- MID: POSITIONS + MARKET RADAR -->
  <div class="grid-mid">
    <div class="card">
      <div class="card-title">Posisi Aktif</div>
      <div id="positions-wrap">
        <div class="empty-state"><div class="empty-icon">💼</div>Belum ada posisi terbuka</div>
      </div>
    </div>
    <div class="card">
      <div class="card-title">Radar Market (9 Koin)</div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Koin</th>
              <th>Harga</th>
              <th>Trend</th>
              <th>RSI</th>
              <th>ADX</th>
              <th>Vol</th>
              <th>BB%</th>
            </tr>
          </thead>
          <tbody id="market-tbody">
            <tr><td colspan="7" style="text-align:center;color:var(--muted);padding:24px">Memuat data...</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>

  <!-- BOT: HISTORY + LOGS -->
  <div class="grid-bot">
    <div class="card">
      <div class="card-title">Histori Trade Sesi Ini</div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Waktu</th>
              <th>Koin</th>
              <th>Hasil</th>
              <th>Strategi</th>
              <th>Entry</th>
              <th>Exit</th>
              <th>PnL</th>
            </tr>
          </thead>
          <tbody id="history-tbody">
            <tr><td colspan="7" style="text-align:center;color:var(--muted);padding:24px;font-family:Inter">Belum ada trade...</td></tr>
          </tbody>
        </table>
      </div>
    </div>
    <div class="card">
      <div class="card-title">Log Aktivitas AI</div>
      <div class="log-wrap" id="log-wrap">
        <div class="log-entry pulse">Menunggu sistem aktif...</div>
      </div>
    </div>
  </div>

</div>

<div class="footer">Binance AI Bot &mdash; Paper Trading Simulation &bull; Data dari Binance Public API</div>

<script>
const src = new EventSource('/stream');
src.onmessage = function(e) {
  const s = JSON.parse(e.data);

  // Last update
  document.getElementById('last-update').innerText = s.last_update || '-';

  // Portfolio & PnL
  const totalPf = (s.virtual_balance || 25) + (s.positions||[]).reduce((a,p)=>a+(p.pnl||0),0)
                  + (s.positions||[]).length * 10;
  const bal = s.virtual_balance || 25;
  const pnl = s.total_profit || 0;
  document.getElementById('total-portfolio').innerText = '$' + bal.toFixed(2);
  const pnlEl = document.getElementById('pnl-pill');
  pnlEl.innerHTML = `<span class="pill ${pnl>=0?'pill-green':'pill-red'}">${pnl>=0?'+':''}\$${pnl.toFixed(2)} PnL Total</span>`;

  // Win rate
  const tp = s.tp_count||0, sl = s.sl_count||0, tot = tp+sl;
  document.getElementById('tp-count').innerText = tp;
  document.getElementById('sl-count').innerText = sl;
  document.getElementById('wr-value').innerText = tot > 0 ? Math.round(tp/tot*100)+'%' : '-%';
  document.getElementById('wr-value').style.color = tot>0?(tp/tot>=0.5?'var(--green)':'var(--red)'):'var(--text)';

  // Market Regime
  const r = s.market_regime || {};
  const rMap = {
    BEAR:   {label:'🐻 BEAR',   bg:'#2d1a1f', border:'#f6465d', color:'#f6465d', bannerBg:'rgba(246,70,93,.08)',  bannerText:'#f6465d'},
    BULL:   {label:'🐂 BULL',   bg:'#0f2318', border:'#0ecb81', color:'#0ecb81', bannerBg:'rgba(14,203,129,.07)', bannerText:'#0ecb81'},
    RANGE:  {label:'📊 RANGE',  bg:'#1a1e10', border:'#f0b90b', color:'#f0b90b', bannerBg:'rgba(240,185,11,.07)', bannerText:'#f0b90b'},
    LOADING:{label:'⏳ ...',    bg:'#1a2030', border:'#242d3d', color:'#5e6a7d', bannerBg:'transparent',           bannerText:'#5e6a7d'},
  };
  const rs = rMap[r.regime] || rMap.LOADING;
  const badge = document.getElementById('regime-badge');
  badge.innerText = rs.label;
  Object.assign(badge.style, {background:rs.bg, borderColor:rs.border, color:rs.color});
  badge.title = r.description || '';

  const banner = document.getElementById('regime-banner');
  if(r.regime && r.regime !== 'LOADING') {
    banner.style.display = 'block';
    banner.style.background = rs.bannerBg;
    banner.style.color = rs.bannerText;
    banner.innerHTML = `<strong>${r.regime}:</strong> ${r.description||''}`;
  }

  document.getElementById('regime-stat').innerText = r.regime || '-';
  document.getElementById('regime-stat').style.color = rs.color;
  document.getElementById('regime-adx').innerText = `ADX avg: ${r.avg_adx||'-'} | RSI avg: ${r.avg_rsi||'-'}`;
  document.getElementById('bar-up').style.width = (r.uptrend_pct||0)+'%';
  document.getElementById('bar-down').style.width = (r.downtrend_pct||0)+'%';
  document.getElementById('pct-up').innerText = (r.uptrend_pct||0)+'%';
  document.getElementById('pct-down').innerText = (r.downtrend_pct||0)+'%';

  // Positions
  const posWrap = document.getElementById('positions-wrap');
  if((s.positions||[]).length > 0) {
    posWrap.innerHTML = s.positions.map(p => {
      const pnlColor = p.pnl >= 0 ? 'var(--green)' : 'var(--red)';
      const range = p.tp - p.sl;
      const prog = range > 0 ? Math.max(0, Math.min(100, ((p.price - p.sl) / range) * 100)) : 50;
      return `<div class="pos-item">
        <div class="pos-header">
          <div>
            <span class="pos-symbol">${p.symbol}</span>
            ${p.strategy ? `<span class="badge-strat" style="margin-left:6px">${p.strategy}</span>` : ''}
          </div>
          <span class="pos-pnl" style="color:${pnlColor}">${p.pnl>=0?'+':''}$${p.pnl.toFixed(2)}</span>
        </div>
        <div class="pos-details">
          <div class="pos-detail-row">
            <span>Entry</span><span>$${p.buy_price.toFixed(4)}</span>
          </div>
          <div class="pos-detail-row">
            <span>Sekarang</span><span>$${p.price.toFixed(4)}</span>
          </div>
          <div class="pos-detail-row">
            <span>Take Profit</span><span style="color:var(--green)">$${p.tp.toFixed(4)}</span>
          </div>
          <div class="pos-detail-row">
            <span>Stop Loss</span><span style="color:var(--red)">$${p.sl.toFixed(4)}</span>
          </div>
        </div>
        <div class="pos-progress"><div class="pos-progress-bar" style="width:${prog}%"></div></div>
      </div>`;
    }).join('');
  } else {
    posWrap.innerHTML = `<div class="empty-state"><div class="empty-icon">💼</div>Belum ada posisi terbuka<br><small style="color:var(--muted);margin-top:4px;display:block">Bot sedang memantau peluang...</small></div>`;
  }

  // Market Radar
  if((s.market_radar||[]).length > 0) {
    document.getElementById('market-tbody').innerHTML = s.market_radar.map(m => {
      const tClass = m.trend.includes('Up') ? 'trend-up' : m.trend.includes('Down') ? 'trend-down' : 'trend-side';
      const tLabel = m.trend.includes('Up') ? '▲ Uptrend' : m.trend.includes('Down') ? '▼ Downtrend' : '◆ Sideways';
      const rsi = m.rsi || 50;
      const rsiColor = rsi < 35 ? 'var(--green)' : rsi > 65 ? 'var(--red)' : 'var(--muted2)';
      const volColor = (m.vol_ratio||1) >= 1.5 ? 'var(--green)' : (m.vol_ratio||1) < 0.8 ? 'var(--red)' : 'var(--muted2)';
      const bbColor  = (m.bb_pct||50) < 20 ? 'var(--green)' : (m.bb_pct||50) > 80 ? 'var(--red)' : 'var(--muted2)';
      return `<tr>
        <td style="font-weight:700;color:var(--text)">${m.symbol.replace('USDT','')}<span style="color:var(--muted);font-size:10px">/USDT</span></td>
        <td>$${m.price.toFixed(m.price<1?4:2)}</td>
        <td class="${tClass}">${tLabel}</td>
        <td style="color:${rsiColor}">${rsi}</td>
        <td style="color:${m.adx>40?'var(--red)':m.adx>25?'var(--accent)':'var(--muted2)'}">${m.adx}</td>
        <td style="color:${volColor}">${(m.vol_ratio||1).toFixed(2)}x</td>
        <td style="color:${bbColor}">${(m.bb_pct||50).toFixed(1)}%</td>
      </tr>`;
    }).join('');
  }

  // Trade History
  if((s.trade_history||[]).length > 0) {
    document.getElementById('history-tbody').innerHTML = s.trade_history.map(t => {
      const pnlColor = t.pnl >= 0 ? 'var(--green)' : 'var(--red)';
      return `<tr>
        <td style="color:var(--muted);font-size:11px">${t.time}</td>
        <td style="font-weight:700">${t.symbol.replace('USDT','')}</td>
        <td><span class="${t.type==='TP'?'badge-tp':'badge-sl'}">${t.type==='TP'?'TP':'SL'}</span></td>
        <td><span class="badge-strat">${t.strategy||'-'}</span></td>
        <td>$${t.buy_price.toFixed(4)}</td>
        <td>$${t.exit_price.toFixed(4)}</td>
        <td style="color:${pnlColor};font-weight:700">${t.pnl>=0?'+':''}$${Math.abs(t.pnl).toFixed(2)}</td>
      </tr>`;
    }).join('');
  }

  // Logs
  if((s.logs||[]).length > 0) {
    document.getElementById('log-wrap').innerHTML = s.logs.map(l =>
      `<div class="log-entry">${l}</div>`
    ).join('');
  }
};
src.onerror = function() {
  document.getElementById('last-update').innerText = 'Koneksi terputus...';
};
</script>
</body>
</html>"""

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
    deploy_port = int(os.environ.get("PORT", port))
    thread = threading.Thread(
        target=lambda: app.run(host='0.0.0.0', port=deploy_port, debug=False, use_reloader=False),
        daemon=True
    )
    thread.start()
    print(f"Dashboard aktif di PORT {deploy_port}")

#!/usr/bin/env python3
"""Builds ufc_dashboard.html by surgically modifying the original dashboard."""
import re, os

SRC = r"C:\Users\edcha\Downloads\ufc_dashboard (5).html"
DST = r"C:\Users\edcha\UFC Dashboard\ufc_dashboard.html"

# ── Constants defined first ──────────────────────────────────────
# (populated below the main loop, but Python reads the whole file before executing)
# We use a two-pass approach: define constants at bottom, import them via exec trick
# Actually: just move constants to top by restructuring.
# See end of file for constant definitions — we exec them first.
import sys
_src = open(__file__, encoding='utf-8').read()
_const_start = _src.index('\n# ─────────────────────────────────────────────────────────────────\n')
exec(_src[_const_start:], globals())

with open(SRC, encoding='utf-8') as f:
    lines = f.readlines()

# Strip trailing newlines for easier processing
lines = [l.rstrip('\n').rstrip('\r') for l in lines]

out = []
i = 0
while i < len(lines):
    line = lines[i]

    # ── Skip embedded FIGHTS_DATA (line 381, idx 380) and const FIGHTS= (idx 381) ──
    if i == 380:
        out.append('let FIGHTS=[],pageData=[],expandedIdx=-1;')
        i += 2  # skip both data lines
        continue

    # ── Replace the single old media query with full new CSS ──
    if line.strip().startswith('@media(max-width:900px){#p-db{flex-direction:column'):
        out.append(NEW_CSS)
        i += 1
        continue

    # ── Before <div id="nav">, insert loading overlay + sidebar overlay ──
    if line.strip() == '<div id="nav">':
        out.append('<div id="loading"><div class="ld-brand">FIGHT <span>DB</span></div><div class="ld-spin"></div><div class="ld-txt">Loading fight data...</div></div>')
        out.append('<div id="sidebar-overlay" onclick="closeMobileSidebar()"></div>')
        out.append('<div id="nav">')
        out.append('  <button id="hamburger" onclick="toggleMobileSidebar()">&#9776;</button>')
        # Copy brand line from original
        out.append('  <div class="nav-brand">FIGHT <span>DB</span></div>')
        out.append('  <button class="nav-tab active" onclick="showPage(\'db\',this)">Database</button>')
        out.append('  <button class="nav-tab" onclick="showPage(\'stats\',this)">Stats</button>')
        out.append('  <button class="nav-tab" onclick="showPage(\'compare\',this)">Compare</button>')
        out.append('</div>')
        # Skip original nav internals (nav-brand, db-tab, stats-tab, </div>)
        i += 4
        continue

    # ── Replace subtitle line ──
    if 'class="subtitle"' in line and '8,560' in line:
        out.append('  <div class="subtitle">8,560 fights &middot; 1994&ndash;2026 &middot; 784 events<span class="upd-stamp">Last updated: Feb 25, 2026</span></div>')
        i += 1
        continue

    # ── Before <script>, insert Compare page HTML ──
    if line.strip() == '<script>':
        out.append(COMPARE_HTML)
        out.append('<script>')
        i += 1
        continue

    # ── After showPage function, add mobile sidebar helpers ──
    if "if(p==='stats')renderStatsPage();" in line and i > 400:
        out.append(line)
        out.append("function toggleMobileSidebar(){var sb=document.getElementById('sidebar'),ov=document.getElementById('sidebar-overlay');sb.classList.toggle('open');ov.classList.toggle('open');}")
        out.append("function closeMobileSidebar(){document.getElementById('sidebar').classList.remove('open');document.getElementById('sidebar-overlay').classList.remove('open');}")
        i += 1
        continue

    # ── applyFilters: add event_location to search ──
    if 'inName=' in line and 'fighter1' in line and 'event_name' in line and i > 400:
        out.append("      const inName=(f.fighter1||'')+' '+(f.fighter2||'')+' '+(f.event_name||'')+' '+(f.event_location||'');")
        # Skip the original inName line + the if(!inName...) line
        out.append("      if(!inName.toLowerCase().includes(search))return false;")
        i += 2  # skip original 2 lines
        continue

    # ── Replace renderTable function ──
    if line.strip() == 'function renderTable(){':
        out.append(RENDER_TABLE_JS)
        # Skip until we reach the pagination section
        i += 1
        while i < len(lines) and "const pnsEl=document.getElementById('pns')" not in lines[i]:
            i += 1
        # Include pagination code until stats section
        while i < len(lines) and not re.match(r'^// .+ STATS PAGE', lines[i]):
            out.append(lines[i])
            i += 1
        continue

    # ── Fighter profile: add career timeline before closing of html template ──
    if 'Recent Form' in line and 'newest first' in line and i > 400:
        out.append(line)
        i += 1
        # Copy lines until we hit the template closing "  </div>`;"
        while i < len(lines) and not (lines[i].strip() == '</div>`;'):
            out.append(lines[i])
            i += 1
        # Insert timeline section
        out.append(TIMELINE_JS)
        out.append('  </div>`;')
        i += 1
        continue

    # ── Replace INIT section with fetch-based version ──
    if re.match(r'^// .+ INIT ', line):
        out.append(NEW_INIT_JS)
        break  # everything after this is old init code + closing tags

    out.append(line)
    i += 1

# Write output
with open(DST, 'w', encoding='utf-8') as f:
    f.write('\n'.join(out))

print(f"Done. Lines: {len(out)}, Size: {os.path.getsize(DST)//1024}KB")
# Quick checks
content = '\n'.join(out)
for check in ['id="loading"', 'id="hamburger"', 'page-compare', 'Last updated', 'toggleExpand',
              'tl-tip', 'runCompare', 'fetch(', 'initDashboard', 'URLSearchParams', 'event_location']:
    status = 'OK' if check in content else 'MISSING'
    print(f'{status}: {check}')


# ─────────────────────────────────────────────────────────────────
NEW_CSS = """\
/* === LOADING === */
#loading{position:fixed;inset:0;background:var(--bg);z-index:9999;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:14px}
.ld-brand{font-family:Georgia,serif;font-size:24px;font-weight:900;color:var(--bright);letter-spacing:-1px}.ld-brand span{color:var(--red)}
.ld-spin{width:36px;height:36px;border:3px solid rgba(229,51,51,0.2);border-top-color:var(--red);border-radius:50%;animation:spin 0.75s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
.ld-txt{font-size:10px;letter-spacing:3px;text-transform:uppercase;color:#444}
#hamburger{display:none;background:none;border:1px solid rgba(255,255,255,0.12);border-radius:6px;color:#aaa;padding:5px 9px;cursor:pointer;font-size:15px;margin-right:10px;line-height:1;font-family:inherit}
#hamburger:hover{color:#fff}
#sidebar-overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,0.65);z-index:149}
#sidebar-overlay.open{display:block}
tbody tr.data-row{cursor:pointer}
tbody tr.data-row.expanded{background:rgba(229,51,51,0.07)!important}
tbody tr.data-row.expanded td:first-child{border-left:2px solid var(--red)}
tbody tr.detail-row td{background:rgba(150,10,10,0.06);border-bottom:1px solid rgba(229,51,51,0.15);padding:0}
.exp-inner{padding:11px 16px 13px;display:flex;gap:20px;align-items:flex-start;flex-wrap:wrap}
.exp-grid{display:flex;gap:16px;flex-wrap:wrap;flex:1}
.exp-item .exp-lbl{font-size:8px;letter-spacing:1.5px;text-transform:uppercase;color:#444;margin-bottom:2px}
.exp-item .exp-val{font-size:12px;color:#bbb;font-weight:700}
.exp-title{display:inline-block;background:rgba(245,158,11,0.12);border:1px solid rgba(245,158,11,0.3);color:var(--amber);font-size:9px;padding:2px 7px;border-radius:4px;letter-spacing:1px;font-weight:700;margin-top:6px}
.exp-actions{display:flex;gap:7px;align-items:center;flex-shrink:0;flex-wrap:wrap}
.exp-btn{background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.12);color:#999;padding:5px 10px;border-radius:6px;font-size:11px;font-family:inherit;text-decoration:none;display:inline-flex;align-items:center;gap:5px;white-space:nowrap;transition:all 0.15s}
.exp-btn:hover{background:rgba(255,255,255,0.08);color:#fff}
.exp-btn.yt{border-color:rgba(229,51,51,0.3);color:#ef4444}.exp-btn.yt:hover{background:var(--red-dim)}
.exp-btn.uf{border-color:rgba(20,184,166,0.3);color:var(--teal)}.exp-btn.uf:hover{background:rgba(20,184,166,0.08)}
.tl-outer{overflow-x:auto;-webkit-overflow-scrolling:touch;padding-bottom:4px;margin-top:6px}
.tl-track{display:flex;gap:2px;align-items:center;min-width:max-content;padding:4px 0 2px;position:relative}
.tl-track::before{content:'';position:absolute;left:0;right:0;top:50%;height:1px;background:rgba(255,255,255,0.05);pointer-events:none}
.tl-item{display:flex;flex-direction:column;align-items:center;gap:2px;position:relative;z-index:1}
.tl-dot{width:18px;height:18px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:7px;font-weight:900;flex-shrink:0}
.tl-dot.W{background:rgba(20,184,166,0.25);color:var(--teal);border:1px solid rgba(20,184,166,0.4)}
.tl-dot.L{background:rgba(239,68,68,0.2);color:#ef4444;border:1px solid rgba(239,68,68,0.35)}
.tl-dot.NC{background:rgba(255,255,255,0.06);color:#555;border:1px solid rgba(255,255,255,0.1)}
.tl-dot.title{box-shadow:0 0 0 2px var(--amber)}
.tl-yr{font-size:6px;color:#333;white-space:nowrap}
.tl-tip{position:absolute;bottom:calc(100% + 5px);left:50%;transform:translateX(-50%);background:#13131f;border:1px solid rgba(255,255,255,0.12);padding:5px 8px;border-radius:5px;font-size:10px;color:#ddd;white-space:nowrap;pointer-events:none;display:none;z-index:400}
.tl-item:hover .tl-tip{display:block}
.upd-stamp{color:#333;margin-left:14px;padding-left:14px;border-left:1px solid rgba(255,255,255,0.07);font-size:10px}
#page-compare{padding:28px 32px}
.cmp-row{display:flex;gap:16px;align-items:flex-end;flex-wrap:wrap;margin-bottom:20px}
.cmp-col{flex:1;min-width:180px;max-width:300px;position:relative}
.cmp-lbl{font-size:9px;letter-spacing:2.5px;color:var(--dim);text-transform:uppercase;font-weight:700;margin-bottom:6px}
.cmp-vs-badge{font-size:18px;color:#333;font-weight:900;padding-bottom:7px;flex-shrink:0}
.cmp-go{background:var(--red-dim);border:1px solid var(--red-border);color:var(--red);padding:8px 20px;border-radius:7px;cursor:pointer;font-family:inherit;font-size:12px;font-weight:700;letter-spacing:1px;align-self:flex-end;flex-shrink:0}
.cmp-dd{position:absolute;top:100%;left:0;right:0;z-index:300;background:#111;border:1px solid rgba(255,255,255,0.12);border-top:none;border-radius:0 0 8px 8px;max-height:200px;overflow-y:auto;display:none}
.cmp-results{display:none;margin-top:4px}
.cmp-cards{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:20px}
.cmp-card{background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.08);border-radius:12px;padding:16px 18px}
.cmp-card.f1{border-top:2px solid rgba(229,51,51,0.4)}.cmp-card.f2{border-top:2px solid rgba(20,184,166,0.4)}
.cmp-flag{font-size:22px}.cmp-name{font-size:17px;font-weight:900;font-family:Georgia,serif;color:#fff;margin:4px 0 2px}
.cmp-rec{font-size:22px;font-weight:900;margin:6px 0 2px}.cmp-rec .w{color:var(--teal)}.cmp-rec .l{color:#ef4444}
.cmp-sub{font-size:9px;color:#444;letter-spacing:1.5px;text-transform:uppercase;margin-bottom:10px}
.cmp-stat{display:flex;justify-content:space-between;font-size:11px;padding:4px 0;border-top:1px solid rgba(255,255,255,0.04)}
.cmp-stat .sl{color:#555}.cmp-stat .sv{color:#bbb;font-weight:700}
.cmp-common{background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.07);border-radius:12px;padding:16px 20px}
.cmp-ctitle{font-size:10px;letter-spacing:3px;text-transform:uppercase;color:var(--amber);font-weight:700;margin-bottom:12px;padding-bottom:10px;border-bottom:1px solid rgba(255,255,255,0.06)}
.cmp-tbl{width:100%;border-collapse:collapse;font-size:11px}
.cmp-tbl th{text-align:left;padding:4px 8px;font-size:8px;letter-spacing:2px;color:#444;text-transform:uppercase;border-bottom:1px solid rgba(255,255,255,0.06)}
.cmp-tbl td{padding:6px 8px;border-bottom:1px solid rgba(255,255,255,0.03)}.cmp-tbl tr:last-child td{border:none}
.cmp-tbl .cn{color:#aaa;font-weight:700}.rW{color:var(--teal);font-weight:700}.rL{color:#ef4444;font-weight:700}.rN{color:#555}
.cmp-none{color:#444;font-size:12px;text-align:center;padding:24px}
@media(max-width:900px){
  #p-db{flex-direction:column;padding:12px 16px;gap:0}
  #p-stats{padding:16px}#page-compare{padding:16px}
  #hamburger{display:inline-block}
  #nav{padding:0 16px}
  #sidebar{display:none;position:fixed;top:0;left:0;bottom:0;width:280px;z-index:150;background:#0d0d14;border-right:1px solid var(--red-border);overflow-y:auto;padding:60px 16px 20px}
  #sidebar.open{display:block}
  .stat-boxes{gap:6px}.stat-box{padding:8px 10px;flex:1 1 70px}.stat-box .val{font-size:15px}
  .cmp-cards{grid-template-columns:1fr}
  .tw{overflow-x:auto;-webkit-overflow-scrolling:touch}
  thead th:first-child,tbody td:first-child{position:sticky;left:0;z-index:2;background:#0a0a0f}
  thead th:first-child{background:#0d0d14;z-index:3}
}
@media(max-width:600px){
  #fighter-profile{position:fixed;inset:0;top:46px;z-index:140;border-radius:0;overflow-y:auto;margin:0;background:#0a0a0f;border:none;border-top:1px solid var(--red-border)}
  .fp-body{grid-template-columns:1fr}.fp-section.full{grid-column:auto}
}"""

COMPARE_HTML = """\
<div id="page-compare" class="page">
  <div style="max-width:900px">
    <div style="font-size:10px;letter-spacing:4px;color:var(--indigo);text-transform:uppercase;margin-bottom:6px">Fighter Analysis</div>
    <div style="font-family:Georgia,serif;font-size:24px;font-weight:900;color:#fff;letter-spacing:-1px;margin-bottom:20px">HEAD-TO-HEAD <span style="color:var(--indigo)">COMPARE</span></div>
    <div class="cmp-row">
      <div class="cmp-col">
        <div class="cmp-lbl">Fighter 1</div>
        <div style="position:relative">
          <input type="text" id="cmp-f1" placeholder="Search fighter..." autocomplete="off" oninput="cmpDropdown(1)" onblur="setTimeout(()=>hideCmpDd(1),150)" onfocus="cmpDropdown(1)">
          <div id="cmp-dd1" class="cmp-dd"></div>
        </div>
      </div>
      <div class="cmp-vs-badge">VS</div>
      <div class="cmp-col">
        <div class="cmp-lbl">Fighter 2</div>
        <div style="position:relative">
          <input type="text" id="cmp-f2" placeholder="Search fighter..." autocomplete="off" oninput="cmpDropdown(2)" onblur="setTimeout(()=>hideCmpDd(2),150)" onfocus="cmpDropdown(2)">
          <div id="cmp-dd2" class="cmp-dd"></div>
        </div>
      </div>
      <button class="cmp-go" onclick="runCompare()">&#9654; Compare</button>
    </div>
    <div id="cmp-results" class="cmp-results">
      <div class="cmp-cards">
        <div class="cmp-card f1" id="cmp-card1"></div>
        <div class="cmp-card f2" id="cmp-card2"></div>
      </div>
      <div class="cmp-common">
        <div class="cmp-ctitle">&#9876; Common Opponents</div>
        <div id="cmp-common-body"></div>
      </div>
    </div>
  </div>
</div>"""

RENDER_TABLE_JS = """\
function toggleExpand(i,e){
  e.stopPropagation();
  const tb=document.getElementById('tbody');
  tb.querySelectorAll('.detail-row').forEach(r=>r.remove());
  tb.querySelectorAll('.data-row').forEach(r=>r.classList.remove('expanded'));
  if(expandedIdx===i){expandedIdx=-1;return;}
  expandedIdx=i;
  const f=pageData[i];if(!f)return;
  const row=tb.querySelector('.data-row[data-idx="'+i+'"]');if(!row)return;
  row.classList.add('expanded');
  const yr=f.year||(f.event_date||'').match(/\\d{4}/)?.[0]||'';
  const ytQ=encodeURIComponent(f.fighter1+' vs '+f.fighter2+' full fight UFC '+yr);
  const ytUrl='https://www.youtube.com/results?search_query='+ytQ;
  const detail=document.createElement('tr');
  detail.className='detail-row';
  let dhtml='<td colspan="12"><div class="exp-inner"><div class="exp-grid">';
  dhtml+='<div class="exp-item"><div class="exp-lbl">Method</div><div class="exp-val">'+(f.method||'&mdash;')+'</div></div>';
  dhtml+='<div class="exp-item"><div class="exp-lbl">Round</div><div class="exp-val">R'+(f.round||'&mdash;')+'</div></div>';
  dhtml+='<div class="exp-item"><div class="exp-lbl">Time</div><div class="exp-val">'+(f.time||'&mdash;')+'</div></div>';
  dhtml+='<div class="exp-item"><div class="exp-lbl">Referee</div><div class="exp-val">'+(f.referee||'&mdash;')+'</div></div>';
  if(f.is_title==='1')dhtml+='<div class="exp-title">&#127942; TITLE FIGHT</div>';
  dhtml+='</div><div class="exp-actions">';
  dhtml+='<a class="exp-btn yt" href="'+ytUrl+'" target="_blank" rel="noopener">&#9654; Watch on YouTube</a>';
  if(f.fight_url)dhtml+='<a class="exp-btn uf" href="'+f.fight_url+'" target="_blank" rel="noopener">&#128202; UFCStats</a>';
  dhtml+='</div></div></td>';
  detail.innerHTML=dhtml;
  row.after(detail);
}
function renderTable(){
  const tot=Math.ceil(filtered.length/PAGE_SIZE),st=(curPage-1)*PAGE_SIZE,en=Math.min(st+PAGE_SIZE,filtered.length);
  document.getElementById('ri').innerHTML='<span>'+(st+1).toLocaleString()+'&ndash;'+en.toLocaleString()+'</span>';
  document.getElementById('ti2').innerHTML='<span>'+filtered.length.toLocaleString()+'</span>';
  document.getElementById('pl').textContent=curPage+' / '+(tot||1);
  document.getElementById('pp').disabled=curPage<=1;
  document.getElementById('pn-btn').disabled=curPage>=tot;
  pageData=filtered.slice(st,en); expandedIdx=-1;
  const tb=document.getElementById('tbody');
  if(!pageData.length){tb.innerHTML='<tr><td colspan="12" class="nr">No fights match your filters.</td></tr>';return;}
  tb.innerHTML=pageData.map(function(f,i){
    const w1=f.winner===f.fighter1,w2=f.winner===f.fighter2,m=f.method||'&mdash;';
    const f1f=flag(f.country1),f2f=flag(f.country2);
    const n1=f1f?f1f+'<span class="nat-txt">'+(f.country1||'')+'</span>':'<span class="nat-txt" style="color:#333">'+(f.country1||'')+'</span>';
    const n2=f2f?f2f+'<span class="nat-txt">'+(f.country2||'')+'</span>':'<span class="nat-txt" style="color:#333">'+(f.country2||'')+'</span>';
    const bonus=(f.bonus&&f.bonus!=='nan'&&f.bonus!==''&&f.bonus!=='0')?'&#11088;':'';
    const titleMark=f.is_title==='1'?'&#127942;':'';
    let r='<tr class="data-row" data-idx="'+i+'" onclick="toggleExpand('+i+',event)">';
    r+='<td class="en" title="'+(f.event_name||'').replace(/"/g,'&quot;')+'">'+titleMark+bonus+(f.event_name||'&mdash;')+'</td>';
    r+='<td class="ed">'+(f.event_date||'&mdash;')+'</td>';
    r+='<td class="fc"><span class="fn '+(w1?'won':'lost')+'">'+(w1?'<span class="wm">&#9654;</span> ':'')+(f.fighter1||'&mdash;')+'</span></td>';
    r+='<td class="nc">'+n1+'</td><td class="vs">vs</td>';
    r+='<td class="fc"><span class="fn '+(w2?'won':'lost')+'">'+(w2?'<span class="wm">&#9654;</span> ':'')+(f.fighter2||'&mdash;')+'</span></td>';
    r+='<td class="nc">'+n2+'</td>';
    r+='<td class="div">'+(f.weight_class||'&mdash;')+'</td>';
    r+='<td><span class="mb-badge '+mc(m)+'">'+m+'</span></td>';
    r+='<td class="tim">'+(f.time||'&mdash;')+'</td>';
    r+='<td class="ref">'+(f.referee||'&mdash;')+'</td>';
    r+='<td class="odds-cell">'+oddsDisplay(f)+'</td>';
    r+='</tr>';
    return r;
  }).join('');"""

TIMELINE_JS = """\
    <div class="fp-section full">
      <div class="fp-sec-title teal">Career Timeline</div>
      <div class="tl-outer"><div class="tl-track">${fights.slice().sort((a,b)=>(parseInt(a.year)||0)-(parseInt(b.year)||0)).map(f=>{
        const r=f.won?'W':f.lost?'L':'NC';
        const tc=f.isTitle?' title':'';
        const tip=`${r} vs ${f.opponent} \u00b7 ${f.method||'?'} R${f.round||'?'} \u00b7 ${f.year||'?'}`;
        return `<div class="tl-item"><div class="tl-dot ${r}${tc}"><span class="tl-tip">${tip}</span>${r}</div><div class="tl-yr">${f.year||''}</div></div>`;
      }).join('')}</div></div>
    </div>"""

NEW_INIT_JS = """\
// -- H2H COMPARE --
let cmpSelected={'1':'','2':''};
function cmpDropdown(n){
  const inp=document.getElementById('cmp-f'+n),dd=document.getElementById('cmp-dd'+n);
  const q=inp.value.toLowerCase().trim();
  if(q.length<2){dd.style.display='none';return;}
  const matches=FIGHTER_NAMES.filter(nm=>nm.toLowerCase().includes(q))
    .sort((a,b)=>{const as=a.toLowerCase().startsWith(q)?0:1,bs=b.toLowerCase().startsWith(q)?0:1;return as-bs||a.localeCompare(b);})
    .slice(0,10);
  if(!matches.length){dd.style.display='none';return;}
  dd.innerHTML=matches.map(nm=>{
    const nat=FIGHTER_NAT[nm]||'',fl=flag(nat);
    return `<div class="fd-item" onmousedown="pickCmpFighter(${n},this)" data-name="${nm}">${fl?`<span class="fd-flag">${fl}</span>`:''}<span class="fd-name">${nm}</span><span class="fd-nat">${nat}</span></div>`;
  }).join('');
  dd.style.display='block';
}
function pickCmpFighter(n,el){const name=el.dataset.name;document.getElementById('cmp-f'+n).value=name;cmpSelected[String(n)]=name;hideCmpDd(n);}
function hideCmpDd(n){document.getElementById('cmp-dd'+n).style.display='none';}
function openCompareWith(name){
  document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
  document.getElementById('page-compare').classList.add('active');
  document.querySelectorAll('.nav-tab').forEach(t=>t.classList.remove('active'));
  const ct=[...document.querySelectorAll('.nav-tab')].find(t=>t.textContent.trim()==='Compare');
  if(ct)ct.classList.add('active');
  document.getElementById('cmp-f1').value=name;
  cmpSelected['1']=name;
}
function fighterStats(name){
  const ff=FIGHTS.filter(f=>f.fighter1===name||f.fighter2===name);
  const fights=ff.map(f=>{
    const s1=f.fighter1===name;
    return{opponent:s1?f.fighter2:f.fighter1,won:f.winner===name,
      lost:f.winner&&f.winner!==name&&f.winner!=='NC'&&f.winner!=='Draw',method:f.method,round:f.round,year:f.year};
  });
  const W=fights.filter(x=>x.won).length,L=fights.filter(x=>x.lost).length;
  const wins=fights.filter(x=>x.won);
  const koW=wins.filter(x=>x.method==='KO/TKO').length,subW=wins.filter(x=>x.method==='Submission').length;
  return{name,nat:FIGHTER_NAT[name]||'',W,L,NC:fights.length-W-L,total:fights.length,koW,subW,decW:wins.length-koW-subW,fights};
}
function runCompare(){
  const n1=cmpSelected['1']||document.getElementById('cmp-f1').value.trim();
  const n2=cmpSelected['2']||document.getElementById('cmp-f2').value.trim();
  if(!n1||!n2){alert('Please select two fighters');return;}
  cmpSelected['1']=n1;cmpSelected['2']=n2;
  const s1=fighterStats(n1),s2=fighterStats(n2);
  function card(s){
    const fl=flag(s.nat),wr=s.total?Math.round(s.W/s.total*100):0,fr=s.W?Math.round((s.koW+s.subW)/s.W*100):0;
    return `<div class="cmp-flag">${fl||''}</div><div class="cmp-name">${s.name}</div>`
      +`<div class="cmp-rec"><span class="w">${s.W}</span>&ndash;<span class="l">${s.L}</span>${s.NC>0?`<span style="color:#555;font-size:14px">&ndash;${s.NC}</span>`:''}</div>`
      +`<div class="cmp-sub">W &ndash; L${s.NC?' &ndash; NC':''}</div>`
      +`<div class="cmp-stat"><span class="sl">Total fights</span><span class="sv">${s.total}</span></div>`
      +`<div class="cmp-stat"><span class="sl">Win rate</span><span class="sv">${wr}%</span></div>`
      +`<div class="cmp-stat"><span class="sl">KO/TKO wins</span><span class="sv">${s.koW}</span></div>`
      +`<div class="cmp-stat"><span class="sl">Submission wins</span><span class="sv">${s.subW}</span></div>`
      +`<div class="cmp-stat"><span class="sl">Finish rate</span><span class="sv">${fr}%</span></div>`;
  }
  document.getElementById('cmp-card1').innerHTML=card(s1);
  document.getElementById('cmp-card2').innerHTML=card(s2);
  const opps1=new Set(s1.fights.map(x=>x.opponent));
  const commonOpps=[...new Set(s2.fights.filter(x=>opps1.has(x.opponent)).map(x=>x.opponent))];
  if(!commonOpps.length){
    document.getElementById('cmp-common-body').innerHTML='<div class="cmp-none">No common opponents found.</div>';
  } else {
    const rows=commonOpps.map(opp=>{
      const r1=s1.fights.find(x=>x.opponent===opp),r2=s2.fights.find(x=>x.opponent===opp);
      const res=r=>`<span class="${r.won?'rW':r.lost?'rL':'rN'}">${r.won?'W':r.lost?'L':'NC'}</span> <span style="color:#555;font-size:10px">${r.method||'?'} R${r.round||'?'}</span>`;
      return `<tr><td class="cn">${opp}</td><td>${r1?res(r1):'&mdash;'}</td><td>${r2?res(r2):'&mdash;'}</td></tr>`;
    }).join('');
    document.getElementById('cmp-common-body').innerHTML=`<table class="cmp-tbl"><thead><tr><th>Opponent</th><th>${n1}</th><th>${n2}</th></tr></thead><tbody>${rows}</tbody></table>`;
  }
  document.getElementById('cmp-results').style.display='block';
}
// -- INIT --
function initDashboard(){
  Object.keys(FIGHTER_NAT).forEach(k=>delete FIGHTER_NAT[k]);
  FIGHTS.forEach(f=>{
    if(f.fighter1&&!FIGHTER_NAT[f.fighter1])FIGHTER_NAT[f.fighter1]=f.country1||'';
    if(f.fighter2&&!FIGHTER_NAT[f.fighter2])FIGHTER_NAT[f.fighter2]=f.country2||'';
  });
  FIGHTER_NAMES.length=0;
  Object.keys(FIGHTER_NAT).sort().forEach(n=>FIGHTER_NAMES.push(n));
  const searchEl=document.getElementById('search');
  let _ddTimer=null;
  searchEl.addEventListener('input',()=>{
    if(profileOpen){closeFighterProfile();return;}
    applyFilters();
    clearTimeout(_ddTimer);
    _ddTimer=setTimeout(()=>showDropdown(searchEl.value),200);
  });
  searchEl.addEventListener('focus',()=>{if(!profileOpen&&searchEl.value.length>=2)showDropdown(searchEl.value);});
  searchEl.addEventListener('blur',()=>setTimeout(hideDropdown,150));
  ['f-weight','f-method','f-nat1','f-nat2','f-cont1','f-cont2','f-referee'].forEach(id=>
    document.getElementById(id).addEventListener('change',applyFilters)
  );
  const si=document.getElementById('si-event_date');
  if(si){si.textContent='\u25bc';si.parentElement.classList.add('srt');}
  populateFilters();
  applyFilters();
  const urlFighter=new URLSearchParams(location.search).get('fighter');
  if(urlFighter){
    const match=FIGHTER_NAMES.find(n=>n.toLowerCase()===urlFighter.toLowerCase())
      ||FIGHTER_NAMES.find(n=>n.toLowerCase().includes(urlFighter.toLowerCase()));
    if(match)setTimeout(()=>openFighterProfile(match),100);
  }
  document.getElementById('loading').style.display='none';
}
fetch('ufc_fights.json')
  .then(r=>{if(!r.ok)throw new Error('Failed to load fight data');return r.json();})
  .then(data=>{FIGHTS=data;filtered=[...FIGHTS];initDashboard();})
  .catch(err=>{
    document.getElementById('loading').innerHTML='<div class="ld-brand">FIGHT <span>DB</span></div>'
      +'<div style="color:#ef4444;margin-top:12px">'+err.message+'</div>'
      +'<div style="color:#444;font-size:11px;margin-top:8px">Serve via: python -m http.server 8765</div>';
  });
</script>
</body>
</html>"""

"""
chat_page.py, the MANTRA CHAT page served by chatd.py.

Left: a collapsible pane, golden ratio wide, with the claude.ai companion
controls (claude.ai refuses to be framed, so it opens as its own window
tiled beside this one). Right: the conversation mirror, Claude's answers with
READ, and the composer that sends to the Claude Code session.

READ opens the TELEPROMPTER: a fixed scrolling box in which the sentence
being read is pushed to the top edge, so the eyes stay in one place and the
text arrives. It is driven from a FLOATING PILL that can be dragged anywhere:
play and pause, speed minus and plus, font minus and plus, and X to end.
Closing the pill stops the reading and closes the teleprompter. The player
is the one from page.py: eased media clock, binary search for the word,
colour only on the word, instant jumps and never a smooth scroll.
"""

CSS = r"""
:root{--bg:#0b0d10;--panel:#10141a;--ink:#f2ddb4;--dim:#8b8578;--line:#1f2630;--slate:#23303d;
--amber:#f59e0b;--sent:#ffd93b;--sent-fg:#10120a;--wordbg:#e23b4e;--wordfg:#fff;--gold:38.2vw}
*{box-sizing:border-box}
html,body{height:100%;margin:0;background:var(--bg);color:var(--ink);
  font:17px/1.55 -apple-system,"Helvetica Neue",Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased}
body{display:flex;overflow:hidden}
#side{width:0;flex:0 0 auto;overflow:hidden;background:var(--panel);border-right:1px solid var(--line);transition:width .18s ease}
body.open #side{width:var(--gold);min-width:280px}
#side .in{width:var(--gold);min-width:280px;padding:18px 18px 30px;height:100%;overflow:auto}
#side h2{font:700 11px/1 ui-monospace,Menlo,monospace;letter-spacing:.14em;color:var(--amber);margin:0 0 12px}
#side p{margin:0 0 12px;color:var(--dim);font-size:14px}
#side .btns{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:18px}
.b{background:var(--amber);color:#0b0d10;border:0;border-radius:999px;font:700 12px/1 ui-monospace,Menlo,monospace;
  letter-spacing:.1em;padding:11px 16px;cursor:pointer;text-decoration:none;display:inline-block}
.b.ghost{background:transparent;color:var(--ink);border:1px solid var(--slate)}
#sessions{font:12px/1.6 ui-monospace,Menlo,monospace;color:var(--dim);white-space:pre-wrap}
#main{flex:1;display:flex;flex-direction:column;min-width:0;position:relative}
/* the top bar hides; it slides down when the mouse touches the top edge, or stays when pinned */
#hot{position:absolute;top:0;left:0;right:0;height:10px;z-index:14}
#top{position:absolute;top:0;left:0;right:0;z-index:15;display:flex;align-items:center;gap:12px;padding:10px 16px;
  border-bottom:1px solid var(--line);background:rgba(11,13,16,.96);transform:translateY(-100%);transition:transform .18s ease}
#top.show,body.pinned #top{transform:none}
#top .t{cursor:pointer}
#pin{background:transparent;border:1px solid var(--slate);color:var(--dim);border-radius:999px;font:700 10px/1 ui-monospace,Menlo,monospace;
  letter-spacing:.1em;padding:6px 9px;cursor:pointer}
body.pinned #pin{color:var(--amber);border-color:var(--amber)}
#tog{background:transparent;border:0;padding:6px;cursor:pointer;color:var(--ink);border-radius:8px;display:flex}
#tog:hover{background:var(--slate)}
#tog svg{width:24px;height:24px;display:block}
#top .t{font:700 12px/1 ui-monospace,Menlo,monospace;letter-spacing:.16em;color:var(--amber)}
#top .p{font:12px/1.3 ui-monospace,Menlo,monospace;color:var(--dim);flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
#dot{width:9px;height:9px;border-radius:50%;background:#e23b4e}
#dot.on{background:#3ddc84}
#list{flex:1;overflow:auto;padding:22px 16px 24px}
.msg{max-width:860px;margin:0 auto 18px;padding:14px 18px;border-radius:14px;background:var(--panel);border:1px solid var(--line)}
.msg.marko{background:#151a14;border-color:#26301f}
.msg.system{background:transparent;border:0;text-align:center;padding:4px;font:12px/1.4 ui-monospace,Menlo,monospace;color:var(--dim)}
.msg .who{font:700 10.5px/1 ui-monospace,Menlo,monospace;letter-spacing:.14em;color:var(--amber);margin-bottom:8px;display:flex;gap:10px;align-items:baseline}
.msg.marko .who{color:#9ccf7a}
.msg .who .tm{font-weight:400;color:var(--dim);letter-spacing:0}
.msg .body{white-space:pre-wrap;word-wrap:break-word;font-size:18px;line-height:1.6}
.msg .body pre{background:#0b0d10;border:1px solid var(--line);border-radius:8px;padding:10px 12px;overflow:auto;font-size:13px}
.msg .body code{background:#0b0d10;border-radius:4px;padding:0 4px;font-size:15px}
.msg .body b{color:#fff}
.msg .foot{display:flex;align-items:center;gap:10px;margin-top:10px;flex-wrap:wrap}
.msg.reading{border-color:var(--amber)}
.rd{background:var(--amber);color:#0b0d10;border:0;border-radius:999px;font:700 11px/1 ui-monospace,Menlo,monospace;
  letter-spacing:.12em;padding:9px 14px;cursor:pointer}
.rd.on{background:var(--slate);color:var(--ink)}
.st{font:11px/1.4 ui-monospace,Menlo,monospace;color:var(--dim)}
.st.bad{color:#e23b4e}
/* the teleprompter: the Beatrice window. Floating, dragged by its grip, resized from its corner,
   its scrollbar hidden; the sentence being read is pushed to the top edge inside it. */
#tp{position:fixed;left:50%;top:18px;transform:translateX(-50%);width:min(92vw,900px);height:46vh;display:none;
  min-width:320px;min-height:160px;resize:both;background:#07090c;border:1px solid var(--slate);border-radius:16px;
  box-shadow:0 20px 60px rgba(0,0,0,.6);z-index:20;overflow:hidden}
#tp.on{display:block}
#tp.drag{cursor:grabbing}
#tpgrip{position:absolute;left:0;right:0;top:0;height:26px;display:flex;align-items:center;gap:10px;padding:0 14px;
  cursor:grab;user-select:none;touch-action:none;z-index:2;background:linear-gradient(#0b0d10,rgba(11,13,16,0))}
#tpgrip .dots{width:22px;height:8px;border-top:2px dotted var(--dim);border-bottom:2px dotted var(--dim)}
#tpgrip .who{font:700 10px/1 ui-monospace,Menlo,monospace;letter-spacing:.16em;color:var(--amber)}
#tpgrip .cnt{font:10px/1 ui-monospace,Menlo,monospace;color:var(--dim);margin-left:auto}
#tpbox{position:absolute;inset:0;top:26px;overflow:auto;padding:12px 26px 80vh;scroll-behavior:auto;scrollbar-width:none}
#tpbox::-webkit-scrollbar{display:none}
#tpline{position:absolute;left:0;right:0;top:38px;height:0;border-top:1px dashed rgba(245,158,11,.35);pointer-events:none}
#tpdoc{white-space:pre-wrap;font-size:var(--tpfont,26px);line-height:1.6}
#tpcorner{position:absolute;right:4px;bottom:4px;width:14px;height:14px;border-right:2px solid var(--dim);border-bottom:2px solid var(--dim);
  border-radius:0 0 4px 0;opacity:.7;pointer-events:none}
#tpstatus{position:absolute;right:16px;bottom:8px;max-width:70%;text-align:right;pointer-events:none;
  font:10.5px/1.3 ui-monospace,Menlo,monospace;letter-spacing:.08em;color:var(--dim)}
#tpstatus.bad{color:#b8865a}
.sent{padding:1px 2px;border-radius:5px;transition:background .12s,color .12s,opacity .2s;opacity:.5;cursor:pointer}
.sent.done{opacity:.85}
.sent.active{background:var(--sent);color:var(--sent-fg);opacity:1;box-shadow:0 0 0 3px var(--sent)}
.sent.paused{background:rgba(255,217,59,.34);color:var(--ink);opacity:1;box-shadow:0 0 0 3px rgba(255,217,59,.34)}
.sent .w{border-radius:4px}
.sent.active .w.now,.sent.paused .w.now{background:var(--wordbg);color:var(--wordfg);padding:0 2px;margin:0 -2px;
  -webkit-box-decoration-break:clone;box-decoration-break:clone}
/* the floating pill */
#pill{position:fixed;left:50%;bottom:120px;transform:translateX(-50%);display:none;align-items:center;gap:6px;
  background:#151a21;border:1px solid var(--slate);border-radius:999px;padding:8px 10px;box-shadow:0 12px 40px rgba(0,0,0,.6);
  z-index:30;user-select:none;touch-action:none;cursor:grab}
#pill.on{display:flex}
#pill.drag{cursor:grabbing}
#pill button{background:transparent;color:var(--ink);border:1px solid transparent;border-radius:999px;width:40px;height:40px;
  font:700 15px/1 ui-monospace,Menlo,monospace;cursor:pointer;display:flex;align-items:center;justify-content:center}
#pill button:hover{border-color:var(--slate)}
#pill #pp{background:var(--amber);color:#0b0d10;width:52px}
#pill #px{color:#e23b4e}
#pill .v{font:700 11px/1 ui-monospace,Menlo,monospace;color:var(--amber);min-width:38px;text-align:center}
#pill .grip{width:10px;height:22px;border-left:2px dotted var(--dim);border-right:2px dotted var(--dim);margin:0 4px}
/* THE COMPOSER IS A BAND WHOSE HEIGHT HE SETS. His request, 3.9.2026: "make possible to change
   size of the chat box so there is a chat like a log and there is entry box. I want to be able
   with mouse to change the ratio of that two". The grip above the band drags; the textarea
   fills whatever height the band has; the height is remembered per browser. */
#composer{flex:0 0 auto;height:var(--ch,150px);min-height:90px;max-height:80vh;display:flex;flex-direction:column;
  border-top:1px solid var(--line);padding:0 16px 14px;background:var(--panel);position:relative}
#grip{flex:0 0 14px;cursor:row-resize;display:flex;align-items:center;justify-content:center;user-select:none;touch-action:none}
#grip i{display:block;width:56px;height:4px;border-radius:2px;background:var(--slate)}
#grip:hover i,#grip.drag i{background:var(--amber)}
#composer .in{max-width:860px;margin:0 auto;width:100%;flex:1;min-height:0;display:flex;flex-direction:column}
#rt{width:100%;flex:1;min-height:40px;background:#141a21;color:var(--ink);border:1px solid var(--slate);border-radius:12px;
  padding:12px 14px;font:17px/1.5 inherit;resize:none;outline:none}
#rt:focus{border-color:var(--amber)}
#composer .row{display:flex;align-items:center;gap:12px;margin-top:8px}
#composer.reading{box-shadow:inset 0 1px 0 var(--amber)}
#send{background:var(--amber);color:#0b0d10;border:0;border-radius:999px;font:700 12px/1 ui-monospace,Menlo,monospace;
  letter-spacing:.1em;padding:12px 18px;cursor:pointer}
#send:disabled{opacity:.5;cursor:default}
#rs{font:11px/1.4 ui-monospace,Menlo,monospace;color:var(--dim)}
#rs.ok{color:var(--amber)}
#rs.bad{color:#e23b4e}
#empty{text-align:center;color:var(--dim);padding:60px 20px;font-size:15px}
/* TALK: the microphone button beside SEND, green when it waits, red and pulsing while it listens,
   amber while Whisper writes; a small level bar so he sees he is heard; CANCEL while listening. */
#talk{background:#3fb862;color:#0b0d10;border:0;border-radius:999px;font:700 12px/1 ui-monospace,Menlo,monospace;
  letter-spacing:.1em;padding:12px 18px;cursor:pointer;transition:background .2s;min-width:96px}
#talk.listening{background:#e23b4e;color:#fff;animation:pulse 1.2s infinite}
#talk.thinking{background:#8a6a2a;color:#fff}
#cancel{background:#3a2323;color:#e08a8a;border:0;border-radius:999px;font:700 11px/1 ui-monospace,Menlo,monospace;
  letter-spacing:.1em;padding:12px 14px;cursor:pointer}
#cancel:hover{background:#5a2a2a;color:#fff}
#vu{width:64px;height:10px;border-radius:5px;background:#1c222b;border:1px solid var(--line);overflow:hidden;position:relative;flex:none}
#vu i{position:absolute;left:0;top:0;bottom:0;width:0;transition:width .08s linear;
  background:linear-gradient(90deg,#3fb862 0,#3fb862 60%,#e0c040 80%,#d04a3a 100%)}
@keyframes pulse{0%{box-shadow:0 0 0 0 rgba(226,59,78,.5)}70%{box-shadow:0 0 0 10px rgba(226,59,78,0)}100%{box-shadow:0 0 0 0 rgba(226,59,78,0)}}
/* the voice chip and AUTO VOICE in the top bar; the voices in the side pane */
#vchip,#auto{background:transparent;border:1px solid var(--slate);color:var(--dim);border-radius:999px;font:700 10px/1 ui-monospace,Menlo,monospace;
  letter-spacing:.1em;padding:6px 9px;cursor:pointer;white-space:nowrap}
#vchip{color:var(--amber);border-color:var(--amber)}
#auto.on{color:#3fb862;border-color:#3fb862}
#voices{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:12px}
#voices .b.on{background:var(--amber);color:#0b0d10;border-color:var(--amber)}
#vst{font:12px/1.5 ui-monospace,Menlo,monospace;color:var(--dim);min-height:18px}
/* reading in place: the card's body carries the sentences; a draft is read in a box where the entry box was */
.msg .body .sent{cursor:pointer;line-height:1.6}
#draftdoc{display:none;flex:1;min-height:40px;overflow:auto;background:#141a21;border:1px solid var(--amber);border-radius:12px;
  padding:12px 14px;white-space:pre-wrap;line-height:1.6}
"""

ICON = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round">'
        '<rect x="3" y="4" width="18" height="16" rx="3"/>'
        '<line x1="9.9" y1="4" x2="9.9" y2="20"/></svg>')

JS = r"""
const PORT = __PORT__;
const list = document.getElementById('list'), rt = document.getElementById('rt');
const sendBtn = document.getElementById('send'), rs = document.getElementById('rs');
const dot = document.getElementById('dot'), proj = document.getElementById('proj');
const sessions = document.getElementById('sessions'), sessLink = document.getElementById('sesslink');
const tp = document.getElementById('tp'), tpbox = document.getElementById('tpbox'), tpdoc = document.getElementById('tpdoc');
const tpstatus = document.getElementById('tpstatus');
/* THE STATUS LINE. Quiet, small, bottom right of the Beatrice window. Never in the middle of
   the screen, never a fright: waiting and errors alike go here in the same small type. */
let noteEl = null;                      /* the small line under the card being read */
function tpNote(msg, bad){
  tpstatus.textContent = msg || ''; tpstatus.className = bad ? 'bad' : '';
  if (noteEl){ noteEl.textContent = msg || ''; noteEl.className = (noteEl.id === 'rs' ? '' : 'st') + (bad ? ' bad' : ''); }
}
const draftdoc = document.getElementById('draftdoc');
const pill = document.getElementById('pill'), pp = document.getElementById('pp'), pspd = document.getElementById('pspd'), pfont = document.getElementById('pfont');
let lastId = 0, lastClaude = 0, SPEED = 1, FONT = 26, current = null, pending = null, SERVER_V = 0;
const SPEEDS = [0.75, 1, 1.25, 1.5, 1.75, 2, 2.5];
try { SPEED = parseFloat(localStorage.getItem('mantra.speed')) || 1; } catch(e){}
try { FONT = parseInt(localStorage.getItem('mantra.font')) || 26; } catch(e){}
try { if (localStorage.getItem('mantra.side') === '1') document.body.classList.add('open'); } catch(e){}
const TOP_PAD = 14;

/* ---------------------------------------------------------- top bar */
const topbar = document.getElementById('top'), hot = document.getElementById('hot');
let hideT = null;
function showTop(){ topbar.classList.add('show'); if (hideT) clearTimeout(hideT); }
function hideTopSoon(){ if (hideT) clearTimeout(hideT); hideT = setTimeout(() => topbar.classList.remove('show'), 700); }
hot.addEventListener('mouseenter', showTop);
topbar.addEventListener('mouseenter', showTop);
topbar.addEventListener('mouseleave', hideTopSoon);
document.getElementById('pin').onclick = () => {
  document.body.classList.toggle('pinned');
  try { localStorage.setItem('mantra.pin', document.body.classList.contains('pinned') ? '1' : '0'); } catch(e){}
};
try { if (localStorage.getItem('mantra.pin') === '1') document.body.classList.add('pinned'); } catch(e){}
showTop(); hideT = setTimeout(() => topbar.classList.remove('show'), 2500);

/* ---------------------------------------------------------- side pane */
document.getElementById('tog').onclick = () => {
  document.body.classList.toggle('open');
  try { localStorage.setItem('mantra.side', document.body.classList.contains('open') ? '1' : '0'); } catch(e){}
};
function pane(open){
  const st = document.getElementById('pst'); st.textContent = open ? 'Opening claude.ai beside this window…' : 'Hiding…';
  fetch('/api/pane', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({open})})
    .then(r => r.json()).then(j => { st.textContent = j.ok ? (open ? 'claude.ai is beside this window.' : 'claude.ai window hidden.') : ('Could not tile: ' + (j.detail||'')); })
    .catch(() => { st.textContent = 'Server not reachable.'; });
}
document.getElementById('pOpen').onclick = () => pane(true);
document.getElementById('pHide').onclick = () => pane(false);

/* ---------------------------------------------------------- rendering */
function esc(s){ return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
function md(s){
  const parts = s.split(/```/);
  let out = '';
  parts.forEach((p, i) => {
    if (i % 2){ out += '<pre>' + esc(p.replace(/^[a-z]*\n/, '')) + '</pre>'; return; }
    let t = esc(p);
    t = t.replace(/`([^`\n]+)`/g, '<code>$1</code>');
    t = t.replace(/\*\*([^*\n]+)\*\*/g, '<b>$1</b>');
    t = t.replace(/^#{1,6}\s*(.+)$/gm, '<b>$1</b>');
    t = t.replace(/^\s*[-*]\s+/gm, '• ');
    out += t;
  });
  return out;
}
function tm(iso){ try { return new Date(iso).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'}); } catch(e){ return ''; } }
function nearBottom(){ return list.scrollHeight - list.scrollTop - list.clientHeight < 160; }
function add(m, scroll){
  if (m.id <= lastId) return; lastId = m.id;
  const empty = document.getElementById('empty'); if (empty) empty.remove();
  const el = document.createElement('div'); el.className = 'msg ' + m.role; el.dataset.id = m.id;
  if (m.role === 'system'){
    el.textContent = m.text;
    if (m.project) proj.textContent = m.project + (m.cwd ? '  ' + m.cwd : '');
    if (m.bridge){ sessLink.href = 'https://claude.ai/code/' + m.bridge; sessLink.style.display = 'inline-block'; }
    sessions.textContent = (sessions.textContent ? sessions.textContent + '\n' : '') + tm(m.time) + '  ' + m.text;
  } else {
    const who = m.role === 'claude' ? 'CLAUDE' : 'MARKO';
    el.innerHTML = '<div class="who">' + who + '<span class="tm">' + tm(m.time) + (m.project ? ' · ' + esc(m.project) : '') + '</span></div>'
      + '<div class="body">' + md(m.text) + '</div>';
    if (m.role === 'claude') lastClaude = m.id;
    {   /* READ on every card, his and mine */
      const foot = document.createElement('div'); foot.className = 'foot';
      const rd = document.createElement('button'); rd.className = 'rd'; rd.textContent = 'READ';
      rd.onclick = () => readMsg(m, el, rd);
      /* WHEREVER HE CLICKS, THE VOICE JUMPS THERE (Marko, 8.9.2026). A click in the card's text starts
         the reading at that sentence; while the card is being read its sentences handle the click. */
      el.querySelector('.body').addEventListener('click', e => {
        if (current && current.msgEl === el) return;
        if (e.target.closest('a,pre,code')) return;
        readMsg(m, el, rd, snippetAt(e));
      });
      const st = document.createElement('span'); st.className = 'st';
      foot.appendChild(rd); foot.appendChild(st); el.appendChild(foot);
    }
  }
  list.appendChild(el);
  if (scroll) list.scrollTop = list.scrollHeight;
  return el;
}

/* ---------------------------------------------------------- the pill */
function fmtSpeed(){ return SPEED + '×'; }
function setSpeed(v){
  SPEED = v; try { localStorage.setItem('mantra.speed', v); } catch(e){}
  pspd.textContent = fmtSpeed();
  if (current) current.setSpeed(v);
}
function stepSpeed(d){
  let i = SPEEDS.indexOf(SPEED); if (i < 0) i = 1;
  i = Math.max(0, Math.min(SPEEDS.length - 1, i + d)); setSpeed(SPEEDS[i]);
}
function setFont(px){
  FONT = Math.max(14, Math.min(64, px)); try { localStorage.setItem('mantra.font', FONT); } catch(e){}
  document.documentElement.style.setProperty('--tpfont', FONT + 'px'); pfont.textContent = FONT;
  if (current && current.doc) current.doc.style.fontSize = FONT + 'px';
  if (current) current.lastSent = -1;       /* re-anchor the sentence after the reflow */
}
document.getElementById('psm').onclick = () => stepSpeed(-1);
document.getElementById('psp').onclick = () => stepSpeed(1);
document.getElementById('pfm').onclick = () => setFont(FONT - 2);
document.getElementById('pfp').onclick = () => setFont(FONT + 2);
pp.onclick = () => { if (current) current.toggle(); };
document.getElementById('px').onclick = () => endReading();
/* one drag helper for both floating windows. The pill drags by its body (not its buttons),
   the Beatrice window by its grip. Position is remembered; the window's size too. */
function draggable(el, handle, key, opts){
  let sx = 0, sy = 0, ox = 0, oy = 0, on = false;
  handle.addEventListener('pointerdown', e => {
    if (e.target.tagName === 'BUTTON') return;
    on = true; el.classList.add('drag'); handle.setPointerCapture(e.pointerId);
    const r = el.getBoundingClientRect(); sx = e.clientX; sy = e.clientY; ox = r.left; oy = r.top;
    el.style.transform = 'none'; el.style.left = r.left + 'px'; el.style.top = r.top + 'px'; el.style.bottom = 'auto';
  });
  handle.addEventListener('pointermove', e => {
    if (!on) return;
    const x = Math.max(0, Math.min(window.innerWidth - el.offsetWidth, ox + e.clientX - sx));
    const y = Math.max(0, Math.min(window.innerHeight - 40, oy + e.clientY - sy));
    el.style.left = x + 'px'; el.style.top = y + 'px';
  });
  const save = () => { try { localStorage.setItem(key, JSON.stringify({l: el.style.left, t: el.style.top, w: el.style.width, h: el.style.height})); } catch(e){} };
  const up = () => { if (!on) return; on = false; el.classList.remove('drag'); save(); };
  handle.addEventListener('pointerup', up); handle.addEventListener('pointercancel', up);
  if (opts && opts.size && window.ResizeObserver){
    let first = true;
    new ResizeObserver(() => { if (first){ first = false; return; } if (el.offsetWidth) { el.style.width = el.offsetWidth + 'px'; el.style.height = el.offsetHeight + 'px'; save(); } }).observe(el);
  }
  try { const p = JSON.parse(localStorage.getItem(key) || 'null');
    if (p && p.l){ el.style.transform = 'none'; el.style.left = p.l; el.style.top = p.t; el.style.bottom = 'auto';
      if (opts && opts.size && p.w){ el.style.width = p.w; el.style.height = p.h; } } } catch(e){}
}
draggable(pill, pill, 'mantra.pill');
draggable(tp, document.getElementById('tpgrip'), 'mantra.tp', {size: true});
document.getElementById('pb').onclick = () => { if (current) current.skip(-1); };
document.getElementById('pn').onclick = () => { if (current) current.skip(1); };
function showPill(){ pill.classList.add('on'); pspd.textContent = fmtSpeed(); pfont.textContent = FONT; }
function hidePill(){ pill.classList.remove('on'); }

/* ---------------------------------------------------------- the reader */
/* ONE SENTENCE AT A TIME. The plan gives every sentence at once, so the whole
   text stands in the teleprompter immediately. Sentence 0 is asked for; the
   moment sentence n starts to play, n+1 is asked for. A STOP aborts what is in
   flight and asks for nothing more. Each sentence is one clip and one cache
   file on the server, so nothing is made that is not about to be heard. */
const WORD_LEAD = 0.02, HANDOFF_LEAD = 0.06;
class Reader {
  constructor(plan, msgEl, btn, st){
    this.n = plan.count; this.texts = plan.sents; this.mid = plan.id;
    this.msgEl = msgEl; this.btn = btn; this.st = st;
    this.clips = new Array(this.n).fill(null); this.rows = new Array(this.n).fill(null);
    this.inflight = {}; this.ctls = []; this.ci = -1; this.waiting = -1; this.scale = 1;
    this.lastSent = -1; this.lastWord = -2; this.handed = false; this.raf = null; this.dead = false;
    this.clk = {pred:0, lastWall:0, lastObs:-1, ready:false};
    this.a = document.createElement('audio'); this.a.preload = 'auto';
    /* IN PLACE, ONE WINDOW (Marko, 8.9.2026: "I want to read, write and mark words from the chat
       interface without additional helping window"). The words are lit in the card itself: its body
       is swapped for the sentences while it is read and put back when the reading ends. A draft is
       read in a box that takes the entry box's place. */
    this.doc = msgEl.querySelector('.body');
    this.draft = !this.doc;
    if (this.draft){ this.doc = draftdoc; rt.style.display = 'none'; draftdoc.style.display = 'block'; }
    this.orig = this.doc.innerHTML; this.doc.innerHTML = ''; this.doc.appendChild(this.a);
    this.doc.style.fontSize = FONT + 'px';
    this.sents = this.texts.map((t, i) => {
      const el = document.createElement('span'); el.className = 'sent'; el.textContent = t + ' ';
      el.onclick = () => this.jumpTo(i); this.doc.appendChild(el); return el;
    });
    this.a.addEventListener('loadedmetadata', () => { const c = this.clips[this.ci]; if (c && c.prop && isFinite(this.a.duration)) this.scale = this.a.duration; });
    this.a.addEventListener('ended', () => { if (this.dead) return; if (!this.handed) this.next(); });
    this.a.addEventListener('play', () => { pp.textContent = '❚❚'; btn.textContent = 'READING'; btn.classList.add('on'); });
    this.a.addEventListener('pause', () => { if (!this.a.ended) pp.textContent = '▶'; });
  }
  /* fill sentence i with word spans once its clip is here */
  fill(i){
    const c = this.clips[i], el = this.sents[i]; el.textContent = '';
    const text = c.text || '', ws = []; let p = 0;
    (c.words || []).forEach(w => {
      const x = w.s|0, y = w.e|0;
      if (x > p) el.appendChild(document.createTextNode(text.slice(p, x)));
      const sp = document.createElement('span'); sp.className = 'w'; sp.textContent = text.slice(x, y); el.appendChild(sp);
      ws.push({el: sp, t: w.t, d: (w.d != null ? w.d : w.t)}); p = y;
    });
    if (p < text.length) el.appendChild(document.createTextNode(text.slice(p)));
    el.appendChild(document.createTextNode(' '));
    this.rows[i] = {el, words: ws};
  }
  ensure(i){
    if (this.dead || i < 0 || i >= this.n || this.clips[i] || this.inflight[i]) return;
    const ctl = new AbortController(); this.ctls.push(ctl); this.inflight[i] = true;
    fetch('/api/read/' + this.mid + '/sent/' + i, {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}', signal: ctl.signal})
      .then(r => r.json()).then(j => {
        if (this.dead) return; delete this.inflight[i];
        if (!j.ok){ this.st.textContent = j.error || 'the voice failed'; this.st.className = 'st bad'; tpNote(j.error || 'the voice failed', true); if (this.waiting === i) this.waiting = -1; return; }
        this.clips[i] = j.clip; this.fill(i);
        if (!j.cached) this.spent = (this.spent || 0) + (j.billed || 0);
        this.st.textContent = (this.spent ? this.spent + ' characters' : 'from cache') + ' · ' + (i + 1) + '/' + this.n + ' ready';
        const made = this.clips.filter(Boolean).length; if (this.waiting !== i) tpNote(made + ' / ' + this.n + ' cached');
        if (this.waiting === i){ this.waiting = -1; this.start(i); }
      }).catch(err => { if (this.dead || (err && err.name === 'AbortError')) return; delete this.inflight[i];
        this.st.textContent = 'Server not reachable'; this.st.className = 'st bad'; tpNote('server not reachable', true); if (this.waiting === i) this.waiting = -1; });
  }
  /* play sentence i now, or wait for it, and ask for the one after */
  start(i){
    if (i >= this.n){ this.finish(); return; }
    if (!this.clips[i]){ this.waiting = i; this.ensure(i); tpNote(i > 0 ? 'caching next sentence…' : 'asking ' + vlabel() + '…'); return; }
    tpNote(this.clips.filter(Boolean).length + ' / ' + this.n + ' cached'); document.getElementById('tpcnt').textContent = (i + 1) + ' / ' + this.n;
    this.ci = i; this.handed = false; this.lastSent = -1; this.lastWord = -2; this.scale = 1; this.clk.ready = false;
    this.a.src = this.clips[i].src; this.a.defaultPlaybackRate = SPEED; this.a.playbackRate = SPEED;
    this.a.play().then(() => { if (!this.raf) this.follow(); }).catch(() => { this.st.textContent = 'Press play on the pill, the browser blocked autoplay.'; if (!this.raf) this.follow(); });
    this.ensure(i + 1);
  }
  next(){ this.start(this.ci + 1); }
  setSpeed(v){ this.a.defaultPlaybackRate = v; this.a.playbackRate = v; }
  clock(observed, rate, playing){
    const k = this.clk, now = performance.now();
    if (!k.ready){ k.pred = observed||0; k.lastWall = now; k.lastObs = -1; k.ready = true; return k.pred; }
    const dt = (now - k.lastWall)/1000; k.lastWall = now;
    if (playing) k.pred += dt * (rate||1);
    if (observed !== k.lastObs){ k.lastObs = observed; const err = observed - k.pred; if (Math.abs(err) > 0.35) k.pred = observed; else k.pred += err * 0.5; }
    if (k.pred < 0) k.pred = 0; return k.pred;
  }
  /* THE TELEPROMPTER RULE: the sentence being read sits at the top edge of the box, instantly. */
  /* THE TELEPROMPTER RULE, in the log itself: the sentence being read is brought to the top edge of the
     log, instantly, never smoothly, unless the whole card already stands in view. A draft does not scroll. */
  toTop(el){
    if (this.draft) return;
    const L = list.getBoundingClientRect(), r = el.getBoundingClientRect(), c = this.msgEl.getBoundingClientRect();
    if (c.top >= L.top && c.bottom <= L.bottom) return;
    if (Math.abs(r.top - L.top - TOP_PAD) < 2) return;
    list.scrollTop += r.top - L.top - TOP_PAD;
  }
  follow(){
    this.raf = null; if (this.dead) return;
    const row = this.rows[this.ci];
    if (row){
      const t = this.clock(this.a.currentTime||0, this.a.playbackRate, !this.a.paused) + WORD_LEAD;
      const key = this.ci * 2 + (this.a.paused ? 1 : 0);
      if (key !== this.lastSent){ this.lastSent = key;
        this.doc.querySelectorAll('.sent.active,.sent.paused').forEach(e => { e.classList.remove('active','paused'); e.classList.add('done'); });
        row.el.classList.add(this.a.paused ? 'paused' : 'active'); this.toTop(row.el);
      }
      const sp = row.words;
      if (sp.length){
        let lo = 0, hi = sp.length-1, k = -1;
        while (lo <= hi){ const m = (lo+hi)>>1; if (sp[m].t*this.scale <= t){ k = m; lo = m+1; } else hi = m-1; }
        if (k === sp.length-1 && t > sp[k].d*this.scale + 0.12) k = -1;
        const wk = this.ci*1000 + k;
        if (wk !== this.lastWord){ this.lastWord = wk; sp.forEach((o, wi) => o.el.classList.toggle('now', wi === k)); }
      }
    }
    const dur = this.a.duration;
    if (!this.handed && !this.a.paused && dur && isFinite(dur) && this.a.currentTime >= dur - HANDOFF_LEAD && this.ci + 1 < this.n && this.clips[this.ci + 1]){
      this.handed = true; this.start(this.ci + 1);
    }
    this.raf = requestAnimationFrame(() => this.follow());
  }
  pause(){ this.a.pause(); }
  toggle(){
    if (this.waiting >= 0) return;
    if (this.a.paused){ if (this.a.ended && this.ci >= this.n - 1) this.start(0); else if (this.a.ended) this.next(); else this.a.play().catch(()=>{}); }
    else this.a.pause();
  }
  jumpTo(i){ this.a.pause(); this.start(i); }
  skip(d){ const i = Math.max(0, Math.min(this.n - 1, (this.ci < 0 ? 0 : this.ci) + d)); this.a.pause(); this.start(i); }
  finish(){ pp.textContent = '↺'; this.btn.textContent = 'READ AGAIN'; this.ci = this.n - 1; }
  destroy(){ this.dead = true; this.ctls.forEach(c => { try { c.abort(); } catch(e){} });
    try { this.a.pause(); } catch(e){} this.a.removeAttribute('src'); this.a.remove();
    if (this.raf) cancelAnimationFrame(this.raf); this.raf = null;
    this.doc.innerHTML = this.orig; this.doc.style.fontSize = '';           /* the card as it was */
    if (this.draft){ draftdoc.style.display = 'none'; rt.style.display = ''; }
    this.btn.textContent = 'READ'; this.btn.classList.remove('on'); this.msgEl.classList.remove('reading'); }
}
function openTP(msgEl){
  document.querySelectorAll('.msg.reading').forEach(e => e.classList.remove('reading'));
  msgEl.classList.add('reading');                  /* one window: no teleprompter, the card itself is read */
  document.documentElement.style.setProperty('--tpfont', FONT + 'px');
}
function endReading(){
  if (pending){ pending.abort(); pending = null; }
  if (current){ current.destroy(); current = null; }
  tpNote(''); noteEl = null; tp.classList.remove('on'); hidePill();
  document.querySelectorAll('.msg.reading').forEach(e => e.classList.remove('reading'));
  document.querySelectorAll('.rd').forEach(b => { b.textContent = 'READ'; b.classList.remove('on'); });
}
/* the text around a click: forty characters of the text node under the pointer, so the sentence
   the click fell in can be found among the plan's sentences (the plan's text is the spoken form,
   so offsets do not match; a window of words does) */
function snippetAt(e){
  let r = null;
  try { r = document.caretRangeFromPoint ? document.caretRangeFromPoint(e.clientX, e.clientY) : null; } catch(err){}
  if (!r || !r.startContainer) return '';
  const n = r.startContainer, s = n.nodeType === 3 ? n.textContent : (n.textContent || ''), o = r.startOffset || 0;
  return s.slice(Math.max(0, o - 24), o + 24);
}
const normTxt = s => (s || '').replace(/[`*#_>|]/g, '').replace(/\s+/g, ' ').trim().toLowerCase();
function sentenceFor(plan, snippet){
  const key = normTxt(snippet); if (key.length < 6) return 0;
  const sents = plan.sents.map(normTxt);
  for (const win of [key, key.slice(8, 40), key.slice(16, 40)]){
    if (win.length < 6) continue;
    const i = sents.findIndex(t => t.includes(win)); if (i >= 0) return i;
  }
  /* no whole window inside one sentence: the sentence sharing the most words wins */
  const words = key.split(' ').filter(w => w.length > 3); let best = 0, score = 0;
  sents.forEach((t, i) => { const c = words.filter(w => t.includes(w)).length; if (c > score){ score = c; best = i; } });
  return best;
}
function readPlan(url, payload, el, btn, st, startKey){
  if (current && current.msgEl === el && !startKey){ current.toggle(); return; }
  endReading();
  st.textContent = ''; st.className = st.id === 'rs' ? '' : 'st'; noteEl = st;
  openTP(el); showPill();
  tpNote('asking ' + vlabel() + '…'); btn.textContent = 'WAITING'; btn.classList.add('on');
  pending = new AbortController();
  const ctl = pending;
  fetch(url, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload || {}), signal: ctl.signal})
    .then(r => r.json()).then(plan => {
      if (ctl !== pending) return; pending = null;
      if (!plan.ok){ st.textContent = plan.error || 'nothing to read'; st.className = 'bad'; tpNote(plan.error || 'nothing to read', true); return; }
      current = new Reader(plan, el, btn, st);
      current.start(startKey ? sentenceFor(plan, startKey) : 0);
    }).catch(err => {
      if (ctl !== pending) return; pending = null;
      if (err && err.name === 'AbortError') return;
      st.textContent = 'Server not reachable'; st.className = 'bad'; tpNote('server not reachable', true);
    });
}
function readMsg(m, el, btn, startKey){ readPlan('/api/read/' + m.id + '/plan', {}, el, btn, el.querySelector('.st'), startKey); }
/* READ beside SEND: hear the draft before it goes */
const composer = document.getElementById('composer'), rdraft = document.getElementById('rdraft');
rdraft.onclick = () => {
  const text = rt.value.trim();
  if (!text){ status('Nothing to read yet.'); return; }
  readPlan('/api/read/draft/plan', {text}, composer, rdraft, rs);
};

/* ---------------------------------------------------------- composer */
function status(msg, cls){ rs.textContent = msg; rs.className = cls || ''; }
function sendReply(){
  const text = rt.value.trim(); if (!text) return;
  sendBtn.disabled = true; status('Sending…');
  fetch('/api/send', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({text, reply_to: lastClaude})})
    .then(r => { if (!r.ok) throw new Error(r.status); sendBtn.disabled = false; rt.value = ''; status('Sent to Claude ' + tm(new Date().toISOString()), 'ok'); if (current) current.pause(); })
    .catch(() => { sendBtn.disabled = false; status('Server not reachable. Copy the text into the terminal.', 'bad'); });
}
sendBtn.onclick = sendReply;
/* ENTER SENDS. His request, 3.9.2026: "when I press enter, it sends the message to you command
   enter. It's too much work. Only enter works." Shift+Enter still makes a new line, and so does
   Option+Enter, for the rare answer that needs one. */
rt.addEventListener('keydown', e => {
  if (e.key !== 'Enter' || e.isComposing) return;
  if (e.shiftKey || e.altKey) return;
  e.preventDefault(); sendReply();
});
/* THE GRIP. Drag it up for a taller entry box, down for a longer log. The height is kept in
   localStorage, read inside a try because a browser with site data off throws on the way in. */
const grip = document.getElementById('grip');
const CH_KEY = 'mantra.composerH';
function setCH(h){
  h = Math.max(90, Math.min(Math.round(h), Math.round(window.innerHeight * 0.8)));
  composer.style.setProperty('--ch', h + 'px');
  try { localStorage.setItem(CH_KEY, String(h)); } catch(e){}
}
try { const saved = parseInt(localStorage.getItem(CH_KEY) || '', 10); if (saved > 0) setCH(saved); } catch(e){}
grip.addEventListener('pointerdown', e => {
  e.preventDefault();
  const y0 = e.clientY, h0 = composer.getBoundingClientRect().height;
  grip.classList.add('drag'); grip.setPointerCapture(e.pointerId);
  const move = ev => setCH(h0 + (y0 - ev.clientY));
  const up = () => { grip.classList.remove('drag'); grip.removeEventListener('pointermove', move); grip.removeEventListener('pointerup', up); grip.removeEventListener('pointercancel', up); };
  grip.addEventListener('pointermove', move); grip.addEventListener('pointerup', up); grip.addEventListener('pointercancel', up);
});
/* ---------------------------------------------------------- the voice */
/* Marko, 8.9.2026: "I need a record button which I can also toggle with the space bar to talk with
   you, and then I want to listen with my locally cloned voice what you are saying." The voice the
   sister talks with is the whole system's choice (~/.voice/voice.json): a cloned voice, local and
   free, or Beatrice. The chip in the top bar cycles through them; the side pane lists them. */
const talkBtn = document.getElementById('talk'), vu = document.getElementById('vu').firstElementChild, cancelBtn = document.getElementById('cancel');
const vchip = document.getElementById('vchip'), autoBtn = document.getElementById('auto'), voicesEl = document.getElementById('voices'), vst = document.getElementById('vst');
let VOICE = {engine: 'beatrice', label: 'Beatrice', voices: []}, AUTO = true, MIC = 'idle', rec = null, chunks = [], stream = null, actx = null, vuRaf = null, micTimer = null, queued = [];
try { AUTO = localStorage.getItem('mantra.auto') !== '0'; } catch(e){}
function vlabel(){ return VOICE.label || 'Beatrice'; }
function paintVoice(){
  vchip.textContent = 'VOICE: ' + vlabel().toUpperCase();
  document.querySelector('#tpgrip .who').textContent = vlabel().toUpperCase();
  autoBtn.classList.toggle('on', AUTO); autoBtn.textContent = AUTO ? 'AUTO VOICE ON' : 'AUTO VOICE OFF';
  voicesEl.innerHTML = '';
  const all = [{name: 'beatrice', label: 'Beatrice · Speechify'}].concat((VOICE.voices || []).map(n => ({name: n, label: n + ' · cloned, local'})));
  all.forEach(v => {
    const on = v.name === 'beatrice' ? VOICE.engine === 'beatrice' : (VOICE.engine === 'clone' && VOICE.voice === v.name);
    const b = document.createElement('button'); b.className = 'b ghost' + (on ? ' on' : ''); b.textContent = v.label.toUpperCase();
    b.onclick = () => setVoice(v.name); voicesEl.appendChild(b);
  });
  if (VOICE.available === false) vst.textContent = 'Only Beatrice here: ' + (VOICE.why || 'MANTRA_VOICE is not on this Mac.');
}
function loadVoice(){ return fetch('/api/voice').then(r => r.json()).then(j => { VOICE = j; paintVoice(); }).catch(() => {}); }
function setVoice(name){
  const body = name === 'beatrice' ? {engine: 'beatrice'} : {engine: 'clone', voice: name};
  vst.textContent = 'switching …';
  fetch('/api/voice', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)})
    .then(r => r.json()).then(j => { VOICE = j; paintVoice(); vst.textContent = 'The sister talks with ' + vlabel() + ' now.'; })
    .catch(() => { vst.textContent = 'Server not reachable.'; });
}
vchip.onclick = () => {
  const names = ['beatrice'].concat(VOICE.voices || []);
  const cur = VOICE.engine === 'beatrice' ? 'beatrice' : VOICE.voice;
  setVoice(names[(names.indexOf(cur) + 1) % names.length]);
};
autoBtn.onclick = () => { AUTO = !AUTO; try { localStorage.setItem('mantra.auto', AUTO ? '1' : '0'); } catch(e){} paintVoice(); };
loadVoice();

/* THE MICROPHONE. TALK or the space bar opens it; TALK or the space bar again sends: the recording
   goes to the server, Whisper (local, on the GPU) writes it down, and the words reach the session as
   if typed. Escape throws the recording away. The mouth closes first: a reading is paused when the
   microphone opens, or it would hear the sister and send her words back as his. Ninety seconds at most. */
function micState(s){
  MIC = s; talkBtn.className = s;
  talkBtn.textContent = s === 'listening' ? 'STOP · SEND' : s === 'thinking' ? '…' : 'TALK';
  cancelBtn.hidden = s !== 'listening'; if (s !== 'listening') vu.style.width = '0';
}
function meter(){
  if (!actx || MIC !== 'listening') return;
  const a = actx.analyser, buf = new Uint8Array(a.fftSize); a.getByteTimeDomainData(buf);
  let sum = 0; for (let i = 0; i < buf.length; i++){ const v = (buf[i] - 128) / 128; sum += v * v; }
  vu.style.width = Math.min(100, Math.round(Math.sqrt(sum / buf.length) * 400)) + '%';
  vuRaf = requestAnimationFrame(meter);
}
function pickMime(){ return ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', ''].find(m => !m || (window.MediaRecorder && MediaRecorder.isTypeSupported(m))) || ''; }
async function startMic(){
  if (MIC !== 'idle') return;
  if (!navigator.mediaDevices || !window.MediaRecorder){ status('This browser cannot record.', 'bad'); return; }
  if (current) current.pause();
  try { stream = await navigator.mediaDevices.getUserMedia({audio: {echoCancellation: true, noiseSuppression: true}}); }
  catch(e){ status('The microphone is not allowed: System Settings › Privacy & Security › Microphone › Google Chrome.', 'bad'); return; }
  const AC = window.AudioContext || window.webkitAudioContext; actx = new AC();
  actx.analyser = actx.createAnalyser(); actx.analyser.fftSize = 1024; actx.createMediaStreamSource(stream).connect(actx.analyser);
  const mime = pickMime(); chunks = [];
  rec = new MediaRecorder(stream, mime ? {mimeType: mime} : undefined);
  rec.ondataavailable = e => { if (e.data && e.data.size) chunks.push(e.data); };
  rec.start(250); micState('listening'); status('listening … the space bar or STOP sends, Escape cancels'); meter();
  micTimer = setTimeout(() => stopMic(true), 90000);
}
function closeMic(){
  if (micTimer) clearTimeout(micTimer); micTimer = null;
  if (vuRaf) cancelAnimationFrame(vuRaf); vuRaf = null;
  if (stream) stream.getTracks().forEach(t => t.stop()); stream = null;
  if (actx){ try { actx.close(); } catch(e){} } actx = null;
}
function stopMic(send){
  if (MIC !== 'listening' || !rec) return;
  const r = rec, mime = r.mimeType || 'audio/webm'; rec = null;
  r.onstop = () => {
    closeMic();
    if (!send){ micState('idle'); chunks = []; status('cancelled, nothing sent'); return; }
    const blob = new Blob(chunks, {type: mime}); chunks = [];
    micState('thinking'); status('writing it down …');
    fetch('/api/hear?send=1&page=' + lastClaude, {method: 'POST', headers: {'Content-Type': mime}, body: blob})
      .then(x => x.json()).then(j => {
        micState('idle');
        if (!j.ok){ status(j.error || 'the ears failed', 'bad'); return; }
        status('Sent to Claude ' + tm(new Date().toISOString()) + ' · heard in ' + j.secs + ' s', 'ok');
        if (queued.length){ const q = queued.shift(); queued.length = 0; speakCard(q[0], q[1]); }
      }).catch(() => { micState('idle'); status('Server not reachable.', 'bad'); });
  };
  try { r.stop(); } catch(e){ r.onstop(); }
}
function toggleMic(){ if (MIC === 'listening') stopMic(true); else if (MIC === 'idle') startMic(); }
talkBtn.onclick = toggleMic;
cancelBtn.onclick = () => stopMic(false);
/* AUTO VOICE: an answer of Claude is spoken the moment it arrives, in the chosen voice. Never into an
   open microphone: while he talks it waits, and speaks once his words have gone. */
function speakCard(m, el){
  const btn = el.querySelector('.rd'); if (!btn) return;
  if (MIC !== 'idle'){ queued.push([m, el]); return; }
  readMsg(m, el, btn);
}
/* CLONE MY VOICE: fifteen seconds of him reading anything, naturally. The model is shown the sample
   with every sentence it speaks; nothing is trained, nothing leaves the Mac. */
document.getElementById('cloneme').onclick = async () => {
  if (MIC !== 'idle') return;
  let s; try { s = await navigator.mediaDevices.getUserMedia({audio: true}); } catch(e){ vst.textContent = 'The microphone is not allowed.'; return; }
  const mime = pickMime(), parts = [];
  const r = new MediaRecorder(s, mime ? {mimeType: mime} : undefined); r.ondataavailable = e => { if (e.data.size) parts.push(e.data); };
  let left = 15; MIC = 'cloning'; talkBtn.disabled = true; vst.textContent = 'Read anything aloud, naturally … ' + left;
  const iv = setInterval(() => { left--; vst.textContent = 'Read anything aloud, naturally … ' + left; if (left <= 0){ clearInterval(iv); r.stop(); } }, 1000);
  r.onstop = () => {
    s.getTracks().forEach(t => t.stop());
    vst.textContent = 'Cutting the sample and writing its words …';
    fetch('/api/voice/clone?name=marko', {method: 'POST', headers: {'Content-Type': r.mimeType || 'audio/webm'}, body: new Blob(parts, {type: r.mimeType})})
      .then(x => x.json()).then(j => {
        MIC = 'idle'; talkBtn.disabled = false;
        if (!j.ok){ vst.textContent = j.error || 'cloning failed'; return; }
        VOICE = Object.assign(VOICE, j); paintVoice();
        vst.textContent = 'Your voice is here as "' + j.voice + '" and the sister talks with it now. READ on any card to hear it.';
      }).catch(() => { MIC = 'idle'; talkBtn.disabled = false; vst.textContent = 'Server not reachable.'; });
  };
  r.start(250);
};

document.addEventListener('keydown', e => {
  const tag = (e.target && e.target.tagName) || '';
  if (e.metaKey || e.ctrlKey || e.altKey) return;
  /* THE SPACE BAR TALKS (Marko, 8.9.2026). In the entry box it still types, unless the box is empty. */
  if (e.code === 'Space'){
    if (tag === 'INPUT') return;
    if (tag === 'TEXTAREA' && rt.value.trim()) return;
    e.preventDefault(); toggleMic(); return;
  }
  if (e.key === 'Escape' && MIC === 'listening'){ e.preventDefault(); stopMic(false); return; }
  if (tag === 'TEXTAREA' || tag === 'INPUT') return;
  if ((e.key === 'p' || e.key === 'P') && current) current.toggle();
  if (e.key === 'ArrowLeft' && current) current.skip(-1);
  if (e.key === 'ArrowRight' && current) current.skip(1);
  if (e.key === 'Escape' && (current || pending)) endReading();
  if (e.key === '+' || e.key === '=') { if (tp.classList.contains('on')) setFont(FONT + 2); }
  if (e.key === '-') { if (tp.classList.contains('on')) setFont(FONT - 2); }
});

/* ---------------------------------------------------------- live feed */
function connect(){
  const es = new EventSource('/api/events');
  es.onopen = () => dot.classList.add('on');
  /* a new server (a restart after a change): this page is old, it reloads itself */
  es.addEventListener('hello', ev => { try { const v = JSON.parse(ev.data).v; if (SERVER_V && v !== SERVER_V) location.reload(); SERVER_V = v; } catch(e){} });
  es.onerror = () => dot.classList.remove('on');
  es.onmessage = ev => {
    try {
      const m = JSON.parse(ev.data), el = add(m, nearBottom());
      /* AUTO VOICE: a fresh answer of Claude (not one replayed after a reconnect) is spoken at once */
      if (el && m.role === 'claude' && AUTO && Math.abs(Date.now() - new Date(m.time).getTime()) < 120000) speakCard(m, el);
    } catch(e){}
  };
}
setFont(FONT);
fetch('/api/messages?since=0&limit=300').then(r => r.json()).then(ms => {
  ms.forEach(m => add(m, false)); list.scrollTop = list.scrollHeight;
  if (!ms.length){ const d = document.createElement('div'); d.id = 'empty'; d.textContent = 'Nothing yet. Start a Claude Code session and the conversation appears here.'; list.appendChild(d); }
  if (!/static/.test(location.search)) connect();
}).catch(() => { connect(); });
"""

HTML = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>MANTRA CHAT</title>
<link rel="icon" type="image/svg+xml" href="data:image/svg+xml;base64,PHN2ZyB4bWxucz0naHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmcnIHZpZXdCb3g9JzAgMCAzMiAzMic+PHJlY3Qgd2lkdGg9JzMyJyBoZWlnaHQ9JzMyJyByeD0nNycgZmlsbD0nIzBiMGQxMCcvPjxwYXRoIGQ9J002IDYuNWgyMGEzLjIgMy4yIDAgMCAxIDMuMiAzLjJ2OWEzLjIgMy4yIDAgMCAxLTMuMiAzLjJIMTVsLTYuMiA0LjJ2LTQuMkg2YTMuMiAzLjIgMCAwIDEtMy4yLTMuMnYtOUEzLjIgMy4yIDAgMCAxIDYgNi41eicgZmlsbD0nI2YyZGRiNCcvPjxjaXJjbGUgY3g9JzExLjMnIGN5PScxNC4yJyByPScyLjEnIGZpbGw9JyMwYjBkMTAnLz48Y2lyY2xlIGN4PScxNycgY3k9JzE0LjInIHI9JzIuMScgZmlsbD0nI2UyM2I0ZScvPjxjaXJjbGUgY3g9JzIyLjcnIGN5PScxNC4yJyByPScyLjEnIGZpbGw9JyMwYjBkMTAnLz48L3N2Zz4=">
<style>%(css)s</style></head><body>
<aside id="side"><div class="in">
<h2>CLAUDE.AI BESIDE</h2>
<p>claude.ai refuses to live inside another page, so it opens as its own window tiled to the left of this one, the golden section. The icon at the top hides and shows this pane.</p>
<div class="btns"><button class="b" id="pOpen">OPEN CLAUDE.AI BESIDE</button><button class="b ghost" id="pHide">HIDE IT</button></div>
<p id="pst"></p>
<div class="btns"><a class="b ghost" href="https://claude.ai/new" target="_blank" rel="noopener">NEW CHAT ON CLAUDE.AI</a>
<a class="b ghost" id="sesslink" href="#" target="_blank" rel="noopener" style="display:none">THIS SESSION ON CLAUDE.AI</a></div>
<h2>VOICE</h2>
<p>TALK, or the space bar, opens the microphone; TALK or the space bar again sends the words to Claude, written down by Whisper here on this Mac. Escape throws a recording away. With AUTO VOICE on, every answer is spoken as it arrives, in the voice chosen here, the sentence and the word lit.</p>
<div id="voices"></div>
<div class="btns"><button class="b ghost" id="cloneme">CLONE MY VOICE · 15 SECONDS</button></div>
<p id="vst"></p>
<h2>READING</h2>
<p>READ lights the words in the card itself, one window: the sentence being read yellow, the word red, the sentence brought to the top edge of the log so the eyes stay put. A click on a sentence jumps there. The control pill has previous and next sentence, play and pause, speed minus and plus, font minus and plus, and X to end. Drag the pill anywhere. P pauses, arrows skip, Escape ends, plus and minus change the font.</p>
<h2>SESSIONS</h2><div id="sessions"></div>
</div></aside>
<main id="main">
<div id="hot"></div>
<div id="top"><button id="tog" title="Side pane">%(icon)s</button><span class="t" id="title">MANTRA CHAT</span><span class="p" id="proj">waiting for a session</span><button id="auto" title="speak every answer as it arrives">AUTO VOICE</button><button id="vchip" title="how the sister talks; click to change">VOICE</button><button id="pin" title="keep the bar">PIN</button><span id="dot" title="live"></span></div>
<div id="list"></div>
<div id="tp"><div id="tpgrip"><span class="dots"></span><span class="who">BEATRICE</span><span class="cnt" id="tpcnt"></span></div><div id="tpbox"><div id="tpdoc"></div></div><div id="tpline"></div><div id="tpcorner"></div>
<div id="tpstatus"></div></div>
<div id="composer"><div id="grip" title="drag to resize"><i></i></div><div class="in"><div id="draftdoc"></div><textarea id="rt" placeholder="Your answer to Claude. Enter sends, Shift+Enter is a new line."></textarea>
<div class="row"><button id="talk" title="the space bar, too">TALK</button><span id="vu"><i></i></span><button id="cancel" title="Escape" hidden>✕</button><button id="send">SEND TO CLAUDE</button><button id="rdraft" class="rd">READ</button><span id="rs"></span></div></div></div>
</main>
<div id="pill"><span class="grip"></span><button id="pb" title="previous sentence">⏮</button><button id="pp" title="play / pause">▶</button><button id="pn" title="next sentence">⏭</button>
<button id="psm" title="slower">−</button><span class="v" id="pspd">1×</span><button id="psp" title="faster">+</button>
<button id="pfm" title="smaller text">A−</button><span class="v" id="pfont">26</span><button id="pfp" title="larger text">A+</button>
<button id="px" title="end reading">✕</button></div>
<script>%(js)s</script></body></html>"""


def page_html(port):
    return HTML % {'css': CSS, 'icon': ICON, 'js': JS.replace('__PORT__', str(int(port)))}

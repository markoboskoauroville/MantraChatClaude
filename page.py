"""
page.py, the self contained player for T.

One HTML file, no external resources. The audio rides inside as data URIs,
one clip per chunk, with the Speechify word marks beside it. The player is
the offline reader from 3sh_i_ma_reader_v3_macos.sh (render 9953, clock
10005, word lookup 9987, follow 10046) with the handoff simplified to one
audio element that swaps clips. Sentence highlight is a change of colour;
the word highlight is colour only and never weight (word-timing.md §4).
"""

import base64
import html
import json

END = ('.', '!', '?')


def sentences_of(text, words):
    """Group tokens into sentences. A sentence ends at a word whose text
    ends in . ! or ?, or where the gap after it holds a paragraph break.
    Returns [{text, t, d, words:[{s,e,t,d}]}], s/e relative to the sentence."""
    if not words:
        return []
    groups, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        word = text[w['s']:w['e']]
        gap = text[w['e']:words[i + 1]['s']] if i + 1 < len(words) else ''
        if word.rstrip('"\')]').endswith(END) or '\n\n' in gap or gap.strip().startswith(END):
            groups.append(cur)
            cur = []
    if cur:
        groups.append(cur)
    out = []
    for gi, g in enumerate(groups):
        start = g[0]['s']
        end = groups[gi + 1][0]['s'] if gi + 1 < len(groups) else len(text)
        stext = text[start:end]
        out.append({'text': stext, 't': g[0]['t'], 'd': g[-1]['d'],
                    'words': [{'s': w['s'] - start, 'e': w['e'] - start,
                               't': w['t'], 'd': w['d']} for w in g]})
    return out


CSS = """
:root{--bg:#0b0d10;--ink:#f2ddb4;--dim:#8b8578;--sent:#ffd93b;--sent-fg:#10120a;
--sent-soft:rgba(255,217,59,.34);--wordbg:#e23b4e;--wordfg:#fff;--amber:#f59e0b}
html,body{background:var(--bg);color:var(--ink);margin:0}
body{font:22px/1.65 -apple-system,"Helvetica Neue",Helvetica,Arial,sans-serif;
  -webkit-font-smoothing:antialiased}
.top{position:sticky;top:0;background:rgba(11,13,16,.92);backdrop-filter:blur(6px);
  padding:12px 20px;display:flex;align-items:center;gap:14px;border-bottom:1px solid #1f2630;z-index:2}
.top .who{font:700 11px/1 ui-monospace,Menlo,monospace;letter-spacing:.14em;color:var(--amber)}
.top .meta{font:12px/1.3 ui-monospace,Menlo,monospace;color:var(--dim);flex:1}
button#play{background:var(--amber);color:#0b0d10;border:0;border-radius:999px;
  font:700 14px/1 ui-monospace,Menlo,monospace;letter-spacing:.1em;padding:12px 20px;cursor:pointer}
button#play.paused{background:#23303d;color:var(--ink)}
.spd{background:transparent;color:var(--dim);border:1px solid #23303d;border-radius:999px;
  font:700 11px/1 ui-monospace,Menlo,monospace;padding:8px 10px;cursor:pointer}
.spd.on{color:var(--amber);border-color:var(--amber)}
#doc{max-width:760px;margin:0 auto;padding:28px 22px 24px;white-space:pre-wrap}
"""

REPLY_CSS = """
#reply{max-width:760px;margin:0 auto 50vh;padding:0 22px 40px}
#reply .lbl{font:700 11px/1 ui-monospace,Menlo,monospace;letter-spacing:.14em;color:var(--amber);margin:8px 0 10px}
#rt{width:100%;box-sizing:border-box;min-height:120px;background:#141a21;color:var(--ink);
  border:1px solid #23303d;border-radius:10px;padding:14px;font:19px/1.5 inherit;resize:vertical;outline:none}
#rt:focus{border-color:var(--amber)}
#reply .row{display:flex;align-items:center;gap:14px;margin-top:10px}
#send{background:var(--amber);color:#0b0d10;border:0;border-radius:999px;
  font:700 13px/1 ui-monospace,Menlo,monospace;letter-spacing:.1em;padding:12px 18px;cursor:pointer}
#send:disabled{opacity:.5;cursor:default}
#rs{font:12px/1.4 ui-monospace,Menlo,monospace;color:var(--dim)}
#rs.ok{color:var(--amber)}
#rs.bad{color:#e23b4e}
#sentlog{margin-top:14px;font-size:16px;color:var(--dim);white-space:pre-wrap}
"""

CSS = CSS + REPLY_CSS + """
.sent{padding:1px 2px;border-radius:5px;transition:background .12s,color .12s,opacity .2s;opacity:.55;cursor:pointer}
.sent.done{opacity:.9}
.sent.active{background:var(--sent);color:var(--sent-fg);opacity:1;box-shadow:0 0 0 3px var(--sent)}
.sent.paused{background:var(--sent-soft);color:var(--ink);opacity:1;box-shadow:0 0 0 3px var(--sent-soft)}
.sent .w{border-radius:4px}
.sent.active .w.now,.sent.paused .w.now{background:var(--wordbg);color:var(--wordfg);
  padding:0 2px;margin:0 -2px;-webkit-box-decoration-break:clone;box-decoration-break:clone}
#tap{position:fixed;inset:0;display:none;align-items:center;justify-content:center;
  background:rgba(11,13,16,.7);z-index:3}
#tap.on{display:flex}
#tap b{background:var(--amber);color:#0b0d10;border-radius:999px;padding:22px 36px;
  font:700 18px/1 ui-monospace,Menlo,monospace;letter-spacing:.14em}
"""

JS = r"""
const CH = __DATA__;
const WORD_LEAD = 0.02, HANDOFF_LEAD = 0.06;
let SPEED = __SPEED__;
const AUTOPLAY = __AUTOPLAY__;
const a = document.getElementById('a'), doc = document.getElementById('doc');
const btn = document.getElementById('play'), tap = document.getElementById('tap');
let ci = 0, S = [], lastSent = -1, lastWord = -2, lastScroll = 0, handed = false, scale = 1;

function render(){
  doc.innerHTML = ''; S = [];
  CH.forEach((ch, c) => {
    const rows = [];
    ch.sents.forEach((s, i) => {
      const sent = document.createElement('span');
      sent.className = 'sent'; sent.dataset.c = c; sent.dataset.i = i;
      const text = s.text || '', words = s.words || [], wspans = []; let p = 0;
      words.forEach(w => {
        const x = w.s|0, y = w.e|0;
        if (x > p) sent.appendChild(document.createTextNode(text.slice(p, x)));
        const ws = document.createElement('span'); ws.className = 'w';
        ws.textContent = text.slice(x, y); sent.appendChild(ws);
        wspans.push({el: ws, t: w.t, d: (w.d != null ? w.d : w.t)}); p = y;
      });
      if (p < text.length) sent.appendChild(document.createTextNode(text.slice(p)));
      sent.onclick = () => jump(c, s.t);
      doc.appendChild(sent);
      rows.push({el: sent, t: s.t, d: s.d, words: wspans});
    });
    S.push(rows);
  });
}
/* drift corrected media clock, the reader's OFFCLK */
const CLK = {pred: 0, lastWall: 0, lastObs: -1, ready: false};
function clockReset(t){ CLK.pred = t||0; CLK.lastWall = performance.now(); CLK.lastObs = -1; CLK.ready = true; }
function clockSample(observed, rate, playing){
  const now = performance.now();
  if (!CLK.ready){ clockReset(observed); return CLK.pred; }
  const dt = (now - CLK.lastWall)/1000; CLK.lastWall = now;
  if (playing) CLK.pred += dt * (rate||1);
  if (observed !== CLK.lastObs){
    CLK.lastObs = observed;
    const err = observed - CLK.pred;
    if (Math.abs(err) > 0.35) CLK.pred = observed; else CLK.pred += err * 0.5;
  }
  if (CLK.pred < 0) CLK.pred = 0;
  return CLK.pred;
}
function sentAt(rows, t){
  let lo = 0, hi = rows.length-1, k = 0;
  while (lo <= hi){ const m = (lo+hi)>>1; if (rows[m].t*scale <= t){ k = m; lo = m+1; } else hi = m-1; }
  return k;
}
function highlightSentence(i, paused){
  const key = ci*100000 + i + (paused ? 0.5 : 0);
  if (key === lastSent) return; lastSent = key;
  document.querySelectorAll('.sent.active,.sent.paused').forEach(e => { e.classList.remove('active','paused'); e.classList.add('done'); });
  const el = S[ci][i].el; el.classList.add(paused ? 'paused' : 'active');
  const r = el.getBoundingClientRect();
  if (r.top < 70 || r.bottom > window.innerHeight * 0.7){
    lastScroll = Date.now();
    window.scrollTo({top: window.scrollY + r.top - 90, behavior: 'auto'});
  }
}
function highlightWord(i, t){
  const spans = S[ci][i].words; if (!spans.length) return;
  let lo = 0, hi = spans.length-1, k = -1;
  while (lo <= hi){ const m = (lo+hi)>>1; if (spans[m].t*scale <= t){ k = m; lo = m+1; } else hi = m-1; }
  if (k === spans.length-1 && t > spans[k].d*scale + 0.12) k = -1;
  const key = ci*100000 + i*1000 + k;
  if (key === lastWord) return; lastWord = key;
  spans.forEach((o, wi) => o.el.classList.toggle('now', wi === k));
  if (k >= 0 && Date.now() - lastScroll > 250){
    const wr = spans[k].el.getBoundingClientRect();
    if (wr.top < 8 || wr.bottom > window.innerHeight - 70){
      lastScroll = Date.now(); window.scrollTo({top: window.scrollY + wr.top - 90, behavior: 'auto'});
    }
  }
}
function load(c){
  ci = c; handed = false; lastSent = -1; lastWord = -2;
  a.src = CH[c].src; scale = 1; CLK.ready = false;
  a.defaultPlaybackRate = SPEED; a.playbackRate = SPEED;
}
function setSpeed(v){
  SPEED = v; a.defaultPlaybackRate = v; a.playbackRate = v;
  document.querySelectorAll('.spd').forEach(b => b.classList.toggle('on', +b.dataset.v === v));
}
document.querySelectorAll('.spd').forEach(b => b.onclick = () => setSpeed(+b.dataset.v));
a.addEventListener('loadedmetadata', () => { if (CH[ci].prop && isFinite(a.duration)) scale = a.duration; });
function follow(){
  if (!S.length) return;
  const rows = S[ci];
  if (rows.length){
    const t = clockSample(a.currentTime||0, a.playbackRate, !a.paused) + WORD_LEAD;
    const i = sentAt(rows, t);
    highlightSentence(i, a.paused);
    highlightWord(i, t);
  }
  const dur = a.duration;
  if (!handed && !a.paused && dur && isFinite(dur) && a.currentTime >= dur - HANDOFF_LEAD && ci+1 < CH.length){
    handed = true; load(ci+1); a.play().catch(()=>{});
  }
  requestAnimationFrame(follow);
}
a.addEventListener('ended', () => {
  if (ci+1 < CH.length){ if (!handed){ load(ci+1); a.play().catch(()=>{}); } }
  else { btn.textContent = 'AGAIN'; btn.classList.add('paused'); }
});
function jump(c, t){
  if (c !== ci) load(c);
  const go = () => { a.currentTime = t*scale; clockReset(t*scale); a.play().catch(showTap); };
  if (a.readyState >= 1) go(); else a.addEventListener('loadedmetadata', go, {once: true});
}
function showTap(){ tap.classList.add('on'); }
function toggle(){
  if (a.paused){
    if (a.ended || (btn.textContent === 'AGAIN')){ load(0); }
    a.play().then(() => tap.classList.remove('on')).catch(showTap);
  } else a.pause();
}
a.addEventListener('play', () => { btn.textContent = 'PAUSE'; btn.classList.remove('paused'); tap.classList.remove('on'); });
a.addEventListener('pause', () => { if (!a.ended) { btn.textContent = 'PLAY'; btn.classList.add('paused'); } });
btn.onclick = toggle; tap.onclick = toggle;
document.addEventListener('keydown', e => {
  const tag = (e.target && e.target.tagName) || '';
  if (tag === 'TEXTAREA' || tag === 'INPUT') return;
  if (e.code === 'Space'){ e.preventDefault(); toggle(); }
});
__REPLY_JS__
render(); load(0); setSpeed(SPEED); requestAnimationFrame(follow);
if (AUTOPLAY) a.play().catch(showTap); else { btn.textContent = 'PLAY'; btn.classList.add('paused'); }
"""


REPLY_HTML = ('<div id="reply"><div class="lbl">YOUR ANSWER TO CLAUDE</div>'
              '<textarea id="rt" placeholder="Type here, then SEND. Cmd+Enter sends too."></textarea>'
              '<div class="row"><button id="send">SEND TO CLAUDE</button><span id="rs"></span></div>'
              '<div id="sentlog"></div></div>')

REPLY_JS = r"""
const INBOX = '__INBOX__', PAGE = '__PAGE__';
const rt = document.getElementById('rt'), sendBtn = document.getElementById('send');
const rs = document.getElementById('rs'), sentlog = document.getElementById('sentlog');
function status(msg, cls){ rs.textContent = msg; rs.className = cls || ''; }
function sendReply(){
  const text = rt.value.trim(); if (!text) return;
  sendBtn.disabled = true; status('Sending…');
  const fail = () => {
    sendBtn.disabled = false;
    const done = () => status('Inbox not reachable. Copied to the clipboard, paste it in the chat.', 'bad');
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(done, done); else done();
  };
  if (!INBOX){ fail(); return; }
  fetch(INBOX + '/reply', {method: 'POST', headers: {'Content-Type': 'text/plain'},
                           body: JSON.stringify({page: PAGE, text: text})})
    .then(r => { if (!r.ok) throw new Error(r.status);
      sendBtn.disabled = false; rt.value = '';
      const when = new Date().toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'});
      status('Sent to Claude ' + when, 'ok');
      sentlog.textContent = (sentlog.textContent ? sentlog.textContent + '\n\n' : '') + when + '  ' + text;
      if (!a.paused) a.pause();
    }).catch(fail);
}
sendBtn.onclick = sendReply;
rt.addEventListener('keydown', e => { if ((e.metaKey || e.ctrlKey) && e.key === 'Enter'){ e.preventDefault(); sendReply(); } });
"""


def reply_js(inbox, stamp):
    return REPLY_JS.replace('__INBOX__', inbox or '').replace('__PAGE__', stamp)


OLD_DOC_CSS = '#doc{max-width:760px;margin:0 auto;padding:28px 22px 60vh;white-space:pre-wrap}'
NEW_DOC_CSS = '#doc{max-width:760px;margin:0 auto;padding:28px 22px 24px;white-space:pre-wrap}'
OLD_KEYS = "document.addEventListener('keydown', e => { if (e.code === 'Space'){ e.preventDefault(); toggle(); } });"
NEW_KEYS = ("document.addEventListener('keydown', e => {\n"
            "  const tag = (e.target && e.target.tagName) || '';\n"
            "  if (tag === 'TEXTAREA' || tag === 'INPUT') return;\n"
            "  if (e.code === 'Space'){ e.preventDefault(); toggle(); }\n});")
BOOT = 'render(); load(0); setSpeed(SPEED); requestAnimationFrame(follow);'


def retrofit(page_html, inbox, stamp):
    """Add the reply box to a page built before it existed. No new audio."""
    h = page_html
    if 'id="reply"' in h:
        return h
    h = h.replace(OLD_DOC_CSS, NEW_DOC_CSS + REPLY_CSS, 1)
    h = h.replace('<div id="doc"></div>', '<div id="doc"></div>' + REPLY_HTML, 1)
    h = h.replace(OLD_KEYS, NEW_KEYS, 1)
    h = h.replace(BOOT, reply_js(inbox, stamp) + '\n' + BOOT, 1)
    return h


def build(clips, title, stamp, chars, speed=1.0, autoplay=True, inbox='', page_id=''):
    """clips: [{audio: bytes, text: str, words: [{s,e,t,d}], prop: bool}]."""
    data = []
    for c in clips:
        data.append({'src': 'data:audio/mpeg;base64,' + base64.b64encode(c['audio']).decode('ascii'),
                     'prop': bool(c.get('prop')),
                     'sents': sentences_of(c['text'], c['words'])})
    payload = json.dumps(data, ensure_ascii=False).replace('</', '<\\/')
    meta = '%s · %d characters · %d clip%s' % (stamp, chars, len(clips), '' if len(clips) == 1 else 's')
    spd = ''.join('<button class="spd" data-v="%g">%g×</button>' % (v, v) for v in (1, 1.25, 1.5, 2))
    script = (JS.replace('__DATA__', payload)
                .replace('__SPEED__', '%g' % float(speed))
                .replace('__AUTOPLAY__', 'true' if autoplay else 'false')
                .replace('__REPLY_JS__', reply_js(inbox, page_id or stamp)))
    head = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>' + html.escape(title) + '</title><style>' + CSS + '</style></head><body>')
    top = ('<div class="top"><span class="who">BEATRICE</span><span class="meta">' + html.escape(meta)
           + '</span>' + spd + '<button id="play">PLAY</button></div>')
    body = ('<audio id="a" preload="auto"></audio><div id="doc"></div>' + REPLY_HTML
            + '<div id="tap"><b>TAP TO PLAY</b></div>')
    return head + top + body + '<script>' + script + '</script></body></html>'

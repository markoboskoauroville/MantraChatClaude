#!/usr/bin/env python3
"""
chatd.py, the chat interface server. Flask, 127.0.0.1 only.

One page, MANTRA CHAT, that mirrors the Claude Code conversation of whatever
project is open: Marko's prompts and Claude's answers arrive through the
Claude Code hooks (chat_hook.py), Marko answers from the page and it lands
in ~/.tspeak/inbox where the session is watching, and every answer has a
READ button that speaks it with Beatrice and lights the words.

Port handling is the SAMPLE_PLAYER pattern: bind upward from 8825, write the
winner to ~/.tspeak/port.txt. Never holds a key, never talks to the network
except Speechify through the ring when READ is pressed.

  GET  /                    the page
  GET  /health              {ok, port, clients, messages}
  GET  /api/messages        ?since=<id>
  GET  /api/events          server sent events, one message per event
  POST /api/message         {role: claude|marko|system, text, session, cwd, project}
  POST /api/send            {text, reply_to}  Marko's answer from the page
  POST /reply               the older reading pages post here, same as /api/send
  POST /api/read/<id>       {speed} -> {clips:[{src, prop, sents}], billed, cached}
  POST /api/pane            {open: true|false} claude.ai window beside the page
  POST /api/open            open the page in the browser if nobody has it open
  POST /api/session         {event, session, cwd, project, bridge}
  GET  /api/voice           {engine, voice, voices, ears, clone}  how the sister talks (voice.py)
  POST /api/voice           {engine?, voice?}  choose: a cloned voice (local) or Beatrice
  POST /api/hear?send=1     the browser's recording in the body -> Whisper -> {text}; with send=1
                            the words go to the session as if typed (TALK, the space bar)
  POST /api/voice/clone?name=marko   a recording in the body becomes a new cloned voice
"""

import base64
import datetime
import json
import os
import queue
import socket
import subprocess
import shutil
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from flask import Flask, Response, jsonify, request, stream_with_context   # noqa: E402

from ring import Ring                          # noqa: E402
from speechify import synth                    # noqa: E402
from page import sentences_of                  # noqa: E402
from lastanswer import plain, chunk, sentences, _split_long   # noqa: E402
from chat_page import page_html                # noqa: E402
import voice as V                              # noqa: E402  the ears and the cloned voice

HOST = '127.0.0.1'
BASE = int(os.environ.get('TSPEAK_INBOX_PORT', '8825'))
DIR = os.path.expanduser('~/.tspeak')
CHAT = os.path.join(DIR, 'chat')
MSGS = os.path.join(CHAT, 'messages.jsonl')
AUDIO = os.path.join(CHAT, 'audio')
INBOX = os.path.join(DIR, 'inbox')
PORTFILE = os.path.join(DIR, 'port.txt')
LOG = os.path.join(DIR, 'chatd.log')
HS = '/opt/homebrew/bin/hs'
GOLDEN = 0.381966            # the smaller part of the golden section
TITLE = 'MANTRA CHAT'

app = Flask(__name__)
LOCK = threading.Lock()
SYNTH_LOCK = threading.Lock()
SUBS = []
MESSAGES = []
STATE = {'port': BASE, 'pane': False}
STARTED = int(__import__('time').time())   # this server's birth; the page reloads when it changes


# ------------------------------------------------------------------ storage
def log(msg):
    try:
        with open(LOG, 'a', encoding='utf-8') as fh:
            fh.write('%s %s\n' % (datetime.datetime.now().strftime('%H:%M:%S'), msg))
    except OSError:
        pass


def load():
    if not os.path.isfile(MSGS):
        return
    with open(MSGS, encoding='utf-8', errors='replace') as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                MESSAGES.append(json.loads(line))
            except ValueError:
                continue


def append(role, text, **meta):
    with LOCK:
        mid = (MESSAGES[-1]['id'] + 1) if MESSAGES else 1
        rec = {'id': mid, 'role': role, 'text': text,
               'time': datetime.datetime.now().isoformat(timespec='seconds')}
        for k, v in meta.items():
            if v not in (None, ''):
                rec[k] = v
        MESSAGES.append(rec)
        os.makedirs(CHAT, exist_ok=True)
        with open(MSGS, 'a', encoding='utf-8') as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + '\n')
        for q in list(SUBS):
            q.put(rec)
    if role == 'claude':
        try:
            sweep_cache(keep=mid)             # old cache goes before the new card is cached
            queue_card(mid)                   # the cloned voice starts on it before READ is pressed
        except Exception as e:                # noqa: BLE001
            log('queue_card %d: %s' % (mid, e))
    return rec


def write_inbox(text, page):
    """The same file the reading page writes, so the session's watcher fires."""
    now = datetime.datetime.now()
    stamp = now.strftime('%Y%m%d-%H%M%S-%f')[:-3]
    os.makedirs(INBOX, exist_ok=True)
    path = os.path.join(INBOX, stamp + '.json')
    rec = {'time': now.isoformat(timespec='seconds'), 'page': str(page or ''), 'text': text}
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fh:
        json.dump(rec, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, path)
    with open(os.path.join(INBOX, 'latest.txt'), 'w', encoding='utf-8') as fh:
        fh.write(text + '\n')
    return path


def body():
    raw = request.get_data(as_text=True) or ''
    if raw.lstrip().startswith('{'):
        try:
            return json.loads(raw)
        except ValueError:
            pass
    return {'text': raw}


# --------------------------------------------------------------------- http
@app.after_request
def cors(resp):
    resp.headers['Access-Control-Allow-Origin'] = '*'
    resp.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    resp.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    resp.headers['Cache-Control'] = 'no-store'
    return resp


@app.route('/', methods=['GET'])
def index():
    V.warm()                       # the ears and the voice load while he reads the page
    return Response(page_html(STATE['port']), mimetype='text/html')


@app.route('/health', methods=['GET'])
def health():
    return jsonify({'ok': True, 'port': STATE['port'], 'clients': len(SUBS),
                    'messages': len(MESSAGES), 'pane': STATE['pane'], 'inbox': INBOX,
                    'voice': who()})


@app.route('/api/messages', methods=['GET'])
def messages():
    since = int(request.args.get('since') or 0)
    limit = int(request.args.get('limit') or 300)
    out = [m for m in MESSAGES if m['id'] > since]
    return jsonify(out[-limit:])


@app.route('/api/events', methods=['GET'])
def events():
    q = queue.Queue()

    def gen():
        with LOCK:
            SUBS.append(q)
        try:
            yield 'retry: 2000\n\n'
            # a new server: the page compares this with what it knew and reloads itself,
            # so a restart after a change never leaves an old page on the screen
            yield 'event: hello\ndata: %s\n\n' % json.dumps({'v': STARTED, 'port': STATE['port']})
            while True:
                try:
                    rec = q.get(timeout=15)
                    yield 'data: %s\n\n' % json.dumps(rec, ensure_ascii=False)
                except queue.Empty:
                    yield ': ping\n\n'
        finally:
            with LOCK:
                if q in SUBS:
                    SUBS.remove(q)
    return Response(stream_with_context(gen()), mimetype='text/event-stream',
                    headers={'X-Accel-Buffering': 'no'})


@app.route('/api/message', methods=['POST', 'OPTIONS'])
def message():
    if request.method == 'OPTIONS':
        return ('', 204)
    d = body()
    text = str(d.get('text') or '').strip()
    role = str(d.get('role') or 'system')
    if role not in ('claude', 'marko', 'system'):
        role = 'system'
    if not text:
        return jsonify({'ok': False, 'error': 'empty'}), 400
    rec = append(role, text, session=d.get('session'), cwd=d.get('cwd'),
                 project=d.get('project'), source=d.get('source'))
    return jsonify({'ok': True, 'id': rec['id']})


@app.route('/api/send', methods=['POST', 'OPTIONS'])
@app.route('/reply', methods=['POST', 'OPTIONS'])
def send():
    if request.method == 'OPTIONS':
        return ('', 204)
    d = body()
    text = str(d.get('text') or '').strip()
    if not text:
        return jsonify({'ok': False, 'error': 'empty'}), 400
    page = d.get('reply_to') or d.get('page') or ''
    path = write_inbox(text, page)
    rec = append('marko', text, source='page', reply_to=page)
    return jsonify({'ok': True, 'file': path, 'id': rec['id']})


@app.route('/api/session', methods=['POST', 'OPTIONS'])
def session():
    if request.method == 'OPTIONS':
        return ('', 204)
    d = body()
    project = d.get('project') or os.path.basename(d.get('cwd') or '') or 'a project'
    ev = d.get('event') or 'start'
    sid = str(d.get('session') or '')[:8]
    text = 'Session %s in %s' % ('started' if ev == 'start' else ev, project)
    if sid:
        text += ' · ' + sid
    rec = append('system', text, session=d.get('session'), cwd=d.get('cwd'),
                 project=project, bridge=d.get('bridge'))
    return jsonify({'ok': True, 'id': rec['id']})


CHROME = '/Applications/Google Chrome.app'


def open_page():
    """Always Chrome, always an app window: no address bar, no tabs, no menus,
    resizable, the whole window is the page. Whatever the default browser is."""
    url = 'http://%s:%d/' % (HOST, STATE['port'])
    if os.path.isdir(CHROME):
        subprocess.Popen(['open', '-na', 'Google Chrome', '--args', '--app=' + url],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        subprocess.Popen(['open', url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return url


@app.route('/api/open', methods=['POST', 'OPTIONS'])
def api_open():
    if request.method == 'OPTIONS':
        return ('', 204)
    if SUBS and not body().get('force'):
        return jsonify({'ok': True, 'opened': False, 'clients': len(SUBS)})
    return jsonify({'ok': True, 'opened': True, 'url': open_page()})


# --------------------------------------------------------------------- read
@app.route('/api/read/<int:mid>', methods=['POST', 'OPTIONS'])
def read(mid):
    if request.method == 'OPTIONS':
        return ('', 204)
    msg = next((m for m in MESSAGES if m['id'] == mid), None)
    if not msg:
        return jsonify({'ok': False, 'error': 'no such message'}), 404
    cache = os.path.join(AUDIO, '%d.json' % mid)
    if os.path.isfile(cache):
        with open(cache, encoding='utf-8') as fh:
            data = json.load(fh)
        data['cached'] = True
        return jsonify(data)
    speech = plain(msg['text'])
    chunks = chunk(speech)
    if not chunks:
        return jsonify({'ok': False, 'error': 'nothing to read'}), 400
    clips, billed = [], 0
    with SYNTH_LOCK:
        ring = Ring()
        if not ring.keys:
            return jsonify({'ok': False, 'error': 'no Speechify keys in ' + ring.keyfile}), 503
        if not ring.usable():
            return jsonify({'ok': False, 'error': 'every Speechify key is dead or cooling'}), 503
        for c in chunks:
            try:
                audio, tokens, b, prop = synth(ring, c)
            except RuntimeError as e:
                log('read %d failed: %s' % (mid, e))
                return jsonify({'ok': False, 'error': str(e)}), 502
            billed += b
            clips.append({'src': 'data:audio/mpeg;base64,' + base64.b64encode(audio).decode('ascii'),
                          'prop': prop, 'sents': sentences_of(c, tokens)})
        label, masked = ring.active()
    data = {'ok': True, 'id': mid, 'clips': clips, 'billed': billed, 'key': label, 'cached': False}
    os.makedirs(AUDIO, exist_ok=True)
    with open(cache, 'w', encoding='utf-8') as fh:
        json.dump(data, fh)
    log('read %d: %d chunks, %d chars on %s %s' % (mid, len(chunks), billed, label, masked))
    return jsonify(data)


# ------------------------------------------------- read, one sentence at a time
# The page asks for the plan (the sentences), then for sentence 0, and while
# sentence n plays it asks for n+1. Each sentence is one Speechify call and one
# cache file, so a STOP wastes at most the sentence already in flight, and a
# second reading of the same card costs nothing.
PLANS = {}
SENT_LIMIT = 1800


def make_plan(pid, text):
    pieces = []
    for sent in sentences(plain(text)):
        sent = sent.strip()
        if not sent:
            continue
        pieces.extend(_split_long(sent, SENT_LIMIT) if len(sent) > SENT_LIMIT else [sent])
    plan = {'id': pid, 'count': len(pieces), 'sents': pieces}
    d = os.path.join(AUDIO, pid)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, 'plan.json'), 'w', encoding='utf-8') as fh:
        json.dump(plan, fh, ensure_ascii=False)
    PLANS[pid] = plan
    return plan


def read_plan(pid):
    """pid is a message id as a string, or 'd<hash>' for an unsent draft."""
    pid = str(pid)
    if pid in PLANS:
        return PLANS[pid]
    planfile = os.path.join(AUDIO, pid, 'plan.json')
    if os.path.isfile(planfile):
        with open(planfile, encoding='utf-8') as fh:
            PLANS[pid] = json.load(fh)
        return PLANS[pid]
    if pid.startswith('d'):
        return None
    try:
        mid = int(pid)
    except ValueError:
        return None
    msg = next((m for m in MESSAGES if m['id'] == mid), None)
    if not msg:
        return None
    return make_plan(pid, msg['text'])


@app.route('/api/read/draft/plan', methods=['POST', 'OPTIONS'])
def read_draft_plan():
    """A plan for text that has not been sent, keyed by its hash, so the same
    draft read twice is free and an edited draft is a new plan."""
    if request.method == 'OPTIONS':
        return ('', 204)
    import hashlib
    text = str(body().get('text') or '').strip()
    if not text:
        return jsonify({'ok': False, 'error': 'nothing to read'}), 400
    pid = 'd' + hashlib.sha1(text.encode('utf-8')).hexdigest()[:12]
    sweep_cache(keep=pid)                     # old cache goes before this draft's is made
    plan = PLANS.get(pid) or read_plan(pid) or make_plan(pid, text)
    if not plan['count']:
        return jsonify({'ok': False, 'error': 'nothing to read'}), 400
    return jsonify(dict(plan, ok=True, who=who()))


@app.route('/api/read/<int:mid>/plan', methods=['POST', 'OPTIONS'])
def read_plan_route(mid):
    mid = str(mid)
    if request.method == 'OPTIONS':
        return ('', 204)
    sweep_cache(keep=mid)                     # old cache goes before this card's is made
    plan = read_plan(mid)
    if plan is None:
        return jsonify({'ok': False, 'error': 'no such message'}), 404
    if not plan['count']:
        return jsonify({'ok': False, 'error': 'nothing to read'}), 400
    queue_card(mid)
    return jsonify(dict(plan, ok=True, who=who()))


# THE CACHE RUNS FROM THE SENTENCE PLAYING TO THE END (Marko, 9.9.2026: "start to cache all the
# sentences while playing. Work in the background until the end of the text. But as you read one
# sentence, delete that cache. When we come to the end, we have cache deleted." And: "if I jump to
# the middle of the page, then you cache until the end.")
#
# Every sentence is a job for one queue keyed (priority, sentence number): what the page waits for
# goes first (priority 0), the rest of the card follows in order (priority 1). A lock is not a
# queue: before this, three requests raced for SYNTH_LOCK and sentence 2 was often made before
# sentence 0. The page says where it is (/at/<i>): the cursor moves there, everything from i to the
# end is queued, and background jobs behind the cursor are dropped, so a jump caches from the
# jump onward. A sentence heard is deleted from this cache; the voice's own store keeps the mp3
# and its timing, so READ AGAIN is quick without the sister holding anything.
#
# Two stages, a pipeline: the clone makes sentence n+1 while the ears time sentence n. In a row
# they cost five to nine seconds a sentence, slower than speech; overlapped, about the clone's
# time alone. The cloned voice is local and free, so a card is queued the moment it arrives from
# the session, before READ is pressed; Beatrice costs per character, so she is made only for what
# the page asks and her clips are never deleted.
JOBS = queue.PriorityQueue()
TIMING = queue.Queue()
JOB_LOCK = threading.Lock()
TIME_LOCK = threading.Lock()
JOB_SEQ = [0]
JOB_DONE = {}          # (mid, n) -> threading.Event: queued, then set when made or failed
JOB_RESULT = {}        # (mid, n) -> (data, http status), taken by the request that waited
CURSOR = {}            # mid -> the sentence playing; background jobs before it are dropped
IN_FLIGHT = set()      # keys between the two stages; a second entry for one of them is dropped


def sentence_cache(mid, n, w):
    if w['engine'] == 'clone':
        # THE CLONED VOICE: local, free, cached per voice and model (voice.py). The
        # sister's cache file is named after the voice so Beatrice's clips and a
        # clone's never mix, and switching voices re-reads nothing already made.
        return os.path.join(AUDIO, mid, '%d.%s-%s.json' % (n, w['voice'], w['model']))
    return os.path.join(AUDIO, mid, '%d.json' % n)


def cached_sentence(mid, n, w):
    cache = sentence_cache(mid, n, w)
    if os.path.isfile(cache):
        with open(cache, encoding='utf-8') as fh:
            data = json.load(fh)
        data['cached'] = True
        return data
    return None


def made_ahead(mid, i, w):
    plan = read_plan(mid)
    if not plan:
        return 0
    return sum(1 for n in range(i + 1, plan['count']) if os.path.isfile(sentence_cache(mid, n, w)))


def store_clip(mid, n, w, text, audio, tokens, prop, billed, label, masked=''):
    clip = {'src': 'data:audio/mpeg;base64,' + base64.b64encode(audio).decode('ascii'),
            'prop': prop, 'text': text, 'words': tokens,
            'dur': (tokens[-1]['d'] if tokens and not prop else 0)}
    data = {'ok': True, 'id': mid, 'n': n, 'clip': clip, 'billed': billed, 'key': label, 'cached': False}
    cache = sentence_cache(mid, n, w)
    os.makedirs(os.path.dirname(cache), exist_ok=True)
    with open(cache, 'w', encoding='utf-8') as fh:
        json.dump(data, fh)
    if w['engine'] == 'clone':
        log('read %s/%d: %d chars in %s' % (mid, n, len(text), label))
    else:
        log('read %s/%d: %d chars on %s %s' % (mid, n, billed, label, masked))
    return data


def beatrice_sentence(mid, n, w, text):
    """One sentence by Speechify, both stages in one call. (data, http status)."""
    with SYNTH_LOCK:
        ring = Ring()
        if not ring.keys:
            return {'ok': False, 'error': 'no Speechify keys in ' + ring.keyfile}, 503
        if not ring.usable():
            return {'ok': False, 'error': 'every Speechify key is dead or cooling'}, 503
        try:
            audio, tokens, billed, prop = synth(ring, text)
        except RuntimeError as e:
            log('read %s/%d failed: %s' % (mid, n, e))
            return {'ok': False, 'error': str(e)}, 502
        label, masked = ring.active()
    return store_clip(mid, n, w, text, audio, tokens, prop, billed, label, masked), 200


def job_key(mid, n, w=None):
    """A job is a sentence IN A VOICE (Marko, 10.9.2026, after "the sentence was lost": a job finished
    in one voice looked finished for the next, so READ AGAIN after a voice change made nothing)."""
    w = w or who()
    return (str(mid), n, w['engine'], w['voice'], w['model'])


def voice_of(key):
    return {'engine': key[2], 'voice': key[3], 'model': key[4], 'label': key[3] if key[2] == 'clone' else 'Beatrice'}


def enqueue(mid, n, prio):
    """Queue sentence n of plan mid in the voice of this moment; a job already queued or made is left alone."""
    key = job_key(mid, n)
    with JOB_LOCK:
        ev = JOB_DONE.get(key)
        if ev is None:
            ev = JOB_DONE[key] = threading.Event()
        elif ev.is_set() or prio > 0:
            return ev
        JOB_SEQ[0] += 1
        JOBS.put((prio, n, JOB_SEQ[0], key))
    return ev


def forget(mid, n):
    """Drop what the sister holds for a sentence: its cache file (a clone's only;
    Beatrice's cost money), its event and its result. Asked for again, it is
    remade from the voice's own store in a moment."""
    with JOB_LOCK:
        for key in [k for k in JOB_DONE if k[0] == str(mid) and k[1] == n]:
            JOB_DONE.pop(key, None)
            JOB_RESULT.pop(key, None)
    w = who()
    if w['engine'] == 'clone':
        try:
            os.remove(sentence_cache(mid, n, w))
        except OSError:
            pass


STALE = 24 * 3600      # a cache entry untouched this long is old


def sweep_cache(keep=None):
    """OLD CACHE GOES BEFORE NEW CACHE COMES (Marko, 9.9.2026: "when you start reading the chat
    it needs to check for the stalled or old cache. If there is something not recent and it's
    there in the cache, before caching new it needs to delete old"). Called at the start of every
    reading and before a card is queued: every card folder under AUDIO whose newest file is
    older than STALE is removed, so are the whole-message <id>.json clips of the first design,
    which nothing reads any more. The card being read (`keep`) is never touched, whatever its
    age. Returns how many entries went."""
    if not os.path.isdir(AUDIO):
        return 0
    now = time.time()
    keep = None if keep is None else str(keep)
    gone = 0
    for name in os.listdir(AUDIO):
        path = os.path.join(AUDIO, name)
        if name == keep or name == '%s.json' % keep:
            continue
        try:
            if os.path.isdir(path):
                newest = max([os.path.getmtime(os.path.join(path, f)) for f in os.listdir(path)]
                             or [os.path.getmtime(path)])
                if now - newest < STALE:
                    continue
                shutil.rmtree(path, ignore_errors=True)
            elif name.endswith('.json'):              # a whole-message clip, the first design
                os.remove(path)
            else:
                continue
        except OSError:
            continue
        gone += 1
        PLANS.pop(name, None)
        CURSOR.pop(name, None)
        with JOB_LOCK:
            for key in [k for k in JOB_DONE if k[0] == name]:
                JOB_DONE.pop(key, None)
                JOB_RESULT.pop(key, None)
    if gone:
        log('sweep: %d old cache entr%s removed' % (gone, 'y' if gone == 1 else 'ies'))
    return gone


def queue_card(mid, start=None):
    """The card from `start` (or its cursor) to the end, in order, behind whatever
    the page is waiting for. Only for the cloned voice: local and free."""
    if who()['engine'] != 'clone':
        return
    plan = read_plan(mid)
    if not plan:
        return
    mid = str(mid)
    if start is None:
        start = CURSOR.get(mid, 0)
    for n in range(start, plan['count']):
        enqueue(mid, n, 1)


def finish_job(key, data, status):
    with JOB_LOCK:
        JOB_RESULT[key] = (data, status)
        ev = JOB_DONE.get(key)
        if status != 200:
            JOB_DONE.pop(key, None)         # so the next request tries again
    if ev:
        ev.set()


def stage_one():
    """The clone (or Beatrice) makes the audio, in order."""
    while True:
        prio, n, _seq, key = JOBS.get()
        mid, n = key[0], key[1]
        try:
            w = voice_of(key)
            now = who()
            if (w['engine'], w['voice']) != (now['engine'], now['voice']):   # the voice changed: the old voice's jobs are dropped
                finish_job(key, {'ok': False, 'error': 'the voice changed'}, 410)
                continue
            if prio > 0 and n < CURSOR.get(mid, 0):
                with JOB_LOCK:                              # behind the reader: made only if asked for
                    if not JOB_DONE.get(key, threading.Event()).is_set():
                        JOB_DONE.pop(key, None)
                continue
            with JOB_LOCK:
                if key in IN_FLIGHT:                       # asked for again while the ears time it
                    continue
            data = cached_sentence(mid, n, w)
            if data is not None:
                finish_job(key, data, 200)
                continue
            plan = read_plan(mid)
            if plan is None or n >= plan['count']:
                finish_job(key, {'ok': False, 'error': 'no such sentence'}, 404)
                continue
            text = plan['sents'][n]
            if w['engine'] == 'clone':
                with JOB_LOCK:
                    IN_FLIGHT.add(key)
                with SYNTH_LOCK:
                    path, tokens = V.clone_audio(text, w['voice'])
                TIMING.put((key, w, text, path, tokens))
            else:
                data, status = beatrice_sentence(mid, n, w, text)
                finish_job(key, data, status)
        except RuntimeError as e:
            log('read %s/%d failed: %s' % (mid, n, e))
            with JOB_LOCK:
                IN_FLIGHT.discard(key)
            finish_job(key, {'ok': False, 'error': str(e)}, 502)
        except Exception as e:                                  # noqa: BLE001
            log('stage one %s/%d: %s' % (mid, n, e))
            with JOB_LOCK:
                IN_FLIGHT.discard(key)
            finish_job(key, {'ok': False, 'error': str(e)}, 502)


def stage_two():
    """The ears time the clip while the clone is already on the next one."""
    while True:
        key, w, text, path, tokens = TIMING.get()
        mid, n = key
        try:
            if not tokens:
                with TIME_LOCK:
                    tokens = V.clone_tokens(path, text)
            from speechify import proportional_tokens
            prop = not tokens
            if prop:
                tokens = proportional_tokens(text)
            with open(path, 'rb') as fh:
                audio = fh.read()
            finish_job(key, store_clip(mid, n, w, text, audio, tokens, prop, 0, w['label']), 200)
        except Exception as e:                                  # noqa: BLE001
            log('stage two %s/%d: %s' % (mid, n, e))
            finish_job(key, {'ok': False, 'error': str(e)}, 502)
        finally:
            with JOB_LOCK:
                IN_FLIGHT.discard(key)


threading.Thread(target=stage_one, name='clone', daemon=True).start()
threading.Thread(target=stage_two, name='timing', daemon=True).start()


@app.route('/api/read/<mid>/sent/<int:n>', methods=['POST', 'OPTIONS'])
def read_sentence(mid, n):
    mid = str(mid)
    if request.method == 'OPTIONS':
        return ('', 204)
    plan = read_plan(mid)
    if plan is None or n < 0 or n >= plan['count']:
        return jsonify({'ok': False, 'error': 'no such sentence'}), 404
    w = who()
    data = cached_sentence(mid, n, w)
    if data is None:
        ev = enqueue(mid, n, 0)
        if not ev.wait(600):
            return jsonify({'ok': False, 'error': 'the voice took too long'}), 504
        with JOB_LOCK:
            got = JOB_RESULT.pop(job_key(mid, n, w), None)
        if got is None:
            data = cached_sentence(mid, n, w)
            if data is None:
                return jsonify({'ok': False, 'error': 'the sentence was lost'}), 502
        else:
            data, status = got
            if status != 200:
                return jsonify(data), status
    data['made'] = made_ahead(mid, n, w)
    return jsonify(data)


@app.route('/api/read/<mid>/at/<int:i>', methods=['POST', 'OPTIONS'])
def read_at(mid, i):
    """The page is at sentence i: cache from here to the end, drop what was heard."""
    mid = str(mid)
    if request.method == 'OPTIONS':
        return ('', 204)
    plan = read_plan(mid)
    if plan is None or i < 0 or i >= plan['count']:
        return jsonify({'ok': False, 'error': 'no such sentence'}), 404
    CURSOR[mid] = i
    for k in body().get('heard') or []:
        if isinstance(k, int) and 0 <= k < plan['count']:
            forget(mid, k)
    queue_card(mid, i)
    return jsonify({'ok': True, 'at': i, 'made': made_ahead(mid, i, who()), 'count': plan['count']})


# -------------------------------------------------------- the ears, the voice
MIC = os.path.join(DIR, 'mic')


def who():
    """How the sister talks right now: {engine, voice, model, label}. The choice
    is the whole system's (~/.voice/voice.json), so the teachers and every READ
    button follow the same voice."""
    c = V.conf()
    if c.get('engine') == 'clone' and V.AVAILABLE:
        return {'engine': 'clone', 'voice': c['voice'], 'model': c.get('model', ''), 'label': c['voice']}
    return {'engine': 'beatrice', 'voice': 'beatrice', 'model': 'speechify', 'label': 'Beatrice'}


@app.route('/api/voice', methods=['GET', 'POST', 'OPTIONS'])
def api_voice():
    if request.method == 'OPTIONS':
        return ('', 204)
    if request.method == 'POST':
        d = body()
        V.set_conf(d.get('engine'), d.get('voice'))
        if who()['engine'] == 'clone':
            V.warm()
        now = who()
        with JOB_LOCK:                                           # the old voice's unfinished jobs go
            for k in [k for k, ev in JOB_DONE.items() if not ev.is_set() and (k[2], k[3]) != (now['engine'], now['voice'])]:
                JOB_DONE.pop(k, None)
                JOB_RESULT.pop(k, None)
    w = who()
    st = V.status()
    return jsonify(dict(w, ok=True, available=V.AVAILABLE, why=V.why_not(),
                        voices=[v['name'] for v in V.voices()], ears=st.get('ears'), clone=st.get('clone')))


def save_recording(raw, mime):
    """The browser's recording (webm/opus, or whatever it made) to a wav the
    ears can read. Returns (wav path, stamp)."""
    ext = 'webm'
    if 'ogg' in mime:
        ext = 'ogg'
    elif 'mp4' in mime or 'aac' in mime or 'm4a' in mime:
        ext = 'm4a'
    elif 'wav' in mime:
        ext = 'wav'
    os.makedirs(MIC, exist_ok=True)
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    src = os.path.join(MIC, stamp + '.in.' + ext)       # never the same name as the wav it becomes
    with open(src, 'wb') as fh:
        fh.write(raw)
    wav = os.path.join(MIC, stamp + '.wav')
    try:
        V.to_wav(src, wav)
    finally:
        try:
            os.remove(src)
        except OSError:
            pass
    return wav, stamp


@app.route('/api/hear', methods=['POST', 'OPTIONS'])
def api_hear():
    """TALK: the recording comes in the body, Whisper writes it down, and with
    send=1 the words go to the session the way typed words do (a MARKO card,
    a file in the inbox). Nothing is kept but the last few wavs in ~/.tspeak/mic."""
    if request.method == 'OPTIONS':
        return ('', 204)
    raw = request.get_data()
    if not raw or len(raw) < 200:
        return jsonify({'ok': False, 'error': 'nothing recorded'}), 400
    try:
        wav, stamp = save_recording(raw, request.content_type or request.args.get('mime') or '')
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as e:
        return jsonify({'ok': False, 'error': 'ffmpeg could not read the recording: %s' % str(e)[:120]}), 400
    if not V.loud_enough(wav):
        return jsonify({'ok': False, 'error': 'I heard nothing above the room'}), 200
    try:
        text, secs = V.hear(wav)
    except RuntimeError as e:
        log('hear failed: %s' % e)
        return jsonify({'ok': False, 'error': str(e)}), 502
    log('hear %s: %.1fs "%s"' % (stamp, secs, text[:80]))
    tidy_mic()
    if not text:
        return jsonify({'ok': False, 'error': 'I could not make out any words'}), 200
    out = {'ok': True, 'text': text, 'secs': round(secs, 2)}
    if request.args.get('send') in ('1', 'true', 'yes'):
        page = request.args.get('page') or ''
        path = write_inbox(text, page)
        rec = append('marko', text, source='voice', reply_to=page)
        out.update({'sent': True, 'id': rec['id'], 'file': path})
    return jsonify(out)


def tidy_mic(keep=12):
    try:
        files = sorted(f for f in os.listdir(MIC) if f.endswith('.wav'))
        for f in files[:-keep]:
            os.remove(os.path.join(MIC, f))
    except OSError:
        pass


@app.route('/api/voice/clone', methods=['POST', 'OPTIONS'])
def api_voice_clone():
    """CLONE MY VOICE: a recording of a few sentences (six to thirty seconds)
    becomes a new voice, and the sister talks with it from now on."""
    if request.method == 'OPTIONS':
        return ('', 204)
    raw = request.get_data()
    name = ''.join(c if c.isalnum() or c in '_-' else '_' for c in (request.args.get('name') or 'marko').strip()) or 'marko'
    if not raw or len(raw) < 2000:
        return jsonify({'ok': False, 'error': 'nothing recorded'}), 400
    try:
        wav, stamp = save_recording(raw, request.content_type or '')
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as e:
        return jsonify({'ok': False, 'error': 'ffmpeg could not read the recording: %s' % str(e)[:120]}), 400
    if not V.loud_enough(wav):
        return jsonify({'ok': False, 'error': 'I heard nothing above the room'}), 200
    try:
        with SYNTH_LOCK:
            name = V.add_voice(name, wav)
        V.set_conf('clone', name)
    except RuntimeError as e:
        log('clone failed: %s' % e)
        return jsonify({'ok': False, 'error': str(e)}), 502
    log('new voice %s from %s' % (name, stamp))
    V.warm()
    return jsonify(dict(who(), ok=True, voices=[v['name'] for v in V.voices()]))


# --------------------------------------------------------------------- pane
LUA_TILE = r"""
local ratio = %(ratio)s
local want = %(open)s
local scr = hs.screen.mainScreen():frame()
local chat, ai
for _, w in ipairs(hs.window.allWindows()) do
  local t = w:title() or ''
  local a = w:application() and w:application():name() or ''
  if t:find('MANTRA CHAT', 1, true) then chat = w
  elseif (a == 'Google Chrome' or a == 'Brave Browser' or a == 'Safari') and t:find('Claude', 1, true) and not t:find('MANTRA', 1, true) then ai = ai or w end
end
local left = hs.geometry.rect(scr.x, scr.y, math.floor(scr.w * ratio), scr.h)
local right = hs.geometry.rect(scr.x + math.floor(scr.w * ratio), scr.y, scr.w - math.floor(scr.w * ratio), scr.h)
if want then
  if not ai then return 'noai' end
  if ai:isMinimized() then ai:unminimize() end
  ai:setFrame(left, 0)
  if chat then chat:setFrame(right, 0) end
  ai:raise()
  if chat then chat:focus() end
  return 'open'
else
  if ai then ai:minimize() end
  if chat then chat:setFrame(scr, 0); chat:focus() end
  return 'closed'
end
"""


def hs_run(code):
    try:
        out = subprocess.run([HS, '-c', code], capture_output=True, text=True, timeout=8)
        lines = [l for l in (out.stdout or '').splitlines() if l.strip() and not l.startswith('--')]
        return (lines[-1].strip() if lines else ''), (out.stderr or '').strip()
    except (OSError, subprocess.TimeoutExpired) as e:
        return '', str(e)


@app.route('/api/pane', methods=['POST', 'OPTIONS'])
def pane():
    if request.method == 'OPTIONS':
        return ('', 204)
    want = bool(body().get('open'))
    if not os.path.exists(HS):
        if want:
            subprocess.Popen(['open', 'https://claude.ai/'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        STATE['pane'] = want
        return jsonify({'ok': True, 'pane': want, 'detail': 'Hammerspoon not installed, opened claude.ai in a tab'})
    code = LUA_TILE % {'ratio': GOLDEN, 'open': 'true' if want else 'false'}
    out, err = hs_run(code)
    if want and out == 'noai':
        # claude.ai has no window yet: open it as its own app window, then tile again
        subprocess.Popen(['open', '-na', 'Google Chrome', '--args', '--app=https://claude.ai/'],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        import time
        for _ in range(20):
            time.sleep(0.4)
            out, err = hs_run(code)
            if out == 'open':
                break
    STATE['pane'] = want if out in ('open', 'closed') else STATE['pane']
    return jsonify({'ok': out in ('open', 'closed'), 'pane': STATE['pane'], 'detail': out or err})


# --------------------------------------------------------------------- main
def pick_port(host, start, span=20):
    for p in range(start, start + span):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)   # as the server itself binds
        try:
            s.bind((host, p))
            return p
        except OSError:
            continue
        finally:
            s.close()
    return start


def main():
    os.makedirs(CHAT, exist_ok=True)
    os.makedirs(INBOX, exist_ok=True)
    load()
    port = pick_port(HOST, BASE)
    STATE['port'] = port
    with open(PORTFILE, 'w', encoding='utf-8') as fh:
        fh.write('%d\n' % port)
    try:
        import flask.cli
        flask.cli.show_server_banner = lambda *a, **k: None
    except Exception:
        pass
    log('chatd on http://%s:%d with %d messages' % (HOST, port, len(MESSAGES)))
    sys.stdout.write('chatd on http://%s:%d\n' % (HOST, port))
    sys.stdout.flush()
    app.run(host=HOST, port=port, threaded=True, debug=False, use_reloader=False)


if __name__ == '__main__':
    main()

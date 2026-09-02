"""
speechify.py, one Speechify call with word marks, for T.

Payload and response per manifest/apis/speechify.md and
MAHA_TRANSCRIBE_STREAMLIT/ttt/providers/speechify.py:135-151. The mark parser
sp_tokens is lifted from 3sh_i_ma_reader_v3_macos.sh:3369-3428.
Host is api.sws.speechify.com, never api.speechify.ai.
NEVER print a key.
"""

import base64
import json
import socket
import urllib.error
import urllib.request

from ring import classify, cool_seconds

API = 'https://api.sws.speechify.com'
VOICE = 'beatrice_32'
MODEL = 'simba-3.2'          # _32 voices ride simba-3.2; anything else is a hard 400
LIMIT = 2000                 # Speechify truncates and bills past this


def call(key, path, payload=None, timeout=120):
    """(json, err, kind, wait). kind is 'dead' | 'cool' | 'soft' | None."""
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(API + path, data=data,
                                 method='POST' if data else 'GET',
                                 headers={'Authorization': 'Bearer ' + key,
                                          'Content-Type': 'application/json',
                                          'Accept': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode('utf-8', 'replace')), None, None, None
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', 'replace')[:400]
        kind = classify(e.code, body)
        wait = cool_seconds(e.headers) if kind == 'cool' else None
        return None, 'HTTP %d %s' % (e.code, body[:160].replace('\n', ' ')), kind, wait
    except (urllib.error.URLError, socket.timeout, OSError) as e:
        return None, 'network: %s' % str(e)[:160], 'soft', None
    except ValueError as e:
        return None, 'bad json: %s' % str(e)[:160], 'soft', None


def sp_tokens(text, marks):
    """Speechify marks -> [{s, e, t, d}], char offsets into text, seconds."""
    flat = []

    def walk(node):
        if not isinstance(node, dict):
            return
        kids = node.get('chunks') or node.get('nestedChunks') or []
        if kids:
            for c in kids:
                walk(c)
            return
        if 'start_time' in node or 'startTime' in node:
            flat.append(node)

    if isinstance(marks, list):
        for m in marks:
            walk(m)
    else:
        walk(marks)
    if not flat:
        return []
    n = len(text)
    out = []
    for m in flat:
        try:
            s = int(m.get('start', m.get('startOffset', 0)))
            e = int(m.get('end', m.get('endOffset', s)))
            t = float(m.get('start_time', m.get('startTime', 0))) / 1000.0
            d = float(m.get('end_time', m.get('endTime', 0))) / 1000.0
        except (TypeError, ValueError):
            continue
        s = max(0, min(n, s))
        e = max(s, min(n, e))
        if e <= s:
            continue
        out.append({'s': s, 'e': e, 't': round(t, 3), 'd': round(d, 3)})
    if not out:
        return []
    out.sort(key=lambda w: (w['t'], w['s']))
    prev = -1.0
    for w in out:
        if w['t'] <= prev:
            w['t'] = round(prev + 0.01, 3)
        prev = w['t']
    for i, w in enumerate(out):
        nxt = out[i + 1]['t'] if i + 1 < len(out) else w['d']
        if w['d'] <= w['t'] or w['d'] > nxt:
            w['d'] = nxt
        if w['d'] <= w['t']:
            w['d'] = round(w['t'] + 0.05, 3)
        w['d'] = round(w['d'], 3)
    return out


def proportional_tokens(text):
    """Fallback when marks are empty: t and d as fractions 0..1 of the clip,
    divided by word length (ttt/wordtimes.py proportional). The page scales
    them by the real duration once the audio has loaded."""
    import re
    spans = [(m.start(), m.end()) for m in re.finditer(r'\S+', text)]
    if not spans:
        return []
    total = sum(max(1, e - s) for s, e in spans)
    out, t = [], 0.0
    for s, e in spans:
        d = max(1, e - s) / total
        out.append({'s': s, 'e': e, 't': round(t, 4), 'd': round(t + d, 4)})
        t += d
    return out


def synth(ring, text):
    """(mp3_bytes, tokens, billed, proportional). Raises RuntimeError with a
    key free message when every key is gone."""
    text = text[:LIMIT]
    payload = {'input': text, 'voice_id': VOICE, 'audio_format': 'mp3', 'model': MODEL}
    result, err = ring.rotate(lambda k: call(k, '/v1/audio/speech', payload))
    if err:
        raise RuntimeError(err)
    audio = base64.b64decode(result.get('audio_data') or '')
    if not audio:
        raise RuntimeError('Speechify answered without audio_data')
    tokens = sp_tokens(text, result.get('speech_marks') or {})
    prop = False
    if not tokens:
        tokens, prop = proportional_tokens(text), True
    return audio, tokens, int(result.get('billable_characters_count') or 0), prop

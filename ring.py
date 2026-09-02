"""
ring.py, the Speechify key ring for T.

Recombined from MAHA_TRANSCRIBE_STREAMLIT/ttt/keyring.py (rotate, mask,
fingerprint) and ttt/providers/base.py (classify_standard, cool_seconds).
The rules come from manifest/modules/keyring.md and quota-and-fallback.md:

  * a working key is kept call after call (sticky active key)
  * 401, 402, 403 bury a key; 429 rests it for as long as the provider says
  * on dead or cool the SAME request is retried on the next key
  * each key is tried at most once per call
  * a soft failure (5xx, timeout, network) is not the key's fault: one
    retry after two seconds, then the next key, nothing condemned
  * never test a key speculatively; a dead key costs one wasted call, ever
  * keys are never written anywhere; the state file holds fingerprints only
  * NEVER print a key. Masked everywhere, including in errors.
"""

import hashlib
import json
import os
import re
import time

KEYFILE = os.path.expanduser('~/Developer/api/speechify_api.txt')
STATE = os.path.expanduser('~/.tspeak/ring.json')
KEY_RE = re.compile(r'^sk_[A-Za-z0-9_-]{20,}$')
COOL_DEFAULT = 300.0
SOFT_WAIT = 2.0

CLOUDFLARE_BLOCK = '1010'
NO_CREDIT_MARKS = ('zero_credits', 'e0300', 'credit balance', 'insufficient',
                   'quota exceeded', 'out of credits', 'payment required',
                   'billing')
_RESET_RE = re.compile(r'(?:(\d+)h)?(?:(\d+)m)?(?:([\d.]+)s)?(?:(\d+)ms)?$')


def fingerprint(key):
    return hashlib.sha256(key.encode()).hexdigest()[:12]


def mask(key):
    return key[:5] + '…' + key[-4:]


def classify(status, body=''):
    """'dead' | 'cool' | 'soft', the verdict map from base.classify_standard."""
    low = (body or '').lower()
    if status == 403 and CLOUDFLARE_BLOCK in low:
        return 'soft'
    if status in (401, 402, 403):
        return 'dead'
    if status == 429:
        return 'cool'
    if status == 400 and any(m in low for m in NO_CREDIT_MARKS):
        return 'dead'
    return 'soft'


def _reset_seconds(value):
    v = (value or '').strip().lower()
    if not v:
        return None
    try:
        return float(v)
    except ValueError:
        pass
    m = _RESET_RE.match(v)
    if not m or not any(m.groups()):
        return None
    h, mi, sec, ms = m.groups()
    return ((float(h or 0) * 3600) + (float(mi or 0) * 60)
            + float(sec or 0) + (float(ms or 0) / 1000.0))


def cool_seconds(headers=None, default=COOL_DEFAULT, floor=1.0, ceiling=3600.0):
    """How long a throttled key rests: Retry-After, then the reset header, then default."""
    h = {str(k).lower(): str(v) for k, v in dict(headers or {}).items()}
    for name in ('retry-after', 'x-ratelimit-reset-requests', 'x-ratelimit-reset-tokens'):
        got = _reset_seconds(h.get(name, ''))
        if got is not None and got > 0:
            return max(floor, min(got, ceiling))
    return max(floor, min(float(default), ceiling))


def parse_keyfile(path):
    """[{key, fp, label}] in file order. The line above a key is its label."""
    keys, seen, label = [], set(), ''
    with open(path, encoding='utf-8', errors='replace') as fh:
        for raw in fh:
            line = raw.strip()
            if not line:
                continue
            if KEY_RE.match(line):
                if line in seen or label.strip('[] ').upper() == 'DELETED':
                    label = ''
                    continue
                seen.add(line)
                keys.append({'key': line, 'fp': fingerprint(line),
                             'label': label or mask(line)})
                label = ''
            else:
                label = line
    return keys


class Ring:
    def __init__(self, keyfile=KEYFILE, state=STATE, now=time.time, sleep=time.sleep):
        self.keyfile, self.statefile = keyfile, state
        self.now, self.sleep = now, sleep
        self.keys = parse_keyfile(keyfile)
        self.state = {'active': '', 'keys': {}}
        if os.path.isfile(state):
            try:
                with open(state, encoding='utf-8') as fh:
                    self.state = json.load(fh)
            except (OSError, ValueError):
                pass
        self.state.setdefault('active', '')
        self.state.setdefault('keys', {})
        for k in self.keys:
            self._rec(k)

    # -- state -------------------------------------------------------------
    def _rec(self, k):
        r = self.state['keys'].setdefault(k['fp'], {})
        r.setdefault('state', 'new')
        r.setdefault('cool_until', 0)
        r.setdefault('last_error', '')
        r.setdefault('calls', 0)
        r.setdefault('chars', 0)
        r['label'] = k['label']
        return r

    def save(self):
        os.makedirs(os.path.dirname(self.statefile), exist_ok=True)
        tmp = self.statefile + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as fh:
            json.dump(self.state, fh, indent=1)
        os.replace(tmp, self.statefile)

    def _start(self):
        for i, k in enumerate(self.keys):
            if k['fp'] == self.state['active']:
                return i
        return 0

    def pick(self, start):
        """Index of the first usable key at or after start, wrapping, or None."""
        n = len(self.keys)
        for step in range(n):
            i = (start + step) % n
            r = self._rec(self.keys[i])
            if r['state'] == 'dead':
                continue
            if r['state'] == 'cool':
                if self.now() < r['cool_until']:
                    continue
                r['state'], r['cool_until'] = 'ok', 0
            return i
        return None

    def mark_dead(self, i, err):
        r = self._rec(self.keys[i])
        r['state'], r['last_error'], r['calls'] = 'dead', err[:200], r['calls'] + 1

    def mark_cool(self, i, err, wait):
        r = self._rec(self.keys[i])
        r['state'], r['last_error'], r['calls'] = 'cool', err[:200], r['calls'] + 1
        r['cool_until'] = self.now() + float(wait or COOL_DEFAULT)

    def mark_ok(self, i, billed=0):
        r = self._rec(self.keys[i])
        r['state'], r['last_error'], r['calls'] = 'ok', '', r['calls'] + 1
        r['chars'] += int(billed or 0)
        self.state['active'] = self.keys[i]['fp']

    def active(self):
        """(label, masked key) of the key that carried the last success."""
        i = self._start()
        k = self.keys[i]
        return k['label'], mask(k['key'])

    def usable(self):
        return self.pick(self._start()) is not None

    # -- the policy ------------------------------------------------------------
    def rotate(self, attempt):
        """attempt(key) -> (result, err, kind, wait). Returns (result, err)."""
        n = len(self.keys)
        if not n:
            return None, 'No Speechify keys in %s' % self.keyfile
        idx, last, tried = self._start(), '', 0
        while tried < n:
            i = self.pick(idx)
            if i is None:
                break
            tried += 1
            key = self.keys[i]['key']
            result, err, kind, wait = attempt(key)
            if not err:
                billed = result.get('billable_characters_count') if isinstance(result, dict) else 0
                self.mark_ok(i, billed)
                self.save()
                return result, None
            last = err
            if kind == 'soft':
                self.sleep(SOFT_WAIT)
                result, err, kind, wait = attempt(key)
                if not err:
                    billed = result.get('billable_characters_count') if isinstance(result, dict) else 0
                    self.mark_ok(i, billed)
                    self.save()
                    return result, None
                last = err
            if kind == 'dead':
                self.mark_dead(i, err)
            elif kind == 'cool':
                self.mark_cool(i, err, wait)
            else:
                r = self._rec(self.keys[i])
                r['last_error'] = err[:200]
            self.save()
            idx = (i + 1) % n
        self.save()
        return None, 'Every Speechify key failed (%d tried). Last: %s' % (tried, last)

    def report(self):
        rows = []
        for k in self.keys:
            r = self._rec(k)
            rows.append((k['label'], mask(k['key']), r['state'], r['calls'], r['chars']))
        return rows

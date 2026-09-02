"""No spend tests for T. Run: python3 tools/speak/test_speak.py"""
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import ring as R                      # noqa: E402
import lastanswer as L                # noqa: E402
import speechify as SP                # noqa: E402
import page as P                      # noqa: E402

FAKE = ['sk_' + c * 43 for c in 'abc']          # 46 chars each, never real


def temp_ring(now):
    d = tempfile.mkdtemp()
    kf = os.path.join(d, 'keys.txt')
    with open(kf, 'w') as fh:
        fh.write('https://example.invalid/\n\nfirst label\n%s\n\nsecond label\n%s\n\nthird label\n%s\n'
                 % tuple(FAKE))
    clock = {'t': now}
    r = R.Ring(kf, os.path.join(d, 'ring.json'), now=lambda: clock['t'], sleep=lambda s: None)
    return r, clock, d


def test_parse():
    r, _, _ = temp_ring(1000)
    assert [k['label'] for k in r.keys] == ['first label', 'second label', 'third label']
    assert all(len(k['fp']) == 12 for k in r.keys)
    assert R.mask(FAKE[0]) == 'sk_aa…aaaa'


def test_rotate_dead_cool_ok():
    r, clock, d = temp_ring(1000)
    calls = []

    def attempt(key):
        calls.append(key)
        i = FAKE.index(key)
        if i == 0:
            return None, 'HTTP 401 unauthorised', 'dead', None
        if i == 1:
            return None, 'HTTP 429 slow down', 'cool', 5.0
        return {'audio_data': 'AAA', 'billable_characters_count': 12}, None, None, None

    out, err = r.rotate(attempt)
    assert err is None and out['audio_data'] == 'AAA'
    assert calls == FAKE, calls
    st = r.state['keys']
    assert st[r.keys[0]['fp']]['state'] == 'dead'
    assert st[r.keys[1]['fp']]['state'] == 'cool'
    assert st[r.keys[1]['fp']]['cool_until'] == 1005.0
    assert st[r.keys[2]['fp']]['state'] == 'ok' and st[r.keys[2]['fp']]['chars'] == 12
    assert r.state['active'] == r.keys[2]['fp']
    # sticky: the next call starts on the third key and touches nothing else
    calls.clear()
    out, err = r.rotate(attempt)
    assert calls == [FAKE[2]], calls
    # the state file holds fingerprints only
    raw = open(os.path.join(d, 'ring.json')).read()
    assert not any(k in raw for k in FAKE)
    # a reloaded ring keeps the verdicts and the active key
    r2 = R.Ring(r.keyfile, r.statefile, now=lambda: clock['t'], sleep=lambda s: None)
    assert r2.state['active'] == r.keys[2]['fp']
    calls.clear()
    r2.rotate(attempt)
    assert calls == [FAKE[2]]
    # the cool key revives after its rest
    clock['t'] = 1010
    assert r2.pick(1) == 1
    assert r2.state['keys'][r.keys[1]['fp']]['state'] == 'ok'


def test_rotate_soft_and_exhausted():
    r, _, _ = temp_ring(1000)
    calls = []

    def soft(key):
        calls.append(key)
        return None, 'network: down', 'soft', None
    out, err = r.rotate(soft)
    assert out is None and 'Every Speechify key failed' in err
    # each key tried twice (one retry), none condemned
    assert len(calls) == 6 and all(v['state'] != 'dead' for v in r.state['keys'].values())

    def dead(key):
        return None, 'HTTP 402 payment required', 'dead', None
    out, err = r.rotate(dead)
    assert out is None and not r.usable()


def test_classify():
    assert R.classify(401) == 'dead' and R.classify(402) == 'dead' and R.classify(403) == 'dead'
    assert R.classify(403, 'error code: 1010') == 'soft'
    assert R.classify(429) == 'cool'
    assert R.classify(400, 'insufficient credit balance') == 'dead'
    assert R.classify(500) == 'soft'
    assert R.cool_seconds({'Retry-After': '7'}) == 7.0
    assert R.cool_seconds({'x-ratelimit-reset-requests': '44m38.4s'}) == 44 * 60 + 38.4
    assert R.cool_seconds({}) == 300.0


def test_plain_and_chunk():
    md = ('## Title\n\n- **Bold** item with `code`\n- second item\n\n'
          '| a | b |\n|---|---|\n| one | two |\n\n```\nsecret code\n```\n\n'
          'A [link](http://x) here. Another sentence!')
    t = L.plain(md)
    assert 'secret code' not in t and '|' not in t and '**' not in t and '`' not in t
    assert 'Title.' in t and 'Bold item with code.' in t and 'one, two.' in t
    assert 'A link here. Another sentence!' in t
    long = ' '.join('Sentence number %d is here.' % i for i in range(300))
    cs = L.chunk(long, 500)
    assert all(len(c) <= 500 for c in cs)
    assert all(c.endswith('.') for c in cs)
    assert ''.join(cs).replace(' ', '') == long.replace(' ', '')
    assert L.chunk('x' * 1200, 500) == ['x' * 500, 'x' * 500, 'x' * 200]


def rec(kind, content, **kw):
    r = {'type': kind, 'isSidechain': False, 'message': {'content': content}}
    r.update(kw)
    return r


def test_last_answer():
    recs = [rec('user', 'first question'),
            rec('assistant', [{'type': 'thinking', 'thinking': 'private'}]),
            rec('assistant', [{'type': 'text', 'text': 'Old answer.'}]),
            rec('user', 'second question'),
            rec('assistant', [{'type': 'tool_use', 'name': 'Bash'}]),
            rec('user', [{'type': 'tool_result', 'content': 'tool output'}]),
            rec('assistant', [{'type': 'text', 'text': 'Side answer.'}], isSidechain=True),
            rec('assistant', [{'type': 'thinking', 'thinking': 'more private'}]),
            rec('assistant', [{'type': 'text', 'text': 'Part one.'}]),
            rec('assistant', [{'type': 'text', 'text': 'Part two.'}]),
            rec('user', '<task-notification>agent done</task-notification>',
                origin={'kind': 'task-notification'}, promptSource='system'),
            rec('assistant', [{'type': 'text', 'text': 'Part three.'}]),
            {'type': 'summary', 'isMeta': True},
            rec('user', 'T', origin={'kind': 'human'}),
            rec('assistant', [{'type': 'text', 'text': 'Speaking now.'}]),
            rec('assistant', [{'type': 'tool_use', 'name': 'Bash'}])]
    assert L.last_answer(recs) == 'Part one.\n\nPart two.\n\nPart three.'
    assert L.last_answer(recs, skip_current=False) == 'Speaking now.'
    p = L.transcript_path()
    if p:
        real = L.last_answer(L.tail_records(p))
        assert real and 'thinking' not in real.lower()[:0]


def test_tokens_and_page():
    text = 'Hello Marko. This is Beatrice!\n\nSecond paragraph here.'
    marks = {'type': 'sentence', 'chunks': [
        {'type': 'word', 'value': 'Hello', 'start': 0, 'end': 5, 'start_time': 0, 'end_time': 300},
        {'type': 'word', 'value': 'Marko.', 'start': 6, 'end': 12, 'start_time': 300, 'end_time': 700},
        {'type': 'word', 'value': 'This', 'start': 13, 'end': 17, 'start_time': 900, 'end_time': 1000},
        {'type': 'word', 'value': 'is', 'start': 18, 'end': 20, 'start_time': 1000, 'end_time': 1100},
        {'type': 'word', 'value': 'Beatrice!', 'start': 21, 'end': 30, 'start_time': 1100, 'end_time': 1600},
        {'type': 'word', 'value': 'Second', 'start': 32, 'end': 38, 'start_time': 2000, 'end_time': 2300},
        {'type': 'word', 'value': 'paragraph', 'start': 39, 'end': 48, 'start_time': 2300, 'end_time': 2700},
        {'type': 'word', 'value': 'here.', 'start': 49, 'end': 54, 'start_time': 2700, 'end_time': 3000}]}
    toks = SP.sp_tokens(text, marks)
    assert len(toks) == 8 and toks[0] == {'s': 0, 'e': 5, 't': 0.0, 'd': 0.3}
    assert toks[1]['d'] == 0.7          # kept, it does not overlap the next word
    sents = P.sentences_of(text, toks)
    assert [s['text'].strip() for s in sents] == ['Hello Marko.', 'This is Beatrice!', 'Second paragraph here.']
    assert sents[1]['words'][0] == {'s': 0, 'e': 4, 't': 0.9, 'd': 1.0}
    prop = SP.proportional_tokens('one three')
    assert prop[0]['s'] == 0 and abs(prop[-1]['d'] - 1.0) < 1e-6
    html = P.build([{'audio': b'\xff\xfb\x90', 'text': text, 'words': toks, 'prop': False}], 'T', 'now', len(text))
    assert 'data:audio/mpeg;base64,' in html and 'Beatrice!' in html and '<script>' in html
    assert 'sk_' not in html
    json.loads(html.split('const CH = ', 1)[1].split(';\nconst WORD_LEAD', 1)[0].replace('<\\/', '</'))


if __name__ == '__main__':
    names = [n for n in dir() if n.startswith('test_')]
    for n in sorted(names):
        globals()[n]()
        print('ok', n)
    print('all %d tests passed' % len(names))

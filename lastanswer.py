"""
lastanswer.py, the text for T.

Reads Claude's last answer out of this session's transcript, turns markdown
into speech text, and packs it into chunks Speechify will accept whole.
The transcript is ~/.claude/projects/<project>/<CLAUDE_CODE_SESSION_ID>.jsonl,
one JSON record per line. Only visible assistant text is taken: never a
thinking block, never a tool call, never a subagent's sidechain.
"""

import glob
import json
import os
import re

PROJECT_DIR = os.path.expanduser('~/.claude/projects/-Users-markobosko-Developer-brain-break')
TAIL_BYTES = 2_000_000
LIMIT = 1800          # under Speechify's 2000, so a chunk is never truncated


# ----------------------------------------------------------------- transcript
def transcript_path():
    sid = os.environ.get('CLAUDE_CODE_SESSION_ID', '')
    if sid:
        p = os.path.join(PROJECT_DIR, sid + '.jsonl')
        if os.path.isfile(p):
            return p
    files = glob.glob(os.path.join(PROJECT_DIR, '*.jsonl'))
    return max(files, key=os.path.getmtime) if files else None


def tail_records(path, nbytes=TAIL_BYTES):
    size = os.path.getsize(path)
    with open(path, 'rb') as fh:
        if size > nbytes:
            fh.seek(size - nbytes)
            fh.readline()                      # drop the cut line
        data = fh.read()
    recs = []
    for line in data.decode('utf-8', 'replace').splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            recs.append(json.loads(line))
        except ValueError:
            continue
    return recs


def is_real_user(rec):
    """A message Marko typed, not a tool result and not a meta record."""
    if rec.get('type') != 'user' or rec.get('isMeta') or rec.get('isSidechain'):
        return False
    origin = rec.get('origin')
    if isinstance(origin, dict) and origin.get('kind') != 'human':
        return False                       # a task notification or other system prompt
    if rec.get('promptSource') == 'system':
        return False
    c = (rec.get('message') or {}).get('content')
    if isinstance(c, str):
        return bool(c.strip())
    if isinstance(c, list):
        return any(isinstance(b, dict) and b.get('type') == 'text' for b in c)
    return False


def assistant_text(rec):
    if rec.get('type') != 'assistant' or rec.get('isSidechain'):
        return ''
    c = (rec.get('message') or {}).get('content')
    if not isinstance(c, list):
        return ''
    parts = [b.get('text', '') for b in c
             if isinstance(b, dict) and b.get('type') == 'text' and b.get('text', '').strip()]
    return '\n\n'.join(parts)


def last_answer(recs, skip_current=True):
    """Assistant text of the turn before the newest user message.

    With skip_current the newest real user record (the T itself) is passed
    over first, so whatever Claude says while running the tool is not read
    aloud; text is then collected back to the previous real user record."""
    i = len(recs) - 1
    if skip_current:
        while i >= 0 and not is_real_user(recs[i]):
            i -= 1
        i -= 1
    parts = []
    while i >= 0:
        r = recs[i]
        if is_real_user(r):
            break
        t = assistant_text(r)
        if t:
            parts.append(t)
        i -= 1
    return '\n\n'.join(reversed(parts))


def last_answer_text(skip_current=True):
    p = transcript_path()
    if not p:
        return ''
    return last_answer(tail_records(p), skip_current)


# ---------------------------------------------------------------------- plain
_TABLE_RULE = re.compile(r'^\|?\s*:?-{2,}')


def plain(md):
    """Markdown to speech text. Code is dropped, tables become a sentence a
    row, markers and links go, sentence punctuation stays."""
    s = md.replace('\r', '')
    s = re.sub(r'```.*?```', ' ', s, flags=re.S)
    s = re.sub(r'<[^>\n]{1,80}>', ' ', s)
    out = []
    for line in s.split('\n'):
        l = line.strip()
        if not l:
            out.append('')
            continue
        if _TABLE_RULE.match(l):
            continue
        if l.startswith('|'):
            cells = [c.strip() for c in l.strip('|').split('|')]
            l = ', '.join(c for c in cells if c)
        l = re.sub(r'^#{1,6}\s*', '', l)
        l = re.sub(r'^(?:[-*+]|\d+[.)])\s+', '', l)
        l = re.sub(r'!?\[([^\]]*)\]\([^)]*\)', r'\1', l)
        l = re.sub(r'`([^`]*)`', r'\1', l)
        l = re.sub(r'(\*\*|__)(.*?)\1', r'\2', l)
        l = re.sub(r'(?<!\w)[*_](.+?)[*_](?!\w)', r'\1', l)
        l = l.replace('**', '').replace('*', '')
        l = re.sub(r'\s+', ' ', l).strip()
        if l and l[-1] not in '.!?:;':
            l += '.'
        out.append(l)
    text = '\n'.join(out)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


# ---------------------------------------------------------------------- chunk
_PIECE = re.compile(r'[^.!?]*[.!?]+\s*|[^.!?]+$', re.S)


def sentences(text):
    return [p for p in _PIECE.findall(text) if p.strip()]


def _split_long(piece, limit):
    out = []
    while len(piece) > limit:
        cut = piece.rfind(' ', 0, limit)
        if cut < limit // 2:
            cut = limit
        out.append(piece[:cut])
        piece = piece[cut:].lstrip()
    if piece:
        out.append(piece)
    return out


def chunk(text, limit=LIMIT):
    """Pack whole sentences into chunks under limit. Never cuts a sentence
    unless the sentence alone is longer than the limit."""
    chunks, cur = [], ''
    for piece in sentences(text):
        for p in ([piece] if len(piece) <= limit else _split_long(piece, limit)):
            if cur and len(cur) + len(p) > limit:
                chunks.append(cur.strip())
                cur = ''
            cur += p
    if cur.strip():
        chunks.append(cur.strip())
    return chunks

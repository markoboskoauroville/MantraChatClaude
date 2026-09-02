#!/usr/bin/env python3
"""
tspeak.py, the T command.

Speaks Claude's last answer with Speechify's Beatrice and opens a page that
highlights the sentence and the word as it is read. Output lives outside
every repository in ~/.tspeak/. Prints ONE line on success and never a key.

  python3 tools/speak/tspeak.py              the last answer of this session
  python3 tools/speak/tspeak.py --text "…"   anything
  python3 tools/speak/tspeak.py --no-open    build only
  python3 tools/speak/tspeak.py --speed 1.5  playback speed, remembered
"""

import argparse
import datetime
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from ring import Ring                              # noqa: E402
from speechify import synth                        # noqa: E402
from lastanswer import last_answer_text, plain, chunk   # noqa: E402
from page import build                             # noqa: E402

PYTHON = sys.executable
PORTFILE = os.path.expanduser('~/.tspeak/port.txt')
INBOX_LOG = os.path.expanduser('~/.tspeak/inbox.log')


def inbox_url():
    """The local reply inbox, started if it is not answering. '' when it cannot."""
    import time
    import urllib.request

    def alive():
        try:
            with open(PORTFILE, encoding='utf-8') as fh:
                port = int(fh.read().strip())
            url = 'http://127.0.0.1:%d' % port
            with urllib.request.urlopen(url + '/health', timeout=1) as r:
                if r.status == 200:
                    return url
        except (OSError, ValueError):
            pass
        return ''
    url = alive()
    if url:
        return url
    try:
        log = open(INBOX_LOG, 'a')
        subprocess.Popen([PYTHON, os.path.join(HERE, 'chatd.py')], stdout=log, stderr=log,
                         stdin=subprocess.DEVNULL, start_new_session=True)
    except OSError:
        return ''
    for _ in range(30):
        time.sleep(0.1)
        url = alive()
        if url:
            return url
    return ''

OUT = os.path.expanduser('~/.tspeak/out')
LAST = os.path.expanduser('~/.tspeak/last.html')
SPEEDFILE = os.path.expanduser('~/.tspeak/speed.txt')


def remembered_speed():
    try:
        with open(SPEEDFILE, encoding='utf-8') as fh:
            return max(0.5, min(3.0, float(fh.read().strip())))
    except (OSError, ValueError):
        return 1.0


def fail(msg, ring=None, code=2):
    sys.stderr.write(msg.rstrip() + '\n')
    if ring is not None:
        for label, masked, state, calls, chars in ring.report():
            sys.stderr.write('  %-24s %s  %-5s calls=%d chars=%d\n' % (label[:24], masked, state, calls, chars))
    sys.exit(code)


def main():
    ap = argparse.ArgumentParser(description='Speak the last answer with Beatrice.')
    ap.add_argument('--text', help='speak this instead of the last answer')
    ap.add_argument('--text-file', help='speak this file instead of the last answer')
    ap.add_argument('--raw', action='store_true', help='do not strip markdown')
    ap.add_argument('--no-open', action='store_true', help='build the page, do not open it')
    ap.add_argument('--speed', type=float, help='playback speed, 0.5 to 3, remembered for next time')
    ap.add_argument('--paused', action='store_true', help='open the page but wait for PLAY')
    ap.add_argument('--include-current', action='store_true',
                    help='read the newest assistant text, not the turn before the last user message')
    args = ap.parse_args()

    if args.text is not None:
        text = args.text
    elif args.text_file:
        with open(args.text_file, encoding='utf-8') as fh:
            text = fh.read()
    else:
        text = last_answer_text(skip_current=not args.include_current)
    if not text.strip():
        fail('Nothing to speak: no answer text found.')
    speech = text if args.raw else plain(text)
    chunks = chunk(speech)
    if not chunks:
        fail('Nothing to speak after stripping markdown.')

    ring = Ring()
    if not ring.keys:
        fail('No Speechify keys found in %s' % ring.keyfile)
    if not ring.usable():
        fail('Every Speechify key is dead or cooling.', ring)

    clips, billed, seconds = [], 0, 0.0
    for c in chunks:
        try:
            audio, tokens, b, prop = synth(ring, c)
        except RuntimeError as e:
            fail('Speechify failed: %s' % e, ring)
        clips.append({'audio': audio, 'text': c, 'words': tokens, 'prop': prop})
        billed += b
        if tokens and not prop:
            seconds += tokens[-1]['d']

    speed = max(0.5, min(3.0, args.speed)) if args.speed else remembered_speed()
    now = datetime.datetime.now()
    stamp = now.strftime('%Y%m%d-%H%M%S')
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, stamp + '.html')
    inbox = inbox_url()
    page = build(clips, 'Beatrice ' + now.strftime('%-d.%-m.%Y %H:%M'),
                 now.strftime('%-d.%-m.%Y %H:%M'), sum(len(c) for c in chunks), speed, not args.paused,
                 inbox, stamp)
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(page)
    with open(os.path.join(OUT, stamp + '.txt'), 'w', encoding='utf-8') as fh:
        fh.write(speech)
    shutil.copyfile(path, LAST)
    with open(SPEEDFILE, 'w', encoding='utf-8') as fh:
        fh.write('%g\n' % speed)
    if not args.no_open:
        subprocess.Popen(['open', path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    label, masked = ring.active()
    print('%s chunks=%d chars=%d audio=%.1fs speed=%g inbox=%s key=%s %s'
          % (path, len(chunks), billed, seconds, speed, inbox or 'none', label, masked))


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
chat_hook.py, the Claude Code side of MANTRA CHAT.

Wired into ~/.claude/settings.json for every project:

  SessionStart      chat_hook.py start    if chatd is up: opens the page and prints the
                                          greeting Claude must relay. Never starts her:
                                          Marko starts her from the star menu (5.9.2026)
  (by hand)         chat_hook.py launch   starts chatd; install.sh uses it once
  UserPromptSubmit  chat_hook.py prompt   mirrors what Marko typed in the terminal
  Stop              chat_hook.py stop     mirrors Claude's answer from the transcript

Reads the hook JSON on stdin, never blocks for long, never prints a key.
"""

import json
import os
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

PYTHON = '/Users/markobosko/.pyenv/shims/python3'
PORTFILE = os.path.expanduser('~/.tspeak/port.txt')
LOG = os.path.expanduser('~/.tspeak/chatd.log')


def stdin_json():
    try:
        raw = sys.stdin.read()
        return json.loads(raw) if raw.strip() else {}
    except (ValueError, OSError):
        return {}


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


def server_url():
    url = alive()
    if url:
        return url
    try:
        log = open(LOG, 'a')
        subprocess.Popen([PYTHON, os.path.join(HERE, 'chatd.py')], stdout=log, stderr=log,
                         stdin=subprocess.DEVNULL, start_new_session=True)
    except OSError:
        return ''
    for _ in range(50):
        time.sleep(0.1)
        url = alive()
        if url:
            return url
    return ''


def post(url, path, data, timeout=3):
    if not url:
        return None
    req = urllib.request.Request(url + path, data=json.dumps(data).encode('utf-8'),
                                 headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode('utf-8', 'replace'))
    except (OSError, ValueError):
        return None


def main():
    event = sys.argv[1] if len(sys.argv) > 1 else 'start'
    d = stdin_json()
    session = d.get('session_id') or os.environ.get('CLAUDE_CODE_SESSION_ID', '')
    cwd = d.get('cwd') or os.getcwd()
    project = os.path.basename(cwd.rstrip('/')) or cwd
    meta = {'session': session, 'cwd': cwd, 'project': project}

    if event == 'launch':
        # THE ONE EXPLICIT WAY TO START HER FROM HERE: install.sh, or Marko asking.
        url = server_url()
        print('MANTRA CHAT is %s at %s.' % ('running' if url else 'NOT running', url or 'no port'))
        return

    if event == 'start':
        # SHE IS NOT STARTED BY THE HOOK ANY MORE. Marko, 5.9.2026: "don't run
        # sister up automatically until I ask you. I can run her through the
        # David star menu." So the hook only looks: if she is up, it mirrors
        # the session and prints the greeting; if not, it says so in one line
        # and the session goes on without her.
        url = alive()
        if not url:
            print('MANTRA CHAT is not running. Nothing was started: Marko starts her from the '
                  'star menu (Sister) when he wants her. Do not start her yourself. Skip the '
                  'chat greeting; the inbox Monitor may still be armed on ~/.tspeak/inbox.')
            return
        bridge = os.environ.get('CLAUDE_CODE_BRIDGE_SESSION_ID', '')
        post(url, '/api/session', dict(meta, event='start', bridge=bridge))
        opened = post(url, '/api/open', {}) or {}
        remote = ('https://claude.ai/code/' + bridge) if bridge else 'not connected yet'
        print('MANTRA CHAT is %s at %s (page %s). Remote view: %s.' % (
            'running' if url else 'NOT running', url or 'no port',
            'opened now' if opened.get('opened') else 'already open', remote))
        print('At the start of this session, before anything else, tell Marko in a few short lines: '
              '"Remote control: starting." "Chat interface: starting at %s." Then the rules: '
              'R reads the last answer aloud (R 1.5 sets the speed); W pushes the watch folder; '
              'what he types in MANTRA CHAT and sends reaches this session; READ under any answer '
              'plays it with Beatrice and lights the words; the side pane icon opens claude.ai beside the page.' % (url or 'the chat page'))
        print('Then arm a persistent Monitor on ~/.tspeak/inbox (one line per new json file with '
              'page, time and text) so his answers from the page arrive here as events, and treat '
              'each event as his message.')
        return

    url = alive()
    if event == 'prompt':
        text = str(d.get('prompt') or '').strip()
        if text and not text.startswith('<') and len(text) > 1 or text.upper() in ('R', 'W', 'T'):
            post(url, '/api/message', dict(meta, role='marko', text=text, source='terminal'))
        return

    if event == 'stop':
        transcript = d.get('transcript_path') or ''
        if not transcript or not os.path.isfile(transcript):
            return
        try:
            from lastanswer import tail_records, last_answer
            text = last_answer(tail_records(transcript), skip_current=False).strip()
        except Exception:
            text = ''
        if text:
            post(url, '/api/message', dict(meta, role='claude', text=text, source='transcript'))
        return


if __name__ == '__main__':
    try:
        main()
    except Exception as e:      # a hook must never break the session
        sys.stderr.write('chat_hook: %s\n' % e)
    sys.exit(0)

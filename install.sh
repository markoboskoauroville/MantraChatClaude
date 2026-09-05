#!/bin/bash
# install.sh, bring MantraChatClaude (the sister app) onto this Mac.
# Idempotent: run it again after a pull and nothing is duplicated.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
PY="${PYTHON:-$HOME/.pyenv/shims/python3}"
[ -x "$PY" ] || PY="$(command -v python3)"
echo "MantraChatClaude install from $HERE"
echo "python: $PY"

# 1. python and flask
"$PY" - <<'EOF'
import sys
v = sys.version_info
assert v >= (3, 9), 'python 3.9 or newer is needed, found %d.%d' % (v.major, v.minor)
try:
    import flask
    print('flask', flask.__version__)
except ImportError:
    raise SystemExit('flask is missing: %s -m pip install flask' % sys.executable)
EOF

# 2. chrome
[ -d "/Applications/Google Chrome.app" ] && echo "chrome: found" || echo "chrome: NOT found, the page will open in the default browser"

# 3. the key file
KEYS="$HOME/Developer/api/speechify_api.txt"
if [ -s "$KEYS" ]; then echo "keys: $KEYS"; else echo "keys: $KEYS is missing. READ will not speak until it exists (label line above each sk_ key)."; fi

# 4. hooks and remote control in ~/.claude/settings.json, merged
mkdir -p "$HOME/.claude" "$HOME/.tspeak"
"$PY" - "$HERE" "$PY" <<'EOF'
import json, os, sys
here, py = sys.argv[1], sys.argv[2]
p = os.path.expanduser('~/.claude/settings.json')
s = {}
if os.path.isfile(p):
    with open(p, encoding='utf-8') as fh:
        s = json.load(fh)
hooks = s.setdefault('hooks', {})
def put(ev, arg, timeout, extra):
    entry = {'type': 'command', 'command': '%s %s/chat_hook.py %s' % (py, here, arg), 'timeout': timeout}
    entry.update(extra)
    lst = hooks.setdefault(ev, [])
    for grp in lst:
        for h in grp.get('hooks', []):
            if 'chat_hook.py' in h.get('command', ''):
                h.clear(); h.update(entry); return
    lst.append({'hooks': [entry]})
put('SessionStart', 'start', 20, {'statusMessage': 'Starting MANTRA CHAT'})
put('UserPromptSubmit', 'prompt', 5, {'async': True})
put('Stop', 'stop', 10, {'async': True})
s['remoteControlAtStartup'] = True
tmp = p + '.tmp'
with open(tmp, 'w', encoding='utf-8') as fh:
    json.dump(s, fh, indent=2)
os.replace(tmp, p)
print('hooks: written to', p)
EOF

# 5. the companion note in ~/.claude/CLAUDE.md, once
NOTE="$HOME/.claude/CLAUDE.md"
if ! grep -q 'MantraChatClaude' "$NOTE" 2>/dev/null; then
cat >> "$NOTE" <<'EOF'

# MantraChatClaude, the sister app

MantraChatClaude at ~/Developer/MantraChatClaude is the companion app that follows Claude Code
into every project on this machine: a local page, MANTRA CHAT, at http://127.0.0.1:8825 that
mirrors the session, speaks every card with Beatrice, and sends what Marko types back to the
session. Read ~/Developer/MantraChatClaude/CLAUDE.md for how to behave with her: the session
start greeting, the R and W letters, the inbox Monitor, the status line rule, never a key in
the open. GitHub is the hub: every change to her is committed and pushed to
https://github.com/markoboskoauroville/MantraChatClaude.
EOF
echo "note: added to $NOTE"
else
echo "note: already in $NOTE"
fi

# 6. start her once
echo '{}' | "$PY" "$HERE/chat_hook.py" launch | head -1
echo "done. Open a new Claude Code session anywhere; she comes along."

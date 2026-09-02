# TAKEOVER

How to bring MANTRA CHAT back on a fresh Mac, or hand it to someone else. Written 2.9.2026.
Marko's rule: if a step changed something on the machine and it is not in here, the step is
not finished.

## 1. What has to exist on the machine

* macOS with Google Chrome installed. The page opens only in Chrome, as an app window.
* Python 3.10 with Flask. On Marko's Mac it is pyenv: `/Users/markobosko/.pyenv/shims/python3`
  with `flask` and `requests` installed. Everything else is the standard library.
* `ffmpeg` and `node` are not needed by the chat. `node --check` was only used to test the page script.
* Hammerspoon with `hs.ipc` (the `hs` command at `/opt/homebrew/bin/hs`) for the side pane
  that tiles claude.ai beside the page. Without it the pane opens claude.ai in a tab instead.
* Claude Code, logged in, with Remote Control available.

## 2. The clone

```
git clone https://github.com/markoboskoauroville/MantraChatClaude ~/Developer/MantraChatClaude
```

On Marko's Mac `~/Developer/brain_break/tools/speak` is a symbolic link to this folder, so
older notes that name that path still work.

## 3. The key file

`~/Developer/api/speechify_api.txt`. One label line, then the key on the next line, blank
lines between. Keys start with `sk_` and are 46 characters. The file is never committed
anywhere; `brain_break/.gitignore` covers `*api*.txt`. The ring's state lives in
`~/.tspeak/ring.json` and holds fingerprints only.

## 4. The hooks

In `~/.claude/settings.json`, merged with whatever is there:

```json
{
  "remoteControlAtStartup": true,
  "hooks": {
    "SessionStart": [{"hooks": [{"type": "command", "timeout": 20, "statusMessage": "Starting MANTRA CHAT",
      "command": "/Users/markobosko/.pyenv/shims/python3 /Users/markobosko/Developer/MantraChatClaude/chat_hook.py start"}]}],
    "UserPromptSubmit": [{"hooks": [{"type": "command", "timeout": 5, "async": true,
      "command": "/Users/markobosko/.pyenv/shims/python3 /Users/markobosko/Developer/MantraChatClaude/chat_hook.py prompt"}]}],
    "Stop": [{"hooks": [{"type": "command", "timeout": 10, "async": true,
      "command": "/Users/markobosko/.pyenv/shims/python3 /Users/markobosko/Developer/MantraChatClaude/chat_hook.py stop"}]}]
  }
}
```

Check with `jq -e '.hooks.SessionStart[].hooks[].command' ~/.claude/settings.json`. Hooks
added while a session runs are picked up on the next session or after opening `/hooks` once.

## 5. First start

```
echo '{}' | /Users/markobosko/.pyenv/shims/python3 ~/Developer/MantraChatClaude/chat_hook.py start
```

This starts the server, writes `~/.tspeak/port.txt`, opens the page in Chrome, and prints
the greeting instructions. Then `curl http://127.0.0.1:8825/health` should answer with ok.

## 6. What lives where

```
~/.tspeak/port.txt              the port the server took (8825 unless busy)
~/.tspeak/ring.json             key ring state, fingerprints only
~/.tspeak/speed.txt             last reading speed of the R command
~/.tspeak/chat/messages.jsonl   every card, one JSON per line
~/.tspeak/chat/audio/<id>/      plan.json and one <n>.json per sentence, cached audio
~/.tspeak/inbox/<stamp>.json    what Marko sent from a page; the session watches this folder
~/.tspeak/out/<stamp>.html      pages made by the R command
~/.tspeak/chatd.log             the server log
```

Nothing generated ever lands in a repository.

## 7. The session side

At the start of every session Claude says, in a few short lines: "Remote control: starting."
"Chat interface: starting at http://127.0.0.1:8825." Then the rules: R reads the last answer
aloud (R 1.5 sets the speed), W pushes the watch folder, what is typed in MANTRA CHAT
reaches the session, READ under any card plays it with Beatrice, the pane icon opens
claude.ai beside. Then it arms a persistent Monitor on `~/.tspeak/inbox`:

```
cd ~/.tspeak/inbox; seen=$(ls *.json 2>/dev/null | sort); while true; do cur=$(ls *.json 2>/dev/null | sort);
new=$(comm -13 <(echo "$seen") <(echo "$cur")); for f in $new; do python3 -c "import json,sys;d=json.load(open(sys.argv[1]));
print('MARKO REPLIED on page %s at %s: %s'%(d.get('page'),d.get('time'),d.get('text','')))" "$f"; done; seen=$cur; sleep 1; done
```

The memory files that carry this live in
`~/.claude/projects/-Users-markobosko-Developer-brain-break/memory/`: `mantra-chat-interface.md`,
`r-trigger-read.md`, `status-line-not-overlays.md`.

## 8. Restarting the server

```
pkill -f 'MantraChatClaude/chatd.py'; sleep 2
echo '{}' | /Users/markobosko/.pyenv/shims/python3 ~/Developer/MantraChatClaude/chat_hook.py start
```

Wait for the old process to be gone before starting, or the new one binds the next port up.
The page in Chrome reconnects on its own; close the old app window if two are open.

## 9. Known limits

* claude.ai sends `X-Frame-Options: SAMEORIGIN`, so it can never sit inside the page. The
  side pane opens it as its own window beside.
* Chrome may block autoplay on the first READ after a fresh load; play on the pill is one tap.
* The Stop hook mirrors the whole visible text of a turn, interim lines included.
* Speechify's API is text to speech only; there is no transcription endpoint. Transcription
  stays with AssemblyAI, per the manifest.

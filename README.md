# MantraChatClaude

A local chat interface for Claude Code, built for one person who reads by ear.

It is a Flask page on the Mac, MANTRA CHAT, that follows every Claude Code session in every
project. What Marko types and what Claude answers appear on the page as cards. Every card
has READ: the text is spoken by Speechify's Beatrice, one sentence at a time, in a floating
Beatrice window where the sentence being read is pushed to the top edge and the spoken word
is lit red. A floating control pill carries previous and next sentence, play and pause,
speed, font size, and X to end. What is typed on the page reaches the Claude Code session.
A side pane opens claude.ai beside the page, tiled at the golden section.

Nothing here is invented. It was recombined on 2.9.2026 from code that already existed in
Marko's other projects: the reader script's offline player, the Streamlit project's key ring
and Speechify provider, the sample player's port handling.

## The files

| file | what |
|---|---|
| `chatd.py` | the Flask server, 127.0.0.1 only, base port 8825, port in `~/.tspeak/port.txt` |
| `chat_page.py` | the page: side pane, cards, composer, the Beatrice window, the pill |
| `chat_hook.py` | the Claude Code hooks: SessionStart, UserPromptSubmit, Stop |
| `ring.py` | the Speechify key ring: sticky working key, dead on 401 402 403, cool on 429, fingerprints only on disk |
| `speechify.py` | one call to `api.sws.speechify.com` with word marks, voice `beatrice_32`, model `simba-3.2` |
| `lastanswer.py` | reads Claude's last answer from the session transcript, strips markdown, splits sentences |
| `page.py` | the standalone reading page used by the R command |
| `tspeak.py` | the R command: read the last answer into a self contained page, local and remote |
| `test_speak.py` | tests without spend: `python3 test_speak.py` |

## How it runs

Three hooks in `~/.claude/settings.json` run `chat_hook.py` for every project:

* **SessionStart** starts `chatd.py` if `/health` does not answer, opens the page in Chrome
  as an app window if nobody has it open, posts a session line, and prints into Claude's
  context the greeting to say and the inbox watch to arm.
* **UserPromptSubmit** mirrors what was typed in the terminal.
* **Stop** mirrors Claude's finished answer out of the transcript.

The composer posts to `/api/send`, which writes `~/.tspeak/inbox/<stamp>.json`; the session
keeps a Monitor on that folder and treats each file as a message from Marko.

READ is progressive. `POST /api/read/<id>/plan` returns the sentences. `POST
/api/read/<id>/sent/<n>` makes exactly one sentence, one Speechify call, one cache file under
`~/.tspeak/chat/audio/<id>/`. The page plays sentence 0 as soon as it arrives and asks for
n+1 the moment n starts playing. STOP aborts what is in flight and asks for nothing more.
`POST /api/read/draft/plan` does the same for text not yet sent, keyed by a hash of the text.

## Rules that shaped it

* Never print a key. The key file is `~/Developer/api/speechify_api.txt`, a label above each
  key; the ring stores sha256 fingerprints, never keys.
* Status goes in a small line at the bottom right of the window, never in the middle of the
  screen, never a fright.
* The sentence being read sits at the top edge, instantly. A smooth scroll is a delay by
  another name.
* Colour changes nothing about layout, weight does. The word is lit by colour only.
* Chrome only, as an app window: no address bar, no menus. The top bar hides itself.
* No dashes as punctuation in anything written for Marko.

See `TAKEOVER.md` to rebuild it on a fresh Mac and `LESSONS.md` for what was learned.

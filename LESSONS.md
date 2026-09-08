# LESSONS

What one day of building this taught, 2.9.2026. Each one cost something; none should be paid twice.

1. **A global constant named `top` kills the whole page.** `const top = …` at script level
   collides with the window's own `top`, the browser throws at load, and nothing runs, while
   `node --check` says the file is fine. Name it `topbar`. In general, test in the browser,
   not only in node.

2. **Restarting a Flask server needs the socket to be free.** Werkzeug binds with
   SO_REUSEADDR; a port probe that does not is fooled by TIME_WAIT connections and steps to
   the next port. Probe with the same flag, and wait until the old process is really gone.

3. **Headless Chrome hangs on a page that keeps a live connection.** A server sent events
   stream never finishes, so `--virtual-time-budget` waits forever. Give the page a
   `?static=1` switch that skips the live feed for renders.

4. **`timeout` is not on macOS.** The GNU command is missing; a pipeline that relies on it
   silently does nothing. Use the page's own switches instead of external timeouts.

5. **Do not pipe a page into Python and also feed Python its script on stdin.** Fetch the
   page inside Python with urllib.

6. **Task notifications arrive as user records in the transcript.** They carry
   `origin.kind: task-notification` and `promptSource: system`; a typed message has
   `origin.kind: human`. Filter on that or the tool reads its own progress lines aloud.

7. **Thinking blocks and tool calls sit beside text blocks in the same record.** Take only
   `type: text` and skip `isSidechain` records, or subagents speak.

8. **Speechify truncates and bills past 2000 characters**, and every call returns exact
   word marks for free. So chunk under the cap and never re-time a Speechify clip.

9. **A `%d` in a log line is a crash when the id becomes a string.** The draft reader turned
   message ids into hashes; the log line in the sentence route then raised after the cache
   file was written, so the first request failed and the second was served from cache. Use
   `%s` for ids.

10. **Read the last line of Hammerspoon's output.** The first `hs -c` after a Hammerspoon
    restart prints "Loading extension" lines before the verdict.

11. **claude.ai refuses to be framed.** `X-Frame-Options: SAMEORIGIN`. Do not try; open it as
    a Chrome app window beside the page and tile with Hammerspoon.

12. **Status in the middle of the screen is a fright.** Waiting and errors go to one small
    line at the bottom right of the window, in the same quiet type whether good or bad.

13. **Make one sentence at a time.** A whole answer synthesised first means a long wait and a
    wasted spend on STOP. One sentence per call, the next made while the current plays, one
    cache file per sentence, and STOP aborts what is in flight.

14. **Patching a page already made beats synthesising again.** Speed, paused start and the
    reply box were all added to pages whose audio was inside the HTML. Never spend twice for
    a change of presentation.

15. **One letter is a command.** W pushes, R reads (R 1.5 at speed). Act on the letter, say
    nothing first, put the summary on the clipboard when done.

16. **Enter sends.** Marko, 3.9.2026: "when I press enter, it sends the message to you command
    enter. It's too much work. Only enter works." Shift+Enter and Option+Enter make a new
    line. A chord for the thing he does most is a tax on every answer.

17. **The band between the log and the entry box is his to set.** A grip above the composer
    drags the height; the textarea fills the band; the height is kept in localStorage per
    browser and read inside a try. Nothing appears or disappears, the ratio changes.

## 8.9.2026, the ears and the second voice

- The sister talks and listens through MANTRA_VOICE (voice.py imports ears, clone, timing) and
  starts their socket servers herself; she never needs voiced.py to be up, and she never builds a
  second model server. The choice of voice is the system's (~/.voice/voice.json), so the chip on
  her page changes how every app on the Mac talks.
- The microphone is the browser's (MediaRecorder, webm/opus), sent whole to /api/hear; ffmpeg
  makes it a 16 kHz wav there. The mouth closes when the ear opens: a reading is paused before the
  microphone starts, or the ears send the sister's own words back as Marko's.
- The space bar talks. Inside the entry box it still types, unless the box is empty. The reader's
  play and pause moved to P; arrows, Escape, plus and minus stayed.
- A cloned voice's clips are cached under a name that carries the voice and the model
  (<n>.<voice>-<model>.json), so Beatrice's and a clone's never mix and switching re-reads nothing.
- A wav uploaded to /api/hear must not be written under the name ffmpeg will write to: the input
  is <stamp>.in.<ext>, the output <stamp>.wav.

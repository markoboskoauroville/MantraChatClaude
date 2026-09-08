"""
voice.py, the sister's ears and her second voice. Marko, 8.9.2026: "upgrade the
sister app: voice cloning and Whisper for voice recognition. Build it in the
sister app. I need a record button which I can also toggle with the space bar
to talk with you, and then I want to listen with my locally cloned voice what
you are saying."

Nothing here is new machinery: the ears and the cloned voice live in
MANTRA_VOICE (~/Developer/MANTRA_VOICE: ears.py, clone.py, timing.py), the
local Whisper on the GPU behind ~/.voice/ears.sock and the zero-shot cloning
models (mlx-audio) behind ~/.voice/clone.sock. This module is the sister's
way in: it imports them, starts their servers when they are down, and turns
their answers into the sister's shapes (the clip with words the reader page
already plays). When MANTRA_VOICE is not on the machine, the sister still
works with Beatrice alone and TALK says so in the status line.

    conf()                    {engine: clone|beatrice, voice, model}, from ~/.voice/voice.json
    set_conf(engine, voice)   choose how the sister talks (the whole system follows)
    voices()                  the cloned voices there are
    warm()                    start the ears and the voice server in the background
    to_wav(src, dst)          ffmpeg: whatever the browser recorded -> mono 16 kHz wav
    loud_enough(wav)          was anything said above the room
    hear(wav)                 the words, through the ears (Whisper)
    clone_clip(text, voice)   (mp3 bytes, tokens [{s,e,t,d}]) in a cloned voice, cached
    add_voice(name, wav)      a new voice from a recording made on the page
"""

import audioop
import os
import subprocess
import sys
import threading
import time
import wave

HOME = os.path.expanduser('~')
VOICE_SYS = os.path.join(HOME, 'Developer', 'MANTRA_VOICE')
FFMPEG = '/opt/homebrew/bin/ffmpeg' if os.path.exists('/opt/homebrew/bin/ffmpeg') else 'ffmpeg'

_ears = _clone = _timing = None
_err = ''
if os.path.isdir(VOICE_SYS):
    sys.path.insert(0, VOICE_SYS)
    try:
        import ears as _ears          # noqa: E402
        import clone as _clone        # noqa: E402
        import timing as _timing      # noqa: E402
    except Exception as e:            # noqa: BLE001
        _ears = _clone = _timing = None
        _err = 'MANTRA_VOICE could not be imported: %s' % str(e)[:120]
else:
    _err = 'MANTRA_VOICE is not at ' + VOICE_SYS

AVAILABLE = _clone is not None
_WARM = {'started': False}
_LOCK = threading.Lock()


def why_not():
    return _err


def conf():
    if not AVAILABLE:
        return {'engine': 'beatrice', 'voice': 'beatrice', 'model': ''}
    return _clone.conf()


def set_conf(engine=None, voice=None):
    if not AVAILABLE:
        return conf()
    c = _clone.conf()
    if engine in ('clone', 'beatrice'):
        c['engine'] = engine
    if voice and os.path.isfile(os.path.join(_clone.voice_dir(voice), 'ref.wav')):
        c['voice'] = voice
    _clone.save_conf(c)
    return c


def voices():
    if not AVAILABLE:
        return []
    return _clone.voices()


def status():
    """What the page shows: ears up or not, voice server up or not."""
    if not AVAILABLE:
        return {'ears': False, 'clone': False, 'why': _err}
    c = _clone.alive()
    return {'ears': _ears.alive(), 'clone': bool(c), 'clone_model': (c or {}).get('model')}


def warm():
    """The first TALK should not wait for Whisper to load, nor the first READ
    for the voice model: start both servers now, quietly, once."""
    if not AVAILABLE or _WARM['started']:
        return
    _WARM['started'] = True

    def go():
        try:
            _ears.up()
        except Exception:                                   # noqa: BLE001
            pass
        try:
            if _clone.conf().get('engine') == 'clone':
                _clone.up()
        except Exception:                                   # noqa: BLE001
            pass
    threading.Thread(target=go, daemon=True).start()


def to_wav(src, dst, rate=16000):
    subprocess.run([FFMPEG, '-hide_banner', '-loglevel', 'error', '-y', '-i', src,
                    '-ac', '1', '-ar', str(rate), '-c:a', 'pcm_s16le', dst], check=True, timeout=120)
    return dst


def loud_enough(path, floor=120):
    try:
        with wave.open(path) as w:
            frames = w.readframes(w.getnframes())
            return audioop.rms(frames, w.getsampwidth()) >= floor
    except (OSError, wave.Error, audioop.error):
        return True


def hear(wav):
    """The words in a wav, through the ears server (started if it is down;
    the first start loads the model, seconds). Raises RuntimeError."""
    if not AVAILABLE:
        raise RuntimeError(_err)
    t0 = time.time()
    with _LOCK:
        if not _ears.up():
            raise RuntimeError('the ears did not start (see %s)' % _ears.LOG)
        r = _ears.ask(os.path.abspath(wav), timeout=180)
    if r.get('error'):
        raise RuntimeError(r['error'])
    return ' '.join((r.get('text') or '').split()), time.time() - t0


def clone_clip(text, voice=None):
    """(mp3 bytes, tokens) for one sentence in a cloned voice. The mp3 comes
    from clone.py's cache (made once per voice and model); the words are timed
    by the ears listening to the clip again (timing.py). Raises RuntimeError."""
    if not AVAILABLE:
        raise RuntimeError(_err)
    text = ' '.join(text.split())
    try:
        path, _secs, _cached = _clone.voice_file(text, voice)
    except SystemExit as e:                                 # clone.py exits on its errors
        raise RuntimeError(str(e).replace('ERROR ', '', 1))
    except subprocess.CalledProcessError as e:
        raise RuntimeError('ffmpeg failed: %s' % e)
    if not path:
        raise RuntimeError('nothing to say')
    tj = path[:-4] + '.json'
    tokens = None
    if os.path.isfile(tj):
        try:
            import json
            with open(tj) as fh:
                tokens = json.load(fh).get('tokens')
        except (OSError, ValueError):
            tokens = None
    if not tokens:
        try:
            tokens = _timing.timings(path, text)
        except Exception as e:                              # noqa: BLE001
            tokens = None
            _log('timing failed, proportional words: %s' % str(e)[:100])
        if tokens:
            try:
                import json
                with open(tj, 'w') as fh:
                    json.dump({'text': text, 'tokens': tokens}, fh)
            except OSError:
                pass
    with open(path, 'rb') as fh:
        audio = fh.read()
    return audio, tokens or []


def add_voice(name, wav, text=None):
    """A voice from a recording the page made: clone.py cuts it (up to 30 s,
    mono 24 kHz) and the ears write its words. Returns the voice name."""
    if not AVAILABLE:
        raise RuntimeError(_err)
    length = 12.0
    try:
        with wave.open(wav) as w:
            length = max(3.0, min(30.0, w.getnframes() / float(w.getframerate())))
    except (OSError, wave.Error):
        pass
    try:
        return _clone.add_voice(name, wav, 0.0, length, text)
    except SystemExit as e:
        raise RuntimeError(str(e).replace('ERROR ', '', 1))


def _log(msg):
    try:
        with open(os.path.join(HOME, '.tspeak', 'chatd.log'), 'a', encoding='utf-8') as fh:
            fh.write('%s voice: %s\n' % (time.strftime('%H:%M:%S'), msg))
    except OSError:
        pass

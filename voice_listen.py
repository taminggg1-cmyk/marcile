"""Always-listening voice input for Marcille. Runs under rvc_env (Python 3.10,
GPU). Vosk (cheap, CPU) spots the wake word "Marcille"; once woken, the command
is recorded and transcribed by faster-whisper (accurate, GPU).

Protocol (clean stdout; library noise goes to stderr):
  READY            -> models loaded, mic open
  WAKE             -> heard the wake word
  CMD: <text>      -> transcribed command after waking
  ERR <msg>        -> fatal problem (e.g. no microphone)
marcille.py reads these lines and drives her reply.
"""
import sys
import os
import json
import time
import difflib

_REAL = sys.stdout
sys.stdout = sys.stderr            # keep library prints off the protocol pipe


def emit(msg):
    _REAL.write(msg + "\n")
    _REAL.flush()


HERE = os.path.dirname(os.path.abspath(__file__))
VOSK_DIR = os.path.join(HERE, "vosk_model", "vosk-model-small-en-us-0.15")
SR = 16000
# The small English model has no word "marcille". These IN-VOCABULARY soundalikes
# are what it actually emits when you say "Marcille". We restrict the wake
# recognizer's GRAMMAR to just these (+ [unk]) so the model is strongly biased to
# report one of them instead of guessing some unrelated word -> far more reliable.
WAKE_WORDS = ["marseille", "marcel", "martial", "marcy", "marcella",
              "marshall", "marcie", "marshal"]
WAKE_GRAMMAR = json.dumps(WAKE_WORDS + ["[unk]"])
# Fuzzy fallback (used if grammar mode is unavailable): catch close mishearings.
_FUZZY_TARGETS = ["marcille", "marseille", "marcel", "martial", "marcy",
                  "marcella", "marshall"]

# Seed whisper with the words it's likely to hear -> far fewer mishears on names
# and app/command vocabulary (faster-whisper biases toward the initial_prompt).
COMMAND_HINT = ("Marcille. Commands: open Chrome, Spotify, Notepad, Discord, YouTube. "
                "Play music, pause, resume, skip, next, previous, volume up, mute. "
                "Set a timer for five minutes. What time is it. What's the weather. "
                "Remind me. Take a note. Lock the screen. Take a screenshot.")


def _enable_cuda_dlls():
    """CTranslate2 loads cuBLAS/cuDNN via plain LoadLibrary, which searches PATH (not
    os.add_dll_directory dirs). The CUDA 12 runtime ships as pip packages under the
    venv's site-packages\\nvidia\\*\\bin — put those on PATH so GPU whisper can run."""
    sp = os.path.join(sys.prefix, "Lib", "site-packages")
    bins = [os.path.join(sp, "nvidia", "cublas", "bin"),
            os.path.join(sp, "nvidia", "cudnn", "bin"),
            os.path.join(sp, "nvidia", "cuda_nvrtc", "bin")]
    found = [b for b in bins if os.path.isdir(b)]
    if found:
        os.environ["PATH"] = os.pathsep.join(found) + os.pathsep + os.environ.get("PATH", "")
        for d in found:
            try:
                os.add_dll_directory(d)
            except Exception:
                pass
    return bool(found)


def _load_whisper(WhisperModel):
    """Load the best STT model that actually works on THIS machine. Prefers GPU
    distil-large-v3 (far more accurate than small, handles imperfect mic audio),
    falls back to a smaller-VRAM GPU mode, then CPU. Each attempt is verified with a
    probe transcription so a missing-DLL / out-of-VRAM error is caught here (clean
    fallback) instead of crashing mid-command."""
    import numpy as np
    cuda = _enable_cuda_dlls()
    attempts = []
    if cuda:
        attempts += [("distil-large-v3", "cuda", "float16"),
                     ("distil-large-v3", "cuda", "int8_float16")]
    attempts.append(("small", "cpu", "int8"))
    probe = np.zeros(16000, dtype=np.float32)
    for name, dev, ct in attempts:
        try:
            kw = {"cpu_threads": 4} if dev == "cpu" else {}
            m = WhisperModel(name, device=dev, compute_type=ct, **kw)
            list(m.transcribe(probe, language="en", beam_size=1)[0])   # force lib/VRAM load
            sys.stderr.write("whisper: loaded %s on %s (%s)\n" % (name, dev, ct))
            sys.stderr.flush()
            return m
        except Exception as e:
            sys.stderr.write("whisper: %s/%s/%s failed: %r\n" % (name, dev, ct, e))
            sys.stderr.flush()
    return None


def has_wake(text):
    t = (text or "").lower().strip()
    if not t:
        return False
    for tok in t.split():
        if tok in WAKE_WORDS:
            return True
        for w in _FUZZY_TARGETS:
            if difflib.SequenceMatcher(None, tok, w).ratio() >= 0.80:
                return True
    return False


def main():
    import numpy as np
    import sounddevice as sd
    from vosk import Model, KaldiRecognizer
    from faster_whisper import WhisperModel

    try:
        vosk_model = Model(VOSK_DIR)
        try:
            rec = KaldiRecognizer(vosk_model, SR, WAKE_GRAMMAR)  # biased to wake word
        except Exception:
            rec = KaldiRecognizer(vosk_model, SR)                # plain fallback
    except Exception as e:
        emit("ERR vosk: " + repr(e))
        return
    # Best STT that runs here: GPU distil-large-v3 if possible, else CPU small.
    # (distil-large-v3 downloads ~1.5GB once on first run.)
    whisper = _load_whisper(WhisperModel)
    if whisper is None:
        emit("ERR whisper: no working backend (GPU or CPU)")
        return
    try:
        stream = sd.RawInputStream(samplerate=SR, blocksize=4000,
                                   dtype="int16", channels=1)
        stream.start()
    except Exception as e:
        emit("ERR mic: " + repr(e))
        return

    emit("READY")

    def record_command(max_sec=6.0, silence_sec=1.2, sil_thresh=420):
        frames, started, silent, t0 = [], False, 0.0, time.time()
        # full-vocab recognizer JUST for live partial captions (whisper still does
        # the accurate final transcription below) -> user sees words as they speak
        live = KaldiRecognizer(vosk_model, SR)
        last_partial = ""
        while time.time() - t0 < max_sec:
            data, _ = stream.read(2000)
            raw = bytes(data)
            buf = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
            frames.append(buf)
            try:
                if live.AcceptWaveform(raw):
                    txt = json.loads(live.Result()).get("text", "")
                else:
                    txt = json.loads(live.PartialResult()).get("partial", "")
                if txt and txt != last_partial:
                    last_partial = txt
                    emit("PARTIAL: " + txt)
            except Exception:
                pass
            rms = float(np.sqrt(np.mean(buf ** 2))) if buf.size else 0.0
            if rms > sil_thresh:
                started, silent = True, 0.0
            elif started:
                silent += buf.size / SR
                if silent > silence_sec:
                    break
        if not started:
            return None
        # MUST be contiguous float32 -- float64 can crash CTranslate2 natively
        audio = np.ascontiguousarray(np.concatenate(frames) / 32768.0, dtype=np.float32)
        # beam_size 5 + vocab hint + VAD filter = much better accuracy on short commands
        segs, _ = whisper.transcribe(
            audio, language="en", beam_size=5, temperature=0.0,
            initial_prompt=COMMAND_HINT, condition_on_previous_text=False,
            vad_filter=True)
        text = " ".join(s.text for s in segs).strip()
        return text or None

    import traceback
    last_wake = 0.0
    while True:
        try:
            data, _ = stream.read(2000)        # ~0.125s blocks: snappier wake polling
            chunk = bytes(data)
            woke = False
            if rec.AcceptWaveform(chunk):
                if has_wake(json.loads(rec.Result()).get("text", "")):
                    woke = True
            else:
                if has_wake(json.loads(rec.PartialResult()).get("partial", "")):
                    rec.Reset()
                    woke = True
            # debounce: ignore re-triggers within 2s of the last wake
            if woke and time.time() - last_wake < 2.0:
                woke = False
                rec.Reset()
            if woke:
                last_wake = time.time()
                emit("WAKE")
                cmd = None
                try:
                    cmd = record_command()
                except Exception:
                    sys.stderr.write("record_command error:\n" + traceback.format_exc())
                    sys.stderr.flush()
                rec.Reset()
                last_wake = time.time()        # restart debounce after the command
                if cmd:
                    emit("CMD: " + cmd)
                else:
                    emit("NOCMD")              # heard the wake word but no clear command
        except Exception:
            # never let one bad mic read / transcribe kill the ears
            sys.stderr.write("loop error:\n" + traceback.format_exc())
            sys.stderr.flush()
            time.sleep(0.1)


if __name__ == "__main__":
    main()

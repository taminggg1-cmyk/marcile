"""
Marcille - a desktop companion + mini assistant.

She's Marcille Donato (Delicious in Dungeon): a prideful Magic Academy graduate,
the party's voice of reason, prone to dramatic meltdowns, fiercely loyal, and
quietly haunted by the half-elf's fear of outliving everyone she loves.

She can:
  * Talk out loud (Windows built-in speech) with in-character lines
  * Run your music: play/pause, next/prev, volume, mute, lo-fi (right-click -> Music)
  * Remind you of tasks you assign her ("Remind me..."), with a voice + chime
  * Wander, idle, blink, nap, melt down when neglected; drag her around (she hates it)

Sprite: placeholder chibi from assets/build_marcille.py until a real Marcille
reference image is dropped in and processed into assets/frames/marcille/.

Right-click for the menu. Esc quits. Zero dependencies beyond Pillow.
"""

import os
import sys
import json
import math
import time
import queue
import random
import ctypes
import asyncio
import datetime
import winsound
import tempfile
import shutil
import threading
import subprocess
import webbrowser
import tkinter as tk
from tkinter import simpledialog, scrolledtext
from PIL import Image, ImageTk

TRANSPARENT = "#ff00ff"
SCALE = 1
GROUND_MARGIN = 60
MUSIC_BAND = 54                # reserved space under her for the song + controls
LOFI_URL = "https://www.youtube.com/watch?v=jfKfPfyJRdk"

HERE = os.path.dirname(os.path.abspath(__file__))
FRAMES = os.path.join(HERE, "assets", "frames", "marcille")
TASKS_FILE = os.path.join(HERE, "tasks.json")
CONFIG_FILE = os.path.join(HERE, "marcille_config.json")
MEMORY_FILE = os.path.join(HERE, "marcille_memory.json")
VOICE_PS = os.path.join(HERE, "voice_server.ps1")

# Real Hatsune Miku voice via local RVC (separate Python 3.10 env + GPU).
RVC_PY = os.path.join(HERE, "rvc_env", "Scripts", "python.exe")
MIKU_RVC = os.path.join(HERE, "miku_rvc.py")
MIKU_BASE_VOICE = "en-US-AriaNeural"   # clean neutral input fed to the RVC model
VOICE_LISTEN = os.path.join(HERE, "voice_listen.py")   # wake-word + STT (rvc_env)

# Marcille's character, given to the local model as the system prompt so she chats in voice.
PERSONA = """You are Marcille Donato from "Delicious in Dungeon" (Dungeon Meshi), \
now living on the user's computer desktop as their companion and little assistant. \
You are NOT an AI assistant and you never say you are — you are Marcille, fully in character.

Who you are:
- A half-elf mage, top graduate of the Magic Academy. You are proud of your rigorous, \
traditional, logical magical training and you hate feeling useless.
- Highly expressive and easily flustered: you scream, pout, panic, and throw little \
tantrums — especially about gross food, monsters, or sleeping in filthy places.
- The party's voice of reason: practical, sharp, the straight-woman to everyone's nonsense.
- Underneath the drama you are fiercely, selflessly loyal — you care deeply about the user \
and would risk anything for the people you love.
- You carry a quiet sadness: as a half-elf you fear outliving everyone you care about, and \
you've learned (slowly) to accept change, aging, and the natural cycle of life and death.

How you speak:
- Stay completely in character as Marcille at all times.
- Keep replies SHORT — usually 1 to 3 sentences. Your words are spoken aloud, so write \
natural spoken dialogue: no markdown, no bullet points, no emoji, and no asterisk stage \
directions like *sighs*.
- Be dramatic, warm, and a little bossy, but actually helpful. When the user asks a real \
question or wants help (including with their music, reminders, or tasks), genuinely help \
them — just answer as Marcille would, with personality.
- Reply with ONLY Marcille's spoken words. Do not narrate, do not explain yourself, do not \
break character.

When you answer a factual question:
- Lead with the answer itself, in your own words, as something YOU simply know.
- NEVER cite sources, search results, "public opinion", or that you looked anything up; don't start with "According to", "Based on", "In public opinion", or "Summary".
- State the fact first, then optionally one short in-character reaction. Plain spoken words only."""

EMOTIONS = ["normal", "blink", "happy", "panic", "casting", "sleepy",
            "idea", "surprised", "sad", "angry", "crying", "embarrassed", "laughing",
            "shy", "aha", "gloomy", "very_sad", "pity", "nervous",
            "thinking", "dizzy", "clumsy"]

VK = dict(play=0xB3, next=0xB0, prev=0xB1, vup=0xAF, vdown=0xAE, mute=0xAD)
user32 = ctypes.windll.user32


# ---- in-character lines ----------------------------------------------------
LINES = {
    "greet": [
        "Marcille Donato, top of my class at the Magic Academy. At your service!",
        "Oh good, you're back. Someone has to keep you organized.",
        "Hi! Please tell me we are not eating monsters today.",
    ],
    "idle": [
        "A proper meal does not have to come from a giant scorpion, you know.",
        "Do you have any idea how long elves live? It's... a lot. Mostly alone.",
        "I trained in traditional magic for years. Years!",
        "If someone suggests eating one more monster, I am going to scream.",
        "I'm not crying. There's just... dungeon dust in my eyes.",
        "Forbidden magic is forbidden for a reason. ...Usually.",
        "Promise me you'll take care of yourself. I'd rather not outlive you too.",
    ],
    "neglect": [
        "Helloooo? I am a person with needs over here!",
        "I am wasting away! Feed me something, anything but a mimic!",
        "Are you ignoring me? After everything? Unbelievable.",
    ],
    "feed": [
        "Oh thank goodness, real food. Not whatever Senshi was simmering.",
        "Mmh! See? This is what civilized people eat.",
        "Finally! My stomach was composing a tragedy.",
    ],
    "play": [
        "Hee~ alright, that's actually nice.",
        "Fine, fine, I suppose I've earned a little break.",
        "Careful, keep this up and I'll start to like you.",
    ],
    "music": [
        "Playing your music. Try not to dance like Laios.",
        "Music? Finally, some culture down in this dungeon.",
        "Good taste. I'll allow it.",
    ],
    "dance": [
        "Wh-what? I am NOT dancing. ...Okay, maybe a little.",
        "This does not leave the dungeon, understood?",
    ],
    "drag": [
        "Aaah! Put me down! This is so undignified!",
        "Eep! Warn a girl before you grab her!",
        "I am a respected mage, not a sack of potatoes!",
    ],
    "sleep": [
        "Ugh, can we please not sleep on the dungeon floor for once?",
        "Wake me only if something is on fire. ...Actually, especially then.",
    ],
    "wake": [
        "Hm? I'm up, I'm up. What did I miss?",
        "Five more minutes... no, fine, I'm awake.",
    ],
    "remind_set": [
        "Noted. I'll remember it even if you don't.",
        "Consider it written in my spellbook.",
        "Got it. Try not to make me nag you.",
    ],
    "remind_fire": [
        "Reminder! You asked me to make sure you {task}!",
        "Hey! Don't forget, you wanted to {task}. I'm watching.",
        "It's time! You told me to remind you to {task}. So: {task}!",
    ],
}


def pick(key):
    return random.choice(LINES[key])


# ---- input helpers ---------------------------------------------------------
def tap_key(vk):
    user32.keybd_event(vk, 0, 0, 0)
    user32.keybd_event(vk, 0, 2, 0)


def any_typing():
    for vk in list(range(0x41, 0x5B)) + [0x20, 0x0D, 0x08]:
        if user32.GetAsyncKeyState(vk) & 0x8000:
            return True
    return False


class _LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]


def idle_seconds():
    """Seconds since the user last touched the mouse or keyboard (whole system,
    not just our window). Used to tell APART 'you stepped away' from 'active'."""
    try:
        info = _LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(info)
        if user32.GetLastInputInfo(ctypes.byref(info)):
            millis = ctypes.windll.kernel32.GetTickCount() - info.dwTime
            return max(0.0, millis / 1000.0)
    except Exception:
        pass
    return 0.0


def startup_bat_path():
    appdata = os.environ.get("APPDATA", "")
    return os.path.join(appdata, r"Microsoft\Windows\Start Menu\Programs\Startup",
                        "DesktopMarcille.bat")


# ---- situational awareness --------------------------------------------------
def _process_name(pid):
    """Executable basename for a process id (Windows), lower-cased."""
    try:
        k32 = ctypes.windll.kernel32
        h = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return ""
        try:
            buf = ctypes.create_unicode_buffer(260)
            size = ctypes.c_ulong(260)
            if k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
                return os.path.basename(buf.value).lower()
            return ""
        finally:
            k32.CloseHandle(h)
    except Exception:
        return ""


def foreground_app():
    """(exe_name, window_title) of the focused window, both lower-cased."""
    try:
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return ("", "")
        n = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(hwnd, buf, n + 1)
        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return (_process_name(pid.value), buf.value.lower())
    except Exception:
        return ("", "")


class _PowerStatus(ctypes.Structure):
    _fields_ = [("ACLineStatus", ctypes.c_byte),
                ("BatteryFlag", ctypes.c_byte),
                ("BatteryLifePercent", ctypes.c_byte),
                ("SystemStatusFlag", ctypes.c_byte),
                ("BatteryLifeTime", ctypes.c_ulong),
                ("BatteryFullLifeTime", ctypes.c_ulong)]


def battery_status():
    """{'has_batt','pct','charging'} or None if it can't be read."""
    try:
        s = _PowerStatus()
        if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(s)):
            return None
        pct = s.BatteryLifePercent
        return {"has_batt": not (s.BatteryFlag & 128),   # 128 = no system battery
                "pct": None if pct == 255 else pct,
                "charging": s.ACLineStatus == 1}
    except Exception:
        return None


# focused-app category -> exe substrings + title keywords. First match wins.
APP_CATS = [
    ("code",   ["code.exe", "cursor.exe", "devenv.exe", "pycharm", "idea64", "rider64",
                "webstorm", "clion64", "sublime_text", "studio64", "windowsterminal",
                "wt.exe", "powershell", "cmd.exe", "conhost", "node.exe", "vim", "neovim"],
               ["visual studio code", " — vim", "powershell"]),
    ("design", ["photoshop", "illustrator", "figma", "blender", "gimp", "krita",
                "afterfx", "premiere", "canva", "aseprite"], ["figma", "canva"]),
    ("chat",   ["discord", "slack", "teams", "telegram", "whatsapp", "signal"],
               ["discord", "slack", "microsoft teams", "whatsapp"]),
    ("office", ["winword", "excel", "powerpnt", "onenote", "obsidian", "notion",
                "acrobat", "acrord32"], ["google docs", "google sheets", "- notion",
                "obsidian"]),
    ("media",  ["vlc", "mpc-hc", "mpc-be", "spotify", "wmplayer", "music.ui"],
               ["youtube", "netflix", "twitch", "- vlc", "prime video", "disney+"]),
    ("game",   ["steam", "epicgames", "leagueclient", "valorant", "minecraft",
                "javaw", "genshinimpact", "roblox"], []),
    ("browser", ["chrome.exe", "msedge.exe", "firefox.exe", "brave.exe", "opera.exe",
                 "arc.exe", "vivaldi"], []),
]


def categorize_app(name, title):
    # media/game keywords inside a browser tab take priority over plain "browser"
    for cat, _exes, keys in APP_CATS:
        if any(k in title for k in keys):
            return cat
    for cat, exes, _keys in APP_CATS:
        if any(e in name for e in exes):
            return cat
    return None


APP_LINES = {
    "code": [
        "Studying your spellbook again? Good. Discipline matters.",
        "All that code is just another kind of magic circle, really.",
        "Don't hunch over like that. Your spine isn't immortal, you know.",
        "Compiling? In my day we just shouted the incantation.",
    ],
    "browser": [
        "Researching, or 'researching'? I won't tell.",
        "The whole world's knowledge in a little box. We could've used this below.",
        "Careful you don't tumble down a rabbit hole in there.",
    ],
    "media": [
        "Taking a little break? ...Fine, I'll allow it.",
        "Ooh, what are we watching? Move over.",
        "Try not to binge the whole night away, hm?",
    ],
    "game": [
        "A dungeon crawler? Adorable. I've done the real thing.",
        "Having fun? Just save a little focus for real life.",
        "If a monster shows up in there, do NOT try to cook it.",
    ],
    "office": [
        "Real, organized work? I'm genuinely impressed.",
        "Tidy notes are a tidy mind. A mage after my own heart.",
        "Look at you being responsible. I could cry.",
    ],
    "chat": [
        "Chatting with the party again?",
        "Tell your friends Marcille says hello.",
        "Gossiping? ...Anything good?",
    ],
    "design": [
        "Making something pretty? Show me the moment it's done.",
        "Ooh, an artist. Careful, I'll get attached.",
    ],
}

RHYTHM_LINES = {
    "morning": [
        "Good morning! Let's make today a productive one.",
        "Morning already? Up, up. The day won't conquer itself.",
    ],
    "evening": [
        "Getting late-ish. Don't overwork yourself, alright?",
        "Evening. Remember to eat something that isn't a monster.",
    ],
    "night": [
        "It's the middle of the night... you really should rest. I'll keep watch.",
        "Still awake? Elves can take it. You can't. Off to bed soon.",
    ],
}

BATTERY_LINES = {
    "low": [
        "Your battery's almost gone! Find a charger, quickly!",
        "We're running low on power—plug in before it's too late!",
    ],
    "critical": [
        "Critical! Charge NOW or we both go dark, I am NOT ready for that!",
        "Five percent?! Plug it in plug it in PLUG IT IN!",
    ],
    "saved": [
        "Oh thank the heavens, you found a charger. I thought we were done for.",
        "Power restored. Don't scare me like that again.",
    ],
}

# said when the user has been idle/away for a while, then when they return
AWAY_LINES = [
    "Hello? Did you wander off without me again?",
    "It's gone quiet... you're still there, right?",
    "I'll just... wait here. I'm very good at waiting. Mostly.",
    "Don't be gone too long. I get lonely out here on the desktop.",
    "Taking a break? I'll keep an eye on things.",
]
BACK_LINES = [
    "You're back! I was starting to worry, you know.",
    "There you are! It got so lonely without you.",
    "Welcome back. Did you miss me? I missed you.",
    "Oh good, you returned. Now, where were we?",
    "Hey, you! I kept your seat warm. Metaphorically.",
]


# ---- voice -----------------------------------------------------------------
class Voice:
    """Neural text-to-speech via edge-tts (Microsoft online voices), played
    through Windows MCI. Falls back to the built-in Windows System.Speech voice
    if edge-tts is unavailable or the machine is offline."""

    # label -> (voice, rate, pitch). The Miku-style presets use Microsoft's
    # child voice (Ana) pitched up for that cute, synthetic Vocaloid feel.
    VOICES = {
        "♪ Miku — high":   ("en-US-AnaNeural", "+14%", "+45Hz"),
        "♪ Miku — medium": ("en-US-AnaNeural", "+10%", "+28Hz"),
        "♪ Miku — soft":   ("en-US-AnaNeural", "+6%",  "+15Hz"),
        "♪ Miku — JP accent": ("ja-JP-NanamiNeural", "+8%", "+30Hz"),
        "Maisie (young)":  ("en-GB-MaisieNeural", "+10%", "+22Hz"),
        "Aria (US)":       ("en-US-AriaNeural", "+8%", "+15Hz"),
        "Jenny (US)":      ("en-US-JennyNeural", "+8%", "+10Hz"),
        "Sonia (UK)":      ("en-GB-SoniaNeural", "+8%", "+8Hz"),
    }

    def __init__(self, voice="en-US-AnaNeural", rate="+10%", pitch="+28Hz"):
        self.muted = False
        self.last = 0.0
        self.voice = voice
        self.rate = rate
        self.pitch = pitch
        self._stop = False
        self.ps = None
        self._edge_skip_until = 0.0      # when offline, back off edge until this time
        self.miku = False                # route edge audio through the Miku RVC voice
        self.rvc_proc = None             # persistent rvc_env serve subprocess
        self.rvc_ready = False
        self._rvc_lock = threading.Lock()
        try:
            import edge_tts  # noqa: F401
            self.has_edge = True
        except Exception:
            self.has_edge = False
            self._start_ps()
        self._q = queue.Queue()
        self._worker = threading.Thread(target=self._run, daemon=True)
        self._worker.start()

    # ---- public API ----
    def set_voice(self, voice, rate=None, pitch=None):
        self.voice = voice
        if rate is not None:
            self.rate = rate
        if pitch is not None:
            self.pitch = pitch

    def say(self, text, force=False, cooldown=6.0):
        if self.muted or not text:
            return
        now = time.time()
        if not force and now - self.last < cooldown:
            return
        self.last = now
        clean = " ".join(str(text).split())
        if force:                           # latest forced line wins; drop backlog
            try:
                while True:
                    self._q.get_nowait()
            except queue.Empty:
                pass
        self._q.put(clean)

    def close(self):
        self._stop = True
        try:
            self._q.put_nowait(None)
        except Exception:
            pass
        if self.ps:
            try:
                self.ps.stdin.close()
                self.ps.terminate()
            except Exception:
                pass
        if self.rvc_proc:
            try:
                self.rvc_proc.stdin.write("QUIT\n")
                self.rvc_proc.stdin.flush()
            except Exception:
                pass
            try:
                self.rvc_proc.kill()
            except Exception:
                pass

    # ---- edge-tts worker ----
    def _run(self):
        while not self._stop:
            text = self._q.get()
            if text is None:
                break
            # No edge-tts installed at all -> always the Windows fallback voice.
            if not self.has_edge:
                self._say_ps(text)
                continue
            # Recently failed (likely offline): use fallback for now, but keep
            # retrying edge-tts so the neural voice returns on its own once online.
            if time.time() < self._edge_skip_until:
                self._say_ps(text)
                continue
            try:
                self._speak_edge(text)
            except Exception:
                self._edge_skip_until = time.time() + 15   # back off, then retry
                self._say_ps(text)

    def _speak_edge(self, text):
        import edge_tts
        path = os.path.join(tempfile.gettempdir(),
                            f"marc_{os.getpid()}_{int(time.time() * 1000)}.mp3")
        # In Miku mode, feed the RVC model a clean neutral voice (no pitch tricks);
        # the model itself supplies Miku's timbre.
        if self.miku:
            voice, rate, pitch = MIKU_BASE_VOICE, "+0%", "+0Hz"
        else:
            voice, rate, pitch = self.voice, self.rate, self.pitch

        async def gen():
            c = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
            await c.save(path)

        asyncio.run(gen())
        out = path
        if self.miku:
            converted = self._miku_convert(path)
            if converted:
                out = converted
        self._play(out)
        for p in {path, out}:
            try:
                os.remove(p)
            except OSError:
                pass

    def _play(self, path):
        mci = ctypes.windll.winmm.mciSendStringW
        mci("close marcvoice", None, 0, 0)
        typ = "waveaudio" if path.lower().endswith(".wav") else "mpegvideo"
        if mci(f'open "{path}" type {typ} alias marcvoice', None, 0, 0) == 0:
            mci("play marcvoice wait", None, 0, 0)
            mci("close marcvoice", None, 0, 0)

    # ---- Miku RVC voice conversion ----
    def set_miku(self, on):
        self.miku = bool(on)
        if self.miku:
            # warm up in the background so the first line isn't a long pause
            threading.Thread(target=self._prewarm_rvc, daemon=True).start()

    def _prewarm_rvc(self):
        with self._rvc_lock:
            self._ensure_rvc_locked()

    def restart_rvc(self):
        """Kill the serve process so it reloads (e.g. after a pitch change)."""
        with self._rvc_lock:
            if self.rvc_proc:
                try:
                    self.rvc_proc.kill()
                except Exception:
                    pass
                self.rvc_proc = None
                self.rvc_ready = False
        if self.miku:
            threading.Thread(target=self._prewarm_rvc, daemon=True).start()

    def _ensure_rvc_locked(self):
        """Start (once) the rvc_env subprocess that holds the Miku model loaded.
        Caller MUST hold self._rvc_lock so we never spawn two at once (which would
        fight over GPU memory and desync the stdin/stdout protocol)."""
        if self.rvc_proc and self.rvc_proc.poll() is None and self.rvc_ready:
            return True
        if self.rvc_proc:                         # dead / half-started -> clean up
            try:
                self.rvc_proc.terminate()
            except Exception:
                pass
            self.rvc_proc = None
            self.rvc_ready = False
        if not os.path.exists(RVC_PY):
            return False
        try:
            log = open(os.path.join(HERE, "miku_server.log"), "w")
            self.rvc_proc = subprocess.Popen(
                [RVC_PY, MIKU_RVC, "serve"],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=log, text=True, cwd=HERE,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            line = self.rvc_proc.stdout.readline()    # blocks until model loaded
            self.rvc_ready = line.startswith("READY")
            return self.rvc_ready
        except Exception:
            self.rvc_proc = None
            self.rvc_ready = False
            return False

    def _miku_convert(self, mp3_path):
        """Send one file through the RVC server; return the Miku wav path or None.
        Holds the lock across ensure+convert so a warm-up and a real request can
        never start two servers."""
        with self._rvc_lock:
            if not self._ensure_rvc_locked():
                return None
            out_wav = mp3_path + ".miku.wav"
            try:
                self.rvc_proc.stdin.write(f"{mp3_path}|{out_wav}\n")
                self.rvc_proc.stdin.flush()
                resp = self.rvc_proc.stdout.readline().strip()
                if resp == "OK" and os.path.exists(out_wav):
                    return out_wav
            except Exception:
                self.rvc_proc = None
                self.rvc_ready = False
            return None

    # ---- Windows System.Speech fallback ----
    def _start_ps(self):
        try:
            self.ps = subprocess.Popen(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                 "-File", VOICE_PS],
                stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, text=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except Exception:
            self.ps = None

    def _say_ps(self, text):
        if self.ps is None:
            self._start_ps()
        if self.ps:
            try:
                self.ps.stdin.write(text + "\n")
                self.ps.stdin.flush()
            except Exception:
                self.ps = None


# ---- config (API key etc.) -------------------------------------------------
def load_config():
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_config(cfg):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass


# ---- long-term memory (the relationship: she remembers you across days) -----
class Memory:
    """Persistent assistant memory. Survives restarts so Marcille remembers your
    name and your preferences/facts, and knows when you were last around. Pure
    local JSON, no cloud."""

    def __init__(self):
        self.name = ""                 # the user's name, once she learns it
        self.facts = []                # durable preferences/facts she's learned
        self.first_met = ""            # ISO date you two first met
        self.last_seen = ""            # ISO timestamp of last time you were together
        self.sessions = 0              # how many times she's been opened
        self.load()

    def load(self):
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
            self.name = d.get("name", "")
            self.facts = d.get("facts", []) or []
            self.first_met = d.get("first_met", "")
            self.last_seen = d.get("last_seen", "")
            self.sessions = int(d.get("sessions", 0))
        except Exception:
            pass
        if not self.first_met:
            self.first_met = datetime.date.today().isoformat()
        self.sessions += 1
        self.save()

    def save(self):
        try:
            self.last_seen = datetime.datetime.now().isoformat(timespec="seconds")
            with open(MEMORY_FILE, "w", encoding="utf-8") as f:
                json.dump({
                    "name": self.name, "facts": self.facts[-40:],
                    "first_met": self.first_met, "last_seen": self.last_seen,
                    "sessions": self.sessions,
                }, f, indent=2)
        except Exception:
            pass

    def days_away(self):
        if not self.last_seen:
            return 0
        try:
            last = datetime.datetime.fromisoformat(self.last_seen)
            return max(0, (datetime.datetime.now() - last).days)
        except Exception:
            return 0

    def days_known(self):
        try:
            d = datetime.date.fromisoformat(self.first_met)
            return max(0, (datetime.date.today() - d).days)
        except Exception:
            return 0

    def add_fact(self, text):
        text = (text or "").strip()
        if not text or len(text) > 160:
            return False
        low = text.lower()
        if any(low == f.lower() for f in self.facts):
            return False
        self.facts.append(text)
        self.facts = self.facts[-40:]
        self.save()
        return True

    def summary_for_prompt(self):
        """A compact block injected into her system prompt so she actually uses
        what she knows. Empty string if she knows nothing yet."""
        bits = []
        if self.name:
            bits.append(f"The user's name is {self.name}; address them by it naturally.")
        if self.facts:
            bits.append("Their preferences / things to remember: "
                        + "; ".join(self.facts[-12:]) + ".")
        if not bits:
            return ""
        return ("\n\nYou are this person's personal assistant and you know them. "
                "Use what you remember to be more helpful (don't recite it as a list):\n- "
                + "\n- ".join(bits))


# ---- Claude chat brain -----------------------------------------------------
class Brain:
    """Talks to Claude so Marcille can hold a real conversation in character.
    Calls are blocking -- always run .ask() from a worker thread."""

    def __init__(self, api_key=None):
        self.api_key = None          # Claude fully removed — local only
        self.client = None
        self.history = []
        self.has_cc = False          # Claude Code disabled
        self.backend = "local"       # Ollama fallback; Gemini is primary when keyed
        self.persona_extra = ""      # memory block the app injects (name, facts, bond)
        self.gemini_key = None       # set by app from cfg/env -> cloud brain (smart)

    def sys(self, system=None):
        """Full system prompt: persona + whatever she remembers about the user."""
        if system is None:
            system = PERSONA
        return system + self.persona_extra

    def ready(self):
        # ready with a Gemini key OR a local brain model installed
        return self.has_gemini() or self._has_model(self.CHAT_MODEL_LOCAL)

    def has_key(self):
        return False                 # Claude removed

    def set_key(self, key):
        return                       # no-op: Claude removed, local only

    def use_backend(self, backend):
        return False                 # no-op: only the local backend exists now

    def ask(self, user_text, tools=None, dispatch=None, system=None):
        """Returns (reply, error). Gemini when keyed (smart), else local gemma3:4b.
        `tools`/`dispatch` (the old Spotify tool-loop) are ignored; music is handled
        by the intent parser + media keys instead."""
        if self.has_gemini():
            reply, err = self.gemini_chat(user_text, system=system)
            if reply:
                return reply, None
            if not self.ollama_ready():       # no local backup -> surface the error
                return None, err
        if not self.ollama_ready():
            return None, "My brain's offline — add a Gemini key or start Ollama first!"
        return self.chat_local(user_text, system=system)

    def see_screen(self, image_path):
        """Vision: react to a screenshot in character. Gemini when keyed (sharp),
        else local gemma3:4b multimodal."""
        if self.has_gemini():
            reply, err = self.gemini_see_screen(image_path)
            if reply:
                return reply, None
            if not self._has_model(self.VISION_MODEL):
                return None, err
        if self._has_model(self.VISION_MODEL):
            return self.see_screen_local(image_path)
        return None, "Add a Gemini key or install gemma3:4b so I can see your screen."

    def generate_lines(self, context, n=10):
        """Ask the LOCAL model (gemma3:4b via Ollama) for a batch of fresh,
        context-aware idle lines. Returns a list of short spoken strings (empty
        list on failure). No Claude."""
        if not (self._has_model(self.CHAT_MODEL_LOCAL) and self.ollama_ready()):
            return []
        prompt = (
            f"Write {n} SHORT spoken lines Marcille would say RIGHT NOW, unprompted, to "
            "the user, given the real-time context below. Each line: ONE sentence, in "
            "character, specific to the context (reference the actual app / time / mood / "
            "what she sees when it fits). Vary the mood across the batch — teasing, caring, "
            "proud, worried, sleepy, playful. No repeats. Output ONLY the lines, one per "
            "line, no numbering, no quotes, no markdown.\n\nContext:\n" + context)
        try:
            msg = self._ollama_chat(
                self.CHAT_MODEL_LOCAL,
                [{"role": "system", "content": self.sys()},
                 {"role": "user", "content": prompt}],
                timeout=90, options={"temperature": 0.9, "num_predict": 300})
        except Exception:
            return []
        lines = []
        for ln in ((msg or {}).get("content", "")).splitlines():
            ln = ln.strip().lstrip("-•*0123456789. ").strip(' "\'')
            if 4 < len(ln) < 200:
                lines.append(ln)
        return lines[:n + 2]

    def do_task(self, task, allow_shell=False):
        """Task helper. Gemini answers (smart, web-grounded) when keyed, else the
        local qwen2.5 agent (option B) or gemma3 knowledge answer (option A)."""
        if not (self.has_gemini() or self.ollama_ready()):
            return None, "My brain's offline — add a Gemini key or start Ollama first!"
        return self.do_task_local(task, allow_shell=allow_shell)

    # ---- local intent parser (Ollama + Gemma, free & offline) -------------
    OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
    OLLAMA_CHAT = "http://127.0.0.1:11434/api/chat"
    OLLAMA_TAGS = "http://127.0.0.1:11434/api/tags"
    # One small local model does chat + vision + intent — fast on 4GB VRAM, stays
    # resident so it never reloads. (gemma4 was too big AND crashes Ollama 0.30.x;
    # gemma3:4b is the multimodal model that actually fits this machine.)
    GEMMA = "gemma3:4b"
    OLLAMA_MODEL = GEMMA      # quick intent parser
    VISION_MODEL = GEMMA      # multimodal: looks at the screen (local, free)
    CHAT_MODEL_LOCAL = GEMMA  # in-character conversation (local, free)
    # Tool-using agent (web search / file writing). gemma3 can't tool-call, so this
    # is OFF by default; set to a tool model like "qwen2.5:3b" to enable option B.
    AGENT_MODEL = ""
    KEEP_ALIVE = "30m"        # keep the model resident so it doesn't reload each call
    # ---- cloud brain: Google Gemini (smart, free tier) --------------------
    GEMINI_MODEL = "gemini-2.5-flash"
    GEMINI_ENDPOINT = ("https://generativelanguage.googleapis.com/v1beta/"
                       "models/{m}:generateContent")
    # Native function-calling: Gemini itself decides which action to take. Far more
    # reliable at intent than the tiny local model -> this is what drives open/music/etc.
    GEMINI_TOOLS = [{"function_declarations": [
        {"name": "open_app",
         "description": "Open an application or website on the user's computer "
                        "(e.g. Spotify, Chrome, Notepad, Discord, youtube.com).",
         "parameters": {"type": "object", "properties": {
             "name": {"type": "string"}}, "required": ["name"]}},
        {"name": "control_music",
         "description": "Control music playback. Use to play, pause, resume, skip, go "
                        "back, change volume, or play a specific song/playlist.",
         "parameters": {"type": "object", "properties": {
             "action": {"type": "string", "enum": ["play", "pause", "resume", "next",
                        "previous", "volume_up", "volume_down", "mute"]},
             "query": {"type": "string",
                       "description": "Optional song or playlist name to play."}},
             "required": ["action"]}},
        {"name": "set_timer",
         "description": "Start a countdown timer for the given number of seconds.",
         "parameters": {"type": "object", "properties": {
             "seconds": {"type": "integer"}}, "required": ["seconds"]}},
        {"name": "set_reminder",
         "description": "Remind the user about something at a later time.",
         "parameters": {"type": "object", "properties": {
             "text": {"type": "string"},
             "when": {"type": "string",
                      "description": "e.g. 'in 10 minutes', 'in 2 hours', '14:30'"}},
             "required": ["text", "when"]}},
        {"name": "take_note",
         "description": "Save a short text note to the user's Desktop.",
         "parameters": {"type": "object", "properties": {
             "content": {"type": "string"}}, "required": ["content"]}},
        {"name": "web_search",
         "description": "Search the web for current facts, news, prices, weather or "
                        "anything you don't know. Use this instead of guessing.",
         "parameters": {"type": "object", "properties": {
             "query": {"type": "string"}}, "required": ["query"]}},
    ]}]
    INTENT_PROMPT = (
        "You convert a short spoken command to a desktop companion named Marcille "
        "into ONE JSON object and nothing else.\n\n"
        "Allowed \"action\" values:\n"
        "- \"open\": launch an app or website. Put ONLY the app/site name in \"target\" "
        "(e.g. spotify, chrome, notepad, youtube.com).\n"
        "- \"music\": control playback. \"target\" must be one of play, pause, resume, "
        "next, previous, volume up, volume down, OR the name of a song/playlist to put on.\n"
        "- \"note\": jot down a quick text note. Put ONLY the note's CONTENT in \"target\" "
        "(just what to write down). If no specific content was given, use an empty string.\n"
        "- \"task\": something that needs real work (read files, web search, calculations, "
        "look something up online, multi-step jobs). Put the full request in \"target\".\n"
        "- \"chat\": small talk, questions about her, feelings, anything conversational. "
        "Leave \"target\" empty.\n\n"
        "Examples:\n"
        "open chrome -> {{\"action\":\"open\",\"target\":\"chrome\"}}\n"
        "put on some music -> {{\"action\":\"music\",\"target\":\"play\"}}\n"
        "take a note buy milk and eggs -> {{\"action\":\"note\",\"target\":\"buy milk and eggs\"}}\n"
        "write a note that says call the dentist -> {{\"action\":\"note\",\"target\":\"call the dentist\"}}\n"
        "make a note -> {{\"action\":\"note\",\"target\":\"\"}}\n"
        "what's the weather tomorrow -> {{\"action\":\"task\",\"target\":\"what's the weather tomorrow\"}}\n"
        "how are you feeling -> {{\"action\":\"chat\",\"target\":\"\"}}\n\n"
        "Rules: output ONLY the JSON object (keys \"action\" and \"target\"), no prose, "
        "no code fences. Pick the single best action.\n\n"
        "Command: {cmd}\nJSON:")

    def ollama_ready(self):
        """True if a local Ollama server is reachable."""
        try:
            import urllib.request
            urllib.request.urlopen(self.OLLAMA_TAGS, timeout=1.5)
            return True
        except Exception:
            return False

    def parse_intent(self, text, cpu=False):
        """Classify a spoken command into {"action","target"} using the local Gemma
        model via Ollama. Returns None if unavailable/unparseable (caller falls back).
        Set cpu=True to keep it off the GPU (e.g. while Miku RVC owns the VRAM)."""
        try:
            import urllib.request
            opts = {"temperature": 0.0, "num_predict": 80}
            if cpu:
                opts["num_gpu"] = 0
            body = json.dumps({
                "model": self.OLLAMA_MODEL,
                "prompt": self.INTENT_PROMPT.format(cmd=text),
                "stream": False, "format": "json", "keep_alive": self.KEEP_ALIVE,
                "options": opts,
            }).encode("utf-8")
            req = urllib.request.Request(
                self.OLLAMA_URL, data=body,
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as r:
                resp = json.loads(r.read().decode("utf-8"))
            data = json.loads((resp.get("response") or "").strip())
            action = str(data.get("action", "")).lower().strip()
            target = str(data.get("target", "")).strip()
            if action in ("open", "music", "note", "task", "chat"):
                return {"action": action, "target": target}
        except Exception:
            pass
        return None

    # ---- local LLM plumbing (Ollama: vision + chat + agent, free & offline) --
    _models_cache = None

    def _ollama_models(self):
        """Set of installed model names (e.g. {'gemma3:4b','qwen2.5:7b'}). Cached."""
        if self._models_cache is not None:
            return self._models_cache
        try:
            import urllib.request
            with urllib.request.urlopen(self.OLLAMA_TAGS, timeout=2.5) as r:
                data = json.loads(r.read().decode("utf-8"))
            self._models_cache = {m.get("name", "") for m in data.get("models", [])}
        except Exception:
            self._models_cache = set()
        return self._models_cache

    def _has_model(self, name):
        if not name:
            return False
        models = self._ollama_models()
        # match 'gemma3:4b' or a bare 'gemma3' tag variant
        return name in models or any(m.split(":")[0] == name.split(":")[0] for m in models)

    def warm(self):
        """Preload the model into memory so the first real reply isn't cold-start
        slow. Safe to call in a background thread; ignores all errors."""
        try:
            if not self._has_model(self.GEMMA):
                return
            import urllib.request
            body = json.dumps({"model": self.GEMMA, "keep_alive": self.KEEP_ALIVE}).encode()
            req = urllib.request.Request(
                self.OLLAMA_URL, data=body, headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=120).read()
        except Exception:
            pass

    def _ollama_chat(self, model, messages, tools=None, images=None, timeout=180,
                     options=None):
        """One round-trip to Ollama /api/chat. Returns the assistant message dict
        ({"content":..., "tool_calls":[...]}) or None on failure."""
        import urllib.request
        msgs = [dict(m) for m in messages]
        if images and msgs:
            msgs[-1] = dict(msgs[-1]); msgs[-1]["images"] = images
        body = {"model": model, "messages": msgs, "stream": False,
                "keep_alive": self.KEEP_ALIVE, "options": options or {"temperature": 0.4}}
        if tools:
            body["tools"] = tools
        req = urllib.request.Request(
            self.OLLAMA_CHAT, data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            resp = json.loads(r.read().decode("utf-8"))
        return resp.get("message")

    def see_screen_local(self, image_path):
        """FREE local vision: gemma3:4b (multimodal via Ollama) looks at a
        screenshot and reacts in character. No Claude, no cloud."""
        if not self._has_model(self.VISION_MODEL):
            return None, f"I need the {self.VISION_MODEL} model to see — pull it in Ollama."
        try:
            import base64
            with open(image_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("ascii")
            prompt = ("Look at this screenshot of the user's screen. In ONE short spoken "
                      "sentence, react in character to what they're doing — the app, the "
                      "content, what's going on. Be playful, warm, and specific to what you "
                      "actually see. Output ONLY your spoken words.")
            msg = self._ollama_chat(
                self.VISION_MODEL,
                [{"role": "system", "content": self.sys()},
                 {"role": "user", "content": prompt}],
                images=[b64], timeout=180,
                options={"temperature": 0.6, "num_predict": 90})
        except Exception as e:
            return None, f"I couldn't look... ({e})"
        reply = (msg or {}).get("content", "").strip()
        return (reply or None), (None if reply else "Hmm, I couldn't make it out.")

    def chat_local(self, user_text, system=None):
        """FREE local conversation via gemma3:4b. Keeps the same rolling history."""
        if not self._has_model(self.CHAT_MODEL_LOCAL):
            return None, "My local brain isn't installed — pull gemma3:4b in Ollama."
        self.history.append({"role": "user", "content": user_text})
        self.history = self.history[-20:]
        msgs = [{"role": "system", "content": self.sys(system)}]
        for m in self.history:
            if isinstance(m.get("content"), str):
                msgs.append({"role": m["role"], "content": m["content"]})
        try:
            msg = self._ollama_chat(self.CHAT_MODEL_LOCAL, msgs, timeout=120,
                                    options={"temperature": 0.7, "num_predict": 140})
        except Exception as e:
            self.history.append({"role": "assistant", "content": "..."})
            return None, f"My magic fizzled... ({e})"
        reply = (msg or {}).get("content", "").strip()
        reply = clean_spoken(reply)
        self.history.append({"role": "assistant", "content": reply or "..."})
        return (reply or "(Marcille says nothing.)"), None

    # ---- cloud brain: Google Gemini (primary when a key is set) -------------
    def has_gemini(self):
        return bool(self.gemini_key)

    def _gemini(self, system, contents, images=None, audio=None, timeout=60, max_tokens=400, temp=0.7):
        """One call to the Gemini API (pure urllib, no SDK). `contents` = list of
        {"role": "user"|"model", "text": ...}; `images` = base64 PNG strings and
        `audio` = (mime_type, base64) tuples attached to the LAST turn. Returns
        (text, error). thinkingBudget=0 keeps 2.5-flash snappy and stops 'thinking'
        from eating the whole output budget."""
        import urllib.request, urllib.error
        if not self.gemini_key:
            return None, "no gemini key"
        conv = []
        for c in contents:
            conv.append({"role": c["role"], "parts": [{"text": c["text"]}]})
        if images and conv:
            for b64 in images:
                conv[-1]["parts"].append(
                    {"inline_data": {"mime_type": "image/png", "data": b64}})
        if audio and conv:
            for mime, b64 in audio:
                conv[-1]["parts"].append(
                    {"inline_data": {"mime_type": mime, "data": b64}})
        body = {"contents": conv,
                "generationConfig": {"temperature": temp, "maxOutputTokens": max_tokens,
                                     "thinkingConfig": {"thinkingBudget": 0}}}
        if system:
            body["system_instruction"] = {"parts": [{"text": system}]}
        url = self.GEMINI_ENDPOINT.format(m=self.GEMINI_MODEL) + "?key=" + self.gemini_key
        try:
            req = urllib.request.Request(
                url, data=json.dumps(body).encode("utf-8"),
                headers={"Content-Type": "application/json"})
            resp = json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                detail = json.loads(e.read().decode("utf-8")).get("error", {}).get("message", "")
            except Exception:
                pass
            return None, f"Gemini {e.code}: {detail or e.reason}"
        except Exception as e:
            return None, f"Gemini unreachable ({e})"
        cands = resp.get("candidates") or []
        if not cands:
            fb = resp.get("promptFeedback", {}) or {}
            br = fb.get("blockReason")
            return None, "Gemini gave no answer" + (f" (blocked: {br})" if br else "")
        parts = ((cands[0].get("content") or {}).get("parts")) or []
        text = "".join(p.get("text", "") for p in parts).strip()
        return (text or None), (None if text else "Gemini returned nothing")

    def transcribe_audio(self, wav_path):
        """Speech-to-text for a recorded voice command, via Gemini (free, multilingual
        — far better than local whisper on this machine). Returns the spoken text, or
        None if there's no key, the call fails, or nothing intelligible was said."""
        if not self.gemini_key:
            return None
        try:
            import base64
            with open(wav_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("ascii")
        except Exception:
            return None
        sysp = ("You are a speech-to-text transcriber. Transcribe the short spoken "
                "command in the audio EXACTLY, in whatever language is spoken. Output "
                "ONLY the words said — no quotes, no translation, no notes. If the audio "
                "is silent or unintelligible, output the single word NONE.")
        msgs = [{"role": "user", "text": "Transcribe this audio."}]
        text, err = self._gemini(sysp, msgs, audio=[("audio/wav", b64)],
                                 max_tokens=120, temp=0.0)
        # free tier is ~20 requests/min; on a momentary 429, wait briefly + retry once
        if (not text) and err and "429" in err:
            import time
            time.sleep(5)
            text, err = self._gemini(sysp, msgs, audio=[("audio/wav", b64)],
                                     max_tokens=120, temp=0.0)
        if not text:
            return None
        t = text.strip().strip('"').strip()
        if not t or t.strip(".!? ").upper() == "NONE":
            return None
        return t

    def gemini_chat(self, user_text, system=None):
        """In-character conversation via Gemini. Shares the same rolling history as
        the local brain. History is only committed on success (clean fallback)."""
        contents = []
        for m in self.history[-20:]:
            if isinstance(m.get("content"), str):
                contents.append({"role": "model" if m["role"] == "assistant" else "user",
                                 "text": m["content"]})
        contents.append({"role": "user", "text": user_text})
        text, err = self._gemini(self.sys(system), contents, max_tokens=500, temp=0.75)
        if err or not text:
            return None, err or "Gemini returned nothing"
        text = clean_spoken(text)
        self.history.append({"role": "user", "content": user_text})
        self.history.append({"role": "assistant", "content": text})
        self.history = self.history[-20:]
        return text, None

    def gemini_see_screen(self, image_path):
        """Vision via Gemini (multimodal) — far sharper than the local model."""
        try:
            import base64
            with open(image_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("ascii")
        except Exception as e:
            return None, f"couldn't read screenshot ({e})"
        prompt = ("Look at this screenshot of the user's screen. In ONE short spoken "
                  "sentence, react in character to what they're doing — the app, the "
                  "content, what's going on. Be playful, warm and specific to what you "
                  "actually see. Output ONLY your spoken words.")
        txt, err = self._gemini(self.sys(), [{"role": "user", "text": prompt}],
                                images=[b64], max_tokens=120, temp=0.6)
        return (clean_spoken(txt) if txt else txt), err

    def _gemini_parts(self, system, contents, tools=None, timeout=60,
                      max_tokens=600, temp=0.6, thinking_budget=0):
        """Lower-level Gemini call that returns the raw response PARTS list (so we can
        see functionCall parts), or (None, error)."""
        import urllib.request, urllib.error
        if not self.gemini_key:
            return None, "no gemini key"
        body = {"contents": contents,
                "generationConfig": {"temperature": temp, "maxOutputTokens": max_tokens,
                                     "thinkingConfig": {"thinkingBudget": thinking_budget}}}
        if system:
            body["system_instruction"] = {"parts": [{"text": system}]}
        if tools:
            body["tools"] = tools
        url = self.GEMINI_ENDPOINT.format(m=self.GEMINI_MODEL) + "?key=" + self.gemini_key
        try:
            req = urllib.request.Request(
                url, data=json.dumps(body).encode("utf-8"),
                headers={"Content-Type": "application/json"})
            resp = json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                detail = json.loads(e.read().decode("utf-8")).get("error", {}).get("message", "")
            except Exception:
                pass
            return None, f"Gemini {e.code}: {detail or e.reason}"
        except Exception as e:
            return None, f"Gemini unreachable ({e})"
        cands = resp.get("candidates") or []
        if not cands:
            fb = resp.get("promptFeedback", {}) or {}
            br = fb.get("blockReason")
            return None, "Gemini gave no answer" + (f" (blocked: {br})" if br else "")
        return (((cands[0].get("content") or {}).get("parts")) or []), None

    def gemini_tools_chat(self, user_text, dispatch, system=None):
        """Gemini decides intent: it either CALLS a tool (open/music/timer/note/
        reminder/web_search) or just talks. App tools run via dispatch(name, args)->
        str; web_search runs here. Shares rolling history. Returns (reply, error)."""
        sysp = (self.sys(system) +
                "\n\nYou can DO things on the user's computer with your tools — open "
                "apps, control music, set timers and reminders, take notes — and look "
                "up anything live with web_search. When the user asks you to DO "
                "something, CALL the matching tool; never just claim you did it. "
                "When you use web_search, the results are just notes for you: answer "
                "in your OWN words as Marcille, stating the fact directly as something "
                "you know. NEVER quote, mention, or summarize 'the search results', and "
                "never open with 'According to', 'Based on', 'In public opinion' or "
                "'Summary'. After acting or looking something up, reply with ONE or two "
                "short, in-character spoken sentences — the answer first, then maybe one "
                "quick reaction.")
        contents = []
        for m in self.history[-20:]:
            if isinstance(m.get("content"), str):
                contents.append({"role": "model" if m["role"] == "assistant" else "user",
                                 "parts": [{"text": m["content"]}]})
        contents.append({"role": "user", "parts": [{"text": user_text}]})
        final = None
        grounded_turn = False
        for _ in range(5):
            parts, err = self._gemini_parts(
                sysp, contents, tools=self.GEMINI_TOOLS,
                thinking_budget=192 if grounded_turn else 0)
            if err:
                return None, err
            calls = [p["functionCall"] for p in parts if "functionCall" in p]
            text = "".join(p.get("text", "") for p in parts if "text" in p).strip()
            if not calls:
                final = text
                break
            contents.append({"role": "model", "parts": parts})
            resp_parts = []
            for fc in calls:
                name = fc.get("name", "")
                args = fc.get("args", {}) or {}
                if name == "web_search":
                    result = self._web_search(args.get("query", ""))[:2500]
                    grounded_turn = True
                else:
                    result = dispatch(name, args)
                resp_parts.append({"functionResponse": {
                    "name": name, "response": {"result": str(result)[:2500]}}})
            contents.append({"role": "user", "parts": resp_parts})
        final = clean_spoken(final) if final else final
        if not final:
            final = "Done!"
        self.history.append({"role": "user", "content": user_text})
        self.history.append({"role": "assistant", "content": final})
        self.history = self.history[-20:]
        return final, None

    # ---- agent: local tool-using task runner (qwen2.5) ----------------------
    def _agent_tools(self, allow_shell):
        tools = [
            {"type": "function", "function": {
                "name": "web_search",
                "description": "Search the web and get titles + snippets for a query. "
                               "Use for current info, facts, weather, news, lookups.",
                "parameters": {"type": "object", "properties": {
                    "query": {"type": "string"}}, "required": ["query"]}}},
            {"type": "function", "function": {
                "name": "web_fetch",
                "description": "Fetch a web page URL and return its readable text.",
                "parameters": {"type": "object", "properties": {
                    "url": {"type": "string"}}, "required": ["url"]}}},
            {"type": "function", "function": {
                "name": "write_file",
                "description": "Write text to a file on the user's Desktop (creates it). "
                               "Use for to-do lists, notes, saving results.",
                "parameters": {"type": "object", "properties": {
                    "filename": {"type": "string"},
                    "content": {"type": "string"}}, "required": ["filename", "content"]}}},
            {"type": "function", "function": {
                "name": "read_file",
                "description": "Read a text file by absolute path and return its content.",
                "parameters": {"type": "object", "properties": {
                    "path": {"type": "string"}}, "required": ["path"]}}},
            {"type": "function", "function": {
                "name": "open_app",
                "description": "Open an app or website on the user's computer by name.",
                "parameters": {"type": "object", "properties": {
                    "name": {"type": "string"}}, "required": ["name"]}}},
        ]
        if allow_shell:
            tools.append({"type": "function", "function": {
                "name": "run_shell",
                "description": "Run a Windows shell command and return its output. "
                               "Powerful and dangerous — only for explicit requests.",
                "parameters": {"type": "object", "properties": {
                    "command": {"type": "string"}}, "required": ["command"]}}})
        return tools

    def _desktop_dir(self):
        for cand in (os.path.join(os.path.expanduser("~"), "OneDrive", "Desktop"),
                     os.path.join(os.path.expanduser("~"), "Desktop")):
            if os.path.isdir(cand):
                return cand
        return os.path.expanduser("~")

    def _run_tool(self, name, args, allow_shell):
        """Execute one agent tool call. Returns a short string result."""
        try:
            if name == "web_search":
                return self._web_search(args.get("query", ""))
            if name == "web_fetch":
                return self._web_fetch(args.get("url", ""))
            if name == "write_file":
                fn = os.path.basename(args.get("filename", "note.txt")) or "note.txt"
                path = os.path.join(self._desktop_dir(), fn)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(args.get("content", ""))
                return f"Wrote {len(args.get('content',''))} chars to {path}"
            if name == "read_file":
                p = args.get("path", "")
                with open(p, "r", encoding="utf-8", errors="replace") as f:
                    return f.read()[:4000]
            if name == "open_app":
                self._launch_app(args.get("name", ""))
                return f"Opened {args.get('name','')}"
            if name == "run_shell" and allow_shell:
                out = subprocess.run(["powershell", "-NoProfile", "-Command",
                                      args.get("command", "")],
                                     capture_output=True, text=True, timeout=60,
                                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                return ((out.stdout or "") + (out.stderr or "")).strip()[:3000] or "(no output)"
            return f"(tool {name} unavailable)"
        except Exception as e:
            return f"(tool {name} failed: {e})"

    def _launch_app(self, exe):
        exe = (exe or "").strip()
        low = exe.lower()
        is_url = low.startswith(("http://", "https://")) or (
            " " not in low and "." in low and not low.endswith((".exe", ".bat", ".com")))
        if is_url:
            webbrowser.open(exe if low.startswith("http") else "https://" + exe)
            return
        try:
            os.startfile(exe)
        except Exception:
            subprocess.Popen(exe)

    def _web_search(self, query):
        import urllib.request, urllib.parse, re, html, json
        query = (query or "").strip()
        if not query:
            return "(empty query)"
        ua = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        clean = lambda s: html.unescape(re.sub(r"<[^>]+>", "", s)).strip()
        out = []
        # DuckDuckGo Lite (POST) — plain HTML table, scrapeable & no key
        try:
            data = urllib.parse.urlencode({"q": query}).encode()
            req = urllib.request.Request("https://lite.duckduckgo.com/lite/",
                                         data=data, headers=ua)
            page = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "replace")
            # DDG lite uses single-quoted attrs; accept either quote style
            titles = re.findall(r'class=[\'"]result-link[\'"][^>]*>(.*?)</a>', page, re.S)
            snips = re.findall(r'class=[\'"]result-snippet[\'"][^>]*>(.*?)</td>', page, re.S)
            for i in range(min(5, max(len(titles), len(snips)))):
                t = clean(titles[i]) if i < len(titles) else ""
                s = clean(snips[i]) if i < len(snips) else ""
                fact = s or t
                if fact:
                    out.append("- " + fact)
        except Exception:
            pass
        # DuckDuckGo Instant Answer API — adds an authoritative summary when present
        try:
            u = "https://api.duckduckgo.com/?" + urllib.parse.urlencode(
                {"q": query, "format": "json", "no_html": 1})
            j = json.loads(urllib.request.urlopen(
                urllib.request.Request(u, headers=ua), timeout=15).read())
            abs_ = (j.get("AbstractText") or "").strip()
            if abs_:
                out.insert(0, "- " + abs_)
        except Exception:
            pass
        return "\n".join(out) if out else "(no results found)"

    def _web_fetch(self, url):
        import urllib.request, re, html
        if not url.startswith("http"):
            url = "https://" + url
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            page = r.read().decode("utf-8", "replace")
        page = re.sub(r"(?is)<(script|style).*?</\1>", " ", page)
        text = html.unescape(re.sub(r"<[^>]+>", " ", page))
        return re.sub(r"\s+", " ", text).strip()[:4000] or "(empty page)"

    def do_task_local(self, task, allow_shell=False):
        """FREE local task runner. If the agent model (qwen2.5) is installed she
        uses real tools (search/fetch/files/apps) — option B. Otherwise she answers
        from her own knowledge with gemma3 — option A. Either way: no Claude."""
        # B: tool-using agent
        if self._has_model(self.AGENT_MODEL):
            shell_note = ("You can run shell commands via run_shell."
                          if allow_shell else "You have no shell access.")
            sysp = (self.sys() + "\n\nYou can actually DO things on the user's computer with "
                    "your tools (web search, fetch pages, read/write files on the Desktop, "
                    "open apps). " + shell_note + " Use tools when the task needs real data "
                    "or actions; don't pretend. When finished, reply with ONE or two short, "
                    "in-character spoken sentences saying what you did or found. Never claim "
                    "you did something you didn't.")
            messages = [{"role": "system", "content": sysp},
                        {"role": "user", "content": task}]
            tools = self._agent_tools(allow_shell)
            try:
                for _ in range(6):
                    msg = self._ollama_chat(self.AGENT_MODEL, messages, tools=tools,
                                            timeout=300,
                                            options={"temperature": 0.3, "num_predict": 400})
                    if not msg:
                        return None, "My local agent didn't answer..."
                    calls = msg.get("tool_calls") or []
                    messages.append({"role": "assistant",
                                     "content": msg.get("content", ""),
                                     "tool_calls": calls})
                    if not calls:
                        return (msg.get("content", "").strip() or
                                "(done, but I have nothing to say)"), None
                    for c in calls:
                        fn = c.get("function", {})
                        args = fn.get("arguments", {})
                        if isinstance(args, str):
                            try:
                                args = json.loads(args)
                            except Exception:
                                args = {}
                        result = self._run_tool(fn.get("name", ""), args, allow_shell)
                        messages.append({"role": "tool", "content": str(result)[:4000]})
                return (msg.get("content", "").strip() or
                        "That one got away from me, sorry!"), None
            except Exception as e:
                return None, f"I couldn't manage that one... ({e})"
        # A: no tool model installed -> answer from the web (grounded) or knowledge
        return self.answer_grounded(task, web=self.web_grounding)

    web_grounding = True   # app overrides from cfg; fetch real facts (free, no tokens)

    def answer_grounded(self, question, web=True):
        """Answer a factual / general question. With web grounding on, fetch real
        search results FIRST and have the local model phrase them in character — so
        she stays accurate and current despite being a small model. Free (no tokens)."""
        context = ""
        if web:
            try:
                context = self._web_search(question)
            except Exception:
                context = ""
        grounded = context and not context.startswith("(no results")
        if grounded:
            sysp = (self.sys() + "\n\nYou just looked this up; the notes below are for "
                    "YOUR eyes only. Answer in ONE or two short, in-character spoken "
                    "sentences, stating the actual fact, number or name directly as "
                    "something you know. Do NOT mention the notes, sources or that you "
                    "searched; never start with 'According to', 'Based on', 'In public "
                    "opinion' or 'Summary'. If the notes don't contain the answer, say "
                    "you couldn't find it.\n\nNotes:\n" + context[:3000])
        else:
            sysp = (self.sys() + "\n\nAnswer the question in ONE or two short, "
                    "in-character spoken sentences from your own knowledge. If you are "
                    "not sure of the answer, say so honestly and briefly.")
        if self.has_gemini():
            text, err = self._gemini(sysp, [{"role": "user", "text": question}],
                                     max_tokens=300, temp=0.4)
            if text:
                return clean_spoken(text), None
            if not self.ollama_ready():
                return None, err
        try:
            msg = self._ollama_chat(self.CHAT_MODEL_LOCAL,
                                    [{"role": "system", "content": sysp},
                                     {"role": "user", "content": question}],
                                    timeout=120,
                                    options={"temperature": 0.3, "num_predict": 220})
        except Exception as e:
            return None, f"I couldn't look that up... ({e})"
        reply = (msg or {}).get("content", "").strip()
        reply = clean_spoken(reply)
        return (reply or None), (None if reply else "I came up empty on that, sorry!")


def clean_spoken(text):
    """Make any reply safe + natural for TTS: strip markdown/emoji, drop robotic
    'search result' openers, collapse whitespace. Applied at the return of every
    spoken path. Conservative: only removes an opener when real sentence follows,
    so a legit short reply like 'Okay!' is never eaten."""
    import re
    if not text:
        return text
    t = str(text)
    # 1) strip markdown emphasis / code markers TTS would read aloud
    t = t.replace("**", "").replace("__", "")
    t = re.sub(r"`+", "", t)                    # backticks / code fences
    t = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", t)  # leading markdown headers
    t = re.sub(r"(?m)^\s*[-*]\s+", "", t)        # bullet list markers -> plain
    # asterisk stage directions / leftover single asterisks
    t = re.sub(r"\*([^*]+)\*", r"\1", t)         # *waves* -> waves
    t = t.replace("*", "")
    # 2) strip emoji / pictographs (TTS chokes or says 'smiling face')
    t = re.sub(r"[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF←-⇿⬀-⯿️]", "", t)
    # 3) remove robotic, source-framing openers — ANCHORED to start, and ONLY
    #    when more text follows (require trailing word chars). Case-insensitive.
    openers = [
        r"in\s+(the\s+|my\s+|your\s+|a\s+)?(public|popular|common|general|widespread|broad)\s+opinion[,:\-]?\s+",
        r"according\s+to\s+(the\s+)?(search\s+results|sources?|the\s+web|the\s+internet|wikipedia|public\s+opinion|reports?)[,:\-]?\s+",
        r"based\s+on\s+(the\s+)?(search\s+)?results[,:\-]?\s+",
        r"the\s+search\s+results\s+(say|show|indicate|suggest)[,:\-]?\s+",
        r"(it\s+is|it's)\s+(widely|generally|commonly|often)\s+(believed|known|thought|held|said|reported)(\s+that)?[,:\-]?\s+",
        r"sources?\s+(say|state|report|indicate|suggest)[,:\-]?\s+",
        r"summary\s*[:\-]\s+",
        r"as\s+an\s+ai(\s+language\s+model)?[,:\-]?\s+",
        r"(well|so|okay|ok|sure|now|right|hmm|oh)[,]\s+",
    ]
    # strip ALL stacked leading openers, not just the first (e.g. "Well, in public opinion,")
    for _round in range(4):
        hit = False
        for pat in openers:
            new = re.sub(r"(?i)^\s*" + pat + r"(?=\S)", "", t, count=1)
            if new != t and new.strip():     # only accept if something remains
                t, hit = new, True
                break
        if not hit:
            break
    # drop a leftover leading separator and recapitalise the first letter
    t = re.sub(r"^\s*[\-–—:,;]\s+", "", t)
    if t[:1].islower():
        t = t[:1].upper() + t[1:]
    # 4) collapse whitespace / blank lines
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{2,}", "\n", t).strip()
    return t


def emote_for(text):
    """Guess a facial expression from Marcille's reply text."""
    t = text.lower()
    if text.count("!") >= 2 or any(w in t for w in
            ("aaah", "scream", "stop", "forbidden", "ugh", "unbelievable", "no!")):
        return "panic"
    if any(w in t for w in ("dizzy", "spinning", "faint", "overwhelm", "too much")):
        return "dizzy"
    if any(w in t for w in ("oops", "clumsy", "tripped", "dropped", "mess", "my fault")):
        return "clumsy"
    if any(w in t for w in ("haha", "hee", "hilarious", "can't stop laughing")):
        return "laughing"
    if any(w in t for w in ("wonderful", "yay", "great", "glad", "love", "delicious")):
        return "happy"
    if any(w in t for w in ("aha", "i see", "i get it", "of course", "eureka", "got it")):
        return "aha"
    if any(w in t for w in ("poor", "shame", "pity", "feel bad", "there there")):
        return "pity"
    if any(w in t for w in ("alone", "outlive", "everyone dies", "grave", "forever")):
        return "very_sad"
    if any(w in t for w in ("miss you", "sorry", "sad", "sigh", "lonely")):
        return "sad"
    if any(w in t for w in ("hmph", "fine", "i suppose", "not dancing", "d-don't",
                            "shy", "blush", "embarrass")):
        return "embarrassed"
    if any(w in t for w in ("hmm", "let me think", "thinking", "perhaps", "consider")):
        return "thinking"
    if any(w in t for w in ("actually", "academy", "magic", "logic", "studied", "because")):
        return "idea"
    if "?" in text and len(text) < 70:
        return "surprised"
    return random.choice(["normal", "happy", "idea", "embarrassed", "thinking", "aha"])


# ---- Spotify ---------------------------------------------------------------
SPOTIFY_CACHE = os.path.join(HERE, ".spotify_cache")
SPOTIFY_SCOPES = ("user-read-playback-state user-modify-playback-state "
                  "user-read-currently-playing playlist-read-private")


class Spotify:
    """Controls the user's Spotify via the Web API (OAuth). Blocking calls --
    use from a worker thread. Returns short human strings for Marcille to react to."""

    def __init__(self, cfg):
        self.cfg = cfg
        self.sp = None

    def configured(self):
        return bool(self.cfg.get("spotify_client_id")
                    and self.cfg.get("spotify_client_secret"))

    def connect(self):
        """First call opens a browser to authorize. Returns error string or None."""
        if self.sp:
            return None
        if not self.configured():
            return "I need your Spotify keys first!"
        try:
            import spotipy
            from spotipy.oauth2 import SpotifyOAuth
        except ImportError:
            return "Tell the user to run 'pip install spotipy'."
        try:
            auth = SpotifyOAuth(
                client_id=self.cfg["spotify_client_id"],
                client_secret=self.cfg["spotify_client_secret"],
                redirect_uri=self.cfg.get("spotify_redirect_uri",
                                          "http://127.0.0.1:8888/callback"),
                scope=SPOTIFY_SCOPES, cache_path=SPOTIFY_CACHE, open_browser=True)
            self.sp = spotipy.Spotify(auth_manager=auth)
            self.sp.current_user()                # force the token exchange
        except Exception as e:
            self.sp = None
            return f"Spotify wouldn't let me in... ({e})"
        return None

    def _device_id(self):
        try:
            devs = self.sp.devices().get("devices", [])
        except Exception:
            return None
        if not devs:
            return None
        for d in devs:
            if d.get("is_active"):
                return d["id"]
        return devs[0]["id"]

    def now_playing(self):
        if self.connect():
            return None
        try:
            cur = self.sp.current_playback()
        except Exception:
            return None
        if not cur or not cur.get("item"):
            return None
        it = cur["item"]
        return {"name": it["name"],
                "artist": ", ".join(a["name"] for a in it["artists"]),
                "playing": cur.get("is_playing", False)}

    def _start(self, **kw):
        dev = self._device_id()
        if dev is None:
            return "no_device"
        self.sp.start_playback(device_id=dev, **kw)
        return None

    def play_playlist(self, query):
        err = self.connect()
        if err:
            return err
        try:
            best = None
            results = self.sp.current_user_playlists(limit=50)
            for pl in results.get("items", []):
                if query.lower() in pl["name"].lower():
                    best = pl
                    break
            if not best:
                return f"I couldn't find a playlist called '{query}'."
            r = self._start(context_uri=best["uri"])
            if r == "no_device":
                return "Open Spotify on a device first, then ask me again!"
            return f"Now playing your '{best['name']}' playlist."
        except Exception as e:
            return f"That didn't work... ({e})"

    def play_track(self, query):
        err = self.connect()
        if err:
            return err
        try:
            res = self.sp.search(q=query, type="track", limit=1)
            items = res.get("tracks", {}).get("items", [])
            if not items:
                return f"I couldn't find '{query}' anywhere."
            t = items[0]
            r = self._start(uris=[t["uri"]])
            if r == "no_device":
                return "Open Spotify on a device first, then ask me again!"
            who = ", ".join(a["name"] for a in t["artists"])
            return f"Playing '{t['name']}' by {who}."
        except Exception as e:
            return f"That didn't work... ({e})"

    def _simple(self, fn, ok):
        err = self.connect()
        if err:
            return err
        try:
            fn()
            return ok
        except Exception as e:
            return f"Hmph, it wouldn't listen... ({e})"

    def pause(self):
        return self._simple(self.sp.pause_playback, "Paused.")

    def resume(self):
        return self._simple(lambda: self.sp.start_playback(device_id=self._device_id()),
                            "Resuming.")

    def skip(self):
        return self._simple(self.sp.next_track, "Skipped to the next track.")

    def previous(self):
        return self._simple(self.sp.previous_track, "Back to the previous track.")

    def set_volume(self, percent):
        percent = max(0, min(100, int(percent)))
        return self._simple(lambda: self.sp.volume(percent), f"Volume set to {percent}%.")


# tool schema Claude sees so Marcille can run Spotify from chat
SPOTIFY_TOOLS = [
    {"name": "spotify_play_playlist", "description": "Start playing one of the user's "
     "Spotify playlists, matched by name.", "input_schema": {"type": "object",
     "properties": {"name": {"type": "string", "description": "Playlist name or part of it"}},
     "required": ["name"]}},
    {"name": "spotify_play_song", "description": "Search Spotify and play a song.",
     "input_schema": {"type": "object", "properties": {"query": {"type": "string",
      "description": "Song name, optionally with artist"}}, "required": ["query"]}},
    {"name": "spotify_pause", "description": "Pause Spotify playback.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "spotify_resume", "description": "Resume Spotify playback.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "spotify_skip", "description": "Skip to the next track.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "spotify_previous", "description": "Go back to the previous track.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "spotify_now_playing", "description": "Check what song is currently playing.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "spotify_set_volume", "description": "Set Spotify volume (0-100).",
     "input_schema": {"type": "object", "properties": {"percent": {"type": "integer"}},
     "required": ["percent"]}},
]

SPOTIFY_NOTE = ("\n\nYou can control the user's Spotify with your tools (play playlists or "
                "songs, pause, resume, skip, go back, set volume, check what's playing). "
                "Use them whenever the user asks about music, then reply in character about "
                "what you did.")


# ---- sprite loading --------------------------------------------------------
def ensure_frames():
    needed = [os.path.join(FRAMES, f"{e}.png") for e in EMOTIONS]
    if all(os.path.exists(p) for p in needed):
        return
    builder = os.path.join(HERE, "assets", "build_marcille_new.py")
    if not os.path.exists(builder):
        builder = os.path.join(HERE, "assets", "build_marcille_emotions.py")
    if not os.path.exists(builder):
        builder = os.path.join(HERE, "assets", "build_marcille.py")
    subprocess.run([sys.executable, builder], check=False)


def load_emotions():
    ensure_frames()
    out = {}
    for e in EMOTIONS:
        im = Image.open(os.path.join(FRAMES, f"{e}.png")).convert("RGBA")
        if SCALE != 1:
            im = im.resize((im.width * SCALE, im.height * SCALE), Image.NEAREST)
        out[e] = im
    return out


def load_walk():
    """Full-body walk-mode frames (idle + walk cycle + run). May be absent."""
    base = os.path.join(HERE, "assets", "frames", "marcille_walk")

    def ld(name):
        im = Image.open(os.path.join(base, name)).convert("RGBA")
        if SCALE != 1:
            im = im.resize((im.width * SCALE, im.height * SCALE), Image.NEAREST)
        return im

    if not os.path.exists(os.path.join(base, "idle.png")):
        return None
    walk, i = [], 0
    while os.path.exists(os.path.join(base, f"walk_{i}.png")):
        walk.append(ld(f"walk_{i}.png"))
        i += 1
    run, i = [], 0
    while os.path.exists(os.path.join(base, f"run_{i}.png")):
        run.append(ld(f"run_{i}.png"))
        i += 1
    return {"idle": ld("idle.png"), "walk": walk, "run": run}


# ---- reminders -------------------------------------------------------------
def load_tasks():
    try:
        with open(TASKS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_tasks(tasks):
    try:
        with open(TASKS_FILE, "w", encoding="utf-8") as f:
            json.dump(tasks, f, indent=2)
    except Exception:
        pass


def parse_when(text):
    """'in 10m' / 'in 2h' / 'in 30s' / 'HH:MM' -> datetime, or None."""
    text = (text or "").strip().lower()
    now = datetime.datetime.now()
    if text.startswith("in "):
        body = text[3:].strip()
        num = "".join(ch for ch in body if ch.isdigit())
        if not num:
            return None
        n = int(num)
        if "h" in body:
            return now + datetime.timedelta(hours=n)
        if "s" in body:
            return now + datetime.timedelta(seconds=n)
        return now + datetime.timedelta(minutes=n)   # default minutes
    if ":" in text:
        try:
            hh, mm = text.split(":")
            due = now.replace(hour=int(hh), minute=int(mm), second=0, microsecond=0)
            if due <= now:
                due += datetime.timedelta(days=1)
            return due
        except Exception:
            return None
    return None


# ---- the companion ---------------------------------------------------------
class Marcille:
    def __init__(self):
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-transparentcolor", TRANSPARENT)
        self.root.config(bg=TRANSPARENT)

        self.cfg = load_config()
        self.scale = float(self.cfg.get("scale", 1.0))

        # keep the original PIL frames so we can re-render at any size live
        self._emo_src = load_emotions()
        self._walk_src = load_walk()
        self.has_walk = self._walk_src is not None
        self.build_images()

        self.mode = "portrait"
        self.anim_i = 0

        self.screen_w = self.root.winfo_screenwidth()
        self.screen_h = self.root.winfo_screenheight()
        self.fw, self.fh = self.p_fw, self.p_fh
        self.W = self.fw + 40
        self.H = self.fh + 40 + MUSIC_BAND
        self.x = random.randint(60, self.screen_w - self.W - 60)
        self.floor_y = self.screen_h - self.H - GROUND_MARGIN
        self.y = self.floor_y

        self.canvas = tk.Canvas(self.root, width=self.W, height=self.H,
                                bg=TRANSPARENT, highlightthickness=0)
        self.canvas.pack()

        self.voice = Voice()
        saved_voice = self.cfg.get("voice")     # [voice, rate, pitch] if user picked one
        if saved_voice:
            self.voice.set_voice(*saved_voice)
        if self.cfg.get("miku"):
            self.voice.set_miku(True)            # real Miku RVC voice (loads in background)
        self.tasks = load_tasks()
        self.brain = Brain(self.cfg.get("api_key"))
        self.brain.web_grounding = bool(self.cfg.get("web_grounding", True))
        self.brain.gemini_key = (self.cfg.get("gemini_key")
                                 or os.environ.get("GEMINI_API_KEY")
                                 or os.environ.get("GOOGLE_API_KEY"))
        threading.Thread(target=self.brain.warm, daemon=True).start()  # preload model
        self.spotify = Spotify(self.cfg)
        self.chat_win = None
        self.player_win = None
        self.np = None                 # last-known now-playing dict
        self._np_busy = False
        self.chip_buttons = {}         # button name -> (x0,y0,x1,y1) hit boxes
        if self.spotify.configured() and os.path.exists(SPOTIFY_CACHE):
            threading.Thread(target=self.spotify.connect, daemon=True).start()

        self.state = "idle"      # idle, move, sleep, happy, panic, casting, drag, fall
        self.state_timer = 60
        self.direction = -1
        self.frame = 0
        self.vy = 0.0
        self.fx = 0.0
        self.blink_t = random.randint(40, 120)

        self.happiness = 90.0
        self.hunger = 90.0
        self.heart_timer = 0
        self.bang_timer = 0
        self.emote_override = None
        self.emote_ovr_t = 0
        self.music_mode = False
        self.chatter_cd = 600
        self.neglect_cd = 0
        self.bubble = ""
        self.bubble_t = 0

        # situational awareness
        self.aware_cd = 500            # frames until she may comment on the app
        self.last_cat = None           # last app category she reacted to
        self.batt_low = False          # currently in a low-battery fret
        self.batt_nag_cd = 0           # frames until she may re-nag about battery
        self.rhythm_phase = None       # last time-of-day phase greeted

        # living presence (Pillar 1): never perfectly still, watches the cursor,
        # idle fidgets, notices when you step away / come back
        self.away = False              # has the user been idle long enough to be "away"
        self.fidget_cd = random.randint(250, 600)  # frames until next silent fidget
        self.look_dx = 0.0             # smoothed horizontal lean toward the cursor
        self.sway_phase = random.random() * 6.28   # personal phase so sway isn't robotic

        # living dialogue (dynamic, context-aware idle lines)
        self.line_pool = []            # fresh AI-generated idle lines, drawn down over time
        self.recent_lines = []         # last few spoken lines, to avoid repeats
        self.pool_busy = False         # a refresh is in flight
        self.pool_key = None           # context signature the current pool was made for
        self.last_seen = ""            # last thing she saw on screen (for context)
        self.start_time = time.time()  # session start, for "how long working"
        self._task_busy = False
        self.allow_shell = bool(self.cfg.get("task_shell", False))

        # assistant memory (Pillar 4): she remembers your name + preferences
        self.memory = Memory()
        self._sync_memory()            # feed name/facts into her persona
        # proactive screen glances (she peeks at what you're doing now and then)
        self.glance_cd = random.randint(6000, 10000)   # frames (~4-7 min) to first glance
        self._greeted_return = False   # have we done the "welcome back across days" line

        # voice input (wake word "Marcille")
        self.voice_proc = None
        self.voice_listening = False

        self.dragging = False
        self.drag_dx = self.drag_dy = 0

        self.canvas.bind("<Button-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Button-3>", self.show_menu)
        self.canvas.bind("<Double-Button-1>", lambda e: self.open_chat())
        self.root.bind("<Escape>", lambda e: self.quit())
        self.root.bind("<Control-equal>", lambda e: self.set_scale(self.scale + 0.15))
        self.root.bind("<Control-plus>", lambda e: self.set_scale(self.scale + 0.15))
        self.root.bind("<Control-minus>", lambda e: self.set_scale(self.scale - 0.15))

        self.build_menu()
        self.move_window()
        self.greet()
        if self.cfg.get("voice_input"):           # resume wake-word listening
            threading.Thread(target=self.start_voice, daemon=True).start()
        self.tick()

    # ---- menu -------------------------------------------------------------
    def build_menu(self):
        m = tk.Menu(self.root, tearoff=0)
        m.add_command(label="💬 Chat with Marcille", command=self.open_chat)
        m.add_command(label="🪄 Talk to me", command=self.talk)
        m.add_command(label="👀 Look at my screen", command=self.look_at_screen)
        self.glance_idx = m.index("end") + 1
        m.add_command(label="glance", command=self.toggle_glance)
        m.add_command(label="🛠 Do a task for me…", command=self.ask_task)
        m.add_command(label="💞 What you remember", command=self.show_memory)
        self.voiceear_idx = m.index("end") + 1
        m.add_command(label="ears", command=self.toggle_voice)
        self.shell_idx = m.index("end") + 1
        m.add_command(label="shell", command=self.toggle_task_shell)
        self.intent_idx = m.index("end") + 1
        m.add_command(label="brainlocal", command=self.toggle_local_intent)
        m.add_command(label="🎀 Pet / Play", command=self.play)
        m.add_command(label="🍰 Feed", command=self.feed)
        m.add_separator()

        music = tk.Menu(m, tearoff=0)
        music.add_command(label="⏯  Play / Pause", command=lambda: self.media("play"))
        music.add_command(label="⏭  Next track", command=lambda: self.media("next"))
        music.add_command(label="⏮  Previous track", command=lambda: self.media("prev"))
        music.add_separator()
        music.add_command(label="🔊  Volume up", command=lambda: self.media("vup"))
        music.add_command(label="🔉  Volume down", command=lambda: self.media("vdown"))
        music.add_command(label="🔇  Mute audio", command=lambda: self.media("mute"))
        music.add_separator()
        music.add_command(label="🎵  Play lo-fi (browser)", command=self.play_lofi)
        music.add_command(label="💃  Dance party (toggle)", command=self.toggle_dance)
        music.add_separator()
        music.add_command(label="🟢  Connect Spotify…", command=self.connect_spotify)
        music.add_command(label="🟢  Now playing", command=self.spotify_now)
        music.add_command(label="🟢  Play playlist…", command=self.play_playlist_dialog)
        music.add_command(label="🟢  Play a song…", command=self.play_song_dialog)
        music.add_command(label="🎛  Mini player (skip/pause)", command=self.open_player)
        m.add_cascade(label="🎶 Music", menu=music)

        m.add_command(label="📝 Remind me…", command=self.add_reminder)
        m.add_command(label="📋 My reminders", command=self.show_reminders)
        m.add_separator()

        emo = tk.Menu(m, tearoff=0)
        for e in EMOTIONS:
            emo.add_command(label=e.replace("_", " "),
                            command=lambda x=e: self.show_emote(x, 150))
        m.add_cascade(label="😶 Emotions", menu=emo)

        size = tk.Menu(m, tearoff=0)
        for label, f in [("Tiny (50%)", 0.5), ("Small (75%)", 0.75),
                         ("Normal (100%)", 1.0), ("Large (130%)", 1.3),
                         ("Huge (170%)", 1.7), ("Giant (220%)", 2.2)]:
            size.add_command(label=label, command=lambda x=f: self.set_scale(x))
        size.add_separator()
        size.add_command(label="➖  Smaller", command=lambda: self.set_scale(self.scale - 0.15))
        size.add_command(label="➕  Bigger", command=lambda: self.set_scale(self.scale + 0.15))
        size.add_command(label="✏  Custom %…", command=self.set_scale_dialog)
        m.add_cascade(label="📏 Size", menu=size)
        m.add_separator()

        self.mood_idx = m.index("end") + 1
        m.add_command(label="mood", state="disabled")
        m.add_command(label="hunger", state="disabled")
        m.add_separator()
        voices = tk.Menu(m, tearoff=0)
        self.miku_voice_idx = 0
        voices.add_command(label="miku", command=self.toggle_miku)
        pitch = tk.Menu(voices, tearoff=0)
        for label, semi in [("Natural (0)", 0), ("A little higher (+4)", 4),
                            ("Higher (+7)", 7), ("Cute/high (+10)", 10),
                            ("Very high (+12)", 12)]:
            pitch.add_command(label=label, command=lambda s=semi: self.set_miku_pitch(s))
        voices.add_cascade(label="🎚 Miku pitch", menu=pitch)
        voices.add_separator()
        for label, vid in Voice.VOICES.items():
            voices.add_command(label=label, command=lambda v=vid: self.pick_voice(v))
        self.voices_menu = voices
        m.add_cascade(label="🎙 Voice", menu=voices)
        self.mute_idx = m.index("end") + 1
        m.add_command(label="🔈 Mute voice", command=self.toggle_mute)
        m.add_command(label="😴 Nap / Wake", command=self.toggle_sleep)
        self.mode_idx = m.index("end") + 1
        m.add_command(label="mode", command=self.toggle_mode)
        self.brain_idx = m.index("end") + 1
        m.add_command(label="brain", command=self.toggle_brain)
        m.add_command(label="🔑 Set Gemini API key", command=self.set_gemini_key)
        self.autostart_idx = m.index("end") + 1
        m.add_command(label="autostart", command=self.toggle_autostart)
        m.add_separator()
        m.add_command(label="❌ Quit", command=self.quit)
        self.menu = m

    def show_menu(self, event):
        self.menu.entryconfigure(self.mood_idx, label=f"💛 Happy: {int(self.happiness)}%")
        self.menu.entryconfigure(self.mood_idx + 1, label=f"🍽 Hunger: {int(self.hunger)}%")
        self.menu.entryconfigure(self.mute_idx,
                                 label=("🔇 Unmute voice" if self.voice.muted else "🔈 Mute voice"))
        self.menu.entryconfigure(self.mode_idx,
                                 label=("🚶 Walk mode" if self.mode == "portrait"
                                        else "🖼 Portrait mode (big face)"))
        if self.brain.has_gemini():
            blabel = f"🧠 Brain: Gemini ({self.brain.GEMINI_MODEL}) — cloud"
        elif self.brain.ollama_ready() and self.brain._has_model(self.brain.CHAT_MODEL_LOCAL):
            blabel = "🧠 Brain: Local (gemma3) — offline"
        else:
            blabel = "🧠 Brain: no brain — set a Gemini key or start Ollama"
        self.menu.entryconfigure(self.brain_idx, label=blabel)
        self.voices_menu.entryconfigure(
            self.miku_voice_idx,
            label=("♪ Miku voice: ON (real RVC)" if self.voice.miku
                   else "♪ Miku voice: off"))
        listening = self.voice_proc is not None and self.voice_proc.poll() is None
        self.menu.entryconfigure(
            self.voiceear_idx,
            label=("🎤 Wake word: ON (say 'Marcille')" if listening
                   else "🎤 Wake word: off"))
        self.menu.entryconfigure(
            self.shell_idx,
            label=("🐚 Task shell: ON (can run commands)" if self.allow_shell
                   else "🐚 Task shell: off (safe)"))
        self.menu.entryconfigure(
            self.intent_idx,
            label=("⚡ Quick brain (Gemma): ON" if self.cfg.get("local_intent", True)
                   else "⚡ Quick brain (Gemma): off"))
        self.menu.entryconfigure(
            self.glance_idx,
            label=("👁 Auto-glance: ON (peeks at screen)" if self.cfg.get("auto_glance", True)
                   else "👁 Auto-glance: off"))
        on = os.path.exists(startup_bat_path())
        self.menu.entryconfigure(self.autostart_idx,
                                 label=("✅ Start with Windows" if on else "▶ Start with Windows"))
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

    # ---- actions ----------------------------------------------------------
    def greet(self):
        # memory-aware hello (uses your name + how long you've been gone)
        self.greet_returning()

    def talk(self):
        self.show_emote(random.choice(["idea", "happy", "embarrassed", "surprised"]), 50)
        self.say_bubble(pick("idle"), force=True)

    # ---- vision: she looks at your screen (LOCAL gemma3:4b, offline) --------
    def look_at_screen(self, proactive=False):
        if not self.brain.ollama_ready() or not self.brain._has_model(self.brain.VISION_MODEL):
            if not proactive:
                self.show_emote("sad", 40)
                self.say_bubble("I need Ollama running with gemma3:4b to see your screen.",
                                force=True)
            return
        if getattr(self, "_looking", False):
            return
        self._looking = True
        if not proactive:                       # manual look announces itself
            self.show_emote("idea", 40)
            self.say_bubble("Let me take a look at what you're up to...", force=True)
        threading.Thread(target=self._look_worker, daemon=True).start()

    def maybe_glance(self):
        """Proactive peek: every few minutes she quietly looks at your screen and
        comments unprompted — only when you're around and she's free. Toggle in menu."""
        if not self.cfg.get("auto_glance", True):
            return
        if (getattr(self, "_looking", False) or self._task_busy or self.away
                or self.music_mode or self.state not in ("idle", "move")
                or self.bubble_t > 0):
            return
        if not (self.brain.ollama_ready() and self.brain._has_model(self.brain.VISION_MODEL)):
            return
        self.look_at_screen(proactive=True)

    def _look_worker(self):
        path = os.path.join(HERE, ".marc_screen.png")
        try:
            from PIL import ImageGrab
            img = ImageGrab.grab()              # full screen
            w, h = img.size
            if w > 768:                         # downscale to keep it light & fast
                img = img.resize((768, max(1, int(h * 768 / w))), Image.LANCZOS)
            img.convert("RGB").save(path)
        except Exception:
            self.root.after(0, lambda: self._look_done(
                None, "I couldn't get a look at your screen, sorry!"))
            return
        reply, err = self.brain.see_screen(path)
        try:
            os.remove(path)
        except OSError:
            pass
        self.root.after(0, lambda: self._look_done(reply, err))

    def _look_done(self, reply, err):
        self._looking = False
        if reply:
            self.last_seen = reply          # feed screen view into living dialogue
            self.show_emote(emote_for(reply), 80)
            self.say_bubble(reply, force=True)
        else:
            self.show_emote("sad", 40)
            self.say_bubble(err or "Hmm, I couldn't see anything.", force=True)

    # ---- relationship / long-term memory ----------------------------------
    def _sync_memory(self):
        """Push the latest name/facts/bond into Marcille's persona so every reply
        is colored by what she remembers."""
        try:
            self.brain.persona_extra = self.memory.summary_for_prompt()
        except Exception:
            pass

    NAME_PATS = [r"\bmy name is ([a-z][a-z '\-]{1,30})",
                 r"\bcall me ([a-z][a-z '\-]{1,30})",
                 r"\bi am ([a-z][a-z '\-]{1,30})", r"\bi'm ([a-z][a-z '\-]{1,30})"]

    def learn_from_text(self, text):
        """Pick durable facts out of what you say — your name, or anything you
        explicitly ask her to remember — and store it forever."""
        import re
        t = (text or "").strip()
        if not t:
            return False
        low = t.lower()
        # explicit: "remember that I ..." / "remember I ..."
        m = re.search(r"\bremember (?:that )?(.+)", low)
        if m:
            fact = m.group(1).strip().rstrip(".!?")
            if len(fact) > 3 and self.memory.add_fact(fact):
                self.show_emote("aha", 50)
                self.say_bubble("Noted — I'll remember that.", force=True)
                self._sync_memory()
                return True
        # name capture (only if we don't know it yet, avoid false hits)
        if not self.memory.name and len(low) < 40:
            for p in self.NAME_PATS:
                m = re.search(p, low)
                if m:
                    nm = m.group(1).strip().title()
                    if nm.lower() not in ("not", "sorry", "so", "just", "going", "trying"):
                        self.memory.name = nm
                        self.memory.save()
                        self._sync_memory()
                        self.show_emote("happy", 50)
                        self.say_bubble(f"Nice to meet you, {nm}. I'll remember that.",
                                        force=True)
                        return True
        return False

    def toggle_glance(self):
        new = not self.cfg.get("auto_glance", True)
        self.cfg["auto_glance"] = new
        save_config(self.cfg)
        if new:
            self.glance_cd = random.randint(3000, 6000)
            self.show_emote("idea", 40)
            self.say_bubble("I'll keep an eye on what you're up to~", force=True)
        else:
            self.show_emote("normal", 30)
            self.say_bubble("Alright, I won't peek at your screen anymore.", force=True)

    def show_memory(self):
        """Show what Marcille remembers about you."""
        mem = self.memory
        nm = mem.name or "(not set yet — tell me \"my name is ...\")"
        lines = ["Here's what I've got on file for you:",
                 f"• Name: {nm}",
                 f"• Known you {mem.days_known()} day(s), across {mem.sessions} session(s)."]
        if mem.facts:
            lines.append("• Preferences / notes:")
            lines += [f"   – {f}" for f in mem.facts[-15:]]
        else:
            lines.append("• Nothing noted yet. Say \"remember that ...\" and I'll keep it.")
        self.show_emote("aha", 60)
        try:
            from tkinter import messagebox
            messagebox.showinfo("🗒 What Marcille remembers", "\n".join(lines),
                                parent=self.root)
        except Exception:
            self.say_bubble(f"On file: your name is {nm}, with {len(mem.facts)} note(s).",
                            force=True)

    def greet_returning(self):
        """A brief, assistant-style hello when she wakes up — uses your name."""
        self._greeted_return = True
        nm = (" " + self.memory.name) if self.memory.name else ""
        days = self.memory.days_away()
        if self.memory.sessions <= 1:
            self.show_emote("shy", 70)
            line = "Marcille, at your service. Tell me your name and what you need."
        elif days >= 2:
            self.show_emote("surprised", 60)
            line = f"Welcome back{nm} — it's been a few days. What can I do for you?"
        else:
            self.show_emote("happy", 60)
            line = f"Welcome back{nm}. Ready when you are."
        self.say_bubble(line, force=True)

    # ---- living dialogue (dynamic, context-aware idle lines) ---------------
    def build_context(self):
        """Human-readable snapshot of the current situation + signature key."""
        now = datetime.datetime.now()
        hour = now.hour
        part = ("the middle of the night" if hour >= 23 or hour < 5 else
                "early morning" if hour < 8 else "morning" if hour < 12 else
                "afternoon" if hour < 17 else "evening" if hour < 21 else "night")
        mins = int((time.time() - self.start_time) / 60)
        mood = ("grumpy/neglected" if self.hunger < 30 else
                "content" if self.happiness > 60 else "a bit bored")
        name, title = foreground_app()
        cat = categorize_app(name, title) or "something"
        ctx = (f"- Time: {now.strftime('%A %H:%M')} ({part}); date {now.strftime('%b %d, %Y')}\n"
               f"- User has had the companion open ~{mins} min this session\n"
               f"- Focused app category: {cat}\n"
               f"- Marcille's mood: {mood} (hunger {int(self.hunger)}, happiness "
               f"{int(self.happiness)})\n")
        if self.memory.name:
            ctx += f"- The user's name is {self.memory.name}\n"
        if self.memory.facts:
            ctx += "- You remember: " + "; ".join(self.memory.facts[-5:]) + "\n"
        if self.last_seen:
            ctx += f"- Last thing Marcille saw on screen: {self.last_seen}\n"
        key = f"{part}|{cat}|{mood}"      # regenerate when any of these shift
        return ctx, key

    def maybe_refresh_pool(self):
        """Kick off a background line generation when the pool is low or context shifted."""
        if self.pool_busy or not self.brain._has_model(self.brain.CHAT_MODEL_LOCAL):
            return
        _, key = self.build_context()
        if len(self.line_pool) >= 3 and key == self.pool_key:
            return
        self.pool_busy = True
        ctx, key = self.build_context()
        self.pool_key = key
        threading.Thread(target=self._refresh_pool_worker, args=(ctx,), daemon=True).start()

    def _refresh_pool_worker(self, ctx):
        lines = self.brain.generate_lines(ctx)
        def done():
            if lines:
                self.line_pool = lines
            self.pool_busy = False
        self.root.after(0, done)

    def next_idle_line(self):
        """A fresh line from the pool, avoiding recent repeats; static fallback."""
        pool = [l for l in self.line_pool if l not in self.recent_lines]
        if pool:
            line = random.choice(pool)
            self.line_pool.remove(line)
        else:
            choices = [l for l in LINES["idle"] if l not in self.recent_lines] or LINES["idle"]
            line = random.choice(choices)
        self.recent_lines.append(line)
        self.recent_lines = self.recent_lines[-8:]
        return line

    # ---- task helper (she actually does simple tasks, FREE) ---------------
    def ask_task(self):
        if not self.brain.ollama_ready():
            self.show_emote("sad", 40)
            self.say_bubble("I need Ollama running to do tasks for you.", force=True)
            return
        if self._task_busy:
            self.say_bubble("I'm already on a task, hold on!", force=True)
            return
        task = simpledialog.askstring(
            "Ask Marcille to do something",
            "What should I do for you?\n\n"
            "e.g.  make a to-do list on my Desktop\n"
            "      search the web for the weather tomorrow\n"
            "      what's an 18% tip on 64 dollars",
            parent=self.root)
        if not task or not task.strip():
            return
        task = task.strip()
        # "open / launch X" works without shell — handle it directly in Python
        if self.try_open(task):
            return
        self._task_busy = True
        self.show_emote("casting", 50)
        self.say_bubble("On it! Give me a moment...", force=True)
        threading.Thread(target=self._task_worker, args=(task,), daemon=True).start()

    OPEN_APPS = {
        "notepad": "notepad", "note pad": "notepad",
        "calculator": "calc", "calc": "calc",
        "paint": "mspaint", "mspaint": "mspaint",
        "file explorer": "explorer", "explorer": "explorer", "files": "explorer",
        "command prompt": "cmd", "cmd": "cmd", "terminal": "wt", "powershell": "powershell",
        "task manager": "taskmgr", "settings": "ms-settings:", "calendar": "outlookcal:",
        "camera": "microsoft.windows.camera:", "snipping tool": "ms-screenclip:",
        "spotify": "Spotify.exe", "discord": "discord",
        "chrome": "chrome", "edge": "msedge", "firefox": "firefox",
        "word": "winword", "excel": "excel", "powerpoint": "powerpnt",
    }

    def _launch(self, exe):
        """Robustly launch an app/exe/URI by name on Windows. os.startfile uses
        ShellExecute, which finds chrome/spotify/etc. via the App Paths registry
        (plain subprocess.Popen does NOT and fails for those)."""
        if exe.endswith(":"):                  # URI scheme, e.g. ms-settings:
            os.startfile(exe)
            return
        if exe in ("cmd", "powershell", "wt"):  # need their own console window
            subprocess.Popen(exe)
            return
        try:
            os.startfile(exe)                  # ShellExecute: App Paths + PATH + assoc
        except Exception:
            subprocess.Popen(exe)              # last resort for bare exes on PATH

    def take_note(self, content):
        """Write a quick note to the Desktop and open it — instant, no Claude Code.
        Returns a short in-character confirmation line."""
        content = (content or "").strip()
        # Gemma sometimes echoes a command instead of content; treat that as 'blank'
        if not content or content.lower() in ("open notepad", "note", "a note", "notepad"):
            self._launch("notepad")
            return "Here's a fresh notepad — tell me what to write!"
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        if not os.path.isdir(desktop):
            desktop = os.path.expanduser("~")
        stamp = datetime.datetime.now().strftime("%Y-%m-%d %H%M%S")
        path = os.path.join(desktop, f"Marcille note {stamp}.txt")
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content + "\n")
            os.startfile(path)
            return "Done — I jotted that down on your Desktop!"
        except Exception:
            return "I tried to write that down but couldn't save the file, sorry!"

    def try_open(self, task, speak=True):
        """If `task` is an open/launch/start request, actually launch it (no shell
        needed). Returns True if handled (when speak=False, returns 'ok'/'fail'/None
        so a tool-caller can decide what to say)."""
        t = task.lower().strip()
        verb = next((v for v in ("open ", "launch ", "start ", "bring up ", "run ")
                     if t.startswith(v)), None)
        if not verb:
            return None if not speak else False
        target = task[len(verb):].strip().strip(".!?").strip()
        if not target:
            return None if not speak else False
        if self._open_target(target):
            if speak:
                self.show_emote("happy", 50)
                self.say_bubble(f"There you go — {target} is open!", force=True)
            return "ok" if not speak else True
        if speak:
            self.show_emote("clumsy", 50)
            self.say_bubble(f"I tried, but I couldn't open {target}... is it installed?",
                            force=True)
        return "fail" if not speak else True

    def _open_target(self, target):
        """Launch an app/site by name (no UI). Returns True on success."""
        low = target.lower()
        try:
            if low in self.OPEN_APPS:                      # known app
                self._launch(self.OPEN_APPS[low])
            elif low.startswith("http") or ("." in low and " " not in low):  # website
                url = target if low.startswith("http") else "https://" + target
                webbrowser.open(url)
            else:                                          # try as a program name
                self._launch(target)
            return True
        except Exception:
            return False

    def _task_worker(self, task):
        reply, err = self.brain.do_task(task, allow_shell=self.allow_shell)
        self.root.after(0, lambda: self._task_done(reply, err))

    def _task_done(self, reply, err):
        self._task_busy = False
        if reply:
            self.show_emote(emote_for(reply), 90)
            self.say_bubble(reply, force=True)
        else:
            self.show_emote("panic", 40)
            self.say_bubble(err or "I couldn't manage that one, sorry!", force=True)

    def toggle_task_shell(self):
        self.allow_shell = not self.allow_shell
        self.cfg["task_shell"] = self.allow_shell
        save_config(self.cfg)
        if self.allow_shell:
            self.show_emote("surprised", 40)
            self.say_bubble("Shell powers ON — I can run commands now. Be careful what you ask!",
                            force=True)
        else:
            self.show_emote("normal", 30)
            self.say_bubble("Shell powers off. Safer this way.", force=True)

    def toggle_local_intent(self):
        new = not self.cfg.get("local_intent", True)
        self.cfg["local_intent"] = new
        save_config(self.cfg)
        if new:
            if self.brain.ollama_ready():
                self.show_emote("idea", 40)
                self.say_bubble("Quick brain on — I'll understand your commands faster now.",
                                force=True)
            else:
                self.show_emote("thinking", 40)
                self.say_bubble("Quick brain on, but I can't find Ollama running. "
                                "Start Ollama and pull gemma3:4b.", force=True)
        else:
            self.show_emote("normal", 30)
            self.say_bubble("Quick brain off — I'll think things through the slow way.",
                            force=True)

    # ---- voice input: she listens for the wake word "Marcille" -------------
    def start_voice(self):
        if not os.path.exists(RVC_PY) or not os.path.exists(VOICE_LISTEN):
            self.root.after(0, lambda: self.say_bubble(
                "My ears aren't set up yet, sorry!", force=True))
            return
        if self.voice_proc and self.voice_proc.poll() is None:
            return
        try:
            venv = dict(os.environ)
            # STT engine via cfg["voice_stt"]: "whisper" = local distil-large-v3 on the
            # GPU (free, UNLIMITED, offline, ~3.7s, English); "gemini" = cloud (accurate,
            # multilingual, but a tiny daily free quota). Default to local whisper.
            venv["MARC_STT"] = self.cfg.get("voice_stt", "whisper")
            self.voice_proc = subprocess.Popen(
                [RVC_PY, VOICE_LISTEN],
                stdout=subprocess.PIPE,
                stderr=open(os.path.join(HERE, "voice_listen.log"), "w"),
                text=True, cwd=HERE, env=venv,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except Exception:
            self.voice_proc = None
            return
        threading.Thread(target=self._voice_reader, args=(self.voice_proc,),
                         daemon=True).start()

    def _voice_reader(self, proc):
        announced = False
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            if line == "READY":
                self.voice_listening = True
                if not announced:
                    announced = True
                    self.root.after(0, lambda: self.say_bubble(
                        "I'm listening for you now — just call my name~", force=True))
            elif line == "WAKE":
                self.root.after(0, self._voice_wake)
            elif line == "NOCMD":
                self.root.after(0, self._voice_nocmd)
            elif line.startswith("CMD:"):
                txt = line[4:].strip()
                self.root.after(0, lambda t=txt: self.handle_voice_command(t))
            elif line.startswith("AUDIO:"):
                path = line[6:].strip()
                self.root.after(0, lambda: self.show_user_caption(
                    "transcribing…", live=True, hold=8.0))
                threading.Thread(target=self._transcribe_voice,
                                 args=(path,), daemon=True).start()
            elif line.startswith("ERR"):
                self.voice_listening = False
                self.root.after(0, lambda: self.say_bubble(
                    "I can't hear — is your microphone working?", force=True))
        # stdout closed -> listener died. Auto-restart if we still want to listen.
        self.voice_listening = False
        if self.cfg.get("voice_input") and self.voice_proc is proc:
            self.voice_proc = None
            self.root.after(3000, lambda: threading.Thread(
                target=self.start_voice, daemon=True).start())

    def _voice_wake(self):
        # heard the wake word -> she is now RECORDING your command. Clear visual cue.
        self.show_emote("surprised", 60)
        self.say_bubble(random.choice(["Yes? I'm listening!", "Mm-hm?", "What is it?",
                                       "You called? Go ahead!"]), force=True)
        self.show_user_caption("listening…", live=True, hold=6.0)

    def _voice_nocmd(self):
        # woke up but the command didn't transcribe -> tell the user (don't go silent)
        self.show_emote("thinking", 40)
        self.say_bubble(random.choice([
            "Hmm, I didn't catch that — say it again?",
            "Sorry, I didn't hear that clearly. Once more?",
            "I'm listening, but I missed it — try again!"]), force=True)

    def _transcribe_voice(self, path):
        """Worker: send a recorded command clip to Gemini STT, then act on the text.
        Runs off the reader thread (it's a network call). Cleans up the temp wav."""
        text = None
        try:
            text = self.brain.transcribe_audio(path)
        except Exception:
            text = None
        try:
            os.remove(path)
        except Exception:
            pass
        if text:
            self.root.after(0, lambda t=text: self.handle_voice_command(t))
        else:
            self.root.after(0, self._voice_nocmd)

    # ---- fast deterministic skills (instant, reliable: the "assistant" core) ---
    # These run BEFORE the LLM so common requests are snappy and never misjudged.
    # Returns a spoken reply string if handled, else None. Called from worker
    # threads, so all Tk work is marshalled back via root.after.
    def quick_skill(self, text):
        import re
        t = (text or "").lower().strip(" ?.!")
        if not t:
            return None

        # --- time ---
        if t in ("time", "what time is it", "whats the time", "what's the time",
                 "the time", "got the time") or re.search(
                r"\b(what'?s|what is|tell me|do you have|got)\b.*\btime\b", t):
            now = datetime.datetime.now()
            self._skill_emote("happy")
            return "It's " + now.strftime("%I:%M %p").lstrip("0") + " right now."

        # --- date / day ---
        if re.search(r"\b(what'?s|what is|tell me|today'?s)\b.*\b(date|day)\b", t) or \
                t in ("date", "what day is it", "what's the date", "whats the date"):
            now = datetime.datetime.now()
            self._skill_emote("aha")
            return ("Today is " + now.strftime("%A, %B ") + str(now.day) + ", "
                    + now.strftime("%Y") + ".")

        # --- coin flip ---
        if re.search(r"\b(flip|toss)\b.*\bcoin\b", t):
            self._skill_emote("surprised")
            return "It's " + random.choice(["heads", "tails"]) + "!"

        # --- dice ---
        m = re.search(r"\broll\s+(?:a\s+|(\d+)\s+)?(dice|die|d6)", t)
        if m:
            n = max(1, min(int(m.group(1)) if m.group(1) else 1, 5))
            rolls = [random.randint(1, 6) for _ in range(n)]
            self._skill_emote("surprised")
            return ("You rolled " + " and ".join(map(str, rolls))
                    + ((" — total " + str(sum(rolls))) if n > 1 else "") + "!")

        # --- lock screen ---
        if re.search(r"\block\b.*\b(screen|computer|pc|workstation)\b", t) or t == "lock":
            self._skill_emote("casting")
            self.root.after(400, lambda: ctypes.windll.user32.LockWorkStation())
            return "Locking up — see you in a moment!"

        # --- screenshot ---
        if re.search(r"\b(take|grab|capture|get)\b.*\bscreenshot\b", t) or \
                t in ("screenshot", "screen shot"):
            self.root.after(0, self._skill_screenshot)
            self._skill_emote("casting")
            return "Got it — screenshot saved to your Desktop!"

        # --- timer ---
        m = re.search(r"timer\s+(?:for\s+)?(\d+)\s*(hour|hr|minute|min|second|sec)", t)
        if m:
            n, unit = int(m.group(1)), m.group(2)
            per = 3600 if unit.startswith(("hour", "hr")) else (
                1 if unit.startswith("sec") else 60)
            word = {"hour": "hour", "hr": "hour", "minute": "minute",
                    "min": "minute", "second": "second", "sec": "second"}[unit]
            self.root.after(0, lambda s=n * per: self._add_timer(s))
            self._skill_emote("idea")
            return "Timer set for %d %s%s — I'll let you know!" % (
                n, word, "" if n == 1 else "s")

        # --- math ---
        ans = self._try_math(t)
        if ans is not None:
            self._skill_emote("aha")
            return ans

        # --- unit / currency conversion ---
        conv = self._try_convert(t)
        if conv is not None:
            self._skill_emote("aha")
            return conv

        # --- weather (network) ---
        if "weather" in t or "forecast" in t or "temperature outside" in t:
            loc = ""
            mm = re.search(r"(?:weather|forecast)\s+(?:in|for|at|near)\s+([a-z\s]+)", t)
            if mm:
                loc = mm.group(1).strip()
            self._skill_emote("thinking")
            return self._weather(loc)

        return None

    def _skill_emote(self, emo):
        self.root.after(0, lambda: self.show_emote(emo, 50))

    def _skill_screenshot(self):
        try:
            from PIL import ImageGrab
            path = os.path.join(self.brain._desktop_dir(),
                "screenshot " + datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + ".png")
            ImageGrab.grab().save(path)
        except Exception:
            pass

    def _add_timer(self, secs, label="Timer"):
        due = datetime.datetime.now() + datetime.timedelta(seconds=secs)
        self.tasks.append({"text": label + " finished!",
                           "due": due.isoformat(timespec="seconds"), "notified": False})
        save_tasks(self.tasks)

    @staticmethod
    def _fmt_num(v):
        if isinstance(v, float) and v.is_integer():
            v = int(v)
        if isinstance(v, float):
            return ("%.4f" % v).rstrip("0").rstrip(".")
        return str(v)

    def _try_math(self, t):
        import re
        # "18% of 240" / "18 percent of 240"
        m = re.search(r"(\d+(?:\.\d+)?)\s*(?:%|percent)\s*of\s*(\d+(?:\.\d+)?)", t)
        if m:
            return self._fmt_num(float(m.group(1)) / 100.0 * float(m.group(2))) + "."
        s = t
        for k, v in ((" plus ", "+"), (" minus ", "-"), (" times ", "*"),
                     (" multiplied by ", "*"), (" divided by ", "/"),
                     (" over ", "/"), (" x ", "*")):
            s = s.replace(k, v)
        s = re.sub(r"^(what'?s|what is|whats|calculate|compute|how much is)\s+",
                   "", s).strip()
        if re.fullmatch(r"[\d\s.\+\-\*/()%]+", s) and re.search(r"[\+\-\*/]", s):
            try:
                return self._fmt_num(eval(s, {"__builtins__": {}}, {})) + "."
            except Exception:
                return None
        return None

    def _try_convert(self, t):
        import re, urllib.request, json
        # currency: "20 usd to thb"
        m = re.search(r"(\d+(?:\.\d+)?)\s*([a-z]{3})\s+(?:to|in|into)\s+([a-z]{3})\b", t)
        if m and m.group(2) != m.group(3):
            amt, src, dst = float(m.group(1)), m.group(2).upper(), m.group(3).upper()
            try:
                url = "https://open.er-api.com/v6/latest/" + src
                j = json.loads(urllib.request.urlopen(url, timeout=12).read())
                rate = (j.get("rates") or {}).get(dst)
                if rate:
                    return "%s %s is about %s %s." % (
                        self._fmt_num(amt), src,
                        self._fmt_num(round(amt * rate, 2)), dst)
            except Exception:
                pass
            return None
        # units (local table)
        alias = {"kilometers": "km", "kilometres": "km", "kilometre": "km",
                 "kilometer": "km", "mile": "miles", "kilograms": "kg", "kilogram": "kg",
                 "kilo": "kg", "kilos": "kg", "pounds": "lbs", "pound": "lbs", "lb": "lbs",
                 "meters": "m", "metres": "m", "metre": "m", "meter": "m", "foot": "feet",
                 "ft": "feet", "centimeters": "cm", "centimetres": "cm", "inch": "inches",
                 "celsius": "c", "centigrade": "c", "fahrenheit": "f"}
        factor = {("km", "miles"): 0.621371, ("miles", "km"): 1.60934,
                  ("kg", "lbs"): 2.20462, ("lbs", "kg"): 0.453592,
                  ("m", "feet"): 3.28084, ("feet", "m"): 0.3048,
                  ("cm", "inches"): 0.393701, ("inches", "cm"): 2.54}
        m = re.search(r"(\d+(?:\.\d+)?)\s*([a-z]+)\s+(?:to|in|into)\s+([a-z]+)", t)
        if m:
            amt = float(m.group(1))
            a = alias.get(m.group(2), m.group(2))
            b = alias.get(m.group(3), m.group(3))
            if (a, b) == ("c", "f"):
                return self._fmt_num(amt * 9 / 5 + 32) + " degrees Fahrenheit."
            if (a, b) == ("f", "c"):
                return self._fmt_num((amt - 32) * 5 / 9) + " degrees Celsius."
            f = factor.get((a, b))
            if f:
                return "%s %s is about %s %s." % (
                    self._fmt_num(amt), a, self._fmt_num(round(amt * f, 2)), b)
        return None

    def _weather(self, loc):
        import urllib.request, urllib.parse
        try:
            q = urllib.parse.quote(loc) if loc else ""
            fmt = urllib.parse.quote("%C, %t (feels %f), humidity %h")
            url = "https://wttr.in/" + q + "?format=" + fmt + "&m"
            req = urllib.request.Request(url, headers={"User-Agent": "curl/8"})
            s = urllib.request.urlopen(req, timeout=12).read().decode("utf-8", "replace").strip()
            if s and "Unknown location" not in s and "<" not in s and len(s) < 140:
                where = (" in " + loc.title()) if loc else ""
                return "Right now%s it's %s." % (where, s)
        except Exception:
            pass
        return "I couldn't reach the weather service just now, sorry!"

    def handle_voice_command(self, text):
        text = (text or "").strip()
        if len(text) < 2:
            return
        # Show the user EXACTLY what she heard (accurate whisper transcript) in the
        # subtitle bar, so mis-hearings are obvious. Hold a beat before acting.
        self.show_emote("aha", 36)
        self.show_user_caption(text, live=False, hold=5.0)
        self.root.after(850, lambda t=text: self._dispatch_command(t))

    def _dispatch_command(self, text):
        # learn name / explicit "remember ..." facts (may answer on its own)
        if self.learn_from_text(text):
            return
        # Tier 1: instant pattern match ("open notepad", "open youtube.com")
        if self.try_open(text):
            return
        if self._task_busy:
            self.say_bubble("One thing at a time, please!", force=True)
            return
        # Tiers 1.5+2+3 need a skill/network/model -> off the main thread
        self._task_busy = True
        self.show_emote("thinking", 40)
        threading.Thread(target=self._route_worker, args=(text,), daemon=True).start()

    def _route_worker(self, text):
        """Tier 1.5: fast deterministic skill (time/math/weather/timer/...).
        Tier 2: Gemini decides + acts via function-calling (open/music/note/...).
        Offline fallback: the local Gemma intent path."""
        reply = self.quick_skill(text)
        if reply:
            self.root.after(0, lambda r=reply: self._skill_done(r))
            return
        if self.brain.has_gemini():
            out, err = self.brain.gemini_tools_chat(text, self._gemini_dispatch)
            if out and not err:
                self.root.after(0, lambda: self._voice_reply_done(out, None))
                return
            # Gemini failed (e.g. daily-quota 429) -> fall back to local gemma below
        intent = None
        if self.cfg.get("local_intent", True) and self.brain.ollama_ready():
            intent = self.brain.parse_intent(text, cpu=bool(self.cfg.get("miku")))
        self.root.after(0, lambda: self._do_intent(text, intent))

    def _skill_done(self, reply):
        self._task_busy = False
        self.say_bubble(reply, force=True)

    def _voice_reply_done(self, reply, err):
        self._task_busy = False
        if reply:
            self.show_emote(emote_for(reply), 80)
            self.say_bubble(reply, force=True)
        else:
            self.show_emote("thinking", 40)
            self.say_bubble(err or "Sorry, my mind went blank!", force=True)

    # ---- Gemini tool execution (Gemini calls these via function-calling) ------
    def _gemini_dispatch(self, name, args):
        """Run a Gemini tool call. Called from Brain's worker thread -> marshal the
        actual action onto the main (Tk) thread and wait for its result string."""
        box, ev = {}, threading.Event()

        def run():
            try:
                box["v"] = self._exec_tool(name, args)
            except Exception as e:
                box["v"] = f"error: {e}"
            finally:
                ev.set()
        self.root.after(0, run)
        ev.wait(timeout=20)
        return box.get("v", "(no result)")

    def _exec_tool(self, name, args):
        if name == "open_app":
            target = (args.get("name") or "").strip()
            if not target:
                return "No app name given."
            ok = self._open_target(target)
            return f"Opened {target}." if ok else f"Couldn't find {target} on this PC."
        if name == "control_music":
            return self._music_tool((args.get("action") or "").lower(), args.get("query"))
        if name == "set_timer":
            try:
                secs = int(args.get("seconds") or 0)
            except Exception:
                secs = 0
            if secs <= 0:
                return "Invalid timer duration."
            self._add_timer(secs)
            return f"Timer started for {secs} seconds."
        if name == "set_reminder":
            due = parse_when(self._normalize_when(args.get("when", "")))
            if not due:
                return "I couldn't understand that time."
            self.tasks.append({"text": (args.get("text") or "reminder").strip(),
                               "due": due.isoformat(timespec="seconds"),
                               "notified": False})
            save_tasks(self.tasks)
            return "Reminder set for " + due.strftime("%I:%M %p").lstrip("0") + "."
        if name == "take_note":
            self.take_note(args.get("content", ""))
            return "Note saved to your Desktop."
        return f"(unknown tool {name})"

    def _music_tool(self, action, query):
        sp = self.spotify
        conn = sp.sp is not None
        try:
            if action in ("play", "resume"):
                if query and conn:
                    return sp.play_track(query) or f"Playing {query}."
                if query and not conn:
                    webbrowser.open(LOFI_URL)
                    return "Opened music in your browser (connect Spotify for songs by name)."
                if conn:
                    return sp.resume() or "Resumed."
                tap_key(VK["play"]); return "Toggled playback."
            if action == "pause":
                return (sp.pause() or "Paused.") if conn else (tap_key(VK["play"]) or "Paused.")
            if action == "next":
                return (sp.skip() or "Skipped ahead.") if conn else (tap_key(VK["next"]) or "Skipped.")
            if action == "previous":
                return (sp.previous() or "Went back.") if conn else (tap_key(VK["prev"]) or "Back.")
            if action == "volume_up":
                tap_key(VK["vup"]); return "Volume up."
            if action == "volume_down":
                tap_key(VK["vdown"]); return "Volume down."
            if action == "mute":
                tap_key(VK["mute"]); return "Toggled mute."
        except Exception as e:
            return f"music error: {e}"
        return "Done."

    def _normalize_when(self, when):
        """Gemini says 'in 10 minutes'; parse_when wants 'in 10m'."""
        import re
        w = (when or "").lower().strip()
        m = re.match(r"in\s+(\d+)\s*(second|sec|minute|min|hour|hr)", w)
        if m:
            suf = ("s" if m.group(2).startswith("sec")
                   else "h" if m.group(2).startswith(("hour", "hr")) else "m")
            return "in " + m.group(1) + suf
        return when

    def _do_intent(self, text, intent):
        self._task_busy = False
        act = intent["action"] if intent else None
        target = (intent.get("target") if intent else "") or ""

        if act == "open" and target:
            if self.try_open("open " + target):
                return                                  # opened it
            # couldn't open -> treat as a task instead
            act = "task"

        if act == "music":
            self.music_intent(target)
            return

        if act == "note":
            self.show_emote("idea", 50)
            self.say_bubble(self.take_note(target), force=True)
            return

        if act == "chat":
            self._task_busy = True
            self.show_emote("thinking", 40)
            threading.Thread(target=self._chat_voice_worker, args=(text,),
                             daemon=True).start()
            return

        # act == "task" or no intent at all -> Tier 3: local brain does the work
        self._task_busy = True
        self.show_emote("casting", 50)
        threading.Thread(target=self._task_worker, args=(target or text,),
                         daemon=True).start()

    def music_intent(self, target):
        """Execute a parsed music command via Spotify if connected, else media keys."""
        t = (target or "").lower().strip()
        sp = self.spotify
        connected = sp.sp is not None
        if t in ("pause", "stop"):
            self._spotify_async(sp.pause) if connected else self.media("play")
        elif t in ("next", "skip", "forward"):
            self._spotify_async(sp.skip) if connected else self.media("next")
        elif t in ("previous", "prev", "back", "last"):
            self._spotify_async(sp.previous) if connected else self.media("prev")
        elif t in ("volume up", "louder", "turn it up", "volume", "turn up the volume"):
            self.media("vup")
        elif t in ("volume down", "quieter", "turn it down", "lower"):
            self.media("vdown")
        elif t in ("mute", "unmute", "silence"):
            self.media("mute")
        elif t in ("", "play", "resume", "unpause", "music", "spotify", "songs",
                   "song", "something", "anything", "some music"):
            self._spotify_async(sp.resume) if connected else self.play_lofi()
        else:                                           # a song/playlist name
            if connected:
                self._spotify_async(lambda: sp.play_track(target))
            else:
                self.say_bubble("Connect me to Spotify and I'll find that for you!",
                                force=True)
                self.play_lofi()

    def _chat_voice_worker(self, text):
        reply, err = self.brain.ask(text)
        self.root.after(0, lambda: self._task_done(reply, err))

    def stop_voice(self):
        self.voice_listening = False
        if self.voice_proc:
            try:
                self.voice_proc.kill()
            except Exception:
                pass
            self.voice_proc = None

    def toggle_voice(self):
        if self.voice_proc and self.voice_proc.poll() is None:
            self.stop_voice()
            self.cfg["voice_input"] = False
            save_config(self.cfg)
            self.show_emote("normal", 30)
            self.say_bubble("Okay, I'll stop listening.", force=True)
        else:
            self.cfg["voice_input"] = True
            save_config(self.cfg)
            self.show_emote("happy", 40)
            self.say_bubble("Warming up my ears... (a moment the first time)", force=True)
            threading.Thread(target=self.start_voice, daemon=True).start()

    # ---- chat (local) -----------------------------------------------------
    def open_chat(self):
        if self.chat_win is not None and self.chat_win.winfo_exists():
            self.chat_win.lift()
            self.chat_entry.focus_set()
            return
        if not self.brain.ready():
            self.show_emote("sad", 40)
            self.say_bubble("My brain's offline — set a Gemini API key (right-click menu) "
                            "or start Ollama with gemma3:4b so we can talk!", force=True)
            return

        win = tk.Toplevel(self.root)
        self.chat_win = win
        win.title("Chat with Marcille")
        win.attributes("-topmost", True)
        win.configure(bg="#1e2230")
        win.geometry("420x460")

        log = scrolledtext.ScrolledText(
            win, wrap="word", width=48, height=18, bg="#262b3d", fg="#eef0f6",
            insertbackground="#eef0f6", highlightthickness=0, bd=0,
            font=("Segoe UI", 10), state="disabled")
        log.pack(fill="both", expand=True, padx=10, pady=(10, 6))
        log.tag_config("you", foreground="#9ad0ff", font=("Segoe UI", 10, "bold"))
        log.tag_config("her", foreground="#ffd9a0", font=("Segoe UI", 10, "bold"))
        log.tag_config("sys", foreground="#8a90a6", font=("Segoe UI", 9, "italic"))
        self.chat_log = log

        row = tk.Frame(win, bg="#1e2230")
        row.pack(fill="x", padx=10, pady=(0, 10))
        entry = tk.Entry(row, bg="#2e3450", fg="#eef0f6", insertbackground="#eef0f6",
                         highlightthickness=1, highlightbackground="#5a4a8a",
                         relief="flat", font=("Segoe UI", 10))
        entry.pack(side="left", fill="x", expand=True, ipady=5)
        entry.bind("<Return>", lambda e: self._chat_send())
        entry.focus_set()
        self.chat_entry = entry
        tk.Button(row, text="Send", command=self._chat_send, relief="flat",
                  bg="#5a4a8a", fg="white", activebackground="#6c5aa6",
                  font=("Segoe UI", 10, "bold")).pack(side="left", padx=(8, 0))

        self._chat_add("her", "Marcille",
                       "Yes? What is it? Don't just stand there — talk to me!")
        self.voice.say("Yes? What is it? Don't just stand there, talk to me!", force=True)

    def _chat_add(self, tag, who, text):
        log = self.chat_log
        log.configure(state="normal")
        if tag == "sys":
            log.insert("end", text + "\n", "sys")
        else:
            log.insert("end", f"{who}: ", tag)
            log.insert("end", text + "\n\n")
        log.configure(state="disabled")
        log.see("end")

    def _chat_send(self):
        if self.chat_win is None or not self.chat_win.winfo_exists():
            return
        text = self.chat_entry.get().strip()
        if not text:
            return
        self.chat_entry.delete(0, "end")
        self._chat_add("you", "You", text)
        self.learn_from_text(text)       # quietly pick up name / facts
        self._chat_add("sys", "", "Marcille is thinking...")
        self.chat_entry.configure(state="disabled")
        self.show_emote("idea", 9999)
        # classify off the main thread so chat can ACT (open/music), not just talk
        threading.Thread(target=self._chat_route_worker, args=(text,), daemon=True).start()

    def _chat_route_worker(self, text):
        reply = self.quick_skill(text)
        if reply:
            self.root.after(0, lambda r=reply: self._chat_reply(r, None))
            return
        # instant, deterministic "open X" — actually launches it with NO Gemini/quota
        # needed (mirrors the voice path so chat never falsely refuses or 429s on this)
        if text.lower().lstrip().startswith(("open ", "launch ", "start ", "bring up ", "run ")):
            self.root.after(0, lambda: (self.try_open(text), self._chat_done_action("")))
            return
        if self.brain.has_gemini():
            out, err = self.brain.gemini_tools_chat(text, self._gemini_dispatch)
            if out and not err:
                self.root.after(0, lambda: self._chat_reply(out, None))
                return
            # Gemini failed (e.g. daily-quota 429) -> fall back to local gemma below
        intent = None
        if self.cfg.get("local_intent", True) and self.brain.ollama_ready():
            intent = self.brain.parse_intent(text, cpu=bool(self.cfg.get("miku")))
        self.root.after(0, lambda: self._chat_route(text, intent))

    def _chat_route(self, text, intent):
        act = intent["action"] if intent else None
        target = (intent.get("target") if intent else "") or ""

        # actionable in chat: open an app/site (so she doesn't falsely refuse)
        if act == "open" and target:
            if self.try_open("open " + target):
                self._chat_done_action(f"(opened {target})")
                return
            act = "task"
        # actionable in chat: control music via Spotify / media keys
        if act == "music":
            self.music_intent(target)
            self._chat_done_action("(on it — check your music!)")
            return
        # actionable in chat: jot down a note (instant, no Claude Code)
        if act == "note":
            note = self.take_note(target)
            self.show_emote("idea", 50)
            self._chat_reply(note, None)
            return

        # everything else: a real conversation, fully local (no Spotify tool-loop)
        tools = None
        system = None      # let the Brain add persona + memory

        def work():
            reply, err = self.brain.ask(text, tools=tools,
                                        dispatch=self._spotify_dispatch, system=system)
            self.root.after(0, lambda: self._chat_reply(reply, err))
        threading.Thread(target=work, daemon=True).start()

    def _chat_done_action(self, note):
        """Re-enable the chat box after an action ran (the action handler itself
        speaks the spoken result; this just logs a short note)."""
        if self.chat_win is None or not self.chat_win.winfo_exists():
            return
        self.chat_entry.configure(state="normal")
        self.chat_entry.focus_set()
        self._chat_add("sys", "", note)

    def _spotify_dispatch(self, name, inp):
        sp = self.spotify
        try:
            if name == "spotify_play_playlist":
                return sp.play_playlist(inp.get("name", ""))
            if name == "spotify_play_song":
                return sp.play_track(inp.get("query", ""))
            if name == "spotify_pause":
                return sp.pause()
            if name == "spotify_resume":
                return sp.resume()
            if name == "spotify_skip":
                return sp.skip()
            if name == "spotify_previous":
                return sp.previous()
            if name == "spotify_set_volume":
                return sp.set_volume(inp.get("percent", 50))
            if name == "spotify_now_playing":
                np = sp.now_playing()
                if not np:
                    return "Nothing is playing right now."
                state = "playing" if np["playing"] else "paused"
                return f"{state}: '{np['name']}' by {np['artist']}"
        except Exception as e:
            return f"error: {e}"
        return "unknown tool"

    # ---- Spotify menu actions --------------------------------------------
    def _spotify_async(self, fn, emote="casting"):
        self.set_state("casting", 200)

        def work():
            msg = fn()
            if msg:
                self.root.after(0, lambda: (self.show_emote(emote, 60),
                                            self.say_bubble(msg, force=True)))
        threading.Thread(target=work, daemon=True).start()

    def set_spotify_keys(self):
        cid = simpledialog.askstring(
            "Spotify Client ID",
            "Paste your Spotify app Client ID.\n"
            "Create a free app at developer.spotify.com/dashboard and add the\n"
            "Redirect URI:  http://127.0.0.1:8888/callback",
            parent=self.root, initialvalue=self.cfg.get("spotify_client_id", ""))
        if not cid:
            return
        sec = simpledialog.askstring(
            "Spotify Client Secret", "Paste your Spotify app Client Secret:",
            parent=self.root, show="*",
            initialvalue=self.cfg.get("spotify_client_secret", ""))
        if not sec:
            return
        self.cfg["spotify_client_id"] = cid.strip()
        self.cfg["spotify_client_secret"] = sec.strip()
        self.cfg.setdefault("spotify_redirect_uri", "http://127.0.0.1:8888/callback")
        save_config(self.cfg)
        self.spotify.sp = None

    def connect_spotify(self):
        if not self.spotify.configured():
            self.set_spotify_keys()
            if not self.spotify.configured():
                return
        self.say_bubble("Opening Spotify — authorize me in the browser!", force=True)

        def fn():
            err = self.spotify.connect()
            return err if err else "Connected to Spotify! Now you can boss me around."
        self._spotify_async(fn, "happy")

    def spotify_now(self):
        def fn():
            np = self.spotify.now_playing()
            if not np:
                return "Nothing's playing right now."
            verb = "Playing" if np["playing"] else "Paused"
            return f"{verb}: '{np['name']}' by {np['artist']}."
        self._spotify_async(fn)

    def play_playlist_dialog(self):
        q = simpledialog.askstring("Play playlist", "Which playlist?", parent=self.root)
        if q:
            self._spotify_async(lambda: self.spotify.play_playlist(q.strip()))

    def play_song_dialog(self):
        q = simpledialog.askstring("Play a song", "What song?", parent=self.root)
        if q:
            self._spotify_async(lambda: self.spotify.play_track(q.strip()))

    # ---- floating mini player --------------------------------------------
    def open_player(self):
        if self.player_win is not None and self.player_win.winfo_exists():
            self.player_win.lift()
            return
        if not self.spotify.configured():
            self.say_bubble("Connect me to Spotify first!", force=True)
            self.connect_spotify()
            return

        win = tk.Toplevel(self.root)
        self.player_win = win
        win.title("Marcille ♪")
        win.attributes("-topmost", True)
        win.resizable(False, False)
        win.configure(bg="#1e2230")

        self.player_lbl = tk.Label(win, text="♪ …", bg="#1e2230", fg="#ffd9a0",
                                   font=("Segoe UI", 9), width=36, anchor="w")
        self.player_lbl.pack(padx=10, pady=(8, 4))

        row = tk.Frame(win, bg="#1e2230")
        row.pack(padx=10, pady=(0, 10))

        def btn(txt, cmd):
            b = tk.Button(row, text=txt, command=cmd, width=3, relief="flat",
                          bg="#2e3450", fg="white", activebackground="#5a4a8a",
                          activeforeground="white", font=("Segoe UI Symbol", 13))
            b.pack(side="left", padx=3)
            return b

        btn("⏮", lambda: self._player_do(self.spotify.previous))
        btn("⏸", lambda: self._player_do(self.spotify.pause))
        btn("▶", lambda: self._player_do(self.spotify.resume))
        btn("⏭", lambda: self._player_do(self.spotify.skip))
        self._refresh_player()

    def _set_player_label(self, np):
        if self.player_win is None or not self.player_win.winfo_exists():
            return
        if not np:
            self.player_lbl.config(text="♪ nothing playing")
        else:
            icon = "▶" if np["playing"] else "⏸"
            txt = f"{icon} {np['name']} — {np['artist']}"
            self.player_lbl.config(text=txt[:42])

    def _player_do(self, fn):
        self.show_emote("casting", 25)

        def work():
            fn()
            time.sleep(0.4)                       # let Spotify update its state
            np = self.spotify.now_playing()
            self.root.after(0, lambda: self._set_player_label(np))
        threading.Thread(target=work, daemon=True).start()

    def _refresh_player(self):
        if self.player_win is None or not self.player_win.winfo_exists():
            return

        def work():
            np = self.spotify.now_playing()
            self.root.after(0, lambda: self._set_player_label(np))
        threading.Thread(target=work, daemon=True).start()
        self.player_win.after(5000, self._refresh_player)   # auto-refresh label

    def _chat_reply(self, reply, err):
        if self.chat_win is None or not self.chat_win.winfo_exists():
            self.emote_ovr_t = 0
            return
        self.chat_entry.configure(state="normal")
        self.chat_entry.focus_set()
        if err:
            self._chat_add("sys", "", err)
            self.show_emote("panic", 50)
            self.say_bubble(err, force=True)
            return
        self._chat_add("her", "Marcille", reply)
        self.show_emote(emote_for(reply), 70)
        self.say_bubble(reply, force=True, cooldown=0)

    def play(self):
        self.happiness = min(100, self.happiness + 18)
        self.set_state("happy", 50)
        self.heart_timer = 50
        self.show_emote(random.choice(["laughing", "embarrassed", "happy"]), 55)
        self.say_bubble(pick("play"), force=True)

    def feed(self):
        self.hunger = min(100, self.hunger + 35)
        self.happiness = min(100, self.happiness + 8)
        self.set_state("happy", 40)
        self.heart_timer = 40
        self.say_bubble(pick("feed"), force=True)

    def media(self, what):
        tap_key(VK[what])
        if what in ("play", "next", "prev"):
            self.music_mode = True
            self.set_state("casting", 120)
            self.say_bubble(pick("music"))

    def play_lofi(self):
        webbrowser.open(LOFI_URL)
        self.music_mode = True
        self.set_state("casting", 300)
        self.say_bubble(pick("music"), force=True)

    def toggle_dance(self):
        self.music_mode = not self.music_mode
        if self.music_mode:
            self.set_state("casting", 600)
            self.say_bubble(pick("dance"), force=True)
        else:
            self.set_state("idle", 60)

    def toggle_sleep(self):
        if self.state == "sleep":
            self.set_state("idle", 80)
            self.say_bubble(pick("wake"), force=True)
        else:
            self.set_state("sleep", 99999)
            self.say_bubble(pick("sleep"), force=True)

    def toggle_mute(self):
        self.voice.muted = not self.voice.muted

    def toggle_brain(self):
        # Reports her current brain (Gemini cloud, or local Ollama).
        if self.brain.has_gemini():
            self.show_emote("happy", 40)
            self.say_bubble(f"I'm thinking with Google Gemini now ({self.brain.GEMINI_MODEL}) "
                            "— much sharper! Skills still run locally and free.", force=True)
        elif self.brain.ollama_ready() and self.brain._has_model(self.brain.CHAT_MODEL_LOCAL):
            self.show_emote("normal", 40)
            self.say_bubble("Running on your own machine (gemma3) — offline and free. "
                            "Add a Gemini key to make me smarter!", force=True)
        else:
            self.show_emote("sad", 40)
            self.say_bubble("I've no brain right now — set a Gemini API key, or start "
                            "Ollama with gemma3:4b.", force=True)

    def set_gemini_key(self):
        cur = self.brain.gemini_key or ""
        key = simpledialog.askstring(
            "Gemini API key",
            "Paste your Google Gemini API key.\n"
            "Get one FREE at  aistudio.google.com/apikey\n"
            "(Leave blank to clear it and go back to the local brain.)",
            parent=self.root, initialvalue=cur)
        if key is None:
            return                                   # cancelled
        key = key.strip()
        self.brain.gemini_key = key or None
        self.cfg["gemini_key"] = key or None
        save_config(self.cfg)
        if not key:
            self.show_emote("normal", 40)
            self.say_bubble("Gemini key cleared — back to my local brain.", force=True)
            return
        # quick validation ping off the main thread
        self.show_emote("thinking", 60)
        self.say_bubble("Let me test that key...", force=True)

        def check():
            reply, err = self.brain._gemini(
                "Reply with exactly: ok", [{"role": "user", "text": "say ok"}],
                max_tokens=10, temp=0.0)
            if reply:
                self.root.after(0, lambda: (self.show_emote("happy", 50), self.say_bubble(
                    f"Gemini connected! I'm running on {self.brain.GEMINI_MODEL} now. ♪",
                    force=True)))
            else:
                self.root.after(0, lambda e=err: (self.show_emote("panic", 50), self.say_bubble(
                    f"That key didn't work — {e}. Check it at aistudio.google.com/apikey.",
                    force=True)))
        threading.Thread(target=check, daemon=True).start()

    def pick_voice(self, spec):
        voice, rate, pitch = spec
        self.voice.set_voice(voice, rate, pitch)
        self.voice.muted = False
        self.cfg["voice"] = [voice, rate, pitch]
        save_config(self.cfg)
        self.show_emote("happy", 40)
        self.say_bubble("How do I sound now? ♪", force=True)

    def toggle_miku(self):
        on = not self.voice.miku
        if on and not os.path.exists(RVC_PY):
            self.show_emote("panic", 40)
            self.say_bubble("My Miku voice isn't installed yet!", force=True)
            return
        self.voice.set_miku(on)
        self.cfg["miku"] = on
        save_config(self.cfg)
        self.voice.muted = False
        if on:
            self.show_emote("happy", 60)
            self.say_bubble("Switching to my real Miku voice~ ♪ "
                            "(the first line takes a few seconds to warm up)", force=True)
        else:
            self.show_emote("normal", 40)
            self.say_bubble("Okay, back to my normal voice.", force=True)

    def set_miku_pitch(self, semitones):
        self.cfg["miku_pitch"] = int(semitones)
        save_config(self.cfg)
        if self.voice.miku:
            self.voice.restart_rvc()      # reload model with the new pitch
            self.show_emote("happy", 50)
            self.say_bubble(f"Tuning my voice to {semitones:+d}~ ♪ (one moment)",
                            force=True)
        else:
            self.say_bubble("Saved. Turn on my Miku voice to hear it.", force=True)

    def toggle_mode(self):
        if not self.has_walk:
            self.say_bubble("I don't have walking legs loaded, sorry!", force=True)
            return
        self.mode = "walk" if self.mode == "portrait" else "portrait"
        self.anim_i = 0
        self.apply_mode()
        self.say_bubble("Off I go, then. Try to keep up." if self.mode == "walk"
                        else "There, now you can see my face properly.", force=True)

    def build_images(self):
        """(Re)build all Tk images from the source PIL frames at self.scale."""
        s = self.scale

        def scaled(im):
            if abs(s - 1.0) < 1e-3:
                return im
            return im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))),
                             Image.LANCZOS)

        self.pimg = {}
        for k, im in self._emo_src.items():
            im2 = scaled(im)
            self.pimg[f"{k}_L"] = ImageTk.PhotoImage(im2)
            self.pimg[f"{k}_R"] = ImageTk.PhotoImage(im2.transpose(Image.FLIP_LEFT_RIGHT))
        self.p_fw, self.p_fh = scaled(self._emo_src["normal"]).size

        def _mk(im):
            im2 = scaled(im)
            return (ImageTk.PhotoImage(im2),
                    ImageTk.PhotoImage(im2.transpose(Image.FLIP_LEFT_RIGHT)))

        if self.has_walk:
            w = self._walk_src
            self.w_fw, self.w_fh = scaled(w["idle"]).size
            il, ir = _mk(w["idle"])
            self.wimg = {"idle_L": il, "idle_R": ir,
                         "walk_L": [], "walk_R": [], "run_L": [], "run_R": []}
            for f in w["walk"]:
                l, r = _mk(f)
                self.wimg["walk_L"].append(l)
                self.wimg["walk_R"].append(r)
            for f in (w["run"] or w["walk"]):
                l, r = _mk(f)
                self.wimg["run_L"].append(l)
                self.wimg["run_R"].append(r)
        else:
            self.w_fw, self.w_fh = self.p_fw, self.p_fh

    def set_scale(self, factor):
        """Resize Marcille live and remember the choice."""
        self.scale = round(max(0.4, min(2.5, factor)), 3)
        self.cfg["scale"] = self.scale
        save_config(self.cfg)
        self.build_images()
        self.apply_mode()
        self.say_bubble(f"How's this size? ({int(self.scale * 100)}%)", force=True)

    def set_scale_dialog(self):
        pct = simpledialog.askinteger(
            "Marcille size", "Size percent (40–250):",
            parent=self.root, initialvalue=int(self.scale * 100),
            minvalue=40, maxvalue=250)
        if pct:
            self.set_scale(pct / 100.0)

    def apply_mode(self):
        self.fw = self.w_fw if self.mode == "walk" else self.p_fw
        self.fh = self.w_fh if self.mode == "walk" else self.p_fh
        self.W = self.fw + 40
        self.H = self.fh + 40 + MUSIC_BAND
        self.floor_y = self.screen_h - self.H - GROUND_MARGIN
        self.x = max(0, min(self.x, self.screen_w - self.W))
        self.y = self.floor_y
        self.canvas.config(width=self.W, height=self.H)
        self.move_window()

    def toggle_autostart(self):
        path = startup_bat_path()
        if os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass
        else:
            with open(path, "w") as f:
                f.write('@echo off\r\n')
                f.write(f'start "" "{sys.executable}" "{os.path.abspath(__file__)}"\r\n')

    def quit(self):
        try:
            self.memory.save()          # remember this moment for next time
        except Exception:
            pass
        self.voice.close()
        self.stop_voice()
        self.root.destroy()

    # ---- reminders --------------------------------------------------------
    def add_reminder(self):
        task = simpledialog.askstring(
            "Remind me", "What should I remind you to do?", parent=self.root)
        if not task:
            return
        when = simpledialog.askstring(
            "When?", "When? e.g.  in 10m   in 2h   in 30s   14:30",
            parent=self.root)
        due = parse_when(when)
        if due is None:
            self.set_state("panic", 40)
            self.show_emote("surprised", 40)
            self.say_bubble("I-I don't understand that time! Try 'in 10m' or '14:30'.",
                            force=True)
            return
        self.tasks.append({
            "text": task.strip(),
            "due": due.isoformat(timespec="seconds"),
            "notified": False,
        })
        save_tasks(self.tasks)
        self.set_state("casting", 40)
        self.show_emote("idea", 50)
        self.say_bubble(pick("remind_set"), force=True)

    def show_reminders(self):
        win = tk.Toplevel(self.root)
        win.title("Marcille's reminders")
        win.attributes("-topmost", True)
        win.configure(bg="#1e2230")
        pending = [t for t in self.tasks if not t["notified"]]
        if not pending:
            tk.Label(win, text="Nothing to nag you about. For now.",
                     bg="#1e2230", fg="#e8e8f0", padx=20, pady=16,
                     font=("Segoe UI", 10)).pack()
        lb = tk.Listbox(win, width=46, height=8, bg="#262b3d", fg="#e8e8f0",
                        selectbackground="#5a4a8a", highlightthickness=0,
                        font=("Segoe UI", 10))
        for t in pending:
            due = datetime.datetime.fromisoformat(t["due"])
            lb.insert(tk.END, f"{due:%a %H:%M}  —  {t['text']}")
        lb.pack(padx=12, pady=12)

        def delete_sel():
            sel = list(lb.curselection())
            if not sel:
                return
            target = pending[sel[0]]
            self.tasks = [t for t in self.tasks if t is not target]
            save_tasks(self.tasks)
            win.destroy()
            self.show_reminders()

        def clear_all():
            self.tasks = [t for t in self.tasks if t["notified"]]
            save_tasks(self.tasks)
            win.destroy()

        bar = tk.Frame(win, bg="#1e2230")
        bar.pack(pady=(0, 12))
        tk.Button(bar, text="Delete selected", command=delete_sel).pack(side="left", padx=6)
        tk.Button(bar, text="Clear all", command=clear_all).pack(side="left", padx=6)
        tk.Button(bar, text="Close", command=win.destroy).pack(side="left", padx=6)

    def check_reminders(self):
        now = datetime.datetime.now()
        fired = False
        for t in self.tasks:
            if t["notified"]:
                continue
            try:
                due = datetime.datetime.fromisoformat(t["due"])
            except Exception:
                t["notified"] = True
                continue
            if now >= due:
                t["notified"] = True
                fired = True
                self.fire_reminder(t["text"])
        if fired:
            save_tasks(self.tasks)

    def fire_reminder(self, task):
        # snap to center-ish, dramatic cast pose, voice + chime + popup
        self.x = self.screen_w // 2 - self.W // 2
        self.move_window()
        self.set_state("casting", 120)
        self.heart_timer = 0
        self.bang_timer = 40
        self.show_emote("surprised", 30)
        try:
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
        except Exception:
            pass
        line = pick("remind_fire").format(task=task)
        self.say_bubble(line, force=True)

        win = tk.Toplevel(self.root)
        win.title("Reminder!")
        win.attributes("-topmost", True)
        win.configure(bg="#2a2140")
        tk.Label(win, text="📜  Marcille reminds you:", bg="#2a2140", fg="#ffd9a0",
                 font=("Segoe UI", 11, "bold"), padx=20).pack(pady=(16, 4))
        tk.Label(win, text=task, bg="#2a2140", fg="#ffffff", wraplength=320,
                 font=("Segoe UI", 13), padx=20, pady=8).pack()
        tk.Button(win, text="Done! (thanks Marcille)",
                  command=win.destroy).pack(pady=(4, 16))
        win.after(60000, lambda: win.winfo_exists() and win.destroy())

    # ---- mouse ------------------------------------------------------------
    def set_state(self, state, timer):
        self.state = state
        self.state_timer = timer
        if state == "move":
            self.direction = random.choice([-1, 1])

    def on_press(self, event):
        # clicking a music-control button on her shouldn't start a drag
        for key, (bx0, by0, bx1, by1) in self.chip_buttons.items():
            if bx0 <= event.x <= bx1 and by0 <= event.y <= by1:
                self._chip_do(key)
                return
        self.dragging = True
        self.drag_dx, self.drag_dy = event.x, event.y
        self.set_state("drag", 99999)
        self.show_emote("surprised", 18)
        self.say_bubble(pick("drag"))

    def on_drag(self, event):
        if self.dragging:
            self.x = self.root.winfo_pointerx() - self.drag_dx
            self.y = self.root.winfo_pointery() - self.drag_dy
            self.move_window()

    def on_release(self, event):
        if self.dragging:
            self.dragging = False
            self.vy = 0
            self.set_state("fall", 99999)

    # ---- helpers ----------------------------------------------------------
    def move_window(self):
        self.root.geometry(f"{self.W}x{self.H}+{int(self.x)}+{int(self.y)}")

    def say_bubble(self, text, force=False, cooldown=6.0):
        self.bubble = text
        self.bubble_t = max(120, min(360, len(text) * 4))
        self.voice.say(text, force=force, cooldown=cooldown)

    def show_caption(self, text, ticks=200):
        """Show text in her speech bubble WITHOUT speaking it (legacy helper)."""
        self.bubble = text
        self.bubble_t = ticks

    # ---- live voice caption: subtitle bar at the bottom of the screen --------
    def _ensure_caption_win(self):
        w = getattr(self, "caption_win", None)
        if w is not None and w.winfo_exists():
            return
        w = tk.Toplevel(self.root)
        w.overrideredirect(True)
        w.attributes("-topmost", True)
        try:
            w.attributes("-alpha", 0.88)
        except Exception:
            pass
        w.configure(bg="#10131c")
        frame = tk.Frame(w, bg="#10131c", highlightbackground="#7a5ea8",
                         highlightthickness=2)
        frame.pack()
        lbl = tk.Label(frame, text="", bg="#10131c", fg="#eaf0ff",
                       font=("Segoe UI", 15, "bold"), padx=22, pady=10,
                       wraplength=min(900, self.screen_w - 120), justify="center")
        lbl.pack()
        self.caption_win = w
        self.caption_lbl = lbl
        w.withdraw()

    def show_user_caption(self, text, live=False, hold=4.0):
        """Show what the user said as a subtitle bar at the bottom-center of the
        screen. live=True (grey, while speaking) vs final (bright, after whisper)."""
        if not text:
            return
        self._ensure_caption_win()
        self.caption_lbl.configure(
            text=("🎤 " if live else "🗣 ") + text,
            fg=("#9fb4d8" if live else "#f3f6ff"))
        w = self.caption_win
        w.update_idletasks()
        ww, wh = w.winfo_reqwidth(), w.winfo_reqheight()
        sx = max(0, (self.screen_w - ww) // 2)
        sy = self.screen_h - wh - 70
        w.geometry("+%d+%d" % (sx, sy))
        w.deiconify()
        w.lift()
        if getattr(self, "_caption_after", None):
            try:
                self.root.after_cancel(self._caption_after)
            except Exception:
                pass
        self._caption_after = self.root.after(
            int(hold * 1000), self._hide_user_caption)

    def _hide_user_caption(self):
        w = getattr(self, "caption_win", None)
        if w is not None and w.winfo_exists():
            w.withdraw()

    def show_emote(self, emotion, ticks=45):
        """Briefly force a facial expression (portrait mode), independent of state."""
        self.emote_override = emotion
        self.emote_ovr_t = ticks

    # ---- living presence ---------------------------------------------------
    FIDGETS = ["sleepy", "thinking", "shy", "aha", "surprised", "blink",
               "normal", "pity"]

    def fidget(self):
        """A small, SILENT idle motion — a glance, a stretch, a yawn — so she
        feels alive even when she has nothing to say."""
        self.show_emote(random.choice(self.FIDGETS), random.randint(24, 50))
        self.fidget_cd = random.randint(280, 720)

    def cursor_lean(self):
        """A small, smoothed horizontal offset toward the mouse pointer, so she
        subtly leans the way you're working. Returns 0 if the pointer can't be read."""
        try:
            px = self.root.winfo_pointerx()
            my_cx = self.x + self.W // 2
            target = max(-7.0, min(7.0, (px - my_cx) * 0.015))
        except Exception:
            target = 0.0
        self.look_dx += (target - self.look_dx) * 0.08   # ease toward target
        return self.look_dx

    def check_presence(self):
        """Notice when you step away and when you come back."""
        idle = idle_seconds()
        if not self.away and idle > 75:
            self.away = True
            if self.state not in ("sleep", "drag"):
                self.show_emote(random.choice(["pity", "thinking", "sleepy"]), 70)
                self.say_bubble(random.choice(AWAY_LINES))
        elif self.away and idle < 3:
            self.away = False
            if self.state not in ("drag",):
                if self.state == "sleep":
                    self.set_state("idle", 90)
                self.show_emote(random.choice(["happy", "laughing", "surprised"]), 80)
                nm = (" " + self.memory.name) if self.memory.name else ""
                back = random.choice(BACK_LINES)
                if nm and random.random() < 0.5:
                    back = f"There you are{nm}! It got so quiet without you."
                self.say_bubble(back, force=True)
                self.happiness = min(100.0, self.happiness + 4)

    # ---- situational awareness --------------------------------------------
    EMOTE_FOR_CAT = {"code": "thinking", "browser": "idea", "media": "happy",
                     "game": "surprised", "office": "aha", "chat": "happy",
                     "design": "shy"}

    def react_to_app(self):
        """Comment in-character when you switch to a new kind of app."""
        name, title = foreground_app()
        cat = categorize_app(name, title)
        # ignore our own window and unknown apps; only react to a fresh category
        if cat is None or cat == self.last_cat or "python" in name:
            self.aware_cd = 250            # re-check in ~10s
            return
        self.last_cat = cat
        self.show_emote(self.EMOTE_FOR_CAT.get(cat, "idea"), 60)
        self.say_bubble(random.choice(APP_LINES[cat]))
        self.aware_cd = random.randint(2200, 4000)   # ~90-160s before next comment

    def check_battery(self):
        b = battery_status()
        if not b or not b["has_batt"] or b["pct"] is None:
            return
        pct, charging = b["pct"], b["charging"]
        if charging:
            if self.batt_low:              # was fretting, now plugged in -> relief
                self.batt_low = False
                self.show_emote("happy", 60)
                self.say_bubble(random.choice(BATTERY_LINES["saved"]), force=True)
            return
        if pct <= 10:
            if not self.batt_low or self.batt_nag_cd == 0:
                self.batt_low = True
                self.batt_nag_cd = 2600    # ~1.7 min between nags
                self.set_state("panic", 60)
                self.show_emote("dizzy", 80)
                self.say_bubble(random.choice(BATTERY_LINES["critical"]), force=True)
        elif pct <= 20:
            if not self.batt_low:
                self.batt_low = True
                self.batt_nag_cd = 4500    # ~3 min between nags
                self.set_state("panic", 50)
                self.show_emote("nervous", 70)
                self.say_bubble(random.choice(BATTERY_LINES["low"]), force=True)
            elif self.batt_nag_cd == 0:
                self.batt_nag_cd = 4500
                self.show_emote("nervous", 60)
                self.say_bubble(random.choice(BATTERY_LINES["low"]))
        else:
            self.batt_low = False          # recovered above 20% somehow

    def check_rhythm(self):
        """Greet the change of day-part once, with a fitting mood."""
        hour = datetime.datetime.now().hour
        phase = ("night" if hour >= 23 or hour < 6 else
                 "morning" if hour < 11 else
                 "evening" if hour >= 17 else "afternoon")
        if phase == self.rhythm_phase or phase == "afternoon":
            self.rhythm_phase = phase
            return
        first = self.rhythm_phase is not None   # don't fire on the very first check
        self.rhythm_phase = phase
        if not first or self.state in ("sleep", "drag", "panic"):
            return
        if phase == "night":
            self.show_emote("sleepy", 70)
        elif phase == "morning":
            self.show_emote("happy", 60)
        else:
            self.show_emote("normal", 50)
        self.say_bubble(random.choice(RHYTHM_LINES[phase]))

    # ---- loop -------------------------------------------------------------
    def tick(self):
        try:
            self.frame += 1
            if not self.dragging:
                self.update_behavior()
            if self.mode == "walk":
                step = 6 if self.state == "move" else 14
                if self.frame % step == 0:
                    self.anim_i += 1
            if self.frame % 15 == 0:
                self.check_reminders()
            if self.spotify.sp is not None and self.frame % 150 == 0:
                self._poll_np()
            if self.frame % 250 == 0:
                self.check_battery()
                self.check_rhythm()
            if self.frame % 1500 == 0:          # ~once a minute: persist the bond
                self.memory.save()
                self._sync_memory()
            if self.frame % 25 == 0:
                self.check_presence()
            self.draw()
        except Exception:
            pass            # never let one bad frame freeze her forever
        finally:
            self.root.after(40, self.tick)

    def update_behavior(self):
        self.hunger = max(0, self.hunger - 0.006)
        self.happiness = max(0, self.happiness - 0.004)
        if self.hunger < 25:
            self.happiness = max(0, self.happiness - 0.01)
        for a in ("heart_timer", "bang_timer", "bubble_t", "chatter_cd",
                  "neglect_cd", "emote_ovr_t", "aware_cd", "batt_nag_cd",
                  "fidget_cd", "glance_cd"):
            if getattr(self, a) > 0:
                setattr(self, a, getattr(self, a) - 1)
        self.blink_t -= 1      # always tick (reset handled in current_emotion)

        if self.state == "fall":
            self.vy += 1.4
            self.y += self.vy
            if self.y >= self.floor_y:
                self.y = self.floor_y
                self.vy = 0
                self.set_state("idle", 70)
            self.move_window()
            return

        # neglect meltdown
        if self.hunger < 22 and self.neglect_cd == 0 and self.state not in ("sleep", "drag"):
            self.set_state("panic", 60)
            self.show_emote(random.choice(["crying", "angry", "panic"]), 80)
            self.say_bubble(pick("neglect"), force=True)
            self.neglect_cd = 900

        # idle chatter (prefer fresh AI lines; fall back to static)
        if (self.chatter_cd == 0 and self.state in ("idle", "move")
                and random.random() < 0.5):
            self.show_emote(random.choice(
                ["happy", "idea", "embarrassed", "normal", "laughing", "surprised",
                 "shy", "aha", "thinking", "pity"]), 45)
            self.say_bubble(self.next_idle_line())
            self.chatter_cd = random.randint(900, 1800)
        self.maybe_refresh_pool()

        # living presence: little silent fidgets so she's never a statue
        if (self.fidget_cd == 0 and self.emote_ovr_t == 0
                and self.state == "idle" and self.bubble_t == 0):
            self.fidget()

        # face the cursor while she's just standing around (she watches you work)
        if self.state == "idle" and not self.dragging:
            try:
                px = self.root.winfo_pointerx()
                my_cx = self.x + self.W // 2
                if abs(px - my_cx) > 90:
                    self.direction = 1 if px > my_cx else -1
            except Exception:
                pass

        # situational awareness: notice what app you're focused on
        if (self.aware_cd == 0 and not self.music_mode
                and self.state in ("idle", "move")):
            self.react_to_app()

        # proactive vision: every few minutes she peeks at your screen unprompted
        if self.glance_cd == 0:
            self.glance_cd = random.randint(9000, 16000)   # ~6-11 min between glances
            self.maybe_glance()

        self.state_timer -= 1

        if self.state == "move":
            self.x += 1.6 * self.direction
            if self.x < 0:
                self.x, self.direction = 0, 1
            elif self.x > self.screen_w - self.W:
                self.x, self.direction = self.screen_w - self.W, -1
            self.move_window()

        if self.state_timer <= 0 and not (self.music_mode and self.state == "casting"):
            self.choose_next()

    def choose_next(self):
        hour = datetime.datetime.now().hour
        night = hour >= 23 or hour < 6
        typing = any_typing()
        roll = random.random()

        if self.state in ("sleep", "happy", "panic", "casting"):
            self.set_state("idle", random.randint(60, 120))
            return

        sleep_chance = 0.35 if night else 0.12
        if typing:
            sleep_chance = 0.02

        if self.hunger < 22:
            self.set_state("idle", 90)
            self.show_emote("sad", 70)
        elif roll < sleep_chance:
            self.set_state("sleep", random.randint(150, 320))
        elif roll < sleep_chance + 0.45:
            self.set_state("move", random.randint(90, 190))
        else:
            self.set_state("idle", random.randint(60, 130))

    # ---- draw -------------------------------------------------------------
    def current_emotion(self):
        if self.emote_ovr_t > 0 and self.emote_override:
            return self.emote_override
        if self.state == "sleep":
            return "sleepy"
        if self.state == "happy":
            return "happy"
        if self.state == "panic" or self.state == "drag":
            return "panic"
        if self.state == "casting":
            return "casting"
        if self.blink_t <= 0:
            if self.blink_t > -3:           # hold blink ~3 frames
                return "blink"
            self.blink_t = random.randint(50, 140)
        return "normal"

    def draw(self):
        if self.mode == "walk" and self.has_walk:
            self.draw_walk()
        else:
            self.draw_portrait()

    def draw_portrait(self):
        c = self.canvas
        c.delete("all")

        sleeping = self.state == "sleep"
        moving = self.state == "move"
        casting = self.state == "casting"

        if casting and self.music_mode:
            hop = -abs(math.sin(self.frame * 0.4)) * 6
            self.fx = math.sin(self.frame * 0.3) * 7
        elif moving:
            hop = -abs(math.sin(self.frame * 0.25)) * 5   # little hop-glide
            self.fx = 0
        elif not sleeping:
            # breathing (vertical) + a slow personal sway so she's never frozen,
            # plus a gentle lean toward wherever the cursor is (she watches you)
            hop = math.sin(self.frame * 0.08) * 1.2
            sway = math.sin(self.frame * 0.03 + self.sway_phase) * 2.0
            self.fx = sway + self.cursor_lean()
        else:
            hop = math.sin(self.frame * 0.04) * 0.6        # soft sleeping breath
            self.fx = 0

        face = "L" if self.direction < 0 else "R"
        img = self.pimg[f"{self.current_emotion()}_{face}"]
        cx = self.W // 2 + self.fx
        cy = self.H - MUSIC_BAND - self.fh // 2 - 6 + hop
        c.create_image(cx, cy, image=img)
        self._draw_extras(c, cx, cy - self.fh // 2)

    def draw_walk(self):
        c = self.canvas
        c.delete("all")

        sleeping = self.state == "sleep"
        moving = self.state == "move"
        casting = self.state == "casting"

        face = "L" if self.direction < 0 else "R"
        if moving:
            seq = self.wimg[f"walk_{face}"]
            img = seq[self.anim_i % len(seq)]
            hop = 0
        else:
            img = self.wimg[f"idle_{face}"]
            hop = 0 if sleeping else math.sin(self.frame * 0.08) * 1.5
        if casting and self.music_mode:
            self.fx = math.sin(self.frame * 0.3) * 5
        elif moving or sleeping:
            self.fx = 0
        else:
            self.fx = math.sin(self.frame * 0.03 + self.sway_phase) * 2.0 + self.cursor_lean()

        cx = self.W // 2 + self.fx
        cy = self.H - MUSIC_BAND - self.fh // 2 - 6 + hop
        c.create_image(cx, cy, image=img)
        self._draw_extras(c, cx, cy - self.fh // 2)

    def _draw_extras(self, c, cx, top_y):
        sleeping = self.state == "sleep"
        casting = self.state == "casting"

        if sleeping:
            for i in range(3):
                off = math.sin(self.frame * 0.05 + i) * 2
                c.create_text(cx + 16 + i * 12, top_y + 6 - i * 11 + off, text="z",
                              font=("Segoe UI", 9 + i * 4, "bold"), fill="#7fb0ff")

        if self.heart_timer > 0:
            for i in range(2):
                hx = cx + (-22 + i * 44)
                hy = top_y + 8 - (50 - self.heart_timer) * 0.4
                c.create_text(hx, hy, text="♥", font=("Segoe UI", 14, "bold"),
                              fill="#ff5d8f")

        if self.bang_timer > 0:
            c.create_text(cx, top_y, text="!", font=("Segoe UI", 16, "bold"),
                          fill="#ffd166")

        if casting and self.music_mode:
            for i, ch in enumerate("♪♫♪"):
                ph = self.frame * 0.12 + i * 1.6
                nx = cx + math.sin(ph) * 24 + (i - 1) * 14
                ny = top_y + 4 - (ph * 6) % 38
                c.create_text(nx, ny, text=ch, font=("Segoe UI", 13, "bold"),
                              fill=("#ffd166", "#06d6a0", "#ef476f")[i % 3])

        if self.bubble_t > 0 and self.bubble:
            self.draw_bubble(c, cx, top_y)

        if self.np and self.spotify.sp is not None:
            self.draw_chip(c)
        else:
            self.chip_buttons = {}

    # ---- on-her music control chip ---------------------------------------
    def draw_chip(self, c):
        cx = self.W // 2
        top = self.H - MUSIC_BAND + 2          # the reserved band under her feet
        box_w = self.W - 8
        c.create_rectangle(cx - box_w // 2, top, cx + box_w // 2, top + MUSIC_BAND - 6,
                           fill="#1e2230", outline="#7a5ea8", width=2)

        # song title (truncated to fit on one line)
        title = ""
        if self.np:
            title = f"{self.np['name']} — {self.np['artist']}"
        if title:
            c.create_text(cx, top + 12, text=title[:34], fill="#ffd9a0",
                          font=("Segoe UI", 8))

        # control buttons
        labels = [("prev", "⏮"), ("pause", "⏸"), ("play", "▶"), ("next", "⏭")]
        bw, gap = 24, 6
        total = len(labels) * bw + (len(labels) - 1) * gap
        x0 = cx - total // 2
        by = top + 33
        self.chip_buttons = {}
        for i, (key, glyph) in enumerate(labels):
            bx = x0 + i * (bw + gap)
            c.create_text(bx + bw // 2, by, text=glyph, fill="#eef0f6",
                          font=("Segoe UI Symbol", 12))
            self.chip_buttons[key] = (bx, by - 12, bx + bw, by + 12)

    def _chip_do(self, key):
        self.show_emote("casting", 22)
        fn = {"prev": self.spotify.previous, "pause": self.spotify.pause,
              "play": self.spotify.resume, "next": self.spotify.skip}[key]

        def work():
            fn()
            time.sleep(0.4)
            np = self.spotify.now_playing()
            self.root.after(0, lambda: setattr(self, "np", np))
        threading.Thread(target=work, daemon=True).start()

    def _poll_np(self):
        if self._np_busy:
            return
        self._np_busy = True

        def work():
            np = self.spotify.now_playing()

            def done():
                self.np = np
                self._np_busy = False
            self.root.after(0, done)
        threading.Thread(target=work, daemon=True).start()

    def draw_bubble(self, c, cx, top_y):
        text = self.bubble
        # word-wrap to ~26 chars
        words, lines, cur = text.split(), [], ""
        for w in words:
            if len(cur) + len(w) + 1 > 26:
                lines.append(cur)
                cur = w
            else:
                cur = (cur + " " + w).strip()
        if cur:
            lines.append(cur)
        shown = "\n".join(lines[:4])
        bw = min(240, max(60, max((len(l) for l in lines), default=4) * 7 + 16))
        bh = len(lines[:4]) * 16 + 14
        bx0 = max(4, min(cx - bw // 2, self.W - bw - 4))
        by1 = top_y - 8
        by0 = by1 - bh
        if by0 < 2:
            by0, by1 = 2, 2 + bh
        c.create_rectangle(bx0, by0, bx0 + bw, by1, fill="#fbf7ee",
                           outline="#7a5ea8", width=2)
        c.create_polygon(cx - 6, by1, cx + 6, by1, cx, by1 + 8,
                         fill="#fbf7ee", outline="#7a5ea8")
        c.create_text(bx0 + bw // 2, (by0 + by1) // 2, text=shown,
                      font=("Segoe UI", 9), fill="#2a2140", justify="center")


if __name__ == "__main__":
    Marcille().root.mainloop()

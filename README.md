# Marcille — Desktop Companion 🧝‍♀️

Marcille is an animated desktop pet + mini-assistant. She's [Marcille Donato](https://en.wikipedia.org/wiki/Delicious_in_Dungeon) from *Delicious in Dungeon*: she wanders your screen, blinks, naps, reacts to your cursor, talks back in character, controls your music, runs little tasks, and remembers you over time.

She runs **fully on your own machine** — no account required for the basics.

---

## ⚡ Quick start (the short answer)

1. **Download the project** (clone or [download ZIP](https://github.com/taminggg1-cmyk/marcile/archive/refs/heads/main.zip) → extract).
2. Install the one required dependency:
   ```
   pip install pillow
   ```
3. **Run the app:**
   - **Easiest (Windows):** double-click **`Start Marcille.bat`**
   - **Or from a terminal:** `python marcille.py`

That's it. Right-click her for the menu. Press **Esc** to quit.

> **Which file do I run?** → **`marcille.py`** (the `.bat` is just a convenience launcher that picks the right Python for you).

---

## 💻 Does it work on Linux / macOS?

**No — this is currently Windows-only.** ❌🐧

The app relies on Windows-specific APIs that have no direct equivalent in the code:
- `winsound` — system sounds / beeps
- `ctypes.windll.user32` / `kernel32` / `winmm` — idle detection, keypress simulation, foreground-window awareness, lock-screen, audio
- `os.startfile` — launching apps/files

To run on Linux or macOS you'd need to port those pieces (e.g. swap `winsound` for `playsound`, `os.startfile` for `xdg-open`/`open`, and replace the Win32 idle/window calls). That porting work has **not** been done yet.

**Recommended:** run it on **Windows 10 or 11**.

---

## 📦 Do I need to clone the whole project?

**Yes — clone/download the whole repo.** The app needs both `marcille.py` **and** the `assets/` folder (her sprites and animation frames live there). It won't run without the assets.

What is **not** in the repo (intentionally — they're large and/or personal, and the `.gitignore` skips them):
- The Python virtual environment (`rvc_env/`)
- Downloaded AI/voice model weights (`vosk_model/`, `miku_model/`)
- Your personal state — config, memory, Spotify cache (`marcille_config.json`, `marcille_memory.json`, etc.)

These are only needed for the **optional** advanced features below; they get created/downloaded when you set those up. The core pet works without any of them.

---

## 🔧 Dependencies

### Required (core pet)
| What | How to get it |
|------|---------------|
| **Python 3.10+** (3.14 recommended) | https://www.python.org/downloads/ |
| **Pillow** | `pip install pillow` |
| **tkinter** | Bundled with the official Python installer on Windows (no action needed) |

The base desktop pet — animation, dragging, moods, music keys, reminders, Windows text-to-speech — needs **nothing beyond Pillow**.

### Optional features (install only if you want them)

| Feature | Extra dependencies | Notes |
|---------|-------------------|-------|
| 🗣️ **Nicer TTS voice** | `pip install edge-tts` | Microsoft Edge neural voices |
| 🎵 **Spotify control** | `pip install spotipy` | Needs your own Spotify app credentials |
| 🎤 **Wake-word + voice commands** ("Marcille…") | `pip install vosk sounddevice numpy faster-whisper` + a downloaded Vosk model | See `voice_listen.py` |
| 🧠 **Local AI brain** (chat / sees your screen / does tasks) | [Ollama](https://ollama.com) running locally with `gemma3:4b` + `qwen2.5:7b` | Fully offline, free |
| ☁️ **Smarter cloud brain** (optional) | A Google **Gemini** API key in your config | Used as the "smart" brain when present; falls back to local Ollama otherwise |
| 🎙️ **Custom Miku-style voice (RVC)** | `torch` + the RVC env (heavy) | Advanced; see `miku_rvc.py` |

Install everything optional at once:
```
pip install pillow edge-tts spotipy vosk sounddevice numpy faster-whisper
```

---

## 🎮 Using her

- **Right-click** → menu (music, tasks, voice toggles, "what you remember", size, etc.)
- **Drag** her around (she'll complain)
- **Talk to her** if voice is enabled — say **"Marcille"** then your command
- **Esc** → quit

---

## ❓ FAQ (your friend's questions, answered)

- **Which file do I run?** → `marcille.py` (or double-click `Start Marcille.bat` on Windows).
- **Do I have to clone the whole project?** → Yes — you need `marcille.py` + the `assets/` folder. Models/venv are optional and not included.
- **Does it work on Linux?** → Not as-is. It's Windows-only right now (see above).
- **What dependencies?** → Just **Pillow** for the basics; extras are optional (table above).
- **Is the GitHub project actually downloadable?** → Yes ✅ — it's a **public** repo and the full project (code + all sprite assets) downloads as a working copy.

---

## 📜 Credits

Sprite/art credits are in [`CREDITS.txt`](CREDITS.txt). Marcille Donato is a character from *Delicious in Dungeon* (Ryōko Kui); this is a non-commercial fan project.

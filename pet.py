"""
Desktop Pet - a cute animated black cat companion + music helper.

Cat art: "Black Cat Sprites" by carysaurus (itch.io) - used per its license
(free & commercial use with credit; not redistributed/resold). Frames are
sliced from Black-Idle.png / Black-Run.png at load time.

The cat:
  * Walks/runs around with a real animation, idles with a swishing tail
  * Chases your mouse cursor and pounces (hearts) when it catches it
  * Has hunger + happiness that drift over time - feed & play to keep it happy
  * Sleeps more at night, perks up while you're typing, naps with Zzz
  * Drag it (gravity drop) and click it (hearts)

Music assistant (right-click -> Music):
  * Play/Pause, Next, Previous, Volume up/down/mute (media keys -> any player)
  * "Play lo-fi" opens a chill stream; "Dance party" makes it dance with notes

Other right-click: Feed, nap/wake, new kitten, start-with-Windows, Quit.
Esc quits.
"""

import os
import sys
import math
import random
import ctypes
import datetime
import subprocess
import webbrowser
import tkinter as tk
from PIL import Image, ImageTk

TRANSPARENT = "#ff00ff"
SCALE = 1                  # frames are already pre-scaled in assets/frames/cary
GROUND_MARGIN = 60
LOFI_URL = "https://www.youtube.com/watch?v=jfKfPfyJRdk"

HERE = os.path.dirname(os.path.abspath(__file__))
CARY = os.path.join(HERE, "assets", "frames", "cary")

VK = dict(play=0xB3, next=0xB0, prev=0xB1, vup=0xAF, vdown=0xAE, mute=0xAD)
user32 = ctypes.windll.user32


def tap_key(vk):
    user32.keybd_event(vk, 0, 0, 0)
    user32.keybd_event(vk, 0, 2, 0)


def any_typing():
    for vk in list(range(0x41, 0x5B)) + [0x20, 0x0D, 0x08]:
        if user32.GetAsyncKeyState(vk) & 0x8000:
            return True
    return False


def startup_bat_path():
    appdata = os.environ.get("APPDATA", "")
    return os.path.join(appdata, r"Microsoft\Windows\Start Menu\Programs\Startup",
                        "DesktopPetCat.bat")


def load_seq(prefix, count):
    out = []
    for i in range(count):
        im = Image.open(os.path.join(CARY, f"{prefix}_{i}.png")).convert("RGBA")
        if SCALE != 1:
            im = im.resize((im.width * SCALE, im.height * SCALE), Image.NEAREST)
        out.append(im)
    return out


class Pet:
    def __init__(self):
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-transparentcolor", TRANSPARENT)
        self.root.config(bg=TRANSPARENT)

        idle = load_seq("idle", 12)
        run = load_seq("run", 6)
        self.fw, self.fh = idle[0].size
        # facing left = original art; facing right = mirrored
        self.anim = {
            "idle_L": [ImageTk.PhotoImage(f) for f in idle],
            "idle_R": [ImageTk.PhotoImage(f.transpose(Image.FLIP_LEFT_RIGHT)) for f in idle],
            "run_L": [ImageTk.PhotoImage(f) for f in run],
            "run_R": [ImageTk.PhotoImage(f.transpose(Image.FLIP_LEFT_RIGHT)) for f in run],
        }

        self.W = self.fw + 40
        self.H = self.fh + 40

        self.screen_w = self.root.winfo_screenwidth()
        self.screen_h = self.root.winfo_screenheight()
        self.x = random.randint(60, self.screen_w - self.W - 60)
        self.floor_y = self.screen_h - self.H - GROUND_MARGIN
        self.y = self.floor_y

        self.canvas = tk.Canvas(self.root, width=self.W, height=self.H,
                                bg=TRANSPARENT, highlightthickness=0)
        self.canvas.pack()

        self.state = "idle"          # idle, move, chase, sleep, happy, drag, fall, dance
        self.state_timer = 60
        self.direction = -1          # -1 left, 1 right
        self.frame = 0
        self.anim_i = 0
        self.vy = 0.0
        self.fx = 0.0

        self.happiness = 90.0
        self.hunger = 90.0
        self.heart_timer = 0
        self.bang_timer = 0
        self.pounce_cd = 0
        self.music_mode = False

        self.prev_ptr = (0, 0)
        self.interest = 0

        self.dragging = False
        self.drag_dx = self.drag_dy = 0

        self.canvas.bind("<Button-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Button-3>", self.show_menu)
        self.root.bind("<Escape>", lambda e: self.root.destroy())

        self.build_menu()
        self.move_window()
        self.tick()

    # ---- menu --------------------------------------------------------------
    def build_menu(self):
        m = tk.Menu(self.root, tearoff=0)
        m.add_command(label="🐾 Pet / Play", command=self.play)
        m.add_command(label="🍣 Feed", command=self.feed)
        m.add_separator()

        music = tk.Menu(m, tearoff=0)
        music.add_command(label="⏯  Play / Pause", command=lambda: self.media("play"))
        music.add_command(label="⏭  Next track", command=lambda: self.media("next"))
        music.add_command(label="⏮  Previous track", command=lambda: self.media("prev"))
        music.add_separator()
        music.add_command(label="🔊  Volume up", command=lambda: self.media("vup"))
        music.add_command(label="🔉  Volume down", command=lambda: self.media("vdown"))
        music.add_command(label="🔇  Mute", command=lambda: self.media("mute"))
        music.add_separator()
        music.add_command(label="🎵  Play lo-fi (browser)", command=self.play_lofi)
        music.add_command(label="💃  Dance party (toggle)", command=self.toggle_dance)
        m.add_cascade(label="🎶 Music", menu=music)

        m.add_separator()
        self.mood_idx = m.index("end") + 1
        m.add_command(label="mood", state="disabled")
        m.add_command(label="hunger", state="disabled")
        m.add_separator()
        m.add_command(label="😴 Nap / Wake", command=self.toggle_sleep)
        m.add_command(label="🐈 New kitten", command=self.spawn)
        self.autostart_idx = m.index("end") + 1
        m.add_command(label="autostart", command=self.toggle_autostart)
        m.add_separator()
        m.add_command(label="❌ Quit", command=self.root.destroy)
        self.menu = m

    def show_menu(self, event):
        self.menu.entryconfigure(self.mood_idx, label=f"💛 Happy: {int(self.happiness)}%")
        self.menu.entryconfigure(self.mood_idx + 1, label=f"🍽 Hunger: {int(self.hunger)}%")
        on = os.path.exists(startup_bat_path())
        self.menu.entryconfigure(self.autostart_idx,
                                 label=("✅ Start with Windows" if on else "▶ Start with Windows"))
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

    # ---- actions -----------------------------------------------------------
    def play(self):
        self.happiness = min(100, self.happiness + 18)
        self.set_state("happy", 45)
        self.heart_timer = 45

    def feed(self):
        self.hunger = min(100, self.hunger + 35)
        self.happiness = min(100, self.happiness + 8)
        self.set_state("happy", 35)
        self.heart_timer = 35

    def media(self, what):
        tap_key(VK[what])
        if what in ("play", "next", "prev"):
            self.music_mode = True
            self.set_state("dance", 220)

    def play_lofi(self):
        webbrowser.open(LOFI_URL)
        self.music_mode = True
        self.set_state("dance", 400)

    def toggle_dance(self):
        self.music_mode = not self.music_mode
        self.set_state("dance" if self.music_mode else "idle", 400 if self.music_mode else 60)

    def toggle_sleep(self):
        self.set_state("idle" if self.state == "sleep" else "sleep",
                       80 if self.state == "sleep" else 9999)

    def spawn(self):
        try:
            subprocess.Popen([sys.executable, os.path.abspath(__file__)])
        except Exception:
            pass

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

    # ---- mouse -------------------------------------------------------------
    def set_state(self, state, timer):
        if state != self.state:
            self.anim_i = 0
        self.state = state
        self.state_timer = timer
        if state == "move":
            self.direction = random.choice([-1, 1])

    def on_press(self, event):
        self.dragging = True
        self.drag_dx, self.drag_dy = event.x, event.y
        self.set_state("drag", 9999)

    def on_drag(self, event):
        if self.dragging:
            self.x = self.root.winfo_pointerx() - self.drag_dx
            self.y = self.root.winfo_pointery() - self.drag_dy
            self.move_window()

    def on_release(self, event):
        if self.dragging:
            self.dragging = False
            self.vy = 0
            self.set_state("fall", 9999)

    # ---- helpers -----------------------------------------------------------
    def move_window(self):
        self.root.geometry(f"{self.W}x{self.H}+{int(self.x)}+{int(self.y)}")

    def cat_center(self):
        return self.x + self.W / 2, self.y + (self.H - self.fh / 2)

    # ---- loop --------------------------------------------------------------
    def tick(self):
        self.frame += 1
        if not self.dragging:
            self.update_behavior()
        self.advance_anim()
        self.draw()
        self.root.after(40, self.tick)

    def advance_anim(self):
        if self.state in ("move", "chase"):
            step = 3 if self.state == "chase" else 4
        elif self.state == "dance":
            step = 5
        elif self.state == "sleep":
            step = 999          # basically frozen
        else:
            step = 7            # gentle idle
        if self.frame % step == 0:
            self.anim_i += 1

    def update_behavior(self):
        self.hunger = max(0, self.hunger - 0.006)
        self.happiness = max(0, self.happiness - 0.004)
        if self.hunger < 25:
            self.happiness = max(0, self.happiness - 0.01)
        for a in ("heart_timer", "bang_timer", "pounce_cd"):
            if getattr(self, a) > 0:
                setattr(self, a, getattr(self, a) - 1)

        px, py = self.root.winfo_pointerx(), self.root.winfo_pointery()
        if abs(px - self.prev_ptr[0]) + abs(py - self.prev_ptr[1]) > 6:
            self.interest = 45
        self.prev_ptr = (px, py)
        if self.interest > 0:
            self.interest -= 1

        if self.state == "fall":
            self.vy += 1.4
            self.y += self.vy
            if self.y >= self.floor_y:
                self.y = self.floor_y
                self.vy = 0
                self.set_state("idle", 70)
            self.move_window()
            return

        # mouse chasing
        if self.state not in ("sleep", "dance"):
            cx, cy = self.cat_center()
            dx = px - cx
            dist = math.hypot(dx, py - cy)
            if dist < 70 and self.pounce_cd == 0:
                self.happiness = min(100, self.happiness + 6)
                self.heart_timer = 30
                self.set_state("happy", 30)
                self.pounce_cd = 60
            elif dist < 300 and self.interest > 0 and self.state != "happy":
                if self.state != "chase":
                    self.bang_timer = 12
                self.state = "chase"
                self.state_timer = 20
                self.direction = 1 if dx > 0 else -1
                self.x += self.direction * 3.4
                self.x = max(0, min(self.x, self.screen_w - self.W))
                self.move_window()

        self.state_timer -= 1

        if self.state == "move":
            self.x += 1.7 * self.direction
            if self.x < 0:
                self.x, self.direction = 0, 1
            elif self.x > self.screen_w - self.W:
                self.x, self.direction = self.screen_w - self.W, -1
            self.move_window()

        if self.state_timer <= 0 and self.state != "dance":
            self.choose_next()

    def choose_next(self):
        hour = datetime.datetime.now().hour
        night = hour >= 22 or hour < 6
        typing = any_typing()
        roll = random.random()

        if self.state in ("sleep", "happy"):
            self.set_state("idle", random.randint(60, 110))
            return

        sleep_chance = 0.45 if night else 0.18
        if typing:
            sleep_chance = 0.03

        if self.hunger < 22:
            self.set_state("idle", 90)          # mope when hungry
        elif roll < sleep_chance:
            self.set_state("sleep", random.randint(150, 360))
        elif roll < sleep_chance + 0.5:
            self.set_state("move", random.randint(90, 200))
        else:
            self.set_state("idle", random.randint(60, 130))

    # ---- draw --------------------------------------------------------------
    def frames_for_state(self):
        face = "L" if self.direction < 0 else "R"
        kind = "run" if self.state in ("move", "chase") else "idle"
        return self.anim[f"{kind}_{face}"]

    def draw(self):
        c = self.canvas
        c.delete("all")

        sleeping = self.state == "sleep"
        moving = self.state in ("move", "chase")
        dancing = self.state == "dance"

        if dancing:
            hop = -abs(math.sin(self.frame * 0.5)) * 6
            self.fx = math.sin(self.frame * 0.35) * 9
        elif moving:
            hop = 0
            self.fx = 0
        elif not sleeping:
            hop = math.sin(self.frame * 0.08) * 1.2
            self.fx = 0
        else:
            hop = 0
            self.fx = 0

        seq = self.frames_for_state()
        img = seq[self.anim_i % len(seq)]
        cx = self.W // 2 + self.fx
        cy = self.H - self.fh // 2 - 6 + hop
        c.create_image(cx, cy, image=img)

        top_y = cy - self.fh // 2

        if sleeping:
            for i in range(3):
                off = math.sin(self.frame * 0.05 + i) * 2
                c.create_text(cx + 16 + i * 12, top_y + 6 - i * 11 + off, text="z",
                              font=("Segoe UI", 9 + i * 4, "bold"), fill="#7fb0ff")

        if self.heart_timer > 0:
            for i in range(2):
                hx = cx + (-22 + i * 44)
                hy = top_y + 8 - (45 - self.heart_timer) * 0.5
                c.create_text(hx, hy, text="♥", font=("Segoe UI", 14, "bold"),
                              fill="#ff5d8f")

        if self.bang_timer > 0:
            c.create_text(cx, top_y, text="!", font=("Segoe UI", 16, "bold"),
                          fill="#ffd166")

        if dancing:
            for i, ch in enumerate("♪♫♪"):
                ph = self.frame * 0.12 + i * 1.6
                nx = cx + math.sin(ph) * 24 + (i - 1) * 14
                ny = top_y + 4 - (ph * 6) % 38
                c.create_text(nx, ny, text=ch, font=("Segoe UI", 13, "bold"),
                              fill=("#ffd166", "#06d6a0", "#ef476f")[i % 3])


if __name__ == "__main__":
    Pet().root.mainloop()

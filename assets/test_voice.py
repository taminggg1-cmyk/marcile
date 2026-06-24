"""Verify edge-tts generation + MCI mp3 playback end to end."""
import os, time, asyncio, ctypes, tempfile
import edge_tts

VOICE = "en-US-AriaNeural"
path = os.path.join(tempfile.gettempdir(), f"marc_voicetest_{int(time.time())}.mp3")


async def gen():
    c = edge_tts.Communicate("Marcille Donato, top of my class. Can you hear me?",
                             VOICE, rate="+6%", pitch="+12Hz")
    await c.save(path)

asyncio.run(gen())
size = os.path.getsize(path) if os.path.exists(path) else 0
print("generated mp3:", size, "bytes")

mci = ctypes.windll.winmm.mciSendStringW
def cmd(s):
    return mci(s, None, 0, 0)

r1 = cmd(f'open "{path}" type mpegvideo alias mv')
r2 = cmd('play mv wait')
r3 = cmd('close mv')
print("mci open/play/close return codes:", r1, r2, r3, "(0 = OK)")
try:
    os.remove(path)
except OSError:
    pass
print("VOICE_TEST_DONE")

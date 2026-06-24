"""Headless smoke test: exercise the paths that were broken (reminder popup,
emotion draws, mode toggle, walk frames) WITHOUT going through tick()'s
exception guard, so any error surfaces here. Does not consume real reminders."""
import traceback
import marcille

m = marcille.Marcille()
m.voice.muted = True            # keep the test silent / offline
try:
    # portrait draws + emotion/blink cycling
    for _ in range(40):
        m.frame += 1
        m.update_behavior()
        m.draw()
    seen = set()
    for st in ("happy", "panic", "casting", "sleep"):
        m.set_state(st, 30)
        m.draw()
        seen.add(m.current_emotion())
    # force-render every emotion frame (catches a missing/broken PNG)
    for emo in marcille.EMOTIONS:
        m.show_emote(emo, 30)
        m.draw()
        assert m.current_emotion() == emo, f"emote {emo} not shown"
    # the popup that used to crash (bad pady)
    m.fire_reminder("test reminder popup")
    m.draw()
    # walk mode
    m.toggle_mode()
    assert m.mode == "walk", "toggle did not enter walk"
    m.set_state("move", 60)
    for _ in range(40):
        m.frame += 1
        m.update_behavior()
        if m.frame % 6 == 0:
            m.anim_i += 1
        m.draw()
    m.toggle_mode()
    assert m.mode == "portrait", "toggle did not return to portrait"
    m.draw()
    print("HARNESS_OK  emotions_seen=", sorted(seen))
except Exception:
    print("HARNESS_FAIL")
    traceback.print_exc()
finally:
    try:
        m.voice.close()
    except Exception:
        pass
    m.root.destroy()

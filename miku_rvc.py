"""Miku RVC voice-conversion helper. Runs under rvc_env (Python 3.10 + torch
CUDA + rvc-python), NOT the main 3.14 Python that runs marcille.py.

Modes:
  python miku_rvc.py once  INPUT OUTPUT   -> convert one file and exit (for tests)
  python miku_rvc.py serve                -> read 'INPUT|OUTPUT' lines on stdin,
                                             convert each, emit 'OK' / 'ERR ...'

rvc-python prints a lot of diagnostic chatter to stdout during load/inference.
That would corrupt the simple line protocol marcille.py speaks over the pipe, so
we redirect the library's stdout to stderr and send ONLY our sentinels
(READY / OK / ERR) on the real stdout via emit().
"""
import sys
import os

# Keep a clean handle to the real stdout, then send everything the library
# prints to stderr (which marcille.py captures to miku_server.log).
_REAL_STDOUT = sys.stdout
sys.stdout = sys.stderr


def emit(msg):
    _REAL_STDOUT.write(msg + "\n")
    _REAL_STDOUT.flush()


HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = os.path.join(HERE, "miku_model", "extracted", "MikuAI_e210_s6300.pth")
INDEX = os.path.join(HERE, "miku_model", "extracted",
                     "added_IVF1811_Flat_nprobe_1_MikuAI_v2.index")
MODELS_DIR = os.path.join(HERE, "rvc_models")   # hubert_base.pt / rmvpe.pt land here


def _miku_pitch():
    """Semitone pitch shift, read from marcille_config.json (key 'miku_pitch').
    0 = Miku speaking naturally; +7..+12 = higher / more singing-range."""
    import json
    try:
        d = json.load(open(os.path.join(HERE, "marcille_config.json"),
                           encoding="utf-8"))
        return int(d.get("miku_pitch", 0))
    except Exception:
        return 0


def make_rvc():
    from rvc_python.infer import RVCInference
    try:
        import torch
        dev = "cuda:0" if torch.cuda.is_available() else "cpu"
    except Exception:
        dev = "cpu"
    rvc = RVCInference(models_dir=MODELS_DIR, device=dev)
    rvc.load_model(MODEL, index_path=INDEX)
    # tune for converting a female TTS voice into Miku's timbre
    rvc.set_params(f0method="rmvpe", f0up_key=_miku_pitch(),
                   index_rate=0.5, protect=0.33)
    return rvc, dev


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "serve"
    rvc, dev = make_rvc()

    if mode == "once":
        rvc.infer_file(sys.argv[2], sys.argv[3])
        emit("OK " + dev + " " + sys.argv[3])
        return

    emit("READY " + dev)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        if line == "QUIT":
            break
        try:
            inp, out = line.split("|", 1)
            rvc.infer_file(inp, out)
            emit("OK")
        except Exception as e:
            emit("ERR " + repr(e))


if __name__ == "__main__":
    main()

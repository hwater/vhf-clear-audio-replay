#!/usr/bin/env python3
# Klassifiziert eine VHF-Aufnahme: echte Sprache (behalten, exit 0) vs
# Stoerung/Traeger/Rauschen (verwerfen, exit 1).
#
# Merkmal = SPRACH-RHYTHMUS der Lautstaerke-Huellkurve (gain-unabhaengig!):
#   modIndex = std/mean der Energie-Huellkurve (Sprachband 250-3400 Hz)
#   mod4     = Anteil der Huellkurven-Energie im 2-8 Hz Silbentakt
# Anlernung an gelabelten Aufnahmen (User): echte Sprache liegt in einem
# mittleren Modulations-Band; Dauertraeger (modIndex niedrig) und erratisches
# Rauschen (modIndex hoch) liegen darueber/darunter.
#   SPRACHE wenn  MI_LO <= modIndex <= MI_HI  UND  mod4 >= MOD4.  Im Zweifel BEHALTEN.
import sys, os, subprocess
import numpy as np

MI_LO = float(os.environ.get("VHF_MI_LO", "0.55"))
MI_HI = float(os.environ.get("VHF_MI_HI", "1.65"))
MOD4  = float(os.environ.get("VHF_MOD4",  "0.30"))
LOG = "/run/vhf/classify.log"

def log(m):
    try:
        os.makedirs("/run/vhf", exist_ok=True)
        with open(LOG, "a") as f:
            f.write(m + "\n")
    except Exception:
        pass

def done(tag, info, name, code):
    m = "%-6s %-24s %s" % (tag, info, name)
    log(m); print(m, file=sys.stderr); sys.exit(code)

path = sys.argv[1]
name = os.path.basename(path)
try:
    p = subprocess.run(["ffmpeg", "-v", "quiet", "-i", path, "-ac", "1", "-ar", "8000",
                        "-af", "highpass=f=250,lowpass=f=3400", "-f", "s16le", "-"],
                       capture_output=True, timeout=25)
    x = np.frombuffer(p.stdout, dtype=np.int16).astype(np.float32) / 32768.0
except Exception:
    done("KEEP", "decode-err", name, 0)

hop, win = 80, 200                       # 10ms Hop, 25ms Fenster @8k -> Huellkurve @100Hz
n = (len(x) - win) // hop
if n < 15:                               # zu kurz -> im Zweifel behalten
    done("KEEP", "too-short", name, 0)

env = np.sqrt(np.array([np.mean(x[i*hop:i*hop+win]**2) for i in range(n)])) + 1e-9
modIndex = float(env.std() / env.mean())
e = env - env.mean()
E = np.abs(np.fft.rfft(e)) ** 2
fr = np.fft.rfftfreq(len(e), d=hop / 8000.0)
tot = E[(fr >= 0.3) & (fr < 20)].sum() + 1e-9
mod4 = float(E[(fr >= 2) & (fr < 8)].sum() / tot)

info = "modIdx=%.2f mod4=%.2f" % (modIndex, mod4)
if MI_LO <= modIndex <= MI_HI and mod4 >= MOD4:
    done("KEEP", info, name, 0)
done("NOISE", info, name, 1)

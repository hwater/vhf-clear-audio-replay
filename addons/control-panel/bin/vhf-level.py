#!/usr/bin/env python3
# Liest rohes Mono-PCM (vom VHF-Capture, sox-bandpass) von stdin und schreibt
# ~12x/s den aktuellen Spitzenpegel (0..1) nach /run/vhf/level. Quelle fuer
# das VU-Meter im Panel. Laeuft unabhaengig (eigener dsnoop-Leser).
# Zusaetzlich: "Funk nachhoeren" (mute) automatisch AN, aber erst COOLDOWN nach
# der letzten Deaktivierung. Die mtime der mute-Datei = Zeitpunkt der letzten
# Deaktivierung (echter Funk setzt mute=0 -> mtime aktualisiert). So springt es
# nach echtem Funk nicht gleich zurueck, sondern erst 5 min nach dem letzten Funk.
import sys, os, struct, time

LEVEL = "/run/vhf/level"
MUTE = "/run/vhf/mute"
CHUNK = 2048           # ~1024 Samples mono ~23ms
RX_THRESH = 0.03       # = Recorder-Schwelle (Funk anliegend)
COOLDOWN = float(os.environ.get("VHF_MUTE_COOLDOWN", "300"))   # 5 min seit letzter Deaktivierung
os.makedirs("/run/vhf", exist_ok=True)
if not os.path.exists(MUTE):       # Startpunkt fuer den Cooldown setzen
    try:
        with open(MUTE, "w") as f:
            f.write("0")
    except Exception:
        pass

inp = sys.stdin.buffer
last = 0.0
while True:
    d = inp.read(CHUNK)
    if not d:
        break
    now = time.monotonic()
    if now - last > 0.08:
        peak = 0.0
        n = len(d) // 2
        if n:
            s = struct.unpack("<%dh" % n, d[:n * 2])
            peak = max(abs(x) for x in s) / 32768.0
            try:
                with open(LEVEL + ".tmp", "w") as f:
                    f.write("%.4f" % peak)
                os.replace(LEVEL + ".tmp", LEVEL)
            except Exception:
                pass
        # Auto-AN: nur wenn mute gerade AUS ist, kein Funk/keine Wiedergabe laeuft,
        # und seit der letzten Deaktivierung (mute-mtime) >= COOLDOWN vergangen ist.
        active = peak > RX_THRESH or os.path.exists("/run/vhf/playing")
        if not active:
            try:
                cur = open(MUTE).read().strip()
                age = time.time() - os.path.getmtime(MUTE)
            except Exception:
                cur, age = "1", 0
            if cur == "0" and age >= COOLDOWN:
                try:
                    with open(MUTE, "w") as f:
                        f.write("1")
                except Exception:
                    pass
        last = now

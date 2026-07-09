#!/usr/bin/env python3
# VHF-/Audio-Bedienpanel (maritim) - Schieberegler + Anzeigen, Port 8090.
import json, os, re, html, subprocess, threading, time, urllib.request, urllib.parse, urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DELAY_FILE = "/var/lib/vhf/delay"
LEVEL_FILE = "/run/vhf/level"
OWNTONE = "http://localhost:3689"
DELAY_MIN, DELAY_MAX = 0.0, 30.0
PORT = int(os.environ.get("VHF_PANEL_PORT", "8090"))
WEB_PORT = int(os.environ.get("VHF_WEB_PORT", "8088"))   # interne Nachhoer-Liste (Proxy /rec)
SERVICES = {"monitor": "vhf-monitor"}   # einziger im Panel schaltbarer Dienst (Live-Monitor)

# ---- Konfiguration (Schiffsname, HomePod-Modus) -----------------------------
# Einfache key=value-Datei, siehe etc/vhf.conf.example. Fehlt sie, gelten die
# Defaults. Wird bei jedem Aufruf frisch gelesen -> Aenderungen ohne Neustart.
CONFIG_FILE = os.environ.get("VHF_CONFIG", "/etc/vhf/vhf.conf")

def read_config():
    # shipname: "auto" = aus Signal K holen; sonst woertlich (Override).
    cfg = {"shipname": "auto", "homepods": "auto",         # auto | on | off
           "signalk": "http://localhost:3000"}
    try:
        for ln in open(CONFIG_FILE):
            ln = ln.strip()
            if not ln or ln.startswith("#") or "=" not in ln:
                continue
            k, _, v = ln.partition("=")
            k = k.strip().lower(); v = v.strip()
            if k in cfg and v:
                cfg[k] = v
    except Exception:
        pass
    return cfg

_sk_cache = {"t": 0.0, "name": None}

def signalk_name(base):
    # Schiffsname aus Signal K (vessels.self.name); 30s gecacht, kurzer Timeout.
    now = time.monotonic()
    if now - _sk_cache["t"] < 30:
        return _sk_cache["name"]
    name = None
    try:
        url = base.rstrip("/") + "/signalk/v1/api/vessels/self/name"
        with urllib.request.urlopen(url, timeout=1.5) as r:
            d = json.load(r)
        if isinstance(d, str):
            name = d
        elif isinstance(d, dict):
            name = d.get("value") or d.get("name")
        if name:
            name = str(name).strip() or None
    except Exception:
        name = None
    _sk_cache["t"] = now
    _sk_cache["name"] = name
    return name

def resolve_shipname():
    cfg = read_config()
    nm = cfg["shipname"]
    if nm.lower() != "auto":
        return nm                                    # expliziter Override
    return signalk_name(cfg["signalk"]) or "Wilhelmina"

_pods_seen = {"t": 0.0}

def pods_enabled(outs):
    # Sind HomePods "an Bord"? auto = erkannt via OwnTone-Ausgaenge ODER Netz-
    # Erreichbarkeit (podwatch). ENTPRELLT: nach dem letzten Sichten noch 90s als
    # "an Bord" halten, damit ein einzelner leerer/langsamer OwnTone-Poll die
    # Anzeige nicht flackern laesst. Erst nach 90s ohne Pods -> Messe-Betrieb.
    mode = read_config()["homepods"].lower()
    if mode == "on":
        return True
    if mode == "off":
        return False
    seen = any(o.get("name", "").startswith("ShiPod") for o in outs)
    if not seen:                                  # 2. Signal: stabile Netz-Erreichbarkeit
        pn = pods_net()
        if pn and (pn.get("bb") or pn.get("sb")):
            seen = True
    now = time.monotonic()
    if seen:
        _pods_seen["t"] = now
        return True
    return _pods_seen["t"] > 0 and (now - _pods_seen["t"]) < 90

def read_delay():
    try:
        return max(DELAY_MIN, min(DELAY_MAX, float(open(DELAY_FILE).read().strip())))
    except Exception:
        return 7.0

def write_delay(v):
    v = max(DELAY_MIN, min(DELAY_MAX, float(v)))
    os.makedirs(os.path.dirname(DELAY_FILE), exist_ok=True)
    with open(DELAY_FILE + ".tmp", "w") as f:
        f.write("%.1f" % v)
    os.replace(DELAY_FILE + ".tmp", DELAY_FILE)
    return v

def read_level():
    try:
        return float(open(LEVEL_FILE).read().strip())
    except Exception:
        return 0.0

def svc_states():
    units = list(SERVICES.values())
    try:
        r = subprocess.run(["systemctl", "is-active"] + units,
                           capture_output=True, text=True, timeout=4)
        out = r.stdout.split()
    except Exception:
        out = []
    res = {}
    for k, u in SERVICES.items():
        i = units.index(u)
        res[k] = (out[i] == "active") if i < len(out) else False
    return res

def set_svc(unit, on):
    subprocess.run(["systemctl", "start" if on else "stop", unit], timeout=15)

def owntone_outputs():
    try:
        with urllib.request.urlopen(OWNTONE + "/api/outputs", timeout=4) as r:
            return json.load(r).get("outputs", [])
    except Exception:
        return []

HPVOL_FILE = "/var/lib/vhf/hpvol"

def get_hpvol():
    # Uebernahme-Lautstaerke aus der Datei (stabil, = was vhf-playout nutzt). NICHT die
    # Live-OwnTone-Vol nehmen: die faellt auf 0, sobald die ShiPods (Schlaf/IPv6) kurz
    # aus den Ausgaengen fallen -> Regler sprang deshalb auf 0.
    try:
        return max(0, min(100, int(open(HPVOL_FILE).read().strip())))
    except Exception:
        return 60

def set_hpvol(v):
    v = int(max(0, min(100, float(v))))
    try:  # Uebernahme-Lautstaerke fuer vhf-playout.sh festhalten
        os.makedirs("/var/lib/vhf", exist_ok=True)
        with open(HPVOL_FILE, "w") as f:
            f.write(str(v))
    except Exception:
        pass
    for o in owntone_outputs():
        if o["name"].startswith("ShiPod"):
            req = urllib.request.Request(
                OWNTONE + "/api/outputs/%s" % o["id"],
                data=json.dumps({"volume": v}).encode(),
                method="PUT", headers={"Content-Type": "application/json"})
            try:
                urllib.request.urlopen(req, timeout=4).read()
            except Exception:
                pass
    return v

def get_monvol():
    try:
        r = subprocess.run(["amixer", "-c", "3", "sget", "Speaker"],
                           capture_output=True, text=True, timeout=4)
        m = re.search(r"\[(\d+)%\]", r.stdout)
        return int(m.group(1)) if m else 0
    except Exception:
        return 0

def set_monvol(v):
    v = int(max(0, min(100, float(v))))
    subprocess.run(["amixer", "-c", "3", "sset", "Speaker", "%d%%" % v],
                   capture_output=True, timeout=4)
    return v

def read_file_level(path):
    try:
        return float(open(path).read().strip())
    except Exception:
        return 0.0

def shipod_status(outs):
    # "present" = in OwnTone ODER laut podwatch im Netz erreichbar -> Badge flackert
    # nicht bei einem kurzen OwnTone-Aussetzer.
    by = {o.get("name"): o for o in outs}
    pn = pods_net() or {}
    key = {"ShiPod BB": "bb", "ShiPod SB": "sb"}
    res = []
    for nm in ("ShiPod BB", "ShiPod SB"):
        o = by.get(nm)
        res.append({"name": nm, "present": (o is not None) or bool(pn.get(key[nm])),
                    "selected": bool(o and o.get("selected"))})
    return res

_cache = {"t": 0.0, "d": None}

def heavy():
    # teure Aufrufe (systemctl, amixer, OwnTone-HTTP) nur ~1.2s cachen -> Panel reaktiv
    now = time.monotonic()
    if _cache["d"] is None or now - _cache["t"] > 1.2:
        outs = owntone_outputs()
        svc = svc_states()
        _cache["d"] = {"outs": outs, "svc": svc, "hpvol": get_hpvol(),
                       "monvol": get_monvol(), "delay": read_delay()}
        _cache["t"] = now
    return _cache["d"]

def state():
    h = heavy()
    vhf_lvl = read_file_level(LEVEL_FILE)             # Pegel immer frisch (fluessige Anzeige)
    svc = h["svc"]
    return {"delay": h["delay"], "delay_max": DELAY_MAX,
            "hpvol": h["hpvol"], "monvol": h["monvol"], "level": vhf_lvl,
            "monitor": svc["monitor"],
            "mute": read_mute(), "pods_net": pods_net(),
            "pods": pods_enabled(h["outs"]),
            "shipods": shipod_status(h["outs"])}

REC_DIR = "/srv/music/VHF-Aufnahmen"
def replay_file(name=None):
    import glob
    if name:                                   # bestimmte Uebertragung aus der Liste
        name = os.path.basename(name)          # kein Pfad-Ausbruch
        ok = (name.startswith("VHF_") or name.startswith(".noise-VHF_")) and name.endswith(".mp3")
        if not ok:
            return None
        path = os.path.join(REC_DIR, name)
        if not os.path.isfile(path):
            return None
    else:                                      # sonst die neueste
        files = glob.glob(os.path.join(REC_DIR, "VHF_*.mp3"))
        if not files:
            return None
        path = max(files, key=os.path.getmtime)
    if pods_enabled(owntone_outputs()):
        subprocess.Popen(["/usr/local/bin/vhf-playout.sh", path, "now"])   # auf die HomePods
    else:
        subprocess.Popen(["/usr/local/bin/vhf-messe-play.sh", path])       # sonst: Messe-Ausgang
    return os.path.basename(path)

def pods_net():     # Netz-Erreichbarkeit der HomePods (von vhf-podwatch.sh)
    try:
        d = json.load(open("/run/vhf/pods-net"))
        if time.time() - d.get("ts", 0) > 90:   # veraltet -> unbekannt
            return None
        return {"bb": bool(d.get("bb")), "sb": bool(d.get("sb"))}
    except Exception:
        return None

def is_playing():   # laeuft gerade eine Uebernahme/Wiederholung? (Flag von vhf-playout.sh)
    try:
        return (time.time() - os.path.getmtime("/run/vhf/playing")) < 120
    except Exception:
        return False

_env_cache = {}          # basename -> {"dur","env"} | "pending"
PLAY_BUFFER = 3.0        # AirPlay-Vorlauf: Ton startet ~3s nach Uebernahme-Beginn

def _compute_env(base, path):
    try:
        import numpy as np
        p = subprocess.run(["ffmpeg", "-v", "quiet", "-i", path, "-ac", "1", "-ar", "8000",
                            "-f", "s16le", "-"], capture_output=True, timeout=20)
        x = np.frombuffer(p.stdout, dtype=np.int16).astype(np.float32) / 32768.0
        dur = len(x) / 8000.0
        N = 56
        segs = np.array_split(np.abs(x), N) if len(x) >= N else [np.abs(x)]
        env = [float(np.sqrt(np.mean(s * s + 1e-9))) for s in segs]
        mx = max(env) or 1.0
        _env_cache[base] = {"dur": round(dur, 2), "env": [round(min(1.0, e / mx), 3) for e in env]}
    except Exception:
        _env_cache[base] = {"dur": 0, "env": []}

def play_info():         # laufende Wiedergabe fuers VU in der aktiven Zeile
    try:
        base = open("/run/vhf/playing").read().strip()
        started = os.path.getmtime("/run/vhf/playing")
    except Exception:
        return None
    if time.time() - started > 120:
        return None
    ce = _env_cache.get(base)
    if ce is None:
        if len(_env_cache) > 20:
            _env_cache.clear()
        _env_cache[base] = "pending"
        threading.Thread(target=_compute_env, daemon=True,
                         args=(base, os.path.join(REC_DIR, base + ".mp3"))).start()
        ce = None
    dur, env, pos = 0, [], 0.0
    if isinstance(ce, dict):
        dur, env = ce["dur"], ce["env"]
        pos = max(0.0, (time.time() - started) - PLAY_BUFFER)
        if dur:
            pos = min(pos, dur)
    return {"pos": round(pos, 1), "dur": dur, "env": env}

def classify_file(name, as_):
    # Manuelles Nachsortieren: echte Aufnahme VHF_x.mp3 <-> verworfen .noise-VHF_x.mp3.
    # Der Dateiname merkt den Zustand (ok/verworfen) dauerhaft.
    name = os.path.basename(name)
    if name.startswith(".noise-VHF_") and name.endswith(".mp3"):
        bare = name[len(".noise-"):]
    elif name.startswith("VHF_") and name.endswith(".mp3"):
        bare = name
    else:
        return None
    dst_name = (".noise-" + bare) if as_ == "noise" else bare if as_ == "speech" else None
    if dst_name is None:
        return None
    src = os.path.join(REC_DIR, name)
    dst = os.path.join(REC_DIR, dst_name)
    if not os.path.isfile(src):
        return None
    if src != dst:
        try:
            os.replace(src, dst)
            urllib.request.urlopen(
                urllib.request.Request(OWNTONE + "/api/update", method="PUT"), timeout=4).read()
        except Exception:
            return None
    return {"name": dst_name, "noise": dst_name.startswith(".noise-")}

def recent_recs(n=40):
    import glob
    files = (glob.glob(os.path.join(REC_DIR, "VHF_*.mp3"))            # echte
             + glob.glob(os.path.join(REC_DIR, ".noise-VHF_*.mp3")))  # verworfene (versteckt)
    files.sort(key=os.path.getmtime, reverse=True)                    # neueste zuerst
    now = time.time()
    out = []
    for f in files[:n]:
        try:
            st = os.stat(f)
            bn = os.path.basename(f)
            m = re.search(r"(\d{4})-(\d{2})-(\d{2})_(\d{2})-(\d{2})-(\d{2})", bn)
            tstr = "%s.%s. %s:%s:%s" % (m.group(3), m.group(2), m.group(4),
                                        m.group(5), m.group(6)) if m else ""
            out.append({"name": bn, "t": tstr,
                        "sec": max(1, round(st.st_size / 12000)),   # 96 kbit/s ~ 12000 B/s
                        "age": max(0, int(now - st.st_mtime)),
                        "noise": bn.startswith(".noise-")})
        except Exception:
            pass
    return out

MUTE_FILE = "/run/vhf/mute"
def read_mute():
    try:
        return open(MUTE_FILE).read().strip() == "1"
    except Exception:
        return False

def stop_playout():   # laufende Uebernahme/Wiedergabe sofort beenden + HomePods freigeben
    subprocess.run(["pkill", "-f", "vhf-playout.sh"], timeout=5)
    subprocess.run(["pkill", "-f", "vhf-messe-play.sh"], timeout=5)     # Messe-Wiedergabe
    subprocess.run(["pkill", "-f", "aplay -q -D vhfoutplug"], timeout=5)
    try:
        req = urllib.request.Request(OWNTONE + "/api/player/stop", method="PUT")
        urllib.request.urlopen(req, timeout=4).read()
    except Exception:
        pass
    for oid in ("279973827291484", "178870811768074"):
        try:
            req = urllib.request.Request(
                OWNTONE + "/api/outputs/" + oid,
                data=b'{"selected":false}', method="PUT",
                headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=4).read()
        except Exception:
            pass

def set_mute(on):
    on = str(on) in ("1", "true", "True")
    try:
        os.makedirs("/run/vhf", exist_ok=True)
        with open(MUTE_FILE, "w") as f:
            f.write("1" if on else "0")
    except Exception:
        pass
    if on:
        stop_playout()
    return on

def invalidate_cache():
    _cache["t"] = 0.0

PAGE = r'''<!doctype html><html lang=de><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>__SHIP__ VHF</title>
<style>
:root{--brass:#caa45a;--accent:#ffce6b;--ok:#46d17a}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
body{margin:0;font-family:ui-sans-serif,system-ui,Segoe UI,Roboto,sans-serif;
 background:radial-gradient(120% 120% at 50% -10%,#1c2c39,#0b121a 60%,#070b10);
 color:#e8eef4;min-height:100vh;padding:16px 14px 28px}
h1{font-size:14px;letter-spacing:.3em;font-weight:600;color:#bcd2e6;margin:2px 0 0;text-transform:uppercase;text-align:center}
.sub{font-size:10px;color:#6f8497;letter-spacing:.18em;text-align:center;margin:2px 0 16px}
.panel{max-width:460px;margin:0 auto;display:flex;flex-direction:column;gap:14px}
.card{background:#111a24;border:1px solid #20303d;border-radius:14px;padding:14px 16px}
.mlab{font-size:11px;letter-spacing:.2em;color:#9fb4c6;text-transform:uppercase;margin-bottom:8px}
.meter{height:20px;border-radius:8px;background:#0b141c;overflow:hidden;position:relative;border:1px solid #20303d}
.meter>div{height:100%;width:0%;background:linear-gradient(90deg,#2f7d53 0%,#2f7d53 65%,#c9a23a 80%,#ff5a4d 100%);
 transition:width .09s ease-out}
.meter.vu{height:26px}
.rxind{font-size:11px;letter-spacing:.15em;padding:.25em .7em;border-radius:6px;
 background:#0b141c;color:#54647a;border:1px solid #20303d;transition:all .12s}
.rxind.on{background:#163b2a;color:#9affc7;border-color:#2f7d53;box-shadow:0 0 9px #2f7d5599}
.pk{position:absolute;top:0;width:3px;height:100%;background:#eaf6ff;left:0%;
 transition:left .12s linear;box-shadow:0 0 6px #cfe9ff}
.fader{display:flex;align-items:center;gap:12px;margin:14px 0 2px}
.fader label{flex:0 0 116px;font-size:13px;color:#cfe0ee}
.fader input{flex:1;min-width:0}
.fader .val{flex:0 0 58px;text-align:right;font-variant-numeric:tabular-nums;font-size:17px;font-weight:600;color:var(--accent)}
input[type=range]{-webkit-appearance:none;appearance:none;height:8px;border-radius:6px;
 background:#1c2b38;outline:none;border:1px solid #26404f}
input[type=range]::-webkit-slider-thumb{-webkit-appearance:none;width:28px;height:28px;border-radius:50%;
 background:var(--brass);border:2px solid #3a2e12;cursor:pointer}
input[type=range]::-moz-range-thumb{width:26px;height:26px;border-radius:50%;background:var(--brass);
 border:2px solid #3a2e12;cursor:pointer}
.btns{display:flex;flex-direction:column;gap:10px}
.tg{height:56px;border-radius:13px;border:2px solid #233344;background:linear-gradient(#16222e,#0d161e);
 color:#7f97a9;font-size:14px;letter-spacing:.16em;font-weight:700;text-transform:uppercase;
 display:flex;align-items:center;gap:12px;padding:0 18px}
.tg .dot{width:14px;height:14px;border-radius:50%;background:#3a4a59;box-shadow:inset 0 0 4px #000;flex:0 0 auto}
.tg .sub2{margin-left:auto;font-size:10px;letter-spacing:.1em;color:#6f8497;font-weight:400}
.tg.on{color:#d9ffe9;border-color:#2f7d53;background:linear-gradient(#163b2a,#0f261c)}
.tg.on .dot{background:var(--ok);box-shadow:0 0 12px var(--ok)}
.dev{display:flex;align-items:center;gap:10px;margin:9px 0}
.dev label{flex:0 0 122px;font-size:13px;color:#cfe0ee;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.dev .meter{flex:1}
.dev.off{opacity:.38}
.foot{text-align:center;font-size:12px;margin-top:4px}.foot a{color:#7fd1ff;text-decoration:none}
.chk{display:flex;align-items:center;gap:10px;margin-top:12px;font-size:14px;color:#cfe0ee;cursor:pointer}
.chk input{width:22px;height:22px}
.desc{font-size:12px;color:#9aa3bd;margin:8px 0 2px;line-height:1.45}
.podnet{display:none;margin:0 0 10px;padding:.6em .8em;border-radius:8px;font-size:13px;
 background:#5a1d1d;color:#ffd9d9;border:1px solid #9c3b3b}
.podnet.warn{display:block}
.recbtn.busy{pointer-events:none;color:#9affc7;border-color:#2f7d53;background:linear-gradient(#13261c,#0d1a14)}
.spin{display:inline-block;width:13px;height:13px;margin-right:7px;vertical-align:-2px;
 border:2px solid #9affc744;border-top-color:#9affc7;border-radius:50%;animation:sp .7s linear infinite}
@keyframes sp{to{transform:rotate(360deg)}}
.reclist{display:none;flex-direction:column;gap:5px;margin-top:7px}
.reclist.open{display:flex;max-height:60vh;overflow-y:auto;padding-right:4px}
.ic{width:32px;height:28px;border-radius:6px;border:1px solid #233344;background:#0e1922;
 font-size:14px;line-height:1;cursor:pointer;flex:none;padding:0}
.ic.good{color:#9affc7}.ic.bad{color:#ffb3b3}
.ic.cur{outline:1px solid currentColor;outline-offset:-3px;background:#13261c}
.ic.bad.cur{background:#2a1414}
.rec{position:relative;display:flex;align-items:center;gap:8px;padding:.45em .55em;border-radius:7px;
 background:#213141;border-left:5px solid #888;font-size:13px;cursor:pointer;transition:background .1s}
.rec .vu{position:absolute;inset:0;display:flex;align-items:center;gap:8px;padding:0 .7em;
 border-radius:7px;background:#12251b;border:1px solid #2f7d53;box-sizing:border-box;cursor:pointer}
.rec:hover{background:#2b4055}
.rec.play{background:#1d4a34;outline:1px solid #3a9a63}
.rec.noise{opacity:.55}
.rec .len{flex:none;text-align:right;font-weight:700;color:#eaf2fa;white-space:nowrap}
.rec .meta{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#c3cede;font-size:12px}
.rec .ic{flex:none;margin:0}
.shipodstat{display:flex;gap:8px;margin-top:10px;flex-wrap:wrap}
.pod{padding:.35em .7em;border-radius:8px;font-size:13px;font-weight:600}
.pod.ok{background:#163b2a;color:#9affc7}.pod.warn{background:#3a3413;color:#ffe08a}
.pod.miss{background:#5a1d1d;color:#ffb3b3}
.recbtn{width:100%;height:48px;border-radius:12px;border:1px solid #233344;background:linear-gradient(#16222e,#0d161e);color:#7fd1ff;font-size:15px}
.wrap{display:flex;gap:16px;justify-content:center;align-items:flex-start;max-width:1300px;margin:0 auto}
.left{flex:0 1 460px;max-width:460px;width:100%}
.recpanel{display:none;flex:0 0 50%;max-width:760px;position:sticky;top:10px}
.recpanel.on{display:block}
.recbar{display:flex;align-items:center;gap:12px;margin-bottom:8px}
.recbar button{background:#1d3a5a;color:#cfe6ff;border:none;border-radius:8px;padding:.5em .9em;font-size:14px}
.recframe{width:100%;height:62vh;border:1px solid #20303d;border-radius:10px;background:#0b1020;display:block}
@media(max-width:820px){.wrap{flex-direction:column;align-items:stretch}.left,.recpanel{flex:none;max-width:100%}.recframe{height:70vh}}
</style></head><body>
<div class=wrap>
<div class=left>
<h1>&#9875;&nbsp; __SHIP__ &middot; Audio</h1>
<div class=sub id=sub>VHF-MONITOR &amp; AIRPLAY</div>
<div class=panel>

  <div class=card>
    <div class=mlab style="display:flex;justify-content:space-between;align-items:center">
      <span>Funk-Pegel</span><span id=rxind class=rxind>FUNK AKTIV</span></div>
    <div class="meter vu"><div id=lvl></div><span id=pk class=pk></span></div>
  </div>

  <div class=card id=reccard style="padding:0;overflow:hidden">
    <button id=recbtn2 onclick="toggleCompact()" style="width:100%;background:none;border:none;color:#7fd1ff;font-size:15px;text-align:left;padding:14px 16px;display:flex;align-items:center;gap:8px;cursor:pointer">
      <span>&#9835; Nachh&ouml;ren letzte Funkspr&uuml;che</span>
      <span id=rectgt style="color:#6f8497;font-size:12px">&middot; auf die HomePods</span>
      <span id=recchev style="margin-left:auto">&#9662;</span></button>
    <div id=reclist class=reclist style="margin:0 16px 14px"></div>
  </div>

  <div class=card>
    <div class=mlab>Messe-Monitor (latenzarm)</div>
    <div class=btns>
      <button class=tg id=bmon><span class=dot></span>Live-Monitor<span class=sub2>VHF &rarr; Messe-Lautsprecher</span></button>
    </div>
    <div class=fader><label>Lautst&auml;rke</label><input type=range id=smon min=0 max=100 step=1><span class=val id=vmon>38</span></div>
  </div>

  <div class=card id=hpcard>
    <div class=mlab>VHF-&Uuml;bernahme (HomePods)</div>
    <div id=podnet class=podnet></div>
    <div class=fader><label>Lautst&auml;rke</label><input type=range id=shp min=0 max=100 step=1><span class=val id=vhp>60</span></div>
    <div class=fader><label>Verz&ouml;gerung</label><input type=range id=sdelay min=0 max=30 step=0.5><span class=val id=vdelay>7.0 s</span></div>
    <div class=btns><button class=tg id=bmute><span class=dot></span>Funk nachh&ouml;ren<span class=sub2>nicht live &ndash; nur sp&auml;ter nachh&ouml;ren</span></button></div>
    <div class=desc>Echter Funk wird kurz auf die HomePods gespielt (in dieser Lautst&auml;rke), dann wieder freigegeben. St&ouml;rungen werden ignoriert. Bei <b>nachh&ouml;ren</b> l&auml;uft die Aufnahme + das VU-Meter weiter, aber die HomePods bleiben live unber&uuml;hrt &ndash; du h&ouml;rst den Funk &uuml;ber die Aufnahmen-Liste nach.</div>
    <div id=shipodstat class=shipodstat></div>
  </div>

  <button class=recbtn id=recbtn onclick="toggleRecs()" style="position:sticky;top:8px;z-index:6">&#9835; Alle Aufnahmen &ndash; am Ger&auml;t anh&ouml;ren &#9662;</button>
  <div id=recwrap style="display:none">
    <div id=recspin style="text-align:center;padding:1.2em;color:#8fa2b6"><span class=spin></span> l&auml;dt &hellip;</div>
    <iframe id=recframe class=recframe title=Aufnahmen style="display:none"></iframe>
  </div>

</div>
</div>
</div>

<script>
const $=id=>document.getElementById(id);
const FAD={
  delay:{el:$('sdelay'), out:$('vdelay'), fmt:v=>(+v).toFixed(1)+' s'},
  hpvol:{el:$('shp'),   out:$('vhp'),    fmt:v=>String(Math.round(v))},
  monvol:{el:$('smon'), out:$('vmon'),   fmt:v=>String(Math.round(v))}
};
let lastInput={};   // key -> timestamp, um Server-Updates kurz zu unterdruecken
let postTimer=null, pending={};
function send(k,v){pending[k]=v;if(postTimer)return;postTimer=setTimeout(async()=>{
  const p={...pending};pending={};postTimer=null;
  const q=Object.entries(p).map(([a,b])=>a+'='+encodeURIComponent(b)).join('&');
  try{await fetch('/api/set?'+q,{method:'POST'});}catch(e){}
},120);}
for(const k in FAD){const f=FAD[k];
  f.el.addEventListener('input',()=>{lastInput[k]=Date.now();
    f.out.textContent=f.fmt(f.el.value);send(k,f.el.value);});}

function setFader(k,v){const f=FAD[k];
  if(Date.now()-(lastInput[k]||0)<1500)return;   // User regelt gerade
  f.el.value=v;f.out.textContent=f.fmt(v);}

function tgl(id,name){const b=$(id);b._on=false;
  b._set=v=>{b._on=v;b.classList.toggle('on',v);};
  b.addEventListener('click',async()=>{b._set(!b._on);
    try{await fetch('/api/svc?name='+name+'&on='+(b._on?1:0),{method:'POST'});}catch(e){}});
  return b;}
const bmon=tgl('bmon','monitor');

const bmute=$('bmute');let muteTs=0;bmute._on=false;
bmute._set=v=>{bmute._on=v;bmute.classList.toggle('on',v);};
bmute.addEventListener('click',async()=>{muteTs=Date.now();bmute._set(!bmute._on);
  try{await fetch('/api/mute?on='+(bmute._on?1:0),{method:'POST'});}catch(e){}});

async function poll(){try{const r=await fetch('/api/state');const s=await r.json();
  if(s.delay!=null)setFader('delay',s.delay);
  if(s.hpvol!=null)setFader('hpvol',s.hpvol);
  if(s.monvol!=null)setFader('monvol',s.monvol);
  bmon._set(!!s.monitor);
  if(s.mute!=null&&Date.now()-muteTs>1500)bmute._set(!!s.mute);
  applyPods(s.pods!==false);
  renderPodNet(s.pods_net);
  renderPods(s.shipods||[]);
}catch(e){}}

function applyPods(on){                 // keine HomePods an Bord -> HomePod-Karte weg, Kompakt-Liste bleibt (Messe)
  const hp=$('hpcard'); if(hp) hp.style.display=on?'':'none';
  const rt=$('rectgt'); if(rt) rt.textContent=on?'· auf die HomePods':'· auf die Messe';
  const sub=$('sub'); if(sub) sub.textContent=on?'VHF-MONITOR · AIRPLAY':'VHF-MONITOR · MESSE';}

let recOpen=false;                       // Kompakt-Liste oben: ein-/ausklappbar, default aus
function toggleCompact(){
  recOpen=!recOpen;
  $('reclist').classList.toggle('open',recOpen);
  $('recchev').innerHTML=recOpen?'&#9652;':'&#9662;';
  if(recOpen)recPoll();}

function toggleRecs(){                   // Aufnahmen-Liste ein-/ausklappen; lazy beim 1. Mal
  const b=$('recbtn'), w=$('recwrap'), f=$('recframe'), sp=$('recspin');
  const open = (w.style.display==='none' || !w.style.display);
  const CH=' &#9662;', UP=' &#9652;', LBL='&#9835; Alle Aufnahmen &ndash; am Ger&auml;t anh&ouml;ren';
  if(open){
    w.style.display='block'; b.innerHTML=LBL+UP;
    if(!f.getAttribute('src')){          // erst beim ersten Öffnen laden (Warte-Cursor)
      sp.style.display='block'; f.style.display='none'; document.body.style.cursor='progress';
      f.onload=function(){sp.style.display='none'; f.style.display='block'; document.body.style.cursor='';
        b.scrollIntoView({block:'start'});};        // nach dem Laden Ansicht oben zeigen
      f.src='/rec/?embed=1';
    }
    setTimeout(function(){b.scrollIntoView({behavior:'smooth',block:'start'});},60);
  } else {
    w.style.display='none'; b.innerHTML=LBL+CH;
  }}

function renderPodNet(n){const e=$('podnet');if(!e)return;
  if(n&&(!n.bb||!n.sb)){
    const miss=[!n.bb?'BB':null,!n.sb?'SB':null].filter(Boolean).join(' + ');
    e.innerHTML='&#9888; HomePod '+miss+' nicht im Netz erreichbar &ndash; '
      +'Übernahme/Lautstärke gehen nicht. HomePod neu starten (kurz stromlos).';
    e.classList.add('warn');
  } else { e.classList.remove('warn'); }}

function renderPods(list){const c=$('shipodstat');if(!c)return;c.innerHTML='';
  list.forEach(p=>{const e=document.createElement('span');var ok=p.present;
    e.className='pod '+(ok?'ok':'miss');
    e.textContent=p.name.replace('ShiPod ','')+(ok?' erreichbar':' fehlt!');c.appendChild(e);});}

poll();setInterval(poll,1000);

let peak=0,peakTs=0,rxOn=false,rxTs=0;
const RX_THRESH=0.03;   // = Recorder-Schwelle (3% im Sprachband) => Funk wird aufgenommen
async function lvlPoll(){try{const r=await fetch('/api/level');const s=await r.json();
  const raw=s.level||0, v=Math.max(0,Math.min(1,raw*1.6));
  $('lvl').style.width=(v*100)+'%';
  const now=Date.now();
  if(v>=peak){peak=v;peakTs=now;}
  else if(now-peakTs>900){peak=Math.max(v,peak-0.05);}
  $('pk').style.left=(peak*100)+'%';
  if(raw>RX_THRESH){rxOn=true;rxTs=now;}
  else if(now-rxTs>800){rxOn=false;}        // kurzes Nachleuchten gegen Flackern
  $('rxind').classList.toggle('on',rxOn);
  updatePlay(s.play);
}catch(e){}}
lvlPoll();setInterval(lvlPoll,120);

// ---- Kompakte Liste (oben): tippen = auf die HomePods spielen, + gut/Stoerung ----
let playing=false, activeName=null;
async function stopPlay(){try{await fetch('/api/stop',{method:'POST'});}catch(e){}}
function updatePlay(p){
  const was=playing; playing=!!p; const list=$('reclist'); if(!list)return;
  if(!p){ if(was){list.querySelectorAll('.vu').forEach(e=>{e.parentElement.classList.remove('vuon');e.remove();});activeName=null;recPoll();} return; }
  if(!activeName)return;
  const row=list.querySelector('.rec[data-name="'+activeName+'"]'); if(!row)return;
  let ov=row.querySelector('.vu');
  if(!ov){ov=document.createElement('div');ov.className='vu';ov.title='Wiedergabe stoppen';
    ov.onclick=e=>{e.stopPropagation();stopPlay();};row.classList.add('vuon');row.appendChild(ov);}
  const env=p.env||[], frac=p.dur>0?Math.min(1,p.pos/p.dur):0;
  const bars=env.length?env.map((v,i)=>{const on=(i+0.5)/env.length<=frac;const h=Math.max(12,Math.round(v*100));
    return '<span style="flex:1;height:'+h+'%;background:'+(on?'#9affc7':'#33564a')+';border-radius:1px"></span>';}).join('')
    :'<span style="color:#9affc7;font-size:12px">spielt &hellip;</span>';
  ov.innerHTML='<span style="color:#ff9a9a;font-size:14px;flex:none">&#9632;</span>'
    +'<span style="flex:1;display:flex;align-items:flex-end;gap:1px;height:22px;min-width:0">'+bars+'</span>'
    +(p.dur?'<span style="flex:none;color:#9affc7;font-size:11px">'+Math.round(p.pos)+' / '+Math.round(p.dur)+' s</span>':'');
}
const PRIDE=['#e40303','#ff8c00','#ffed00','#22c55e','#2563eb','#750787'];
function agefmt(s){
  const p=n=>String(n).padStart(2,'0');
  if(s<60)return 'vor '+s+' sek';
  const m=Math.floor(s/60);
  if(m<60)return 'vor '+m+' min';
  const h=Math.floor(m/60), rm=m%60;
  if(h<24)return 'vor '+h+':'+p(rm)+' Std';
  const d=Math.floor(h/24), rh=h%24;
  return 'vor '+d+' T '+rh+':'+p(rm)+' Std';
}
async function recPoll(){if(playing||!recOpen)return;   // zu / Wiedergabe -> nicht neu aufbauen
  try{const r=await fetch('/api/recs');const list=await r.json();
  const c=$('reclist');if(!c)return;
  if(!list.length){c.innerHTML='<div class=rec style="opacity:.5;border-left-color:#444">noch keine</div>';return;}
  c.innerHTML=list.map((x,i)=>{const col=PRIDE[i%PRIDE.length];
    const n=x.name.replace(/'/g,"\\'");
    return '<div class="rec'+(x.noise?' noise':'')+'" data-name="'+x.name+'" style="border-left-color:'+col+'" onclick="replayFile(this,\''+n+'\')">'
      +'<span class=len>'+x.sec+' s</span>'
      +'<span class=meta>'+(x.t||'')+' &middot; '+agefmt(x.age)+(x.noise?' &middot; verworfen':'')+'</span>'
      +'<button class="ic good'+(x.noise?'':' cur')+'" title="Sprache (behalten)" onclick="event.stopPropagation();classify(\''+n+'\',\'speech\')">&#10003;</button>'
      +'<button class="ic bad'+(x.noise?' cur':'')+'" title="St&ouml;rung (verwerfen)" onclick="event.stopPropagation();classify(\''+n+'\',\'noise\')">&#10007;</button>'
      +'</div>';}).join('');
}catch(e){}}
recPoll();setInterval(recPoll,5000);
async function replayFile(el,name){
  activeName=name;   // Anzeigeort fuers VU = diese Zeile
  try{await fetch('/api/replay?file='+encodeURIComponent(name),{method:'POST'});}catch(e){}}
async function classify(name,as){
  try{await fetch('/api/classify?file='+encodeURIComponent(name)+'&as='+as,{method:'POST'});}catch(e){}
  recPoll();}
</script></body></html>'''

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _send(self, code, body, ctype="application/json"):
        b = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)
    def _proxy(self):
        # Reverse-Proxy /rec/... -> interne Nachhoer-Liste (vhf-web) auf WEB_PORT,
        # damit alles ueber Port 8090 erreichbar ist (kein zweiter offener Port noetig).
        sub = self.path[4:]                       # alles nach "/rec"
        if not sub.startswith("/"):
            sub = "/" + sub
        target = "http://127.0.0.1:%d%s" % (WEB_PORT, sub)
        data = None
        if self.command == "POST":
            n = int(self.headers.get("Content-Length", 0) or 0)
            data = self.rfile.read(n) if n else b""
        req = urllib.request.Request(target, data=data, method=self.command)
        ct = self.headers.get("Content-Type")
        if ct:
            req.add_header("Content-Type", ct)
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                self._send(r.status, r.read(),
                           r.headers.get("Content-Type", "application/octet-stream"))
        except urllib.error.HTTPError as e:
            self._send(e.code, e.read() or b"",
                       e.headers.get("Content-Type", "text/plain"))
        except Exception:
            self._send(502, "Nachhoer-Liste (vhf-web) nicht erreichbar", "text/plain")
    def do_GET(self):
        if self.path == "/" or self.path.startswith("/index"):
            page = PAGE.replace("__SHIP__", html.escape(resolve_shipname()))
            self._send(200, page, "text/html; charset=utf-8")
        elif self.path == "/rec" or self.path.startswith("/rec/"):
            self._proxy()
        elif self.path.startswith("/api/state"):
            self._send(200, json.dumps(state()))
        elif self.path.startswith("/api/level"):   # leichtgewichtig, schnelles VU-Polling
            self._send(200, json.dumps({"level": read_file_level(LEVEL_FILE),
                                        "play": play_info()}))
        elif self.path.startswith("/api/recs"):
            self._send(200, json.dumps(recent_recs()))
        else:
            self._send(404, "{}")
    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        if u.path == "/rec" or u.path.startswith("/rec/"):
            self._proxy(); return
        q = urllib.parse.parse_qs(u.query)
        if u.path == "/api/set":
            out = {}
            if "delay" in q:  out["delay"] = write_delay(q["delay"][0])
            if "hpvol" in q:  out["hpvol"] = set_hpvol(q["hpvol"][0])
            if "monvol" in q: out["monvol"] = set_monvol(q["monvol"][0])
            invalidate_cache()
            self._send(200, json.dumps(out))
        elif u.path == "/api/svc":
            unit = SERVICES.get(q.get("name", [""])[0])
            if not unit:
                self._send(400, "{}"); return
            on = q.get("on", ["1"])[0] not in ("0", "false", "off")
            set_svc(unit, on)
            invalidate_cache()
            self._send(200, json.dumps({"ok": on}))
        elif u.path == "/api/mute":
            on = q.get("on", ["1"])[0] not in ("0", "false", "off")
            self._send(200, json.dumps({"mute": set_mute(on)}))
        elif u.path == "/api/replay":
            f = q.get("file", [None])[0]
            self._send(200, json.dumps({"played": replay_file(f)}))
        elif u.path == "/api/stop":
            stop_playout()
            self._send(200, "{}")
        elif u.path == "/api/classify":
            f = q.get("file", [None])[0]
            as_ = q.get("as", [""])[0]
            stop_playout()   # beim Einordnen die laufende Wiedergabe stoppen
            self._send(200, json.dumps(classify_file(f, as_) or {}))
        else:
            self._send(404, "{}")

if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()

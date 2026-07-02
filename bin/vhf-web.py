#!/usr/bin/env python3
# VHF-Aufnahmen: Web-Liste. Abspielen, Download, und Markieren (ausgrauen) ohne
# Nachfrage; beim Verlassen der Seite werden die markierten geloescht.
# Laeuft OHNE root (in Gruppe audio); Loeschen via Verzeichnisrechte.
import os, re, html, json, time, subprocess, urllib.parse, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DIR = os.environ.get("VHF_DIR", "/srv/music/VHF-Aufnahmen")
PORT = int(os.environ.get("VHF_WEB_PORT", "8088"))
CONFIG_FILE = os.environ.get("VHF_CONFIG", "/etc/vhf/vhf.conf")

def read_config():
    # shipname: "auto" = aus Signal K holen; sonst woertlich (Override).
    cfg = {"shipname": "auto", "signalk": "http://localhost:3000"}
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
        name = (str(name).strip() or None) if name else None
    except Exception:
        name = None
    _sk_cache["t"] = now
    _sk_cache["name"] = name
    return name

def shipname():
    cfg = read_config()
    nm = cfg["shipname"]
    if nm.lower() != "auto":
        return nm                                    # expliziter Override
    return signalk_name(cfg["signalk"]) or "Wilhelmina"

LABELS_FILE = os.path.join(DIR, ".labels.txt")
LABEL_GROUPS = [
    ("A  &ndash; Haupthaufen (niedriger Centroid, stabile Tonh&ouml;he)",
     ["VHF_2026-06-27_04-43-30.mp3", "VHF_2026-06-27_05-10-17.mp3",
      "VHF_2026-06-27_05-12-05.mp3", "VHF_2026-06-27_07-27-02.mp3"]),
    ("B  &ndash; oberer Bereich (hoher Centroid, wandernde Tonh&ouml;he)",
     ["VHF_2026-06-27_07-52-09.mp3", "VHF_2026-06-27_10-08-24.mp3",
      "VHF_2026-06-27_12-00-24.mp3", "VHF_2026-06-27_12-13-42.mp3"]),
]

def read_labels():
    d = {}
    try:
        for ln in open(LABELS_FILE):
            parts = ln.split()
            if len(parts) == 2:
                d[parts[0]] = parts[1]
    except Exception:
        pass
    return d

def label_page():
    lab = read_labels()
    secs = []
    for title, files in LABEL_GROUPS:
        rows = []
        for f in files:
            base = f[4:-4]; dd, _, tt = base.partition("_"); tt = tt.replace("-", ":")
            fe = html.escape(f); cur = lab.get(f, "")
            rows.append(
                "<li data-f=\"%s\"><div class=hd><span class=t>%s&nbsp;&nbsp;%s</span>"
                "<span class=cur>%s</span></div>"
                "<audio controls preload=none src=\"%s\"></audio>"
                "<div class=lb><button class=st onclick=\"setl(this,'stoerung')\">St&ouml;rung</button>"
                "<button class=ec onclick=\"setl(this,'echt')\">echt</button></div></li>"
                % (fe, html.escape(dd), html.escape(tt),
                   ("&rarr; " + cur) if cur else "", fe))
        secs.append("<h3>%s</h3><ul>%s</ul>" % (title, "".join(rows)))
    return ("<!doctype html><html lang=de><head><meta charset=utf-8>"
            "<meta name=viewport content=\"width=device-width,initial-scale=1\">"
            "<title>VHF beurteilen</title><style>"
            "body{font-family:system-ui,sans-serif;max-width:760px;margin:0 auto;padding:1em;"
            "background:#0b1020;color:#e6e9f0}h2,h3{margin:.4em 0}ul{padding:0}"
            "li{list-style:none;background:#161c33;border-radius:10px;padding:.6em .8em;margin:.55em 0}"
            ".hd{display:flex;gap:10px;align-items:center}.t{font-weight:600}"
            ".cur{margin-left:auto;color:#ffce6b;font-size:.9em}audio{width:100%;margin:.45em 0}"
            ".lb{display:flex;gap:10px}.lb button{flex:1;border:none;border-radius:8px;padding:.6em;font-size:15px}"
            ".st{background:#5a1d1d;color:#ffd9d9}.ec{background:#163b2a;color:#d9ffe9}"
            ".lb button.on{outline:3px solid #fff}</style></head><body>"
            "<h2>&#9875; Aufnahmen beurteilen</h2>"
            "<p style=color:#9aa3bd>Jede anh&ouml;ren, dann <b>St&ouml;rung</b> oder <b>echt</b> tippen.</p>"
            + "".join(secs) +
            "<script>async function setl(b,l){var li=b.closest('li');"
            "await fetch('setlabel?f='+encodeURIComponent(li.dataset.f)+'&l='+l,{method:'POST'});"
            "li.querySelectorAll('.lb button').forEach(function(x){x.classList.remove('on');});"
            "b.classList.add('on');"
            "li.querySelector('.cur').textContent='\\u2192 '+l;}"
            "</script></body></html>")

def recordings():
    try:
        fs = [f for f in os.listdir(DIR) if f.startswith("VHF_") and f.endswith(".mp3")]
    except Exception:
        fs = []
    return sorted(fs, reverse=True)

def safe(name):
    return ("/" not in name and "\\" not in name
            and name.startswith("VHF_") and name.endswith(".mp3")
            and os.path.isfile(os.path.join(DIR, name)))

def noise_list():
    try:
        fs = [f for f in os.listdir(DIR) if f.startswith(".noise-VHF_") and f.endswith(".mp3")]
    except Exception:
        fs = []
    return sorted(fs, reverse=True)

def safe_noise(name):
    return ("/" not in name and "\\" not in name
            and name.startswith(".noise-VHF_") and name.endswith(".mp3")
            and os.path.isfile(os.path.join(DIR, name)))

def dur_str(path):
    # Laufzeit aus Dateigroesse schaetzen (MP3 CBR 96 kbit/s = 12000 B/s)
    try:
        s = os.path.getsize(path) * 8.0 / 96000.0
    except Exception:
        return "?"
    if s < 60:
        return "%.0f s" % s
    return "%d:%02d" % (int(s // 60), int(s % 60))

def owntone_update():
    try:
        urllib.request.urlopen(urllib.request.Request(
            "http://localhost:3689/api/update", method="PUT"), timeout=3).read()
    except Exception:
        pass

def _dt(f):
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})_(\d{2})-(\d{2})-(\d{2})", f)
    if not m:
        return ("", "")
    return ("%s-%s-%s" % (m.group(1), m.group(2), m.group(3)),
            "%s:%s:%s" % (m.group(4), m.group(5), m.group(6)))

def all_recs(limit=80):
    # echte + aussortierte Aufnahmen in EINER Liste, neueste zuerst.
    try:
        fs = [f for f in os.listdir(DIR) if f.endswith(".mp3")
              and (f.startswith("VHF_") or f.startswith(".noise-VHF_"))]
    except Exception:
        fs = []
    def mt(f):
        try:
            return os.path.getmtime(os.path.join(DIR, f))
        except Exception:
            return 0
    fs.sort(key=mt, reverse=True)
    return fs[:limit]

_env_cache = {}

def compute_env(name):
    # Huellkurve (48 Balken, 0..1) fuer die VU-Uebersicht pro Zeile; gecacht.
    if name in _env_cache:
        return _env_cache[name]
    res = {"dur": 0, "env": []}
    try:
        import numpy as np
        path = os.path.join(DIR, name)
        p = subprocess.run(["ffmpeg", "-v", "quiet", "-i", path, "-ac", "1",
                            "-ar", "8000", "-f", "s16le", "-"],
                           capture_output=True, timeout=20)
        x = np.frombuffer(p.stdout, dtype=np.int16).astype(np.float32) / 32768.0
        dur = len(x) / 8000.0
        N = 48
        segs = np.array_split(np.abs(x), N) if len(x) >= N else [np.abs(x)]
        env = [float(np.sqrt(np.mean(s * s + 1e-9))) for s in segs]
        mx = max(env) or 1.0
        res = {"dur": round(dur, 2), "env": [round(min(1.0, e / mx), 3) for e in env]}
    except Exception:
        res = {"dur": 0, "env": []}
    if len(_env_cache) > 300:
        _env_cache.clear()
    _env_cache[name] = res
    return res

def classify_file(name, as_):
    # VHF_x.mp3  <->  .noise-VHF_x.mp3  (gut / Stoerung), Zustand steckt im Namen.
    if "/" in name or "\\" in name or not name.endswith(".mp3"):
        return None
    if name.startswith(".noise-VHF_"):
        bare = name[len(".noise-"):]
    elif name.startswith("VHF_"):
        bare = name
    else:
        return None
    dst = (".noise-" + bare) if as_ == "noise" else bare
    src = os.path.join(DIR, name); dstp = os.path.join(DIR, dst)
    if not os.path.isfile(src):
        return None
    if src != dstp:
        try:
            os.replace(src, dstp)
            owntone_update()
        except Exception:
            return None
    return {"name": dst, "noise": dst.startswith(".noise-")}

def page(embed=False):
    ship = html.escape(shipname())
    # Eingebettet (im Panel-iframe): eigene Titelzeile weglassen (kein Doppelkopf).
    hdr = "" if embed else ("<h1>&#9875;&nbsp; " + ship + " &middot; Audio</h1>"
                            "<div class=sub>VHF &middot; NACHH&Ouml;REN</div>")
    rows = []
    for f in all_recs():
        noise = f.startswith(".noise-")
        d, t = _dt(f)
        du = dur_str(os.path.join(DIR, f))
        fe = html.escape(f)
        rows.append(
            "<li class=\"rec%s\" data-f=\"%s\" data-noise=\"%d\">"
            "<div class=hd><span class=t>%s&nbsp;&nbsp;%s</span><span class=s>%s</span></div>"
            "<div class=ctl>"
            "<button class=play aria-label=Abspielen onclick=\"play(this)\">&#9654;</button>"
            "<div class=vu></div>"
            "<button class=\"cl gut%s\" onclick=\"cls(this,'speech')\">gut</button>"
            "<button class=\"cl st%s\" onclick=\"cls(this,'noise')\">St&ouml;rung</button>"
            "<a class=dlb href=\"%s\" download title=Download>&#11015;</a>"
            "</div>"
            "<audio preload=none src=\"%s\"></audio></li>"
            % (" noise" if noise else "", fe, 1 if noise else 0,
               html.escape(d), html.escape(t), du,
               "" if noise else " on", " on" if noise else "", fe, fe))
    if not rows:
        rows = ["<li class=s style=\"text-align:center;color:#8fa2b6\">Noch keine Aufnahmen.</li>"]

    return ("<!doctype html><html lang=de><head><meta charset=utf-8>"
            "<meta name=viewport content=\"width=device-width,initial-scale=1\">"
            "<title>VHF-Aufnahmen</title><style>"
            "*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}"
            ":root{--brass:#caa45a;--accent:#ffce6b;--ok:#46d17a}"
            "body{margin:0;font-family:ui-sans-serif,system-ui,Segoe UI,Roboto,sans-serif;"
            "background:radial-gradient(120% 120% at 50% -10%,#1c2c39,#0b121a 60%,#070b10);"
            "color:#e8eef4;min-height:100vh;padding:16px 14px 28px}"
            "h1{font-size:14px;letter-spacing:.3em;font-weight:600;color:#bcd2e6;margin:2px 0 0;"
            "text-transform:uppercase;text-align:center}"
            ".sub{font-size:10px;color:#6f8497;letter-spacing:.18em;text-align:center;margin:2px 0 16px}"
            ".panel{max-width:620px;margin:0 auto}"
            ".hint{font-size:12px;color:#9aa3bd;line-height:1.5;margin:0 0 14px;text-align:center}"
            "ul{padding:0;margin:0;list-style:none}"
            "li{background:#111a24;border:1px solid #20303d;border-radius:12px;padding:.6em .8em;margin:.55em 0}"
            "li.noise{opacity:.72}"
            ".hd{display:flex;align-items:baseline;gap:10px}.t{font-weight:600;color:#eaf2fa}"
            ".s{color:#8fa2b6;font-size:.85em;font-variant-numeric:tabular-nums;margin-left:auto}"
            ".ctl{display:flex;align-items:center;gap:8px;margin-top:.55em}"
            ".play{flex:none;width:42px;height:42px;border-radius:50%;border:1px solid #2f4a63;"
            "background:linear-gradient(#16222e,#0d161e);color:var(--accent);font-size:15px;cursor:pointer}"
            ".play.playing{color:#9affc7;border-color:#2f7d53;background:linear-gradient(#163b2a,#0f261c)}"
            ".vu{flex:1;min-width:0;height:42px;display:flex;align-items:flex-end;gap:1px;overflow:hidden;"
            "background:#0b141c;border:1px solid #20303d;border-radius:8px;padding:3px}"
            ".vu .b{flex:1;min-width:1px;background:#33564a;border-radius:1px;min-height:2px;transition:background .05s}"
            ".vu .b.on{background:var(--accent)}"
            ".cl{flex:none;border-radius:8px;padding:0 .7em;height:42px;font-size:13px;font-weight:600;"
            "background:#0e1922;color:#9fb4c6;border:1px solid #2a3a49;cursor:pointer}"
            ".gut.on{background:#163b2a;color:#9affc7;border-color:#2f7d53}"
            ".st.on{background:#5a1d1d;color:#ffd9d9;border-color:#9c3b3b}"
            ".dlb{flex:none;width:42px;height:42px;display:flex;align-items:center;justify-content:center;"
            "color:var(--accent);text-decoration:none;font-size:1.2em;background:#0e1922;border:1px solid #2a3a49;border-radius:8px}"
            "@media(max-width:480px){.cl{padding:0 .5em;font-size:12px}.play,.vu,.cl,.dlb{height:38px}.play,.dlb{width:38px}}"
            "</style></head><body>"
            + hdr +
            "<div class=panel>"
            "<p class=hint>&#9654; Abspielen &middot; Wellenform &middot; <b>gut</b>/<b>St&ouml;rung</b> einordnen &middot; &#11015; Download</p>"
            "<ul id=list>" + "".join(rows) + "</ul></div>"
            "<script>"
            "var q=function(s,r){return (r||document).querySelector(s);};"
            "var curA=null;"
            "function bars(vu,env){vu.innerHTML='';"
            "var a=(env&&env.length)?env:[];if(!a.length){for(var i=0;i<40;i++)a.push(0.12);}"
            "a.forEach(function(v){var b=document.createElement('span');b.className='b';"
            "b.style.height=Math.max(2,Math.round(v*100))+'%';vu.appendChild(b);});}"
            "function setProg(vu,frac){var bs=vu.querySelectorAll('.b');var idx=Math.round(frac*bs.length);"
            "for(var i=0;i<bs.length;i++)bs[i].classList.toggle('on',i<idx);}"
            "async function loadEnv(li){if(li._env)return;li._env=1;var vu=q('.vu',li);"
            "try{var r=await fetch('env?f='+encodeURIComponent(li.dataset.f));var d=await r.json();"
            "if(d&&d.env&&d.env.length)bars(vu,d.env);}catch(e){}}"
            "var io=new IntersectionObserver(function(es){es.forEach(function(e){"
            "if(e.isIntersecting){loadEnv(e.target);io.unobserve(e.target);}});},{rootMargin:'150px'});"
            "document.querySelectorAll('#list>li.rec').forEach(function(li){"
            "bars(q('.vu',li),null);io.observe(li);"
            "var a=q('audio',li),btn=q('.play',li),vu=q('.vu',li);"
            "a.addEventListener('play',function(){if(curA&&curA!==a)curA.pause();curA=a;"
            "btn.classList.add('playing');btn.innerHTML='&#9208;';});"
            "a.addEventListener('pause',function(){btn.classList.remove('playing');btn.innerHTML='&#9654;';});"
            "a.addEventListener('ended',function(){setProg(vu,0);});"
            "a.addEventListener('timeupdate',function(){if(a.duration)setProg(vu,a.currentTime/a.duration);});"
            "});"
            "function play(btn){var a=q('audio',btn.closest('li'));if(a.paused){a.play();}else{a.pause();}}"
            "async function cls(btn,as){var li=btn.closest('li');"
            "var r=await fetch('classify?f='+encodeURIComponent(li.dataset.f)+'&as='+as,{method:'POST'});"
            "if(!r.ok)return;var d=await r.json();if(!d.name)return;"
            "li.dataset.f=d.name;li.dataset.noise=d.noise?'1':'0';"
            "q('audio',li).src=d.name;q('.dlb',li).setAttribute('href',d.name);"
            "li.classList.toggle('noise',!!d.noise);"
            "q('.gut',li).classList.toggle('on',!d.noise);"
            "q('.st',li).classList.toggle('on',!!d.noise);}"
            "</script></body></html>")

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        p = urllib.parse.urlparse(self.path)
        name = urllib.parse.unquote(p.path.lstrip("/"))
        if p.path in ("/", "") or p.path == "/label":
            if p.path == "/label":
                b = label_page().encode()
            else:
                embed = "embed" in urllib.parse.parse_qs(p.query)
                b = page(embed).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers(); self.wfile.write(b)
        elif p.path == "/env":
            q = urllib.parse.parse_qs(p.query)
            f = q.get("f", [""])[0]
            if safe(f) or safe_noise(f):
                b = json.dumps(compute_env(f)).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(b)))
                self.end_headers(); self.wfile.write(b)
            else:
                self.send_response(404); self.end_headers()
        elif safe(name) or safe_noise(name):
            fp = os.path.join(DIR, name)
            self.send_response(200)
            self.send_header("Content-Type", "audio/mpeg")
            self.send_header("Content-Length", str(os.path.getsize(fp)))
            self.end_headers()
            with open(fp, "rb") as fh:
                while True:
                    chunk = fh.read(65536)
                    if not chunk: break
                    self.wfile.write(chunk)
        else:
            self.send_response(404); self.end_headers()
    def do_POST(self):
        p = urllib.parse.urlparse(self.path)
        if p.path == "/classify":
            q = urllib.parse.parse_qs(p.query)
            f = q.get("f", [""])[0]; as_ = q.get("as", [""])[0]
            res = classify_file(f, as_) if as_ in ("speech", "noise") else None
            b = json.dumps(res or {}).encode()
            self.send_response(200 if res else 400)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers(); self.wfile.write(b)
        elif p.path == "/commit":
            try:
                n = int(self.headers.get("Content-Length", 0))
                names = json.loads(self.rfile.read(n) or b"[]")
            except Exception:
                names = []
            moved = 0
            for name in names if isinstance(names, list) else []:
                if isinstance(name, str) and safe(name):
                    try:  # NICHT loeschen, nur verstecken (rueckholbar)
                        os.rename(os.path.join(DIR, name),
                                  os.path.join(DIR, ".noise-" + name)); moved += 1
                    except Exception:
                        pass
            if moved:
                owntone_update()
            self.send_response(200); self.end_headers()
        elif p.path == "/restore":
            q = urllib.parse.parse_qs(p.query)
            name = q.get("f", [""])[0]
            if safe_noise(name):
                try:
                    os.rename(os.path.join(DIR, name),
                              os.path.join(DIR, name[len(".noise-"):]))  # .noise-VHF_.. -> VHF_..
                    owntone_update()
                    self.send_response(200)
                except Exception:
                    self.send_response(500)
            else:
                self.send_response(400)
            self.end_headers()
        elif p.path == "/setlabel":
            q = urllib.parse.parse_qs(p.query)
            f = q.get("f", [""])[0]; l = q.get("l", [""])[0]
            if (safe(f) or safe_noise(f)) and l in ("stoerung", "echt"):
                try:
                    with open(LABELS_FILE, "a") as fh:
                        fh.write("%s %s\n" % (f, l))
                    self.send_response(200)
                except Exception:
                    self.send_response(500)
            else:
                self.send_response(400)
            self.end_headers()
        else:
            self.send_response(404); self.end_headers()

if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()

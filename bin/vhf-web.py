#!/usr/bin/env python3
# VHF-Aufnahmen: Web-Liste. Abspielen, Download, und Markieren (ausgrauen) ohne
# Nachfrage; beim Verlassen der Seite werden die markierten geloescht.
# Laeuft OHNE root (in Gruppe audio); Loeschen via Verzeichnisrechte.
import os, html, json, urllib.parse, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DIR = os.environ.get("VHF_DIR", "/srv/music/VHF-Aufnahmen")
PORT = int(os.environ.get("VHF_WEB_PORT", "8088"))
CONFIG_FILE = os.environ.get("VHF_CONFIG", "/etc/vhf/vhf.conf")

def shipname():
    # Schiffsname aus /etc/vhf/vhf.conf (key=value); Default falls nicht gesetzt.
    try:
        for ln in open(CONFIG_FILE):
            ln = ln.strip()
            if ln.startswith("shipname") and "=" in ln:
                v = ln.partition("=")[2].strip()
                if v:
                    return v
    except Exception:
        pass
    return "Wilhelmina"

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
            "await fetch('/setlabel?f='+encodeURIComponent(li.dataset.f)+'&l='+l,{method:'POST'});"
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

def page():
    ship = html.escape(shipname())
    rows = []
    for f in recordings():
        base = f[4:-4]
        d, _, t = base.partition("_")
        t = t.replace("-", ":")
        du = dur_str(os.path.join(DIR, f))
        fe = html.escape(f)
        rows.append(
            "<li data-f=\"%s\"><div class=hd>"
            "<span class=cb onclick=\"sel(event,this)\"></span>"
            "<button class=del onclick=\"mark(this)\">&#10005;</button>"
            "<span class=t>%s&nbsp;&nbsp;%s</span>"
            "<span class=s>%s</span>"
            "<a class=dl href=\"%s\" download>&#11015;</a></div>"
            "<audio controls preload=none src=\"%s\"></audio></li>"
            % (fe, html.escape(d), html.escape(t), du, fe, fe))
    if not rows:
        rows = ["<li class=s>Noch keine Aufnahmen.</li>"]

    nrows = []
    for f in noise_list():
        base = f[len(".noise-VHF_"):-4]
        d, _, t = base.partition("_")
        t = t.replace("-", ":")
        fe = html.escape(f)
        du = dur_str(os.path.join(DIR, f))
        nrows.append(
            "<li data-f=\"%s\"><div class=hd>"
            "<span class=t>%s&nbsp;&nbsp;%s</span><span class=s>St&ouml;rung &middot; %s</span></div>"
            "<audio controls preload=none src=\"%s\"></audio>"
            "<button class=res onclick=\"restore(this)\">&#8617; echte Sprache</button></li>"
            % (fe, html.escape(d), html.escape(t), du, fe))
    noise_section = ""
    if nrows:
        noise_section = ("<details><summary class=s>Aussortiert / ausgeblendet (%d) &ndash; "
                         "anh&ouml;ren / als echt zur&uuml;ckholen</summary><ul id=noise>%s</ul></details>"
                         % (len(nrows), "".join(nrows)))

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
            ".panel{max-width:560px;margin:0 auto}"
            ".hint{font-size:12px;color:#9aa3bd;line-height:1.5;margin:0 0 14px;text-align:center}"
            "ul{padding:0;margin:0;list-style:none}"
            "li{background:#111a24;border:1px solid #20303d;border-radius:12px;padding:.6em .8em;margin:.55em 0}"
            "li.marked{opacity:.4}li.marked .t{text-decoration:line-through}"
            ".hd{display:flex;align-items:center;gap:10px}.t{font-weight:600;color:#eaf2fa}"
            ".s{color:#8fa2b6;font-size:.85em;font-variant-numeric:tabular-nums}"
            ".dl{margin-left:auto;color:var(--accent);text-decoration:none;font-size:1.25em}"
            ".del{background:#5a1d1d;color:#ffd9d9;border:1px solid #9c3b3b;border-radius:7px;width:34px;height:30px;font-size:15px}"
            ".del:active{background:#7a2626}li.marked .del{background:#20303d;color:#9aa3bd;border-color:#2a3a49}"
            ".res{display:block;width:100%;margin-top:.5em;background:linear-gradient(#163b2a,#0f261c);color:#d9ffe9;"
            "border:1px solid #2f7d53;border-radius:9px;padding:.7em;font-size:15px;font-weight:600;letter-spacing:.02em}.res:active{background:#0f261c}"
            ".cb{flex:0 0 auto;width:22px;height:22px;border:2px solid #3a4a63;border-radius:5px;cursor:pointer}"
            "li.sel .cb{background:var(--accent);border-color:var(--accent)}li.sel{outline:2px solid var(--accent)}"
            ".bar{position:sticky;top:8px;z-index:5;background:rgba(11,18,26,.92);backdrop-filter:blur(6px);"
            "border:1px solid #20303d;border-radius:12px;padding:.5em .7em;margin-bottom:.5em;"
            "display:none;align-items:center;gap:8px;flex-wrap:wrap}.bar.on{display:flex}"
            ".bar .cnt{font-weight:600;color:var(--accent)}.bar button{background:#1d3a5a;color:#cfe6ff;border:none;"
            "border-radius:8px;padding:.5em .8em;font-size:14px}.bar .rng.active{background:#2f7d53;color:#dfffe9}"
            ".bar .hide{background:#5a1d1d;color:#ffd9d9}"
            "details{margin-top:1.2em}summary{cursor:pointer;color:#8fa2b6}audio{width:100%;margin-top:.5em}"
            "</style></head><body>"
            "<h1>&#9875;&nbsp; " + ship + " &middot; Audio</h1>"
            "<div class=sub>VHF &middot; NACHH&Ouml;REN</div>"
            "<div class=panel>"
            "<p class=hint>Antippen zum Abh&ouml;ren &middot; &#11015; Download &middot; &#10005; einzeln ausblenden &middot; "
            "&#9744; Mehrfachauswahl. Ausgeblendete werden beim Verlassen nur versteckt &ndash; nichts wird gel&ouml;scht.</p>"
            "<div class=bar id=bar><span class=cnt id=cnt>0 ausgew&auml;hlt</span>"
            "<button class=rng id=rng onclick=\"toggleRange(this)\">&#8597; Bereich</button>"
            "<button class=hide onclick=\"hideSel()\">Ausblenden</button>"
            "<button onclick=\"clearSel()\">Aufheben</button></div>"
            "<ul id=list>" + "".join(rows) + "</ul>" + noise_section + "</div>" +
            "<script>"
            "var items=[].slice.call(document.querySelectorAll('#list>li'));"
            "var anchor=-1,rangeMode=false;"
            "function updBar(){var s=document.querySelectorAll('#list>li.sel').length;"
            "document.getElementById('bar').classList.toggle('on',s>0);"
            "document.getElementById('cnt').textContent=s+' ausgew\\u00e4hlt';}"
            "function sel(e,el){var li=el.closest('li');var i=items.indexOf(li);"
            "if((e.shiftKey||rangeMode)&&anchor>=0){var lo=Math.min(anchor,i),hi=Math.max(anchor,i);"
            "for(var k=lo;k<=hi;k++)items[k].classList.add('sel');}"
            "else{li.classList.toggle('sel');}anchor=i;updBar();}"
            "function hideSel(){[].slice.call(document.querySelectorAll('#list>li.sel')).forEach(function(li){"
            "li.classList.add('marked');li.classList.remove('sel');var a=li.querySelector('audio');"
            "if(a){a.pause();}});anchor=-1;updBar();}"
            "function clearSel(){[].slice.call(document.querySelectorAll('#list>li.sel')).forEach("
            "function(li){li.classList.remove('sel');});updBar();}"
            "function toggleRange(b){rangeMode=!rangeMode;b.classList.toggle('active',rangeMode);}"
            "function mark(btn){var li=btn.closest('li');li.classList.toggle('marked');"
            "if(li.classList.contains('marked')){var a=li.querySelector('audio');"
            "if(a){a.pause();try{a.currentTime=0;}catch(e){}}}}"
            "function commit(){var m=[].slice.call(document.querySelectorAll('li.marked'))"
            ".map(function(li){return li.dataset.f;});"
            "if(m.length){try{navigator.sendBeacon('/commit',JSON.stringify(m));}catch(e){}}}"
            "window.addEventListener('pagehide',commit);"
            "window.addEventListener('beforeunload',commit);"
            "async function restore(btn){var li=btn.closest('li');"
            "var r=await fetch('/restore?f='+encodeURIComponent(li.dataset.f),{method:'POST'});"
            "if(r.ok){li.remove();}else{alert('Wiederherstellen fehlgeschlagen');}}"
            "</script></body></html>")

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        p = urllib.parse.urlparse(self.path)
        name = urllib.parse.unquote(p.path.lstrip("/"))
        if p.path in ("/", "") or p.path == "/label":
            b = (label_page() if p.path == "/label" else page()).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers(); self.wfile.write(b)
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
        if p.path == "/commit":
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

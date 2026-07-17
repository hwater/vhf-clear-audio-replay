#!/opt/pyatv-venv/bin/python3
# VHF pyatv-Playout-Daemon — haelt pyatv IMPORTIERT (spart ~1.5-2s Kaltstart pro
# Uebernahme) und streamt Funk-Clips per RAOP auf beide ShiPods (Dual-Mono).
#
# Warum: OwnTone crasht bei diesen HomePods; pyatv per `atvremote` funktioniert, ist
# aber ~5s langsam (Python/pyatv-Import bei jedem Aufruf). Dieser residente Dienst
# haelt pyatv warm -> Klick-bis-Ton ~2.5s (Connect ~0.5s + HomePod-AirPlay-Puffer ~2s).
#
# Steuerung: atomar eine Zeile "MODE\tPATH" nach /run/vhf/playreq schreiben.
#   MODE = now  -> sofort (Funkwiederholung); unterbricht eine laufende Wiedergabe
#          auto -> respektiert /run/vhf/mute + /var/lib/vhf/delay (Auto-Uebernahme)
#          stop -> laufende Wiedergabe abbrechen
# Setzt /run/vhf/playing (Basename) fuers VU-Overlay im Panel.
import asyncio, os
import pyatv

BB = "FE:A2:7C:85:A9:5C"          # ShiPod BB (pyatv/AirPlay-Identifier)
SB = "A2:AE:9B:32:35:0A"          # ShiPod SB
HOST = {BB: "ShiPod-BB.local", SB: "ShiPod-SB.local"}
REQ = "/run/vhf/playreq"
PLAYING = "/run/vhf/playing"

def rd(path, default=""):
    try:
        return open(path).read().strip()
    except Exception:
        return default

def hpvol():
    try:
        return max(0, min(100, int(rd("/var/lib/vhf/hpvol", "40"))))
    except Exception:
        return 40

async def resolve_ip(host):
    # avahi-resolve -4 -> gezielter (schneller) pyatv-Scan statt Broadcast
    try:
        p = await asyncio.create_subprocess_exec(
            "avahi-resolve", "-4", "-n", host,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
        out, _ = await asyncio.wait_for(p.communicate(), 2)
        parts = out.split()
        return parts[1].decode() if len(parts) >= 2 else None
    except Exception:
        return None

async def stream_one(loop, ident, path, vol):
    try:
        ip = await resolve_ip(HOST.get(ident, ""))
        confs = None
        if ip:
            confs = await pyatv.scan(loop, identifier=ident, hosts=[ip], timeout=2)
        if not confs:                              # Fallback: voller Scan
            confs = await pyatv.scan(loop, identifier=ident, timeout=3)
        if not confs:
            return
        atv = await pyatv.connect(confs[0], loop)
        try:
            try:
                await atv.audio.set_volume(vol)
            except Exception:
                pass
            await atv.stream.stream_file(path)
        finally:
            await atv.close()
    except asyncio.CancelledError:
        raise
    except Exception:
        pass

async def do_play(loop, path):
    vol = hpvol()
    base = os.path.basename(path)
    if base.endswith(".mp3"):
        base = base[:-4]
    try:
        with open(PLAYING, "w") as f:
            f.write(base)
    except Exception:
        pass
    try:
        await asyncio.gather(stream_one(loop, BB, path, vol),
                             stream_one(loop, SB, path, vol))
    finally:
        try:
            os.remove(PLAYING)
        except Exception:
            pass

async def handle(loop, mode, path):
    if mode != "now":
        if rd("/run/vhf/mute") == "1":
            return
        try:
            d = float(rd("/var/lib/vhf/delay", "7"))
        except Exception:
            d = 7.0
        await asyncio.sleep(max(0.0, d))
        if rd("/run/vhf/mute") == "1":
            return
    await do_play(loop, path)

async def main():
    loop = asyncio.get_event_loop()
    os.makedirs("/run/vhf", exist_ok=True)
    try:
        last = os.path.getmtime(REQ)               # bestehenden Request nicht nachspielen
    except Exception:
        last = 0
    cur = None
    while True:
        await asyncio.sleep(0.05)
        try:
            m = os.path.getmtime(REQ)
        except Exception:
            continue
        if m == last:
            continue
        last = m
        line = rd(REQ)
        if not line:
            continue
        parts = line.split("\t")
        mode = parts[0].strip()
        path = parts[1].strip() if len(parts) > 1 else ""
        if mode == "stop":
            if cur and not cur.done():
                cur.cancel()
            continue
        if not path or not os.path.isfile(path):
            continue
        if cur and not cur.done():
            if mode == "now":
                cur.cancel()                       # Funkwiederholung unterbricht
            else:
                continue                           # schon eine laeuft -> ignorieren
        cur = asyncio.ensure_future(handle(loop, mode, path))

if __name__ == "__main__":
    asyncio.run(main())

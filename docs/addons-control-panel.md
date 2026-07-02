# Add-on: Bedienpanel (:8090)

*🇩🇪 Deutsch*

> **Optional.** Ein maritimes Touch-Bedienpanel für Handy/Tablet, das die
> VHF-Funktionen an **einem Port (8090)** bündelt: Funk-Pegelanzeige,
> Messe-Live-Monitor, die Nachhör-Liste (eingebettet über einen Proxy, siehe
> „Ein Port" unten) und – falls HomePods an Bord sind – die HomePod-Übernahme.
>
> **Ohne HomePods** zeigt und steuert das Panel automatisch **nur den
> Messe-Lautsprecher** (siehe `homepods`-Einstellung unten).

Dateien: [`addons/control-panel/`](../addons/control-panel/)

```
addons/control-panel/
├── bin/
│   ├── vhf-control.py     das Panel (Port 8090)
│   ├── vhf-monitor.sh     latenzarmer Live-Monitor: VHF → Messe-Lautsprecher (~100 ms)
│   ├── vhf-level.py       Pegelmessung → /run/vhf/level (Quelle fürs VU-Meter)
│   └── vhf-messe-play.sh  spielt einen Clip auf den Messe-Ausgang (ohne HomePods)
└── systemd/
    ├── vhf-control.service
    ├── vhf-monitor.service
    └── vhf-level.service
```

## Konfiguration: Schiffsname & HomePod-Modus

Das Panel (und die Nachhör-Liste :8088) lesen `/etc/vhf/vhf.conf`
(siehe [`etc/vhf.conf.example`](../etc/vhf.conf.example)) — **ohne Neustart**:

```ini
shipname = auto                    # auto = aus Signal K; oder fester Name
signalk  = http://localhost:3000   # Signal-K-Server (nur bei shipname = auto)
homepods = auto                    # auto | on | off
```

- `shipname = auto` — der Schiffsname wird aus **Signal K** geholt
  (`vessels.self.name`, 30 s gecacht); ist Signal K nicht erreichbar, gilt der
  Fallback „Wilhelmina". Ein fester Wert (`shipname = Möwe`) überschreibt Signal K.
- `homepods = auto` — HomePod-Übernahme erscheint, sobald ShiPod-Ausgänge in
  OwnTone erkannt werden (Standard).
- `homepods = on` — immer anzeigen.
- `homepods = off` — nie anzeigen: das Panel nutzt **nur den Messe-Lautsprecher**;
  Titel-Unterzeile wird zu „VHF-MONITOR · MESSE".

```bash
sudo mkdir -p /etc/vhf
sudo cp etc/vhf.conf.example /etc/vhf/vhf.conf
sudo nano /etc/vhf/vhf.conf        # shipname/homepods anpassen
```

## Ein Port (8090)

Damit man nicht zwei Ports braucht, ist die Nachhör-Liste **durch das Panel
erreichbar**: `vhf-control` proxyt alles unter `http://<pi>:8090/rec/` an den
intern weiterlaufenden `vhf-web` (Standard-Port 8088, `VHF_WEB_PORT`). Die
eingebettete Aufnahmen-Ansicht im Panel zeigt auf `/rec/` — nach außen genügt
**Port 8090**.

- `vhf-web` läuft weiter (Nachhör-Kern), wird aber nur noch intern gebraucht;
  Port 8088 kann per Firewall geschlossen oder auf `127.0.0.1` gebunden werden.
- Alle Aktionen der Liste (Abspielen, Download, Ausblenden, Zurückholen) laufen
  über den Proxy — die Client-Pfade sind relativ, damit das sowohl direkt (8088)
  als auch eingebettet (8090/rec) funktioniert.

## Zwei Aufnahmen-Listen

- **Oben, unter dem Funk-Pegel: „♫ Nachhören letzte Funksprüche"** — kompakte Liste,
  Zeile antippen spielt den Clip **laut** ab: mit HomePods auf die HomePods
  (`vhf-playout.sh`), **ohne HomePods automatisch auf den Messe-Ausgang**
  (`vhf-messe-play.sh` → ALSA `vhfoutplug`, Lautstärke = Messe-Regler). ✓/✗ ordnet ein.
  Der Untertitel der Karte zeigt das aktuelle Ziel („· auf die HomePods" / „· auf die Messe").
- **Ganz unten: „♫ Alle Aufnahmen – am Gerät anhören"** — die volle Nachhör-Liste
  (Wellenform, Wiedergabe **im Browser**, Download), ein-/ausklappbar, lazy geladen.

## Was das Panel nutzt

| Funktion | Abhängigkeit |
|---|---|
| Funk-Pegel (VU) | `vhf-level` schreibt `/run/vhf/level` |
| Messe-Live-Monitor (An/Aus + Lautstärke) | `vhf-monitor` + ALSA-Mixer `Speaker` (Karte 3) |
| Kompakt-Liste laut abspielen | mit Pods `vhf-playout.sh` (HomePod-Add-on), sonst `vhf-messe-play.sh` (Messe) |
| Volle Aufnahmen-Liste (Browser) | Nachhör-Kern `vhf-web` (intern :8088), eingebettet über Proxy `/rec/` |
| Schiffsname | Signal K (`vessels.self.name`), sonst `/etc/vhf/vhf.conf` |

Ohne das HomePod-Add-on bleibt das Panel voll nutzbar (Messe-Betrieb); die
HomePod-**Karte** wird bei `homepods = off` bzw. `auto` (ohne erkannte Pods) ausgeblendet,
die Kompakt-Liste bleibt und spielt dann auf den Messe-Ausgang.

## Installation

```bash
# Panel + Messe-Helfer
sudo install -m755 addons/control-panel/bin/vhf-control.py \
                   addons/control-panel/bin/vhf-monitor.sh \
                   addons/control-panel/bin/vhf-level.py \
                   addons/control-panel/bin/vhf-messe-play.sh   /usr/local/bin/
sudo install -m644 addons/control-panel/systemd/* /etc/systemd/system/

# Konfiguration
sudo mkdir -p /etc/vhf && sudo cp etc/vhf.conf.example /etc/vhf/vhf.conf

sudo systemctl daemon-reload
sudo systemctl enable --now vhf-control vhf-level
# Messe-Live-Monitor nach Bedarf (kann auch im Panel getoggelt werden):
sudo systemctl enable --now vhf-monitor
```

Panel öffnen: **http://<pi>.local:8090/**

## Deaktivieren

```bash
sudo systemctl disable --now vhf-control vhf-level vhf-monitor
sudo rm /etc/systemd/system/vhf-{control,level,monitor}.*
sudo rm /usr/local/bin/vhf-{control.py,level.py,monitor.sh}
```

## Hinweis / Umfang

Der latenzarme Messe-Monitor (`vhf-monitor`) und die Pegelmessung (`vhf-level`)
lesen die gemeinsame ALSA-Capture-Quelle `vhf` (dsnoop) des Nachhör-Kerns. Der
Messe-**Ausgang** nutzt die C-Media-Karte (Karte 3). Das größere
AirPlay-/Ducking-System (`vhf-mixer`, `shairport-sync`) ist hier **nicht**
enthalten.

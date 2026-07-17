# Add-on: HomePod- / AirPlay-2-Ausgabe

*🇩🇪 Deutsch · [🇬🇧 English](addons-homepods.md)*

> **Optional.** Der Nachhör-Kern (Aufnahme + Web-Replay) läuft ohne dieses Add-on.
> Hier kommt hinzu: erkannter *echter* Funk wird nach einer einstellbaren Verzögerung
> kurz auf AirPlay-2-Lautsprecher (z. B. HomePods) „übernommen" und danach wieder
> freigegeben – so bleiben die Lautsprecher sonst für iPhone-Musik frei.

Dateien: [`addons/homepods/`](../addons/homepods/)

```
addons/homepods/
├── bin/
│   ├── vhf-playd.py       residenter pyatv-Daemon (hält pyatv warm → schneller Ton)
│   ├── vhf-playout.sh    schlanker Client → reicht den Clip an vhf-playd weiter
│   ├── vhf-shipods.sh    Ausgänge ausgewählt halten + Zustand melden
│   └── vhf-podwatch.sh   Netz-Erreichbarkeit überwachen, OwnTone selbstheilen
└── systemd/
    ├── vhf-shipods.service / .timer
    └── vhf-podwatch.service
```

## Voraussetzung: pyatv (nicht OwnTone!)

Die Funk-Übernahme streamt über **[pyatv](https://pyatv.dev)** (RAOP/AirPlay) **direkt**
auf die HomePods. **Bewusst nicht OwnTone:** OwnTone (v29.x) stürzt beim AirPlay-Streaming
zu genau diesen HomePods reproduzierbar ab bzw. hängt (bekannte upstream-Bugs; ein in
HomeKit aufgelöstes Stereopaar wird als Einzelgeräte mit AirPlay 1 behandelt). pyatv
streamt stabil, ganz ohne OwnTone.

```bash
# pyatv in ein venv installieren
sudo python3 -m venv /opt/pyatv-venv
sudo /opt/pyatv-venv/bin/pip install pyatv
```

`vhf-playout.sh` spielt **Dual-Mono** (beide Pods parallel denselben Clip) — für
Funksprache völlig ausreichend. OwnTone darf weiterlaufen (Messe-Ausgang / Pod-Erkennung),
wird aber für die HomePod-Wiedergabe **nicht** mehr gebraucht.

## Geräte-IDs anpassen (Pflicht!)

`vhf-playout.sh` enthält feste **pyatv/AirPlay-Identifier** der HomePods:

```bash
BB=FE:A2:7C:85:A9:5C     # ShiPod BB
SB=A2:AE:9B:32:35:0A     # ShiPod SB
```

Deine findest du mit:

```bash
/opt/pyatv-venv/bin/atvremote scan
```

→ pro Gerät die MAC-artige Zeile unter **„Identifiers"** nehmen. Die HomePods brauchen für
RAOP i.d.R. **keine Kopplung** (`Pairing: NotNeeded`), sofern in der Home-App
„Lautsprecher- & TV-Zugriff" auf „Jeder im selben Netzwerk" steht.

## Funktionsweise

- **`vhf-playd`** (Dienst) – residenter Daemon, hält pyatv geladen und streamt Clips
  per RAOP **direkt auf beide ShiPods** (Dual-Mono), Lautstärke aus `/var/lib/vhf/hpvol`.
  Dadurch entfällt der ~2 s pyatv-Kaltstart pro Übernahme → Klick-bis-Ton ~2,5 s.
- **`vhf-playout.sh <mp3> [now]`** – schlanker Client: schreibt den Request atomar nach
  `/run/vhf/playreq`. Ohne `now`: der Daemon wartet die Verzögerung aus
  `/var/lib/vhf/delay` (Default 7 s) ab und respektiert das Mute-Flag `/run/vhf/mute`;
  er setzt `/run/vhf/playing` (fürs VU-Overlay). Stoppen: `stop` nach `/run/vhf/playreq`.
- **`vhf-shipods.*` / `vhf-podwatch.*`** – Reste vom OwnTone-Weg; für pyatv nicht mehr
  nötig (podwatch meldet weiter die Netz-Erreichbarkeit der Pods fürs Panel).

## Installation

```bash
# pyatv (siehe oben) + Daemon
sudo python3 -m venv /opt/pyatv-venv && sudo /opt/pyatv-venv/bin/pip install pyatv
sudo install -m755 addons/homepods/bin/vhf-playd.py addons/homepods/bin/*.sh /usr/local/bin/
sudo install -m644 addons/homepods/systemd/* /etc/systemd/system/
sudo mkdir -p /var/lib/vhf
echo 7  | sudo tee /var/lib/vhf/delay     # Verzögerung Sekunden
echo 60 | sudo tee /var/lib/vhf/hpvol     # HomePod-Lautstärke 0..100
sudo systemctl daemon-reload
sudo systemctl enable --now vhf-playd     # der Playout-Daemon (Pflicht)
sudo systemctl enable --now vhf-podwatch  # optional: Pod-Erreichbarkeit fürs Panel
```

Sobald `vhf-playout.sh` als `/usr/local/bin/vhf-playout.sh` **ausführbar** vorhanden
ist, ruft der `vhf-recorder` es bei erkannter Sprache automatisch auf – keine Änderung
am Recorder nötig.

## Deaktivieren

```bash
sudo systemctl disable --now vhf-shipods.timer vhf-podwatch
sudo rm /usr/local/bin/vhf-playout.sh    # Recorder überspringt die Übernahme dann wieder
```

## Hinweis / Umfang

Dieses Add-on deckt die **Nachhör-Übernahme** (einzelner Clip → HomePods) ab. Das
größere Live-/AirPlay-/Ducking-System (Live-Monitor, `vhf-mixer`, `shairport-sync`,
Messe-Lautsprecher) aus dem ursprünglichen `wilhelmina-audio`-Setup ist hier bewusst
**nicht** enthalten – es kann später als weiteres Add-on ergänzt werden.

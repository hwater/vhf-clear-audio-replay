# Add-on: HomePod- / AirPlay-2-Ausgabe

> **Optional.** Der Nachhör-Kern (Aufnahme + Web-Replay) läuft ohne dieses Add-on.
> Hier kommt hinzu: erkannter *echter* Funk wird nach einer einstellbaren Verzögerung
> kurz auf AirPlay-2-Lautsprecher (z. B. HomePods) „übernommen" und danach wieder
> freigegeben – so bleiben die Lautsprecher sonst für iPhone-Musik frei.

Dateien: [`addons/homepods/`](../addons/homepods/)

```
addons/homepods/
├── bin/
│   ├── vhf-playout.sh    echten Funk-Clip kurz auf die AirPlay-Ausgänge spielen
│   ├── vhf-shipods.sh    Ausgänge ausgewählt halten + Zustand melden
│   └── vhf-podwatch.sh   Netz-Erreichbarkeit überwachen, OwnTone selbstheilen
└── systemd/
    ├── vhf-shipods.service / .timer
    └── vhf-podwatch.service
```

## Voraussetzung: OwnTone

Die Ausgabe läuft über **[OwnTone](https://owntone.github.io/owntone-server/)** (Fork
von forked-daapd) als AirPlay-2-Sender.

```bash
# OwnTone aus dem offiziellen APT-Repo installieren (siehe OwnTone-Doku)
sudo apt install owntone
```

In `/etc/owntone.conf` mindestens einen ALSA/Pipe-Betrieb konfigurieren und die
AirPlay-Ausgänge im Webinterface (`http://<pi>:3689`) einmalig **auswählen**.

## Geräte-IDs anpassen (Pflicht!)

Die Skripte enthalten **feste OwnTone-Ausgangs-IDs** der HomePods dieses Setups:

```bash
# vhf-playout.sh
BB=279973827291484     # ShiPod BB
SB=178870811768074     # ShiPod SB
```

Deine IDs findest du mit:

```bash
curl -s http://localhost:3689/api/outputs | python3 -m json.tool
```

`BB`/`SB` in `vhf-playout.sh` **und** die Listen in `vhf-shipods.sh` / `vhf-podwatch.sh`
(`NAME`-Map, `ShiPod-*.local`-Hostnamen) auf deine Geräte umschreiben.

## Funktionsweise

- **`vhf-playout.sh <mp3> [now]`** – wählt die AirPlay-Ausgänge, setzt die Lautstärke
  (`/var/lib/vhf/hpvol`), spielt genau einen Clip über OwnTone und gibt die Ausgänge
  danach wieder frei. Ohne `now`: wartet die Verzögerung aus `/var/lib/vhf/delay`
  (Default 7 s) ab und respektiert das Mute-Flag `/run/vhf/mute`.
- **`vhf-shipods.*`** – ein Timer hält die AirPlay-2-Ausgänge *ausgewählt* (AirPlay-2
  verliert die Auswahl bei OwnTone-Neustart) und meldet den Zustand nach
  `/run/vhf/shipods.state`.
- **`vhf-podwatch.*`** – prüft die WLAN-Erreichbarkeit der Pods (mDNS + AirPlay-Port
  7000) und startet OwnTone *einmalig* neu (Cooldown 5 min), wenn beide wieder im Netz
  sind, OwnTone sie aber verloren hat.

## Installation

```bash
sudo install -m755 addons/homepods/bin/*.sh /usr/local/bin/
sudo install -m644 addons/homepods/systemd/* /etc/systemd/system/
sudo mkdir -p /var/lib/vhf
echo 7  | sudo tee /var/lib/vhf/delay     # Verzögerung Sekunden
echo 60 | sudo tee /var/lib/vhf/hpvol     # HomePod-Lautstärke 0..100
sudo systemctl daemon-reload
sudo systemctl enable --now vhf-shipods.timer vhf-podwatch
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

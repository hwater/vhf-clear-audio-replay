# VHF – clear Audio replay

*🇩🇪 Deutsch · [🇬🇧 English](README.en.md)*

<img width="984" height="1076" alt="Bildschirmfoto 2026-07-02 um 19 37 04" src="https://github.com/user-attachments/assets/1785da8d-0530-4b0f-8c07-640007a63ac4" />


**Marine-VHF-Funk mitschneiden und sauber nachhören.** Ein Raspberry-Pi-System, das
den Ton aus einem VHF/UKW-Seefunkgerät über einen USB-Audio-Adapter abgreift, jeden
Funkspruch als einzelne, entrauschte MP3 aufzeichnet und im Browser zum Nachhören,
Herunterladen und Aussortieren bereitstellt.

> Kern dieses Projekts ist das **Nachhören** (Aufnahme + Replay). Die optionale
> Ausgabe auf HomePods/AirPlay-Lautsprecher ist ein separates **Add-on**
> ([`addons/homepods/`](addons/homepods/), siehe [docs/addons-homepods.de.md](docs/addons-homepods.de.md)).

## Was es kann

- **Sprachgesteuerte Aufnahme (VOX):** eine MP3 pro Funkspruch, automatisch getrimmt.
- **Entrauschen & Normalisieren:** Bandpass (250–3400 Hz), FFT-Denoise und Loudness-
  Normalisierung → gleichmäßig laute, gut verständliche Aufnahmen („clear audio").
- **Automatische Störungs-Erkennung:** ein Klassifikator trennt echte Sprache von
  Trägern/Rauschen anhand des Sprach-Rhythmus (gain-unabhängig). Störungen werden
  versteckt, nicht gelöscht – rückholbar.
- **Web-Replay** (Port 8088): responsive Liste zum Anhören am Handy — pro Zeile
  Play-Taste, Wellenform/VU-Übersicht, **gut**/**Störung**-Einordnung und Download.
- **Automatische Aufräumung:** Störungen > 1 Tag, Aufnahmen > 7 Tage werden gelöscht.

## Architektur

```
 VHF/UKW-Funkgerät
   │ (Lautsprecher-/Line-Out)
   ▼
 USB-Audio-Adapter (C-Media, mono capture)  ── hw:3,0
   │
   ▼  ALSA dsnoop  (etc/asound.conf → pcm "vhf")   ← teilbare Capture-Quelle
   │
   ▼
 vhf-recorder.sh   VOX-Aufnahme (sox) → Bandpass → Denoise/Loudnorm (ffmpeg) → MP3
   │
   ├─► vhf-classify.py   Sprache?  ── ja ──►  /srv/music/VHF-Aufnahmen/VHF_<zeit>.mp3
   │                                └─ nein ─►  .noise-VHF_<zeit>.mp3  (versteckt)
   ▼
 /srv/music/VHF-Aufnahmen/
   │
   ├─► vhf-web.py         :8088  Replay-/Download-Liste (Browser, ohne root)
   └─► vhf-cleanup.timer  täglich alte Dateien entfernen

 (optional) HomePod-Add-on:  echter Funk wird zusätzlich kurz auf AirPlay-2-
            Lautsprecher „übernommen"  →  addons/homepods/
```

## Hardware

- **VHF-Audio-Abgriff:** USB-Audio-Adapter C-Media `0d8c:0014` (z. B. Unitek Y-247A),
  Capture mono. Vom Funkgerät kommt Mono; Pegel am Funkgerät moderat halten (nicht
  übersteuern). Optional galvanische Trennung (Audio-Übertrager) gegen Brumm.
- **Rechner:** Raspberry Pi (getestet: Pi mit Raspberry Pi OS *Trixie*). CPU-Last gering.
- Kein Netz nötig außer LAN/WLAN für die Web-Oberfläche.

## Schnellstart

Siehe [docs/install.de.md](docs/install.de.md) für alle Schritte. Kurzform:

```bash
# 1) Pakete
sudo apt install sox ffmpeg alsa-utils python3-numpy curl

# 2) Dateien installieren
sudo install -m755 bin/vhf-recorder.sh bin/vhf-classify.py bin/vhf-web.py /usr/local/bin/
sudo install -m644 etc/asound.conf         /etc/asound.conf
sudo install -m644 etc/85-vhf-audio.rules  /etc/udev/rules.d/
sudo install -m644 etc/alsa-vhf-index.conf /etc/modprobe.d/
sudo install -m644 systemd/*               /etc/systemd/system/

# 3) Ablage + Rechte (Web-Dienst läuft ohne root, Gruppe audio)
sudo mkdir -p /srv/music/VHF-Aufnahmen
sudo chgrp -R audio /srv/music/VHF-Aufnahmen && sudo chmod -R g+rws /srv/music/VHF-Aufnahmen

# 4) udev/modprobe greifen nach Reboot (USB-Karte fix auf hw:3, ID „VHF")
sudo udevadm control --reload-rules
sudo systemctl daemon-reload
sudo systemctl enable --now vhf-recorder vhf-web vhf-cleanup.timer
```

Danach: **http://<pi>.local:8088/** öffnen. Ins Funkgerät sprechen (oder Funk abwarten) –
nach ein paar Sekunden erscheint die erste Aufnahme.

## Dienste

| Dienst | Funktion | Port |
|---|---|---|
| `vhf-recorder` | VOX-Mitschnitt → entrauschte MP3 pro Funkspruch | – |
| `vhf-web` | Replay-/Download-Liste im Browser (ohne root) | 8088 |
| `vhf-cleanup.timer` | täglich: Störungen > 1 Tag, Aufnahmen > 7 Tage löschen | – |

## Ordner

```
bin/      vhf-recorder.sh · vhf-classify.py · vhf-web.py
etc/      asound.conf (ALSA capture) · udev-Regel · modprobe-Index
systemd/  vhf-recorder · vhf-web · vhf-cleanup (.service/.timer)
docs/     Architektur · Installation · Tuning · HomePod-Add-on
addons/   homepods/       – optionale AirPlay-2-Ausgabe (separater Setup)
          control-panel/  – optionales Touch-Bedienpanel (:8090)
```

Der Schiffsname in den Titelzeilen kommt aus **Signal K** (`vessels.self.name`) oder
aus [`etc/vhf.conf.example`](etc/vhf.conf.example) (`/etc/vhf/vhf.conf`, ohne Neustart).

## Doku

- [docs/architecture.de.md](docs/architecture.de.md) – Signalweg, ALSA, Klassifikator im Detail
- [docs/install.de.md](docs/install.de.md) – vollständige Installation & Erst-Check
- [docs/tuning.de.md](docs/tuning.de.md) – VOX-Schwellen, Denoise, Störungsfilter justieren
- [docs/addons-homepods.de.md](docs/addons-homepods.de.md) – HomePod-/AirPlay-Ausgabe nachrüsten
- [docs/addons-control-panel.md](docs/addons-control-panel.md) – Bedienpanel (:8090), Schiffsname & Messe-Fallback

## Lizenz

[MIT](LICENSE).

# VHF – clear Audio replay

*[🇩🇪 Deutsch](README.md) · 🇬🇧 English*

**Record marine VHF radio traffic and replay it cleanly.** A Raspberry Pi system that
taps the audio from a VHF/marine-band radio via a USB audio adapter, records every
transmission as a separate, denoised MP3, and serves them in the browser for replay,
download and triage.

> The core of this project is **replay** (record + listen back). Optional output to
> HomePods / AirPlay speakers is a separate **add-on**
> ([`addons/homepods/`](addons/homepods/), see [docs/addons-homepods.md](docs/addons-homepods.md)).

## Features

- **Voice-activated recording (VOX):** one MP3 per transmission, auto-trimmed.
- **Denoise & normalize:** band-pass (250–3400 Hz), FFT denoise and loudness
  normalization → evenly loud, intelligible recordings ("clear audio").
- **Automatic interference detection:** a classifier separates real speech from
  carriers/noise using the speech *rhythm* (gain-independent). Noise is hidden, not
  deleted — recoverable.
- **Web replay** (port 8088): responsive list for listening on the phone, single-file
  download, multi-select to hide, and an expandable section for sorted-out noise.
- **Automatic cleanup:** noise older than 1 day, recordings older than 7 days.

## Architecture

```
 VHF / marine radio
   │ (speaker / line out)
   ▼
 USB audio adapter (C-Media, mono capture)  ── hw:3,0
   │
   ▼  ALSA dsnoop  (etc/asound.conf → pcm "vhf")   ← shareable capture source
   │
   ▼
 vhf-recorder.sh   VOX record (sox) → band-pass → denoise/loudnorm (ffmpeg) → MP3
   │
   ├─► vhf-classify.py   speech?  ── yes ──►  /srv/music/VHF-Aufnahmen/VHF_<time>.mp3
   │                              └─ no  ──►  .noise-VHF_<time>.mp3  (hidden)
   ▼
 /srv/music/VHF-Aufnahmen/
   │
   ├─► vhf-web.py         :8088  replay / download list (browser, no root)
   └─► vhf-cleanup.timer  daily removal of old files

 (optional) HomePod add-on:  real traffic is additionally played briefly on
            AirPlay-2 speakers  →  addons/homepods/
```

## Hardware

- **VHF audio tap:** USB audio adapter C-Media `0d8c:0014` (e.g. Unitek Y-247A),
  mono capture. The radio provides mono; keep the radio's output level moderate (do not
  clip). Optional galvanic isolation (audio transformer) against hum.
- **Computer:** Raspberry Pi (tested on Pi with Raspberry Pi OS *Trixie*). Low CPU load.
- No internet required, only LAN/Wi-Fi for the web interface.

## Quick start

See [docs/install.md](docs/install.md) for all steps. Short form:

```bash
# 1) Packages
sudo apt install sox ffmpeg alsa-utils python3-numpy curl

# 2) Install files
sudo install -m755 bin/vhf-recorder.sh bin/vhf-classify.py bin/vhf-web.py /usr/local/bin/
sudo install -m644 etc/asound.conf         /etc/asound.conf
sudo install -m644 etc/85-vhf-audio.rules  /etc/udev/rules.d/
sudo install -m644 etc/alsa-vhf-index.conf /etc/modprobe.d/
sudo install -m644 systemd/*               /etc/systemd/system/

# 3) Storage + permissions (web service runs without root, group audio)
sudo mkdir -p /srv/music/VHF-Aufnahmen
sudo chgrp -R audio /srv/music/VHF-Aufnahmen && sudo chmod -R g+rws /srv/music/VHF-Aufnahmen

# 4) udev/modprobe take effect after reboot (USB card fixed to hw:3, id "VHF")
sudo udevadm control --reload-rules
sudo systemctl daemon-reload
sudo systemctl enable --now vhf-recorder vhf-web vhf-cleanup.timer
```

Then open **http://<pi>.local:8088/**. Speak into the radio (or wait for traffic) — after
a few seconds the first recording appears.

## Services

| Service | Function | Port |
|---|---|---|
| `vhf-recorder` | VOX recording → denoised MP3 per transmission | – |
| `vhf-web` | replay / download list in the browser (no root) | 8088 |
| `vhf-cleanup.timer` | daily: delete noise > 1 day, recordings > 7 days | – |

## Folders

```
bin/      vhf-recorder.sh · vhf-classify.py · vhf-web.py
etc/      asound.conf (ALSA capture) · udev rule · modprobe index
systemd/  vhf-recorder · vhf-web · vhf-cleanup (.service/.timer)
docs/     architecture · install · tuning · HomePod add-on
addons/   homepods/       – optional AirPlay-2 output (separate setup)
          control-panel/  – optional touch control panel (:8090)
```

The ship name shown in the title bars comes from **Signal K** (`vessels.self.name`) or
from [`etc/vhf.conf.example`](etc/vhf.conf.example) (`/etc/vhf/vhf.conf`, no restart needed).

## Docs

- [docs/architecture.md](docs/architecture.md) – signal path, ALSA, classifier in detail
- [docs/install.md](docs/install.md) – full installation & first check
- [docs/tuning.md](docs/tuning.md) – adjust VOX thresholds, denoise, noise filter
- [docs/addons-homepods.md](docs/addons-homepods.md) – add HomePod / AirPlay output
- [docs/addons-control-panel.md](docs/addons-control-panel.md) – control panel (:8090), ship name & Messe fallback *(DE)*

## License

[MIT](LICENSE).

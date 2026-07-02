# Installation – VHF clear Audio replay

Getestet auf Raspberry Pi OS (Trixie). Alle Schritte als Benutzer mit `sudo`.

## 1. Pakete

```bash
sudo apt update
sudo apt install sox ffmpeg alsa-utils python3-numpy curl
```

- `sox` – VOX-Aufnahme, `ffmpeg` – Denoise/Loudnorm/MP3, `python3-numpy` – Klassifikator.
- `curl` wird nur vom optionalen HomePod-Add-on wirklich gebraucht; schadet aber nicht.

## 2. USB-Audio-Adapter fixieren

Damit der Adapter nach Reboots stabil `hw:3` / ALSA-ID `VHF` bleibt:

```bash
sudo install -m644 etc/85-vhf-audio.rules  /etc/udev/rules.d/
sudo install -m644 etc/alsa-vhf-index.conf /etc/modprobe.d/
```

> Anderer Adapter? `lsusb` zeigt `idVendor:idProduct`. In `85-vhf-audio.rules`
> anpassen. Anderer Karten-Index als 3 gewünscht? `alsa-vhf-index.conf` **und**
> die `hw:3,0`-Angaben in `etc/asound.conf` gleichziehen.

## 3. ALSA-Capture

```bash
sudo install -m644 etc/asound.conf /etc/asound.conf
```

Definiert die teilbare Aufnahmequelle `pcm.vhf` (dsnoop). Nach einem **Reboot** prüfen:

```bash
arecord -l                 # Karte 3 = „VHF" vorhanden?
arecord -D vhf -f S16_LE -c1 -r44100 -d 3 /tmp/test.wav && aplay /tmp/test.wav
```

## 4. Programme installieren

```bash
sudo install -m755 bin/vhf-recorder.sh bin/vhf-classify.py bin/vhf-web.py /usr/local/bin/
```

## 5. Ablage & Rechte

Der Web-Dienst läuft **ohne root** (systemd `DynamicUser`, Gruppe `audio`).
Verschieben/Löschen funktioniert über die Verzeichnisrechte:

```bash
sudo mkdir -p /srv/music/VHF-Aufnahmen
sudo chgrp -R audio /srv/music/VHF-Aufnahmen
sudo chmod -R g+rws /srv/music/VHF-Aufnahmen     # group-writable + setgid
```

## 6. Dienste aktivieren

```bash
sudo install -m644 systemd/* /etc/systemd/system/
sudo systemctl daemon-reload
sudo udevadm control --reload-rules
sudo systemctl enable --now vhf-recorder vhf-web vhf-cleanup.timer
```

## 7. Funktionscheck

```bash
systemctl status vhf-recorder vhf-web          # beide active (running)?
journalctl -u vhf-recorder -f                  # „aufgenommen: …" bei Funk/Sprache
```

Browser: **http://<pi>.local:8088/** – nach dem ersten Funkspruch erscheint eine
Aufnahme. Über den Klassifikator geht mit: `tail -f /run/vhf/classify.log`.

## Deinstallation

```bash
sudo systemctl disable --now vhf-recorder vhf-web vhf-cleanup.timer
sudo rm /etc/systemd/system/vhf-{recorder,web,cleanup}.* 
sudo rm /usr/local/bin/vhf-{recorder.sh,classify.py,web.py}
sudo rm /etc/asound.conf /etc/udev/rules.d/85-vhf-audio.rules /etc/modprobe.d/alsa-vhf-index.conf
# Aufnahmen bleiben unter /srv/music/VHF-Aufnahmen erhalten (bei Bedarf löschen)
```

## Nächster Schritt (optional)

HomePod-/AirPlay-2-Ausgabe nachrüsten → [addons-homepods.md](addons-homepods.md).

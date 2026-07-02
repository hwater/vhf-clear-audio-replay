# Installation – VHF clear Audio replay

*[🇩🇪 Deutsch](install.de.md) · 🇬🇧 English*

Tested on Raspberry Pi OS (Trixie). All steps as a user with `sudo`.

## 1. Packages

```bash
sudo apt update
sudo apt install sox ffmpeg alsa-utils python3-numpy curl
```

- `sox` – VOX recording, `ffmpeg` – denoise/loudnorm/MP3, `python3-numpy` – classifier.
- `curl` is only really needed by the optional HomePod add-on; harmless otherwise.

## 2. Pin the USB audio adapter

So the adapter stays stable at `hw:3` / ALSA id `VHF` across reboots:

```bash
sudo install -m644 etc/85-vhf-audio.rules  /etc/udev/rules.d/
sudo install -m644 etc/alsa-vhf-index.conf /etc/modprobe.d/
```

> Different adapter? `lsusb` shows `idVendor:idProduct`. Adjust it in
> `85-vhf-audio.rules`. Want a card index other than 3? Change `alsa-vhf-index.conf`
> **and** the `hw:3,0` references in `etc/asound.conf` to match.

## 3. ALSA capture

```bash
sudo install -m644 etc/asound.conf /etc/asound.conf
```

Defines the shareable capture source `pcm.vhf` (dsnoop). After a **reboot**, check:

```bash
arecord -l                 # card 3 = "VHF" present?
arecord -D vhf -f S16_LE -c1 -r44100 -d 3 /tmp/test.wav && aplay /tmp/test.wav
```

## 4. Install programs

```bash
sudo install -m755 bin/vhf-recorder.sh bin/vhf-classify.py bin/vhf-web.py /usr/local/bin/
```

## 5. Storage & permissions

The web service runs **without root** (systemd `DynamicUser`, group `audio`).
Moving/deleting works through directory permissions:

```bash
sudo mkdir -p /srv/music/VHF-Aufnahmen
sudo chgrp -R audio /srv/music/VHF-Aufnahmen
sudo chmod -R g+rws /srv/music/VHF-Aufnahmen     # group-writable + setgid
```

## 6. Enable services

```bash
sudo install -m644 systemd/* /etc/systemd/system/
sudo systemctl daemon-reload
sudo udevadm control --reload-rules
sudo systemctl enable --now vhf-recorder vhf-web vhf-cleanup.timer
```

## 7. Function check

```bash
systemctl status vhf-recorder vhf-web          # both active (running)?
journalctl -u vhf-recorder -f                  # "aufgenommen: …" on traffic/speech
```

Browser: **http://<pi>.local:8088/** – a recording appears after the first
transmission. Watch the classifier with: `tail -f /run/vhf/classify.log`.

## Uninstall

```bash
sudo systemctl disable --now vhf-recorder vhf-web vhf-cleanup.timer
sudo rm /etc/systemd/system/vhf-{recorder,web,cleanup}.*
sudo rm /usr/local/bin/vhf-{recorder.sh,classify.py,web.py}
sudo rm /etc/asound.conf /etc/udev/rules.d/85-vhf-audio.rules /etc/modprobe.d/alsa-vhf-index.conf
# Recordings remain under /srv/music/VHF-Aufnahmen (delete if desired)
```

## Next step (optional)

Add HomePod / AirPlay-2 output → [addons-homepods.md](addons-homepods.md).

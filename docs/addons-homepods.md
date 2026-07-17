# Add-on: HomePod / AirPlay-2 output

*[🇩🇪 Deutsch](addons-homepods.de.md) · 🇬🇧 English*

> **Optional.** The replay core (recording + web replay) works without this add-on.
> What it adds: detected *real* traffic is briefly "taken over" onto AirPlay-2 speakers
> (e.g. HomePods) after an adjustable delay and released again afterwards — so the
> speakers otherwise stay free for iPhone music.

Files: [`addons/homepods/`](../addons/homepods/)

```
addons/homepods/
├── bin/
│   ├── vhf-playout.sh    play a real traffic clip briefly on the AirPlay outputs
│   ├── vhf-shipods.sh    keep the outputs selected + report state
│   └── vhf-podwatch.sh   monitor network reachability, self-heal OwnTone
└── systemd/
    ├── vhf-shipods.service / .timer
    └── vhf-podwatch.service
```

## Prerequisite: pyatv (not OwnTone!)

Playout streams to the HomePods **directly via [pyatv](https://pyatv.dev)** (RAOP/AirPlay).
**Deliberately not OwnTone:** OwnTone (v29.x) reliably crashes/hangs when streaming AirPlay
to these particular HomePods (known upstream bugs; a HomeKit stereo pair that was dissolved
is treated as individual AirPlay-1 devices). pyatv streams reliably, without OwnTone.

```bash
sudo python3 -m venv /opt/pyatv-venv
sudo /opt/pyatv-venv/bin/pip install pyatv
```

`vhf-playout.sh` plays **dual-mono** (both pods the same clip in parallel) — fine for radio
voice. OwnTone may keep running (mess output / pod detection) but is **no longer used** for
HomePod playout. Get the device identifiers with `/opt/pyatv-venv/bin/atvremote scan`
(the MAC-like line under *Identifiers*); HomePods usually need no pairing for RAOP
(`Pairing: NotNeeded`) if "Allow Speaker & TV Access" is set to "Anyone on the same network".

> **The old OwnTone route (kept for reference).** If you ever go back to OwnTone: it needs
> IPv6 enabled — HomePods are often reachable for AirPlay **only over IPv6** (IPv4/ARP drops
> when they sleep), and OwnTone defaults IPv6 off. Set `ipv6 = yes` in the
> `general { … }` block of `/etc/owntone.conf`, then `sudo systemctl restart owntone`. But
> even with that, OwnTone crashes streaming to these pods — hence pyatv.

> **IPv6 einschalten — Pflicht für HomePods!** HomePods sind für AirPlay oft **nur
> über IPv6** erreichbar (IPv4/ARP fällt weg, wenn sie schlafen); OwnTone hat IPv6
> per Default **aus**. Ohne das verschwinden die HomePods sporadisch aus den
> Ausgängen, obwohl AirPlay vom iPhone geht. In `/etc/owntone.conf`, Abschnitt
> `general { … }`:
> ```
> ipv6 = yes
> ```
> danach `sudo systemctl restart owntone`. (Prüfen, welchen Weg die Pods nutzen:
> `avahi-resolve -6 -n ShiPod-BB.local` → wenn eine `fe80:`/`fd..`-Adresse kommt und
> `ping6` darauf antwortet, aber IPv4 tot ist, ist IPv6 zwingend.)

## Adjust device IDs (required!)

The scripts contain **fixed OwnTone output IDs** of the HomePods in this setup:

```bash
# vhf-playout.sh
BB=279973827291484     # ShiPod BB
SB=178870811768074     # ShiPod SB
```

Find your IDs with:

```bash
curl -s http://localhost:3689/api/outputs | python3 -m json.tool
```

Rewrite `BB`/`SB` in `vhf-playout.sh` **and** the lists in `vhf-shipods.sh` /
`vhf-podwatch.sh` (`NAME` map, `ShiPod-*.local` hostnames) to your devices.

## How it works

- **`vhf-playout.sh <mp3> [now]`** – selects the AirPlay outputs, sets the volume
  (`/var/lib/vhf/hpvol`), plays exactly one clip through OwnTone and releases the outputs
  afterwards. Without `now`: waits the delay from `/var/lib/vhf/delay` (default 7 s) and
  honors the mute flag `/run/vhf/mute`.
- **`vhf-shipods.*`** – a timer keeps the AirPlay-2 outputs *selected* (AirPlay-2 loses
  the selection on an OwnTone restart) and reports state to `/run/vhf/shipods.state`.
- **`vhf-podwatch.*`** – checks Wi-Fi reachability of the pods (mDNS + AirPlay port 7000)
  and restarts OwnTone *once* (5-min cooldown) when both are back on the network but
  OwnTone has lost them.

## Installation

```bash
sudo install -m755 addons/homepods/bin/*.sh /usr/local/bin/
sudo install -m644 addons/homepods/systemd/* /etc/systemd/system/
sudo mkdir -p /var/lib/vhf
echo 7  | sudo tee /var/lib/vhf/delay     # delay in seconds
echo 60 | sudo tee /var/lib/vhf/hpvol     # HomePod volume 0..100
sudo systemctl daemon-reload
sudo systemctl enable --now vhf-shipods.timer vhf-podwatch
```

As soon as `vhf-playout.sh` is present and **executable** at
`/usr/local/bin/vhf-playout.sh`, the `vhf-recorder` calls it automatically on detected
speech — no change to the recorder needed.

## Disable

```bash
sudo systemctl disable --now vhf-shipods.timer vhf-podwatch
sudo rm /usr/local/bin/vhf-playout.sh    # the recorder then skips the takeover again
```

## Note / scope

This add-on covers the **replay takeover** (single clip → HomePods). The larger
live / AirPlay / ducking system (live monitor, `vhf-mixer`, `shairport-sync`, wired
speaker) from the original `wilhelmina-audio` setup is deliberately **not** included
here — it can be added later as another add-on.

# Architecture – VHF clear Audio replay

*[🇩🇪 Deutsch](architecture.de.md) · 🇬🇧 English*

## Signal chain

```
Radio ──► USB adapter (hw:3,0, mono) ──► ALSA dsnoop "vhf" ──► sox VOX ──► ffmpeg ──► MP3
                                                                 │            (denoise/loudnorm)
                                                                 ▼
                                                           vhf-classify.py
                                                          (speech / noise)
                                                                 ▼
                                                    /srv/music/VHF-Aufnahmen/
                                                                 ▼
                                                 vhf-web.py  (browser, :8088)
```

## 1. Audio capture (ALSA)

The USB adapter is given a fixed name via a **udev rule** and pinned to card 3 via a
**modprobe index**, so the device name does not shift after reboots / USB re-ordering:

- [`etc/85-vhf-audio.rules`](../etc/85-vhf-audio.rules): C-Media `0d8c:0014` → ALSA id `VHF`
- [`etc/alsa-vhf-index.conf`](../etc/alsa-vhf-index.conf): `snd-usb-audio index=3` → `hw:3`

In [`etc/asound.conf`](../etc/asound.conf), **`pcm.vhfsnoop` (type dsnoop)** defines a
*shareable* capture source: several processes can read the same mono capture
simultaneously without blocking each other with "device busy". `pcm.vhf` puts a `plug`
on top (format/rate conversion). The recorder simply reads the ALSA device `vhf`.

> The `vhfout`/`vhfoutplug` (dmix playback) blocks in `asound.conf` are only needed by
> the **HomePod add-on** (local wired output / OwnTone); for the pure replay core they
> are unused but harmless.

## 2. Recording (`bin/vhf-recorder.sh`)

An endless loop records **one transmission per pass**:

1. `sox -t alsa vhf ... silence 1 0.1 THRESH 1 TRAIL THRESH trim 0 MAXDUR`
   – blocks until audio above the **VOX threshold** (`THRESH`, default `3%`) is present,
   records, and stops after `TRAIL` (1.5 s) of silence. `highpass 250 lowpass 3400`
   restricts to the speech band.
2. **Plausibility:** shorter than `MINDUR` (1 s) = noise blip → discard; longer than
   `MAXDUR` (90 s) = open squelch / continuous interference → discard.
3. **Post-processing** with ffmpeg: `afftdn` (FFT denoise) + `loudnorm`
   (I=-16, TP=-1.5) → evenly loud, denoised mono MP3 (96 kbit/s) at
   `/srv/music/VHF-Aufnahmen/VHF_<time>.mp3`.
4. **Classification** in the background (see below). Noise is renamed to
   `.noise-VHF_<time>.mp3` (hidden, recoverable).

The OwnTone/HomePod calls in the recorder are **conditional** (`[ -x vhf-playout.sh ]`):
without the HomePod add-on they are skipped — the replay core is standalone.

## 3. Interference classifier (`bin/vhf-classify.py`)

Separates real speech from carriers/noise **gain-independently** via the *rhythm* of the
loudness envelope rather than absolute levels:

- `modIndex = std/mean` of the energy envelope (speech band, envelope @100 Hz)
- `mod4` = fraction of envelope energy in the **2–8 Hz syllable rate**

**Speech** if `MI_LO ≤ modIndex ≤ MI_HI` **and** `mod4 ≥ MOD4`
(defaults 0.55 / 1.65 / 0.30). Continuous carriers (modIndex too low) and erratic noise
(modIndex too high) fall out. **When in doubt it keeps** (decode error, very short clips
→ KEEP). Decisions go to `/run/vhf/classify.log`.

## 4. Web replay (`bin/vhf-web.py`)

A stdlib `ThreadingHTTPServer` on **:8088**, no framework, no root:

- **List** newest first; each row with `<audio controls>` (streamed from the server),
  duration estimate, download link, single-hide and multi-select.
- **Hiding** moves to `.noise-*` (hidden, not deleted); sorted-out noise is listenable in
  an expandable section and can be restored as "real".
- Deleting/moving goes through **directory permissions** (folder `group audio`,
  group-writable) — the service runs as a `DynamicUser` in group `audio`, never as root.
- Path safety: only file names `VHF_*.mp3` / `.noise-VHF_*.mp3`, no `/` or `\`.

## 5. Cleanup (`systemd/vhf-cleanup.*`)

`vhf-cleanup.timer` (daily) deletes `.noise-*` older than 1 day and `VHF_*.mp3` older
than 7 days. The retention can be adjusted in the `.service` (find `-mtime`).

## File-state flow

```
   recording ──► VHF_<time>.mp3 ──(classify: noise)──► .noise-VHF_<time>.mp3
                     ▲                                          │
                     └─────────── restore as "real" ◄───────────┘
   cleanup:  .noise-* > 1 day  and  VHF_* > 7 days  →  deleted
```

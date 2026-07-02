# Architektur – VHF clear Audio replay

*🇩🇪 Deutsch · [🇬🇧 English](architecture.md)*

## Signalkette

```
Funkgerät ──► USB-Adapter (hw:3,0, mono) ──► ALSA dsnoop "vhf" ──► sox VOX ──► ffmpeg ──► MP3
                                                                     │            (Denoise/Loudnorm)
                                                                     ▼
                                                               vhf-classify.py
                                                              (Sprache / Störung)
                                                                     ▼
                                                        /srv/music/VHF-Aufnahmen/
                                                                     ▼
                                                     vhf-web.py  (Browser, :8088)
```

## 1. Audio-Capture (ALSA)

Der USB-Adapter wird per **udev-Regel** fest benannt und per **modprobe-Index** fest auf
Karte 3 gelegt, damit sich der Gerätename nach Reboots/USB-Reihenfolge nicht verschiebt:

- [`etc/85-vhf-audio.rules`](../etc/85-vhf-audio.rules): C-Media `0d8c:0014` → ALSA-ID `VHF`
- [`etc/alsa-vhf-index.conf`](../etc/alsa-vhf-index.conf): `snd-usb-audio index=3` → `hw:3`

In [`etc/asound.conf`](../etc/asound.conf) definiert **`pcm.vhfsnoop` (type dsnoop)** eine
*teilbare* Aufnahmequelle: mehrere Prozesse können denselben mono-Capture gleichzeitig
lesen, ohne sich „das Gerät ist belegt" zu blockieren. `pcm.vhf` legt einen `plug`
darüber (Format-/Rate-Konvertierung). Der Recorder liest schlicht das ALSA-Device `vhf`.

> Die `vhfout`/`vhfoutplug`-Blöcke (dmix-Playback) in `asound.conf` werden nur vom
> **HomePod-Add-on** (lokale Messe-Ausgabe/OwnTone) gebraucht; für den reinen Nachhör-
> Kern sind sie ungenutzt, stören aber nicht.

## 2. Aufnahme (`bin/vhf-recorder.sh`)

Eine Endlosschleife nimmt **einen Funkspruch pro Durchlauf** auf:

1. `sox -t alsa vhf ... silence 1 0.1 THRESH 1 TRAIL THRESH trim 0 MAXDUR`
   – blockiert, bis Ton über der **VOX-Schwelle** (`THRESH`, Default `3%`) anliegt,
   nimmt auf und stoppt nach `TRAIL` (1.5 s) Stille. `highpass 250 lowpass 3400`
   beschneidet auf das Sprachband.
2. **Plausibilität:** kürzer als `MINDUR` (1 s) = Störblip → verwerfen; länger als
   `MAXDUR` (90 s) = offener Squelch/Dauerstörung → verwerfen.
3. **Nachbearbeitung** mit ffmpeg: `afftdn` (FFT-Denoise) + `loudnorm`
   (I=-16, TP=-1.5) → gleichmäßig laute, entrauschte Mono-MP3 (96 kbit/s) unter
   `/srv/music/VHF-Aufnahmen/VHF_<zeit>.mp3`.
4. **Klassifikation** im Hintergrund (siehe unten). Störungen werden nach
   `.noise-VHF_<zeit>.mp3` umbenannt (versteckt, rückholbar).

Die OwnTone-/HomePod-Aufrufe im Recorder sind **bedingt** (`[ -x vhf-playout.sh ]`):
ohne das HomePod-Add-on werden sie übersprungen – der Nachhör-Kern ist eigenständig.

## 3. Störungs-Klassifikator (`bin/vhf-classify.py`)

Trennt echte Sprache von Trägern/Rauschen **gain-unabhängig** über den *Rhythmus* der
Lautstärke-Hüllkurve statt über absolute Pegel:

- `modIndex = std/mean` der Energie-Hüllkurve (Sprachband, Hüllkurve @100 Hz)
- `mod4` = Anteil der Hüllkurven-Energie im **2–8 Hz Silbentakt**

**Sprache**, wenn `MI_LO ≤ modIndex ≤ MI_HI` **und** `mod4 ≥ MOD4`
(Defaults 0.55 / 1.65 / 0.30). Dauerträger (modIndex zu niedrig) und erratisches
Rauschen (modIndex zu hoch) fallen raus. **Im Zweifel wird behalten** (Decode-Fehler,
sehr kurze Clips → KEEP). Entscheidungen landen in `/run/vhf/classify.log`.

## 4. Web-Replay (`bin/vhf-web.py`)

Ein stdlib-`ThreadingHTTPServer` auf **:8088**, kein Framework, kein root:

- **Liste** neueste zuerst (echte + aussortierte in einer Liste). Jede Zeile hat: eine
  **Play**-Taste (Wiedergabe im Browser), eine **Wellenform/VU-Übersicht** (Hüllkurve via
  `GET env?f=`, füllt sich mit dem Abspiel-Fortschritt), einen **gut** / **Störung**-Umschalter
  (Einordnung) und einen **Download**-Link.
- **Einordnen** (`POST classify?f=&as=speech|noise`) benennt die Datei zwischen `VHF_*`
  (gut) und `.noise-VHF_*` (Störung/versteckt) um; der Zustand steckt im Dateinamen, die
  Zeile hebt den aktiven Button hervor. Störung wird versteckt, nicht gelöscht (Cleanup entfernt sie).
- Löschen/Verschieben läuft über **Verzeichnisrechte** (Ordner `group audio`,
  group-writable) – der Dienst läuft als `DynamicUser` in Gruppe `audio`, nie als root.
- Pfad-Sicherheit: nur Dateinamen `VHF_*.mp3` / `.noise-VHF_*.mp3`, kein `/` oder `\`.

## 5. Aufräumung (`systemd/vhf-cleanup.*`)

`vhf-cleanup.timer` (täglich) löscht `.noise-*` älter als 1 Tag und `VHF_*.mp3` älter
als 7 Tage. Die Retention lässt sich in der `.service` (find `-mtime`) anpassen.

## Datenfluss der Dateizustände

```
   Aufnahme ──► VHF_<zeit>.mp3 ──(classify: Störung)──► .noise-VHF_<zeit>.mp3
                     ▲                                          │
                     └────────── „echt" zurückholen ◄───────────┘
   Cleanup:  .noise-* > 1 Tag  und  VHF_* > 7 Tage  →  gelöscht
```

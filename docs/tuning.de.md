# Tuning – VHF clear Audio replay

*🇩🇪 Deutsch · [🇬🇧 English](tuning.md)*

Alle Stellschrauben stehen als Konstanten oben in den Skripten. Nach Änderungen an
`/usr/local/bin/*` den jeweiligen Dienst neu starten
(`sudo systemctl restart vhf-recorder`).

## VOX / Rauschsperre (`bin/vhf-recorder.sh`)

| Variable | Default | Wirkung |
|---|---|---|
| `THRESH` | `3%` | VOX-Schwelle. Höher = nur lauterer Funk löst aus (weniger Fehlstarts, aber leise Sprüche gehen verloren). |
| `TRAIL` | `1.5` | Sekunden Stille, bis ein Spruch als beendet gilt. Höher = Sprechpausen brechen die Aufnahme nicht auf. |
| `MINDUR` | `1.0` | Kürzere Schnipsel (Störblips) werden verworfen. |
| `MAXDUR` | `90` | Sicherheits-Limit; längeres Signal = offener Squelch/Dauerstörung → verworfen. Auch per Env `VHF_MAXDUR`. |

**Symptom → Stellschraube**
- *Nimmt Rauschen auf:* `THRESH` erhöhen (z. B. `4%`), Squelch am Funkgerät zudrehen.
- *Verpasst leise Sprüche:* `THRESH` senken (z. B. `2%`).
- *Zerhackt lange Sprüche in Teile:* `TRAIL` erhöhen.

## Klang / „clear audio" (ffmpeg-Zeile im Recorder)

```
-af "afftdn=nf=-25,loudnorm=I=-16:TP=-1.5:LRA=11"
```

- `afftdn=nf=-25` – FFT-Rauschunterdrückung; aggressiver = `-20`, sanfter = `-30`.
- `loudnorm I=-16` – Ziel-Lautheit; lauter = `-14`, leiser = `-18`.
- Bandbreite kommt aus `sox … highpass 250 lowpass 3400` (Sprachband). MP3 96 kbit/s
  reicht für Funksprache; `-b:a` bei Bedarf hochsetzen.

## Störungs-Klassifikator (`bin/vhf-classify.py`, Env im Recorder)

Der Recorder exportiert die Schwellen; Regel: **Sprache**, wenn
`MI_LO ≤ modIndex ≤ MI_HI` **und** `mod4 ≥ MOD4`.

| Env | Default | Wirkung |
|---|---|---|
| `VHF_MI_LO` | `0.55` | untere Modulations-Grenze (darunter = Dauerträger) |
| `VHF_MI_HI` | `1.65` | obere Grenze (darüber = erratisches Rauschen) |
| `VHF_MOD4` | `0.30` | Mindestanteil im 2–8 Hz Silbentakt |

- **Enger stellen** (`MI_LO` hoch, `MI_HI` runter, `MOD4` hoch) = fängt mehr Störungen,
  Risiko echten Funk zu verlieren.
- **Weiter stellen** = sicherer, lässt mehr durch. Im Zweifel behält der Klassifikator.
- Kalibrieren: `tail -f /run/vhf/classify.log` – zeigt `modIdx`/`mod4` je Aufnahme mit
  KEEP/NOISE. Werte falsch einsortierter Clips ablesen und Grenzen nachziehen.
- Im Web unter „Aussortiert / ausgeblendet" lässt sich jede Fehlentscheidung anhören
  und mit **„echt"** zurückholen.

## Retention (`systemd/vhf-cleanup.service`)

```
find … -name ".noise-*"   -mtime +1 -delete     # Störungen > 1 Tag
find … -name "VHF_*.mp3"  -mtime +7 -delete     # Aufnahmen > 7 Tage
```

`+1` / `+7` anpassen für kürzere/längere Aufbewahrung. Timer läuft `OnCalendar=daily`.

## Speicherbedarf (Faustregel)

MP3 mono 96 kbit/s ≈ **12 kB/s** → ~43 MB pro Stunde reiner Sprache. Da nur Sprüche
aufgenommen werden, ist der reale Verbrauch weit geringer.

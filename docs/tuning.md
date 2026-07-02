# Tuning – VHF clear Audio replay

*[🇩🇪 Deutsch](tuning.de.md) · 🇬🇧 English*

All knobs are constants near the top of the scripts. After editing `/usr/local/bin/*`,
restart the relevant service (`sudo systemctl restart vhf-recorder`).

## VOX / squelch (`bin/vhf-recorder.sh`)

| Variable | Default | Effect |
|---|---|---|
| `THRESH` | `3%` | VOX threshold. Higher = only louder traffic triggers (fewer false starts, but quiet transmissions are lost). |
| `TRAIL` | `1.5` | Seconds of silence until a transmission counts as finished. Higher = speech pauses don't split the recording. |
| `MINDUR` | `1.0` | Shorter clips (noise blips) are discarded. |
| `MAXDUR` | `90` | Safety limit; a longer signal = open squelch / continuous interference → discarded. Also via env `VHF_MAXDUR`. |

**Symptom → knob**
- *Records noise:* raise `THRESH` (e.g. `4%`), close the squelch on the radio.
- *Misses quiet transmissions:* lower `THRESH` (e.g. `2%`).
- *Chops long transmissions into parts:* raise `TRAIL`.

## Sound / "clear audio" (ffmpeg line in the recorder)

```
-af "afftdn=nf=-25,loudnorm=I=-16:TP=-1.5:LRA=11"
```

- `afftdn=nf=-25` – FFT noise reduction; more aggressive = `-20`, gentler = `-30`.
- `loudnorm I=-16` – target loudness; louder = `-14`, quieter = `-18`.
- Bandwidth comes from `sox … highpass 250 lowpass 3400` (speech band). MP3 96 kbit/s is
  enough for radio speech; raise `-b:a` if desired.

## Interference classifier (`bin/vhf-classify.py`, env set in the recorder)

The recorder exports the thresholds; rule: **speech** if
`MI_LO ≤ modIndex ≤ MI_HI` **and** `mod4 ≥ MOD4`.

| Env | Default | Effect |
|---|---|---|
| `VHF_MI_LO` | `0.55` | lower modulation bound (below = continuous carrier) |
| `VHF_MI_HI` | `1.65` | upper bound (above = erratic noise) |
| `VHF_MOD4` | `0.30` | minimum share in the 2–8 Hz syllable rate |

- **Tighter** (`MI_LO` up, `MI_HI` down, `MOD4` up) = catches more noise, at the risk of
  losing real traffic.
- **Wider** = safer, lets more through. When in doubt the classifier keeps.
- Calibrate: `tail -f /run/vhf/classify.log` – shows `modIdx`/`mod4` per recording with
  KEEP/NOISE. Read off the values of misclassified clips and adjust the bounds.
- In the web UI under "Aussortiert / ausgeblendet" you can listen to any wrong decision
  and restore it with **"echt"** (real).

## Retention (`systemd/vhf-cleanup.service`)

```
find … -name ".noise-*"   -mtime +1 -delete     # noise > 1 day
find … -name "VHF_*.mp3"  -mtime +7 -delete     # recordings > 7 days
```

Adjust `+1` / `+7` for shorter/longer retention. The timer runs `OnCalendar=daily`.

## Storage footprint (rule of thumb)

MP3 mono 96 kbit/s ≈ **12 kB/s** → ~43 MB per hour of pure speech. Since only
transmissions are recorded, real usage is far lower.

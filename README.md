# Webcam Mic EQ & Diagnostics (`USB Camera MIC`)

**English** | [Русский](README.ru.md)

Fix muffled, boxy, low-end-heavy audio from USB webcam microphones **system-wide** across every application (Discord, Telegram, Zoom, Chrome/Meet, OBS, games) — with zero-latency native OS audio processing and Python FFT diagnostics.

Built and measured on a generic USB webcam (`USB\VID_0C45&PID_6301`, `"USB Camera MIC"`) for both **Windows (Equalizer APO)** and **Linux / Omarchy (PipeWire `filter-chain` & EasyEffects)**.

---

## Why This Exists (Measured Before & After)

Cheap/mid-range webcam mics placed near a desk or monitor suffer from two physical issues:
1. **Desk boundary boom & boxiness:** strong resonance peaks around **125 Hz** (`+11.2 dB`) and **400 Hz** (`+9.8 dB`).
2. **Collapsed upper-mids & highs:** a steep drop above `1.25 kHz` with a deep **4 kHz** notch (`-39.7 dB` relative to mids), pushing `95%` of speech energy below `604 Hz` (`379 Hz` spectral centroid) — making voices sound distant and muddy even though the capsule physically captures up to `12.5–16 kHz`.

Moving the webcam to the **top of the monitor** (mic hole facing down toward the speaker) removes the `400 Hz` desk-bounce peak on its own, and applying a lightweight 6-band biquad EQ restores clarity and air with **zero clipping**:

| Metric | Raw (`dry_metrics`) | Under Monitor + EQ (`live_test3`) | Top of Monitor + EQ (`live_top_eq`) |
|---|---:|---:|---:|
| **Spectral Centroid** | `379 Hz` | `1269 Hz` | `1048 Hz` |
| **95% Energy Rolloff** | `604 Hz` | `3481 Hz` | `3188 Hz` |
| **Boxiness (`400 Hz`)** | `+9.78 dB` | `+4.57 dB` | `-3.86 dB` |
| **Clarity Dip (`4 kHz`)** | `-39.70 dB` | `-19.28 dB` | `-18.40 dB` |
| **Presence/Treble (`5–8 kHz`)** | `-37.64 dB` | `-17.09 dB` | `-20.25 dB` |
| **Clipped Samples** | `0` | `0` | `0` |

---

## Repository Structure

```text
.
├── analyze_mic.py              # Cross-platform FFT / 1/3-octave / SNR analyzer (Python + numpy)
├── windows/
│   ├── config.txt              # Equalizer APO root router (Device: USB Camera MIC)
│   ├── mic-top.txt             # Active EQ profile for top-of-monitor placement
│   └── mic-bottom.txt          # EQ profile for under-monitor / desk-ledge placement
├── linux/
│   ├── 99-webcam-eq.conf       # Native PipeWire filter-chain config (same biquad math)
│   ├── AGENT_INSTALL.md        # Autonomous AI-agent setup runbook (EN, Omarchy/Arch/Linux)
│   └── AGENT_INSTALL.ru.md     # Autonomous AI-agent setup runbook (RU)
└── metrics/                    # Saved JSON benchmark reports (raw .wav files are gitignored)
```

---

## Quick Start: Windows (Equalizer APO)

### 1. Set Windows Mic Format (`mmsys.cpl`)
Open **Recording** -> **`Микрофон (USB Camera MIC)`** -> **Properties** -> **Advanced**:
- **Default Format:** **`1 channel, 16 bit, 48000 Hz (DVD Quality)`** *(critical: 16 kHz phone modes physically discard everything above 8 kHz)*.
- **Uncheck** both **Exclusive Mode** checkboxes so apps cannot bypass system APO processing.

### 2. Install Equalizer APO
In an **Administrator PowerShell**:
```powershell
choco install equalizerapo -y
```

### 3. Bind Equalizer APO to the Webcam Mic (`DeviceSelector.exe`)
> **Gotcha in Equalizer APO 1.4.2:** launching `DeviceSelector.exe` from another working directory can fail with `no Qt platform plugin could be initialized`. Run it from the install directory with explicit Qt paths in **Administrator PowerShell**:

```powershell
cd "C:\Program Files\EqualizerAPO"
$env:QT_PLUGIN_PATH = "C:\Program Files\EqualizerAPO\qt"
$env:QT_QPA_PLATFORM_PLUGIN_PATH = "C:\Program Files\EqualizerAPO\qt\platforms"
.\DeviceSelector.exe
```

In **Device Selector**:
1. Go to **Capture devices** and check **`USB Camera MIC`**.
2. If default `Pre-mix` does not engage after testing, select the row -> **Troubleshooting options** -> **`SFX/EFX`**.
3. Click **OK** (wait for the audio service restart, or reboot if prompted).

### 4. Deploy the Config
> **Permissions note:** Windows Audio (`NT AUTHORITY\LocalService`) cannot read files inside `C:\Users\<user>\...`. Keep `config.txt` and `mic.txt` directly inside `C:\Program Files\EqualizerAPO\config\`, which grants user write access by default.

```powershell
Copy-Item .\windows\config.txt "C:\Program Files\EqualizerAPO\config\config.txt" -Force
Copy-Item .\windows\mic-top.txt "C:\Program Files\EqualizerAPO\config\mic.txt" -Force
```

Edits to `mic.txt` apply **instantly on the fly** without rebooting.

<details>
<summary>Using under-monitor / desk-ledge placement instead?</summary>

Copy `windows\mic-bottom.txt` as `mic.txt` instead of `mic-top.txt` — it applies a stronger cut at `125 Hz` (`-6.5 dB`) and `380 Hz` (`-8.0 dB`) to compensate for desk boundary reflections.

</details>

---

## Quick Start: Linux / Omarchy (PipeWire)

> **Using an AI coding agent?** Point your agent to [linux/AGENT_INSTALL.md](linux/AGENT_INSTALL.md) (or [linux/AGENT_INSTALL.ru.md](linux/AGENT_INSTALL.ru.md)) for automated hardware detection, loop-safe `target.object` binding, and live spectrum verification.

### Option A: Native PipeWire `filter-chain` (No GUI, Zero Extra Apps)

Modern Linux distributions (including **Omarchy / Arch + Hyprland**, Ubuntu 22.10+, Fedora, Debian 12+) use PipeWire, which includes built-in RBJ biquad nodes (`bq_highpass`, `bq_peaking`, `bq_highshelf`) matching Equalizer APO math 1:1.

1. **Find your exact hardware webcam source** (ignore `.monitor` nodes):
   ```bash
   pactl list short sources
   ```
   Look for your camera source (e.g. `alsa_input.usb-0c45_6301-02.mono-fallback`).
2. **Install the PipeWire config:**
   ```bash
   mkdir -p ~/.config/pipewire/pipewire.conf.d
   cp linux/99-webcam-eq.conf ~/.config/pipewire/pipewire.conf.d/99-webcam-eq.conf
   ```
   Uncomment `target.object = "..."` in `capture.props` and paste your exact hardware `alsa_input...` source name to prevent routing loops.
3. **Restart PipeWire and WirePlumber:**
   ```bash
   systemctl --user restart pipewire pipewire-pulse wireplumber
   ```
4. **Set `USB Camera MIC (EQ)` as your default input:**
   ```bash
   wpctl status
   wpctl set-default <SOURCE_ID>
   ```
   *(All apps — Discord, Telegram, browsers, OBS — will now use the processed mic automatically. Adjust input gain with `pavucontrol` or `wpctl set-volume` if needed.)*

<details>
<summary>Option B: EasyEffects GUI (if you prefer sliders, compression, or RNNoise)</summary>

1. Install **EasyEffects** (`com.github.wwmm.easyeffects` Flatpak or distro package) + `lsp-plugins`.
2. Under **Input -> Equalizer**, enter the 7 bands from `windows/mic-top.txt`:
   - `HPF` `90 Hz` (12 dB/oct)
   - `Peak` `125 Hz`, `-4.5 dB`, `Q 1.5`
   - `Peak` `380 Hz`, `-4.0 dB`, `Q 1.1`
   - `Peak` `780 Hz`, `-3.5 dB`, `Q 1.6`
   - `Peak` `2000 Hz`, `+9.0 dB`, `Q 1.3`
   - `Peak` `4200 Hz`, `+9.5 dB`, `Q 1.4`
   - `High-Shelf` `5500 Hz`, `+8.5 dB`, `Q 0.71`
   - Output Gain: `+3.5 dB`
3. Enable background autostart (`easyeffects --gapplication-service`).

</details>

---

## Measure & Tune Your Own Mic (`analyze_mic.py`)

Requires `ffmpeg` and Python `numpy`. Record ~3–4 seconds of room silence followed by ~15 seconds of normal speech:

**Windows:**
```powershell
ffmpeg -y -f dshow -sample_rate 48000 -channels 1 -i audio="Микрофон (USB Camera MIC)" -t 20 -c:a pcm_s16le test.wav
python analyze_mic.py test.wav --json-out metrics/test.json
```

**Linux (PipeWire / PulseAudio):**
```bash
ffmpeg -y -f pulse -ac 1 -ar 48000 -i default -t 20 -c:a pcm_s16le test.wav
python3 analyze_mic.py test.wav --json-out metrics/test.json
```

---

## Practical Mic Tips (Zero Hardware Cost)

- **Top of monitor > under monitor:** keeps the mic out of desk reflections, keyboard noise, and hand/desk acoustic shadow.
- **Aim the mic pinhole:** make sure privacy shutters or monitor bezels don't partially cover the pinhole, and angle it slightly toward your face.
- **Disable aggressive AGC in voice apps:** turn off automatic gain control in Discord/Zoom/Telegram if it pumps room fan noise during pauses.

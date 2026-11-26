# AI Agent Runbook: Linux / Omarchy Installation & Verification

**English** | [Русский](AGENT_INSTALL.ru.md)

Autonomous setup guide for an AI coding agent running on Linux — tailored for **Omarchy (Arch Linux + Hyprland + PipeWire + WirePlumber)** and compatible with Ubuntu, Fedora, and Debian — using the USB webcam `VID_0C45:PID_6301` (`USB Camera MIC`).

Goal: configure **system-wide** microphone EQ (works in Discord, Telegram, Zoom, browsers, OBS, games) with minimal latency, bind it safely to the hardware webcam source, set it as default, and verify the frequency response with `analyze_mic.py`.

---

## Agent Rules

1. **Never guess device names** — query PipeWire / WirePlumber first (`wpctl status`, `pactl list short sources`).
2. **Prevent routing loops:** before setting `USB Camera MIC (EQ)` as the default source, always uncomment and set `target.object` in `linux/99-webcam-eq.conf` to the exact hardware `alsa_input...` node name.
3. **Respect PEP 668 (no global `pip install`):** on Arch/Omarchy, use system packages (`sudo pacman -S --needed ffmpeg python-numpy`) or a local `.venv`.
4. **Always restart `wireplumber` together with PipeWire** on Omarchy/Arch: `systemctl --user restart pipewire pipewire-pulse wireplumber`.
5. **Warn the user before recording:** never start a microphone test capture without letting the user know to stay silent for 3s (noise floor) and speak normally.

---

## Step 1. Check Audio Stack & Hardware

```bash
systemctl --user is-active pipewire pipewire-pulse wireplumber
pactl info | grep -E "Server Name|Default Source"
lsusb | grep -i 0c45 || true
```

- If `pipewire`, `pipewire-pulse`, and `wireplumber` are active (standard on Omarchy), follow the steps below.
- If the system runs legacy PulseAudio without PipeWire, inform the user and offer EasyEffects/PulseEffects using the parameters from `README.md`.

---

## Step 2. Identify Exact Webcam Source & Verify 48 kHz

List capture sources (ignore `.monitor` sources):

```bash
pactl list short sources
wpctl status
```

Look for the hardware webcam node matching `0c45` / `6301` / `USB_Camera` (typically `alsa_input.usb-0c45_6301-02.mono-fallback` or similar).

Verify sample rate and mute state:

```bash
pactl list sources | grep -A 15 -E "Name: .*0c45|Name: .*USB_Camera"
```

Confirm:
- Sample rate is `48000Hz` (not `16000Hz`).
- `Mute: no`.

If multiple USB mics are detected or placement is ambiguous, ask the user:
- **Top of monitor** (default in `linux/99-webcam-eq.conf`, mic facing down toward face).
- **Under monitor / on desk** (replace filter values with `windows/mic-bottom.txt`: `HP 92`, `125: -6.5`, `380: -8.0`, `2050: +7.5 Q=1.0`, `4500: +9.5 Q=1.4`, `HS 6200: +8.5`, remove `780`).

---

## Step 3. Install PipeWire `filter-chain` Config

1. Create the drop-in folder and copy the profile:
   ```bash
   mkdir -p ~/.config/pipewire/pipewire.conf.d
   cp linux/99-webcam-eq.conf ~/.config/pipewire/pipewire.conf.d/99-webcam-eq.conf
   ```
2. Inside `~/.config/pipewire/pipewire.conf.d/99-webcam-eq.conf` (`capture.props`), uncomment `target.object` and set it to the exact hardware `node.name` from Step 2:
   ```text
   target.object = "<EXACT_ALSA_INPUT_NODE_NAME>"
   ```
   *(On legacy PipeWire `< 0.3.64`, use `node.target` instead of `target.object`.)*

---

## Step 4. Restart Services, Set Default Source, and Check Logs

```bash
systemctl --user restart pipewire pipewire-pulse wireplumber
sleep 2
systemctl --user is-active pipewire pipewire-pulse wireplumber
journalctl --user -u pipewire -u wireplumber -n 30 --no-pager
```

Verify `USB Camera MIC (EQ)` (`filter_chain.webcam_eq_out`) appears and set it as default via `wpctl` (WirePlumber persists this across reboots):

```bash
wpctl status
# Find the ID of "USB Camera MIC (EQ)" under Audio -> Sources, then:
wpctl set-default <SOURCE_ID>
# Pulse-compatible alternative:
# pactl set-default-source filter_chain.webcam_eq_out
```

Optionally verify link topology:

```bash
pw-link -l | grep -A 3 -E "webcam_eq|0c45|USB_Camera" || true
```

---

## Step 5. Live Spectrum Verification (`analyze_mic.py`)

1. Check `ffmpeg` and `numpy`:
   ```bash
   command -v ffmpeg
   python3 -c "import numpy; print(numpy.__version__)"
   ```
   On Omarchy/Arch, install missing packages via `sudo pacman -S --needed ffmpeg python-numpy` (with user permission) or create a local `.venv` for `numpy` (`python3 -m venv .venv && .venv/bin/pip install numpy`).
2. Tell the user: **"Starting a 20-second recording: stay quiet for 3 seconds (noise floor), then speak normally (including sibilants like 's/sh')".**
3. Once confirmed, capture from the default source (`USB Camera MIC (EQ)`) and analyze:
   ```bash
   ffmpeg -y -hide_banner -f pulse -ac 1 -ar 48000 -i default -t 20 -c:a pcm_s16le test_linux.wav
   python3 analyze_mic.py test_linux.wav --json-out metrics/test_linux.json
   ```
4. Check `metrics/test_linux.json` against `metrics/dry_metrics.json` and `metrics/live_top_eq_metrics.json`:
   - `sample_rate_hz == 48000`, `clipped_samples == 0`
   - `global_peak_dbfs` around `-10 .. -2 dBFS` (if quieter than `-10 dBFS`, gently raise capture volume via `wpctl set-volume` / `pactl set-source-volume` without clipping; Windows `mic-top.txt` uses `+3.5 dB` preamp)
   - `spectral_centroid_hz` rises from `~379 Hz` to `~900–1300 Hz`; `spectral_rolloff_95_hz` reaches `~2800–3600 Hz`
   - `400 Hz` boom is gone and `4000 Hz` clarity dip is restored.
5. Remove `test_linux.wav` when done (`*.wav` is gitignored).

---

## Step 6. App Checklist

Remind the user:
- In Discord / Telegram / Zoom / Chrome / OBS, input should be **Default** or **`USB Camera MIC (EQ)`**.
- Disable aggressive AGC in voice apps if it boosts background fan noise during silence.

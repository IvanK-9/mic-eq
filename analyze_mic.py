"""Analyze a WAV recording from a microphone for voice EQ & noise diagnostics."""

from __future__ import annotations

import argparse
import json
import math
import sys
import wave
from pathlib import Path

import numpy as np


def load_wav_mono(path: Path) -> tuple[np.ndarray, int]:
    """Load a PCM WAV file as float64 mono normalized to [-1, 1]."""
    with wave.open(str(path), "rb") as wf:
        sr = wf.getframerate()
        nch = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        nframes = wf.getnframes()
        raw = wf.readframes(nframes)

    if sampwidth == 2:
        data = np.frombuffer(raw, dtype=np.int16).astype(np.float64) / 32768.0
    elif sampwidth == 4:
        data = np.frombuffer(raw, dtype=np.int32).astype(np.float64) / 2147483648.0
    elif sampwidth == 1:
        data = (np.frombuffer(raw, dtype=np.uint8).astype(np.float64) - 128.0) / 128.0
    else:
        raise ValueError(f"Unsupported sample width: {sampwidth} bytes")

    if nch > 1:
        data = data.reshape(-1, nch).mean(axis=1)
    return data, sr


def db(val: float, floor: float = 1e-12) -> float:
    return 20.0 * math.log10(max(val, floor))


def power_db(val: float, floor: float = 1e-24) -> float:
    return 10.0 * math.log10(max(val, floor))


def segment_speech_and_noise(
    samples: np.ndarray, sr: int, frame_ms: float = 30.0
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Split frames into noise-floor and active-speech masks."""
    frame_len = max(1, int(sr * frame_ms / 1000.0))
    n_frames = len(samples) // frame_len
    if n_frames == 0:
        raise ValueError("Audio too short for frame analysis")

    trimmed = samples[: n_frames * frame_len].reshape(n_frames, frame_len)
    frame_rms = np.sqrt(np.mean(trimmed**2, axis=1) + 1e-24)
    frame_db = 20.0 * np.log10(frame_rms)

    noise_est_db = float(np.percentile(frame_db, 20))
    peak_frame_db = float(np.percentile(frame_db, 95))
    speech_thresh_db = max(noise_est_db + 8.0, peak_frame_db - 22.0)

    speech_mask = frame_db >= speech_thresh_db
    noise_mask = frame_db <= (noise_est_db + 3.0)

    if not np.any(speech_mask):
        speech_mask = frame_db >= np.percentile(frame_db, 60)

    return trimmed, speech_mask, noise_mask


def compute_avg_psd(
    samples: np.ndarray, sr: int, mask: np.ndarray, frame_ms: float = 30.0, nfft: int = 8192
) -> tuple[np.ndarray, np.ndarray]:
    """Compute average power spectral density over masked frames."""
    frame_len = max(1, int(sr * frame_ms / 1000.0))
    indices = np.where(mask)[0]
    if len(indices) == 0:
        freqs = np.fft.rfftfreq(nfft, 1.0 / sr)
        return freqs, np.full_like(freqs, 1e-24)

    # Concatenate contiguous masked regions and take overlapping Hann windows
    selected = np.concatenate([samples[i * frame_len : (i + 1) * frame_len] for i in indices])
    if len(selected) < nfft:
        selected = np.pad(selected, (0, nfft - len(selected)))

    hop = nfft // 2
    win = np.hanning(nfft)
    win_norm = np.sum(win**2)

    acc = None
    count = 0
    for start in range(0, len(selected) - nfft + 1, hop):
        seg = selected[start : start + nfft] * win
        spec = np.fft.rfft(seg)
        psd = (np.abs(spec) ** 2) / win_norm
        acc = psd if acc is None else (acc + psd)
        count += 1

    freqs = np.fft.rfftfreq(nfft, 1.0 / sr)
    return freqs, acc / max(1, count)


def band_level_db(freqs: np.ndarray, psd: np.ndarray, f_lo: float, f_hi: float) -> float:
    mask = (freqs >= f_lo) & (freqs < f_hi)
    if not np.any(mask):
        return -120.0
    # Total RMS-equivalent band power (sum of FFT bin powers, doubled for positive freqs)
    band_power = float(np.sum(psd[mask]) * 2.0 / len(freqs))
    return power_db(band_power)


def band_mean_density_db(freqs: np.ndarray, psd: np.ndarray, f_lo: float, f_hi: float) -> float:
    """Mean power density per Hz in band (good for comparing EQ tilt across different bandwidths)."""
    mask = (freqs >= f_lo) & (freqs < f_hi)
    if not np.any(mask):
        return -120.0
    return power_db(float(np.mean(psd[mask])))


def analyze(path: Path) -> dict:
    samples, sr = load_wav_mono(path)
    duration = len(samples) / sr
    dc_offset = float(np.mean(samples))
    centered = samples - dc_offset

    peak_amp = float(np.max(np.abs(centered)))
    rms_amp = float(np.sqrt(np.mean(centered**2)))
    clip_count = int(np.sum(np.abs(samples) >= 0.999))

    frames, speech_mask, noise_mask = segment_speech_and_noise(centered, sr)
    speech_samples = frames[speech_mask].ravel()
    noise_samples = frames[noise_mask].ravel() if np.any(noise_mask) else frames[~speech_mask].ravel()

    speech_rms = float(np.sqrt(np.mean(speech_samples**2) + 1e-24))
    noise_rms = float(np.sqrt(np.mean(noise_samples**2) + 1e-24)) if len(noise_samples) else 1e-12
    snr_db = db(speech_rms) - db(noise_rms)

    freqs, speech_psd = compute_avg_psd(centered, sr, speech_mask)
    _, noise_psd = compute_avg_psd(centered, sr, noise_mask)

    # Voice bands (mean density in dB/Hz and relative to 500-2000 Hz anchor)
    voice_bands = [
        ("sub_rumble_20_80", 20.0, 80.0),
        ("bass_80_200", 80.0, 200.0),
        ("low_mid_mud_200_500", 200.0, 500.0),
        ("mid_500_1200", 500.0, 1200.0),
        ("upper_mid_1200_2500", 1200.0, 2500.0),
        ("presence_2500_5000", 2500.0, 5000.0),
        ("sibilance_5000_8000", 5000.0, 8000.0),
        ("brilliance_8000_12000", 8000.0, 12000.0),
        ("air_12000_16000", 12000.0, 16000.0),
        ("ultra_16000_22000", 16000.0, 22000.0),
    ]

    anchor_db = band_mean_density_db(freqs, speech_psd, 400.0, 1600.0)
    band_summary = {}
    for name, f_lo, f_hi in voice_bands:
        if f_lo >= sr / 2:
            continue
        f_hi_eff = min(f_hi, sr / 2 - 1.0)
        sp_db = band_mean_density_db(freqs, speech_psd, f_lo, f_hi_eff)
        ns_db = band_mean_density_db(freqs, noise_psd, f_lo, f_hi_eff)
        band_summary[name] = {
            "range_hz": [f_lo, f_hi_eff],
            "speech_density_db": round(sp_db, 2),
            "rel_to_mid_db": round(sp_db - anchor_db, 2),
            "noise_density_db": round(ns_db, 2),
            "band_snr_db": round(sp_db - ns_db, 2),
        }

    # 1/3 octave centers from 40 Hz to 16000 Hz
    third_oct_centers = [
        40, 50, 63, 80, 100, 125, 160, 200, 250, 315, 400, 500, 630, 800,
        1000, 1250, 1600, 2000, 2500, 3150, 4000, 5000, 6300, 8000, 10000, 12500, 16000
    ]
    third_oct = {}
    factor = 2.0 ** (1.0 / 6.0)
    for fc in third_oct_centers:
        if fc * factor > sr / 2:
            continue
        val = band_mean_density_db(freqs, speech_psd, fc / factor, fc * factor)
        ns = band_mean_density_db(freqs, noise_psd, fc / factor, fc * factor)
        third_oct[str(fc)] = {
            "speech_db": round(val, 2),
            "rel_mid_db": round(val - anchor_db, 2),
            "snr_db": round(val - ns, 2),
        }

    # Spectral centroid & rolloff (50 Hz .. Nyquist)
    valid = (freqs >= 50.0) & (freqs <= sr / 2 - 100.0)
    vf = freqs[valid]
    vp = speech_psd[valid]
    total_p = float(np.sum(vp)) + 1e-24
    centroid_hz = float(np.sum(vf * vp) / total_p)
    cum = np.cumsum(vp) / total_p
    rolloff_85 = float(vf[np.searchsorted(cum, 0.85)])
    rolloff_95 = float(vf[np.searchsorted(cum, 0.95)])

    # Check mains hum (50/60 Hz and harmonics) in noise floor
    hum_checks = {}
    for target in [50, 60, 100, 120, 150]:
        local = (freqs >= target - 12) & (freqs <= target + 12)
        tone = (freqs >= target - 2.5) & (freqs <= target + 2.5)
        if np.any(local) and np.any(tone):
            bg = float(np.median(noise_psd[local]))
            pk = float(np.max(noise_psd[tone]))
            hum_checks[f"{target}Hz_excess_db"] = round(power_db(pk) - power_db(bg), 2)

    # Effective upper cutoff where speech density drops within 3 dB of noise floor (above 2 kHz)
    effective_bw_hz = 0
    for fc_str, info in third_oct.items():
        if int(fc_str) >= 2000 and info["snr_db"] >= 4.0:
            effective_bw_hz = int(fc_str)

    return {
        "file": str(path),
        "sample_rate_hz": sr,
        "duration_sec": round(duration, 2),
        "dc_offset": round(dc_offset, 6),
        "global_peak_dbfs": round(db(peak_amp), 2),
        "global_rms_dbfs": round(db(rms_amp), 2),
        "speech_rms_dbfs": round(db(speech_rms), 2),
        "noise_floor_dbfs": round(db(noise_rms), 2),
        "estimated_snr_db": round(snr_db, 2),
        "crest_factor_db": round(db(peak_amp) - db(speech_rms), 2),
        "clipped_samples": clip_count,
        "speech_active_pct": round(100.0 * float(np.mean(speech_mask)), 1),
        "spectral_centroid_hz": round(centroid_hz, 1),
        "spectral_rolloff_85_hz": round(rolloff_85, 1),
        "spectral_rolloff_95_hz": round(rolloff_95, 1),
        "effective_speech_bw_hz": effective_bw_hz,
        "hum_checks": hum_checks,
        "bands": band_summary,
        "third_octave": third_oct,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze microphone WAV recording.")
    parser.add_argument("wav_path", type=Path, help="Path to WAV file")
    parser.add_argument("--json-out", type=Path, default=None, help="Optional JSON report output")
    args = parser.parse_args()

    result = analyze(args.wav_path)
    if args.json_out:
        args.json_out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

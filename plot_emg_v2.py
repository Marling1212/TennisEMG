
"""
plot_emg_v2.py
Advanced EMG Analysis and Visualization Tool based on Wang (2025) & SENIAM Protocol.

Key Features:
- Supports up to 5 Forearm Target Muscles:
    1. PT   (Pronator Teres, 旋前圓肌)
    2. FCU  (Flexor Carpi Ulnaris, 尺側屈腕肌)
    3. FCR  (Flexor Carpi Radialis, 撓側屈腕肌)
    4. ECRB (Extensor Carpi Radialis Brevis, 短撓側伸腕肌)
    5. SP   (Supinator, 旋後肌)
  (Automatically backwards-compatible with legacy 1-, 2-, and 3-channel CSV files)
- Signal Processing:
    1. Baseline DC Offset removal
    2. Adaptive Bandpass / Lowpass Butterworth filter (or Moving RMS)
    3. Full-wave rectification (Absolute value)
    4. Linear envelope extraction
- %MVC Normalization (Maximum Voluntary Contraction):
    - Normalizes raw activation to %MVC using an MVC reference trial or calibration profile
    - Eliminates inter-individual anatomical and impedance differences
- Biomechanics Metrics:
    - Peak %MVC & Mean activation per muscle
    - Co-activation analysis (Pronation/Supination & Flexion/Extension ratios)
"""

import os
import sys
import csv
import json
import argparse
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import butter, filtfilt

# Ensure UTF-8 output in Windows command prompt / PowerShell
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# Configure fonts for Chinese and English bilingual display
plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'PingFang TC', 'SimHei', 'DejaVu Sans', 'Arial', 'sans-serif']
plt.rcParams['axes.unicode_minus'] = False


# --- MUSCLE DEFINITIONS (Wang 2025 & SENIAM) ---
FIVE_MUSCLE_LABELS = [
    {"abbr": "PT",   "name_en": "Pronator Teres",             "name_zh": "旋前圓肌",   "color": "#1f77b4"}, # Blue
    {"abbr": "FCU",  "name_en": "Flexor Carpi Ulnaris",       "name_zh": "尺側屈腕肌", "color": "#d62728"}, # Red
    {"abbr": "FCR",  "name_en": "Flexor Carpi Radialis",      "name_zh": "撓側屈腕肌", "color": "#ff7f0e"}, # Orange
    {"abbr": "ECRB", "name_en": "Extensor Carpi Radialis Br.", "name_zh": "短撓側伸腕肌", "color": "#2ca02c"}, # Green
    {"abbr": "SP",   "name_en": "Supinator",                  "name_zh": "旋後肌",     "color": "#9467bd"}, # Purple
]

LEGACY_THREE_CHANNELS = [
    {"abbr": "FCR",  "name_en": "Flexor Carpi Radialis",      "name_zh": "撓側屈腕肌", "color": "#1f77b4"}, # Blue
    {"abbr": "FCU",  "name_en": "Flexor Carpi Ulnaris",       "name_zh": "尺側屈腕肌", "color": "#d62728"}, # Red
    {"abbr": "ECRB", "name_en": "Extensor Carpi Radialis Br.", "name_zh": "短撓側伸腕肌", "color": "#2ca02c"}, # Green
]

MVC_CONFIG_FILE = "mvc_calibration.json"


def load_emg_csv(filename):
    """
    Reads an EMG CSV file and parses time and channel columns.
    Returns: time_data (np.array), channels_data (list of np.array)
    """
    if not os.path.exists(filename):
        raise FileNotFoundError(f"File '{filename}' not found.")

    time_list = []
    channels_raw = []

    with open(filename, 'r', encoding='utf-8', errors='ignore') as f:
        reader = csv.reader(f)
        for row in reader:
            if not row or row[0].startswith('#'):
                continue
            try:
                values = [float(v.strip()) for v in row if v.strip() != '']
                if len(values) >= 2:
                    t = values[0]
                    ch_vals = values[1:]
                    time_list.append(t)
                    
                    # Initialize channel lists dynamically
                    while len(channels_raw) < len(ch_vals):
                        channels_raw.append([])
                    
                    for ch_idx, val in enumerate(ch_vals):
                        channels_raw[ch_idx].append(val)
            except ValueError:
                continue

    if not time_list:
        raise ValueError(f"No valid numerical data found in '{filename}'.")

    time_arr = np.array(time_list)
    channels_arr = [np.array(ch) for ch in channels_raw]
    return time_arr, channels_arr


def estimate_sampling_rate(time_arr):
    """
    Estimates sampling frequency (Hz) from timestamp array in milliseconds.
    """
    if len(time_arr) < 2:
        return 100.0  # default fallback
    diffs = np.diff(time_arr)
    median_dt_ms = np.median(diffs[diffs > 0])
    if median_dt_ms <= 0:
        return 100.0
    fs = 1000.0 / median_dt_ms
    return fs


def process_emg_signal(raw_data, fs, cutoff_envelope=6.0):
    """
    Standard Biomechanics EMG Signal Processing Pipeline:
    1. DC offset removal (resting baseline subtraction)
    2. Zero-phase Bandpass / High-pass (if fs allows)
    3. Full-wave rectification (|x|)
    4. Linear envelope via 4th-order zero-phase Butterworth low-pass filter
    """
    raw_data = np.array(raw_data, dtype=float)
    n_samples = len(raw_data)
    if n_samples == 0:
        return raw_data

    # 1. Baseline DC Offset Removal (first 200 samples or 10% of signal)
    baseline_len = min(200, max(10, int(n_samples * 0.1)))
    baseline = np.mean(raw_data[:baseline_len])
    centered = raw_data - baseline

    # 2. Bandpass filtering if sampling rate is high enough (e.g. > 100 Hz)
    nyquist = 0.5 * fs
    filtered = centered
    if fs >= 100.0 and nyquist > 20.0:
        low_cut = 20.0
        high_cut = min(450.0, nyquist * 0.95)
        if high_cut > low_cut:
            try:
                b, a = butter(2, [low_cut / nyquist, high_cut / nyquist], btype='bandpass')
                filtered = filtfilt(b, a, centered)
            except Exception:
                filtered = centered

    # 3. Full-Wave Rectification
    rectified = np.abs(filtered)

    # 4. Linear Envelope (Butterworth Lowpass Filter, default 6 Hz)
    # Ensure cutoff is safely below Nyquist
    actual_cutoff = min(cutoff_envelope, nyquist * 0.4)
    if actual_cutoff > 0 and n_samples > 15:
        try:
            b_low, a_low = butter(2, actual_cutoff / nyquist, btype='lowpass')
            envelope = filtfilt(b_low, a_low, rectified)
            envelope = np.maximum(0, envelope)  # Non-negative
        except Exception:
            # Fallback: Moving Average
            win = max(5, int(fs * 0.1))
            envelope = np.convolve(rectified, np.ones(win)/win, mode='same')
    else:
        win = max(5, int(fs * 0.1))
        envelope = np.convolve(rectified, np.ones(win)/win, mode='same')

    return envelope


def calculate_mvc_peaks(channels_processed):
    """
    Calculates the 99th percentile or peak 500ms activation for each channel
    to serve as the MVC maximum reference level.
    """
    mvc_peaks = []
    for ch_data in channels_processed:
        if len(ch_data) == 0:
            mvc_peaks.append(1.0)
            continue
        # Use 99th percentile to be robust against single-sample noise spikes
        peak_val = float(np.percentile(ch_data, 99))
        mvc_peaks.append(max(peak_val, 1e-3))
    return mvc_peaks


def load_saved_mvc():
    """Loads saved MVC calibration peaks if available."""
    if os.path.exists(MVC_CONFIG_FILE):
        try:
            with open(MVC_CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return None


def save_mvc_calibration(mvc_dict):
    """Saves MVC calibration peaks to disk."""
    with open(MVC_CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(mvc_dict, f, indent=4)
    print(f"MVC Calibration saved to '{MVC_CONFIG_FILE}'.")


def get_muscle_meta(num_channels):
    """
    Determines muscle labeling based on channel count:
    - 5 channels: Wang (2025) 5-muscle setup (PT, FCU, FCR, ECRB, SP)
    - 3 channels: Legacy 3-muscle setup (FCR, FCU, ECRB)
    - Other counts: Default labels
    """
    if num_channels == 5:
        return FIVE_MUSCLE_LABELS
    elif num_channels == 3:
        return LEGACY_THREE_CHANNELS
    elif num_channels == 2:
        return LEGACY_THREE_CHANNELS[:2]
    else:
        palette = ["#1f77b4", "#d62728", "#ff7f0e", "#2ca02c", "#9467bd", "#8c564b", "#e377c2"]
        return [
            {
                "abbr": f"CH{i+1}",
                "name_en": f"Channel {i+1}",
                "name_zh": f"通道 {i+1}",
                "color": palette[i % len(palette)]
            }
            for i in range(num_channels)
        ]


def detect_trigger_channel(channels_arr, explicit_trigger_idx=None):
    """
    Detects if any channel represents a hardware trigger pulse (e.g. OptiTrack 200 Hz sync trigger).
    A trigger channel typically has binary / step values (e.g. 0 and 1 or 0 and 5V).
    Returns: emg_channels (list), trigger_channel (np.array or None), trigger_idx (int or None)
    """
    if explicit_trigger_idx is not None and 0 <= explicit_trigger_idx < len(channels_arr):
        trig = channels_arr[explicit_trigger_idx]
        emg = [ch for i, ch in enumerate(channels_arr) if i != explicit_trigger_idx]
        return emg, trig, explicit_trigger_idx

    # If 6 channels are present, default assumption is 5 EMG + 1 Trigger (Wang 2025)
    if len(channels_arr) == 6:
        trig = channels_arr[5]
        emg = channels_arr[:5]
        return emg, trig, 5

    # Auto-detection: scan for binary channel
    for idx, ch in enumerate(channels_arr):
        if len(ch) > 10:
            uniq = np.unique(ch)
            if len(uniq) <= 4 and (np.max(uniq) - np.min(uniq)) >= 0.8:
                emg = [c for i, c in enumerate(channels_arr) if i != idx]
                return emg, ch, idx

    return channels_arr, None, None


def find_trigger_events(trigger_data, time_arr):
    """
    Finds rising edge trigger timestamps (e.g. OptiTrack motion capture sync).
    """
    if trigger_data is None or len(trigger_data) < 2:
        return []
    threshold = (np.max(trigger_data) + np.min(trigger_data)) / 2.0
    binary = (trigger_data > threshold).astype(int)
    rising_edges = np.where(np.diff(binary) == 1)[0] + 1
    return [time_arr[idx] for idx in rising_edges]


def plot_emg_v2(filename, mvc_file=None, save_fig=False, trigger_col=None, no_show=False):
    """
    Main processing and plotting function.
    """
    print(f"Reading {filename}...")
    time_arr, all_channels_raw = load_emg_csv(filename)
    fs = estimate_sampling_rate(time_arr)

    # Separate EMG channels from trigger synchronization pulse
    channels_raw, trigger_raw, trig_col_idx = detect_trigger_channel(all_channels_raw, trigger_col)
    trigger_times = find_trigger_events(trigger_raw, time_arr) if trigger_raw is not None else []

    num_channels = len(channels_raw)
    print(f"Detected {num_channels} EMG channel(s). Estimated sampling rate: {fs:.1f} Hz.")
    if trigger_raw is not None:
        print(f"OptiTrack Hardware Trigger Pulse detected on Channel {trig_col_idx+1} ({len(trigger_times)} sync event(s)).")

    # Muscle metadata
    muscle_meta = get_muscle_meta(num_channels)

    # Process all channels into envelopes
    channels_envelope = [process_emg_signal(ch, fs) for ch in channels_raw]

    # Handle MVC Normalization
    mvc_source_info = "Not normalized (Raw Envelope Units)"
    mvc_values = None
    is_mvc_normalized = False

    if mvc_file:
        print(f"Calculating MVC baseline from reference file: {mvc_file}...")
        _, mvc_raw = load_emg_csv(mvc_file)
        mvc_envelopes = [process_emg_signal(ch, fs) for ch in mvc_raw]
        mvc_values = calculate_mvc_peaks(mvc_envelopes)
        mvc_source_info = f"Normalized to MVC file: {os.path.basename(mvc_file)}"
        is_mvc_normalized = True
    else:
        # Check saved MVC config
        saved_mvc = load_saved_mvc()
        if saved_mvc and "peaks" in saved_mvc and len(saved_mvc["peaks"]) >= num_channels:
            mvc_values = saved_mvc["peaks"][:num_channels]
            mvc_source_info = f"Normalized to saved profile: '{saved_mvc.get('profile_name', 'Default')}'"
            is_mvc_normalized = True

    # Calculate normalized activation (%MVC)
    channels_display = []
    peak_metrics = []
    mean_metrics = []

    for i in range(num_channels):
        env = channels_envelope[i]
        if is_mvc_normalized and mvc_values and i < len(mvc_values) and mvc_values[i] > 0:
            norm = (env / mvc_values[i]) * 100.0
            channels_display.append(norm)
            peak_metrics.append(np.max(norm))
            mean_metrics.append(np.mean(norm))
        else:
            channels_display.append(env)
            peak_metrics.append(np.max(env))
            mean_metrics.append(np.mean(env))

    # --- Print Summary Metrics in Console ---
    print("\n" + "=" * 65)
    print("      FOREARM EMG ACTIVATION SUMMARY (Wang 2025 Standard)      ")
    print("=" * 65)
    metric_unit = "%MVC" if is_mvc_normalized else "Units"
    for i in range(num_channels):
        m = muscle_meta[i]
        print(f"[{m['abbr']:4s}] {m['name_zh']:6s} ({m['name_en']:24s}): Peak={peak_metrics[i]:6.1f} {metric_unit} | Mean={mean_metrics[i]:6.1f} {metric_unit}")
    
    # Biomechanics Co-activation Analysis for 5-channel Tennis Forehand
    if num_channels == 5:
        # Channels: 0:PT, 1:FCU, 2:FCR, 3:ECRB, 4:SP
        pt_peak = peak_metrics[0]
        sp_peak = peak_metrics[4]
        flex_peak = (peak_metrics[1] + peak_metrics[2]) / 2.0
        ext_peak = peak_metrics[3]
        
        pronation_ratio = pt_peak / (sp_peak + 1e-4)
        flex_ext_ratio = flex_peak / (ext_peak + 1e-4)
        
        print("-" * 65)
        print("  Tennis Forehand Biomechanical Balance Ratios:")
        print(f"  • Pronation / Supination Balance (PT / SP)      : {pronation_ratio:.2f}")
        print(f"  • Wrist Flexion / Extension Balance (Flex / Ext): {flex_ext_ratio:.2f}")
    print("=" * 65 + "\n")

    # --- Multi-Panel Figure Layout ---
    fig = plt.figure(figsize=(14, 9))
    gs = fig.add_gridspec(3, 3, height_ratios=[1.2, 1.2, 0.9])

    ax_raw = fig.add_subplot(gs[0, :])
    ax_env = fig.add_subplot(gs[1, :], sharex=ax_raw)
    ax_bar = fig.add_subplot(gs[2, :2])
    ax_info = fig.add_subplot(gs[2, 2])
    ax_info.axis('off')

    # 1. Top Panel: Raw Signals
    for i in range(num_channels):
        m = muscle_meta[i]
        ax_raw.plot(time_arr, channels_raw[i], color=m['color'], alpha=0.65, linewidth=1.0,
                    label=f"{m['abbr']}: {m['name_zh']} ({m['name_en']})")
    
    if trigger_times:
        for trig_t in trigger_times:
            ax_raw.axvline(x=trig_t, color='#d62728', linestyle='--', linewidth=1.5, alpha=0.85,
                           label='OptiTrack Sync Trigger' if trig_t == trigger_times[0] else None)

    ax_raw.set_title(f"Raw EMG Signals: {os.path.basename(filename)} (Fs ~ {fs:.0f} Hz)", fontsize=12, fontweight='bold')
    ax_raw.set_ylabel("Raw ADC Value", fontsize=10)
    ax_raw.legend(loc='upper right', framealpha=0.9, fontsize=9)
    ax_raw.grid(True, linestyle='--', alpha=0.5)

    # 2. Middle Panel: Processed Signal (Linear Envelope / %MVC)
    for i in range(num_channels):
        m = muscle_meta[i]
        ax_env.plot(time_arr, channels_display[i], color=m['color'], linewidth=2.0,
                    label=f"{m['abbr']} Envelope")

    if trigger_times:
        for trig_t in trigger_times:
            ax_env.axvline(x=trig_t, color='#d62728', linestyle='--', linewidth=1.5, alpha=0.85,
                           label='OptiTrack Sync Trigger' if trig_t == trigger_times[0] else None)
    
    y_label = "% MVC Activation" if is_mvc_normalized else "Activation Level (Envelope)"
    ax_env.set_title(f"Processed Linear Envelope (DC-removed + Rectified + 6Hz Lowpass) | {mvc_source_info}",
                     fontsize=11, fontweight='bold')
    ax_env.set_xlabel("Time (ms)", fontsize=10)
    ax_env.set_ylabel(y_label, fontsize=10)
    ax_env.legend(loc='upper right', framealpha=0.9, fontsize=9)
    ax_env.grid(True, linestyle='--', alpha=0.5)

    # 3. Bottom-Left Panel: Peak & Mean Comparison Bar Chart
    x_indices = np.arange(num_channels)
    bar_width = 0.35
    abbr_labels = [m['abbr'] for m in muscle_meta]
    bar_colors = [m['color'] for m in muscle_meta]

    ax_bar.bar(x_indices - bar_width/2, peak_metrics, bar_width, label='Peak Activation',
               color=bar_colors, alpha=0.9)
    ax_bar.bar(x_indices + bar_width/2, mean_metrics, bar_width, label='Mean Activation',
               color=bar_colors, alpha=0.45, hatch='//')
    
    ax_bar.set_xticks(x_indices)
    ax_bar.set_xticklabels([f"{m['abbr']}\n{m['name_zh']}" for m in muscle_meta], fontsize=9)
    ax_bar.set_ylabel(f"Activation ({metric_unit})", fontsize=10)
    ax_bar.set_title("Muscle Activation Comparison", fontsize=11, fontweight='bold')
    ax_bar.legend(loc='upper right', fontsize=8)
    ax_bar.grid(axis='y', linestyle='--', alpha=0.5)

    # 4. Bottom-Right Panel: Research Summary Card
    info_text = (
        f"Wang (2025) EMG Protocol\n"
        f"────────────────────────\n"
        f"• File: {os.path.basename(filename)[:22]}\n"
        f"• Channels: {num_channels} Active\n"
        f"• MVC Status: {'Calibrated (%MVC)' if is_mvc_normalized else 'Uncalibrated'}\n"
        f"• Duration: {(time_arr[-1]-time_arr[0])/1000.0:.2f} s\n"
    )
    if trigger_times:
        info_text += f"• Sync Trigger: {len(trigger_times)} events (OptiTrack)\n"
    if num_channels == 5:
        info_text += (
            f"\nForearm Mechanics:\n"
            f"• PT/SP Ratio: {pt_peak/(sp_peak+1e-4):.2f}\n"
            f"• Flex/Ext Ratio: {flex_peak/(ext_peak+1e-4):.2f}\n"
        )
    ax_info.text(0.05, 0.95, info_text, transform=ax_info.transAxes, verticalalignment='top',
                 fontsize=10, family='monospace', bbox=dict(boxstyle='round,pad=0.6', facecolor='#f4f4f4', edgecolor='#cccccc'))

    plt.tight_layout()

    if save_fig:
        out_img = os.path.splitext(filename)[0] + "_analysis_v2.png"
        plt.savefig(out_img, dpi=300)
        print(f"Figure saved to: {out_img}")

    if not no_show:
        plt.show()
    else:
        plt.close(fig)


def calibrate_mvc_cli(filenames, profile_name="default"):
    """
    Extracts global maximum voluntary contraction (MVC) peaks across multiple isolated trials
    (e.g. Wrist Flexion trial + Wrist Extension trial + Grip trial).
    """
    if isinstance(filenames, str):
        filenames = [filenames]

    # Check if there is an existing calibration to incrementally update
    saved = load_saved_mvc()
    if saved and "peaks" in saved and len(saved["peaks"]) > 0:
        global_peaks = list(saved["peaks"])
        sources = list(saved.get("source_files", [saved.get("source_file", "")]))
        num_channels = len(global_peaks)
        muscle_meta = get_muscle_meta(num_channels)
    else:
        global_peaks = None
        muscle_meta = None
        num_channels = None
        sources = []

    for fname in filenames:
        if not os.path.exists(fname):
            print(f"Warning: MVC file '{fname}' not found. Skipping.")
            continue
        print(f"Extracting MVC from: {fname}...")
        time_arr, channels_raw = load_emg_csv(fname)
        n_ch = len(channels_raw)
        fs = estimate_sampling_rate(time_arr)
        
        if muscle_meta is None:
            num_channels = n_ch
            muscle_meta = get_muscle_meta(num_channels)
            global_peaks = [0.0] * num_channels

        channels_envelope = [process_emg_signal(ch, fs) for ch in channels_raw]
        cur_peaks = calculate_mvc_peaks(channels_envelope)

        for i in range(min(len(global_peaks), len(cur_peaks))):
            if cur_peaks[i] > global_peaks[i]:
                global_peaks[i] = cur_peaks[i]
        sources.append(os.path.basename(fname))

    if not global_peaks:
        print("Error: No valid MVC files processed.")
        return

    mvc_data = {
        "profile_name": profile_name,
        "source_files": sources,
        "num_channels": num_channels,
        "peaks": global_peaks,
        "muscles": [m['abbr'] for m in muscle_meta]
    }
    save_mvc_calibration(mvc_data)
    print("\n" + "=" * 60)
    print("  COMBINED MULTI-TRIAL MVC CALIBRATION RESULTS")
    print("=" * 60)
    for i, m in enumerate(muscle_meta):
        print(f"  [{m['abbr']:4s}] {m['name_zh']:6s} ({m['name_en']:24s}): Global MVC Peak = {global_peaks[i]:.2f}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Wang (2025) Forearm 5-Muscle EMG Visualization & %MVC Analysis Tool")
    parser.add_argument("filename", nargs="*", help="CSV file(s) containing EMG data or MVC trials")
    parser.add_argument("--mvc", nargs="+", help="Path to one or more MVC reference CSV files for %MVC normalization")
    parser.add_argument("--trigger", help="Index of trigger channel (0-indexed, default: auto-detect)", type=int, default=None)
    parser.add_argument("--calibrate-mvc", help="Calculate and save global MVC calibration from specified file(s)", action="store_true")
    parser.add_argument("--save", help="Save the visualization plot as a high-res PNG", action="store_true")
    parser.add_argument("--no-show", help="Do not open GUI window (headless mode)", action="store_true")
    args = parser.parse_args()

    files = args.filename

    if args.calibrate_mvc:
        if not files:
            csv_files = [f for f in os.listdir('.') if f.endswith('.csv') and ('mvc' in f.lower() or 'isometric' in f.lower())]
            if not csv_files:
                csv_files = [f for f in os.listdir('.') if f.endswith('.csv')]
            print("Select MVC files to combine (separate numbers by commas, e.g. 0,1):")
            for idx, fname in enumerate(csv_files):
                print(f"  [{idx:2d}] {fname}")
            choice = input("Enter file numbers: ").strip()
            indices = [int(i.strip()) for i in choice.split(',') if i.strip().isdigit()]
            files = [csv_files[i] for i in indices] if indices else [csv_files[0]]
        calibrate_mvc_cli(files)
    else:
        target_file = files[0] if files else None
        if not target_file:
            print("=" * 60)
            print("  Wang (2025) EMG Visualization & Analysis Tool (v2)")
            print("=" * 60)
            csv_files = [f for f in os.listdir('.') if f.endswith('.csv')]
            if not csv_files:
                print("No CSV files found in the current directory.")
                sys.exit(1)

            print("\nAvailable CSV files:")
            for idx, fname in enumerate(csv_files):
                print(f"  [{idx:2d}] {fname}")

            choice = input("\nEnter file number or filename (default: 0): ").strip()
            if choice == "":
                target_file = csv_files[0]
            else:
                try:
                    target_file = csv_files[int(choice)]
                except (ValueError, IndexError):
                    target_file = choice

        # If multiple MVC files were passed via --mvc, combine them first
        mvc_ref = None
        if args.mvc:
            if len(args.mvc) == 1:
                mvc_ref = args.mvc[0]
            else:
                calibrate_mvc_cli(args.mvc, profile_name="cli_combined")
                mvc_ref = None  # plot_emg_v2 will automatically read saved profile

        plot_emg_v2(target_file, mvc_file=mvc_ref, save_fig=args.save, trigger_col=args.trigger, no_show=args.no_show)




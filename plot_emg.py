import matplotlib.pyplot as plt
import csv
import sys
import os
import numpy as np

# Ensure UTF-8 output on Windows command prompt / PowerShell
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# Configure fonts for Chinese and English bilingual display
plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'PingFang TC', 'SimHei', 'DejaVu Sans', 'Arial', 'sans-serif']
plt.rcParams['axes.unicode_minus'] = False


def generate_normalized_overlay(filename, time_data, emg_envelopes, swing_segments, channel_labels, colors):
    """
    Generates a 0%-100% time-normalized ensemble overlay plot across all recorded swings.
    Plots individual swing trajectories, ensemble mean curve, and ±1 SD variability band.
    """
    n_swings = len(swing_segments)
    if n_swings < 2:
        return None

    norm_grid = np.linspace(0, 100, 101)  # 0% to 100% swing cycle
    n_channels = len(emg_envelopes)

    fig_overlay, axes = plt.subplots(n_channels, 1, figsize=(12, 3.2 * n_channels), sharex=True)
    if n_channels == 1:
        axes = [axes]

    fig_overlay.suptitle(f"各次揮拍時間正規化疊合圖 (Normalized Swing Overlay - N = {n_swings} 次)\n{os.path.basename(filename)}",
                         fontsize=12, fontweight='bold', y=0.98)

    print("\n" + "=" * 62)
    print(f"      揮拍時間正規化分析 (0% - 100% Swing Cycle Ensemble, N={n_swings})")
    print("=" * 62)

    for ch_idx in range(n_channels):
        ax = axes[ch_idx]
        env_data = emg_envelopes[ch_idx]
        ch_name = channel_labels[ch_idx]
        ch_color = colors[ch_idx]

        swings_resampled = []
        for s, e, t_s, t_e in swing_segments:
            seg_t = time_data[s:e]
            seg_val = env_data[s:e]
            if len(seg_t) < 2:
                continue
            # Normalize time to 0% - 100%
            t_pct = (seg_t - seg_t[0]) / (seg_t[-1] - seg_t[0] + 1e-9) * 100.0
            interp_curve = np.interp(norm_grid, t_pct, seg_val)
            swings_resampled.append(interp_curve)

        swings_matrix = np.array(swings_resampled)  # Shape: (N, 101)
        mean_curve = np.mean(swings_matrix, axis=0)
        std_curve = np.std(swings_matrix, axis=0)

        # 1. Plot individual swing traces
        for i in range(len(swings_matrix)):
            ax.plot(norm_grid, swings_matrix[i], color=ch_color, alpha=0.22, linewidth=1.1,
                    label='單次揮拍軌跡 (Individual Swing)' if i == 0 else None)

        # 2. Plot ±1 Standard Deviation band
        lower_bound = np.maximum(0, mean_curve - std_curve)
        upper_bound = mean_curve + std_curve
        ax.fill_between(norm_grid, lower_bound, upper_bound, color=ch_color, alpha=0.20,
                        label='±1 SD 變異區間 (Variability Band)')

        # 3. Plot Ensemble Mean Curve
        ax.plot(norm_grid, mean_curve, color=ch_color, linewidth=2.8,
                label='平均趨勢 (Ensemble Mean Curve)')

        # 4. Mark peak activation timing
        peak_idx = int(np.argmax(mean_curve))
        peak_pct = norm_grid[peak_idx]
        peak_val = mean_curve[peak_idx]
        ax.axvline(peak_pct, color='#444444', linestyle=':', linewidth=1.5, alpha=0.8)
        ax.plot(peak_pct, peak_val, 'o', color=ch_color, markersize=7, markeredgecolor='black', markeredgewidth=1.2)

        # Calculate Coefficient of Variation (CV%)
        cv_pct = (np.mean(std_curve) / (np.mean(mean_curve) + 1e-6)) * 100.0

        print(f"  {ch_name:<16} | 平均峰值: {peak_val:<6.2f} ADC @ {peak_pct:<4.1f}% 週期 | 變異係數 (CV): {cv_pct:.1f}%")

        ax.set_title(f"{ch_name} (平均峰值 @ {peak_pct:.0f}% 揮拍週期)", fontsize=11, fontweight='bold')
        ax.set_ylabel("活化程度 (Activation)", fontsize=9.5)
        ax.grid(True, linestyle='--', alpha=0.55)
        ax.legend(loc='upper right', fontsize=8.5, framealpha=0.9)

        # Info Box on each subplot
        stat_box = (
            f"峰值 (Peak)  : {peak_val:.1f} ADC\n"
            f"峰值時機點    : {peak_pct:.0f}% 週期\n"
            f"穩定度 (CV%)  : {cv_pct:.1f}%"
        )
        ax.text(0.02, 0.93, stat_box, transform=ax.transAxes, fontsize=8.5,
                verticalalignment='top',
                bbox=dict(boxstyle='round,pad=0.35', facecolor='#f8f9fa', edgecolor='#ced4da', alpha=0.9))

    axes[-1].set_xlabel("揮拍動作百分比 (% Swing Cycle: 0% = 揮拍起點, 100% = 揮拍結束)", fontsize=10.5, fontweight='bold')
    plt.tight_layout(rect=[0, 0, 1, 0.96])

    overlay_png = os.path.splitext(filename)[0] + '_overlay.png'
    try:
        fig_overlay.savefig(overlay_png, dpi=300)
        print(f"\n[成功] 已匯出高解析度揮拍疊合圖 (300 DPI): {overlay_png}")
    except Exception as e:
        print(f"Could not save overlay image: {e}")

    print("=" * 62 + "\n")
    return fig_overlay


def plot_emg(filename):
    if not os.path.exists(filename):
        print(f"Error: File '{filename}' not found.")
        return

    time1_data = []
    emg1_data = []
    time2_data = []
    emg2_data = []
    time3_data = []
    emg3_data = []
    marker_data = []
    has_two_channels = False
    has_three_channels = False
    has_markers = False

    print(f"Reading {filename}...")
    with open(filename, 'r', encoding='utf-8', errors='ignore') as file:
        reader = csv.reader(file)
        for row in reader:
            if not row or row[0].startswith('#'):
                continue
            try:
                if len(row) >= 2:
                    time1_data.append(float(row[0]))
                    emg1_data.append(float(row[1]))
                if len(row) >= 3:
                    time2_data.append(float(row[0]))
                    emg2_data.append(float(row[2]))
                    has_two_channels = True
                if len(row) >= 4:
                    time3_data.append(float(row[0]))
                    emg3_data.append(float(row[3]))
                    has_three_channels = True
                if len(row) >= 5:
                    marker_data.append(float(row[4]))
                    has_markers = True
            except ValueError:
                pass  # Skip non-numeric header rows

    if not time1_data:
        print("No valid data found to plot.")
        return

    time_arr = np.array(time1_data)
    raw1_arr = np.array(emg1_data)
    raw2_arr = np.array(emg2_data) if has_two_channels else None
    raw3_arr = np.array(emg3_data) if has_three_channels else None

    print("Plotting data...")
    
    # Data Processing Function
    def process_emg(data):
        data = np.array(data)
        if len(data) == 0: return data
        
        # 1. Remove DC Offset (Center to 0 using the first 200 samples as resting baseline)
        baseline = np.mean(data[:200]) if len(data) > 200 else np.mean(data)
        centered = data - baseline
        
        # 2. Rectification (Absolute value)
        rectified = np.abs(centered)
        
        # 3. Smoothing (Moving Average with window size 50)
        window_size = 50
        weights = np.ones(window_size) / window_size
        smoothed = np.convolve(rectified, weights, mode='same')
        return smoothed

    emg1_processed = process_emg(raw1_arr)
    emg2_processed = process_emg(raw2_arr) if has_two_channels else None
    emg3_processed = process_emg(raw3_arr) if has_three_channels else None

    # Detect Swing vs Noise regions using markers (if present)
    swing_segments = []
    marker_arr = None
    if has_markers and len(marker_data) == len(time1_data):
        marker_arr = np.array(marker_data) > 0.5
        if np.any(marker_arr):
            # Detect start and stop transitions (0 -> 1 and 1 -> 0)
            padded = np.pad(marker_arr.astype(int), (1, 1), mode='constant')
            diff = np.diff(padded)
            starts = np.where(diff == 1)[0]
            ends = np.where(diff == -1)[0]

            for s, e in zip(starts, ends):
                t_start = time_arr[s]
                t_end = time_arr[min(e - 1, len(time_arr) - 1)]
                swing_segments.append((s, e, t_start, t_end))

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(13, 8), sharex=True)
    
    # --- Top Subplot: Raw Data ---
    ax1.plot(time_arr, raw1_arr, color='#1f77b4', linewidth=1, alpha=0.75, label='A0: FCR (Raw)')
    if has_two_channels:
        ax1.plot(time_arr, raw2_arr, color='#d62728', linewidth=1, alpha=0.75, label='A2: FCU (Raw)')
    if has_three_channels:
        ax1.plot(time_arr, raw3_arr, color='#2ca02c', linewidth=1, alpha=0.75, label='A4: ECRB (Raw)')
    
    title_suffix = f" [共 {len(swing_segments)} 次揮拍標記 - 綠色陰影]" if swing_segments else ""
    ax1.set_title(f'Raw EMG Data: {os.path.basename(filename)}{title_suffix}', fontsize=11, fontweight='bold')
    ax1.set_ylabel('Raw Value (0-1023)')
    ax1.grid(True, linestyle='--', alpha=0.6)

    # --- Bottom Subplot: Processed Data (Envelope) ---
    ax2.plot(time_arr, emg1_processed, color='#1f77b4', linewidth=2, label='A0: FCR (Envelope)')
    if has_two_channels:
        ax2.plot(time_arr, emg2_processed, color='#d62728', linewidth=2, label='A2: FCU (Envelope)')
    if has_three_channels:
        ax2.plot(time_arr, emg3_processed, color='#2ca02c', linewidth=2, label='A4: ECRB (Envelope)')
    ax2.set_title('Processed EMG Envelope (Rectified + Smoothed)', fontsize=11, fontweight='bold')
    ax2.set_xlabel('Time (ms)')
    ax2.set_ylabel('Activation Level')
    ax2.grid(True, linestyle='--', alpha=0.6)

    # Calculate full overview bounds
    full_xlim = (time_arr[0], time_arr[-1])
    full_ylim_raw = (0, 1024)
    all_envs = [emg1_processed] + ([emg2_processed] if has_two_channels else []) + ([emg3_processed] if has_three_channels else [])
    full_env_max = max(np.max(env) for env in all_envs)
    full_ylim_env = (0, full_env_max * 1.25 + 5)

    # --- Highlight Swing vs Noise if markers exist ---
    if swing_segments and marker_arr is not None:
        noise_mask = ~marker_arr
        has_noise = np.any(noise_mask)

        # Print detailed CLI breakdown
        print("\n" + "=" * 62)
        print("         EMG SWING vs NOISE SEGMENTATION ANALYSIS        ")
        print("=" * 62)
        for idx, (s, e, t_s, t_e) in enumerate(swing_segments):
            dur = (t_e - t_s) / 1000.0 if t_e >= t_s else (e - s) * 0.01
            print(f"  Swing #{idx+1}: {t_s:.0f} ms -> {t_e:.0f} ms (Duration: {dur:.2f}s, Samples {s}-{e-1})")

        print("-" * 62)
        print(f"  {'Channel':<10} | {'Noise Baseline':<16} | {'Swing Peak':<12} | {'Ratio'}")
        print("-" * 62)

        def print_stats(ch_name, processed):
            noise_val = np.mean(processed[noise_mask]) if has_noise else 1.0
            swing_val = np.max(processed[marker_arr])
            ratio = swing_val / (noise_val + 1e-6)
            print(f"  {ch_name:<10} | {noise_val:<16.2f} | {swing_val:<12.2f} | {ratio:.1f}x")
            return noise_val, swing_val, ratio

        n1, p1, r1 = print_stats("A0 (FCR)", emg1_processed)
        r_str = f"Swing Peak vs Noise:\n• A0 (FCR) : {r1:.1f}x"

        if has_two_channels:
            _, _, r2 = print_stats("A2 (FCU)", emg2_processed)
            r_str += f"\n• A2 (FCU) : {r2:.1f}x"
        if has_three_channels:
            _, _, r3 = print_stats("A4 (ECRB)", emg3_processed)
            r_str += f"\n• A4 (ECRB): {r3:.1f}x"

        print("=" * 62 + "\n")

        # Shade regions and draw marker lines on both subplots
        for idx, (s, e, t_s, t_e) in enumerate(swing_segments):
            for ax in (ax1, ax2):
                ax.axvspan(t_s, t_e, color='#2ecc71', alpha=0.18,
                           label='Swing Window (Active)' if idx == 0 else None)
                ax.axvline(t_s, color='#27ae60', linestyle='--', linewidth=1.8,
                           label='Start Marker [Space]' if idx == 0 else None)
                ax.axvline(t_e, color='#e74c3c', linestyle='--', linewidth=1.8,
                           label='Stop Marker [Space]' if idx == 0 else None)

            # Label on top plot
            mid_t = (t_s + t_e) / 2
            y_max1 = ax1.get_ylim()[1]
            ax1.text(mid_t, y_max1 * 0.92, f'#{idx+1}', color='#196f3d',
                     ha='center', va='top', fontsize=9.0, fontweight='bold',
                     bbox=dict(boxstyle='round,pad=0.2', facecolor='#ffffff', edgecolor='#27ae60', alpha=0.85))

        # Add Noise / Baseline tags to left and right outside swing
        first_start = swing_segments[0][2]
        if first_start > time_arr[0] + 50:
            mid_noise = (time_arr[0] + first_start) / 2
            ax1.text(mid_noise, ax1.get_ylim()[1] * 0.92, 'NOISE / REST', color='#7f8c8d',
                     ha='center', va='top', fontsize=8.5, style='italic',
                     bbox=dict(boxstyle='round,pad=0.2', facecolor='#f8f9fa', edgecolor='#bdc3c7', alpha=0.8))

        # Stats info box on processed envelope plot
        ax2.text(0.02, 0.95, r_str, transform=ax2.transAxes, fontsize=8.5,
                 verticalalignment='top',
                 bbox=dict(boxstyle='round,pad=0.4', facecolor='#f8f9fa', edgecolor='#adb5bd', alpha=0.9))

        # --- Interactive Arrow Key Zoom Navigation ---
        current_swing = [-1]  # -1 = full overview, 0..N-1 = zoomed on specific swing

        hud_text = fig.text(
            0.5, 0.985,
            f"[全景模式] 共 {len(swing_segments)} 次揮拍 | 按 [→] 進入第 1 次特寫 | [←/→] 切換揮拍 | [ESC] 全景",
            ha='center', va='top', fontsize=10, fontweight='bold',
            bbox=dict(boxstyle='round,pad=0.4', facecolor='#eef6fc', edgecolor='#2980b9', lw=1.2)
        )

        def update_zoom():
            idx = current_swing[0]
            if idx == -1:
                # Reset to full overview
                ax1.set_xlim(full_xlim)
                ax2.set_xlim(full_xlim)
                ax1.set_ylim(full_ylim_raw)
                ax2.set_ylim(full_ylim_env)
                hud_text.set_text(f"[全景模式] 共 {len(swing_segments)} 次揮拍 | 按 [→] 進入第 1 次特寫 | [←/→] 切換揮拍 | [ESC] 全景")
                hud_text.set_bbox(dict(boxstyle='round,pad=0.4', facecolor='#eef6fc', edgecolor='#2980b9', lw=1.2))
            else:
                s, e, t_s, t_e = swing_segments[idx]
                dur_ms = t_e - t_s
                pad_ms = max(250.0, dur_ms * 0.20)
                z_min = max(time_arr[0], t_s - pad_ms)
                z_max = min(time_arr[-1], t_e + pad_ms)

                ax1.set_xlim(z_min, z_max)
                ax2.set_xlim(z_min, z_max)

                # Local adaptive Y scaling for clear waveform inspection
                loc_raws = [raw1_arr[s:e]] + ([raw2_arr[s:e]] if has_two_channels else []) + ([raw3_arr[s:e]] if has_three_channels else [])
                raw_max = max(np.max(r) for r in loc_raws)
                raw_min = min(np.min(r) for r in loc_raws)
                ax1.set_ylim(max(0, raw_min - 25), min(1024, raw_max + 35))

                loc_envs = [emg1_processed[s:e]] + ([emg2_processed[s:e]] if has_two_channels else []) + ([emg3_processed[s:e]] if has_three_channels else [])
                env_max = max(np.max(ev) for ev in loc_envs)
                ax2.set_ylim(0, env_max * 1.30 + 3)

                dur_s = (t_e - t_s) / 1000.0 if t_e >= t_s else (e - s) * 0.01
                hud_text.set_text(f"[單次揮拍特寫] #{idx+1} / {len(swing_segments)} ({t_s:.0f} - {t_e:.0f} ms, 持續 {dur_s:.2f}s) | [→] 下一次 | [←] 上一次 | [ESC] 全景")
                hud_text.set_bbox(dict(boxstyle='round,pad=0.4', facecolor='#d4edda', edgecolor='#28a745', lw=1.5))

            fig.canvas.draw_idle()

        def on_key(event):
            if not swing_segments:
                return
            if event.key in ('right', 'd', 'down'):
                if current_swing[0] == -1:
                    current_swing[0] = 0
                else:
                    current_swing[0] = (current_swing[0] + 1) % len(swing_segments)
                update_zoom()
            elif event.key in ('left', 'a', 'up'):
                if current_swing[0] == -1:
                    current_swing[0] = len(swing_segments) - 1
                else:
                    current_swing[0] = (current_swing[0] - 1) % len(swing_segments)
                update_zoom()
            elif event.key in ('escape', 'h', 'home', '0', 'backspace'):
                current_swing[0] = -1
                update_zoom()

        fig.canvas.mpl_connect('key_press_event', on_key)

    ax1.legend(loc='upper right', fontsize=8.5)
    ax2.legend(loc='upper right', fontsize=8.5)

    plt.tight_layout(rect=[0, 0, 1, 0.96])

    # Automatically save high-resolution visualization image (300 DPI)
    output_png = os.path.splitext(filename)[0] + '_plot.png'
    try:
        fig.savefig(output_png, dpi=300)
        print(f"[成功] 已匯出高解析度全景圖 (300 DPI): {output_png}")
    except Exception as e:
        print(f"Could not save figure image: {e}")

    # --- Generate Normalized Swing Ensemble Overlay Figure (Figure 2) ---
    fig_overlay = None
    if len(swing_segments) >= 2:
        channel_labels = ['A0: FCR (撓側屈腕肌)']
        colors = ['#1f77b4']
        emg_envs = [emg1_processed]

        if has_two_channels:
            channel_labels.append('A2: FCU (尺側屈腕肌)')
            colors.append('#d62728')
            emg_envs.append(emg2_processed)
        if has_three_channels:
            channel_labels.append('A4: ECRB (短橈側伸腕肌)')
            colors.append('#2ca02c')
            emg_envs.append(emg3_processed)

        fig_overlay = generate_normalized_overlay(
            filename=filename,
            time_data=time_arr,
            emg_envelopes=emg_envs,
            swing_segments=swing_segments,
            channel_labels=channel_labels,
            colors=colors
        )

    plt.show()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # If user passes a filename as an argument
        target_file = sys.argv[1]
    else:
        # Ask user for filename if none provided
        print("Available CSV files:")
        csv_files = [f for f in os.listdir('.') if f.endswith('.csv')]
        for i, f in enumerate(csv_files):
            print(f"[{i}] {f}")
        
        if not csv_files:
            print("No CSV files found in the current directory.")
            sys.exit()
            
        choice = input("Enter the number of the file to plot (or type filename): ")
        
        try:
            target_file = csv_files[int(choice)]
        except (ValueError, IndexError):
            target_file = choice

    plot_emg(target_file)

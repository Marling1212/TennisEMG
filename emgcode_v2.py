"""
emgcode_v2.py
Real-time EMG Data Acquisition Tool based on Wang (2025) & SENIAM Protocol.

Target Forearm Muscles (up to 5 channels):
  CH1: PT   (Pronator Teres, 旋前圓肌)
  CH2: FCU  (Flexor Carpi Ulnaris, 尺側屈腕肌)
  CH3: FCR  (Flexor Carpi Radialis, 撓側屈腕肌)
  CH4: ECRB (Extensor Carpi Radialis Brevis, 短撓側伸腕肌)
  CH5: SP   (Supinator, 旋後肌)
  (Automatically adapts if your hardware currently streams 1, 2, 3, 4, or 5 channels)

Supported Protocols:
  1. Dynamic Swing - Racket (Forehand with Tennis Racket)
  2. Dynamic Swing - Shadow (Empty Hand / Shadow Swing)
  3. Isometric Squeeze (Forearm Grip / Isometric Contraction)
  4. MVC Calibration (Maximum Voluntary Contraction - 3-5 sec max effort)
"""

import sys
import os
import csv
import time
from datetime import datetime
import collections
import serial
import serial.tools.list_ports
import matplotlib.pyplot as plt
from plot_emg_v2 import plot_emg_v2, calibrate_mvc_cli, FIVE_MUSCLE_LABELS, LEGACY_THREE_CHANNELS

# Ensure UTF-8 output on Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# Configure fonts for Chinese and English bilingual display
plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'PingFang TC', 'SimHei', 'DejaVu Sans', 'Arial', 'sans-serif']
plt.rcParams['axes.unicode_minus'] = False

# --- DEFAULT HARDWARE CONFIGURATION ---
DEFAULT_SERIAL_PORT = 'COM18'
DEFAULT_BAUD_RATE = 9600
DEFAULT_SAMPLES = 1000


def select_serial_port():
    """Detects available serial ports and automatically prioritizes USB-SERIAL/Arduino."""
    ports = list(serial.tools.list_ports.comports())
    port_names = [p.device for p in ports]

    print("=" * 60)
    print("      Wang (2025) Forearm EMG Data Acquisition (v2)      ")
    print("=" * 60)

    # Auto-detect USB serial adapter (e.g. CH340 / FTDI / Arduino)
    usb_ports = [p for p in ports if any(k in p.description.upper() for k in ('CH340', 'USB-SERIAL', 'ARDUINO', 'CP210', 'FTDI'))]
    best_port = usb_ports[0].device if usb_ports else ('COM18' if 'COM18' in port_names else (DEFAULT_SERIAL_PORT if DEFAULT_SERIAL_PORT in port_names else None))

    if best_port and best_port in port_names:
        desc = next((p.description for p in ports if p.device == best_port), "")
        print(f"Detected USB Sensor Device: {best_port} ({desc})")
        choice = input(f"Use {best_port}? ([y]/n or enter port name): ").strip().lower()
        if choice in ('', 'y', 'yes'):
            return best_port
        elif choice not in ('n', 'no'):
            return choice.upper()

    if ports:
        print("\nAvailable COM Ports:")
        for idx, p in enumerate(ports):
            print(f"  [{idx}] {p.device}: {p.description}")
        sel = input("Select port number or type port name (e.g. COM18): ").strip()
        try:
            return ports[int(sel)].device
        except (ValueError, IndexError):
            return sel.upper() if sel else DEFAULT_SERIAL_PORT
    else:
        print(f"No active COM ports detected. Defaulting to '{DEFAULT_SERIAL_PORT}'.")
        return DEFAULT_SERIAL_PORT



def configure_test_metadata():
    """Configures test type, condition, and samples."""
    print("\n--- Test Protocol Selection ---")
    print("  [1] Dynamic Swing (Racket Forehand)  - 網球正拍持拍擊球")
    print("  [2] Dynamic Swing (Shadow Forehand)  - 網球空手揮拍對照")
    print("  [3] Isometric Squeeze                - 等長收縮握力測試")
    print("  [4] MVC Standardization Calibration  - 最大自發性收縮校正 (3-5秒全力抗阻)")

    choice = input("\nSelect test protocol [1-4] (default: 1): ").strip()

    if choice == '2':
        action = "swing"
        condition = "shadow"
        is_mvc = False
    elif choice == '3':
        action = "squeeze"
        condition = "isometric"
        is_mvc = False
    elif choice == '4':
        action = "mvc"
        is_mvc = True
        print("\n  Which isolated MVC contraction are you performing?")
        print("    [a] Wrist Flexion      (屈腕最大抗阻 -> 活化 FCR, FCU)")
        print("    [b] Wrist Extension    (伸腕最大抗阻 -> 活化 ECRB)")
        print("    [c] Hand Grip / Squeeze (全力握拳等長收縮 -> 握力基線)")
        print("    [d] Forearm Pronation  (前臂內旋最大抗阻 -> 活化 PT)")
        print("    [e] Forearm Supination (前臂外旋最大抗阻 -> 活化 SP)")
        sub_c = input("  Select contraction [a-e] (default: a): ").strip().lower()
        sub_map = {
            'a': "wrist_flexion",
            'b': "wrist_extension",
            'c': "hand_grip",
            'd': "forearm_pronation",
            'e': "forearm_supination"
        }
        condition = sub_map.get(sub_c, "wrist_flexion")
    else:
        action = "swing"
        condition = "racket"
        is_mvc = False

    samples_in = input(f"Number of samples to collect (default: {DEFAULT_SAMPLES}): ").strip()
    try:
        samples_to_collect = int(samples_in) if samples_in else DEFAULT_SAMPLES
    except ValueError:
        samples_to_collect = DEFAULT_SAMPLES

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"emg_{timestamp}_{action}_{condition}.csv"

    print(f"\nConfiguration confirmed:")
    print(f"  • Action/Condition: {action}_{condition}")
    print(f"  • Total Samples   : {samples_to_collect}")
    print(f"  • Output CSV File : {output_file}")
    if is_mvc:
        print("  • NOTE: This file will be tagged as an MVC reference standard.")

    return output_file, samples_to_collect, is_mvc


def main():
    port = select_serial_port()
    output_file, samples_to_collect, is_mvc = configure_test_metadata()

    baud_rate = DEFAULT_BAUD_RATE
    baud_in = input(f"\nBaud rate (default: {DEFAULT_BAUD_RATE}): ").strip()
    if baud_in.isdigit():
        baud_rate = int(baud_in)

    print("-" * 60)
    ser = None

    try:
        ser = serial.Serial(port, baud_rate, timeout=2.0)
        print(f"Successfully connected to {port} at {baud_rate} baud.")

        print("\nGet ready! Starting sampling countdown:")
        for i in range(3, 0, -1):
            print(f"  {i}...")
            time.sleep(1)

        ser.reset_input_buffer()
        print("\n>>> SAMPLING NOW! <<<")

        # Setup Interactive Real-time Plot
        plt.ion()
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.set_title("Live EMG Data Acquisition (Wang 2025 Forearm Setup)", fontsize=11, fontweight='bold')
        ax.set_xlabel("Sample Count", fontsize=10)
        ax.set_ylabel("Raw ADC Value (0 - 1023)", fontsize=10)
        ax.set_ylim(0, 1024)
        ax.set_xlim(0, samples_to_collect)
        ax.grid(True, linestyle='--', alpha=0.5)

        # Candidate lines for up to 5 channels
        colors = ["#1f77b4", "#d62728", "#ff7f0e", "#2ca02c", "#9467bd"]
        labels_5 = [
            "PT (旋前圓肌 - CH1)",
            "FCU (尺側屈腕肌 - CH2)",
            "FCR (撓側屈腕肌 - CH3)",
            "ECRB (短撓側伸腕肌 - CH4)",
            "SP (旋後肌 - CH5)"
        ]

        lines = [ax.plot([], [], color=colors[i], label=labels_5[i], linewidth=1.2)[0] for i in range(5)]
        ax.legend(loc='upper right', fontsize=8, framealpha=0.9)

        channel_buffers = [collections.deque(maxlen=samples_to_collect) for _ in range(5)]
        x_buffer = collections.deque(maxlen=samples_to_collect)

        num_channels_detected = 0

        with open(output_file, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)

            for i in range(samples_to_collect):
                raw_line = ser.readline().decode('utf-8', errors='ignore').strip()

                if ',' in raw_line:
                    tokens = [t.strip() for t in raw_line.split(',')]
                    writer.writerow(tokens)

                    # Extract channels (assuming tokens[0] is time/index, tokens[1..n] are EMG)
                    if len(tokens) >= 2:
                        emg_tokens = tokens[1:]
                        if num_channels_detected == 0:
                            num_channels_detected = len(emg_tokens)
                            # Adjust legend labels if only 3 channels (Legacy)
                            if num_channels_detected == 3:
                                lines[0].set_label("FCR (撓側屈腕肌)")
                                lines[1].set_label("FCU (尺側屈腕肌)")
                                lines[2].set_label("ECRB (短撓側伸腕肌)")
                                lines[3].set_visible(False)
                                lines[4].set_visible(False)
                                ax.legend(loc='upper right', fontsize=8, framealpha=0.9)

                        x_buffer.append(i)
                        for ch_idx in range(min(5, len(emg_tokens))):
                            try:
                                channel_buffers[ch_idx].append(float(emg_tokens[ch_idx]))
                            except ValueError:
                                pass

                    # Throttled draw: refresh if buffer is healthy
                    if i % 10 == 0 and ser.in_waiting < 100 and len(x_buffer) > 0:
                        x_list = list(x_buffer)
                        for ch_idx in range(min(5, num_channels_detected if num_channels_detected else 5)):
                            y_list = list(channel_buffers[ch_idx])
                            if len(y_list) > 0:
                                lines[ch_idx].set_data(x_list[-len(y_list):], y_list)

                        fig.canvas.draw()
                        fig.canvas.flush_events()

                if i > 0 and i % 100 == 0:
                    print(f"Collected {i}/{samples_to_collect} samples...")

        plt.ioff()
        plt.close(fig)

        print(f"\nDone! Data collection complete. Saved to '{output_file}'.")

        # If this was an MVC trial, offer to set as global calibration
        if is_mvc:
            save_as_calib = input("\nSave this trial as the default MVC calibration profile? ([y]/n): ").strip().lower()
            if save_as_calib in ('', 'y', 'yes'):
                calibrate_mvc_cli(output_file, profile_name=f"MVC_{output_file}")

        # Automatically open visualization
        print("\nLaunching analysis and visualization...")
        plot_emg_v2(output_file)

    except serial.SerialException as se:
        print(f"\nSerial Port Error: {se}")
        print("Please check that your device is plugged in, powered on, and not opened by another application.")
    except Exception as e:
        print(f"\nUnexpected Error: {e}")
    finally:
        if ser and ser.is_open:
            ser.close()
            print("Serial connection closed.")


if __name__ == "__main__":
    main()

import serial
import csv
import time
from datetime import datetime
from plot_emg import plot_emg
import matplotlib.pyplot as plt
import collections

# Optional dependencies for multi-modal spacebar detection & audio cues
try:
    import keyboard
except ImportError:
    keyboard = None

try:
    import msvcrt
except ImportError:
    msvcrt = None

try:
    import winsound
except ImportError:
    winsound = None


class SwingMarkerTracker:
    """Tracks swing start and stop markers via the Spacebar."""
    def __init__(self):
        self.is_swing_active = False
        self.marker_count = 0
        self.last_press_time = 0.0
        self.events = []
        self.new_events = []
        self._hook = None

        if keyboard:
            try:
                self._hook = keyboard.on_press_key('space', self._on_space_global)
            except Exception:
                self._hook = None

    def _on_space_global(self, event=None):
        self.trigger()

    def trigger(self, sample_idx=None):
        now = time.time()
        # 350ms debounce to prevent bouncing / double-clicks
        if now - self.last_press_time < 0.35:
            return False
        self.last_press_time = now
        self.is_swing_active = not self.is_swing_active
        self.marker_count += 1
        event_type = 'START' if self.is_swing_active else 'STOP'
        
        self.events.append((event_type, sample_idx))
        self.new_events.append((event_type, sample_idx))

        if self.is_swing_active:
            s_info = f"at sample #{sample_idx}" if sample_idx is not None else ""
            print(f"\n>>> [MARKER #{self.marker_count}: SWING START] {s_info} <<<")
            if winsound:
                try: winsound.Beep(1000, 100)
                except Exception: pass
        else:
            s_info = f"at sample #{sample_idx}" if sample_idx is not None else ""
            print(f"\n>>> [MARKER #{self.marker_count}: SWING STOP] {s_info} <<<")
            if winsound:
                try: winsound.Beep(600, 150)
                except Exception: pass
        return True

    def pop_new_events(self):
        evs = list(self.new_events)
        self.new_events.clear()
        return evs

    def cleanup(self):
        if self._hook is not None and keyboard:
            try:
                keyboard.unhook(self._hook)
            except Exception:
                pass


# --- HARDWARE CONFIGURATION ---
SERIAL_PORT = 'COM18'  # Your working port
BAUD_RATE = 9600
SAMPLES_TO_COLLECT = 3000  # Adjust for longer/shorter tests

# --- 1. INTERACTIVE FILE NAMING ---
print("--- EMG Test Setup ---")
is_swing = input("Is this a dynamic swing test? (y/n): ").strip().lower()

if is_swing == 'y':
    action = "swing"
    has_racket = input("Are you holding a racket? (y/n): ").strip().lower()
    if has_racket == 'y':
        condition = "racket"
    else:
        condition = "shadow"
else:
    action = "squeeze"
    condition = "isometric"

# Generate a unique filename using a timestamp with date and time
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
OUTPUT_FILE = f"emg_{timestamp}_{action}_{condition}.csv"

print(f"\nAwesome. Data will be saved to: {OUTPUT_FILE}")
print("-" * 55)
print("SWING MARKER INSTRUCTIONS:")
print("  • Press [SPACEBAR] right BEFORE your swing -> Marks SWING START")
print("  • Press [SPACEBAR] right AFTER your swing  -> Marks SWING STOP")
print("  • Everything inside markers = Swing | Outside = Noise/Baseline")
print("-" * 55)

# --- 2. DATA COLLECTION ---
marker_tracker = SwingMarkerTracker()

try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE)
    print(f"Connected to {SERIAL_PORT}.")

    # Countdown before sampling
    print("\nGet ready! Starting data collection in:")
    for i in range(3, 0, -1):
        print(f"{i}...")
        time.sleep(1)
        
    ser.reset_input_buffer()  # Clear old data from the buffer
    print("\n>>> SAMPLING NOW! (Press SPACEBAR for swing start/stop) <<<")

    # --- Live Plot Setup ---
    plt.ion()  # Turn on interactive mode
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.set_title("Live EMG Data (Raw) - Press [SPACE] to Mark Swing")
    ax.set_xlabel("Samples")
    ax.set_ylabel("Raw Value (0-1023)")
    ax.set_ylim(0, 1024)
    ax.set_xlim(0, SAMPLES_TO_COLLECT)
    
    line1, = ax.plot([], [], 'b-', label='FCR (A0)')
    line2, = ax.plot([], [], 'r-', label='FCU (A2)')
    line3, = ax.plot([], [], 'g-', label='ECRB (A4)')
    ax.legend(loc='upper right')

    # Visual status badge in the live plot
    status_text = ax.text(0.02, 0.94, "Status: WAITING (Press [SPACE] to Start Swing)",
                          transform=ax.transAxes, fontsize=9.5, fontweight='bold',
                          verticalalignment='top',
                          bbox=dict(boxstyle="round,pad=0.35", fc="#fff3cd", ec="#ffc107", lw=1.5))
    
    current_sample_idx = [0]
    last_start_idx = None

    # Connect matplotlib window keypress as well
    def on_matplotlib_key(event):
        if event.key in (' ', 'space'):
            marker_tracker.trigger(sample_idx=current_sample_idx[0])

    fig.canvas.mpl_connect('key_press_event', on_matplotlib_key)
    
    y1_data = collections.deque(maxlen=SAMPLES_TO_COLLECT)
    y2_data = collections.deque(maxlen=SAMPLES_TO_COLLECT)
    y3_data = collections.deque(maxlen=SAMPLES_TO_COLLECT)
    x_data = collections.deque(maxlen=SAMPLES_TO_COLLECT)

    with open(OUTPUT_FILE, mode='w', newline='') as file:
        writer = csv.writer(file)
        
        for i in range(SAMPLES_TO_COLLECT):
            current_sample_idx[0] = i

            # Check for console keyboard press (terminal window focus)
            if msvcrt and msvcrt.kbhit():
                try:
                    if msvcrt.getch() == b' ':
                        marker_tracker.trigger(sample_idx=i)
                except Exception:
                    pass

            line = ser.readline().decode('utf-8', errors='ignore').strip()
            
            # Split and save the data
            if ',' in line:
                data = line.split(',')
                # Append marker: 1 = swing active, 0 = baseline/noise
                marker_val = 1 if marker_tracker.is_swing_active else 0
                writer.writerow(data + [marker_val])

                # Live plot update
                if len(data) >= 2:
                    try: y1_data.append(float(data[1]))
                    except ValueError: pass
                if len(data) >= 3:
                    try: y2_data.append(float(data[2]))
                    except ValueError: pass
                if len(data) >= 4:
                    try: y3_data.append(float(data[3]))
                    except ValueError: pass
                
                x_data.append(i)

                # Process any newly registered swing events
                for ev_type, s_idx in marker_tracker.pop_new_events():
                    idx_to_use = i if s_idx is None else s_idx
                    if ev_type == 'START':
                        last_start_idx = idx_to_use
                        status_text.set_text(">>> SWING RECORDING <<< (Press [SPACE] to Stop)")
                        status_text.set_bbox(dict(boxstyle="round,pad=0.35", fc="#d4edda", ec="#28a745", lw=1.5))
                        ax.axvline(x=idx_to_use, color='#28a745', linestyle='--', linewidth=1.8)
                    elif ev_type == 'STOP':
                        status_text.set_text("SWING COMPLETE (Noise / Resting)")
                        status_text.set_bbox(dict(boxstyle="round,pad=0.35", fc="#d1ecf1", ec="#17a2b8", lw=1.5))
                        ax.axvline(x=idx_to_use, color='#dc3545', linestyle='--', linewidth=1.8)
                        if last_start_idx is not None and idx_to_use > last_start_idx:
                            ax.axvspan(last_start_idx, idx_to_use, color='#28a745', alpha=0.15)
                    fig.canvas.draw()
                    fig.canvas.flush_events()
                
                # Self-regulating draw: ONLY update if we aren't falling behind
                if i % 10 == 0 and ser.in_waiting < 100 and len(x_data) > 0:
                    if len(y1_data) > 0: line1.set_data(list(x_data)[-len(y1_data):], list(y1_data))
                    if len(y2_data) > 0: line2.set_data(list(x_data)[-len(y2_data):], list(y2_data))
                    if len(y3_data) > 0: line3.set_data(list(x_data)[-len(y3_data):], list(y3_data))
                    
                    fig.canvas.draw()
                    fig.canvas.flush_events()
            
            # Print progress every 100 samples
            if i > 0 and i % 100 == 0:
                state_str = " [SWING ACTIVE]" if marker_tracker.is_swing_active else " [NOISE/REST]"
                print(f"Collected {i}/{SAMPLES_TO_COLLECT} samples...{state_str}")

    plt.ioff()  # Turn off interactive mode
    plt.close(fig)  # Close the live plot figure

    print(f"\nDone! Data collection complete. Saved to {OUTPUT_FILE}")
    if marker_tracker.marker_count > 0:
        print(f"Successfully recorded {marker_tracker.marker_count} marker event(s).")
    else:
        print("Note: Spacebar was not pressed during collection. Full trial recorded as baseline.")

except Exception as e:
    print(f"\nError: {e}")
finally:
    marker_tracker.cleanup()
    if 'ser' in locals() and ser.is_open:
        ser.close()

    # Automatically plot the data after collection is complete
    if 'OUTPUT_FILE' in locals():
        print("\nOpening plot...")
        plot_emg(OUTPUT_FILE)
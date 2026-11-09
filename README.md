# TennisEMG: Forearm Muscle sEMG Acquisition & Biomechanical Analysis

A Python pipeline for real-time surface electromyography (sEMG) data acquisition and biomechanical analysis of forearm muscle activation patterns during tennis forehand strokes, following **Wang (2025)** and international **SENIAM** guidelines.

---

## 🎯 Target Forearm Muscles (5 Channels)

| Channel | Abbr | Muscle Name | Traditional Chinese | Primary Biomechanical Role |
| :---: | :---: | :--- | :--- | :--- |
| **CH1** | **PT** | Pronator Teres | 旋前圓肌 | Forearm pronation |
| **CH2** | **FCU** | Flexor Carpi Ulnaris | 尺側屈腕肌 | Wrist flexion & ulnar deviation |
| **CH3** | **FCR** | Flexor Carpi Radialis | 撓側屈腕肌 | Wrist flexion & radial deviation |
| **CH4** | **ECRB**| Extensor Carpi Radialis Brevis | 短撓側伸腕肌 | Wrist extension & dynamic stabilization |
| **CH5** | **SP** | Supinator | 旋後肌 | Forearm supination |

---

## 📁 Repository Structure

```text
├── emgcode_v2.py           # Real-time multi-channel sEMG data acquisition tool (Wang 2025)
├── plot_emg_v2.py          # Biomechanical signal processing, filtering & %MVC analysis tool
├── emgcode.py              # Legacy acquisition script (kept for backwards compatibility)
├── plot_emg.py             # Legacy 3-channel plotting script
├── WANG_2025_EMG_GUIDE.md  # Detailed electrode placement, MVC calibration & protocol guide
├── requirements.txt        # Python package dependencies
└── README.md               # Project overview and instructions
```

---

## ⚡ Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Marling1212/TennisEMG.git
   cd TennisEMG
   ```

2. **Install required dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

---

## 🚀 Usage

### 1. Real-time Data Acquisition (`emgcode_v2.py`)

Connect your EMG acquisition device (e.g., Arduino / USB-Serial) and run:

```bash
python emgcode_v2.py
```

The script will guide you to:
- Auto-detect or select the active COM serial port.
- Choose an experimental protocol:
  - `[1]` Dynamic Swing (Racket Forehand)
  - `[2]` Dynamic Swing (Shadow Forehand)
  - `[3]` Isometric Squeeze (Forearm Grip)
  - `[4]` MVC Calibration (Maximum Voluntary Contraction)
- Display real-time streaming waveforms.
- Automatically save raw data to a timestamped CSV file and launch analysis upon completion.

### 2. Signal Processing & %MVC Analysis (`plot_emg_v2.py`)

#### Interactive Mode
```bash
python plot_emg_v2.py
```

#### Analyze a Specific CSV File
```bash
python plot_emg_v2.py <data_file>.csv
```

#### Normalize with an MVC Reference Trial
```bash
python plot_emg_v2.py <data_file>.csv --mvc <mvc_calibration_file>.csv
```

#### Calibrate & Save MVC Baseline Profile
```bash
python plot_emg_v2.py --calibrate-mvc <mvc_trial>.csv
```

#### Export High-Resolution Plots (300 DPI)
```bash
python plot_emg_v2.py <data_file>.csv --save
```

---

## 🔬 Signal Processing Pipeline

1. **Baseline DC Offset Correction**: Zero-centering the raw voltage readings.
2. **Filtering**: Butterworth bandpass / lowpass filtering to eliminate motion artifacts and high-frequency noise.
3. **Full-Wave Rectification**: Absolute value transformation of the EMG signal.
4. **Linear Envelope Extraction**: Moving RMS or lowpass filtering (e.g., 6 Hz) for muscle activation curves.
5. **%MVC Normalization**: Normalizing dynamic amplitudes against Maximum Voluntary Contraction to eliminate inter-subject physiological variability.
6. **Co-activation Assessment**: Pronation/Supination and Flexion/Extension ratios to quantify joint stability.

---

## 📖 Reference & Protocol Standards

Detailed anatomical landmarks, electrode placement procedures, and experimental QA/QC procedures are documented in [`WANG_2025_EMG_GUIDE.md`](WANG_2025_EMG_GUIDE.md).

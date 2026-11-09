# Wang (2025) 網球正拍前臂 5 條目標肌肉 sEMG 實驗與分析指南

本指南整合 **Wang (2025)** 最新研究配置與國際 **SENIAM** 表面肌電標準，並對應全新升級的 Python 採集與分析程式（不改動舊版程式，獨立運行）。

---

## 一、 5 條前臂目標肌肉解剖定位與觸診規範 (SENIAM)

| 通道 | 肌肉名稱 | 英文全名 | 功能導向 | 觸診抗阻動作 | 貼片解剖位置 |
|:---:|:---|:---|:---|:---|:---|
| **CH1** | **PT** (旋前圓肌) | Pronator Teres | 前臂內旋 (Pronation) | 手肘微屈，掌心向內/下抗阻旋轉 | 肘內上髁（Medial Epicondyle）下方約 2–3 cm，斜向橈骨肌腹中央 |
| **CH2** | **FCU** (尺側屈腕肌) | Flexor Carpi Ulnaris | 手腕屈曲與尺側偏斜 | 握拳，手腕朝小指側用力屈曲 | 前臂小指側掌側近端 1/3 處，順著尺骨邊緣平行貼附 |
| **CH3** | **FCR** (撓側屈腕肌) | Flexor Carpi Radialis | 手腕屈曲與撓側偏斜 | 握拳，手腕朝大拇指側用力屈曲 | 前臂大拇指側掌側近端 1/3 處（手肘橫紋下方約兩指幅） |
| **CH4** | **ECRB** (短撓側伸腕肌) | Extensor Carpi Radialis Brevis | 手腕背屈與動態擊球穩定 | 掌心朝下，握拳做手腕強力背伸 | 手肘外上髁（Lateral Epicondyle）下方約 3–4 cm 伸肌隆起處 |
| **CH5** | **SP** (旋後肌) | Supinator | 前臂外旋 (Supination) | 手肘伸直，掌心向外/上抗阻旋轉 | 橈骨頭下方外側解剖露頭點，避開淺層指伸肌 |

> **參考電極 (REF)**：貼於手肘鷹嘴突（Olecranon）等無肌肉覆蓋骨凸處，以獲得乾淨基準地電位。

---

## 二、 品質控制與 MVC 校正標準 (QA / QC)

1. **皮膚預處理 (Skin Preparation)**：
   - 剃除毛髮，以 75% 酒精棉片擦拭清潔去角質與油脂，降低接觸阻抗（建議 $< 5\text{ k}\Omega$）。
2. **參考電極 (REF) 定位**：
   - 貼於手肘鷹嘴突（Olecranon）等骨凸區域，消除環境雜訊並提供乾淨基準地電位。
3. **最大自發性收縮 (MVC) 校正**：
   - 進行揮拍實驗前，先針對目標肌肉執行 3–5 秒全力抗阻收縮（Isometric MVC）。
   - 程式自動提取 MVC 峰值，將動態揮拍電壓轉化為 **%MVC**，消除個體皮下脂肪與肌肉量差異。
4. **多模態訊號同步 (Hardware Synchronization)**：
   - 參考 Wang (2025) 規範，sEMG（如 Delsys Trigno 2400 Hz）透過**同步觸發脈衝 (Synchronized Trigger Pulse)** 與 OptiTrack 動作捕捉系統（200 Hz）進行毫秒級時間軸對齊。
   - `plot_emg_v2.py` 自動偵測第 6 通道或數位觸發階躍訊號，並在圖表繪製垂直標記線。

---

## 💡 向教授彙報時的開場與重點整理

> **開場建議**：  
> 「教授，參考 **Wang (2025)** 最新論文與 **SENIAM** 國際標準，我們已經整理好針對**網球正拍前臂 5 條關鍵肌肉（PT、FCU、FCR、ECRB、SP）**的貼片定位與觸診標準。實驗中會加入酒精去油與 MVC 標準化校正，並透過硬體脈衝同步肌電與動捕訊號，確保數據具備發表的嚴謹度。」

---

## 三、 新版程式架構與使用方式

舊版檔案保持完全不變：
- `emgcode.py`（舊版採集程式，保留未改動）
- `plot_emg.py`（舊版 3 通道繪圖程式，保留未改動）

新版程式（Wang 2025 標準）：
- **`emgcode_v2.py`**：支援 1~5 通道動態識別、多模式選擇（持拍/空手/握力/MVC校正）、即時雙語曲線。
- **`plot_emg_v2.py`**：專業肌電訊號處理（DC消除 + 濾波 + 整流 + 6Hz包絡線 + %MVC標準化 + 前臂旋前/旋後、屈/伸生物力學平衡分析）。

---

### 1. 執行新版數據採集 (`emgcode_v2.py`)

```powershell
python emgcode_v2.py
```
- **步驟 1**：確認或選擇 COM 連接埠（預設 COM17）。
- **步驟 2**：選擇實驗協定：
  - `[1]` Dynamic Swing (Racket Forehand) - 網球正拍持拍擊球
  - `[2]` Dynamic Swing (Shadow Forehand) - 網球空手揮拍對照
  - `[3]` Isometric Squeeze - 等長收縮握力測試
  - `[4]` MVC Standardization Calibration - 最大自發性收縮校正（3–5 秒全力）
- **步驟 3**：即時視窗顯示即時肌電曲線，採集完畢後自動叫出分析視窗。

---

### 2. 執行新版分析與繪圖 (`plot_emg_v2.py`)

#### (A) 交互式選擇檔案
```powershell
python plot_emg_v2.py
```

#### (B) 直接分析特定 CSV 檔案（支援舊版 3 通道與新版 5 通道）
```powershell
python plot_emg_v2.py emg_20261007_151313_swing_racket.csv
```

#### (C) 引入 MVC 基準檔案進行 %MVC 標準化
```powershell
python plot_emg_v2.py emg_20261007_151313_swing_racket.csv --mvc emg_20260913_153014_squeeze_isometric.csv
```

#### (D) 將 MVC 試驗儲存為永久設定檔
```powershell
python plot_emg_v2.py --calibrate-mvc emg_20260913_153014_squeeze_isometric.csv
```

#### (E) 儲存高解析度圖表 (300 DPI PNG)
```powershell
python plot_emg_v2.py emg_20261007_151313_swing_racket.csv --save
```

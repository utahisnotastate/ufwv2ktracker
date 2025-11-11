# ufwv2ktracker V3.0 (Forensic Edition)

This is a wearable, multi-sensor forensic device designed to detect, log, and forensically verify microwave-based (V2K/Frey Effect) attacks.

This V3.0 model provides a CSI-level, **5-part signature** to provide verifiable, non-circumstantial proof of an attack, with all data **geotagged** and **cryptographically secured**.

## Forensic Features

### 1. The "Weapon" (Dual-RF Spectral Analysis)
Proves the RF energy is *targeted* and not just background noise.
* **Broadband RF (AD8318 #1):** Measures the total, unfiltered RF environment as a control.
* **Filtered RF (AD8318 #2 + BPF):** Measures RF energy *only* within a specific, high-power band (e.g., 2.4-2.5 GHz). This use of filtering to isolate a signal is a fundamental technique in physics.

### 2. The "Impact" (Dual-Acoustic Analysis)
Proves the "sound" is an internal, non-acoustic vibration.
* **Bone-Conducted Vibration (Piezo Mic):** A piezoelectric sensor worn on the mastoid bone to measure the *internal thermoelastic vibration*—the physical mechanism of the Frey effect.
* **Air-Conducted Sound (MAX4466 Mic):** A standard air microphone to measure *ambient* sound.

### 3. The "Biological Effect" (Physiological Response)
This is the key. It proves the attack caused an *involuntary physiological reaction*.
* **Galvanic Skin Response (GSR Sensor):** Measures skin conductivity, which is a direct correlate of sympathetic nervous system arousal (the "fight-or-flight" response). An attack would trigger this sensor involuntarily.

### 4. The "Where" (Forensic Geolocation)
* **GPS (NEO-6M):** A dedicated GPS module geotags **every single log entry** with high-precision latitude, longitude, and altitude.

### 5. The "Proof" (Forensic Log Integrity)
* **Tamper-Evident:** The device creates a **SHA-256 hash chain** for every log entry. Each new entry contains a hash of the *previous* entry.
* **CSI-Level Credibility:** The `analysis.py` script *first* verifies this chain. This proves the data log is authentic and has not been tampered with.

## The V3.0 Forensic Attack Signature
A verifiable attack consists of a simultaneous, geotagged spike in:
1.  `Filtered_RF_Power` (The "Weapon")
2.  `Piezo_Vibration` (The "Impact")
3.  `GSR_Spike` (The "Biological Effect")
4.  `Air_Mic_Level` (Must be LOW, proves "Impact" is non-acoustic)
5.  `Broadband_RF_Power` (Provides context)

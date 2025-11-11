# analysis.py
# ufwv2ktracker V3.0 - Forensic Analysis
# 1. Verifies log integrity via hash chain
# 2. Runs 5-part ML anomaly detection (RF, Piezo, GSR, Air)
# 3. Plots "Smoking Gun" evidence
# 4. Plots Geotagged Attack Map

import pandas as pd
import matplotlib.pyplot as plt
import os
import hashlib
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

LOG_FILE = 'forensic_log_v3.csv'
# Key features for the attack signature
FEATURES = ['rf_filter', 'mic_piezo', 'mic_air', 'gsr_raw', 'rf_broad']


def verify_hash_chain(df):
    """Verifies the SHA-256 hash chain. Returns True if valid."""
    print("\n--- FORENSIC VERIFICATION (V3.0) ---")
    is_valid = True

    if df.iloc[0]['prev_hash'] != "0" * 64:
        print("!! TAMPERING DETECTED: Genesis hash (line 1) is incorrect. !!")
        return False

    for i in range(1, len(df)):
        prev = df.iloc[i - 1]
        # Reconstruct the exact string from the previous line
        prev_line_string = (f"{prev['timestamp']},{prev['rf_broad']:.2f},{prev['rf_filter']:.2f},"
                            f"{prev['mic_air']},{prev['mic_piezo']},{prev['gsr_raw']},"
                            f"{prev['ax']},{prev['ay']},{prev['az']},{prev['gx']},{prev['gy']},{prev['gz']},"
                            f"{prev['mx']},{prev['my']},{prev['mz']},"
                            f"{prev['lat']:.6f},{prev['lon']:.6f},{prev['alt']:.1f},{prev['prev_hash']}")

        expected_hash = hashlib.sha256(prev_line_string.encode('utf-8')).hexdigest()
        stored_hash = df.iloc[i]['prev_hash']

        if expected_hash != stored_hash:
            print(f"!! TAMPERING DETECTED at line {i + 1} !!")
            is_valid = False
            break

    if is_valid:
        print("VERIFIED: Log file integrity is 100%.")
    else:
        print("CRITICAL: Log file has been tampered with.")
    return is_valid


def analyze_log(df):
    print("\n--- SENSOR LOG ANALYSIS (V3.0) ---")

    # Center the mic data to find amplitude (relative to its own noise)
    df['piezo_amp'] = (df['mic_piezo'] - df['mic_piezo'].rolling(100).mean()).abs()
    df['air_amp'] = (df['mic_air'] - df['mic_air'].rolling(100).mean()).abs()
    # GSR is a slow-moving signal. We care about the *change* (derivative)
    df['gsr_spike'] = df['gsr_raw'].diff().abs()

    # Features for the ML model - we use the new calculated features
    features_for_ml = ['rf_filter', 'piezo_amp', 'air_amp', 'gsr_spike', 'rf_broad']

    # ML model can't handle NaNs from rolling/diff, so fill them
    df_ml = df[features_for_ml].fillna(0)

    scaler = StandardScaler()
    df_scaled = scaler.fit_transform(df_ml)

    model = IsolationForest(contamination=0.001, random_state=42)
    print("Training ML model...")
    model.fit(df_scaled)

    print("Predicting anomalies...")
    df['is_anomaly'] = model.predict(df_scaled)  # -1 for anomaly

    # Filter for the specific V3.0 signature:
    piezo_threshold = df['piezo_amp'].mean() + 3 * df['piezo_amp'].std()
    air_threshold = df['air_amp'].mean() + 1 * df['air_amp'].std()  # Must be LOW
    rf_threshold = df['rf_filter'].mean() + 2 * df['rf_filter'].std()
    gsr_threshold = df['gsr_spike'].mean() + 3 * df['gsr_spike'].std()  # Must have a GSR spike

    attacks = df[
        (df['is_anomaly'] == -1) &
        (df['piezo_amp'] > piezo_threshold) &
        (df['air_amp'] < air_threshold) &
        (df['rf_filter'] > rf_threshold) &
        (df['gsr_spike'] > gsr_threshold)
        ]

    if attacks.empty:
        print("\n--- RESULT ---")
        print("No significant 5-part attack signatures detected in the log.")
    else:
        print(f"\n--- {len(attacks)} VERIFIED ATTACK EVENTS DETECTED ---")

        # 1. "Smoking Gun" Plot
        print("Generating forensic 'Smoking Gun' plot...")
        example_attack = attacks.nlargest(1, 'rf_filter')
        attack_index = example_attack.index[0]
        plot_data = df.loc[max(0, attack_index - 30): min(len(df), attack_index + 30)].copy()

        # Normalize for plotting
        plot_data['RF Filter (norm)'] = (plot_data['rf_filter'] - plot_data['rf_filter'].min()) / (
                    plot_data['rf_filter'].max() - plot_data['rf_filter'].min())
        plot_data['Piezo Amp (norm)'] = (plot_data['piezo_amp'] - plot_data['piezo_amp'].min()) / (
                    plot_data['piezo_amp'].max() - plot_data['piezo_amp'].min())
        plot_data['Air Amp (norm)'] = (plot_data['air_amp'] - plot_data['air_amp'].min()) / (
                    plot_data['air_amp'].max() - plot_data['air_amp'].min())
        plot_data['GSR Spike (norm)'] = (plot_data['gsr_spike'] - plot_data['gsr_spike'].min()) / (
                    plot_data['gsr_spike'].max() - plot_data['gsr_spike'].min())

        plt.figure(figsize=(15, 7))
        plt.plot(plot_data['timestamp'], plot_data['RF Filter (norm)'], label='Weapon: Targeted RF', color='red',
                 linewidth=2)
        plt.plot(plot_data['timestamp'], plot_data['Piezo Amp (norm)'], label='Impact: Internal Vibration',
                 color='blue', linewidth=2, linestyle='--')
        plt.plot(plot_data['timestamp'], plot_data['GSR Spike (norm)'], label='Effect: Involuntary GSR', color='purple',
                 linewidth=2, linestyle=':')
        plt.plot(plot_data['timestamp'], plot_data['Air Amp (norm)'], label='Control: Ambient Sound', color='green',
                 alpha=0.4)

        plt.title(f"FORENSIC PLOT: Attack Event at {example_attack['timestamp'].values[0]}ms")
        plt.ylabel("Normalized Sensor Amplitude")
        plt.xlabel("Timestamp (ms)")
        plt.legend();
        plt.grid(True)
        plt.axvline(x=example_attack['timestamp'].values[0], color='red', linestyle='--', label='Attack Peak')
        plt.savefig('forensic_attack_plot_V3.png')
        print("Saved 'forensic_attack_plot_V3.png'")
        print(
            "PLOT ANALYSIS: Note the simultaneous spike in RF, Piezo, and GSR, while Ambient Sound remains low. This is the V3.0 signature.")
        plt.clf()

        # 2. Geographic Attack Map
        attacks_with_gps = attacks[(attacks['lat'] != 0.0) & (attacks['lon'] != 0.0)]
        if not attacks_with_gps.empty:
            print("Generating geographic attack map...")
            df_gps_normal = df[(df['lat'] != 0.0) & (df['lon'] != 0.0) & (df['is_anomaly'] == 1)]

            plt.figure(figsize=(12, 8))
            plt.scatter(df_gps_normal['lon'], df_gps_normal['lat'], c='grey', alpha=0.1, s=1, label='Normal Path')
            plt.scatter(attacks_with_gps['lon'], attacks_with_gps['lat'], c=attacks_with_gps['rf_filter'],
                        cmap='Reds', s=50, label='Attack (Color=RF Power)', edgecolors='black')
            plt.xlabel('Longitude');
            plt.ylabel('Latitude')
            plt.title('V3.0 Forensic Map: Attack Location & Intensity')
            plt.colorbar(label='Targeted RF Power (dBm)')
            plt.legend();
            plt.grid(True);
            plt.axis('equal')
            plt.savefig('forensic_attack_map_V3.png')
            print("Saved 'forensic_attack_map_V3.png'")
            plt.clf()


if __name__ == "__main__":
    if not os.path.exists(LOG_FILE):
        print(f"Error: {LOG_FILE} not found. Copy it from the SD card.")
    else:
        print(f"Loading log file: {LOG_FILE}...")
        data = pd.read_csv(LOG_FILE, low_memory=False)

        if verify_hash_chain(data):
            analyze_log(data)
        else:
            print("Analysis aborted due to log integrity failure.")

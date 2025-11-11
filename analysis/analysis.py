# analysis.py
# Reads the rf_log.csv and finds power spikes.

import pandas as pd
import matplotlib.pyplot as plt
import os

LOG_FILE = 'rf_log.csv'
RF_POWER_COL = 'rf_power_dbm'


def analyze_rf_log(df):
    if df.empty:
        print("Log is empty.")
        return

    print("--- RF 'Watchdog' Log Analysis ---")

    # Basic stats
    avg_power = df[RF_POWER_COL].mean()
    max_power = df[RF_POWER_COL].max()
    min_power = df[RF_POWER_COL].min()

    print(f"Average RF Power: {avg_power:.2f} dBm")
    print(f"Peak RF Power:    {max_power:.2f} dBm")
    print(f"Noise Floor (Min):{min_power:.2f} dBm")

    # Find "attacks" - we'll define this as any reading
    # 3 standard deviations above the mean. This is a standard
    # way to find anomalies.
    power_std_dev = df[RF_POWER_COL].std()
    attack_threshold = avg_power + (3 * power_std_dev)

    print(f"Calculated 'Attack' Threshold: {attack_threshold:.2f} dBm")

    attacks = df[df[RF_POWER_COL] > attack_threshold]

    if attacks.empty:
        print("\nNo significant anomalies (attacks) detected.")
    else:
        print(f"\n--- {len(attacks)} ANOMALOUS EVENTS DETECTED ---")
        print(attacks[['timestamp', 'rf_power_dbm', 'lat', 'lon', 'activity']])

        # Plot attacks on a map (simple scatter plot)
        df_gps = attacks[(attacks['lat'] != 0.0) & (attacks['lon'] != 0.0)]
        if not df_gps.empty:
            plt.figure(figsize=(10, 8))
            plt.scatter(df_gps['lon'], df_gps['lat'], c=df_gps['rf_power_dbm'], cmap='Reds', s=50)
            plt.colorbar(label='RF Power (dBm)')
            plt.xlabel('Longitude')
            plt.ylabel('Latitude')
            plt.title('Map of High-Power RF Events')
            plt.grid(True)
            plt.savefig('attack_map.png')
            print("Saved 'attack_map.png'")
            plt.clf()

    # Plot RF Power over time
    plt.figure(figsize=(15, 6))
    df[RF_POWER_COL].plot(title='RF Power vs. Time')
    plt.axhline(y=attack_threshold, color='r', linestyle='--', label=f'Attack Threshold ({attack_threshold:.2f} dBm)')
    plt.xlabel('Log Entry (Time)')
    plt.ylabel('RF Power (dBm)')
    plt.legend()
    plt.savefig('rf_power_over_time.png')
    print("Saved 'rf_power_over_time.png'")
    plt.clf()


if __name__ == "__main__":
    if not os.path.exists(LOG_FILE):
        print(f"Error: {LOG_FILE} not found. Copy it from the SD card.")
    else:
        # Load the CSV
        data = pd.read_csv(LOG_FILE, parse_dates=['timestamp'])
        data.set_index('timestamp', inplace=True)
        analyze_rf_log(data)

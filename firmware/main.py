# main.py
# "Watchdog" RF Attack Logger (with OLED Display)

import machine
import uos
import time
import mpu6050
import micropyGPS
import sh1106  # Added for display
from machine import Pin, ADC, UART, SPI, SoftI2C
from sdcard import SDCard

# --- Config ---
# I2C (MPU6050, SH1106)
I2C_SCL_PIN = 22
I2C_SDA_PIN = 21
OLED_ADDR = 0x3C  # [cite: 1272]

# UART (GPS)
GPS_UART_NUM = 2
GPS_TX_PIN = 17
GPS_RX_PIN = 16

# SPI (SD Card)
SPI_SCK_PIN = 18
SPI_MOSI_PIN = 23
SPI_MISO_PIN = 19
SPI_CS_PIN = 5
SD_MOUNT_POINT = '/sd'

# ADC (RF Sensor)
RF_ADC_PIN = 34

# Logic
LOG_FILE = f"{SD_MOUNT_POINT}/rf_log.csv"
LOG_INTERVAL_MS = 250
RF_SLOPE = 0.025
RF_INTERCEPT = -95.0

# --- Globals ---
i2c = None
mpu = None
sd = None
gps_uart = None
gps_parser = micropyGPS.MicropyGPS()
rf_adc = None
oled = None  # Added for display


# --- Initialization ---
def init_all():
    global i2c, mpu, sd, gps_uart, rf_adc, oled
    print("Initializing components...")

    try:
        # I2C
        i2c = SoftI2C(scl=Pin(I2C_SCL_PIN), sda=Pin(I2C_SDA_PIN))
        devices = i2c.scan()
        print(f"I2C devices found: {[hex(d) for d in devices]}")

        # Init OLED (Exercise 67)
        try:
            oled = sh1106.SH1106_I2C(128, 64, i2c, None, OLED_ADDR, rotate=180)[cite: 1272]
            oled.fill(0)
            oled.text("Watchdog RF Log", 0, 0, 1)
            oled.text("Initializing...", 0, 10, 1)
            oled.show()
            print("OLED (SH1106) OK.")
        except Exception as e:
            print(f"OLED init failed: {e}")
            oled = None  # Continue without display if it fails

        # Init MPU6050 (Exercise 65)
        mpu = mpu6050.accel(i2c)
        print("MPU6050 (Activity) OK.")
        if oled:
            oled.text("MPU6050 OK", 0, 20, 1);
            oled.show()

        # UART (GPS)
        gps_uart = UART(GPS_UART_NUM, baudrate=9600, tx=GPS_TX_PIN, rx=GPS_RX_PIN, timeout=10)
        print("NEO-6M (GPS) OK.")
        if oled:
            oled.text("GPS OK", 0, 30, 1);
            oled.show()

        # ADC (RF Sensor)
        rf_adc = ADC(Pin(RF_ADC_PIN))
        rf_adc.atten(ADC.ATTN_11DB)  # Set full 0-3.6V range [cite: 960]
        print("AD8318 (RF Power) OK.")
        if oled:
            oled.text("RF OK", 0, 40, 1);
            oled.show()

        # SPI / SD (Exercise 77)
        spi = SPI(1, sck=Pin(SPI_SCK_PIN), mosi=Pin(SPI_MOSI_PIN), miso=Pin(SPI_MISO_PIN))
        sd = SDCard(spi, Pin(SPI_CS_PIN))
        uos.mount(sd, SD_MOUNT_POINT)[cite: 1335]
        print(f"SD card mounted at {SD_MOUNT_POINT}")
        if oled:
            oled.text("SD Card OK", 0, 50, 1);
            oled.show()

        # Check for log file
        try:
            uos.stat(LOG_FILE)
            print("Log file found.")
        except OSError:
            print("Log file not found. Creating new one.")
            with open(LOG_FILE, 'w') as f:
                f.write("timestamp,rf_power_dbm,lat,lon,altitude,activity\n")

        time.sleep(1)
        print("--- Init complete. Starting logger. ---")
        return True

    except Exception as e:
        print(f"Fatal init error: {e}")
        if oled:
            oled.fill(0);
            oled.text("INIT FAILED", 0, 0, 1);
            oled.show()
        return False


# --- Helper Functions ---
def get_activity_status():
    try:
        ax = mpu.get_values()["AcX"]
        ay = mpu.get_values()["AcY"]
        az = mpu.get_values()["AcZ"]
        mag_squared = (ax ** 2) + (ay ** 2) + (az ** 2)

        if mag_squared < 18000 ** 2 and mag_squared > 15000 ** 2:
            return "Still"
        elif mag_squared > 20000 ** 2:
            return "Moving"
        else:
            return "Low Activity"
    except Exception:
        return "Unknown"


def get_rf_power():
    try:
        adc_val = rf_adc.read()
        v_out = (adc_val / 4095) * 3.3
        dbm = (v_out / RF_SLOPE) + RF_INTERCEPT
        return dbm
    except Exception:
        return -100.0


def get_gps_data():
    if gps_uart.any():
        try:
            line = gps_uart.readline()
            if line:
                line_str = line.decode('utf-8')
                if line_str.startswith('$GPGGA'):
                    gps_parser.update(line_str)
        except Exception:
            pass  # Ignore GPS parse errors

    if gps_parser.fix_stat > 0:
        return gps_parser.latitude, gps_parser.longitude, gps_parser.altitude
    else:
        return 0.0, 0.0, 0.0


def get_timestamp():
    t = time.localtime()
    return f"{t[0]}-{t[1]:02d}-{t[2]:02d}T{t[3]:02d}:{t[4]:02d}:{t[5]:02d}"


def update_display(rf_power, lat, lon, activity):
    if not oled:
        return  # No display found

    oled.fill(0)  # [cite: 1272]

    # RF Power
    oled.text(f"RF: {rf_power:.1f} dBm", 0, 0, 1)

    # GPS Status
    gps_status = "FIX" if lat != 0.0 else "NO FIX"
    oled.text(f"GPS: {gps_status}", 0, 12, 1)
    oled.text(f"Lat: {lat:.3f}", 0, 24, 1)

    # Activity
    oled.text(f"Act: {activity}", 0, 36, 1)

    # SD Status
    # Simple check: just show it's mounted.
    oled.text("SD: LOGGING", 0, 48, 1)

    oled.show()  # [cite: 1272]


# --- Main Loop ---
def run_logger():
    if not init_all():
        return

    last_log_time = 0
    while True:
        try:
            current_time = time.ticks_ms()

            # Read GPS data (it's slow, so read it continuously)
            lat, lon, alt = get_gps_data()

            if time.ticks_diff(current_time, last_log_time) >= LOG_INTERVAL_MS:
                last_log_time = current_time

                # Get sensor snapshots
                timestamp = get_timestamp()
                rf_power = get_rf_power()
                activity = get_activity_status()

                # Format data
                log_line = f"{timestamp},{rf_power:.2f},{lat:.6f},{lon:.6f},{alt:.1f},{activity}\n"

                # Write to SD card
                with open(LOG_FILE, 'a') as f:
                    f.write(log_line)

                # Update display
                update_display(rf_power, lat, lon, activity)

                # Console log
                print(f"LOG: {rf_power:.2f} dBm, GPS:({lat:.2f},{lon:.2f}), ACT:{activity}")

        except Exception as e:
            print(f"Main loop error: {e}")
            if oled:
                oled.fill(0);
                oled.text("LOOP ERROR", 0, 0, 1);
                oled.show()
            time.sleep(1)


# Run the logger
run_logger()

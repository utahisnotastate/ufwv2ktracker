# main.py
# ufwv2ktracker V3.0 - Forensic Logger with Hash Chain & GPS
#
# Hardware:
# ESP32
# I2C (21/22): MPU6050, HMC5883L
# UART2 (16/17): NEO-6M GPS
# SPI (18/19/23/5): SD Card
# ADC1_CH0 (G36): MIC_AIR_PIN
# ADC1_CH1 (G39): MIC_PIEZO_PIN
# ADC1_CH2 (G34): RF_BROAD_PIN
# ADC1_CH3 (G35): RF_FILTER_PIN
# ADC1_CH4 (G32): GSR_PIN

import machine
import uos
import time
import mpu6050, hmc5883l, micropyGPS, gsr_sensor
import uhashlib, ubinascii
from machine import Pin, SoftI2C, SPI, ADC, UART
from sdcard import SDCard

# --- Config ---
# I2C (MPU6050, HMC5883L)
I2C_SCL_PIN = 22
I2C_SDA_PIN = 21

# ADCs (Note: Use ADC1 pins - G32-39, G36)
RF_BROAD_PIN = 34  # AD8318 #1 (Broadband)
RF_FILTER_PIN = 35  # AD8318 #2 (Filtered)
MIC_AIR_PIN = 36  # MAX4466 (Air Mic)
MIC_PIEZO_PIN = 39  # Piezo Contact Mic
GSR_PIN = 32  # GSR Sensor

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

LOG_FILE = f"{SD_MOUNT_POINT}/forensic_log_v3.csv"
LOG_INTERVAL_MS = 100  # Log 10x/sec

# AD8318 Calibration (Tune this)
RF_SLOPE = 0.025
RF_INTERCEPT = -95.0

# --- Globals ---
i2c, mpu, mag, gps_uart, sd = None, None, None, None, None
adc_rf_broad, adc_rf_filter, adc_mic_air, adc_mic_piezo, gsr_dev = None, None, None, None, None
gps_parser = micropyGPS.MicropyGPS()


# --- Initialization ---
def init_all():
    global i2c, mpu, mag, gps_uart, sd, gps_parser
    global adc_rf_broad, adc_rf_filter, adc_mic_air, adc_mic_piezo, gsr_dev
    print("Initializing components V3.0...")

    try:
        i2c = SoftI2C(scl=Pin(I2C_SCL_PIN), sda=Pin(I2C_SDA_PIN))
        mpu = mpu6050.accel(i2c)
        mag = hmc5883l.HMC5883L(i2c)
        print("I2C Sensors (IMU, Mag) OK.")

        # Init ADCs
        adc_rf_broad = ADC(Pin(RF_BROAD_PIN));
        adc_rf_broad.atten(ADC.ATTN_11DB)
        adc_rf_filter = ADC(Pin(RF_FILTER_PIN));
        adc_rf_filter.atten(ADC.ATTN_11DB)
        adc_mic_air = ADC(Pin(MIC_AIR_PIN));
        adc_mic_air.atten(ADC.ATTN_11DB)
        adc_mic_piezo = ADC(Pin(MIC_PIEZO_PIN));
        adc_mic_piezo.atten(ADC.ATTN_11DB)
        gsr_dev = gsr_sensor.GSRSensor(GSR_PIN)
        print("ADC Sensors (RF, Mics, GSR) OK.")

        gps_uart = UART(GPS_UART_NUM, 9600, tx=GPS_TX_PIN, rx=GPS_RX_PIN, timeout=10)
        print("GPS OK.")

        spi = SPI(1, 10000000, sck=Pin(SPI_SCK_PIN), mosi=Pin(SPI_MOSI_PIN), miso=Pin(SPI_MISO_PIN))
        sd = SDCard(spi, Pin(SPI_CS_PIN))
        uos.mount(sd, SD_MOUNT_POINT)
        print(f"SD card mounted at {SD_MOUNT_POINT}")

        # Check log file
        try:
            uos.stat(LOG_FILE)
        except OSError:
            with open(LOG_FILE, 'w') as f:
                f.write("timestamp,rf_broad,rf_filter,mic_air,mic_piezo,gsr_raw,"
                        "ax,ay,az,gx,gy,gz,mx,my,mz,lat,lon,alt,prev_hash\n")

        print("--- Init complete. Starting logger. ---")
        return True

    except Exception as e:
        print(f"Fatal init error: {e}")
        return False


# --- Helper Functions ---
def get_rf_power(adc):
    v_out = (adc.read() / 4095) * 3.3
    dbm = (v_out / RF_SLOPE) + RF_INTERCEPT
    return dbm


def get_hash(data_string):
    sha = uhashlib.sha256(data_string.encode('utf-8'))
    return ubinascii.hexlify(sha.digest()).decode('utf-8')


def get_last_line(filepath):
    try:
        # This is memory-intensive. For a real CSI tool, you'd
        # seek to the end of the file, read backwards to the last \n.
        # This is a good-enough hack for MicroPython.
        with open(filepath, 'r') as f:
            lines = f.readlines()
            if len(lines) > 1:
                return lines[-1].strip()
            else:
                return None
    except Exception:
        return None


def update_gps():
    if gps_uart.any():
        try:
            line = gps_uart.readline()
            if line: gps_parser.update(line.decode('utf-8'))
        except Exception:
            pass


def get_timestamp_ms():
    return time.ticks_ms()


# --- Main Loop ---
def run_logger():
    if not init_all(): return

    last_log_time = 0
    last_line = get_last_line(LOG_FILE)
    prev_hash = get_hash(last_line) if last_line else "0" * 64
    print(f"Resuming hash chain from: {prev_hash[:10]}...")

    log_buffer = []

    while True:
        try:
            current_time = time.ticks_ms()
            update_gps()

            if time.ticks_diff(current_time, last_log_time) >= LOG_INTERVAL_MS:
                last_log_time = current_time

                # --- 1. Get Sensor Snapshots ---
                ts = get_timestamp_ms()
                rf_b = get_rf_power(adc_rf_broad)
                rf_f = get_rf_power(adc_rf_filter)
                mic_a = adc_mic_air.read()  # Raw ADC, faster
                mic_p = adc_mic_piezo.read()  # Raw ADC
                gsr_val = gsr_dev.read_raw()

                imu = mpu.get_values()
                a_x, a_y, a_z = imu["AcX"], imu["AcY"], imu["AcZ"]
                g_x, g_y, g_z = imu["GyX"], imu["GyY"], imu["GyZ"]

                mag_vals = mag.get_values()
                m_x, m_y, m_z = mag_vals["MagX"], mag_vals["MagY"], mag_vals["MagZ"]

                lat, lon, alt = 0.0, 0.0, 0.0
                if gps_parser.fix_stat > 0:
                    lat, lon, alt = gps_parser.latitude, gps_parser.longitude, gps_parser.altitude

                # --- 2. Create Log Line & Hash ---
                log_line = (f"{ts},{rf_b:.2f},{rf_f:.2f},{mic_a},{mic_p},{gsr_val},"
                            f"{a_x},{a_y},{a_z},{g_x},{g_y},{g_z},{m_x},{m_y},{m_z},"
                            f"{lat:.6f},{lon:.6f},{alt:.1f},{prev_hash}")

                prev_hash = get_hash(log_line)  # Update hash for next loop
                log_buffer.append(log_line + "\n")

                # --- 3. Write to SD Card ---
                if len(log_buffer) >= 20:  # Write every 2 seconds
                    with open(LOG_FILE, 'a') as f:
                        for line in log_buffer:
                            f.write(line)
                    log_buffer = []
                    print(f"LOG: RF:{rf_f:.0f} Piezo:{mic_p} GSR:{gsr_val} GPS:{gps_parser.fix_stat}")

        except Exception as e:
            print(f"Main loop error: {e}")
            if log_buffer:
                with open(LOG_FILE, 'a') as f:
                    for line in log_buffer:
                        f.write(line)
            time.sleep(1)


# Run the logger
run_logger()

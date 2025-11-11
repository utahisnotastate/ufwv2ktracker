# /firmware/lib/gsr_sensor.py
# Simple driver for a Grove-style GSR sensor

from machine import ADC, Pin
import time


class GSRSensor:
    def __init__(self, adc_pin):
        self.adc = ADC(Pin(adc_pin))
        self.adc.atten(ADC.ATTN_11DB)  # Set full 0-3.6V range

    def read_raw(self):
        """
        Reads the raw 12-bit ADC value (0-4095).
        This is the fastest and best value for ML analysis.
        """
        try:
            return self.adc.read()
        except Exception:
            return 0

    def read_resistance(self):
        """
        Calculates the approximate skin resistance.
        This is for human-readable output, not for logging.
        """
        try:
            adc_val = self.adc.read()
            if adc_val == 0:
                return float('inf')  # Avoid division by zero

            # Standard Grove GSR sensor has a 1M Ohm resistor (R_DIV)
            # V_out = VCC * R_skin / (R_skin + R_DIV)
            # R_skin = R_DIV * V_out / (VCC - V_out)
            # VCC = 3.3V (maps to 4095)
            # V_out = 3.3V * (adc_val / 4095)
            # So, R_skin = 1000000 * (adc_val / 4095) / (1 - (adc_val / 4095))
            # R_skin = 1000000 * adc_val / (4095 - adc_val)

            resistance = 1000000.0 * adc_val / (4095.0 - adc_val)
            return resistance  # in Ohms

        except Exception:
            return 0

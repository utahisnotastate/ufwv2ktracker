# /firmware/lib/micropyGPS.py
# A simple, lightweight NMEA sentence parser for MicroPython

import time


class MicropyGPS:
    def __init__(self):
        self.latitude = 0.0
        self.longitude = 0.0
        self.altitude = 0.0
        self.satellites_used = 0
        self.timestamp = (0, 0, 0.0)
        self.fix_stat = 0

    def _parse_lat_lon(self, part_str, direction_str):
        if not part_str:
            return 0.0
        try:
            val = float(part_str)
            deg = int(val / 100)
            minutes = val - (deg * 100)
            decimal_val = deg + (minutes / 60)
            if direction_str == 'S' or direction_str == 'W':
                decimal_val = -decimal_val
            return decimal_val
        except ValueError:
            return 0.0

    def update(self, sentence):
        try:
            if not sentence or not sentence.startswith('$GPGGA'):
                return False

            parts = sentence.split(',')
            if len(parts) < 10:
                return False

            # Check checksum
            try:
                payload, checksum = sentence.strip().split('*')
                calc_checksum = 0
                for char in payload[1:]:
                    calc_checksum ^= ord(char)
                if int(checksum, 16) != calc_checksum:
                    return False  # Checksum mismatch
            except:
                return False  # Checksum parse error

            # $GPGGA,timestamp,lat,N/S,lon,E/W,fix,sats,hdop,alt,M,...

            # Fix Status (Index 6)
            self.fix_stat = int(parts[6]) if parts[6] else 0
            if self.fix_stat == 0:
                return False  # No fix

            # Time (Index 1)
            time_str = parts[1]
            if time_str:
                self.timestamp = (int(time_str[0:2]), int(time_str[2:4]), float(time_str[4:]))

            # Satellites (Index 7)
            self.satellites_used = int(parts[7]) if parts[7] else 0

            # Latitude (Index 2, 3)
            self.latitude = self._parse_lat_lon(parts[2], parts[3])

            # Longitude (Index 4, 5)
            self.longitude = self._parse_lat_lon(parts[4], parts[5])

            # Altitude (Index 9)
            self.altitude = float(parts[9]) if parts[9] else 0.0

            return True

        except Exception as e:
            return False

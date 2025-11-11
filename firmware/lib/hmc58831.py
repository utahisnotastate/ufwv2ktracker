# /firmware/lib/hmc5883l.py
# Driver for HMC5883L Magnetometer

from machine import I2C
import time
import ustruct


class HMC5883L:
    def __init__(self, i2c, address=0x1E):
        self.i2c = i2c
        self.address = address

        # Config Reg A: 75Hz data output rate
        self.i2c.writeto_mem(self.address, 0x00, b'\x18')
        # Config Reg B: Gain (default)
        self.i2c.writeto_mem(self.address, 0x01, b'\x20')
        # Mode Register: Continuous-measurement mode
        self.i2c.writeto_mem(self.address, 0x02, b'\x00')

    def read_raw(self):
        try:
            # Read 6 bytes of data starting from 0x03
            data = self.i2c.readfrom_mem(self.address, 0x03, 6)

            # Data is in X, Z, Y order
            # Each is a 16-bit signed big-endian value
            x = ustruct.unpack_from('>h', data, 0)[0]
            z = ustruct.unpack_from('>h', data, 2)[0]
            y = ustruct.unpack_from('>h', data, 4)[0]

            return (x, y, z)
        except OSError:
            # Handle I2C read error
            return (0, 0, 0)

    def get_values(self):
        x, y, z = self.read_raw()
        return {"MagX": x, "MagY": y, "MagZ": z}

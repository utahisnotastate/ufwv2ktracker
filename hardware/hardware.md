
Here's the plan to add the OLED display and the complete GitHub repository structure.

1. Updated Hardware
You only need to add one component to your existing BOM.

Display: SH1106 1.3-inch OLED Display (I2C). Your book covers this in Exercise 67.

2. Updated Wiring
The OLED display connects to the same I2C bus as your other sensors.

OLED Display (I2C):

VCC -> ESP32 3V3

GND -> ESP32 GND

SCL -> ESP32 GPIO 22 (I2C)

SDA -> ESP32 GPIO 21 (I2C)

This display's default I2C address is typically 0x3C. Your other I2C devices (MPU6050 at 0x68) won't conflict.

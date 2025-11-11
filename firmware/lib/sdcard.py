# /firmware/lib/sdcard.py
# MicroPython driver for SD cards using SPI bus.

import time
from micropython import const

_CMD_TIMEOUT = const(100)

_R1_IDLE_STATE = const(1 << 0)
_R1_ERASE_RESET = const(1 << 1)
_R1_ILLEGAL_COMMAND = const(1 << 2)
_R1_COM_CRC_ERROR = const(1 << 3)
_R1_ERASE_SEQUENCE_ERROR = const(1 << 4)
_R1_ADDRESS_ERROR = const(1 << 5)
_R1_PARAMETER_ERROR = const(1 << 6)

# Command definitions
_CMD0 = const(0)  # GO_IDLE_STATE
_CMD1 = const(1)  # SEND_OP_COND
_CMD8 = const(8)  # SEND_IF_COND
_CMD16 = const(16)  # SET_BLOCKLEN
_CMD17 = const(17)  # READ_SINGLE_BLOCK
_CMD24 = const(24)  # WRITE_BLOCK
_CMD55 = const(55)  # APP_CMD
_CMD58 = const(58)  # READ_OCR
_ACMD41 = const(41)  # SD_SEND_OP_COND

# Card types
_CARD_TYPE_SD1 = const(1)
_CARD_TYPE_SD2 = const(2)
_CARD_TYPE_SDHC = const(3)


class SDCard:
    def __init__(self, spi, cs):
        self.spi = spi
        self.cs = cs

        self.cmdbuf = bytearray(6)
        self.tokenbuf = bytearray(1)
        self.buf = bytearray(512)

        self.cs.init(self.cs.OUT, value=1)
        self.card_type = None
        self.init_card()

    def init_card(self):
        self.cs.value(1)

        # Set SPI to low speed for init
        try:
            self.spi.init(baudrate=250000)
        except TypeError:
            self.spi.init()  # Use default slow speed if re-init fails

        for _ in range(10):
            self.spi.write(b"\xff")

        # CMD0: GO_IDLE_STATE
        self.cs.value(0)
        if self._cmd(_CMD0, 0, 0x95) != _R1_IDLE_STATE:
            raise OSError("SD card: No response to CMD0")
        self.cs.value(1)

        # CMD8: SEND_IF_COND
        self.cs.value(0)
        r = self._cmd(_CMD8, 0x1AA, 0x87, 4)
        if r == _R1_IDLE_STATE:
            self.card_type = _CARD_TYPE_SD2
            if r[1] != 0x01 or r[2] != 0xAA:
                raise OSError("SD card: Invalid response to CMD8")
        elif r == (_R1_IDLE_STATE | _R1_ILLEGAL_COMMAND):
            self.card_type = _CARD_TYPE_SD1
        else:
            raise OSError("SD card: Invalid response to CMD8")
        self.cs.value(1)

        # ACMD41: SD_SEND_OP_COND
        arg = 0x40000000 if self.card_type == _CARD_TYPE_SD2 else 0
        start_time = time.ticks_ms()
        while True:
            self.cs.value(0)
            if self._cmd(_CMD55, 0) == _R1_IDLE_STATE:
                if self._cmd(_ACMD41, arg) == 0:
                    self.cs.value(1)
                    break
            self.cs.value(1)
            if time.ticks_diff(time.ticks_ms(), start_time) > 1000:
                raise OSError("SD card: Timeout on ACMD41")

        # CMD58: READ_OCR
        if self.card_type == _CARD_TYPE_SD2:
            self.cs.value(0)
            r = self._cmd(_CMD58, 0, 0, 4)
            if r[0] & 0x40:
                self.card_type = _CARD_TYPE_SDHC
            self.cs.value(1)

        # CMD16: SET_BLOCKLEN
        self.cs.value(0)
        if self._cmd(_CMD16, 512) != 0:
            raise OSError("SD card: Error on CMD16 (set blocklen)")
        self.cs.value(1)

        # Set SPI to full speed
        self.spi.init(baudrate=10000000)

    def _cmd(self, cmd, arg, crc=0, readlen=0):
        self.cmdbuf[0] = 0x40 | cmd
        self.cmdbuf[1] = (arg >> 24) & 0xFF
        self.cmdbuf[2] = (arg >> 16) & 0xFF
        self.cmdbuf[3] = (arg >> 8) & 0xFF
        self.cmdbuf[4] = arg & 0xFF
        self.cmdbuf[5] = crc
        self.spi.write(self.cmdbuf)

        # Wait for response
        for _ in range(_CMD_TIMEOUT):
            self.spi.readinto(self.tokenbuf, 0xFF)
            if not (self.tokenbuf[0] & 0x80):
                if readlen == 0:
                    return self.tokenbuf[0]
                else:
                    r = bytearray(readlen)
                    self.spi.readinto(r, 0xFF)
                    return r
        return -1

    def _wait_ready(self):
        start_time = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), start_time) < 500:
            self.spi.readinto(self.tokenbuf, 0xFF)
            if self.tokenbuf[0] == 0xFF:
                return 0
            time.sleep_ms(1)
        return -1  # Timeout

    def _readinto(self, cmd, buf, arg=0):
        self.cs.value(0)
        if self._cmd(cmd, arg) != 0:
            self.cs.value(1)
            return -1

        # Wait for data token
        start_time = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), start_time) < 200:
            self.spi.readinto(self.tokenbuf, 0xFF)
            if self.tokenbuf[0] == 0xFE:  # Start block token
                break
            time.sleep_ms(1)
        else:
            self.cs.value(1)
            return -1  # Timeout

        self.spi.readinto(buf, 0xFF)  # Read data block
        self.spi.write(b"\xff\xff")  # Read 2-byte CRC
        self.cs.value(1)
        return 0

    def _write(self, cmd, buf, token=0xFE, arg=0):
        self.cs.value(0)
        if self._cmd(cmd, arg) != 0:
            self.cs.value(1)
            return -1

        self.spi.write(bytearray([token]))  # Start block token
        self.spi.write(buf)  # Data
        self.spi.write(b"\xff\xff")  # Dummy CRC

        # Wait for response token
        for _ in range(_CMD_TIMEOUT):
            self.spi.readinto(self.tokenbuf, 0xFF)
            if not (self.tokenbuf[0] & 0x10 == 0):
                break

        if (self.tokenbuf[0] & 0x0F) != 0x05:  # Check if data accepted
            self.cs.value(1)
            return -1

        if self._wait_ready() != 0:  # Wait for card to finish
            self.cs.value(1)
            return -1

        self.cs.value(1)
        return 0

    # --- Block Device API ---
    def readblocks(self, block_num, buf, num_blocks=1):
        if len(buf) != 512 * num_blocks:
            raise ValueError("Buffer size must be 512 * num_blocks")

        offset = 0
        for i in range(num_blocks):
            addr = block_num + i
            if self.card_type != _CARD_TYPE_SDHC:
                addr *= 512

            if self._readinto(_CMD17, self.buf, addr) != 0:
                return -1
            buf[offset:offset + 512] = self.buf
            offset += 512
        return 0

    def writeblocks(self, block_num, buf, num_blocks=1):
        if len(buf) != 512 * num_blocks:
            raise ValueError("Buffer size must be 512 * num_blocks")

        offset = 0
        for i in range(num_blocks):
            addr = block_num + i
            if self.card_type != _CARD_TYPE_SDHC:
                addr *= 512

            self.buf[:] = buf[offset:offset + 512]
            if self._write(_CMD24, self.buf, 0xFE, addr) != 0:
                return -1
            offset += 512
        return 0

    def ioctl(self, op, arg):
        if op == 4:  # Get number of blocks
            # This is a simplified CSD read.
            # A full CSD parse is complex. We'll estimate or use a common size.
            # For modern SDHC cards, this is large.
            # This is a placeholder. For a real CSI tool, you'd fully parse the CSD.
            return 8 * 1024 * 1024  # Assume 8GB card, 512-byte blocks
        if op == 5:  # Get block size
            return 512
        return -1

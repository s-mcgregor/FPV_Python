# crsf_reader.py  —  MicroPython on Raspberry Pi Pico
# Reads ELRS/CRSF RC channels (type 0x16) over UART and prints normalized values.

from machine import UART, Pin
import time

# ----- USER CONFIG -----
UART_ID   = 0         # 0 or 1
PIN_RX    = 1         # UART0 RX=GP1 (change to 5 if using UART1)
PIN_TX    = 0         # UART0 TX=GP0 (optional; needed only for telemetry)
BAUD      = 420000    # try 416666 if your setup prefers it
TIMEOUT   = 50        # ms UART timeout

# ----- CRSF CONSTANTS -----
CRSF_SYNC = 0xC8
TYPE_RC_CHANNELS = 0x16
MAX_FRAME = 64

# CRC8 (poly 0xD5), init=0, over [type..payload]
def crc8_d5(buf):
    poly = 0xD5
    crc = 0x00
    for b in buf:
        crc ^= b
        for _ in range(8):
            if (crc & 0x80):
                crc = ((crc << 1) ^ poly) & 0xFF
            else:
                crc = (crc << 1) & 0xFF
    return crc

# Convert CRSF ticks <-> microseconds and to [-1, 1]
def ticks_to_us(t):     # per CRSF spec
    return int((t - 992) * 5 / 8 + 1500)

def ticks_to_unit(t):   # map 1000..2000us to ~ -1..+1 using 1500 center
    us = ticks_to_us(t)
    return max(-1.0, min(1.0, (us - 1500) / 500.0))

# Unpack 16 x 11-bit channels from 22 payload bytes
def unpack_16ch_11bit(payload22):
    bits = 0
    bitbuf = 0
    out = []
    for b in payload22:
        bitbuf |= (b << bits)
        bits += 8
        while bits >= 11 and len(out) < 16:
            out.append(bitbuf & 0x7FF)
            bitbuf >>= 11
            bits -= 11
    # Ensure 16 entries
    while len(out) < 16:
        out.append(992)  # neutral
    return out[:16]

# ----- UART SETUP -----
uart = UART(UART_ID, baudrate=BAUD, bits=8, parity=None, stop=1, tx=Pin(PIN_TX), rx=Pin(PIN_RX), timeout=TIMEOUT)

def read_frame():
    # Sync hunt
    while True:
        b = uart.read(1)
        if not b:
            return None
        if b[0] == CRSF_SYNC:
            break

    # Length
    lb = uart.read(1)
    if not lb:
        return None
    length = lb[0]  # type + payload + crc
    if length < 2 or length > (MAX_FRAME - 2):
        return None

    rest = uart.read(length)
    if not rest or len(rest) != length:
        return None

    frame_type = rest[0]
    payload = rest[1:-1]
    crc = rest[-1]

    # CRC over [type + payload]
    if crc8_d5(bytes([frame_type]) + payload) != crc:
        return None

    return (frame_type, payload)

print("CRSF reader starting at {} baud...".format(BAUD))

last_print = time.ticks_ms()

while True:
    f = read_frame()
    if not f:
        continue

    ftype, pl = f

    if ftype == TYPE_RC_CHANNELS and len(pl) == 22:
        ch_ticks = unpack_16ch_11bit(pl)
        # Normalize CH1..CH4 for quick viewing
        roll  = ticks_to_unit(ch_ticks[0])   # CH1
        pitch = ticks_to_unit(ch_ticks[1])   # CH2
        yaw   = ticks_to_unit(ch_ticks[2])   # CH3
        thr   = ticks_to_unit(ch_ticks[3])   # CH4

        # Print at ~20 Hz
        now = time.ticks_ms()
        if time.ticks_diff(now, last_print) > 50:
            print("CH1..4 (unit):", round(roll,3), round(pitch,3), round(yaw,3), round(thr,3),
                  "| RAW ticks:", ch_ticks[:8])
            last_print = now

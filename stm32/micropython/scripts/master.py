import lin
import time

lin.init(1, 19200)

while True:
    lin.send(1, 0x12, b"\x01\x02\x03\x04")
    time.sleep_ms(100)

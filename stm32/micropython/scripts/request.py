import lin
import time

lin.init(2, 19200)

while True:
    print("LIN2 0x22:", lin.request(2, 0x22, 4))
    time.sleep_ms(250)

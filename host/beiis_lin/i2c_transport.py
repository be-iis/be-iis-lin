from __future__ import annotations
import time
from smbus2 import SMBus, i2c_msg

REG_STATUS=0x00
REG_RX_FREE=0x01
REG_TX_COUNT=0x02
REG_RX_DATA=0x10
REG_TX_DATA=0x20
REG_CONTROL=0x30
REG_VERSION=0x31

class I2CBytePipe:
    def __init__(self,bus:int=1,address:int=0x42,block_size:int=32,poll_s:float=0.001):
        self.address=address
        self.block_size=block_size
        self.poll_s=poll_s
        self.bus=SMBus(bus)

    def close(self):
        self.bus.close()

    def _read_reg(self,reg:int,n:int)->bytes:
        w=i2c_msg.write(self.address,[reg])
        r=i2c_msg.read(self.address,n)
        self.bus.i2c_rdwr(w,r)
        return bytes(r)

    def _write_reg(self,reg:int,data:bytes=b""):
        self.bus.i2c_rdwr(i2c_msg.write(self.address,bytes([reg])+data))

    def raw_write(self,data:bytes):
        self.bus.i2c_rdwr(i2c_msg.write(self.address,data))

    def raw_read(self,n:int)->bytes:
        r=i2c_msg.read(self.address,n)
        self.bus.i2c_rdwr(r)
        return bytes(r)

    def wait_for_mboot(self,timeout:float=2.0):
        # Raw REPL acknowledges submitted code before machine.bootloader()
        # has necessarily completed.  Wait until mboot's ECHO command answers.
        time.sleep(0.05)
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            try:
                self.raw_write(b"\x01")
                time.sleep(0.002)
                if self.raw_read(1)==b"\x01":
                    return
            except OSError:
                pass
            time.sleep(0.01)
        raise TimeoutError("mboot did not become ready on I2C")

    def version(self)->int:
        return self._read_reg(REG_VERSION,1)[0]

    def status(self)->int:
        return self._read_reg(REG_STATUS,1)[0]

    def in_waiting(self)->int:
        return self._read_reg(REG_TX_COUNT,1)[0]

    def reset_fifos(self):
        self._write_reg(REG_CONTROL,b"\x01")

    def write(self,data:bytes,timeout:float=2.0)->int:
        view=memoryview(data)
        pos=0
        deadline=time.monotonic()+timeout
        while pos<len(view):
            if time.monotonic()>=deadline:
                raise TimeoutError("timeout waiting for STM32 RX FIFO")
            free=self._read_reg(REG_RX_FREE,1)[0]
            if not free:
                time.sleep(self.poll_s)
                continue
            n=min(free,self.block_size,len(view)-pos)
            self._write_reg(REG_RX_DATA,bytes(view[pos:pos+n]))
            pos+=n
        return pos

    def read(self,n:int,timeout:float=2.0)->bytes:
        out=bytearray()
        deadline=time.monotonic()+timeout
        while len(out)<n and time.monotonic()<deadline:
            count=self.in_waiting()
            if count:
                chunk=min(count,self.block_size,n-len(out))
                out+=self._read_reg(REG_TX_DATA,chunk)
            else:
                time.sleep(self.poll_s)
        return bytes(out)

    def read_until_idle(self,idle_s:float=0.03,timeout:float=2.0)->bytes:
        out=bytearray()
        deadline=time.monotonic()+timeout
        idle_deadline=None
        while time.monotonic()<deadline:
            count=self.in_waiting()
            if count:
                out+=self._read_reg(REG_TX_DATA,min(count,self.block_size))
                idle_deadline=time.monotonic()+idle_s
            elif idle_deadline is not None and time.monotonic()>=idle_deadline:
                break
            else:
                time.sleep(self.poll_s)
        return bytes(out)

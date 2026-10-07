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

REG_APP_RX_FREE=0x03
REG_APP_TX_COUNT=0x04
REG_APP_STATUS=0x05
REG_APP_RX_DATA=0x11
REG_APP_TX_DATA=0x21
REG_APP_VERSION=0x32
REG_APP_CHANNELS=0x33
REG_APP_CONTROL=0x34
REG_APP_MAX_PAYLOAD_LO=0x35
REG_APP_MAX_PAYLOAD_HI=0x36
REG_APP_ACTIVE_INSTANCE=0x37

APP_MGMT_CHANNEL=0xFF

class I2CBytePipe:
    def __init__(self,bus:int=1,address:int=0x42,block_size:int=32,poll_s:float=0.001):
        self.address=address
        self.block_size=block_size
        self.poll_s=poll_s
        self.bus=SMBus(bus)
        self._app_bytes=bytearray()
        self._app_frames=[]

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


    def app_capabilities(self)->dict:
        version=self._read_reg(REG_APP_VERSION,1)[0]
        channels=self._read_reg(REG_APP_CHANNELS,1)[0]
        lo=self._read_reg(REG_APP_MAX_PAYLOAD_LO,1)[0]
        hi=self._read_reg(REG_APP_MAX_PAYLOAD_HI,1)[0]
        return {
            "protocol_version":version,
            "channels":channels,
            "max_payload":lo|(hi<<8),
            "active_instance":self._read_reg(REG_APP_ACTIVE_INSTANCE,1)[0],
            "status":self._read_reg(REG_APP_STATUS,1)[0],
        }

    def app_active_instance(self)->int:
        return self._read_reg(REG_APP_ACTIVE_INSTANCE,1)[0]

    def app_set_active_instance(self,instance:int):
        instance=int(instance)
        if not 0<=instance<16:
            raise ValueError("active instance must be 0..15")
        self._write_reg(REG_APP_ACTIVE_INSTANCE,bytes((instance,)))

    def app_reset(self):
        self._write_reg(REG_APP_CONTROL,b"\x01")
        self._app_bytes.clear()
        self._app_frames.clear()

    def app_device_reset(self):
        """Reset the STM32 through the native application control register."""
        self._write_reg(REG_APP_CONTROL,b"\x80")
        self._app_bytes.clear()
        self._app_frames.clear()

    def app_enter_bootloader(self):
        """Enter mboot through the native application control register."""
        self._write_reg(REG_APP_CONTROL,b"\x40")
        self._app_bytes.clear()
        self._app_frames.clear()

    def _app_extract_frames(self):
        while len(self._app_bytes)>=4:
            instance=self._app_bytes[0]
            channel=self._app_bytes[1]
            length=self._app_bytes[2]|(self._app_bytes[3]<<8)
            total=4+length
            if len(self._app_bytes)<total:
                return
            payload=bytes(self._app_bytes[4:total])
            del self._app_bytes[:total]
            self._app_frames.append((instance,channel,payload))

    def _app_take_frame(self,instance:int|None,channel:int|None):
        for index,frame in enumerate(self._app_frames):
            if instance is not None and frame[0]!=instance:
                continue
            if channel is not None and frame[1]!=channel:
                continue
            return self._app_frames.pop(index)
        return None

    def app_send(self,channel:int,data:bytes,timeout:float=2.0):
        caps=self.app_capabilities()
        max_payload=caps["max_payload"]
        if not (0<=channel<caps["channels"] or channel==APP_MGMT_CHANNEL):
            raise ValueError(f"application channel must be 0..{caps['channels']-1} or 0xff")
        payload=bytes(data)
        if len(payload)>max_payload:
            raise ValueError(f"application payload exceeds {max_payload} bytes")
        frame=bytes((channel,len(payload)&0xff,(len(payload)>>8)&0xff))+payload
        pos=0
        deadline=time.monotonic()+timeout
        while pos<len(frame):
            if time.monotonic()>=deadline:
                raise TimeoutError("timeout waiting for STM32 application RX FIFO")
            free=self._read_reg(REG_APP_RX_FREE,1)[0]
            if not free:
                time.sleep(self.poll_s)
                continue
            n=min(free,self.block_size,len(frame)-pos)
            self._write_reg(REG_APP_RX_DATA,frame[pos:pos+n])
            pos+=n

    def app_recv(self,instance:int|None=None,channel:int|None=None,timeout:float=2.0):
        frame=self._app_take_frame(instance,channel)
        if frame is not None:
            return frame

        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            count=self._read_reg(REG_APP_TX_COUNT,1)[0]
            if count:
                self._app_bytes+=self._read_reg(REG_APP_TX_DATA,min(count,self.block_size))
                self._app_extract_frames()
                frame=self._app_take_frame(instance,channel)
                if frame is not None:
                    return frame
            else:
                time.sleep(self.poll_s)
        raise TimeoutError("timeout waiting for STM32 application data")

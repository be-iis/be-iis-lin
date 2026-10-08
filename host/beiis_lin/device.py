from __future__ import annotations
from pathlib import Path
import binascii
import json
from .i2c_transport import I2CBytePipe
from .raw_repl import RawRepl
from .mboot import MbootClient

class LinHat:
    def __init__(
        self,
        bus:int=1,
        address:int=0x42,
        irq_gpio:int|None=None,
        irq_chip:str|None=None,
    ):
        self.transport=I2CBytePipe(
            bus,
            address,
            irq_gpio=irq_gpio,
            irq_chip=irq_chip,
        )
        self.repl=RawRepl(self.transport)
        self._app_request_id=1

    def close(self):
        self.transport.close()

    def ping(self)->dict:
        return {"protocol_version":self.transport.version(),"status":self.transport.status()}

    def exec(self,source:str)->str:
        out,err=self.repl.exec(source)
        if err:
            raise RuntimeError(err.decode("utf-8","replace"))
        return out.decode("utf-8","replace")

    def bootloader(self):
        # Application protocol v3 adds a native mboot control path which stays
        # available even when a MicroPython runtime owns the interpreter.
        try:
            if self.transport.app_capabilities()["protocol_version"] >= 3:
                self.transport.app_enter_bootloader()
                self.transport.wait_for_mboot()
                return
        except OSError:
            pass

        # Compatibility path for older firmware.
        self.repl.exec_detached("import machine; machine.bootloader()")
        self.transport.wait_for_mboot()

    def ensure_mboot(self)->MbootClient:
        # If the normal application protocol is alive, enter mboot first.
        # If not, accept an already-running mboot instance.
        try:
            if self.transport.version()==1:
                self.bootloader()
        except OSError:
            pass
        mboot=MbootClient(self.transport)
        mboot.echo()
        return mboot

    def mboot_info(self)->dict:
        mboot=self.ensure_mboot()
        info=mboot.parse_id(mboot.get_id())
        info["layout"]=mboot.get_layout()
        return info

    def flash_firmware(self,path:str|Path,progress=None)->dict:
        mboot=self.ensure_mboot()
        info=mboot.parse_id(mboot.get_id())
        if info.get("board")!="BE-IIS LIN HAT":
            raise RuntimeError(f"refusing to flash unexpected board: {info}")
        result=mboot.flash_application(path,progress=progress)
        mboot.reset()

        import time
        deadline=time.monotonic()+3.0
        while time.monotonic()<deadline:
            try:
                if self.transport.version()==1:
                    result["application_protocol_version"]=1
                    return result
            except OSError:
                pass
            time.sleep(0.05)
        raise TimeoutError("firmware verified and reset, but application did not return")

    def mboot_reset(self):
        mboot=self.ensure_mboot()
        mboot.reset()

        # mboot RESET intentionally tears down the bootloader immediately.
        # Wait until the native application I2C register block is reachable
        # again, then perform one defined application-side system reset.  This
        # gives autostart code the same clean boot path as device_reset() and
        # avoids racing the long-lived daemon against the mboot->application
        # transition.
        import time
        deadline=time.monotonic()+3.0
        last_error=None
        while time.monotonic()<deadline:
            try:
                caps=self.transport.app_capabilities()
                if caps.get("protocol_version",0)>=3:
                    self.transport.app_device_reset()
                    time.sleep(0.1)
                    return
            except (OSError,IndexError) as exc:
                last_error=exc
            time.sleep(0.02)
        raise TimeoutError(f"application did not return after mboot reset: {last_error!r}")

    def run_file(self,path:str|Path)->str:
        return self.exec(Path(path).read_text(encoding="utf-8"))

    def put(self,local:str|Path,remote:str):
        data=Path(local).read_bytes()
        code=("import binascii\n"
              f"_d=binascii.unhexlify('{data.hex()}')\n"
              f"open({remote!r},'wb').write(_d)\n"
              "del _d\n")
        return self.exec(code)


    def lin_init(self,channel:int,baud:int):
        self.exec(f"import lin; lin.init({int(channel)},{int(baud)})")

    def lin_send(self,channel:int,frame_id:int,data:bytes,enhanced:bool=True):
        payload=bytes(data)
        self.exec(
            f"import lin; lin.send({int(channel)},{int(frame_id)},{payload!r},{bool(enhanced)!r})"
        )

    def lin_request(self,channel:int,frame_id:int,length:int,enhanced:bool=True)->bytes:
        out=self.exec(
            "import lin,binascii; "
            f"print(binascii.hexlify(lin.request({int(channel)},{int(frame_id)},{int(length)},{bool(enhanced)!r})).decode())"
        ).strip()
        return bytes.fromhex(out)

    def lin_slave_set(self,channel:int,frame_id:int,data:bytes,enhanced:bool=True):
        payload=bytes(data)
        self.exec(
            f"import lin; lin.slave_set({int(channel)},{int(frame_id)},{payload!r},{bool(enhanced)!r})"
        )

    def lin_slave_clear(self,channel:int):
        self.exec(f"import lin; lin.slave_clear({int(channel)})")


    def app_capabilities(self)->dict:
        return self.transport.app_capabilities()

    def active_instance(self)->int:
        return self.transport.app_active_instance()

    def set_active_instance(self,instance:int):
        self.transport.app_set_active_instance(instance)

    def device_reset(self):
        self.transport.app_device_reset()

    def data_send(self,channel:int,data:bytes,timeout:float=2.0):
        self.transport.app_send(int(channel),bytes(data),timeout=timeout)

    def data_recv(self,instance:int|None=None,channel:int|None=None,timeout:float=2.0):
        return self.transport.app_recv(instance=instance,channel=channel,timeout=timeout)

    def wait_irq(self,timeout:float=1.0)->bool:
        return self.transport.wait_irq(timeout)

    def drain_irq(self):
        self.transport.drain_irq()

    def irq_info(self)->dict:
        return self.transport.irq_info()

    def prepare_host_irq(self)->dict:
        if self.transport.irq is None:
            return self.transport.irq_info()

        # A daemon restart has no clients yet, so stale STM32->host application
        # frames cannot be consumed meaningfully. Clear only the application
        # transport FIFOs, leave runtime instances and LIN state untouched,
        # then sample a guaranteed idle GPIO level.
        self.transport.app_reset()
        self.transport.calibrate_irq_idle()
        return self.transport.irq_info()

    def runtime_call(self,op:str,args:dict|None=None,timeout:float=2.0):
        request_id=self._app_request_id
        self._app_request_id+=1
        request={"id":request_id,"op":str(op),"args":args or {}}
        self.transport.app_send(0xff,json.dumps(request,separators=(",",":")).encode(),timeout=timeout)

        import time
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            remaining=max(0.001,deadline-time.monotonic())
            _,_,payload=self.transport.app_recv(instance=0xff,channel=0xff,timeout=remaining)
            response=json.loads(payload.decode("utf-8"))
            if int(response.get("id",0))!=request_id:
                continue
            if response.get("ok"):
                return response.get("result")
            raise RuntimeError(response.get("error","runtime operation failed"))
        raise TimeoutError("timeout waiting for STM32 app runtime")

    def app_install(self,path:str|Path,app:str|None=None,timeout:float=5.0):
        path=Path(path)
        data=path.read_bytes()
        app=app or path.stem
        self.runtime_call("install_begin",{"app":app,"size":len(data)},timeout=timeout)
        for offset in range(0,len(data),384):
            chunk=data[offset:offset+384]
            self.runtime_call("install_chunk",{"app":app,"data":chunk.hex()},timeout=timeout)
        crc=binascii.crc32(data)&0xffffffff
        return self.runtime_call("install_commit",{"app":app,"crc32":crc},timeout=timeout)

    def app_remove(self,app:str):
        return self.runtime_call("app_remove",{"app":app})

    def app_list(self):
        return self.runtime_call("app_list")

    def instance_list(self):
        return self.runtime_call("instance_list")

    def instance_add(self,name:str,app:str,channels=None,config=None,autostart:bool=False,resources=None,tap:bool=False):
        return self.runtime_call("instance_add",{
            "name":name,
            "app":app,
            "channels":list(channels or []),
            "config":config or {},
            "autostart":bool(autostart),
            "resources":list(resources or []),
            "tap":bool(tap),
        })

    def instance_remove(self,name:str):
        return self.runtime_call("instance_remove",{"name":name})

    def instance_start(self,name:str):
        return self.runtime_call("start",{"name":name})

    def instance_stop(self,name:str):
        return self.runtime_call("stop",{"name":name})

    def instance_restart(self,name:str):
        return self.runtime_call("restart",{"name":name})

    def instance_autostart(self,name:str,enabled:bool):
        return self.runtime_call("autostart",{"name":name,"enabled":bool(enabled)})

    def runtime_stop(self):
        return self.runtime_call("runtime_stop")

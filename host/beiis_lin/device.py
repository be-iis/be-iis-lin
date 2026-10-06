from __future__ import annotations
from pathlib import Path
from .i2c_transport import I2CBytePipe
from .raw_repl import RawRepl
from .mboot import MbootClient

class LinHat:
    def __init__(self,bus:int=1,address:int=0x42):
        self.transport=I2CBytePipe(bus,address)
        self.repl=RawRepl(self.transport)

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

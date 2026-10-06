from __future__ import annotations
import time

CTRL_A=b"\x01"
CTRL_B=b"\x02"
CTRL_C=b"\x03"
CTRL_D=b"\x04"

class RawRepl:
    def __init__(self,transport):
        self.t=transport

    def enter(self):
        self.t.read_until_idle(idle_s=0.01,timeout=0.05)
        self.t.write(CTRL_C+CTRL_C+CTRL_A)
        data=self.t.read_until_idle(timeout=1.0)
        if b"raw REPL" not in data and b">" not in data:
            raise RuntimeError(f"failed to enter raw REPL: {data!r}")
        return data

    def exit(self):
        self.t.write(CTRL_B)

    def _submit(self,source:str,timeout:float=5.0):
        self.enter()
        self.t.write(source.encode("utf-8")+CTRL_D,timeout=timeout)
        ack=self.t.read(2,timeout=1.0)
        if ack!=b"OK":
            raise RuntimeError(f"raw REPL acknowledge failed: {ack!r}")

    def exec_detached(self,source:str,timeout:float=5.0):
        """Submit code and return after Raw REPL acknowledged it.

        Use this for commands which intentionally make the application transport
        disappear, such as machine.bootloader().  Waiting for stdout/stderr after
        the ACK would turn the expected disconnect into an I2C traceback.
        """
        self._submit(source,timeout=timeout)

    def exec(self,source:str,timeout:float=5.0)->tuple[bytes,bytes]:
        self._submit(source,timeout=timeout)

        stdout=bytearray()
        stderr=bytearray()
        current=stdout
        deadline=time.monotonic()+timeout
        separators=0

        # Read in blocks instead of issuing one I2C transaction per byte.
        # Raw REPL terminates stdout and stderr with one Ctrl-D each.
        while time.monotonic()<deadline and separators<2:
            count=self.t.in_waiting()
            if not count:
                time.sleep(self.t.poll_s)
                continue

            chunk=self.t.read(min(count,self.t.block_size),timeout=0.5)
            for value in chunk:
                if value==CTRL_D[0]:
                    separators+=1
                    if separators==1:
                        current=stderr
                    elif separators==2:
                        break
                else:
                    current.append(value)

        if separators<2:
            raise TimeoutError("raw REPL result timeout")
        return bytes(stdout),bytes(stderr)

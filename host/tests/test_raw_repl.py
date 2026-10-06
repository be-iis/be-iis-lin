import unittest
from beiis_lin.raw_repl import CTRL_A,CTRL_D,RawRepl

class RawReplTest(unittest.TestCase):
    def test_control_bytes(self):
        self.assertEqual(CTRL_A,bytes([1]))
        self.assertEqual(CTRL_D,bytes([4]))

    def test_exec_detached_stops_after_ack(self):
        class Transport:
            poll_s=0.001
            block_size=32

            def __init__(self):
                self.read_until_idle_calls=0
                self.writes=[]

            def read_until_idle(self,*args,**kwargs):
                self.read_until_idle_calls+=1
                if self.read_until_idle_calls==1:
                    return b""
                if self.read_until_idle_calls==2:
                    return b"raw REPL; CTRL-B to exit\r\n>"
                raise AssertionError("exec_detached polled after command ACK")

            def write(self,data,timeout=2.0):
                self.writes.append(bytes(data))
                return len(data)

            def read(self,n,timeout=2.0):
                self.assert_n=n
                return b"OK"

        t=Transport()
        r=RawRepl(t)
        r.exec_detached("import machine; machine.bootloader()")
        self.assertEqual(t.writes[-1],b"import machine; machine.bootloader()"+CTRL_D)
        self.assertEqual(t.read_until_idle_calls,2)

if __name__=="__main__":
    unittest.main()

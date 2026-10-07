# AI context: hardware test status

Verified on real hardware:

- I2C application protocol at 0x42
- Raw REPL host execution
- mboot ECHO / GETID / RESET
- full firmware update by I2C
- application hash verification and final MARKVALID flow
- LIN1 and LIN2 init at 19200 baud
- LIN transmit
- master request raw
- master request classic checksum
- master request enhanced checksum
- slave_set
- slave_clear
- LIN1 master to LIN2 slave end-to-end
- external LIN master pull-up on LIN1
- beiis-lind SOCK_SEQPACKET path end-to-end
- classic and enhanced request through beiis-lind
- application runtime management RPCs on real hardware
- application runtime echo data path through 2048-byte payloads
- application runtime stress test: 1000 echo packets
- application runtime lifecycle stress: repeated runtime_stop -> Raw REPL -> native reset -> autostart
- Unix SOCK_SEQPACKET hardware regression through beiis-lind
- runtime management and application data path through beiis-lind
- bidirectional LIN1/LIN2 request path through beiis-lind
- native mboot entry/reset and runtime restore through beiis-lind
- native APP_CONTROL recovery: STM32 reset and direct mboot entry
- all eight LIN status/activity LEDs and GPIO self-test
- STM32 PC6 -> isolation -> Pi GPIO6 IRQ hardware path

Not yet fully verified/implemented:

- remote LAN regression over SSH stream-local forwarding (test prepared, not yet run)

- LIN2 master pull-up direction as a separate release test
- alternate baud rates
- deliberately induced timeout
- deliberately induced checksum failure
- simultaneous dual-channel traffic
- passive RX/sniffer queue
- multiple slave IDs per channel
- slave receive of master-published data
- scheduler
- sleep/wakeup
- LIN diagnostic transport layer
- daemon use of GPIO6 IRQ for asynchronous events


## IP-over-LIN userspace bridge

Verified on real hardware:

- Linux `lin0` TUN layer-3 interface, NOARP
- IPv4 master address `10.42.1.1/24`
- node mapping `*.2 -> LIN node 2`
- TUN -> `beiis_lin.ip_bridge` -> Unix SOCK_SEQPACKET -> `beiis-lind`
- IPv4/ICMP packet fragmentation into 8-byte LIN payloads
- physical LIN1 master transmission for outbound fragments
- physical LIN2 slave response -> LIN1 master request for return fragments
- reassembly back into Linux IP stack
- `ping 10.42.1.2`: 3/3 replies, 0% loss, about 245 ms RTT

Current first-test limitation:

- the test bridge synthesizes the ICMP Echo Reply after the outbound IP packet is
  accepted; an independent LIN slave does not yet receive/reassemble the
  master-published IP fragments
- production slave-side RX/reassembly is the next milestone

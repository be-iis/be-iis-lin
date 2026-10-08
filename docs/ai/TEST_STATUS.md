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

## Universal runtime instance path

Verified on real hardware:

- 16-slot MicroPython runtime firmware
- standard 9-instance layout autostarts cleanly with no instance errors
- master runtime path: master_tx_query -> master_native -> master_rx_query
- slave runtime path: slave_tx_query -> slave_native -> slave_rx_query
- bidirectional physical LIN traffic through the universal runtime instances
- earlier IP-over-LIN loopback through the runtime instances: 3/3 ICMP replies,
  0% packet loss; that test synthesized the ICMP reply in Linux and returned
  its fragments over the physical LIN2 -> LIN1 response path

Prepared, not yet hardware verified:

- GPIO6-driven host wakeup in beiis-lind using Linux GPIO character ABI v2
- level-based PC6 host IRQ for application TX data and native LIN slave RX
- generic interrupt-driven slave receive of master-published LIN frames
- separate downlink/uplink frame identifiers per logical node
- real second Linux IPv4 endpoint in a network namespace
- real ICMP handled by the second Linux network stack
- TCP iperf3 server/client through the physical LIN bus

The network experiment remains isolated under examples/ip-over-lin. The STM32
and MicroPython runtime contain only generic LIN functionality.

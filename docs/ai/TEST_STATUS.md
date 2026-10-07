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
- native APP_CONTROL recovery: STM32 reset and direct mboot entry
- STM32 PC6 -> isolation -> Pi GPIO6 IRQ hardware path

Not yet fully verified/implemented:

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

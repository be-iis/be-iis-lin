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
- LIN2 master to LIN1 slave end-to-end
- multiple slave IDs (three configured IDs tested, selective removal)
- passive selected-ID sniffer with timestamps and checksum verification
- sniffer/master/slave exclusive mode enforcement
- mode change sniffer -> slave -> sniffer
- 64-bit 1 MHz TIC, 16-bit timer rollover, cross-channel timestamps
- 1000-frame master/slave test: 0 errors; 4465..4712 us measured duration
- FIFO overflow retained most recent 15 entries, order tested
- native SLAVE LED observed lit when configured
- external LIN master pull-up on LIN1
- beiis-lind SOCK_SEQPACKET path end-to-end
- classic and enhanced request through beiis-lind
- STM32 PC6 -> isolation -> Pi GPIO6 IRQ hardware path

Not yet fully verified/implemented:

- alternate baud rates
- deliberately induced timeout
- deliberately induced checksum failure
- truly simultaneous dual-channel traffic (independent sequential tests passed)
- malformed-frame and checksum-error injection for passive sniffer
- passive reception of unknown-length or unconfigured frames
- slave receive of master-published data
- scheduler
- sleep/wakeup
- LIN diagnostic transport layer
- daemon use of GPIO6 IRQ for asynchronous events

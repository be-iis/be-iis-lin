# BE-IIS LIN HAT MicroPython board

Target MCU: STM32G0B0KET6 (Cortex-M0+, 512 KiB flash, 144 KiB SRAM).

Hardware mapping from the final LIN HAT netlist:

| Function | STM32 pin |
|---|---|
| LIN1 TX | PB6 / USART1_TX |
| LIN1 RX | PB7 / USART1_RX |
| LIN1 enable | PA4 |
| LIN2 TX | PA2 / USART2_TX |
| LIN2 RX | PA3 / USART2_RX |
| LIN2 enable | PA8 |
| Pi I2C SCL (isolated) | PB8 / I2C1_SCL |
| Pi I2C SDA (isolated) | PB9 / I2C1_SDA |
| IRQ (isolated) | PC6 |
| SWDIO | PA13 |
| SWCLK | PA14 |

The board intentionally has no UART or USB REPL.  MicroPython stdin/stdout is
redirected by the BE-IIS user module to the I2C Raw-REPL byte pipe.

The I2C target address is fixed for the initial bring-up. Dynamic HAT++ variant
address selection is intentionally deferred.

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
| LIN1 RX LED_N | PA5 |
| LIN1 TX LED_N | PB1 |
| LIN1 slave LED_N | PA10 |
| LIN1 master LED_N | PA6 |
| LIN2 RX LED_N | PB3 |
| LIN2 TX LED_N | PB4 |
| LIN2 slave LED_N | PB5 |
| LIN2 master LED_N | PA15 |
| Pi I2C SCL (isolated) | PB8 / I2C1_SCL |
| Pi I2C SDA (isolated) | PB9 / I2C1_SDA |
| IRQ (isolated) | PC6 |
| SWDIO | PA13 |
| SWCLK | PA14 |

The board intentionally has no UART or USB REPL.  MicroPython stdin/stdout is
redirected by the BE-IIS user module to the I2C Raw-REPL byte pipe.

The I2C target address is fixed for the initial bring-up. Dynamic HAT++ variant
address selection is intentionally deferred.

All eight LIN LEDs are active-low. The slave LED stays on while a slave response is configured. The master LED is on during a master transaction. TX/RX LEDs indicate transmit/receive activity.

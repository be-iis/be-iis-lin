#pragma once

#define MICROPY_HW_BOARD_NAME       "BE-IIS LIN HAT"
#define MICROPY_HW_MCU_NAME         "STM32G0B0KET6"

#define MICROPY_HW_HAS_SWITCH       (0)
#define MICROPY_HW_HAS_FLASH        (1)
#define MICROPY_HW_ENABLE_RNG       (0)
#define MICROPY_HW_ENABLE_RTC       (1)
#define MICROPY_HW_ENABLE_DAC       (0)
#define MICROPY_HW_ENABLE_ADC       (0)

#if BUILDING_MBOOT
// Product bootloader is I2C-only. Keep FS defined so mboot's shared USB
// compile-time types remain available, but do not initialise USB or HSI48.
#define MBOOT_ENABLE_USB            (0)
#define MICROPY_HW_ENABLE_USB       (0)
#define MICROPY_HW_USB_FS           (1)
#define MICROPY_HW_USB_MAIN_DEV     (USB_PHY_FS_ID)
#else
#define MICROPY_HW_ENABLE_USB       (0)
#define MICROPY_HW_USB_FS           (0)
#endif

#define MICROPY_PY_PYB_LEGACY       (0)
#define MICROPY_HW_ENABLE_INTERNAL_FLASH_STORAGE (1)

#if !BUILDING_MBOOT
#define MICROPY_BOARD_EARLY_INIT    BEIIS_LIN_HAT_board_early_init
void BEIIS_LIN_HAT_board_early_init(void);

// Enter our own mboot image rather than the STM32 ROM bootloader.
// 0x70ad0000 is mboot's entry key; the low 7 bits select I2C address 0x42.
#define MICROPY_BOARD_ENTER_BOOTLOADER(n_args, args) \
    powerctrl_enter_bootloader(0x70ad0042, 0x08000000)

// Keep the transport/peripheral blocks owned by the BE-IIS firmware.
#define MICROPY_HW_UART_IS_RESERVED(uart_id) ((uart_id) == 1 || (uart_id) == 2)
#define MICROPY_HW_I2C_IS_RESERVED(i2c_id) ((i2c_id) == 1)
#endif

// STM32G0B0 internal HSI16 -> PLL -> 64 MHz system clock.
#define MICROPY_HW_CLK_USE_HSI      (1)
#define MICROPY_HW_FLASH_LATENCY    FLASH_LATENCY_2
#define MICROPY_HW_CLK_PLLM         (1)
#define MICROPY_HW_CLK_PLLN         (8)
#define MICROPY_HW_CLK_PLLP         (2)
#define MICROPY_HW_CLK_PLLQ         (2)
#define MICROPY_HW_CLK_PLLR         (2)

// LIN channel 1: TJA1021TK
#define MICROPY_HW_UART1_TX         (pin_B6)
#define MICROPY_HW_UART1_RX         (pin_B7)

// LIN channel 2: TJA1021TK
#define MICROPY_HW_UART2_TX         (pin_A2)
#define MICROPY_HW_UART2_RX         (pin_A3)

// Raspberry Pi application I2C, behind ISO1642.
#define MICROPY_HW_I2C1_SCL         (pin_B8)
#define MICROPY_HW_I2C1_SDA         (pin_B9)

// mboot uses the same physical I2C interface as the application.
#define MBOOT_I2C_PERIPH_ID         1
#define MBOOT_I2C_SCL               (pin_B8)
#define MBOOT_I2C_SDA               (pin_B9)
#define MBOOT_I2C_ALTFUNC           (6)
#define MBOOT_I2C_DEFAULT_ADDR      (0x42)
// Same proven 64-MHz target-mode timing as the application I2C transport.
#define MBOOT_I2C_TIMINGR           (0x10B17DB5)

#if !BUILDING_MBOOT
// No conventional UART REPL. The BE-IIS external module overrides the
// weak STM32 stdin/stdout hooks and exposes MicroPython Raw REPL via I2C.
#define MICROPY_HW_USB_MSC          (0)
#define MICROPY_HW_USB_HID          (0)
#endif

MCU_SERIES = g0
CMSIS_MCU = STM32G0B0xx

# Board-local AF table. Do not use the G0B1 table: it advertises
# peripherals such as TIM2 which are absent on STM32G0B0.
AF_FILE = $(BOARD_DIR)/stm32g0b0_af.csv

# With mboot the application starts after the protected 32-KiB bootloader.
ifeq ($(USE_MBOOT),1)
LD_FILES = $(BOARD_DIR)/stm32g0b0xe.ld boards/common_bl.ld
TEXT0_ADDR = 0x08008000
else
LD_FILES = $(BOARD_DIR)/stm32g0b0xe.ld boards/common_basic.ld
endif

LTO = 0
MICROPY_HW_ENABLE_ISR_UART_FLASH_FUNCS_IN_RAM = 1

# Keep asyncio, omit unrelated default DHT/OneWire frozen modules, and add the
# BE-IIS app runtime. This matters because the application flash region is 320 KiB.
FROZEN_MANIFEST = $(BOARD_DIR)/manifest.py
MICROPY_MANIFEST_BEIIS_DIR = $(BOARD_DIR)/frozen

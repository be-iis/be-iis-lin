#!/usr/bin/env python3
from pathlib import Path
import sys

arg = Path(sys.argv[1])

# Accept either the MicroPython repository root or the direct stm32_it.c path.
if arg.name == "stm32_it.c":
    root = arg.parents[2]
else:
    root = arg

def replace_once(path, old, new, marker=None):
    p = root / path
    s = p.read_text()
    if marker and marker in s:
        print(f"{path}: already patched")
        return
    if old not in s:
        raise SystemExit(f"ERROR: expected MicroPython v1.27.0 block not found in {path}")
    p.write_text(s.replace(old, new, 1))
    print(f"{path}: patched")

# USART IRQ layout: G0B0 has USART1, USART2 and combined USART3_4_5_6,
# but no LPUART1/2 IRQ combination used by G0B1/C1.
replace_once(
    "ports/stm32/stm32_it.c",
    """    IRQ_EXIT(USART3_4_5_6_LPUART1_IRQn);
}
#else
#error Unsupported processor
#endif
""",
    """    IRQ_EXIT(USART3_4_5_6_LPUART1_IRQn);
}
#elif defined(STM32G0B0xx)
void USART3_4_5_6_IRQHandler(void) {
    IRQ_ENTER(USART3_4_5_6_IRQn);
    uart_irq_handler(3);
    uart_irq_handler(4);
    uart_irq_handler(5);
    uart_irq_handler(6);
    IRQ_EXIT(USART3_4_5_6_IRQn);
}
#else
#error Unsupported processor
#endif
""",
    "void USART3_4_5_6_IRQHandler(void)"
)

# G0B0 has no TIM2. Guard the clock-enable case.
replace_once(
    "ports/stm32/timer.c",
    """        case 2:
            __HAL_RCC_TIM2_CLK_ENABLE();
            break;
""",
    """        #if defined(TIM2)
        case 2:
            __HAL_RCC_TIM2_CLK_ENABLE();
            break;
        #endif
""",
    "#if defined(TIM2)\n        case 2:"
)

# G0B0 has no TIM2. Guard its instance-table entry.
replace_once(
    "ports/stm32/timer.c",
    """    TIM_ENTRY(2, TIM2_IRQn),

    #if defined(TIM3)
""",
    """    #if defined(TIM2)
    TIM_ENTRY(2, TIM2_IRQn),
    #endif

    #if defined(TIM3)
""",
    "#if defined(TIM2)\n    TIM_ENTRY(2, TIM2_IRQn),"
)

# TIM3/TIM4 share one IRQ on G0B0 as they do on G0B1/C1.
replace_once(
    "ports/stm32/timer.c",
    """    #if defined(STM32G0B1xx) || defined(STM32G0C1xx)
    TIM_ENTRY(3, TIM3_TIM4_IRQn),
""",
    """    #if defined(STM32G0B0xx) || defined(STM32G0B1xx) || defined(STM32G0C1xx)
    TIM_ENTRY(3, TIM3_TIM4_IRQn),
""",
    "#if defined(STM32G0B0xx) || defined(STM32G0B1xx) || defined(STM32G0C1xx)\n    TIM_ENTRY(3"
)

replace_once(
    "ports/stm32/timer.c",
    """    #if defined(STM32G0B1xx) || defined(STM32G0C1xx)
    TIM_ENTRY(4, TIM3_TIM4_IRQn),
""",
    """    #if defined(STM32G0B0xx) || defined(STM32G0B1xx) || defined(STM32G0C1xx)
    TIM_ENTRY(4, TIM3_TIM4_IRQn),
""",
    "#if defined(STM32G0B0xx) || defined(STM32G0B1xx) || defined(STM32G0C1xx)\n    TIM_ENTRY(4"
)

# G0B0 exposes plain TIM6_IRQn/TIM7_IRQn. G0B1/C1 use combined IRQ names.
replace_once(
    "ports/stm32/timer.c",
    """    #elif defined(STM32G0)
    TIM_ENTRY(6, TIM6_DAC_LPTIM1_IRQn),
""",
    """    #elif defined(STM32G0B0xx)
    TIM_ENTRY(6, TIM6_IRQn),
    #elif defined(STM32G0)
    TIM_ENTRY(6, TIM6_DAC_LPTIM1_IRQn),
""",
    "#elif defined(STM32G0B0xx)\n    TIM_ENTRY(6, TIM6_IRQn),"
)

replace_once(
    "ports/stm32/timer.c",
    """    #if defined(STM32G0)
    TIM_ENTRY(7, TIM7_LPTIM2_IRQn),
""",
    """    #if defined(STM32G0B0xx)
    TIM_ENTRY(7, TIM7_IRQn),
    #elif defined(STM32G0)
    TIM_ENTRY(7, TIM7_LPTIM2_IRQn),
""",
    "#if defined(STM32G0B0xx)\n    TIM_ENTRY(7, TIM7_IRQn),"
)


# G0B0 has no TIM2. Guard the encoder-mode capability check too.
replace_once(
    "ports/stm32/timer.c",
    """                self->tim.Instance != TIM2
                #if defined(TIM3)
""",
    """                #if defined(TIM2)
                self->tim.Instance != TIM2
                &&
                #endif
                #if defined(TIM3)
                self->tim.Instance != TIM3
""",
    "#if defined(TIM2)\n                self->tim.Instance != TIM2"
)


# UART IRQ and LPUART differences on G0B0.
replace_once(
    "ports/stm32/uart.c",
    """            #if defined(STM32G0)
            irqn = USART2_LPUART2_IRQn;
            #else
            irqn = USART2_IRQn;
            #endif
""",
    """            #if defined(STM32G0B0xx)
            irqn = USART2_IRQn;
            #elif defined(STM32G0)
            irqn = USART2_LPUART2_IRQn;
            #else
            irqn = USART2_IRQn;
            #endif
""",
    "#if defined(STM32G0B0xx)\n            irqn = USART2_IRQn;"
)

replace_once(
    "ports/stm32/uart.c",
    """    #if defined(STM32G0) || defined(STM32G4) || defined(STM32H5) || defined(STM32H7) || defined(STM32N6) || defined(STM32WB)
    // Compute the smallest prescaler that will allow the given baudrate.
""",
    """    #if (defined(STM32G0) && !defined(STM32G0B0xx)) || defined(STM32G4) || defined(STM32H5) || defined(STM32H7) || defined(STM32N6) || defined(STM32WB)
    // Compute the smallest prescaler that will allow the given baudrate.
""",
    "#if (defined(STM32G0) && !defined(STM32G0B0xx))"
)

replace_once(
    "ports/stm32/uart.c",
    """        #if defined(STM32G0)
        HAL_NVIC_DisableIRQ(USART2_LPUART2_IRQn);
        #else
        HAL_NVIC_DisableIRQ(USART2_IRQn);
        #endif
""",
    """        #if defined(STM32G0B0xx)
        HAL_NVIC_DisableIRQ(USART2_IRQn);
        #elif defined(STM32G0)
        HAL_NVIC_DisableIRQ(USART2_LPUART2_IRQn);
        #else
        HAL_NVIC_DisableIRQ(USART2_IRQn);
        #endif
""",
    "#if defined(STM32G0B0xx)\n        HAL_NVIC_DisableIRQ(USART2_IRQn);"
)

replace_once(
    "ports/stm32/uart.c",
    """        #if defined(STM32G0)
        HAL_NVIC_DisableIRQ(USART3_4_5_6_LPUART1_IRQn);
        #elif !defined(STM32F0)
""",
    """        #if defined(STM32G0B0xx)
        HAL_NVIC_DisableIRQ(USART3_4_5_6_IRQn);
        #elif defined(STM32G0)
        HAL_NVIC_DisableIRQ(USART3_4_5_6_LPUART1_IRQn);
        #elif !defined(STM32F0)
""",
    "#if defined(STM32G0B0xx)\n        HAL_NVIC_DisableIRQ(USART3_4_5_6_IRQn);"
)


# EXTI differences on G0B0.
replace_once(
    "ports/stm32/extint.c",
    """    #if defined(STM32L0)
    PVD_IRQn,
    #else
    PVD_VDDIO2_IRQn,
    #endif
    #if defined(STM32G0)
    ADC1_COMP_IRQn,
    ADC1_COMP_IRQn,
    RTC_TAMP_IRQn,
    0, // COMP3
    RTC_TAMP_IRQn,// 21
""",
    """    #if defined(STM32L0)
    PVD_IRQn,
    #elif defined(STM32G0B0xx)
    0, // no dedicated PVD IRQ on G0B0
    #else
    PVD_VDDIO2_IRQn,
    #endif
    #if defined(STM32G0B0xx)
    ADC1_IRQn,
    ADC1_IRQn,
    RTC_TAMP_IRQn,
    0, // COMP3
    RTC_TAMP_IRQn,// 21
    #elif defined(STM32G0)
    ADC1_COMP_IRQn,
    ADC1_COMP_IRQn,
    RTC_TAMP_IRQn,
    0, // COMP3
    RTC_TAMP_IRQn,// 21
""",
    "#elif defined(STM32G0B0xx)\n    0, // no dedicated PVD IRQ on G0B0"
)

replace_once(
    "ports/stm32/extint.c",
    """    #if defined(STM32G0) || defined(STM32G4) || defined(STM32H5) || defined(STM32L4) || defined(STM32N6) || defined(STM32WB) || defined(STM32WL)
    mp_printf(print, "EXTI_IMR1   %08x\\n", (unsigned int)EXTI->IMR1);
""",
    """    #if defined(STM32G0B0xx)
    mp_printf(print, "EXTI_IMR1   %08x\\n", (unsigned int)EXTI->IMR1);
    mp_printf(print, "EXTI_IMR2   %08x\\n", (unsigned int)EXTI->IMR2);
    mp_printf(print, "EXTI_EMR1   %08x\\n", (unsigned int)EXTI->EMR1);
    mp_printf(print, "EXTI_EMR2   %08x\\n", (unsigned int)EXTI->EMR2);
    mp_printf(print, "EXTI_RTSR1  %08x\\n", (unsigned int)EXTI->RTSR1);
    mp_printf(print, "EXTI_FTSR1  %08x\\n", (unsigned int)EXTI->FTSR1);
    mp_printf(print, "EXTI_SWIER1 %08x\\n", (unsigned int)EXTI->SWIER1);
    mp_printf(print, "EXTI_RPR1   %08x\\n", (unsigned int)EXTI->RPR1);
    mp_printf(print, "EXTI_FPR1   %08x\\n", (unsigned int)EXTI->FPR1);
    #elif defined(STM32G0) || defined(STM32G4) || defined(STM32H5) || defined(STM32L4) || defined(STM32N6) || defined(STM32WB) || defined(STM32WL)
    mp_printf(print, "EXTI_IMR1   %08x\\n", (unsigned int)EXTI->IMR1);
""",
    "#if defined(STM32G0B0xx)\n    mp_printf(print, \"EXTI_IMR1"
)


# FLASH_FLAG_RDERR exists only when FLASH_PCROP_SUPPORT is enabled.
p = root / "ports/stm32/flash.c"
_flash = p.read_text()
if "#define FLASH_FLAG_SR_RDERR" in _flash:
    print("ports/stm32/flash.c: already patched")
else:
    _needle = "#elif defined(STM32G0)\n\n// These are not defined on the CMSIS header\n"
    if _needle not in _flash:
        raise SystemExit("ERROR: STM32G0 flash block not found in MicroPython v1.27.0")
    _flash = _flash.replace(
        _needle,
        _needle + """#if defined(FLASH_FLAG_RDERR)
#define FLASH_FLAG_SR_RDERR       FLASH_FLAG_RDERR
#else
#define FLASH_FLAG_SR_RDERR       0
#endif
""",
        1,
    )
    if "FLASH_FLAG_MISERR | FLASH_FLAG_FASTERR | FLASH_FLAG_RDERR |" not in _flash:
        raise SystemExit("ERROR: FLASH_FLAG_RDERR use not found in MicroPython v1.27.0")
    _flash = _flash.replace(
        "FLASH_FLAG_MISERR | FLASH_FLAG_FASTERR | FLASH_FLAG_RDERR |",
        "FLASH_FLAG_MISERR | FLASH_FLAG_FASTERR | FLASH_FLAG_SR_RDERR |",
        1,
    )
    p.write_text(_flash)
    print("ports/stm32/flash.c: patched")


# Route USART1/2 IRQs to the BE-IIS LIN handler on STM32G0B0.
replace_once(
    "ports/stm32/stm32_it.c",
    """void USART1_IRQHandler(void) {
    IRQ_ENTER(USART1_IRQn);
    uart_irq_handler(1);
    IRQ_EXIT(USART1_IRQn);
}
""",
    """void USART1_IRQHandler(void) {
    IRQ_ENTER(USART1_IRQn);
    #if defined(STM32G0B0xx) && defined(BEIIS_LIN_MODULE_ENABLED)
    extern void beiis_lin_uart_irq(uint8_t channel);
    beiis_lin_uart_irq(1);
    #else
    uart_irq_handler(1);
    #endif
    IRQ_EXIT(USART1_IRQn);
}
""",
    "beiis_lin_uart_irq(1);"
)

replace_once(
    "ports/stm32/stm32_it.c",
    """void USART2_IRQHandler(void) {
    IRQ_ENTER(USART2_IRQn);
    uart_irq_handler(2);
    IRQ_EXIT(USART2_IRQn);
}
""",
    """void USART2_IRQHandler(void) {
    IRQ_ENTER(USART2_IRQn);
    #if defined(STM32G0B0xx) && defined(BEIIS_LIN_MODULE_ENABLED)
    extern void beiis_lin_uart_irq(uint8_t channel);
    beiis_lin_uart_irq(2);
    #else
    uart_irq_handler(2);
    #endif
    IRQ_EXIT(USART2_IRQn);
}
""",
    "beiis_lin_uart_irq(2);"
)


# mboot/i2cslave: G0 uses the same modern I2C register interface as F7/H7/L4/WB.
replace_once(
    "ports/stm32/i2cslave.h",
    """#if defined(STM32F4) || defined(STM32F7) || defined(STM32H7) || defined(STM32L4) || defined(STM32WB)
""",
    """#if defined(STM32F4) || defined(STM32F7) || defined(STM32G0) || defined(STM32H7) || defined(STM32L4) || defined(STM32WB)
""",
    "defined(STM32F7) || defined(STM32G0) || defined(STM32H7)"
)

replace_once(
    "ports/stm32/i2cslave.c",
    """#elif defined(STM32F7) || defined(STM32H7) || defined(STM32L4) || defined(STM32WB)
""",
    """#elif defined(STM32F7) || defined(STM32G0) || defined(STM32H7) || defined(STM32L4) || defined(STM32WB)
""",
    "#elif defined(STM32F7) || defined(STM32G0) || defined(STM32H7)"
)

# mboot expects split I2C event IRQ names, while STM32G0 has one combined IRQ.
replace_once(
    "ports/stm32/mboot/main.c",
    """#define MBOOT_I2Cx EVAL_PASTE2(I2C, MBOOT_I2C_PERIPH_ID)
#define I2Cx_EV_IRQn EVAL_PASTE3(I2C, MBOOT_I2C_PERIPH_ID, _EV_IRQn)
#define I2Cx_EV_IRQHandler EVAL_PASTE3(I2C, MBOOT_I2C_PERIPH_ID, _EV_IRQHandler)
""",
    """#define MBOOT_I2Cx EVAL_PASTE2(I2C, MBOOT_I2C_PERIPH_ID)
#if defined(STM32G0)
#define I2Cx_EV_IRQn EVAL_PASTE3(I2C, MBOOT_I2C_PERIPH_ID, _IRQn)
#define I2Cx_EV_IRQHandler EVAL_PASTE3(I2C, MBOOT_I2C_PERIPH_ID, _IRQHandler)
#else
#define I2Cx_EV_IRQn EVAL_PASTE3(I2C, MBOOT_I2C_PERIPH_ID, _EV_IRQn)
#define I2Cx_EV_IRQHandler EVAL_PASTE3(I2C, MBOOT_I2C_PERIPH_ID, _EV_IRQHandler)
#endif
""",
    "#if defined(STM32G0)\n#define I2Cx_EV_IRQn EVAL_PASTE3"
)

# Allow a board-specific default I2C address. Upstream defaults to 0x23.
replace_once(
    "ports/stm32/mboot/main.c",
    """#if defined(MBOOT_I2C_SCL)

#define PASTE2(a, b) a##b
""",
    """#if defined(MBOOT_I2C_SCL)

#ifndef MBOOT_I2C_DEFAULT_ADDR
#define MBOOT_I2C_DEFAULT_ADDR (0x23)
#endif

#define PASTE2(a, b) a##b
""",
    "#define MBOOT_I2C_DEFAULT_ADDR"
)

replace_once(
    "ports/stm32/mboot/main.c",
    """        initial_r0 = 0x23; // Default I2C address
""",
    """        initial_r0 = MBOOT_I2C_DEFAULT_ADDR;
""",
    "initial_r0 = MBOOT_I2C_DEFAULT_ADDR;"
)

# mboot's pin generator prepends ../ to AF_FILE. Our board uses an absolute AF path.
mp = root / "ports/stm32/mboot/Makefile"
_ms = mp.read_text()

if "MBOOT_AF_FILE =" not in _ms:
    _anchor = "GEN_PINS_AF_DEFS = $(HEADER_BUILD)/pins_af_defs.h\n"
    if _anchor not in _ms:
        raise SystemExit("ERROR: GEN_PINS_AF_DEFS anchor not found in ports/stm32/mboot/Makefile")
    _ms = _ms.replace(
        _anchor,
        _anchor + """\
ifeq ($(filter /%,$(AF_FILE)),)
MBOOT_AF_FILE = ../$(AF_FILE)
else
MBOOT_AF_FILE = $(AF_FILE)
endif
""",
        1,
    )
    print("ports/stm32/mboot/Makefile: AF path helper patched")
else:
    print("ports/stm32/mboot/Makefile: AF path helper already patched")

_old_dep = "$(GEN_PINS_AF_DEFS): $(BOARD_PINS) $(MAKE_PINS) ../$(AF_FILE) $(PREFIX_FILE) | $(HEADER_BUILD)"
_new_dep = "$(GEN_PINS_AF_DEFS): $(BOARD_PINS) $(MAKE_PINS) $(MBOOT_AF_FILE) $(PREFIX_FILE) | $(HEADER_BUILD)"
if _old_dep in _ms:
    _ms = _ms.replace(_old_dep, _new_dep, 1)
elif _new_dep not in _ms:
    raise SystemExit("ERROR: mboot pin-generator dependency line not found")

_old_arg = "--af-csv ../$(AF_FILE)"
_new_arg = "--af-csv $(MBOOT_AF_FILE)"
if _old_arg in _ms:
    _ms = _ms.replace(_old_arg, _new_arg, 1)
elif _new_arg not in _ms:
    raise SystemExit("ERROR: mboot --af-csv argument not found")

mp.write_text(_ms)
print("ports/stm32/mboot/Makefile: patched")


# mboot: Cortex-M0+ has no NVIC priority grouping; use a raw priority value.
mp = root / "ports/stm32/mboot/main.c"
_ms = mp.read_text()
_marker = "#if __CORTEX_M == 0\n#define IRQ_PRI_I2C (1)"
if _marker in _ms:
    print("ports/stm32/mboot/main.c: IRQ priority already patched")
else:
    _old = "#define IRQ_PRI_I2C (NVIC_EncodePriority(NVIC_PRIORITYGROUP_4, 1, 0))"
    if _old not in _ms:
        raise SystemExit("ERROR: mboot IRQ_PRI_I2C definition not found")
    _new = """#if __CORTEX_M == 0
#define IRQ_PRI_I2C (1)
#else
#define IRQ_PRI_I2C (NVIC_EncodePriority(NVIC_PRIORITYGROUP_4, 1, 0))
#endif"""
    _ms = _ms.replace(_old, _new, 1)
    mp.write_text(_ms)
    print("ports/stm32/mboot/main.c: IRQ priority patched")


# mboot: allow an I2C-only build without starting USB.
mp = root / "ports/stm32/mboot/main.c"
_ms = mp.read_text()

if "#ifndef MBOOT_ENABLE_USB" not in _ms:
    _anchor = "// Work out which USB device to use for the USB DFU interface\n"
    if _anchor not in _ms:
        raise SystemExit("ERROR: mboot USB-device anchor not found")
    _ms = _ms.replace(
        _anchor,
        """#ifndef MBOOT_ENABLE_USB
#define MBOOT_ENABLE_USB (1)
#endif

#if MBOOT_ENABLE_USB
""" + _anchor,
        1,
    )
    _end = """#endif

// These bits are used to detect valid application firmware at APPLICATION_ADDR
"""
    if _end not in _ms:
        raise SystemExit("ERROR: mboot USB-device block end not found")
    _ms = _ms.replace(
        _end,
        """#endif
#endif // MBOOT_ENABLE_USB

// These bits are used to detect valid application firmware at APPLICATION_ADDR
""",
        1,
    )

if "#if MBOOT_ENABLE_USB\n// USB" not in _ms:
    _usb = """/******************************************************************************/
 // USB
"""
    # Upstream has no leading space before // USB.
    _usb = _usb.replace(" // USB", "// USB")
    if _usb not in _ms:
        raise SystemExit("ERROR: mboot USB section start not found")
    _ms = _ms.replace(
        _usb,
        """/******************************************************************************/
#if MBOOT_ENABLE_USB
// USB
""",
        1,
    )
    _main = """/******************************************************************************/
 // main
""".replace(" // main", "// main")
    if _main not in _ms:
        raise SystemExit("ERROR: mboot main section start not found")
    _ms = _ms.replace(
        _main,
        """#endif // MBOOT_ENABLE_USB

/******************************************************************************/
 // main
""".replace(" // main", "// main"),
        1,
    )

_init = """    pyb_usbdd_init(&pyb_usbdd, pyb_usbdd_detect_port());
    pyb_usbdd_start(&pyb_usbdd);
"""
if _init in _ms:
    _ms = _ms.replace(
        _init,
        """    #if MBOOT_ENABLE_USB
    pyb_usbdd_init(&pyb_usbdd, pyb_usbdd_detect_port());
    pyb_usbdd_start(&pyb_usbdd);
    #endif
""",
        1,
    )

_shutdown = """    pyb_usbdd_shutdown();
"""
if _shutdown in _ms:
    _ms = _ms.replace(
        _shutdown,
        """    #if MBOOT_ENABLE_USB
    pyb_usbdd_shutdown();
    #endif
""",
        1,
    )

_irq_guard = "#if !USE_USB_POLLING\n\n#if defined(STM32G0)"
if _irq_guard in _ms:
    _ms = _ms.replace(
        _irq_guard,
        "#if MBOOT_ENABLE_USB && !USE_USB_POLLING\n\n#if defined(STM32G0)",
        1,
    )

mp.write_text(_ms)
print("ports/stm32/mboot/main.c: I2C-only USB guard patched")


# mboot: DFU request handlers are USB-only. Keep dfu_init for shared I2C state.
mp = root / "ports/stm32/mboot/main.c"
_ms = mp.read_text()

if "#if MBOOT_ENABLE_USB\nstatic int dfu_process_dnload" not in _ms:
    _start = "static int dfu_process_dnload(void) {"
    if _start not in _ms:
        raise SystemExit("ERROR: mboot dfu_process_dnload start not found")
    _ms = _ms.replace(_start, "#if MBOOT_ENABLE_USB\n" + _start, 1)

    _end = """static int dfu_handle_tx(int cmd, int arg, int len, uint8_t *buf, int max_len) {"""
    _pos = _ms.find(_end)
    if _pos < 0:
        raise SystemExit("ERROR: mboot dfu_handle_tx start not found")
    _usb_section = """/******************************************************************************/
#if MBOOT_ENABLE_USB
// USB
"""
    _usb_pos = _ms.find(_usb_section, _pos)
    if _usb_pos < 0:
        raise SystemExit("ERROR: guarded mboot USB section not found after DFU helpers")
    _ms = _ms[:_usb_pos] + "#endif // MBOOT_ENABLE_USB (DFU handlers)\n\n" + _ms[_usb_pos:]

    mp.write_text(_ms)
    print("ports/stm32/mboot/main.c: USB-only DFU handlers guarded")
else:
    print("ports/stm32/mboot/main.c: USB-only DFU handlers already guarded")


# mboot/i2cslave: initialise STM32G0 TIMINGR before enabling the peripheral.
# The application already uses this timing successfully on the same PB8/PB9 bus.
mp = root / "ports/stm32/i2cslave.c"
_ms = mp.read_text()
_marker = "i2c->TIMINGR = MBOOT_I2C_TIMINGR;"
if _marker in _ms:
    print("ports/stm32/i2cslave.c: STM32G0 timing already patched")
else:
    _needle = """void i2c_slave_init_helper(i2c_slave_t *i2c, int addr) {
    i2c->CR1 = I2C_CR1_STOPIE | I2C_CR1_ADDRIE | I2C_CR1_RXIE | I2C_CR1_TXIE;
    i2c->CR2 = 0;
"""
    if _needle not in _ms:
        raise SystemExit("ERROR: modern i2c_slave_init_helper block not found")
    _replacement = """void i2c_slave_init_helper(i2c_slave_t *i2c, int addr) {
    i2c->CR1 = 0;
    i2c->CR2 = 0;
    #if defined(STM32G0) && defined(MBOOT_I2C_TIMINGR)
    i2c->TIMINGR = MBOOT_I2C_TIMINGR;
    i2c->TIMEOUTR = 0;
    #endif
    i2c->CR1 = I2C_CR1_STOPIE | I2C_CR1_ADDRIE | I2C_CR1_RXIE | I2C_CR1_TXIE;
"""
    _ms = _ms.replace(_needle, _replacement, 1)
    mp.write_text(_ms)
    print("ports/stm32/i2cslave.c: STM32G0 timing patched")


# STM32G0B0 mboot I2C WRITE passes payload as cmd_buf + 1, which is unaligned.
# Avoid direct uint64_t/uint32_t dereferences on Cortex-M0+.
fp = root / "ports/stm32/flash.c"
_fs = fp.read_text()

_old = """        uint64_t val = *(uint64_t *)src;
"""
_new = """        uint64_t val;
        #if defined(STM32G0B0xx)
        memcpy(&val, src, sizeof(val));
        #else
        val = *(uint64_t *)src;
        #endif
"""
if _old in _fs:
    _fs = _fs.replace(_old, _new, 1)
elif "memcpy(&val, src, sizeof(val));" not in _fs:
    raise SystemExit("ERROR: STM32 flash uint64 source load not found")

_old = """        val = (val & 0xffffffff00000000uL) | (*src);
"""
_new = """        uint32_t low_word;
        #if defined(STM32G0B0xx)
        memcpy(&low_word, src, sizeof(low_word));
        #else
        low_word = *src;
        #endif
        val = (val & 0xffffffff00000000uL) | low_word;
"""
if _old in _fs:
    _fs = _fs.replace(_old, _new, 1)
elif "uint32_t low_word;" not in _fs:
    raise SystemExit("ERROR: STM32 flash odd-word source load not found")

fp.write_text(_fs)
print("ports/stm32/flash.c: STM32G0B0 unaligned flash source patched")


# STM32G0B0 cannot re-program the application vector doubleword because flash
# is programmed 64 bits + ECC at a time.  For this MCU MARKVALID receives the
# original 8-byte vector and programs it exactly once into an erased doubleword.
mp = root / "ports/stm32/mboot/main.c"
_ms = mp.read_text()
_old = """    } else if (buf[0] == I2C_CMD_MARKVALID && len == 0) {
        uint32_t buf;
        buf = *(volatile uint32_t *)APPLICATION_ADDR;
        if ((buf & APP_VALIDITY_BITS) != APP_VALIDITY_BITS) {
            len = -1;
        } else {
            buf &= ~APP_VALIDITY_BITS;
            int ret = do_write(APPLICATION_ADDR, (void *)&buf, 4, false);
            if (ret < 0) {
                len = ret;
            } else {
                buf = *(volatile uint32_t *)APPLICATION_ADDR;
                if ((buf & APP_VALIDITY_BITS) != 0) {
                    len = -2;
                } else {
                    len = 0;
                }
            }
        }
"""
_new = """    #if defined(STM32G0B0xx)
    } else if (buf[0] == I2C_CMD_MARKVALID && len == 8) {
        // G0 flash doublewords carry ECC and cannot be programmed twice.
        // Keep the vector doubleword erased during the update, then program
        // the real MSP + reset vector exactly once as the commit operation.
        uint64_t current;
        memcpy(&current, (const void *)APPLICATION_ADDR, sizeof(current));
        if (current != UINT64_MAX) {
            len = -1;
        } else {
            int ret = do_write(APPLICATION_ADDR, buf + 1, 8, false);
            if (ret < 0) {
                len = ret;
            } else {
                uint32_t msp = *(volatile uint32_t *)APPLICATION_ADDR;
                len = (msp & APP_VALIDITY_BITS) == 0 ? 0 : -2;
            }
        }
    #else
    } else if (buf[0] == I2C_CMD_MARKVALID && len == 0) {
        uint32_t buf;
        buf = *(volatile uint32_t *)APPLICATION_ADDR;
        if ((buf & APP_VALIDITY_BITS) != APP_VALIDITY_BITS) {
            len = -1;
        } else {
            buf &= ~APP_VALIDITY_BITS;
            int ret = do_write(APPLICATION_ADDR, (void *)&buf, 4, false);
            if (ret < 0) {
                len = ret;
            } else {
                buf = *(volatile uint32_t *)APPLICATION_ADDR;
                if ((buf & APP_VALIDITY_BITS) != 0) {
                    len = -2;
                } else {
                    len = 0;
                }
            }
        }
    #endif
"""
if _old in _ms:
    _ms = _ms.replace(_old, _new, 1)
elif "G0 flash doublewords carry ECC" not in _ms:
    raise SystemExit("ERROR: mboot MARKVALID block not found")

mp.write_text(_ms)
print("ports/stm32/mboot/main.c: STM32G0B0 one-shot MARKVALID patched")

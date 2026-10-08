#include "py/mphal.h"
#include "repl_i2c.h"

#if BEIIS_I2C_REPL_ENABLED

/*
 * The STM32 MicroPython port declares these functions weak.
 * Strong replacements turn the I2C FIFO into the MicroPython console stream.
 */
int mp_hal_stdin_rx_chr(void) {
    for(;;) {
        int c=beiis_repl_stdin_get();
        if(c>=0) return c;
        __WFI();
    }
}

mp_uint_t mp_hal_stdout_tx_strn(const char *str,size_t len) {
    size_t done=0;
    while(done<len) {
        done+=beiis_repl_stdout_write((const uint8_t*)str+done,len-done);
        if(done<len) __WFI();
    }
    return len;
}
#endif

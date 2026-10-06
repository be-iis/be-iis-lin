#pragma once
#include <stddef.h>
#include <stdint.h>
#include "repl_i2c.h"

/*
 * Contract for the board's I2C target interrupt/backend.
 *
 * Write transaction:
 *   first byte = register
 *   RX_DATA payload -> beiis_repl_host_write()
 *   CONTROL payload -> beiis_repl_control()
 *
 * Read transaction:
 *   scalar registers -> beiis_repl_reg_read_u8()
 *   TX_DATA -> beiis_repl_host_read()
 *
 * Keeping this boundary independent of STM32 family lets the same protocol
 * run on F0/G0/F4/H5/U5 etc. without tying the middleware to one HAL.
 */

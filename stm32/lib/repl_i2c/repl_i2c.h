#pragma once
#include <stddef.h>
#include <stdint.h>

#define BEIIS_REPL_PROTOCOL_VERSION 1
#define BEIIS_REPL_FIFO_SIZE 512

enum {
    BEIIS_REG_STATUS=0x00,
    BEIIS_REG_RX_FREE=0x01,
    BEIIS_REG_TX_COUNT=0x02,
    BEIIS_REG_RX_DATA=0x10,
    BEIIS_REG_TX_DATA=0x20,
    BEIIS_REG_CONTROL=0x30,
    BEIIS_REG_VERSION=0x31,
};

void beiis_repl_i2c_init(void);
size_t beiis_repl_host_write(const uint8_t *src,size_t len);
size_t beiis_repl_host_read(uint8_t *dst,size_t len);
int beiis_repl_stdin_get(void);
size_t beiis_repl_stdout_write(const uint8_t *src,size_t len);
uint8_t beiis_repl_reg_read_u8(uint8_t reg);
void beiis_repl_control(uint8_t value);

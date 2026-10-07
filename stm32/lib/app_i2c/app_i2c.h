#pragma once

#include <stddef.h>
#include <stdint.h>

#define BEIIS_APP_PROTOCOL_VERSION 2
#define BEIIS_APP_FIFO_SIZE 4096
#define BEIIS_APP_MAX_PAYLOAD 2048
#define BEIIS_APP_USER_CHANNELS 32
#define BEIIS_APP_MAX_INSTANCES 8
#define BEIIS_APP_MGMT_CHANNEL 0xff

enum {
    BEIIS_REG_APP_RX_FREE = 0x03,
    BEIIS_REG_APP_TX_COUNT = 0x04,
    BEIIS_REG_APP_STATUS = 0x05,
    BEIIS_REG_APP_RX_DATA = 0x11,
    BEIIS_REG_APP_TX_DATA = 0x21,
    BEIIS_REG_APP_VERSION = 0x32,
    BEIIS_REG_APP_CHANNELS = 0x33,
    BEIIS_REG_APP_CONTROL = 0x34,
    BEIIS_REG_APP_MAX_PAYLOAD_LO = 0x35,
    BEIIS_REG_APP_MAX_PAYLOAD_HI = 0x36,
    BEIIS_REG_APP_ACTIVE_INSTANCE = 0x37,
};

void beiis_app_i2c_init(void);
size_t beiis_app_host_write(const uint8_t *src, size_t len);
size_t beiis_app_host_read(uint8_t *dst, size_t len);
uint8_t beiis_app_reg_read_u8(uint8_t reg);
void beiis_app_control(uint8_t value);
uint8_t beiis_app_active_instance(void);
int beiis_app_set_active_instance(uint8_t instance);

/*
 * Pi -> STM frame: channel:u8, length:u16-le, payload.
 * STM -> Pi frame: instance:u8, channel:u8, length:u16-le, payload.
 *
 * The inbound owner is selected by BEIIS_REG_APP_ACTIVE_INSTANCE.  Outbound
 * frames carry their source slot so active and TAP instances can both report
 * data to the Pi without ambiguity.  instance=0xff is reserved for management.
 */
int beiis_app_rx_peek(uint8_t *channel, size_t *payload_len);
int beiis_app_recv(uint8_t *channel, uint8_t *dst, size_t cap, size_t *payload_len);
int beiis_app_try_send(uint8_t instance, uint8_t channel, const uint8_t *src, size_t len);

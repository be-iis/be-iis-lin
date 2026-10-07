#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

typedef enum {
    LIN_OK=0,
    LIN_ERR_ARG=-1,
    LIN_ERR_IO=-2,
    LIN_ERR_TIMEOUT=-3,
    LIN_ERR_CHECKSUM=-4,
} lin_result_t;

typedef enum {
    LIN_CHECKSUM_CLASSIC=0,
    LIN_CHECKSUM_ENHANCED=1,
} lin_checksum_mode_t;

typedef struct {
    uint8_t id;
    uint8_t len;
    uint8_t data[8];
} lin_frame_t;

typedef enum {
    LIN_LED_RX=0,
    LIN_LED_TX=1,
    LIN_LED_SLAVE=2,
    LIN_LED_MASTER=3,
} lin_led_t;

uint8_t lin_make_pid(uint8_t id);
bool lin_pid_valid(uint8_t pid);
uint8_t lin_checksum(uint8_t pid,const uint8_t *data,size_t len,lin_checksum_mode_t mode);

int lin_port_set_baudrate(uint8_t channel,uint32_t baudrate);
int lin_port_send_break(uint8_t channel);
int lin_port_tx(uint8_t channel,const uint8_t *data,size_t len,uint32_t timeout_ms);
int lin_port_rx(uint8_t channel,uint8_t *data,size_t len,uint32_t timeout_ms);
int lin_port_slave_set(uint8_t channel,uint8_t id,const uint8_t *data,size_t len,lin_checksum_mode_t mode);
int lin_port_slave_clear(uint8_t channel);
void lin_port_led_set(uint8_t channel,lin_led_t led,bool on);
void lin_port_led_set_mask(uint8_t mask);
uint8_t lin_port_led_get_mask(void);

lin_result_t lin_init(uint8_t channel,uint32_t baudrate);
lin_result_t lin_master_send(uint8_t channel,const lin_frame_t *frame,lin_checksum_mode_t mode,uint32_t timeout_ms);
lin_result_t lin_master_request(uint8_t channel,uint8_t id,uint8_t len,lin_checksum_mode_t mode,lin_frame_t *out,uint32_t timeout_ms);
lin_result_t lin_master_request_raw(uint8_t channel,uint8_t id,uint8_t *buf,size_t len,uint32_t timeout_ms);
lin_result_t lin_slave_set(uint8_t channel,uint8_t id,const uint8_t *data,size_t len,lin_checksum_mode_t mode);
lin_result_t lin_slave_clear(uint8_t channel);

void lin_led_set_mask(uint8_t mask);
uint8_t lin_led_get_mask(void);

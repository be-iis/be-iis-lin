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
    LIN_ERR_BUSY=-5,
} lin_result_t;

typedef enum {
    LIN_CHECKSUM_CLASSIC=0,
    LIN_CHECKSUM_ENHANCED=1,
} lin_checksum_mode_t;

typedef struct {
    uint8_t id;
    uint8_t len;
    uint8_t data[8];
    uint64_t tic_start;
    uint32_t tic_duration;
    uint8_t status;
} lin_frame_t;

uint8_t lin_make_pid(uint8_t id);
bool lin_pid_valid(uint8_t pid);
uint8_t lin_checksum(uint8_t pid,const uint8_t *data,size_t len,lin_checksum_mode_t mode);

int lin_port_set_baudrate(uint8_t channel,uint32_t baudrate);
int lin_port_send_break(uint8_t channel);
int lin_port_tx(uint8_t channel,const uint8_t *data,size_t len,uint32_t timeout_ms);
int lin_port_rx(uint8_t channel,uint8_t *data,size_t len,uint32_t timeout_ms);
int lin_port_slave_set(uint8_t channel,uint8_t id,const uint8_t *data,size_t len,lin_checksum_mode_t mode);
int lin_port_slave_clear(uint8_t channel);
int lin_port_slave_remove(uint8_t channel,uint8_t id);
int lin_port_sniffer_set(uint8_t channel,uint8_t id,uint8_t len,lin_checksum_mode_t mode);
int lin_port_sniffer_clear(uint8_t channel);
int lin_port_sniffer_enable(uint8_t channel,bool enable);
bool lin_port_master_allowed(uint8_t channel);

lin_result_t lin_init(uint8_t channel,uint32_t baudrate);
lin_result_t lin_master_send(uint8_t channel,const lin_frame_t *frame,lin_checksum_mode_t mode,uint32_t timeout_ms);
lin_result_t lin_master_request(uint8_t channel,uint8_t id,uint8_t len,lin_checksum_mode_t mode,lin_frame_t *out,uint32_t timeout_ms);
lin_result_t lin_master_request_raw(uint8_t channel,uint8_t id,uint8_t *buf,size_t len,uint32_t timeout_ms);
lin_result_t lin_slave_set(uint8_t channel,uint8_t id,const uint8_t *data,size_t len,lin_checksum_mode_t mode);
lin_result_t lin_slave_clear(uint8_t channel);
lin_result_t lin_slave_remove(uint8_t channel,uint8_t id);
lin_result_t lin_sniffer_set(uint8_t channel,uint8_t id,uint8_t len,lin_checksum_mode_t mode);
lin_result_t lin_sniffer_clear(uint8_t channel);
lin_result_t lin_sniffer_enable(uint8_t channel,bool enable);

// Shared 1 MHz monotonic clock and per-channel completed-frame FIFO.
uint64_t lin_port_tic_now(void);
void lin_port_frame_push(uint8_t channel, const lin_frame_t *frame);
bool lin_port_frame_pop(uint8_t channel, lin_frame_t *frame);

// Built-in activity LEDs (active low), driven only by the native firmware.
void lin_port_led_master(uint8_t channel);
void lin_port_led_tx(uint8_t channel);
void lin_port_led_rx(uint8_t channel);
void lin_port_led_slave(uint8_t channel, bool enabled);

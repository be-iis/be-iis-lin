#include "lin.h"

__attribute__((weak)) int lin_port_set_baudrate(uint8_t channel,uint32_t baudrate) {
    (void)channel; (void)baudrate; return -1;
}
__attribute__((weak)) int lin_port_send_break(uint8_t channel) {
    (void)channel; return -1;
}
__attribute__((weak)) int lin_port_tx(uint8_t channel,const uint8_t *data,size_t len,uint32_t timeout_ms) {
    (void)channel; (void)data; (void)len; (void)timeout_ms; return -1;
}
__attribute__((weak)) int lin_port_rx(uint8_t channel,uint8_t *data,size_t len,uint32_t timeout_ms) {
    (void)channel; (void)data; (void)len; (void)timeout_ms; return -1;
}
__attribute__((weak)) int lin_port_slave_set(uint8_t channel,uint8_t id,const uint8_t *data,size_t len,lin_checksum_mode_t mode) {
    (void)channel; (void)id; (void)data; (void)len; (void)mode; return -1;
}
__attribute__((weak)) int lin_port_slave_clear(uint8_t channel) {
    (void)channel; return -1;
}

__attribute__((weak)) uint64_t lin_port_tic_now(void) { return 0; }
__attribute__((weak)) void lin_port_frame_push(uint8_t channel, const lin_frame_t *frame) { (void)channel; (void)frame; }
__attribute__((weak)) bool lin_port_frame_pop(uint8_t channel, lin_frame_t *frame) { (void)channel; (void)frame; return false; }

__attribute__((weak)) void lin_port_led_master(uint8_t channel) { (void)channel; }
__attribute__((weak)) void lin_port_led_tx(uint8_t channel) { (void)channel; }
__attribute__((weak)) void lin_port_led_rx(uint8_t channel) { (void)channel; }
__attribute__((weak)) void lin_port_led_slave(uint8_t channel, bool enabled) { (void)channel; (void)enabled; }

__attribute__((weak)) int lin_port_slave_remove(uint8_t channel,uint8_t id) { (void)channel; (void)id; return -1; }
__attribute__((weak)) int lin_port_sniffer_set(uint8_t channel,uint8_t id,uint8_t len,lin_checksum_mode_t mode) { (void)channel; (void)id; (void)len; (void)mode; return -1; }
__attribute__((weak)) int lin_port_sniffer_clear(uint8_t channel) { (void)channel; return -1; }
__attribute__((weak)) int lin_port_sniffer_enable(uint8_t channel,bool enable) { (void)channel; (void)enable; return -1; }
__attribute__((weak)) bool lin_port_master_allowed(uint8_t channel) { (void)channel; return true; }

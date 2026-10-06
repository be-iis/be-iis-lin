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

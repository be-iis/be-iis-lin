#include "app_i2c.h"
#include <stdbool.h>

#if (BEIIS_APP_FIFO_SIZE & (BEIIS_APP_FIFO_SIZE - 1)) != 0
#error BEIIS_APP_FIFO_SIZE must be a power of two
#endif

#define FIFO_MASK (BEIIS_APP_FIFO_SIZE - 1)

typedef struct {
    volatile uint16_t head;
    volatile uint16_t tail;
    uint8_t data[BEIIS_APP_FIFO_SIZE];
} fifo_t;

static fifo_t rx_fifo;
static fifo_t tx_fifo;
static volatile uint8_t active_instance;

static uint16_t fifo_count(const fifo_t *fifo) {
    return (uint16_t)((fifo->head - fifo->tail) & FIFO_MASK);
}

static uint16_t fifo_free(const fifo_t *fifo) {
    return (uint16_t)((BEIIS_APP_FIFO_SIZE - 1) - fifo_count(fifo));
}

static int fifo_push(fifo_t *fifo, uint8_t value) {
    uint16_t next = (uint16_t)((fifo->head + 1) & FIFO_MASK);
    if (next == fifo->tail) {
        return 0;
    }
    fifo->data[fifo->head] = value;
    fifo->head = next;
    return 1;
}

static int fifo_pop(fifo_t *fifo, uint8_t *value) {
    if (fifo->tail == fifo->head) {
        return 0;
    }
    *value = fifo->data[fifo->tail];
    fifo->tail = (uint16_t)((fifo->tail + 1) & FIFO_MASK);
    return 1;
}

static uint8_t fifo_peek(const fifo_t *fifo, uint16_t offset) {
    return fifo->data[(fifo->tail + offset) & FIFO_MASK];
}

void beiis_app_i2c_init(void) {
    rx_fifo.head = rx_fifo.tail = 0;
    tx_fifo.head = tx_fifo.tail = 0;
    active_instance = 0;
}

size_t beiis_app_host_write(const uint8_t *src, size_t len) {
    size_t done = 0;
    while (done < len && fifo_push(&rx_fifo, src[done])) {
        ++done;
    }
    return done;
}

size_t beiis_app_host_read(uint8_t *dst, size_t len) {
    size_t done = 0;
    while (done < len && fifo_pop(&tx_fifo, &dst[done])) {
        ++done;
    }
    return done;
}

int beiis_app_host_peek(size_t offset, uint8_t *value) {
    uint16_t count = fifo_count(&tx_fifo);
    if (offset >= count) {
        return 0;
    }
    if (value) {
        *value = fifo_peek(&tx_fifo, (uint16_t)offset);
    }
    return 1;
}

size_t beiis_app_host_consume(size_t len) {
    size_t done = 0;
    uint8_t discard;
    while (done < len && fifo_pop(&tx_fifo, &discard)) {
        ++done;
    }
    return done;
}

uint8_t beiis_app_reg_read_u8(uint8_t reg) {
    uint16_t value;
    switch (reg) {
        case BEIIS_REG_APP_RX_FREE:
            value = fifo_free(&rx_fifo);
            return value > 255 ? 255 : (uint8_t)value;
        case BEIIS_REG_APP_TX_COUNT:
            value = fifo_count(&tx_fifo);
            return value > 255 ? 255 : (uint8_t)value;
        case BEIIS_REG_APP_STATUS:
            return 0x80 | (fifo_free(&rx_fifo) ? 0x01 : 0) | (fifo_count(&tx_fifo) ? 0x02 : 0);
        case BEIIS_REG_APP_VERSION:
            return BEIIS_APP_PROTOCOL_VERSION;
        case BEIIS_REG_APP_CHANNELS:
            return BEIIS_APP_USER_CHANNELS;
        case BEIIS_REG_APP_MAX_PAYLOAD_LO:
            return (uint8_t)(BEIIS_APP_MAX_PAYLOAD & 0xff);
        case BEIIS_REG_APP_MAX_PAYLOAD_HI:
            return (uint8_t)(BEIIS_APP_MAX_PAYLOAD >> 8);
        case BEIIS_REG_APP_ACTIVE_INSTANCE:
            return active_instance;
        default:
            return 0;
    }
}

void beiis_app_control(uint8_t value) {
    if (value & 0x01) {
        rx_fifo.head = rx_fifo.tail = 0;
        tx_fifo.head = tx_fifo.tail = 0;
    }
}

uint8_t beiis_app_active_instance(void) {
    return active_instance;
}

int beiis_app_set_active_instance(uint8_t instance) {
    if (instance >= BEIIS_APP_MAX_INSTANCES) {
        return -1;
    }
    active_instance = instance;
    return 0;
}

int beiis_app_rx_peek(uint8_t *channel, size_t *payload_len) {
    uint16_t count = fifo_count(&rx_fifo);
    if (count < 3) {
        return 0;
    }

    uint8_t ch = fifo_peek(&rx_fifo, 0);
    size_t len = (size_t)fifo_peek(&rx_fifo, 1) | ((size_t)fifo_peek(&rx_fifo, 2) << 8);
    if (len > BEIIS_APP_MAX_PAYLOAD || (ch >= BEIIS_APP_USER_CHANNELS && ch != BEIIS_APP_MGMT_CHANNEL)) {
        rx_fifo.tail = rx_fifo.head;
        return -1;
    }
    if (count < len + 3) {
        return 0;
    }
    if (channel) {
        *channel = ch;
    }
    if (payload_len) {
        *payload_len = len;
    }
    return 1;
}

int beiis_app_recv(uint8_t *channel, uint8_t *dst, size_t cap, size_t *payload_len) {
    uint8_t ch;
    size_t len;
    int ready = beiis_app_rx_peek(&ch, &len);
    if (ready <= 0) {
        return ready;
    }
    if (len > cap) {
        return -2;
    }

    uint8_t discard;
    fifo_pop(&rx_fifo, &discard);
    fifo_pop(&rx_fifo, &discard);
    fifo_pop(&rx_fifo, &discard);
    for (size_t i = 0; i < len; ++i) {
        fifo_pop(&rx_fifo, &dst[i]);
    }

    if (channel) {
        *channel = ch;
    }
    if (payload_len) {
        *payload_len = len;
    }
    return 1;
}

int beiis_app_try_send(uint8_t instance, uint8_t channel, const uint8_t *src, size_t len) {
    bool management = instance == 0xff && channel == BEIIS_APP_MGMT_CHANNEL;
    bool user = instance < BEIIS_APP_MAX_INSTANCES && channel < BEIIS_APP_USER_CHANNELS;
    if ((!management && !user) || len > BEIIS_APP_MAX_PAYLOAD) {
        return -1;
    }
    if (fifo_free(&tx_fifo) < len + 4) {
        return 0;
    }

    uint8_t header[4] = {
        instance,
        channel,
        (uint8_t)(len & 0xff),
        (uint8_t)((len >> 8) & 0xff),
    };

    uint16_t head = tx_fifo.head;
    for (size_t i = 0; i < sizeof(header); ++i) {
        tx_fifo.data[head] = header[i];
        head = (uint16_t)((head + 1) & FIFO_MASK);
    }
    for (size_t i = 0; i < len; ++i) {
        tx_fifo.data[head] = src[i];
        head = (uint16_t)((head + 1) & FIFO_MASK);
    }
    __asm volatile ("" ::: "memory");
    tx_fifo.head = head;
    return 1;
}

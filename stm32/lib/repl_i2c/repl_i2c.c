#include "repl_i2c.h"

#if (BEIIS_REPL_FIFO_SIZE & (BEIIS_REPL_FIFO_SIZE-1)) != 0
#error BEIIS_REPL_FIFO_SIZE must be a power of two
#endif

typedef struct {
    volatile uint16_t head,tail;
    uint8_t data[BEIIS_REPL_FIFO_SIZE];
} fifo_t;

static fifo_t rx_fifo;
static fifo_t tx_fifo;

static uint16_t count(const fifo_t *f) {
    return (uint16_t)((f->head-f->tail)&(BEIIS_REPL_FIFO_SIZE-1));
}
static uint16_t free_space(const fifo_t *f) {
    return (BEIIS_REPL_FIFO_SIZE-1)-count(f);
}
static int push(fifo_t *f,uint8_t v) {
    uint16_t n=(uint16_t)((f->head+1)&(BEIIS_REPL_FIFO_SIZE-1));
    if(n==f->tail) return 0;
    f->data[f->head]=v; f->head=n; return 1;
}
static int pop(fifo_t *f,uint8_t *v) {
    if(f->tail==f->head) return 0;
    *v=f->data[f->tail];
    f->tail=(uint16_t)((f->tail+1)&(BEIIS_REPL_FIFO_SIZE-1));
    return 1;
}

void beiis_repl_i2c_init(void) {
    rx_fifo.head=rx_fifo.tail=0;
    tx_fifo.head=tx_fifo.tail=0;
}
size_t beiis_repl_host_write(const uint8_t *s,size_t len) {
    size_t n=0; while(n<len&&push(&rx_fifo,s[n])) n++; return n;
}
size_t beiis_repl_host_read(uint8_t *d,size_t len) {
    size_t n=0; while(n<len&&pop(&tx_fifo,&d[n])) n++; return n;
}
int beiis_repl_host_peek(size_t offset,uint8_t *value) {
    uint16_t n=count(&tx_fifo);
    if(offset>=n) return 0;
    if(value) *value=tx_fifo.data[(tx_fifo.tail+offset)&(BEIIS_REPL_FIFO_SIZE-1)];
    return 1;
}
size_t beiis_repl_host_consume(size_t len) {
    size_t n=0; uint8_t discard;
    while(n<len&&pop(&tx_fifo,&discard)) n++;
    return n;
}
int beiis_repl_stdin_get(void) {
    uint8_t v; return pop(&rx_fifo,&v)?v:-1;
}
size_t beiis_repl_stdout_write(const uint8_t *s,size_t len) {
    size_t n=0; while(n<len&&push(&tx_fifo,s[n])) n++; return n;
}
uint8_t beiis_repl_reg_read_u8(uint8_t reg) {
    uint16_t n;
    switch(reg) {
        case BEIIS_REG_STATUS: return 0x80|(free_space(&rx_fifo)?1:0)|(count(&tx_fifo)?2:0);
        case BEIIS_REG_RX_FREE: n=free_space(&rx_fifo); return n>255?255:n;
        case BEIIS_REG_TX_COUNT: n=count(&tx_fifo); return n>255?255:n;
        case BEIIS_REG_VERSION: return BEIIS_REPL_PROTOCOL_VERSION;
        default: return 0;
    }
}
void beiis_repl_control(uint8_t v) {
    if(v&1) beiis_repl_i2c_init();
}

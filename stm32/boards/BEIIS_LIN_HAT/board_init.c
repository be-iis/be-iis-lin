#if !BUILDING_MBOOT

#include "py/mphal.h"
#include "irq.h"
#include "powerctrl.h"
#include "stm32g0xx_hal.h"

#include "../../lib/lin/lin.h"
#include "../../lib/repl_i2c/repl_i2c.h"
#include "../../lib/app_i2c/app_i2c.h"

#define BEIIS_REPL_I2C_ADDR (0x42)

#if __CORTEX_M == 0
#define BEIIS_IRQ_PRI_I2C (2)
#else
#define BEIIS_IRQ_PRI_I2C IRQ_PRI_I2C
#endif

static UART_HandleTypeDef lin_uart1;
static UART_HandleTypeDef lin_uart2;

typedef enum {
    LIN_SLAVE_WAIT_BREAK = 0,
    LIN_SLAVE_WAIT_SYNC,
    LIN_SLAVE_WAIT_PID,
    LIN_SLAVE_TX,
    LIN_SLAVE_RX,
} lin_slave_state_t;

typedef struct {
    volatile bool tx_enabled;
    volatile bool rx_enabled;
    volatile lin_slave_state_t state;

    uint8_t tx_id;
    uint8_t tx_data_len;
    uint8_t tx_data[8];
    lin_checksum_mode_t tx_checksum_mode;
    uint8_t tx[9];
    volatile uint8_t tx_len;
    volatile uint8_t tx_pos;

    uint8_t rx_id;
    uint8_t rx_len;
    lin_checksum_mode_t rx_checksum_mode;
    uint8_t rx_work[9];
    volatile uint8_t rx_pos;
    uint8_t rx_data[8];
    volatile bool rx_ready;
    uint8_t rx_pid;
} lin_slave_ctx_t;

static lin_slave_ctx_t lin_slave[2];

#define BEIIS_HOST_IRQ_APP_TX   (1u << 0)
#define BEIIS_HOST_IRQ_LIN1_RX  (1u << 1)
#define BEIIS_HOST_IRQ_LIN2_RX  (1u << 2)

static volatile uint8_t beiis_host_irq_sources;

static void beiis_host_irq_apply(void) {
    HAL_GPIO_WritePin(
        GPIOC,
        GPIO_PIN_6,
        beiis_host_irq_sources ? GPIO_PIN_SET : GPIO_PIN_RESET
    );
}

static void beiis_host_irq_source(uint8_t source,bool active) {
    uint32_t primask = __get_PRIMASK();
    __disable_irq();

    if (active) {
        beiis_host_irq_sources |= source;
    } else {
        beiis_host_irq_sources &= (uint8_t)~source;
    }
    beiis_host_irq_apply();

    // PRIMASK is not stacked/restored by exception return. Restore exactly
    // the state that was active on entry, including when called from an ISR.
    __set_PRIMASK(primask);
}

static uint8_t beiis_lin_rx_irq_source(uint8_t channel) {
    return channel == 1 ? BEIIS_HOST_IRQ_LIN1_RX : BEIIS_HOST_IRQ_LIN2_RX;
}

void beiis_app_host_irq_set(bool active) {
    beiis_host_irq_source(BEIIS_HOST_IRQ_APP_TX, active);
}

static bool lin_led_resolve(uint8_t channel,lin_led_t led,GPIO_TypeDef **port,uint16_t *pin) {
    if(channel==1) {
        switch(led) {
            case LIN_LED_RX:     *port=GPIOA; *pin=GPIO_PIN_5;  return true;
            case LIN_LED_TX:     *port=GPIOB; *pin=GPIO_PIN_1;  return true;
            case LIN_LED_SLAVE:  *port=GPIOA; *pin=GPIO_PIN_10; return true;
            case LIN_LED_MASTER: *port=GPIOA; *pin=GPIO_PIN_6;  return true;
            default: return false;
        }
    }
    if(channel==2) {
        switch(led) {
            case LIN_LED_RX:     *port=GPIOB; *pin=GPIO_PIN_3;  return true;
            case LIN_LED_TX:     *port=GPIOB; *pin=GPIO_PIN_4;  return true;
            case LIN_LED_SLAVE:  *port=GPIOB; *pin=GPIO_PIN_5;  return true;
            case LIN_LED_MASTER: *port=GPIOA; *pin=GPIO_PIN_15; return true;
            default: return false;
        }
    }
    return false;
}

void lin_port_led_set(uint8_t channel,lin_led_t led,bool on) {
    GPIO_TypeDef *port;
    uint16_t pin;
    if(!lin_led_resolve(channel,led,&port,&pin)) return;
    // All board LEDs are active-low (_N).
    HAL_GPIO_WritePin(port,pin,on?GPIO_PIN_RESET:GPIO_PIN_SET);
}

void lin_port_led_set_mask(uint8_t mask) {
    for(uint8_t channel=1;channel<=2;channel++) {
        for(uint8_t led=0;led<4;led++) {
            uint8_t bit=(uint8_t)(((channel-1)*4)+led);
            lin_port_led_set(channel,(lin_led_t)led,(mask&(1u<<bit))!=0);
        }
    }
}

uint8_t lin_port_led_get_mask(void) {
    uint8_t mask=0;
    for(uint8_t channel=1;channel<=2;channel++) {
        for(uint8_t led=0;led<4;led++) {
            GPIO_TypeDef *port;
            uint16_t pin;
            if(!lin_led_resolve(channel,(lin_led_t)led,&port,&pin)) continue;
            uint8_t bit=(uint8_t)(((channel-1)*4)+led);
            if((port->ODR&pin)==0) mask|=(uint8_t)(1u<<bit);
        }
    }
    return mask;
}

static volatile uint8_t i2c_reg;
static volatile uint8_t i2c_expect_reg = 1;
static volatile uint8_t i2c_payload_index;
static volatile bool i2c_system_reset_requested;
static volatile bool i2c_mboot_requested;
static volatile bool i2c_tx_stream_active;
static volatile uint16_t i2c_tx_prefetched;

static void beiis_gpio_init(void) {
    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_GPIOB_CLK_ENABLE();
    __HAL_RCC_GPIOC_CLK_ENABLE();

    GPIO_InitTypeDef g = {0};

    // LIN1 USART1: PB6 TX, PB7 RX, AF0.
    g.Pin = GPIO_PIN_6 | GPIO_PIN_7;
    g.Mode = GPIO_MODE_AF_PP;
    g.Pull = GPIO_NOPULL;
    g.Speed = GPIO_SPEED_FREQ_HIGH;
    g.Alternate = GPIO_AF0_USART1;
    HAL_GPIO_Init(GPIOB, &g);

    // LIN2 USART2: PA2 TX, PA3 RX, AF1.
    g.Pin = GPIO_PIN_2 | GPIO_PIN_3;
    g.Alternate = GPIO_AF1_USART2;
    HAL_GPIO_Init(GPIOA, &g);

    // Active-low LIN status/activity LEDs. Initialise all LEDs off.
    g.Pin = GPIO_PIN_5 | GPIO_PIN_6 | GPIO_PIN_10 | GPIO_PIN_15;
    g.Mode = GPIO_MODE_OUTPUT_PP;
    g.Pull = GPIO_NOPULL;
    g.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(GPIOA, &g);
    HAL_GPIO_WritePin(GPIOA, GPIO_PIN_5 | GPIO_PIN_6 | GPIO_PIN_10 | GPIO_PIN_15, GPIO_PIN_SET);

    g.Pin = GPIO_PIN_1 | GPIO_PIN_3 | GPIO_PIN_4 | GPIO_PIN_5;
    HAL_GPIO_Init(GPIOB, &g);
    HAL_GPIO_WritePin(GPIOB, GPIO_PIN_1 | GPIO_PIN_3 | GPIO_PIN_4 | GPIO_PIN_5, GPIO_PIN_SET);

    // TJA1021 /SLP pins. High = normal mode, low = sleep.
    g.Pin = GPIO_PIN_4 | GPIO_PIN_8;
    g.Mode = GPIO_MODE_OUTPUT_PP;
    g.Pull = GPIO_NOPULL;
    g.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(GPIOA, &g);
    HAL_GPIO_WritePin(GPIOA, GPIO_PIN_4 | GPIO_PIN_8, GPIO_PIN_SET);

    // Isolated host IRQ: PC6. Active-high on the STM32 side.
    // The Linux side listens for both edges so isolation polarity is irrelevant.
    g.Pin = GPIO_PIN_6;
    g.Mode = GPIO_MODE_OUTPUT_PP;
    g.Pull = GPIO_NOPULL;
    g.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(GPIOC, &g);
    beiis_host_irq_sources = 0;
    HAL_GPIO_WritePin(GPIOC, GPIO_PIN_6, GPIO_PIN_RESET);

    // I2C1 target: PB8 SCL, PB9 SDA, AF6 open-drain.
    g.Pin = GPIO_PIN_8 | GPIO_PIN_9;
    g.Mode = GPIO_MODE_AF_OD;
    g.Pull = GPIO_NOPULL;
    g.Speed = GPIO_SPEED_FREQ_HIGH;
    g.Alternate = GPIO_AF6_I2C1;
    HAL_GPIO_Init(GPIOB, &g);
}

static void beiis_i2c_target_init(void) {
    __HAL_RCC_I2C1_CLK_ENABLE();

    beiis_repl_i2c_init();
    beiis_app_i2c_init();
    i2c_reg = BEIIS_REG_STATUS;
    i2c_expect_reg = 1;
    i2c_payload_index = 0;
    i2c_system_reset_requested = false;
    i2c_mboot_requested = false;
    i2c_tx_stream_active = false;
    i2c_tx_prefetched = 0;

    I2C1->CR1 = 0;
    I2C1->CR2 = 0;
    I2C1->OAR1 = 0;
    I2C1->OAR2 = 0;

    // Target mode does not generate SCL; keep a conservative timing value
    // so SDA setup/hold filtering is defined.
    I2C1->TIMINGR = 0x10B17DB5;
    I2C1->TIMEOUTR = 0;

    I2C1->OAR1 = I2C_OAR1_OA1EN | ((uint32_t)BEIIS_REPL_I2C_ADDR << 1);
    I2C1->CR1 = I2C_CR1_ADDRIE | I2C_CR1_RXIE | I2C_CR1_TXIE |
        I2C_CR1_STOPIE | I2C_CR1_ERRIE | I2C_CR1_PE;

    NVIC_SetPriority(I2C1_IRQn, BEIIS_IRQ_PRI_I2C);
    NVIC_EnableIRQ(I2C1_IRQn);
}

void BEIIS_LIN_HAT_board_early_init(void) {
    beiis_gpio_init();
    beiis_i2c_target_init();
}

static void i2c_rx_byte(uint8_t v) {
    if (i2c_expect_reg) {
        i2c_reg = v;
        i2c_expect_reg = 0;
        i2c_payload_index = 0;
        return;
    }

    switch (i2c_reg) {
        case BEIIS_REG_RX_DATA:
            (void)beiis_repl_host_write(&v, 1);
            break;
        case BEIIS_REG_CONTROL:
            if (i2c_payload_index == 0) {
                beiis_repl_control(v);
            }
            break;
        case BEIIS_REG_APP_RX_DATA:
            (void)beiis_app_host_write(&v, 1);
            break;
        case BEIIS_REG_APP_CONTROL:
            if (i2c_payload_index == 0) {
                beiis_app_control(v);
                if (v & 0x40) {
                    // Defer mboot entry until STOPF so the current I2C write
                    // completes before the application resets into mboot.
                    i2c_mboot_requested = true;
                } else if (v & 0x80) {
                    // Defer reset until STOPF so the current I2C write can
                    // complete cleanly before the MCU restarts.
                    i2c_system_reset_requested = true;
                }
            }
            break;
        case BEIIS_REG_APP_ACTIVE_INSTANCE:
            if (i2c_payload_index == 0) {
                (void)beiis_app_set_active_instance(v);
            }
            break;
        default:
            break;
    }
    ++i2c_payload_index;
}

static bool i2c_tx_is_stream_reg(void) {
    return i2c_reg == BEIIS_REG_TX_DATA || i2c_reg == BEIIS_REG_APP_TX_DATA;
}

static uint8_t i2c_tx_stream_peek(uint16_t offset) {
    uint8_t v = 0;
    if (i2c_reg == BEIIS_REG_TX_DATA) {
        (void)beiis_repl_host_peek(offset, &v);
    } else if (i2c_reg == BEIIS_REG_APP_TX_DATA) {
        (void)beiis_app_host_peek(offset, &v);
    }
    return v;
}

static void i2c_tx_stream_consume(uint16_t count) {
    if (i2c_reg == BEIIS_REG_TX_DATA) {
        (void)beiis_repl_host_consume(count);
    } else if (i2c_reg == BEIIS_REG_APP_TX_DATA) {
        (void)beiis_app_host_consume(count);
    }
}

static uint8_t i2c_tx_register_byte(void) {
    uint8_t v = 0;
    switch (i2c_reg) {
        case BEIIS_REG_STATUS:
        case BEIIS_REG_RX_FREE:
        case BEIIS_REG_TX_COUNT:
        case BEIIS_REG_VERSION:
            v = beiis_repl_reg_read_u8(i2c_reg);
            break;
        case BEIIS_REG_APP_RX_FREE:
        case BEIIS_REG_APP_TX_COUNT:
        case BEIIS_REG_APP_STATUS:
        case BEIIS_REG_APP_VERSION:
        case BEIIS_REG_APP_CHANNELS:
        case BEIIS_REG_APP_MAX_PAYLOAD_LO:
        case BEIIS_REG_APP_MAX_PAYLOAD_HI:
        case BEIIS_REG_APP_ACTIVE_INSTANCE:
            v = beiis_app_reg_read_u8(i2c_reg);
            break;
        default:
            v = 0;
            break;
    }
    return v;
}

void I2C1_IRQHandler(void) {
    uint32_t isr = I2C1->ISR;

    if (isr & I2C_ISR_ADDR) {
        bool read = (isr & I2C_ISR_DIR) != 0;

        // Flush any byte left in TXDR from the previous read transaction.
        // Stream registers use deferred FIFO consumption: bytes loaded into
        // TXDR are only peeked here and committed when the read actually ends.
        if (read) {
            I2C1->ISR = I2C_ISR_TXE;
            i2c_tx_stream_active = i2c_tx_is_stream_reg();
            i2c_tx_prefetched = 0;
        } else {
            i2c_tx_stream_active = false;
            i2c_tx_prefetched = 0;
        }

        I2C1->ICR = I2C_ICR_ADDRCF;
        if (!read) {
            i2c_expect_reg = 1;
            i2c_payload_index = 0;
        }
        isr = I2C1->ISR;
    }

    if (isr & I2C_ISR_RXNE) {
        i2c_rx_byte((uint8_t)I2C1->RXDR);
    }

    if (isr & I2C_ISR_NACKF) {
        // For a stream read there are two legal timing cases:
        //
        // 1. NACKF and TXIS arrive together.  TXIS is asking for the byte
        //    *after* the final byte, and we have not prefetched it yet.
        //    Every prefetched byte was therefore actually clocked by the host.
        //
        // 2. TXIS was serviced in an earlier IRQ before NACKF became visible.
        //    In that case the last prefetched byte is speculative and was never
        //    clocked.  Commit all but that final byte.
        if (i2c_tx_stream_active) {
            uint16_t consumed = i2c_tx_prefetched;
            if (!(isr & I2C_ISR_TXIS) && consumed > 0) {
                --consumed;
            }
            i2c_tx_stream_consume(consumed);
            i2c_tx_stream_active = false;
            i2c_tx_prefetched = 0;
        }

        I2C1->ICR = I2C_ICR_NACKCF;

        // TXIS may still require service even though the master has ended the
        // transfer.  Feed a disposable byte; the next ADDR event flushes TXDR.
        if (isr & I2C_ISR_TXIS) {
            I2C1->TXDR = 0;
        }
    } else if (isr & I2C_ISR_TXIS) {
        if (i2c_tx_stream_active) {
            I2C1->TXDR = i2c_tx_stream_peek(i2c_tx_prefetched);
            ++i2c_tx_prefetched;
        } else {
            I2C1->TXDR = i2c_tx_register_byte();
        }
    }

    if (isr & I2C_ISR_STOPF) {
        // Normally target-transmit completion is handled by NACKF.  Keep a
        // conservative STOP fallback for controllers that terminate a read
        // without presenting NACKF to this IRQ snapshot.
        if (i2c_tx_stream_active) {
            uint16_t consumed = i2c_tx_prefetched;
            if (consumed > 0) {
                --consumed;
            }
            i2c_tx_stream_consume(consumed);
            i2c_tx_stream_active = false;
            i2c_tx_prefetched = 0;
        }

        I2C1->ICR = I2C_ICR_STOPCF;
        i2c_expect_reg = 1;
        i2c_payload_index = 0;
        if (i2c_mboot_requested) {
            i2c_mboot_requested = false;
            powerctrl_enter_bootloader(0x70ad0042, 0x08000000);
        }
        if (i2c_system_reset_requested) {
            i2c_system_reset_requested = false;
            NVIC_SystemReset();
        }
    }

    uint32_t err = I2C1->ISR;
    uint32_t clear = 0;
    if (err & I2C_ISR_BERR) clear |= I2C_ICR_BERRCF;
    if (err & I2C_ISR_ARLO) clear |= I2C_ICR_ARLOCF;
    if (err & I2C_ISR_OVR) clear |= I2C_ICR_OVRCF;
    if (clear) I2C1->ICR = clear;
}

static UART_HandleTypeDef *lin_handle(uint8_t channel) {
    if (channel == 1) return &lin_uart1;
    if (channel == 2) return &lin_uart2;
    return NULL;
}

static USART_TypeDef *lin_instance(uint8_t channel) {
    if (channel == 1) return USART1;
    if (channel == 2) return USART2;
    return NULL;
}

int lin_port_set_baudrate(uint8_t channel,uint32_t baudrate) {
    UART_HandleTypeDef *h = lin_handle(channel);
    USART_TypeDef *inst = lin_instance(channel);
    if (!h || !inst) return -1;

    if (channel == 1) {
        __HAL_RCC_USART1_CLK_ENABLE();
    } else {
        __HAL_RCC_USART2_CLK_ENABLE();
    }

    memset(h, 0, sizeof(*h));
    h->Instance = inst;
    h->Init.BaudRate = baudrate;
    h->Init.WordLength = UART_WORDLENGTH_8B;
    h->Init.StopBits = UART_STOPBITS_1;
    h->Init.Parity = UART_PARITY_NONE;
    h->Init.Mode = UART_MODE_TX_RX;
    h->Init.HwFlowCtl = UART_HWCONTROL_NONE;
    h->Init.OverSampling = UART_OVERSAMPLING_16;
    h->Init.OneBitSampling = UART_ONE_BIT_SAMPLE_DISABLE;
    h->Init.ClockPrescaler = UART_PRESCALER_DIV1;
    h->AdvancedInit.AdvFeatureInit = UART_ADVFEATURE_NO_INIT;

    return HAL_LIN_Init(h, UART_LINBREAKDETECTLENGTH_11B) == HAL_OK ? 0 : -1;
}

int lin_port_send_break(uint8_t channel) {
    UART_HandleTypeDef *h = lin_handle(channel);
    if (!h || h->gState == HAL_UART_STATE_RESET) return -1;
    return HAL_LIN_SendBreak(h) == HAL_OK ? 0 : -1;
}

int lin_port_tx(uint8_t channel,const uint8_t *data,size_t len,uint32_t timeout_ms) {
    UART_HandleTypeDef *h = lin_handle(channel);
    if (!h || !data || len == 0) return -1;

    USART_TypeDef *u = h->Instance;

    // The TJA1021 mirrors our own transmitted LIN bits on RXD. Disable the
    // USART receiver during a master transmission so header/data echo never
    // enters RDR. HAL_UART_Transmit waits for TC before returning, so the
    // receiver is re-enabled before the slave response space starts.
    uint32_t had_re = u->CR1 & USART_CR1_RE;
    u->CR1 &= ~USART_CR1_RE;

    HAL_StatusTypeDef st = HAL_UART_Transmit(h, (uint8_t *)data, (uint16_t)len, timeout_ms);

    __HAL_UART_SEND_REQ(h, UART_RXDATA_FLUSH_REQUEST);
    __HAL_UART_CLEAR_OREFLAG(h);
    if (had_re) {
        u->CR1 |= USART_CR1_RE;
    }

    return st == HAL_OK ? 0 : -1;
}

int lin_port_rx(uint8_t channel,uint8_t *data,size_t len,uint32_t timeout_ms) {
    UART_HandleTypeDef *h = lin_handle(channel);
    if (!h || !data || len == 0) return -1;
    return HAL_UART_Receive(h, data, (uint16_t)len, timeout_ms) == HAL_OK ? 0 : -1;
}


static lin_slave_ctx_t *lin_slave_ctx(uint8_t channel) {
    if (channel < 1 || channel > 2) return NULL;
    return &lin_slave[channel - 1];
}

int lin_port_slave_set(uint8_t channel,uint8_t id,const uint8_t *data,size_t len,lin_checksum_mode_t mode) {
    UART_HandleTypeDef *h = lin_handle(channel);
    lin_slave_ctx_t *ctx = lin_slave_ctx(channel);
    if (!h || !ctx || !data || len > 8 || id > 0x3f || h->gState == HAL_UART_STATE_RESET) return -1;

    uint32_t primask = __get_PRIMASK();
    __disable_irq();

    ctx->tx_id = id;
    ctx->tx_data_len = (uint8_t)len;
    memcpy(ctx->tx_data, data, len);
    ctx->tx_checksum_mode = mode;
    ctx->tx_len = 0;
    ctx->tx_pos = 0;
    ctx->state = LIN_SLAVE_WAIT_BREAK;
    ctx->tx_enabled = true;
    lin_port_led_set(channel,LIN_LED_RX,false);
    lin_port_led_set(channel,LIN_LED_TX,false);
    lin_port_led_set(channel,LIN_LED_SLAVE,true);

    USART_TypeDef *u = h->Instance;
    u->ICR = USART_ICR_LBDCF | USART_ICR_ORECF | USART_ICR_FECF | USART_ICR_NECF;
    u->CR2 |= USART_CR2_LBDIE;
    u->CR1 |= USART_CR1_RXNEIE_RXFNEIE;

    IRQn_Type irqn = channel == 1 ? USART1_IRQn : USART2_IRQn;
    NVIC_SetPriority(irqn, IRQ_PRI_UART);
    NVIC_EnableIRQ(irqn);

    if (!primask) __enable_irq();
    return 0;
}

int lin_port_slave_clear(uint8_t channel) {
    UART_HandleTypeDef *h = lin_handle(channel);
    lin_slave_ctx_t *ctx = lin_slave_ctx(channel);
    if (!h || !ctx) return -1;

    uint32_t primask = __get_PRIMASK();
    __disable_irq();

    ctx->tx_enabled = false;
    ctx->state = LIN_SLAVE_WAIT_BREAK;
    ctx->tx_len = 0;
    ctx->tx_pos = 0;
    lin_port_led_set(channel,LIN_LED_RX,false);
    lin_port_led_set(channel,LIN_LED_TX,false);

    h->Instance->CR1 &= ~USART_CR1_TXEIE_TXFNFIE;
    if (!ctx->rx_enabled) {
        h->Instance->CR2 &= ~USART_CR2_LBDIE;
        h->Instance->CR1 &= ~USART_CR1_RXNEIE_RXFNEIE;
        lin_port_led_set(channel,LIN_LED_SLAVE,false);
    }

    if (!primask) __enable_irq();
    return 0;
}

int lin_port_slave_rx_set(uint8_t channel,uint8_t id,size_t len,lin_checksum_mode_t mode) {
    UART_HandleTypeDef *h = lin_handle(channel);
    lin_slave_ctx_t *ctx = lin_slave_ctx(channel);
    if (!h || !ctx || len > 8 || id > 0x3f || h->gState == HAL_UART_STATE_RESET) return -1;

    uint32_t primask = __get_PRIMASK();
    __disable_irq();

    ctx->rx_id = id;
    ctx->rx_len = (uint8_t)len;
    ctx->rx_checksum_mode = mode;
    ctx->rx_pos = 0;
    ctx->rx_ready = false;
    beiis_host_irq_source(beiis_lin_rx_irq_source(channel), false);
    ctx->state = LIN_SLAVE_WAIT_BREAK;
    ctx->rx_enabled = true;
    lin_port_led_set(channel,LIN_LED_RX,false);
    lin_port_led_set(channel,LIN_LED_SLAVE,true);

    USART_TypeDef *u = h->Instance;
    u->ICR = USART_ICR_LBDCF | USART_ICR_ORECF | USART_ICR_FECF | USART_ICR_NECF;
    u->CR2 |= USART_CR2_LBDIE;
    u->CR1 |= USART_CR1_RXNEIE_RXFNEIE;

    IRQn_Type irqn = channel == 1 ? USART1_IRQn : USART2_IRQn;
    NVIC_SetPriority(irqn, IRQ_PRI_UART);
    NVIC_EnableIRQ(irqn);

    if (!primask) __enable_irq();
    return 0;
}

int lin_port_slave_rx_recv(uint8_t channel,uint8_t *data,size_t cap,size_t *len) {
    lin_slave_ctx_t *ctx = lin_slave_ctx(channel);
    if (!ctx || !data || !len) return -1;

    uint32_t primask = __get_PRIMASK();
    __disable_irq();

    if (!ctx->rx_ready) {
        if (!primask) __enable_irq();
        return 0;
    }
    if (cap < ctx->rx_len) {
        if (!primask) __enable_irq();
        return -1;
    }

    memcpy(data, ctx->rx_data, ctx->rx_len);
    *len = ctx->rx_len;
    ctx->rx_ready = false;
    beiis_host_irq_source(beiis_lin_rx_irq_source(channel), false);

    if (!primask) __enable_irq();
    return 1;
}

void beiis_lin_uart_irq(uint8_t channel) {
    UART_HandleTypeDef *h = lin_handle(channel);
    lin_slave_ctx_t *ctx = lin_slave_ctx(channel);
    if (!h || !ctx) return;

    USART_TypeDef *u = h->Instance;
    uint32_t isr = u->ISR;

    if (!ctx->tx_enabled && !ctx->rx_enabled) {
        if (isr & USART_ISR_RXNE_RXFNE) {
            (void)u->RDR;
        }
        if (isr & USART_ISR_LBDF) {
            u->ICR = USART_ICR_LBDCF;
        }
        return;
    }

    if (isr & USART_ISR_LBDF) {
        u->ICR = USART_ICR_LBDCF;
        lin_port_led_set(channel,LIN_LED_RX,true);
        ctx->state = LIN_SLAVE_WAIT_SYNC;
        ctx->tx_pos = 0;
        ctx->tx_len = 0;
        ctx->rx_pos = 0;
    }

    if (isr & USART_ISR_RXNE_RXFNE) {
        uint8_t v = (uint8_t)u->RDR;

        if (ctx->state == LIN_SLAVE_WAIT_SYNC) {
            ctx->state = (v == 0x55) ? LIN_SLAVE_WAIT_PID : LIN_SLAVE_WAIT_BREAK;
            if (ctx->state == LIN_SLAVE_WAIT_BREAK) {
                lin_port_led_set(channel,LIN_LED_RX,false);
            }
        } else if (ctx->state == LIN_SLAVE_WAIT_PID) {
            if (!lin_pid_valid(v)) {
                ctx->state = LIN_SLAVE_WAIT_BREAK;
                lin_port_led_set(channel,LIN_LED_RX,false);
            } else {
                uint8_t id = v & 0x3f;
                if (ctx->tx_enabled && id == ctx->tx_id) {
                    memcpy(ctx->tx, ctx->tx_data, ctx->tx_data_len);
                    ctx->tx[ctx->tx_data_len] = lin_checksum(v, ctx->tx_data, ctx->tx_data_len, ctx->tx_checksum_mode);
                    ctx->tx_len = ctx->tx_data_len + 1;
                    ctx->tx_pos = 0;
                    ctx->state = LIN_SLAVE_TX;
                    lin_port_led_set(channel,LIN_LED_RX,false);
                    lin_port_led_set(channel,LIN_LED_TX,true);
                    u->CR1 |= USART_CR1_TXEIE_TXFNFIE;
                } else if (ctx->rx_enabled && id == ctx->rx_id) {
                    ctx->rx_pid = v;
                    ctx->rx_pos = 0;
                    ctx->state = LIN_SLAVE_RX;
                } else {
                    ctx->state = LIN_SLAVE_WAIT_BREAK;
                    lin_port_led_set(channel,LIN_LED_RX,false);
                }
            }
        } else if (ctx->state == LIN_SLAVE_RX) {
            if (ctx->rx_pos < sizeof(ctx->rx_work)) {
                ctx->rx_work[ctx->rx_pos++] = v;
            } else {
                ctx->state = LIN_SLAVE_WAIT_BREAK;
                lin_port_led_set(channel,LIN_LED_RX,false);
            }

            if (ctx->state == LIN_SLAVE_RX && ctx->rx_pos == (uint8_t)(ctx->rx_len + 1)) {
                uint8_t expected = lin_checksum(
                    ctx->rx_pid,
                    ctx->rx_work,
                    ctx->rx_len,
                    ctx->rx_checksum_mode
                );
                if (ctx->rx_work[ctx->rx_len] == expected) {
                    memcpy(ctx->rx_data, ctx->rx_work, ctx->rx_len);
                    __asm volatile ("" ::: "memory");
                    ctx->rx_ready = true;
                    beiis_host_irq_source(beiis_lin_rx_irq_source(channel), true);
                }
                ctx->state = LIN_SLAVE_WAIT_BREAK;
                lin_port_led_set(channel,LIN_LED_RX,false);
            }
        }
    }

    if ((isr & USART_ISR_TXE_TXFNF) && (u->CR1 & USART_CR1_TXEIE_TXFNFIE) && ctx->state == LIN_SLAVE_TX) {
        if (ctx->tx_pos < ctx->tx_len) {
            u->TDR = ctx->tx[ctx->tx_pos++];
        } else {
            u->CR1 &= ~USART_CR1_TXEIE_TXFNFIE;
            ctx->state = LIN_SLAVE_WAIT_BREAK;
            lin_port_led_set(channel,LIN_LED_TX,false);
        }
    }

    uint32_t err = u->ISR;
    uint32_t clear = 0;
    if (err & USART_ISR_ORE) clear |= USART_ICR_ORECF;
    if (err & USART_ISR_FE) clear |= USART_ICR_FECF;
    if (err & USART_ISR_NE) clear |= USART_ICR_NECF;
    if (clear) u->ICR = clear;
}

#endif // !BUILDING_MBOOT

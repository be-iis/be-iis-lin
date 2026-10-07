#include "lin.h"
#include <string.h>

static bool valid_channel(uint8_t channel) {
    return channel == 1 || channel == 2;
}

static void set_master_active(uint8_t channel,bool active) {
    lin_port_led_set(channel,LIN_LED_MASTER,active);
}

static void set_slave_enabled(uint8_t channel,bool enabled) {
    lin_port_led_set(channel,LIN_LED_SLAVE,enabled);
}

uint8_t lin_make_pid(uint8_t id) {
    id&=0x3f;
    uint8_t i0=(id>>0)&1,i1=(id>>1)&1,i2=(id>>2)&1,i3=(id>>3)&1,i4=(id>>4)&1,i5=(id>>5)&1;
    uint8_t p0=i0^i1^i2^i4;
    uint8_t p1=!(i1^i3^i4^i5);
    return id|(p0<<6)|(p1<<7);
}

bool lin_pid_valid(uint8_t pid) {
    return lin_make_pid(pid&0x3f)==pid;
}

uint8_t lin_checksum(uint8_t pid,const uint8_t *data,size_t len,lin_checksum_mode_t mode) {
    uint16_t sum=mode==LIN_CHECKSUM_ENHANCED?pid:0;
    for(size_t i=0;i<len;i++) {
        sum+=data[i];
        if(sum>0xff) sum=(sum&0xff)+1;
    }
    return (uint8_t)(~sum);
}

lin_result_t lin_init(uint8_t channel,uint32_t baudrate) {
    if(!valid_channel(channel) || baudrate < 1000 || baudrate > 20000) return LIN_ERR_ARG;
    return lin_port_set_baudrate(channel,baudrate)==0?LIN_OK:LIN_ERR_IO;
}

static lin_result_t send_header(uint8_t channel,uint8_t id,uint32_t timeout_ms) {
    uint8_t h[2]={0x55,lin_make_pid(id)};
    if(lin_port_send_break(channel)!=0) return LIN_ERR_IO;
    if(lin_port_tx(channel,h,sizeof(h),timeout_ms)!=0) return LIN_ERR_IO;
    return LIN_OK;
}

lin_result_t lin_master_send(uint8_t channel,const lin_frame_t *f,lin_checksum_mode_t mode,uint32_t timeout_ms) {
    if(!valid_channel(channel)||!f||f->id>0x3f||f->len>8) return LIN_ERR_ARG;
    set_master_active(channel,true);
    lin_port_led_set(channel,LIN_LED_TX,true);
    lin_result_t r=send_header(channel,f->id,timeout_ms);
    if(r==LIN_OK) {
        uint8_t b[9];
        memcpy(b,f->data,f->len);
        b[f->len]=lin_checksum(lin_make_pid(f->id),f->data,f->len,mode);
        r=lin_port_tx(channel,b,f->len+1,timeout_ms)==0?LIN_OK:LIN_ERR_IO;
    }
    lin_port_led_set(channel,LIN_LED_TX,false);
    set_master_active(channel,false);
    return r;
}

lin_result_t lin_master_request(uint8_t channel,uint8_t id,uint8_t len,lin_checksum_mode_t mode,lin_frame_t *out,uint32_t timeout_ms) {
    if(!valid_channel(channel)||!out||id>0x3f||len>8) return LIN_ERR_ARG;
    set_master_active(channel,true);
    lin_port_led_set(channel,LIN_LED_TX,true);
    lin_result_t r=send_header(channel,id,timeout_ms);
    lin_port_led_set(channel,LIN_LED_TX,false);
    if(r!=LIN_OK) {
        set_master_active(channel,false);
        return r;
    }
    uint8_t b[9];
    lin_port_led_set(channel,LIN_LED_RX,true);
    int rx=lin_port_rx(channel,b,len+1,timeout_ms);
    lin_port_led_set(channel,LIN_LED_RX,false);
    if(rx!=0) {
        set_master_active(channel,false);
        return LIN_ERR_TIMEOUT;
    }
    if(b[len]!=lin_checksum(lin_make_pid(id),b,len,mode)) {
        set_master_active(channel,false);
        return LIN_ERR_CHECKSUM;
    }
    out->id=id; out->len=len; memcpy(out->data,b,len);
    set_master_active(channel,false);
    return LIN_OK;
}

lin_result_t lin_slave_set(uint8_t channel,uint8_t id,const uint8_t *data,size_t len,lin_checksum_mode_t mode) {
    if(!valid_channel(channel)||id>0x3f||!data||len>8) return LIN_ERR_ARG;
    int r=lin_port_slave_set(channel,id,data,len,mode);
    if(r==0) set_slave_enabled(channel,true);
    return r==0?LIN_OK:LIN_ERR_IO;
}

lin_result_t lin_slave_clear(uint8_t channel) {
    if(!valid_channel(channel)) return LIN_ERR_ARG;
    int r=lin_port_slave_clear(channel);
    if(r==0) set_slave_enabled(channel,false);
    return r==0?LIN_OK:LIN_ERR_IO;
}


lin_result_t lin_master_request_raw(uint8_t channel,uint8_t id,uint8_t *buf,size_t len,uint32_t timeout_ms) {
    if(!valid_channel(channel)||!buf||id>0x3f||len==0||len>9) return LIN_ERR_ARG;
    set_master_active(channel,true);
    lin_port_led_set(channel,LIN_LED_TX,true);
    lin_result_t r=send_header(channel,id,timeout_ms);
    lin_port_led_set(channel,LIN_LED_TX,false);
    if(r!=LIN_OK) {
        set_master_active(channel,false);
        return r;
    }
    lin_port_led_set(channel,LIN_LED_RX,true);
    int rx=lin_port_rx(channel,buf,len,timeout_ms);
    lin_port_led_set(channel,LIN_LED_RX,false);
    set_master_active(channel,false);
    return rx==0?LIN_OK:LIN_ERR_TIMEOUT;
}

void lin_led_set_mask(uint8_t mask) {
    lin_port_led_set_mask(mask);
}

uint8_t lin_led_get_mask(void) {
    return lin_port_led_get_mask();
}
